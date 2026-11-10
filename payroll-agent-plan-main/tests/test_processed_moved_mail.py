"""Triage dedupe survives folder moves (Graph id changes, internetMessageId does not)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from db.repository import EmailRepository
from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore, NeonProcessedMailPort

IMID = "<CAB12x@mail.example.com>"


def test_local_store_matches_moved_message_by_internet_message_id(tmp_path: Path):
    store = LocalProcessedMailStore(tmp_path, specialist_id="demo")
    store.mark_processed("AAMk-inbox", internet_message_id=IMID)
    # Same email after a move: new Graph id, same internetMessageId.
    assert store.is_processed("AAMk-archive", internet_message_id=IMID) is True
    assert store.is_processed("AAMk-other", internet_message_id="<other@x>") is False
    # Old call shape still works.
    assert store.is_processed("AAMk-inbox") is True
    assert LocalProcessedMailStore(tmp_path, specialist_id="demo").is_processed(
        "AAMk-new", internet_message_id=IMID
    )


def _repo(found: bool):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = object() if found else None
    return EmailRepository(MagicMock(return_value=session)), session


def test_repository_is_processed_queries_both_ids():
    repo, session = _repo(found=True)
    assert repo.is_processed("AAMk-archive", internet_message_id=IMID) is True
    sql = str(session.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "AAMk-archive" in sql and IMID in sql
    assert "internet_message_id" in sql and "is_processed" in sql


def test_repository_is_processed_without_internet_message_id():
    repo, session = _repo(found=False)
    assert repo.is_processed("AAMk-new") is False
    sql = str(session.execute.call_args[0][0].compile(compile_kwargs={"literal_binds": True}))
    assert "internet_message_id =" not in sql


def test_neon_port_forwards_internet_message_id():
    repo = MagicMock()
    repo.is_processed.return_value = True
    port = NeonProcessedMailPort(repo)
    assert port.is_processed("AAMk-archive", internet_message_id=IMID) is True
    repo.is_processed.assert_called_once_with("AAMk-archive", internet_message_id=IMID)


class _FakeEmailRepo:
    def __init__(self):
        self.ingested: list[str] = []

    def upsert_ingested_email(self, *, message):
        self.ingested.append(message.message_id)
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
async def test_orchestrator_skips_email_that_moved_folders(tmp_path: Path):
    store = LocalTriageStore(root=str(tmp_path))
    store.save_specialist_config(
        "demo",
        {"specialist_id": "demo", "mailbox_id": "mb-demo", "lookback_days": 30, "mode": "manual", "interval_hours": 4},
    )
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    # Triaged earlier while it sat in the Inbox.
    processed.mark_processed("AAMk-inbox", internet_message_id=IMID)

    now = datetime(2026, 9, 23, tzinfo=timezone.utc).isoformat()
    mailbox = MockGraphMailbox(
        messages=[
            # Same email, now in another folder with a new Graph id.
            MailMessage(id="AAMk-archive", received_at=now, subject="Pay variance",
                        body_preview="Why is my paycheck lower?", internet_message_id=IMID),
            MailMessage(id="AAMk-fresh", received_at=now, subject="Benefits",
                        body_preview="Help with dental enrollment", internet_message_id="<new@x>"),
        ]
    )
    repo = _FakeEmailRepo()
    orch = TriageOrchestrator(store=store, mailbox=mailbox, processed_store=processed, email_repo=repo)
    out = await orch.run(specialist_id="demo")

    by_id = {r["message_id"]: r for r in out["email_results"]}
    assert by_id["AAMk-archive"]["status"] == "skipped"
    assert by_id["AAMk-fresh"]["status"] == "succeeded"
    assert repo.ingested == ["AAMk-fresh"]
    # The fresh email is now known by both ids.
    assert processed.is_processed("whatever-id", internet_message_id="<new@x>")
