"""Triage → Neon queue persistence."""

from __future__ import annotations

import pytest

from db.repository import UpsertResult
from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore


class FakeEmailRepo:
    def __init__(self) -> None:
        self.upserts: list = []
        self.classifications: list = []
        self.extracts: list = []

    def upsert_ingested_email(self, *, message):
        self.upserts.append(message)
        return UpsertResult.inserted

    def save_classification(self, *, email_id, categories, priority="medium"):
        self.classifications.append((email_id, categories, priority))

    def save_extracts(self, *, message_id, extracts):
        self.extracts.append((message_id, extracts))


@pytest.mark.asyncio
async def test_triage_persists_succeeded_email_to_neon(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-new",
                received_at="2026-09-10T13:00:00Z",
                from_address="client@example.com",
                subject="New",
                body="Why is pay low EMP-1042?",
                conversation_id="c1",
            ),
        ]
    )
    repo = FakeEmailRepo()

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "qa",
                "intent": "variance",
                "confidence": 0.9,
                "employee_id": "EMP-1042",
                "pay_period": None,
                "client_id": "C1",
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": None,
            "qa_findings": None,
        }

    orch = TriageOrchestrator(
        store=store,
        mailbox=mb,
        process_email_fn=fake_process,
        processed_store=processed,
        email_repo=repo,
    )
    store.save_specialist_config(
        "demo",
        {"mailbox_id": "hrc@example.com", "lookback_days": 30, "mode": "manual"},
    )
    out = await orch.run(specialist_id="demo", mailbox_id="hrc@example.com")
    assert out["email_results"][0]["status"] == "succeeded"
    assert len(repo.upserts) == 1
    assert repo.upserts[0].message_id == "m-new"
    assert repo.upserts[0].recipients == ["hrc@example.com"]
    assert repo.classifications == [("m-new", ["qa"], "medium")]
    assert repo.extracts == [("m-new", {"employee_id": "EMP-1042", "client_id": "C1"})]


@pytest.mark.asyncio
async def test_triage_neon_failure_marks_result_failed(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-bad",
                received_at="2026-09-10T13:00:00Z",
                subject="X",
                body="bank account change",
                conversation_id="c1",
            ),
        ]
    )

    class BoomRepo(FakeEmailRepo):
        def upsert_ingested_email(self, *, message):
            raise RuntimeError("db down")

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "changelist",
                "intent": "dd",
                "confidence": 0.8,
                "employee_id": None,
                "pay_period": None,
                "client_id": None,
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": None,
            "qa_findings": None,
        }

    orch = TriageOrchestrator(
        store=store,
        mailbox=mb,
        process_email_fn=fake_process,
        processed_store=processed,
        email_repo=BoomRepo(),
    )
    store.save_specialist_config("demo", {"mailbox_id": "box", "lookback_days": 30})
    out = await orch.run(specialist_id="demo", mailbox_id="box")
    assert out["email_results"][0]["status"] == "failed"
    assert "Neon persist failed" in out["email_results"][0]["error"]
    assert processed.is_processed("m-bad") is False
