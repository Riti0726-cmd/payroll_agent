"""ASGI middleware: capture Authorization Bearer for delegated Graph."""

from __future__ import annotations

import logging
from typing import Any, Callable

from triage.request_context import reset_graph_access_token, set_graph_access_token

logger = logging.getLogger("payroll-specialist")


def _bearer_from_headers(headers: list[tuple[bytes, bytes]]) -> str | None:
    for key, value in headers:
        if key.lower() == b"authorization":
            raw = value.decode("latin-1", errors="ignore").strip()
            if raw.lower().startswith("bearer "):
                token = raw[7:].strip()
                return token or None
            return None
    return None


class GraphTokenMiddleware:
    """Pure ASGI middleware compatible with Starlette ``add_middleware``."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        token = _bearer_from_headers(list(scope.get("headers") or []))
        handle = set_graph_access_token(token)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_graph_access_token(handle)


def mount_graph_token_middleware(app: Any) -> None:
    """Register middleware so inbound Bearer tokens reach RealGraphMailbox."""
    if getattr(app, "_payroll_graph_token_mw", False):
        return
    app.add_middleware(GraphTokenMiddleware)
    app._payroll_graph_token_mw = True
    logger.info("Mounted GraphTokenMiddleware (delegated Mail.Read bearer)")
