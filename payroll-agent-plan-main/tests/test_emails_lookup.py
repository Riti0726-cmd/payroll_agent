"""GET /emails/lookup (Outlook add-in), repository lookup, and CORS."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.testclient import TestClient

from cors import cors_allowed_origins, mount_cors_middleware
from db.repository import EmailNotFoundError, EmailRepository
from emails_http import make_email_lookup_route, mount_emails_routes, row_to_email_record


def _request(query: bytes) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/emails/lookup",
        "raw_path": b"/emails/lookup",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _row(**overrides):
    row = {
        "message_id": "AAMk-1",
        "subject": "Rate change for EMP-1",
        "category": "changelist",
        "priority_rate": "high",
        "email_received_dttm": "2026-10-01T10:00:00+05:30",
        "content": "Please update the rate",
        "sub_content": '{"client_id": "C1", "employee_id": "EMP-1"}',
        "is_drafted": True,
        "draft_content": "Hi, we will update it.",
        "hitl_status": "pending",
        "sender_email": "client@example.com",
        "changelist_response": json.dumps(
            {"changes": [{"field": "hourly_pay_rate", "from": "20", "to": "22"}]}
        ),
        "is_categorized": True,
        "is_processed": False,
    }
    row.update(overrides)
    return row


def test_row_to_email_record_combines_draft_and_changelist():
    record = row_to_email_record(_row())
    assert record["id"] == "AAMk-1"
    assert record["triaged"] is True
    assert record["category"] == "changelist"
    assert record["priority"] == 1
    assert record["done"] is False
    assert record["clientId"] == "C1"
    assert record["draft"]["body"] == "Hi, we will update it."
    assert record["changeList"]["lines"][0]["field"] == "hourly_pay_rate"


def test_row_to_email_record_untriaged_qa_without_draft():
    record = row_to_email_record(
        _row(category=None, is_categorized=False, draft_content=None, hitl_status=None)
    )
    assert record["triaged"] is False
    assert record["category"] is None
    assert "draft" not in record
    assert "changeList" not in record


def test_row_to_email_record_done_when_closed():
    assert row_to_email_record(_row(hitl_status="accepted"))["done"] is True
    assert row_to_email_record(_row(hitl_status=None, is_processed=True))["done"] is True


@pytest.mark.asyncio
async def test_lookup_400_missing_specialist():
    route = make_email_lookup_route(lookup_fn=lambda *_: _row())
    resp = await route(_request(b"rest_id=AAMk-1"))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_lookup_400_missing_ids():
    route = make_email_lookup_route(lookup_fn=lambda *_: _row())
    resp = await route(_request(b"specialist_id=s1"))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_lookup_200_passes_ids():
    seen: dict = {}

    def lookup(sid, mailbox, rest_id, imid):
        seen.update(sid=sid, mailbox=mailbox, rest_id=rest_id, imid=imid)
        return _row()

    route = make_email_lookup_route(lookup_fn=lookup)
    resp = await route(
        _request(b"specialist_id=s1&rest_id=AAMk-1&internet_message_id=%3Cabc%40x%3E")
    )
    assert resp.status_code == 200
    assert seen == {"sid": "s1", "mailbox": "", "rest_id": "AAMk-1", "imid": "<abc@x>"}
    data = json.loads(resp.body)
    assert data["category"] == "changelist"
    assert data["changeList"]["lines"][0]["from"] == "20"


@pytest.mark.asyncio
async def test_lookup_404_when_not_found():
    def lookup(*_):
        raise EmailNotFoundError("Email not found")

    route = make_email_lookup_route(lookup_fn=lookup)
    resp = await route(_request(b"specialist_id=s1&rest_id=nope"))
    assert resp.status_code == 404


def _row_obj(**kw):
    base = dict(
        message_id="AAMk-1",
        subject="S",
        category="qa",
        priority_rate="medium",
        email_received_dttm=None,
        content="c",
        sub_content=None,
        is_drafted=False,
        draft_content=None,
        hitl_status=None,
        sender_email="a@b.c",
        changelist_response=None,
        is_categorized=True,
        is_processed=False,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _repo_with_results(results):
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    session.execute.return_value.scalar_one_or_none.side_effect = results
    return EmailRepository(MagicMock(return_value=session)), session


def test_get_email_record_by_rest_id():
    repo, session = _repo_with_results([_row_obj()])
    out = repo.get_email_record(specialist_mailbox="hrc@example.com", message_id="AAMk-1")
    assert out["message_id"] == "AAMk-1"
    assert out["is_categorized"] is True
    assert session.execute.call_count == 1


def test_get_email_record_falls_back_to_internet_message_id():
    repo, session = _repo_with_results([None, _row_obj(message_id="AAMk-moved")])
    out = repo.get_email_record(
        specialist_mailbox="hrc@example.com",
        message_id="AAMk-new",
        internet_message_id="<abc@x>",
    )
    assert out["message_id"] == "AAMk-moved"
    assert session.execute.call_count == 2


def test_get_email_record_not_found_or_unscoped():
    repo, _ = _repo_with_results([None, None])
    with pytest.raises(EmailNotFoundError):
        repo.get_email_record(
            specialist_mailbox="hrc@example.com", message_id="x", internet_message_id="<y>"
        )
    repo, _ = _repo_with_results([_row_obj()])
    with pytest.raises(EmailNotFoundError):
        repo.get_email_record(specialist_mailbox="", message_id="AAMk-1")


def test_cors_origins_parsing(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " https://localhost:3000/ , https://addin.example ")
    assert cors_allowed_origins() == ["https://localhost:3000", "https://addin.example"]
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS")
    assert cors_allowed_origins() == []


def test_cors_preflight_allows_listed_origin_only(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://localhost:3000")
    app = Starlette()
    mount_emails_routes(app, lookup_fn=lambda *_: _row())
    mount_cors_middleware(app)
    client = TestClient(app)

    ok = client.options(
        "/emails/lookup",
        headers={
            "Origin": "https://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == "https://localhost:3000"

    bad = client.options(
        "/emails/lookup",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert bad.status_code == 400
    assert "access-control-allow-origin" not in bad.headers
