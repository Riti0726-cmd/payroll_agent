"""Resilient ainvoke for create_agent graphs that call Snowflake MCP tools."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("payroll-specialist")

_RETRYABLE_MARKERS = (
    "taskgroup",
    "unhandled errors",
    "connection reset",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "broken pipe",
    "server disconnected",
    "mcp error",
)


def _exception_text(exc: BaseException) -> str:
    parts = [str(exc)]
    group = getattr(exc, "exceptions", None)
    if group:
        for sub in group:
            parts.append(str(sub))
            cause = getattr(sub, "__cause__", None) or getattr(sub, "__context__", None)
            if cause:
                parts.append(str(cause))
    cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    if cause:
        parts.append(str(cause))
    return " | ".join(parts)


def is_retryable_mcp_error(exc: BaseException) -> bool:
    text = _exception_text(exc).lower()
    return any(marker in text for marker in _RETRYABLE_MARKERS)


async def ainvoke_mcp_agent(
    agent: Any,
    payload: dict[str, Any],
    *,
    attempts: int = 3,
    label: str = "mcp_agent",
) -> Any:
    """Invoke a LangGraph create_agent graph with retries on transient MCP failures."""
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            if hasattr(agent, "ainvoke"):
                return await agent.ainvoke(payload)
            return agent.invoke(payload)
        except BaseException as exc:  # noqa: BLE001 — surface nested TaskGroup causes
            last = exc
            detail = _exception_text(exc)
            if attempt >= attempts or not is_retryable_mcp_error(exc):
                logger.warning("%s failed (attempt %s/%s): %s", label, attempt, attempts, detail)
                raise
            logger.warning(
                "%s retryable MCP failure (attempt %s/%s): %s",
                label,
                attempt,
                attempts,
                detail,
            )
            await asyncio.sleep(1.5 * attempt)
    assert last is not None
    raise last
