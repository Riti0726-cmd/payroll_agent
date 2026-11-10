"""Triage progress callback + SSE stream route."""

from __future__ import annotations

import json

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from store.local_store import LocalTriageStore
from triage.mailbox import MailMessage, MockGraphMailbox
from triage.orchestrator import TriageOrchestrator
from triage.processed import LocalProcessedMailStore
from triage_http import make_triage_stream_route, mount_triage_stream_route


class _FakeRepo:
    def upsert_ingested_email(self, *, message):
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
async def test_orchestrator_emits_progress_events(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox(
        [
            MailMessage(
                id="m1",
                received_at="2026-09-10T12:00:00Z",
                subject="Pay Q",
                body="Why is pay low?",
                conversation_id="c1",
            ),
        ]
    )

    async def fake_process(query: str) -> dict:
        return {
            "triage": {
                "category": "qa",
                "intent": "variance",
                "confidence": 0.9,
                "employee_id": "E1",
                "pay_period": None,
                "client_id": None,
                "employee_name": None,
                "effective_date": None,
                "oos_destination": None,
            },
            "draft": "Draft",
            "qa_findings": "ok",
        }

    events: list[dict] = []
    orch = TriageOrchestrator(
        store=store,
        mailbox=mb,
        process_email_fn=fake_process,
        processed_store=processed,
        email_repo=_FakeRepo(),
    )
    store.save_specialist_config(
        "demo",
        {"mailbox_id": "box", "lookback_days": 30, "mode": "manual"},
    )
    await orch.run(specialist_id="demo", mailbox_id="box", on_progress=events.append)

    types = [e["type"] for e in events]
    assert types[0] == "run_started"
    assert "email_started" in types
    assert "email_finished" in types
    assert types[-1] == "run_finished"
    finished = events[-1]
    assert finished["succeeded"] == 1
    assert finished["failed"] == 0


def test_triage_stream_sse_emits_events(tmp_path):
    store = LocalTriageStore(str(tmp_path / "triage"))
    processed = LocalProcessedMailStore(tmp_path / "proc", specialist_id="demo")
    mb = MockGraphMailbox([])

    async def run_fn(*, specialist_id, mailbox_id=None, on_progress=None):
        assert specialist_id == "demo"
        if on_progress:
            on_progress({"type": "run_started", "runId": "r1", "mailbox": "box", "total": 0})
            on_progress(
                {
                    "type": "run_finished",
                    "runId": "r1",
                    "succeeded": 0,
                    "failed": 0,
                    "skipped": 0,
                    "summary": "none",
                }
            )
        return {}

    app = Starlette()
    mount_triage_stream_route(app, run_fn=run_fn)
    client = TestClient(app)
    with client.stream("POST", "/triage/stream?specialist_id=demo") as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes()).decode("utf-8")
    assert "event: run_started" in body
    assert "event: run_finished" in body
    assert '"total": 0' in body


def test_triage_stream_requires_specialist():
    app = Starlette()
    app.add_route("/triage/stream", make_triage_stream_route(run_fn=None), methods=["POST"])
    client = TestClient(app)
    resp = client.post("/triage/stream")
    assert resp.status_code == 400
    assert json.loads(resp.content)["detail"] == "specialist_id is required"
