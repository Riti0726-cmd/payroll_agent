"""Drafting specialist node — streams final employee-facing email."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from prompts import DRAFTER_INSTRUCTIONS
from message_text import extract_message_text
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")


def make_drafting_node(drafter_model: Any) -> Callable:
    async def drafting_specialist_node(state: PayrollState) -> dict:
        # Completed triage run: surface consolidated summary
        if state.get("mode") == "triage" and state.get("triage_summary"):
            with step_span("finalize_run", mode="triage"):
                summary = state["triage_summary"]
                return {"messages": [AIMessage(content=summary)], "draft": summary}

        triage = state.get("triage") or {}
        validation = state.get("validation") or {}
        changelist = state.get("changelist") or {}
        category = str(triage.get("category", "qa")).upper()
        emp_id = triage.get("employee_id") or "General"
        period = triage.get("pay_period") or "not specified"
        query = state.get("query", "")
        needs_clarification = str(validation.get("status") or "").lower() in (
            "needs_clarification",
            "invalid",
        )

        with step_span(
            "drafting_specialist",
            category="clarification" if needs_clarification else category.lower(),
            employee_id=None if emp_id == "General" else emp_id,
        ):
            header_instruction = (
                "IMPORTANT FORMATTING INSTRUCTION: You MUST start your response immediately "
                "with these two lines:\n"
                f"**Triaged Category:** {category}\n"
                f"**Employee ID:** {emp_id}\n\n"
            )

            if needs_clarification:
                draft_prompt = (
                    f"{header_instruction}"
                    f"Original inquiry:\n{query}\n\n"
                    f"Validation status: {validation.get('status')}\n"
                    f"Missing: {validation.get('missing')}\n"
                    f"Notes: {validation.get('notes')}\n\n"
                    "Draft a CLARIFICATION email asking the specialist/client for the missing "
                    "client/employee/period/values. Do not invent payroll figures."
                )
            elif category == "QA":
                draft_prompt = (
                    f"{header_instruction}"
                    f"Original Employee Inquiry:\n{query}\n\n"
                    f"Category: QA\n"
                    f"Employee ID: {emp_id}\n"
                    f"Pay period: {period}\n\n"
                    f"Snowflake / MCP findings:\n{state.get('qa_findings', 'No tool findings available.')}\n\n"
                    "Draft a professional payroll specialist email with an itemized deduction table only if those "
                    "figures appear in the findings. Do not invent numbers."
                )
            elif category == "CHANGELIST":
                changes_json = json.dumps(changelist.get("changes") or [], default=str)
                draft_prompt = (
                    f"{header_instruction}"
                    f"Original Employee Inquiry:\n{query}\n\n"
                    f"Category: CHANGELIST\n"
                    f"Intent: {triage.get('intent', '')}\n"
                    f"Structured changes:\n{changes_json}\n"
                    f"Findings:\n{changelist.get('findings') or state.get('qa_findings') or 'none'}\n"
                    f"Due date: {changelist.get('due_date')}\n\n"
                    "Draft using the structured change facts when present. Do not invent numbers. "
                    "Only use generic portal steps if changes are empty."
                )
            else:
                draft_prompt = (
                    f"{header_instruction}"
                    f"Original Employee Inquiry:\n{query}\n\n"
                    f"Category: {category}\n"
                    f"Intent: {triage.get('intent', '')}\n\n"
                    "Draft a professional payroll specialist email response:\n"
                    "- If TODO: Confirm receipt of the task/approval request, outline expected turnaround "
                    "time, and next action steps."
                )

            sys_msg = SystemMessage(content=DRAFTER_INSTRUCTIONS)
            user_msg = HumanMessage(content=draft_prompt)

            try:
                if hasattr(drafter_model, "ainvoke"):
                    result = await drafter_model.ainvoke([sys_msg, user_msg])
                else:
                    result = drafter_model.invoke([sys_msg, user_msg])

                content = extract_message_text(getattr(result, "content", result))
                if not content:
                    # Last resort — never persist raw list/dict reprs.
                    raw = getattr(result, "content", result)
                    content = extract_message_text(str(raw) if raw is not None else "")
                expected_prefix = f"**Triaged Category:** {category}"
                if expected_prefix not in content:
                    content = (
                        f"**Triaged Category:** {category}\n"
                        f"**Employee ID:** {emp_id}\n\n{content}"
                    )
                return {"messages": [AIMessage(content=content)], "draft": content}
            except Exception as exc:
                logger.error("Drafter invocation failed: %s", exc)
                fallback_text = (
                    f"**Triaged Category:** {category}\n**Employee ID:** {emp_id}\n\n"
                    f"We have received your payroll request regarding: {query}. "
                    "Our team will review this shortly."
                )
                return {"messages": [AIMessage(content=fallback_text)], "draft": fallback_text}

    return drafting_specialist_node
