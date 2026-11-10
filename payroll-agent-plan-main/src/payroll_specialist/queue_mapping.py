"""Map Neon email_processing rows to Queue UI QueueItem dicts."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from db.categories import parse_categories

_MISSING_RECEIVED = "1970-01-01T00:00:00+00:00"


def map_priority_rate(priority_rate: str | None) -> int:
    normalized = (priority_rate or "").lower().strip()
    if normalized == "high":
        return 1
    if normalized == "low":
        return 5
    return 3


def priority_to_rate(priority: int | None) -> str:
    """Map UI priority 1–5 to Neon priority_rate."""
    if priority == 1:
        return "high"
    if priority == 5:
        return "low"
    return "medium"


def map_category(category_csv: str | None) -> str | None:
    tokens = parse_categories(category_csv)
    return tokens[0] if tokens else None


def body_excerpt(content: str | None, *, limit: int = 280) -> str | None:
    if content is None:
        return None
    text = content.strip()
    if not text:
        return None
    return text if len(text) <= limit else text[:limit]


def parse_extracts(sub_content: str | None) -> dict[str, str]:
    if not sub_content or not str(sub_content).strip():
        return {}
    try:
        data = json.loads(sub_content)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        if value is None:
            continue
        out[str(key)] = str(value)
    return out


def _received_at_iso(value: Any) -> str:
    if value is None:
        return _MISSING_RECEIVED
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or _MISSING_RECEIVED


def row_to_queue_item(row: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a Neon-shaped mapping to a camelCase QueueItem dict.

    If category CSV is empty/invalid, category defaults to ``todo`` (defensive;
    list API still filters ``is_categorized=true``).
    """
    extracts = parse_extracts(row.get("sub_content"))
    category = map_category(row.get("category")) or "todo"
    subject = row.get("subject")
    subject_text = subject.strip() if isinstance(subject, str) and subject.strip() else "(no subject)"

    item: dict[str, Any] = {
        "id": str(row.get("message_id") or ""),
        "subject": subject_text,
        "category": category,
        "priority": map_priority_rate(row.get("priority_rate")),
        "receivedAt": _received_at_iso(row.get("email_received_dttm")),
        "bodyExcerpt": body_excerpt(row.get("content")),
        "hasDraft": bool(row.get("is_drafted") and (row.get("draft_content") or "").strip()),
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
