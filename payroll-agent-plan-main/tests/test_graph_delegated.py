"""Delegated Graph auth + /me/messages path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from triage.auth import load_graph_auth
from triage.mailbox import RealGraphMailbox, get_mailbox_port
from triage.request_context import graph_access_token_scope


def test_load_graph_auth_delegated_without_secret(monkeypatch):
    monkeypatch.setenv("GRAPH_AUTH_MODE", "delegated")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    auth = load_graph_auth()
    assert auth is not None
    assert auth.mode == "delegated"
    assert auth.client_secret == ""


def test_load_graph_auth_app_requires_secret(monkeypatch):
    monkeypatch.setenv("GRAPH_AUTH_MODE", "app")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    assert load_graph_auth() is None


def test_delegated_list_messages_uses_me_and_bearer(monkeypatch):
    monkeypatch.setenv("GRAPH_AUTH_MODE", "delegated")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")

    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "value": [
                    {
                        "id": "m1",
                        "receivedDateTime": "2026-09-20T12:00:00Z",
                        "from": {"emailAddress": {"address": "a@b.com"}},
                        "subject": "Hello",
                        "bodyPreview": "preview",
                        "body": {"content": "body"},
                        "conversationId": "c1",
                        "isRead": False,
                        "webLink": "",
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["headers"] = kwargs.get("headers")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            captured["url"] = url
            return FakeResponse()

    mb = RealGraphMailbox()
    with graph_access_token_scope("user-graph-token"):
        with patch("httpx.Client", FakeClient):
            msgs = mb.list_messages(
                "irrelevant@example.com",
                window_start="2026-09-01T00:00:00Z",
                window_end="2026-09-30T00:00:00Z",
            )

    assert captured["headers"]["Authorization"] == "Bearer user-graph-token"
    assert captured["url"].startswith("https://graph.microsoft.com/v1.0/me/messages")
    assert len(msgs) == 1
    assert msgs[0].subject == "Hello"


def test_delegated_requires_bearer_token(monkeypatch):
    monkeypatch.setenv("GRAPH_AUTH_MODE", "delegated")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    mb = RealGraphMailbox()
    with pytest.raises(RuntimeError, match="Bearer"):
        mb.list_messages(
            "x@y.com",
            window_start="2026-09-01T00:00:00Z",
            window_end="2026-09-30T00:00:00Z",
        )


def test_get_mailbox_port_delegated(monkeypatch):
    monkeypatch.setenv("GRAPH_AUTH_MODE", "delegated")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    port = get_mailbox_port()
    assert isinstance(port, RealGraphMailbox)
