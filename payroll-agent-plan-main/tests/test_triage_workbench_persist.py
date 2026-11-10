"""Triage → Neon draft + changelist shell persistence."""

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
        self.drafts: list = []
        self.changelists: list = []
        self._changelist_by_id: dict = {}

    def upsert_ingested_email(self, *, message):
        self.upserts.append(message)
        return UpsertResult.inserted

    def save_classification(self, *, email_id, categories, priority="medium"):
        self.classifications.append((email_id, categories, priority))

    def save_extracts(self, *, message_id, extracts):
        self.extracts.append((message_id, extracts))

    def save_draft(self, *, email_id, draft_content):
        self.drafts.append((email_id, draft_content))

    def get_changelist_response(self, message_id):
        return self._changelist_by_id.get(message_id)

    def save_changelist_response(self, message_id, payload):
        self.changelists.append((message_id, payload))
        self._changelist_by_id[message_id] = payload


@pytest.mark.asyncio
async def test_triage_persists_draft_and_changelist_shell(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-cl",
                received_at="2026-09-10T13:00:00Z",
                from_address="client@example.com",
                subject="Direct deposit",
                body="Please update my bank account",
                conversation_id="c1",
            ),
        ]
    )
    repo = FakeEmailRepo()

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "changelist",
                "intent": "Update DD",
                "confidence": 0.9,
                "employee_id": None,
                "pay_period": None,
                "client_id": "C1",
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": "Please use the portal to update direct deposit.",
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
    assert repo.drafts == [("m-cl", "Please use the portal to update direct deposit.")]
    assert len(repo.changelists) == 1
    assert repo.changelists[0][0] == "m-cl"
    assert repo.changelists[0][1]["lines"] == []
    assert repo.changelists[0][1]["clientId"] == "C1"


@pytest.mark.asyncio
async def test_triage_persists_rich_changelist_from_graph(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-rich-new",
                received_at="2026-09-10T13:00:00Z",
                from_address="client@example.com",
                subject="Rate change",
                body="raise to 22",
                conversation_id="c3",
            ),
        ]
    )
    repo = FakeEmailRepo()

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "changelist",
                "intent": "salary_change",
                "confidence": 0.9,
                "employee_id": "E1",
                "pay_period": None,
                "client_id": "C1",
                "employee_name": None,
                "effective_date": "2026-09-14",
                "oos_destination": None,
            },
            "validation": {"status": "ok"},
            "changelist": {
                "agent": "changelist",
                "status": "pending",
                "clientId": "C1",
                "title": "Rate change",
                "changes": [
                    {
                        "id": "l0",
                        "field": "hourly_pay_rate",
                        "from": "20",
                        "to": "22",
                        "incomplete": False,
                    }
                ],
                "priority_rate": "high",
                "due_date": "2026-09-20",
            },
            "draft": "Ack",
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
    assert repo.classifications[0][2] == "high"
    saved = repo.changelists[0][1]
    assert saved["changes"][0]["to"] == "22"
    assert saved["due_date"] == "2026-09-20"


@pytest.mark.asyncio
async def test_triage_preserves_existing_changelist_changes(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m-rich",
                received_at="2026-09-10T13:00:00Z",
                from_address="client@example.com",
                subject="Pay rate",
                body="raise to 22",
                conversation_id="c2",
            ),
        ]
    )
    repo = FakeEmailRepo()
    rich = {
        "agent": "changelist",
        "parameters": {"client_id": "12890"},
        "changes": [{"field": "hourly_pay_rate", "from": 20.0, "to": 22.0}],
        "status": "ready",
    }
    repo._changelist_by_id["m-rich"] = rich

    async def fake_process(_query: str) -> dict:
        return {
            "triage": {
                "category": "changelist",
                "intent": "salary_change",
                "confidence": 0.9,
                "employee_id": None,
                "pay_period": None,
                "client_id": "C9",
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": "",
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
    assert len(repo.changelists) == 1
    saved = repo.changelists[0][1]
    assert saved["changes"] == rich["changes"]
    assert saved.get("lines") in (None, [])
    assert saved["status"] == "ready"
