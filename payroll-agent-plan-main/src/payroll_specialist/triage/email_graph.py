"""Per-email LangGraph subgraph: classifier → validation → qa | changelist | draft | route."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from models import ChangelistBuildResult, ClassificationResult, ValidationResult
from nodes import (
    make_changelist_node,
    make_classifier_node,
    make_drafting_node,
    make_qa_node,
    make_routing_node,
    make_validation_node,
    route_after_validation,
    route_by_category,
)
from state import PayrollState
from structured_output import with_structured


def build_email_processing_graph(
    *,
    classifier_llm: Any,
    qa_llm: Any,
    qa_model: Any,
    qa_tools: Sequence[Any],
    drafter_model: Any,
    routing_model: Any,
    validation_llm: Any | None = None,
    validation_model: Any | None = None,
    changelist_llm: Any | None = None,
    changelist_model: Any | None = None,
) -> Any:
    """Compile START → classifier → validation → category branch."""
    tools_list = list(qa_tools or [])
    classifier_node = make_classifier_node(classifier_llm)
    # create_agent binds MCP tools — pass unbound chat model (not bind_tools wrappers).
    validation_node = make_validation_node(
        qa_model,
        validation_model
        if validation_model is not None
        else with_structured(qa_model, ValidationResult),
        tools_list,
    )
    qa_specialist_node = make_qa_node(qa_llm, qa_model, tools_list)
    changelist_node = make_changelist_node(
        qa_model,
        changelist_model
        if changelist_model is not None
        else with_structured(qa_model, ChangelistBuildResult),
        tools_list,
    )
    drafting_specialist_node = make_drafting_node(drafter_model)
    routing_agent_node = make_routing_node(routing_model)

    workflow = StateGraph(PayrollState)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("validation_agent", validation_node)
    workflow.add_node("qa_specialist", qa_specialist_node)
    workflow.add_node("changelist_agent", changelist_node)
    workflow.add_node("drafting_specialist", drafting_specialist_node)
    workflow.add_node("routing_agent", routing_agent_node)

    workflow.add_edge(START, "classifier")
    workflow.add_conditional_edges(
        "classifier",
        route_by_category,
        {
            "validation_agent": "validation_agent",
            "routing_agent": "routing_agent",
        },
    )
    workflow.add_conditional_edges(
        "validation_agent",
        route_after_validation,
        {
            "qa_specialist": "qa_specialist",
            "changelist_agent": "changelist_agent",
            "drafting_specialist": "drafting_specialist",
            "routing_agent": "routing_agent",
        },
    )
    workflow.add_edge("qa_specialist", "drafting_specialist")
    workflow.add_edge("changelist_agent", "drafting_specialist")
    workflow.add_edge("drafting_specialist", END)
    workflow.add_edge("routing_agent", END)
    return workflow.compile()


def build_email_processing_graph_from_model(
    model: Any,
    tools: Optional[Sequence[Any]] = None,
) -> Any:
    """Test helper: one mock model for all roles."""
    classifier_llm = with_structured(model, ClassificationResult)
    tools_list = list(tools or [])
    qa_llm = model.bind_tools(tools_list) if tools_list else model
    validation_llm = model.bind_tools(tools_list) if tools_list else model
    validation_model = with_structured(model, ValidationResult)
    changelist_llm = model.bind_tools(tools_list) if tools_list else model
    changelist_model = with_structured(model, ChangelistBuildResult)
    return build_email_processing_graph(
        classifier_llm=classifier_llm,
        qa_llm=qa_llm,
        qa_model=model,
        qa_tools=tools_list,
        drafter_model=model,
        routing_model=model,
        validation_llm=validation_llm,
        validation_model=validation_model,
        changelist_llm=changelist_llm,
        changelist_model=changelist_model,
    )


async def run_email_graph(graph: Any, query: str) -> dict:
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "mode": "email",
        }
    )
    return {
        "triage": result.get("triage") or {},
        "validation": result.get("validation"),
        "changelist": result.get("changelist"),
        "draft": result.get("draft"),
        "qa_findings": result.get("qa_findings"),
    }
