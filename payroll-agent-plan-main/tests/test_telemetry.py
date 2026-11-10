import pytest
from langchain_core.messages import AIMessage, HumanMessage
from unittest.mock import MagicMock

from graph import create_payroll_graph
from models import ClassificationResult
from store.local_store import LocalTriageStore
from telemetry import (
    assert_no_pii_in_spans,
    configure_telemetry,
    get_memory_exporter,
    pii_safe_attributes,
    reset_telemetry_for_tests,
)
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore


def test_pii_safe_attributes_strips_blocked_keys():
    attrs = pii_safe_attributes(
        category="qa",
        employee_id="EMP-1",
        subject="SECRET SUBJECT",
        body="secret body",
        query="full query text",
    )
    assert "subject" not in attrs
    assert "body" not in attrs
    assert "query" not in attrs
    assert attrs["category"] == "qa"
    assert attrs["employee_id"] == "EMP-1"


class MockChatModel:
    def __init__(self, category: str = "qa"):
        self.category = category

    def with_structured_output(self, schema):
        mock_structured = MagicMock()

        async def _ainvoke(messages):
            return ClassificationResult(
                category=self.category,
                intent="Test",
                confidence=0.9,
                employee_id="EMP-1",
                pay_period=None,
                oos_destination=None,
            )

        mock_structured.ainvoke = _ainvoke
        mock_structured.invoke = lambda messages: ClassificationResult(
            category=self.category,
            intent="Test",
            confidence=0.9,
            employee_id="EMP-1",
        )
        return mock_structured

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        return AIMessage(content="ok")

    def invoke(self, messages):
        return AIMessage(content="ok")


@pytest.mark.asyncio
async def test_agent_and_step_spans_for_triage(tmp_path):
    reset_telemetry_for_tests()
    configure_telemetry(use_memory_exporter=True)
    exporter = get_memory_exporter()
    assert exporter is not None

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
        ]
    )
    orch = TriageOrchestrator(
        store=store,
        mailbox=mailbox,
        processed_store=LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo-specialist"),
        email_repo=FakeEmailRepo(),
    )

    graph = create_payroll_graph(
        model=MockChatModel(category="qa"),
        tools=[],
        triage_orchestrator=orch,
        enable_telemetry=False,
    )
    await graph.ainvoke(
        {"messages": [HumanMessage(content="TRIAGE_RUN specialist_id=demo-specialist")]}
    )

    spans = exporter.get_finished_spans()
    names = {s.name for s in spans}
    assert "agent_run" in names
    assert "step_intake" in names
    assert "step_finalize_run" in names or "step_drafting_specialist" in names or "step_triage_orchestrate" in names
    assert_no_pii_in_spans(spans)

    agent = next(s for s in spans if s.name == "agent_run")
    assert agent.attributes.get("mode") == "triage"


@pytest.mark.asyncio
async def test_agent_span_mode_unsupported_for_freeform():
    reset_telemetry_for_tests()
    configure_telemetry(use_memory_exporter=True)
    exporter = get_memory_exporter()
    assert exporter is not None

    graph = create_payroll_graph(
        model=MockChatModel(category="changelist"),
        tools=[],
        enable_telemetry=False,
    )
    await graph.ainvoke({"messages": [HumanMessage(content="Change my bank account")]})

    spans = exporter.get_finished_spans()
    agent = next(s for s in spans if s.name == "agent_run")
    assert agent.attributes.get("mode") == "unsupported"
    assert "step_classifier" not in {s.name for s in spans}
