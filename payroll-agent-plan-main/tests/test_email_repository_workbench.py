"""Unit tests for EmailRepository drafts/changelists helpers (mocked session)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db.repository import EmailNotFoundError, EmailRepository


def test_set_hitl_status_updates_and_optional_body():
    row = SimpleNamespace(
        message_id="m1",
        subject="Hi",
        sender_email="a@b.com",
        draft_content="old",
        hitl_status="pending",
        category="qa",
        sub_content=None,
        changelist_response=None,
        email_received_dttm=None,
    )
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = row
    factory = MagicMock(return_value=session)
    repo = EmailRepository(factory)

    out = repo.set_hitl_status("m1", "accepted", draft_body="new body")
    assert row.hitl_status == "accepted"
    assert row.draft_content == "new body"
    session.commit.assert_called()
    assert out["message_id"] == "m1"
    assert out["draft_content"] == "new body"
    assert out["hitl_status"] == "accepted"


def test_set_hitl_status_missing_raises():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = None
    repo = EmailRepository(MagicMock(return_value=session))
    with pytest.raises(EmailNotFoundError):
        repo.set_hitl_status("missing", "discarded")


def test_list_pending_drafts_empty_mailbox():
    repo = EmailRepository(MagicMock())
    assert repo.list_pending_drafts(specialist_mailbox="  ") == []


def test_list_pending_changelists_empty_mailbox():
    repo = EmailRepository(MagicMock())
    assert repo.list_pending_changelists(specialist_mailbox="") == []


def test_list_pending_drafts_maps_rows():
    row = SimpleNamespace(
        message_id="m1",
        subject="Pay Q",
        sender_email="e@x.com",
        draft_content="Hello",
        hitl_status="pending",
        category="qa",
        sub_content=None,
        changelist_response=None,
        email_received_dttm=None,
    )
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalars.return_value.all.return_value = [row]
    repo = EmailRepository(MagicMock(return_value=session))
    items = repo.list_pending_drafts(specialist_mailbox="hrc@example.com")
    assert items[0]["message_id"] == "m1"
    assert items[0]["draft_content"] == "Hello"


def test_save_draft_sets_hitl_pending():
    row = SimpleNamespace(
        message_id="m1",
        draft_content=None,
        is_drafted=False,
        is_processed=True,
        mail_draft_time=None,
        hitl_status=None,
    )
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = row
    repo = EmailRepository(MagicMock(return_value=session))
    repo.save_draft(email_id="m1", draft_content="Body")
    assert row.draft_content == "Body"
    assert row.is_drafted is True
    assert row.hitl_status == "pending"
