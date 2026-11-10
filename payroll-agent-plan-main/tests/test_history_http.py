import json

import pytest
from starlette.requests import Request

from history_http import make_history_route


def _request(query: bytes = b"specialist_id=default") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/history",
        "raw_path": b"/history",
        "query_string": query,
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_history_200():
    def list_fn(sid: str, mailbox: str, status: str):
        assert sid == "default"
        assert status == "all"
        return [
            {
                "message_id": "m1",
                "subject": "Closed",
                "category": "qa",
                "hitl_status": "done",
                "priority_rate": "medium",
                "email_received_dttm": "2026-09-20T10:00:00+05:30",
                "content": "Body",
                "sub_content": None,
            }
        ]

    route = make_history_route(list_fn=list_fn)
    resp = await route(_request())
    assert resp.status_code == 200
    assert json.loads(resp.body)["items"][0]["status"] == "done"


@pytest.mark.asyncio
async def test_history_400_bad_status():
    route = make_history_route(list_fn=lambda *_a: [])
    resp = await route(_request(b"specialist_id=default&status=nope"))
    assert resp.status_code == 400
