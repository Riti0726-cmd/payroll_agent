import json

import pytest
from starlette.requests import Request

from changelists_http import make_changelist_patch_route, make_changelists_list_route


def _list_request(query: bytes = b"specialist_id=default"):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/changelists",
        "raw_path": b"/changelists",
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
        "path": f"/changelists/{message_id}",
        "raw_path": f"/changelists/{message_id}".encode(),
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
async def test_changelists_list_200():
    def list_fn(sid: str, mailbox: str = ""):
        return [
            {
                "message_id": "c1",
                "subject": "DD",
                "category": "changelist",
                "sub_content": '{"client_id":"C1"}',
                "changelist_response": None,
                "hitl_status": "pending",
                "email_received_dttm": "2026-09-20T10:00:00+00:00",
            }
        ]

    route = make_changelists_list_route(list_fn=list_fn)
    resp = await route(_list_request())
    assert resp.status_code == 200
    item = json.loads(resp.body)["items"][0]
    assert item["id"] == "c1"
    assert item["clientId"] == "C1"
    assert item["lines"] == []


@pytest.mark.asyncio
async def test_changelists_list_503():
    def boom(_sid: str, _mailbox: str = ""):
        raise RuntimeError("DATABASE_URL is not set")

    route = make_changelists_list_route(list_fn=boom)
    resp = await route(_list_request())
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_changelist_patch_approved():
    def patch_fn(sid: str, message_id: str, status: str | None, lines: list | None):
        assert status == "approved"
        assert lines is None
        return {
            "message_id": message_id,
            "subject": "DD",
            "category": "changelist",
            "sub_content": None,
            "changelist_response": None,
            "hitl_status": status,
            "email_received_dttm": None,
        }

    route = make_changelist_patch_route(patch_fn=patch_fn)
    resp = await route(_patch_request("c1", {"status": "approved"}))
    assert resp.status_code == 200
    assert json.loads(resp.body)["id"] == "c1"


@pytest.mark.asyncio
async def test_changelist_patch_lines_only():
    def patch_fn(sid: str, message_id: str, status: str | None, lines: list | None):
        assert status is None
        assert lines == [{"id": "l0", "field": "hourly_pay_rate", "from": "20", "to": "22"}]
        return {
            "message_id": message_id,
            "subject": "Rate",
            "category": "changelist",
            "sub_content": None,
            "changelist_response": json.dumps(
                {
                    "clientId": "C1",
                    "title": "Rate",
                    "changes": [
                        {"id": "l0", "field": "hourly_pay_rate", "from": "20", "to": "22"}
                    ],
                }
            ),
            "hitl_status": "pending",
            "email_received_dttm": None,
        }

    route = make_changelist_patch_route(patch_fn=patch_fn)
    resp = await route(
        _patch_request(
            "c1",
            {"lines": [{"id": "l0", "field": "hourly_pay_rate", "from": "20", "to": "22"}]},
        )
    )
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["lines"][0]["to"] == "22"
