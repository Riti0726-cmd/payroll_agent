"""Per-request Graph access token (delegated) via contextvars."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

_graph_access_token: ContextVar[str | None] = ContextVar("graph_access_token", default=None)


def get_graph_access_token() -> str | None:
    token = _graph_access_token.get()
    if token and token.strip():
        return token.strip()
    return None


def set_graph_access_token(token: str | None) -> Token:
    return _graph_access_token.set((token or "").strip() or None)


def reset_graph_access_token(ctx_token: Token) -> None:
    _graph_access_token.reset(ctx_token)


@contextmanager
def graph_access_token_scope(token: str | None) -> Iterator[None]:
    handle = set_graph_access_token(token)
    try:
        yield
    finally:
        reset_graph_access_token(handle)
