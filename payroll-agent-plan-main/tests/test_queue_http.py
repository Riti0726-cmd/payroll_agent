import json

import pytest
from starlette.requests import Request

from queue_http import make_queue_route


def _request(query: bytes = b"specialist_id=default") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/queue",
        "raw_path": b"/queue",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_queue_400_missing_specialist():
    route = make_queue_route(list_fn=lambda _sid, _mailbox: [])
    resp = await route(_request(b""))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_queue_200_items():
    def list_fn(sid: str, mailbox: str):
        assert sid == "default"
        assert mailbox == ""
        return [
            {
                "message_id": "m1",
                "subject": "Pay question",
                "category": "qa",
                "priority_rate": "medium",
                "email_received_dttm": "2026-09-20T10:00:00+05:30",
                "content": "Why lower?",
                "sub_content": None,
            }
        ]

    route = make_queue_route(list_fn=list_fn)
    resp = await route(_request(b"specialist_id=default"))
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["items"][0]["id"] == "m1"
    assert data["items"][0]["category"] == "qa"
    assert data["items"][0]["priority"] == 3


@pytest.mark.asyncio
async def test_queue_passes_mailbox_override():
    seen: dict[str, str] = {}

    def list_fn(sid: str, mailbox: str):
        seen["sid"] = sid
        seen["mailbox"] = mailbox
        return []

    route = make_queue_route(list_fn=list_fn)
    resp = await route(
        _request(b"specialist_id=default&mailbox=payroll%40peoservices.com")
    )
    assert resp.status_code == 200
    assert seen["sid"] == "default"
    assert seen["mailbox"] == "payroll@peoservices.com"


@pytest.mark.asyncio
async def test_queue_503_when_list_fn_raises_db():
    def boom(_sid: str, _mailbox: str = ""):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_queue_route(list_fn=boom)
    resp = await route(_request(b"specialist_id=default"))
    assert resp.status_code == 503
    assert "detail" in json.loads(resp.body)


def _patch_request(message_id: str, body: dict, query: bytes = b"specialist_id=default"):
    raw = json.dumps(body).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "PATCH",
        "scheme": "http",
        "path": f"/queue/{message_id}",
        "raw_path": f"/queue/{message_id}".encode(),
        "query_string": query,
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
        "path_params": {"message_id": message_id},
    }

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_queue_patch_done():
    from queue_http import make_queue_patch_route

    def patch_fn(message_id: str, done: bool | None, priority: int | None):
        assert message_id == "m1"
        assert done is True
        assert priority is None
        return {
            "message_id": "m1",
            "subject": "Pay question",
            "category": "qa",
            "priority_rate": "medium",
            "email_received_dttm": "2026-09-20T10:00:00+05:30",
            "content": "Why lower?",
            "sub_content": None,
            "is_drafted": False,
            "draft_content": None,
        }

    route = make_queue_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("m1", {"done": True}))
    assert resp.status_code == 200
    assert json.loads(resp.body)["id"] == "m1"


@pytest.mark.asyncio
async def test_queue_patch_priority():
    from queue_http import make_queue_patch_route

    seen: dict = {}

    def patch_fn(message_id: str, done: bool | None, priority: int | None):
        seen["priority"] = priority
        return {
            "message_id": message_id,
            "subject": "X",
            "category": "todo",
            "priority_rate": "high",
            "email_received_dttm": None,
            "content": None,
            "sub_content": None,
            "is_drafted": False,
            "draft_content": None,
        }

    route = make_queue_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("m2", {"priority": 1}))
    assert resp.status_code == 200
    assert seen["priority"] == 1
    assert json.loads(resp.body)["priority"] == 1
