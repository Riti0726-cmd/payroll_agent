"""Map Neon rows to History UI items."""

from __future__ import annotations

from typing import Any, Mapping

from queue_mapping import (
    body_excerpt,
    map_category,
    map_priority_rate,
    parse_extracts,
    _received_at_iso,
)

CLOSED_STATUSES = frozenset(
    {"done", "accepted", "discarded", "approved", "needs_clarification"}
)


def row_to_history_item(row: Mapping[str, Any]) -> dict[str, Any]:
    extracts = parse_extracts(row.get("sub_content"))
    category = map_category(row.get("category")) or "todo"
    subject = row.get("subject")
    subject_text = subject.strip() if isinstance(subject, str) and subject.strip() else "(no subject)"
    status = str(row.get("hitl_status") or "").strip().lower() or "done"

    item: dict[str, Any] = {
        "id": str(row.get("message_id") or ""),
        "subject": subject_text,
        "status": status if status in CLOSED_STATUSES else "done",
        "category": category,
        "priority": map_priority_rate(row.get("priority_rate")),
        "receivedAt": _received_at_iso(row.get("email_received_dttm")),
        "bodyExcerpt": body_excerpt(row.get("content")),
    }
    client_id = extracts.get("client_id")
    employee_id = extracts.get("employee_id")
    if client_id:
        item["clientId"] = client_id
    if employee_id:
        item["employeeId"] = employee_id
    if extracts:
        item["extracted"] = extracts
    return item
