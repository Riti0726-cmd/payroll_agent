"""Changelist agent — create_agent tool loop, then structured ChangelistBuildResult."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from due_priority import apply_due_and_priority
from mcp_agent_invoke import ainvoke_mcp_agent
from mcp_required import (
    MCP_REQUIRED_FINDINGS,
    agent_messages_used_mcp,
    has_live_mcp_tools,
)
from models import ChangelistBuildResult, ChangeLineBuild
from prompts import CHANGELIST_INSTRUCTIONS
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")

__all__ = [
    "MCP_REQUIRED_FINDINGS",
    "build_changelist_payload",
    "make_changelist_node",
]


def build_changelist_payload(
    triage: dict,
    *,
    build: ChangelistBuildResult | None = None,
    title: str = "",
    query: str = "",
    snowflake_fetched: bool = False,
) -> dict[str, Any]:
    """Assemble Neon changelist_response. Lines only when Snowflake rows were fetched."""
    build = build or ChangelistBuildResult()
    changes_in: list = list(build.changes) if snowflake_fetched else []

    changes: list[dict[str, Any]] = []
    any_incomplete = False
    for idx, line in enumerate(changes_in):
        if isinstance(line, ChangeLineBuild):
            data = line.model_dump(by_alias=True)
        elif isinstance(line, dict):
            data = dict(line)
        else:
            continue
        incomplete = bool(data.get("incomplete"))
        if data.get("from") is None or data.get("to") is None:
            incomplete = True
        any_incomplete = any_incomplete or incomplete
        changes.append(
            {
                "id": str(data.get("id") or f"l{idx}"),
                "field": str(data.get("field") or ""),
                "from": data.get("from"),
                "to": data.get("to"),
                "effective_date": data.get("effective_date") or triage.get("effective_date"),
                "recommended_system": data.get("recommended_system")
                or triage.get("system_target")
                or "unknown",
                "recommended_field": data.get("recommended_field"),
                "notes": data.get("notes") or "",
                "reviewed": False,
                "incomplete": incomplete,
            }
        )

    findings = build.findings or ""
    if not snowflake_fetched:
        findings = findings or MCP_REQUIRED_FINDINGS
        status = "incomplete"
    else:
        status = "incomplete" if any_incomplete or not changes else "pending"

    payload: dict[str, Any] = {
        "agent": "changelist",
        "status": status,
        "snowflake_required": True,
        "snowflake_fetched": bool(snowflake_fetched),
        "clientId": triage.get("client_id") or "unknown",
        "title": (title or "").strip() or (triage.get("intent") or "Change request"),
        "parameters": {
            "client_id": triage.get("client_id"),
            "employee_id": triage.get("employee_id"),
            "effective_date": triage.get("effective_date"),
            "change_type": triage.get("change_type"),
        },
        "changes": changes,
        "lines": [],
        "findings": findings,
        "sources": [
            (s.model_dump() if hasattr(s, "model_dump") else dict(s))
            for s in (build.sources or [])
        ]
        if snowflake_fetched
        else [],
    }
    if snowflake_fetched and build.client_active_employees is not None:
        payload["client_active_employees"] = build.client_active_employees
    if snowflake_fetched and build.calendar_cutoff:
        payload["calendar_cutoff"] = build.calendar_cutoff

    return apply_due_and_priority(payload, query=query)


def make_changelist_node(
    changelist_llm: Any,
    changelist_model: Any,
    tools: Sequence[Any],
) -> Callable:
    tools_list = list(tools) if tools else []
    tools_by_name = {t.name: t for t in tools_list}
    base_model = changelist_llm or changelist_model
    agent = (
        create_agent(
            base_model,
            tools=tools_list,
            system_prompt=CHANGELIST_INSTRUCTIONS,
            name="payroll-changelist",
        )
        if has_live_mcp_tools(tools_by_name)
        else None
    )

    async def changelist_agent_node(state: PayrollState) -> dict:
        triage = state.get("triage") or {}
        query = state.get("query", "")
        with step_span(
            "changelist_agent",
            category="changelist",
            employee_id=triage.get("employee_id"),
        ):
            if agent is None:
                payload = build_changelist_payload(
                    triage,
                    build=ChangelistBuildResult(findings=MCP_REQUIRED_FINDINGS),
                    query=query,
                    snowflake_fetched=False,
                )
                return {"changelist": payload, "qa_findings": payload["findings"]}

            prompt = (
                f"client_id: {triage.get('client_id')}\n"
                f"employee_id: {triage.get('employee_id')}\n"
                f"employee_name: {triage.get('employee_name')}\n"
                f"change_type: {triage.get('change_type')}\n"
                f"previous_value: {triage.get('previous_value')}\n"
                f"new_value: {triage.get('new_value')}\n"
                f"effective_date: {triage.get('effective_date')}\n"
                f"Inquiry:\n{query}\n\n"
                "Call Cortex Analyst to generate SQL, then sql_query_executor with that SQL. "
                "If Analyst errors or is unavailable, immediately call sql_query_executor directly with a SELECT query on "
                "PAYROLL_DB.PAYROLL_SCHEMA.SV_HR_WORKFORCE or SV_EMPLOYEE_PAYROLL. "
                "Then produce structured change lines. Never invent from/to amounts."
            )

            try:
                result = await ainvoke_mcp_agent(
                    agent,
                    {"messages": [HumanMessage(content=prompt)]},
                    attempts=3,
                    label="changelist_agent",
                )

                msgs = result.get("messages", []) if isinstance(result, dict) else []
                fetched = agent_messages_used_mcp(msgs)
                if not fetched:
                    build = ChangelistBuildResult(findings=MCP_REQUIRED_FINDINGS)
                else:
                    structured = changelist_model or changelist_llm
                    if hasattr(structured, "ainvoke"):
                        final = await structured.ainvoke(
                            [SystemMessage(content=CHANGELIST_INSTRUCTIONS), *msgs]
                        )
                    else:
                        final = structured.invoke(
                            [SystemMessage(content=CHANGELIST_INSTRUCTIONS), *msgs]
                        )
                    if isinstance(final, ChangelistBuildResult):
                        build = final
                    elif isinstance(final, dict) and (
                        "changes" in final or "findings" in final
                    ):
                        build = ChangelistBuildResult.model_validate(final)
                    else:
                        build = ChangelistBuildResult(
                            findings=str(getattr(final, "content", final))
                        )
            except Exception as exc:
                logger.warning("Changelist agent failed: %s", exc)
                build = ChangelistBuildResult(
                    findings=f"{MCP_REQUIRED_FINDINGS} ({exc})"
                )
                fetched = False

            payload = build_changelist_payload(
                triage,
                build=build,
                query=query,
                snowflake_fetched=fetched,
            )
            with step_span("due_date_priority", category="changelist"):
                pass
            return {"changelist": payload, "qa_findings": payload.get("findings") or None}

    return changelist_agent_node
