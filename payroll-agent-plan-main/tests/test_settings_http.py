import json

import pytest
from starlette.requests import Request

from settings_http import make_settings_get_route, make_settings_put_route


def _request(method: str, query: bytes = b"specialist_id=default", body: bytes = b""):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/settings",
        "raw_path": b"/settings",
        "query_string": query,
        "headers": [(b"content-type", b"application/json")] if body else [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_settings_get_400():
    route = make_settings_get_route(
        get_fn=lambda _sid: {
            "lookbackDays": 7,
            "mode": "manual",
            "intervalHours": 2,
            "runs": [],
        }
    )
    resp = await route(_request("GET", b""))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_settings_get_200():
    route = make_settings_get_route(
        get_fn=lambda sid: {
            "lookbackDays": 7,
            "mode": "manual",
            "intervalHours": 2,
            "runs": [
                {
                    "runId": "r1",
                    "startedAt": "2026-09-25T10:00:00+00:00",
                    "status": "succeeded",
                    "result": "ok",
                }
            ],
        }
    )
    resp = await route(_request("GET"))
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["lookbackDays"] == 7
    assert data["runs"][0]["runId"] == "r1"


@pytest.mark.asyncio
async def test_settings_put_400_bad_interval():
    route = make_settings_put_route(put_fn=lambda sid, payload: payload.model_dump())
    body = json.dumps({"lookbackDays": 7, "mode": "manual", "intervalHours": 3}).encode()
    resp = await route(_request("PUT", body=body))
    assert resp.status_code == 400
