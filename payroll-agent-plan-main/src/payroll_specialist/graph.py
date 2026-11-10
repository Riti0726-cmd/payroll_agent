"""Compile the payroll specialist StateGraph and export `graph` for langgraph.json."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Sequence

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from config import get_llm_base_url, require_foundry_settings, require_llm_api_key
from models import ChangelistBuildResult, ClassificationResult, ValidationResult
from nodes import make_drafting_node, make_intake_node
from state import PayrollState
from structured_output import with_structured
from telemetry import agent_run_span, configure_telemetry
from tools.snowflake_mcp import get_qa_tools
from triage.orchestrator import TriageOrchestrator
from triage.email_graph import build_email_processing_graph, run_email_graph

load_dotenv()

logger = logging.getLogger("payroll-specialist")

# Seed SNOWFLAKE_* from mcp_config.json when present (Cursor-compatible).
try:
    from tools.mcp_config import apply_mcp_config_to_env, find_mcp_config_path, load_mcp_config

    _mcp_path = find_mcp_config_path()
    if _mcp_path is not None:
        apply_mcp_config_to_env(load_mcp_config(_mcp_path))
except Exception as _mcp_exc:  # pragma: no cover - best effort at import
    logger.debug("mcp_config bootstrap skipped: %s", _mcp_exc)


def _infer_mode(payload: Any) -> str:
    text = str(payload)
    if "TRIAGE_RUN" in text.upper() or '"command": "triage"' in text.lower() or '"command":"triage"' in text.lower():
        return "triage"
    return "unsupported"


class _InstrumentedGraph:
    """Wrap compiled graph so each invoke opens an agent_run span with step children."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    @property
    def nodes(self):
        return self._graph.nodes

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        mode = _infer_mode(input)
        with agent_run_span(mode=mode):
            result = await self._graph.ainvoke(input, config=config, **kwargs)
            return result

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        mode = _infer_mode(input)
        with agent_run_span(mode=mode):
            return self._graph.invoke(input, config=config, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._graph, name)


def build_chat_model(
    project_endpoint: Optional[str] = None,
    deployment: Optional[str] = None,
    disable_streaming: bool = False,
    api_key: Optional[str] = None,
) -> ChatOpenAI:
    """Build ChatOpenAI against Foundry Responses using a static API key (no Entra ID)."""
    if not project_endpoint or not deployment:
        project_endpoint, deployment = require_foundry_settings()
    key = (api_key or require_llm_api_key()).strip()
    base_url = get_llm_base_url(project_endpoint)

    return ChatOpenAI(
        model=deployment,
        base_url=base_url,
        api_key=key,
        default_headers={"api-key": key},
        use_responses_api=True,
        output_version="responses/v1",
        temperature=0.0,
        disable_streaming=disable_streaming,
    )


def create_payroll_graph(
    model: Optional[Any] = None,
    tools: Optional[Sequence[Any]] = None,
    *,
    triage_orchestrator: Optional[TriageOrchestrator] = None,
    enable_telemetry: bool = True,
) -> Any:
    """Compile Foundry Responses StateGraph: TRIAGE_RUN only (Q&A → POST /qa)."""
    if enable_telemetry:
        configure_telemetry()

    if model is None:
        classifier_model = build_chat_model(disable_streaming=True)
        qa_model = build_chat_model(disable_streaming=True)
        drafter_model = build_chat_model(disable_streaming=False)
        routing_model = build_chat_model(disable_streaming=True)
    else:
        classifier_model = model
        qa_model = model
        drafter_model = model
        routing_model = model

    qa_tools = list(tools) if tools is not None else get_qa_tools()
    classifier_llm = with_structured(classifier_model, ClassificationResult)
    qa_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    validation_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    validation_model = with_structured(qa_model, ValidationResult)
    changelist_llm = qa_model.bind_tools(qa_tools) if qa_tools else qa_model
    changelist_model = with_structured(qa_model, ChangelistBuildResult)

    # Per-email classify/QA/draft/route lives only in this subgraph (mailbox triage).
    email_graph = build_email_processing_graph(
        classifier_llm=classifier_llm,
        qa_llm=qa_llm,
        qa_model=qa_model,
        qa_tools=qa_tools,
        drafter_model=drafter_model,
        routing_model=routing_model,
        validation_llm=validation_llm,
        validation_model=validation_model,
        changelist_llm=changelist_llm,
        changelist_model=changelist_model,
    )

    async def process_email_fn(query: str) -> dict:
        return await run_email_graph(email_graph, query)

    if triage_orchestrator is None:
        orchestrator = TriageOrchestrator(process_email_fn=process_email_fn)
    else:
        orchestrator = triage_orchestrator
        if getattr(orchestrator, "process_email_fn", None) is None:
            orchestrator.process_email_fn = process_email_fn

    async def triage_runner(*, specialist_id: str, mailbox_id: str | None = None) -> dict:
        return await orchestrator.run(specialist_id=specialist_id, mailbox_id=mailbox_id)

    intake_node = make_intake_node(triage_runner=triage_runner)
    drafting_specialist_node = make_drafting_node(drafter_model)

    def route_after_intake(state: PayrollState) -> str:
        if state.get("mode") == "triage" and state.get("triage_summary"):
            return "drafting_specialist"
        return "unsupported"

    workflow = StateGraph(PayrollState)
    workflow.add_node("intake", intake_node)
    workflow.add_node("drafting_specialist", drafting_specialist_node)

    workflow.add_edge(START, "intake")
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "drafting_specialist": "drafting_specialist",
            "unsupported": END,
        },
    )
    workflow.add_edge("drafting_specialist", END)

    compiled = workflow.compile()
    return _InstrumentedGraph(compiled)


def _try_export_graph() -> Any:
    """Best-effort compiled graph for langgraph.json (requires Foundry env in prod)."""
    if os.environ.get("PAYROLL_SKIP_GRAPH_EXPORT", "").strip() in ("1", "true", "yes"):
        return None
    try:
        return create_payroll_graph()
    except Exception as exc:
        logger.info("graph export deferred (env not ready): %s", exc)
        return None


# LangGraph / LangSmith convention — may be None until Foundry env is available
graph = _try_export_graph()
