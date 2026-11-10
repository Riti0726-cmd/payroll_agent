from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from graph import create_payroll_graph
from models import ClassificationResult
from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator


class MockChatModel:
    """Offline mock model for testing LangGraph workflow execution."""

    def __init__(
        self,
        category: str = "qa",
        employee_id: str | None = "EMP-1042",
        oos_destination: str | None = None,
        client_id: str | None = "C1",
        change_type: str | None = None,
        new_value: str | None = None,
        previous_value: str | None = None,
        validation_status: str = "ok",
    ):
        self.category = category
        self.employee_id = employee_id
        self.oos_destination = oos_destination
        self.client_id = client_id
        self.change_type = change_type
        self.new_value = new_value
        self.previous_value = previous_value
        self.validation_status = validation_status

    def with_structured_output(self, schema):
        mock_structured = MagicMock()
        schema_name = getattr(schema, "__name__", str(schema))

        async def _ainvoke(messages):
            return self._structured_result(schema_name, schema)

        def _invoke(messages):
            return self._structured_result(schema_name, schema)

        mock_structured.ainvoke = _ainvoke
        mock_structured.invoke = _invoke
        return mock_structured

    def _structured_result(self, schema_name: str, schema):
        from models import ChangelistBuildResult, ChangeLineBuild, ClassificationResult, ValidationResult

        if schema_name == "ValidationResult" or schema is ValidationResult:
            return ValidationResult(
                status=self.validation_status,  # type: ignore[arg-type]
                client_ok=True if self.client_id else None,
                employee_ok=True if self.employee_id else None,
                missing=[] if self.validation_status == "ok" else ["employee_id"],
                notes="mock validation",
            )
        if schema_name == "ChangelistBuildResult" or schema is ChangelistBuildResult:
            if self.change_type or self.new_value:
                return ChangelistBuildResult(
                    changes=[
                        ChangeLineBuild.model_validate(
                            {
                                "field": self.change_type or "other",
                                "from": self.previous_value or "20",
                                "to": self.new_value or "22",
                                "incomplete": False,
                            }
                        )
                    ],
                    findings="mock changelist findings",
                )
            return ChangelistBuildResult(findings="mock empty changelist")
        return ClassificationResult(
            category=self.category,
            intent="Test intent",
            confidence=0.98,
            employee_id=self.employee_id,
            pay_period="2026-08",
            client_id=self.client_id,
            oos_destination=self.oos_destination,
            change_type=self.change_type,  # type: ignore[arg-type]
            new_value=self.new_value,
            previous_value=self.previous_value,
        )

    async def _mock_structured_ainvoke(self, messages):
        return self._structured_result("ClassificationResult", None)

    def _mock_structured_invoke(self, messages):
        return self._structured_result("ClassificationResult", None)

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="Mocked response for testing.")

    def invoke(self, messages):
        return AIMessage(content="Mocked response for testing.")


def test_graph_compiles_triage_only_nodes():
    mock_llm = MockChatModel()
    graph = create_payroll_graph(model=mock_llm, tools=[], enable_telemetry=False)
    assert graph is not None
    nodes = set(graph.nodes.keys())
    assert "intake" in nodes
    assert "drafting_specialist" in nodes
    assert "classifier" not in nodes
    assert "qa_specialist" not in nodes
    assert "routing_agent" not in nodes


@pytest.mark.asyncio
async def test_freeform_invoke_rejected_without_classifier():
    """Foundry Responses graph accepts TRIAGE_RUN only; chat must use POST /qa."""
    from nodes.intake import UNSUPPORTED_INVOKE_MESSAGE

    mock_llm = MockChatModel(category="qa", employee_id="EMP-1042")
    graph = create_payroll_graph(model=mock_llm, tools=[], enable_telemetry=False)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="Why was my August paycheck lower? EMP-1042")]}
    )

    assert result.get("mode") == "unsupported"
    assert result.get("triage") is None
    final_message = result["messages"][-1]
    assert UNSUPPORTED_INVOKE_MESSAGE in final_message.content
    assert "**Triaged Category:**" not in final_message.content


@pytest.mark.asyncio
async def test_email_subgraph_executes_qa_flow():
    from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

    mock_llm = MockChatModel(category="qa", employee_id="EMP-1042")
    graph = build_email_processing_graph_from_model(mock_llm, tools=[])
    out = await run_email_graph(graph, "Why was my August paycheck lower? EMP-1042")
    assert out["triage"]["category"] == "qa"
    assert out["triage"]["employee_id"] == "EMP-1042"
    # No live MCP → blocked findings; draft may still acknowledge
    assert out.get("qa_findings")
    assert "Snowflake MCP is required" in out["qa_findings"]
    assert out.get("draft")


@pytest.mark.asyncio
async def test_email_subgraph_executes_changelist_flow():
    from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

    mock_llm = MockChatModel(
        category="changelist",
        employee_id="EMP-1",
        client_id="C1",
        change_type="hourly_pay_rate",
        new_value="22",
        previous_value="20",
    )
    graph = build_email_processing_graph_from_model(mock_llm, tools=[])
    out = await run_email_graph(
        graph, "Please change hourly rate from 20 to 22 for EMP-1 client C1"
    )
    assert out["triage"]["category"] == "changelist"
    assert out.get("validation", {}).get("status") == "ok"
    # Without live Snowflake MCP tools, changelist must not invent lines
    assert out.get("changelist")
    assert out["changelist"].get("snowflake_fetched") is False
    assert out["changelist"].get("changes") == []
    assert out.get("draft")


@pytest.mark.asyncio
async def test_email_subgraph_qa_blocks_without_mcp():
    from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

    mock_llm = MockChatModel(category="qa", employee_id="EMP-1042")
    graph = build_email_processing_graph_from_model(mock_llm, tools=[])
    out = await run_email_graph(graph, "Why was my August paycheck lower? EMP-1042")
    assert out["triage"]["category"] == "qa"
    assert out.get("qa_findings")
    assert "Snowflake MCP is required" in out["qa_findings"]


@pytest.mark.asyncio
async def test_email_subgraph_executes_out_of_scope_routing():
    from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

    mock_llm = MockChatModel(
        category="out_of_scope",
        employee_id=None,
        oos_destination="benefits",
    )
    graph = build_email_processing_graph_from_model(mock_llm, tools=[])
    out = await run_email_graph(graph, "I need help enrolling in dental benefits")
    assert out["triage"]["category"] == "out_of_scope"
    assert out["triage"]["oos_destination"] == "benefits"


@pytest.mark.asyncio
async def test_triage_command_intake(tmp_path):
    from triage.processed import LocalProcessedMailStore

    class FakeEmailRepo:
        def upsert_ingested_email(self, *, message):
            return "inserted"

        def save_classification(self, *, email_id, categories, priority="medium"):
            return None

        def save_extracts(self, *, message_id, extracts):
            return None

        def save_draft(self, *, email_id, draft_content):
            return None

        def save_changelist_response(self, message_id, payload):
            return None

    store = LocalTriageStore(root=str(tmp_path / "store"))
    mailbox = MockGraphMailbox(
        messages=[
            MailMessage(
                id="m1",
                received_at="2026-09-20T12:00:00+00:00",
                subject="Paycheck question",
                body_preview="Why is my net pay lower?",
                is_read=False,
            ),
            MailMessage(
                id="m2",
                received_at="2026-09-21T12:00:00+00:00",
                subject="Benefits",
                body_preview="Please help with dental enrollment",
                is_read=True,
            ),
        ]
    )
    orch = TriageOrchestrator(
        store=store,
        mailbox=mailbox,
        processed_store=LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo-specialist"),
        email_repo=FakeEmailRepo(),
    )
    mock_llm = MockChatModel(category="qa")
    graph = create_payroll_graph(
        model=mock_llm,
        tools=[],
        triage_orchestrator=orch,
        enable_telemetry=False,
    )

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="TRIAGE_RUN specialist_id=demo-specialist")]}
    )

    assert result.get("mode") == "triage"
    assert result.get("run_id")
    assert "**Triage Run Summary**" in result["messages"][-1].content
    assert "Emails in window: 2" in result["messages"][-1].content
    assert "Processed: 2" in result["messages"][-1].content


@pytest.mark.asyncio
async def test_email_subgraph_classifies_todo():
    from triage.email_graph import build_email_processing_graph_from_model, run_email_graph

    mock_llm = MockChatModel(category="todo", employee_id=None)
    graph = build_email_processing_graph_from_model(mock_llm, tools=[])
    out = await run_email_graph(graph, "Please approve off-cycle for EMP-1")
    assert out["triage"]["category"] == "todo"
    assert out.get("draft") or out.get("qa_findings") is None
