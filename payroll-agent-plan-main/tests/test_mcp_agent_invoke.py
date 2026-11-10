"""Tests for MCP agent retry helper."""

from __future__ import annotations

import pytest

from mcp_agent_invoke import ainvoke_mcp_agent, is_retryable_mcp_error


def test_taskgroup_message_is_retryable():
    assert is_retryable_mcp_error(RuntimeError("unhandled errors in a TaskGroup (1 sub-exception)"))


def test_schema_error_not_retryable():
    assert not is_retryable_mcp_error(ValueError("Invalid schema for response_format"))


@pytest.mark.asyncio
async def test_ainvoke_retries_then_succeeds():
    calls = {"n": 0}

    class Flaky:
        async def ainvoke(self, payload):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("unhandled errors in a TaskGroup (1 sub-exception)")
            return {"messages": ["ok"]}

    out = await ainvoke_mcp_agent(Flaky(), {"messages": []}, attempts=3, label="test")
    assert out == {"messages": ["ok"]}
    assert calls["n"] == 3
