"""Intake node — TRIAGE_RUN only on the Foundry Responses graph (chat → POST /qa)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage

from state import PayrollState
from telemetry import step_span

logger = logging.getLogger("payroll-specialist")

UNSUPPORTED_INVOKE_MESSAGE = (
    "This Foundry agent endpoint only accepts triage commands "
    '(TRIAGE_RUN specialist_id=… or {"command":"triage",...}). '
    "For payroll Q&A, use POST /qa."
)

_TRIAGE_PREFIX = re.compile(
    r"^\s*(?:TRIAGE_RUN|TRIAGE)\b",
    re.IGNORECASE,
)


def _extract_user_text(messages: list[Any]) -> str:
    for msg in reversed(messages or []):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", None) == "human":
            return str(msg.content).strip()
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", "")).strip()
        if isinstance(msg, str):
            return msg.strip()
    if messages:
        last = messages[-1]
        return str(getattr(last, "content", last)).strip()
    return ""


def parse_triage_command(text: str) -> dict[str, Any] | None:
    """Parse TRIAGE_RUN specialist_id=... or JSON triage command. Returns None if not triage."""
    raw = (text or "").strip()
    if not raw:
        return None

    # JSON command: {"command":"triage","specialist_id":"..."}
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            cmd = str(payload.get("command") or payload.get("mode") or "").lower()
            if cmd in ("triage", "triage_run"):
                return {
                    "specialist_id": str(
                        payload.get("specialist_id") or payload.get("specialistId") or "default"
                    ).strip()
                    or "default",
                    "mailbox_id": payload.get("mailbox_id") or payload.get("mailboxId"),
                }

    if not _TRIAGE_PREFIX.search(raw):
        return None

    specialist_id = "default"
    mailbox_id = None
    sid_match = re.search(r"specialist_id\s*=\s*([^\s]+)", raw, re.IGNORECASE)
    if sid_match:
        specialist_id = sid_match.group(1).strip().strip("'\"")
    mid_match = re.search(r"mailbox_id\s*=\s*([^\s]+)", raw, re.IGNORECASE)
    if mid_match:
        mailbox_id = mid_match.group(1).strip().strip("'\"")

    return {"specialist_id": specialist_id, "mailbox_id": mailbox_id}


def make_intake_node(triage_runner: Callable | None = None) -> Callable:
    """Build intake node. Non-triage invoke returns unsupported guidance (use POST /qa)."""

    async def intake_node(state: PayrollState) -> dict:
        with step_span("intake"):
            messages = state.get("messages", [])
            user_query = _extract_user_text(messages)
            command = parse_triage_command(user_query)

            if command is None:
                return {
                    "query": user_query,
                    "mode": "unsupported",
                    "messages": [AIMessage(content=UNSUPPORTED_INVOKE_MESSAGE)],
                }

            specialist_id = command["specialist_id"]
            mailbox_id = command.get("mailbox_id")
            result: dict[str, Any] = {
                "query": user_query,
                "mode": "triage",
                "specialist_id": specialist_id,
                "mailbox_id": mailbox_id,
            }

            if triage_runner is not None:
                with step_span("triage_orchestrate", specialist_id=specialist_id):
                    triage_out = await triage_runner(
                        specialist_id=specialist_id,
                        mailbox_id=mailbox_id,
                    )
                result.update(triage_out)
            return result

    return intake_node
