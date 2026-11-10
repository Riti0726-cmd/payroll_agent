"""Routing agent — out_of_scope internal department draft (no Snowflake)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from message_text import extract_message_text
from prompts import ROUTING_INSTRUCTIONS
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")

_DEST_LABELS = {
    "benefits": "Benefits",
    "tax": "Tax / Corporate Tax",
    "workers_comp": "Workers Compensation",
    "other": "General HR / Other",
}


def make_routing_node(routing_model: Any) -> Callable:
    async def routing_agent_node(state: PayrollState) -> dict:
        if state.get("mode") == "triage" and state.get("triage_summary"):
            return {}

        triage = state.get("triage") or {}
        dest = str(triage.get("oos_destination") or "other").lower()
        dest_label = _DEST_LABELS.get(dest, _DEST_LABELS["other"])
        query = state.get("query", "")
        emp_id = triage.get("employee_id") or "General"

        with step_span(
            "routing_agent",
            category="out_of_scope",
            oos_destination=dest,
            employee_id=None if emp_id == "General" else emp_id,
        ):
            header = (
                f"**Triaged Category:** OUT_OF_SCOPE\n"
                f"**Routing Destination:** {dest_label}\n"
                f"**Employee ID:** {emp_id}\n\n"
            )
            prompt = (
                f"Destination department: {dest_label} ({dest})\n"
                f"Employee ID: {emp_id}\n"
                f"Original inquiry:\n{query}\n\n"
                "Draft the internal routing note now."
            )
            sys_msg = SystemMessage(content=ROUTING_INSTRUCTIONS)
            user_msg = HumanMessage(content=prompt)

            try:
                if hasattr(routing_model, "ainvoke"):
                    result = await routing_model.ainvoke([sys_msg, user_msg])
                else:
                    result = routing_model.invoke([sys_msg, user_msg])
                body = extract_message_text(getattr(result, "content", result))
                if not body:
                    raw = getattr(result, "content", result)
                    body = extract_message_text(str(raw) if raw is not None else "")
                if "**Triaged Category:** OUT_OF_SCOPE" not in body:
                    body = header + body
                return {"messages": [AIMessage(content=body)], "draft": body}
            except Exception as exc:
                logger.error("Routing agent invocation failed: %s", exc)
                fallback = (
                    f"{header}"
                    f"Please route this inquiry to {dest_label}. "
                    "The payroll specialist mailbox cannot resolve this request."
                )
                return {"messages": [AIMessage(content=fallback)], "draft": fallback}

    return routing_agent_node
