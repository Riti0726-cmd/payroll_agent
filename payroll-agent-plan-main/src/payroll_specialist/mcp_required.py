"""Shared helpers: triage QA/changelist require live Snowflake MCP fetches."""

from __future__ import annotations

from typing import Any, Mapping

STUB_TOOL_NAME = "snowflake_mcp_unavailable"

MCP_REQUIRED_FINDINGS = (
    "Snowflake MCP is required for this step. No live Cortex tool fetch was completed. "
    "Cannot invent payroll figures or change lines. Configure mcp_config.json / MCP auth and retry."
)


def has_live_mcp_tools(tools_by_name: Mapping[str, Any]) -> bool:
    """True when at least one non-stub MCP tool is bound."""
    if not tools_by_name:
        return False
    live = [n for n in tools_by_name if n != STUB_TOOL_NAME]
    return bool(live)


def tool_result_ok(result: Any) -> bool:
    from message_text import extract_message_text

    text = extract_message_text(result).lower() if result is not None else ""
    if not text:
        text = str(result or "").strip().lower()
    if not text:
        return False
    if text.startswith("tool execution error"):
        return False
    if "not available" in text:
        return False
    if "snowflake mcp is not configured" in text:
        return False
    if "mcp error calling tool" in text or "sql compilation error" in text:
        return False
    if '"status": "error"' in text or '"status":"error"' in text:
        return False
    return True


def agent_messages_used_mcp(messages: Any) -> bool:
    """True when a ReAct agent transcript includes a successful live MCP tool result."""
    if not messages:
        return False
    for msg in messages:
        msg_type = getattr(msg, "type", None) or (
            msg.get("type") if isinstance(msg, dict) else None
        )
        if msg_type != "tool":
            continue
        name = getattr(msg, "name", None) or (
            msg.get("name") if isinstance(msg, dict) else None
        )
        if str(name or "") == STUB_TOOL_NAME:
            continue
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            content = msg.get("content")
        if tool_result_ok(content):
            return True
    return False
