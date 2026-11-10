import pytest

from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore


class _FakeRepo:
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


@pytest.mark.asyncio
async def test_triage_skips_processed_and_runs_graph(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-old",
                received_at="2026-09-10T12:00:00Z",
                subject="Old",
                body="done already",
                conversation_id="c1",
            ),
            MailMessage(
                id="m-new",
                received_at="2026-09-10T13:00:00Z",
                subject="New",
                body="Why is pay low EMP-1042?",
                conversation_id="c1",
            ),
        ]
    )
    processed.mark_processed("m-old")

    async def fake_process(query: str) -> dict:
        assert "New" in query or "pay low" in query
        assert "done already" in query  # prior thread body
        return {
            "triage": {
                "category": "qa",
                "intent": "variance",
                "confidence": 0.9,
                "employee_id": "EMP-1042",
                "pay_period": None,
                "client_id": None,
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": "Draft body",
            "qa_findings": "findings",
        }

    orch = TriageOrchestrator(
        store=store,
        mailbox=mb,
        process_email_fn=fake_process,
        processed_store=processed,
        email_repo=_FakeRepo(),
    )
    store.save_specialist_config(
        "demo",
        {"mailbox_id": "box", "lookback_days": 30, "mode": "manual"},
    )
    out = await orch.run(specialist_id="demo", mailbox_id="box")
    results = out["email_results"]
    skipped = [r for r in results if r.get("skipped")]
    done = [r for r in results if not r.get("skipped")]
    assert any(r["message_id"] == "m-old" for r in skipped)
    assert any(r["message_id"] == "m-new" and r["category"] == "qa" for r in done)
    assert processed.is_processed("m-new") is True

    out2 = await orch.run(specialist_id="demo", mailbox_id="box")
    assert all(r.get("skipped") for r in out2["email_results"])
