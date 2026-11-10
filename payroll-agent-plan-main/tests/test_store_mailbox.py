from datetime import datetime, timezone

from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator


def test_local_store_config_and_interval_validation(tmp_path):
    store = LocalTriageStore(root=str(tmp_path))
    cfg = store.get_specialist_config("spec-1")
    assert cfg["specialist_id"] == "spec-1"
    assert cfg["mode"] == "manual"

    saved = store.save_specialist_config(
        "spec-1",
        {**cfg, "mode": "recurring", "interval_hours": 99, "lookback_days": 3},
    )
    assert saved["mode"] == "recurring"
    assert saved["interval_hours"] == 4  # invalid coerced to default
    assert saved["lookback_days"] == 3


def test_local_store_run_lifecycle(tmp_path):
    store = LocalTriageStore(root=str(tmp_path))
    run = store.create_run("spec-1", {"mailbox_id": "mb-1"})
    assert run["status"] == "running"
    assert store.get_last_successful_run("spec-1") is None

    store.complete_run("spec-1", run["run_id"], {"status": "succeeded", "window_end": "2026-09-23T00:00:00+00:00"})
    last = store.get_last_successful_run("spec-1")
    assert last is not None
    assert last["run_id"] == run["run_id"]


def test_mock_mailbox_filters_window():
    mailbox = MockGraphMailbox(
        messages=[
            MailMessage(id="a", received_at="2026-09-10T00:00:00+00:00", subject="old"),
            MailMessage(id="b", received_at="2026-09-20T00:00:00+00:00", subject="in"),
            MailMessage(id="c", received_at="2026-09-25T00:00:00+00:00", subject="future"),
        ]
    )
    mailbox.bind_specialist("s1", "mb1")
    msgs = mailbox.list_messages(
        "mb1",
        window_start="2026-09-15T00:00:00+00:00",
        window_end="2026-09-22T00:00:00+00:00",
    )
    assert [m.id for m in msgs] == ["b"]


import pytest


@pytest.mark.asyncio
async def test_orchestrator_classifies_emails(tmp_path):
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

    store = LocalTriageStore(root=str(tmp_path))
    store.save_specialist_config(
        "demo",
        {
            "specialist_id": "demo",
            "mailbox_id": "mb-demo",
            "lookback_days": 30,
            "mode": "manual",
            "interval_hours": 4,
        },
    )
    now = datetime(2026, 9, 23, tzinfo=timezone.utc)
    # Force window via empty last success + large lookback by seeding recent messages
    mailbox = MockGraphMailbox(
        messages=[
            MailMessage(
                id="1",
                received_at=now.isoformat(),
                subject="Pay variance",
                body_preview="Why is my paycheck lower?",
            ),
            MailMessage(
                id="2",
                received_at=now.isoformat(),
                subject="Benefits",
                body_preview="Help with dental enrollment",
            ),
        ]
    )
    orch = TriageOrchestrator(
        store=store,
        mailbox=mailbox,
        processed_store=LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo"),
        email_repo=FakeEmailRepo(),
    )
    out = await orch.run(specialist_id="demo")
    assert out["run_id"]
    assert len(out["email_results"]) == 2
    cats = {r["category"] for r in out["email_results"]}
    assert "qa" in cats
    assert "out_of_scope" in cats
