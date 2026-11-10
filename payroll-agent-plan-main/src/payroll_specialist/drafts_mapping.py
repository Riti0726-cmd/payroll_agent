"""Map Neon rows to Draft UI DraftItem dicts."""

from __future__ import annotations

from typing import Any, Mapping

from message_text import extract_message_text

_VALID_STATUS = frozenset({"pending", "accepted", "discarded", "sent"})


def row_to_draft_item(row: Mapping[str, Any]) -> dict:
    """Convert a workbench row dict to camelCase DraftItem keys."""
    status = (row.get("hitl_status") or "pending").strip().lower()
    if status not in _VALID_STATUS:
        status = "pending"
    message_id = str(row.get("message_id") or "")
    subject = row.get("subject")
    to = row.get("sender_email")
    body = extract_message_text(row.get("draft_content"))
    return {
        "id": message_id,
        "subject": (str(subject).strip() if subject else "") or "(no subject)",
        "to": str(to).strip() if to else "",
        "body": body,
        "status": status,
        "relatedQueueId": message_id or None,
    }
