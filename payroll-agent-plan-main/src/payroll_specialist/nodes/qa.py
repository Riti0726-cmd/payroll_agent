"""QA specialist node — create_agent ReAct (Analyst → sql_query_executor)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage

from mcp_agent_invoke import ainvoke_mcp_agent
from mcp_required import (
    MCP_REQUIRED_FINDINGS,
    agent_messages_used_mcp,
    has_live_mcp_tools,
)
from message_text import extract_message_text
from prompts import QA_INSTRUCTIONS
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")

__all__ = ["MCP_REQUIRED_FINDINGS", "make_qa_node"]


def make_qa_node(qa_llm: Any, qa_model: Any, tools: Sequence[Any]) -> Callable:
    tools_list = list(tools) if tools else []
    tools_by_name = {t.name: t for t in tools_list}
    model = qa_model or qa_llm
    agent = (
        create_agent(
            model,
            tools=tools_list,
            system_prompt=QA_INSTRUCTIONS,
            name="payroll-qa-specialist",
        )
        if has_live_mcp_tools(tools_by_name)
        else None
    )

    async def qa_specialist_node(state: PayrollState) -> dict:
        if state.get("mode") == "triage" and state.get("triage_summary"):
            return {}

        triage = state.get("triage") or {}
        period = triage.get("pay_period") or "not specified"
        emp_id = triage.get("employee_id") or "not specified"
        client_id = triage.get("client_id") or "not specified"
        query = state.get("query", "")

        with step_span(
            "qa_specialist",
            category="qa",
            employee_id=emp_id if emp_id != "not specified" else None,
            tool="snowflake_cortex",
        ):
            if agent is None:
                return {
                    "qa_findings": MCP_REQUIRED_FINDINGS,
                    "qa_snowflake_fetched": False,
                }

            prompt = (
                f"Client ID: {client_id}\n"
                f"Employee ID: {emp_id}\n"
                f"Pay period: {period}\n"
                f"Inquiry: {query}\n\n"
                "Use sv_employee_payroll (or workforce/benefits as needed). "
                "Call one Analyst tool, then sql_query_executor with that SQL. "
                "If Analyst errors or is unavailable, immediately call sql_query_executor directly with a SELECT query on "
                "PAYROLL_DB.PAYROLL_SCHEMA.SV_EMPLOYEE_PAYROLL, SV_HR_WORKFORCE, or SV_EMPLOYEE_BENEFITS. "
                "If net pay is not in the semantic model, compare gross/regular/OT/deductions "
                "from executed rows and say net is unavailable. Never invent figures."
            )

            try:
                result = await ainvoke_mcp_agent(
                    agent,
                    {"messages": [HumanMessage(content=prompt)]},
                    attempts=3,
                    label="qa_specialist",
                )

                msgs = result.get("messages", []) if isinstance(result, dict) else []
                if not agent_messages_used_mcp(msgs):
                    return {
                        "qa_findings": MCP_REQUIRED_FINDINGS,
                        "qa_snowflake_fetched": False,
                    }

                findings = ""
                for msg in reversed(msgs):
                    if isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai":
                        if getattr(msg, "tool_calls", None):
                            continue
                        findings = extract_message_text(getattr(msg, "content", ""))
                        if findings:
                            break
                if not findings:
                    return {
                        "qa_findings": MCP_REQUIRED_FINDINGS,
                        "qa_snowflake_fetched": False,
                    }
                return {"qa_findings": findings, "qa_snowflake_fetched": True}

            except Exception as exc:
                logger.warning("QA Specialist invocation failed: %s", exc)
                return {
                    "qa_findings": MCP_REQUIRED_FINDINGS + f" ({exc})",
                    "qa_snowflake_fetched": False,
                }

    return qa_specialist_node
