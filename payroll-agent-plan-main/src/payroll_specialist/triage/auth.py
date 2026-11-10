"""Graph / mailbox authentication helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

GraphAuthMode = Literal["delegated", "app"]


@dataclass
class GraphAuthSettings:
    mode: GraphAuthMode
    tenant_id: str
    client_id: str
    client_secret: str
    allowlist: list[str]


def graph_auth_mode() -> GraphAuthMode:
    raw = (os.environ.get("GRAPH_AUTH_MODE") or "delegated").strip().lower()
    return "app" if raw == "app" else "delegated"


def load_graph_auth() -> GraphAuthSettings | None:
    """Load Graph settings.

    - delegated (default): tenant + client id required; uses caller Bearer token (no secret).
    - app: tenant + client id + client secret required (client credentials).
    """
    mode = graph_auth_mode()
    tenant = os.environ.get("GRAPH_TENANT_ID", "").strip()
    client_id = os.environ.get("GRAPH_CLIENT_ID", "").strip()
    secret = os.environ.get("GRAPH_CLIENT_SECRET", "").strip()
    allow_raw = os.environ.get("GRAPH_MAILBOX_ALLOWLIST", "").strip()
    allowlist = [x.strip().lower() for x in allow_raw.split(",") if x.strip()]

    if mode == "delegated":
        if not (tenant and client_id):
            return None
        return GraphAuthSettings(
            mode="delegated",
            tenant_id=tenant,
            client_id=client_id,
            client_secret="",
            allowlist=allowlist,
        )

    if not (tenant and client_id and secret):
        return None
    return GraphAuthSettings(
        mode="app",
        tenant_id=tenant,
        client_id=client_id,
        client_secret=secret,
        allowlist=allowlist,
    )


def mailbox_allowed(mailbox_id: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    return mailbox_id.strip().lower() in allowlist
