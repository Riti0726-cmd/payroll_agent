import json

import pytest
from starlette.requests import Request

from drafts_http import make_draft_patch_route, make_drafts_list_route


def _list_request(query: bytes = b"specialist_id=default"):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/drafts",
        "raw_path": b"/drafts",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


def _patch_request(message_id: str, body: dict, query: bytes = b"specialist_id=default"):
    raw = json.dumps(body).encode()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "PATCH",
        "scheme": "http",
        "path": f"/drafts/{message_id}",
        "raw_path": f"/drafts/{message_id}".encode(),
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
async def test_drafts_list_200():
    def list_fn(sid: str, mailbox: str = ""):
        return [
            {
                "message_id": "m1",
                "subject": "Hi",
                "sender_email": "a@b.com",
                "draft_content": "Body",
                "hitl_status": "pending",
            }
        ]

    route = make_drafts_list_route(list_fn=list_fn)
    resp = await route(_list_request())
    assert resp.status_code == 200
    assert json.loads(resp.body)["items"][0]["id"] == "m1"


@pytest.mark.asyncio
async def test_drafts_list_503():
    def boom(_sid: str, _mailbox: str = ""):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_drafts_list_route(list_fn=boom)
    resp = await route(_list_request())
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_draft_patch_accepted():
    def patch_fn(sid: str, message_id: str, status: str, body: str | None):
        assert sid == "default"
        assert message_id == "m1"
        assert status == "accepted"
        return {
            "message_id": "m1",
            "subject": "Hi",
            "sender_email": "a@b.com",
            "draft_content": body or "Body",
            "hitl_status": status,
        }

    route = make_draft_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("m1", {"status": "accepted", "body": "Edited"}))
    assert resp.status_code == 200
    assert json.loads(resp.body)["status"] == "accepted"
