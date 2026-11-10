"""Validation agent — create_agent tool loop, then structured ValidationResult."""

from __future__ import annotations

import logging
from typing import Any, Callable, Sequence

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage

from mcp_agent_invoke import ainvoke_mcp_agent
from mcp_required import agent_messages_used_mcp, has_live_mcp_tools
from models import ValidationResult
from prompts import VALIDATION_INSTRUCTIONS
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")


def _heuristic_validation(triage: dict) -> ValidationResult:
    missing: list[str] = []
    if not triage.get("client_id"):
        missing.append("client_id")
    if not triage.get("employee_id") and not triage.get("employee_name"):
        missing.append("employee_id")
    if missing:
        return ValidationResult(
            status="needs_clarification",
            client_ok=bool(triage.get("client_id")) or None,
            employee_ok=bool(triage.get("employee_id") or triage.get("employee_name")) or None,
            missing=missing,
            notes="Missing required identity fields for payroll lookup.",
        )
    return ValidationResult(
        status="ok",
        client_ok=True if triage.get("client_id") else None,
        employee_ok=True,
        missing=[],
        notes="Identity fields present; proceeding without live Snowflake verification.",
    )


def make_validation_node(
    validation_llm: Any,
    validation_model: Any,
    tools: Sequence[Any],
) -> Callable:
    tools_list = list(tools) if tools else []
    tools_by_name = {t.name: t for t in tools_list}
    base_model = validation_llm or validation_model
    agent = (
        create_agent(
            base_model,
            tools=tools_list,
            system_prompt=VALIDATION_INSTRUCTIONS,
            name="payroll-validation",
        )
        if has_live_mcp_tools(tools_by_name)
        else None
    )

    async def validation_agent_node(state: PayrollState) -> dict:
        triage = state.get("triage") or {}
        category = str(triage.get("category") or "").lower()
        if category == "out_of_scope":
            return {
                "validation": ValidationResult(
                    status="ok",
                    notes="Skipped validation for out_of_scope.",
                ).model_dump()
            }

        query = state.get("query", "")
        with step_span("validation_agent", category=category or None):
            prompt = (
                f"Category: {category}\n"
                f"client_id: {triage.get('client_id')}\n"
                f"employee_id: {triage.get('employee_id')}\n"
                f"employee_name: {triage.get('employee_name')}\n"
                f"Inquiry:\n{query}\n\n"
                "Use sv_hr_workforce first to confirm this client_id and employee_id exist "
                "(return employee_id, client_id, full_name, status_class). "
                "Call sql_query_executor with the Analyst SQL. If Analyst errors or is unavailable, "
                "immediately call sql_query_executor directly with a SELECT query on "
                "PAYROLL_DB.PAYROLL_SCHEMA.SV_HR_WORKFORCE to confirm the client and employee exist. "
                "Identity validation does not require payroll history rows."
            )

            if agent is None:
                try:
                    messages = [
                        SystemMessage(content=VALIDATION_INSTRUCTIONS),
                        HumanMessage(content=prompt),
                    ]
                    model = validation_model or validation_llm
                    if hasattr(model, "ainvoke"):
                        final = await model.ainvoke(messages)
                    else:
                        final = model.invoke(messages)
                    if isinstance(final, ValidationResult):
                        return {"validation": final.model_dump()}
                    if isinstance(final, dict) and "status" in final:
                        return {
                            "validation": ValidationResult.model_validate(final).model_dump()
                        }
                except Exception as exc:
                    logger.debug("Structured validation fallback: %s", exc)
                return {"validation": _heuristic_validation(triage).model_dump()}

            try:
                result = await ainvoke_mcp_agent(
                    agent,
                    {"messages": [HumanMessage(content=prompt)]},
                    attempts=3,
                    label="validation_agent",
                )

                msgs = result.get("messages", []) if isinstance(result, dict) else []
                if not agent_messages_used_mcp(msgs):
                    return {
                        "validation": ValidationResult(
                            status="needs_clarification",
                            missing=["verification"],
                            notes=(
                                "Snowflake Analyst/SQL executor did not return result rows "
                                "to verify client/employee."
                            ),
                        ).model_dump()
                    }

                structured = validation_model or validation_llm
                if hasattr(structured, "ainvoke"):
                    final = await structured.ainvoke(
                        [SystemMessage(content=VALIDATION_INSTRUCTIONS), *msgs]
                    )
                else:
                    final = structured.invoke(
                        [SystemMessage(content=VALIDATION_INSTRUCTIONS), *msgs]
                    )
                if isinstance(final, ValidationResult):
                    return {"validation": final.model_dump()}
                if isinstance(final, dict) and "status" in final:
                    return {
                        "validation": ValidationResult.model_validate(final).model_dump()
                    }
                return {"validation": _heuristic_validation(triage).model_dump()}
            except Exception as exc:
                logger.warning("Validation agent failed: %s", exc)
                return {
                    "validation": ValidationResult(
                        status="needs_clarification",
                        missing=["verification"],
                        notes=f"Snowflake validation unavailable: {exc}",
                    ).model_dump()
                }

    return validation_agent_node


def route_after_validation(state: PayrollState) -> str:
    triage = state.get("triage") or {}
    category = str(triage.get("category") or "qa").lower()
    if category == "out_of_scope":
        return "routing_agent"

    validation = state.get("validation") or {}
    status = str(validation.get("status") or "").lower()
    if status in ("needs_clarification", "invalid"):
        return "drafting_specialist"

    if category == "qa":
        return "qa_specialist"
    if category == "changelist":
        return "changelist_agent"
    return "drafting_specialist"
