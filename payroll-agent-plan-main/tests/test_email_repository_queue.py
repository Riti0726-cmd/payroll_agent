"""Unit tests for EmailRepository queue helpers (mocked session)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from db.repository import EmailNotFoundError, EmailRepository


def test_save_extracts_writes_json_sub_content():
    row = SimpleNamespace(message_id="m1", sub_content=None)
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = row

    factory = MagicMock(return_value=session)
    repo = EmailRepository(factory)
    repo.save_extracts(message_id="m1", extracts={"client_id": "C1", "employee_id": None})

    assert row.sub_content == '{"client_id": "C1"}'
    session.commit.assert_called_once()


def test_save_extracts_missing_raises():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.return_value = None
    repo = EmailRepository(MagicMock(return_value=session))
    with pytest.raises(EmailNotFoundError):
        repo.save_extracts(message_id="missing", extracts={"client_id": "C1"})


def test_list_open_queue_maps_rows():
    row = SimpleNamespace(
        message_id="m1",
        subject="Pay Q",
        category="qa",
        priority_rate="high",
        email_received_dttm=None,
        content="Why lower?",
        sub_content='{"client_id":"C1"}',
        is_drafted=False,
        draft_content=None,
    )
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalars.return_value.all.return_value = [row]

    repo = EmailRepository(MagicMock(return_value=session))
    items = repo.list_open_queue(specialist_mailbox="hrc@example.com")
    assert items == [
        {
            "message_id": "m1",
            "subject": "Pay Q",
            "category": "qa",
            "priority_rate": "high",
            "email_received_dttm": None,
            "content": "Why lower?",
            "sub_content": '{"client_id":"C1"}',
            "is_drafted": False,
            "draft_content": None,
        }
    ]


def test_list_open_queue_empty_mailbox():
    repo = EmailRepository(MagicMock())
    assert repo.list_open_queue(specialist_mailbox="  ") == []
