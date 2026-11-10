import json

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from models import QaChatResponse, QaSource
from qa_http import make_qa_route


def _request(body: dict | None, *, method: str = "POST") -> Request:
    payload = b"" if body is None else json.dumps(body).encode("utf-8")
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": "/qa",
        "raw_path": b"/qa",
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8088),
    }

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_qa_route_400_on_empty_messages():
    route = make_qa_route(runner=lambda _m: QaChatResponse(answer="x", sources=[]))
    resp = await route(_request({"messages": []}))
    assert resp.status_code == 400
    assert "messages" in json.loads(resp.body)["detail"]


@pytest.mark.asyncio
async def test_qa_route_200_answer_and_sources():
    async def runner(messages):
        assert messages[0].content == "Why lower?"
        return QaChatResponse(
            answer="Net dropped due to dental.",
            sources=[QaSource(label="structured", detail="Aug 2026")],
        )

    route = make_qa_route(runner=runner)
    resp = await route(_request({"messages": [{"role": "user", "content": "Why lower?"}]}))
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["answer"].startswith("Net dropped")
    assert data["sources"][0]["label"] == "structured"


@pytest.mark.asyncio
async def test_qa_route_502_on_runner_failure():
    def boom(_messages):
        raise RuntimeError("agent down")

    route = make_qa_route(runner=boom)
    resp = await route(_request({"messages": [{"role": "user", "content": "pay?"}]}))
    assert resp.status_code == 502
    assert "unavailable" in json.loads(resp.body)["detail"].lower()
