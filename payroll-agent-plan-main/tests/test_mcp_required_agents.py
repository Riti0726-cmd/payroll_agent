"""Triage QA / changelist require a live Snowflake MCP tool fetch."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool

from models import ChangelistBuildResult, ChangeLineBuild
from nodes.changelist import (
    MCP_REQUIRED_FINDINGS,
    build_changelist_payload,
    make_changelist_node,
)
from nodes.qa import MCP_REQUIRED_FINDINGS as QA_MCP_REQUIRED, make_qa_node
from tools.snowflake_mcp import snowflake_mcp_unavailable


@tool
def fake_cortex(query: str = "") -> str:
    """Fake Snowflake Cortex tool for tests."""
    return '{"hourly_pay_rate": 20.0, "employee_id": "EMP-1"}'


class _ReActLlm:
    """Chat model stand-in for create_agent tool loop + optional structured output."""

    def __init__(self, *, final_text: str = "done", structured: object | None = None):
        self._final_text = final_text
        self._structured = structured

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        parent = self

        class _Structured:
            async def ainvoke(self, messages, config=None, **kw):
                if parent._structured is not None:
                    return parent._structured
                return AIMessage(content=parent._final_text)

            def invoke(self, messages, config=None, **kw):
                if parent._structured is not None:
                    return parent._structured
                return AIMessage(content=parent._final_text)

        return _Structured()

    async def ainvoke(self, messages, config=None, **kwargs):
        for m in reversed(list(messages or [])):
            if isinstance(m, ToolMessage) or getattr(m, "type", None) == "tool":
                return AIMessage(content=self._final_text)
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "fake_cortex", "args": {"query": "net"}, "id": "c1"}
            ],
        )

    def invoke(self, messages, config=None, **kwargs):
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.ainvoke(messages, config=config, **kwargs)
        )


@pytest.mark.asyncio
async def test_qa_blocks_without_mcp_tools():
    node = make_qa_node(object(), object(), tools=[])
    out = await node({"query": "Why lower?", "triage": {"category": "qa", "employee_id": "E1"}})
    assert QA_MCP_REQUIRED in out["qa_findings"]
    assert out.get("qa_snowflake_fetched") is False


@pytest.mark.asyncio
async def test_qa_blocks_on_unavailable_stub_only():
    node = make_qa_node(object(), object(), tools=[snowflake_mcp_unavailable])
    out = await node({"query": "Why lower?", "triage": {"category": "qa"}})
    assert QA_MCP_REQUIRED in out["qa_findings"]
    assert out.get("qa_snowflake_fetched") is False


@pytest.mark.asyncio
async def test_qa_blocks_when_llm_skips_tools():
    class NoToolsLlm:
        def bind_tools(self, tools, **kwargs):
            return self

        async def ainvoke(self, messages, config=None, **kwargs):
            return AIMessage(content="I think net pay is 1000")

    node = make_qa_node(NoToolsLlm(), NoToolsLlm(), tools=[fake_cortex])
    out = await node({"query": "net?", "triage": {"category": "qa", "employee_id": "E1"}})
    assert QA_MCP_REQUIRED in out["qa_findings"] or "cannot verify" in out["qa_findings"].lower()
    assert out.get("qa_snowflake_fetched") is False


@pytest.mark.asyncio
async def test_qa_fetches_when_tools_called():
    llm = _ReActLlm(final_text="Net pay was 3200 per Cortex.")
    node = make_qa_node(llm, llm, tools=[fake_cortex])
    out = await node({"query": "net?", "triage": {"category": "qa", "employee_id": "E1"}})
    assert "3200" in out["qa_findings"]
    assert out.get("qa_snowflake_fetched") is True


@pytest.mark.asyncio
async def test_changelist_blocks_without_mcp_tools():
    node = make_changelist_node(object(), object(), tools=[])
    out = await node(
        {
            "query": "raise to 22",
            "triage": {
                "category": "changelist",
                "client_id": "C1",
                "employee_id": "E1",
                "change_type": "hourly_pay_rate",
                "new_value": "22",
            },
        }
    )
    assert out["changelist"]["snowflake_fetched"] is False
    assert out["changelist"]["status"] == "incomplete"
    assert out["changelist"]["changes"] == []
    assert MCP_REQUIRED_FINDINGS in out["changelist"]["findings"]


@pytest.mark.asyncio
async def test_changelist_fetches_via_mcp_then_builds():
    build = ChangelistBuildResult(
        changes=[
            ChangeLineBuild.model_validate(
                {
                    "field": "hourly_pay_rate",
                    "from": "20",
                    "to": "22",
                    "incomplete": False,
                }
            )
        ],
        findings="from Cortex",
        sources=[{"label": "fake_cortex", "detail": "rate"}],
    )

    class StructuredModel:
        async def ainvoke(self, messages, config=None, **kwargs):
            return build

    tool_llm = _ReActLlm(final_text="done")
    node = make_changelist_node(tool_llm, StructuredModel(), tools=[fake_cortex])
    out = await node(
        {
            "query": "raise to 22",
            "triage": {
                "category": "changelist",
                "client_id": "C1",
                "employee_id": "E1",
                "change_type": "hourly_pay_rate",
                "new_value": "22",
            },
        }
    )
    assert out["changelist"]["snowflake_fetched"] is True
    assert out["changelist"]["changes"][0]["from"] == "20"
    assert out["changelist"]["status"] == "pending"


def test_build_changelist_no_email_fallback_without_snowflake_flag():
    payload = build_changelist_payload(
        {
            "client_id": "12890",
            "change_type": "hourly_pay_rate",
            "new_value": "22",
        },
        query="raise",
        snowflake_fetched=False,
    )
    assert payload["changes"] == []
    assert payload["status"] == "incomplete"
