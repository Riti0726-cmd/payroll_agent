"""Classifier node — qa | changelist | todo | out_of_scope."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from langchain_core.messages import HumanMessage, SystemMessage

from models import ClassificationResult
from prompts import CLASSIFIER_INSTRUCTIONS
from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")


def route_by_category(state: PayrollState) -> str:
    """After classifier: OOS → routing; everything else → validation first."""
    triage = state.get("triage") or {}
    category = str(triage.get("category", "qa")).lower()
    if category == "out_of_scope":
        return "routing_agent"
    return "validation_agent"


def make_classifier_node(classifier_llm: Any) -> Callable:
    async def classifier_node(state: PayrollState) -> dict:
        # Triage mode already classified emails inside the orchestrator
        if state.get("mode") == "triage" and state.get("triage_summary"):
            return {}

        query = state.get("query", "")
        with step_span("classifier"):
            system_msg = SystemMessage(content=CLASSIFIER_INSTRUCTIONS)
            user_msg = HumanMessage(content=query)
            try:
                if hasattr(classifier_llm, "ainvoke"):
                    result: ClassificationResult = await classifier_llm.ainvoke(
                        [system_msg, user_msg]
                    )
                else:
                    result = classifier_llm.invoke([system_msg, user_msg])

                if isinstance(result, ClassificationResult):
                    triage_data = result.model_dump()
                elif isinstance(result, dict):
                    triage_data = result
                else:
                    triage_data = json.loads(str(result))
            except Exception as exc:
                logger.warning("Structured classification parse fallback: %s", exc)
                lower = query.lower()
                if any(k in lower for k in ("benefit", "401k", "workers comp", "tax return")):
                    triage_data = {
                        "category": "out_of_scope",
                        "intent": query,
                        "confidence": 0.5,
                        "employee_id": None,
                        "pay_period": None,
                        "client_id": None,
                        "employee_name": None,
                        "effective_date": None,
                        "change_type": None,
                        "new_value": None,
                        "previous_value": None,
                        "system_target": None,
                        "oos_destination": "other",
                    }
                else:
                    triage_data = {
                        "category": "qa"
                        if ("pay" in lower or "check" in lower)
                        else "changelist",
                        "intent": query,
                        "confidence": 0.5,
                        "employee_id": None,
                        "pay_period": None,
                        "client_id": None,
                        "employee_name": None,
                        "effective_date": None,
                        "change_type": None,
                        "new_value": None,
                        "previous_value": None,
                        "system_target": None,
                        "oos_destination": None,
                    }

            return {"triage": triage_data}

    return classifier_node
