"""LangGraph state for Foundry triage invoke and per-email subgraphs."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class PayrollState(TypedDict, total=False):
    """State channels for ResponsesHostServer + triage orchestration.

    `messages` is the primary channel consumed by ResponsesHostServer.
    Only the final synthesized output is appended to `messages`.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    mode: str  # "triage" | "unsupported" | "email"
    triage: Optional[dict]
    validation: Optional[dict]
    changelist: Optional[dict]
    qa_findings: Optional[str]
    draft: Optional[str]
    specialist_id: Optional[str]
    run_id: Optional[str]
    mailbox_id: Optional[str]
    specialist_config: Optional[dict]
    processing_window: Optional[dict]
    email_results: Optional[list[dict[str, Any]]]
    triage_summary: Optional[str]
