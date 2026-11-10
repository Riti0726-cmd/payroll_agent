"""Map Neon rows to Change list UI ChangeListItem dicts."""

from __future__ import annotations

import json
from typing import Any, Mapping

from queue_mapping import map_priority_rate, parse_extracts


def _stringify_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _map_line_dicts(raw_list: list) -> list[dict]:
    lines: list[dict] = []
    for idx, line in enumerate(raw_list):
        if not isinstance(line, dict):
            continue
        entry = {
            "id": str(line.get("id") or f"l{idx}"),
            "field": str(line.get("field") or ""),
            "from": _stringify_value(line.get("from")),
            "to": _stringify_value(line.get("to")),
            "reviewed": bool(line.get("reviewed", False)),
        }
        if line.get("effective_date") is not None:
            entry["effectiveDate"] = str(line.get("effective_date"))
        elif line.get("effectiveDate") is not None:
            entry["effectiveDate"] = str(line.get("effectiveDate"))
        if line.get("incomplete") is not None:
            entry["incomplete"] = bool(line.get("incomplete"))
        if line.get("recommended_system") is not None:
            entry["recommendedSystem"] = str(line.get("recommended_system"))
        elif line.get("recommendedSystem") is not None:
            entry["recommendedSystem"] = str(line.get("recommendedSystem"))
        if line.get("recommended_field") is not None:
            entry["recommendedField"] = str(line.get("recommended_field"))
        elif line.get("recommendedField") is not None:
            entry["recommendedField"] = str(line.get("recommendedField"))
        lines.append(entry)
    return lines


def merge_changelist_payload(existing: dict | None, shell: dict) -> dict:
    """Keep rich changes/lines; only fill missing shell metadata fields.

    If shell itself has rich changes/lines and existing does not, use shell.
    """
    if not isinstance(existing, dict):
        return shell
    has_changes = isinstance(existing.get("changes"), list) and bool(existing["changes"])
    has_lines = isinstance(existing.get("lines"), list) and bool(existing["lines"])
    shell_rich = (
        isinstance(shell.get("changes"), list)
        and bool(shell["changes"])
    ) or (isinstance(shell.get("lines"), list) and bool(shell["lines"]))
    if not (has_changes or has_lines):
        return shell
    if shell_rich and not (has_changes or has_lines):
        return shell
    out = dict(existing)
    if not out.get("clientId") and shell.get("clientId"):
        out["clientId"] = shell["clientId"]
    if not out.get("title") and shell.get("title"):
        out["title"] = shell["title"]
    if not out.get("status") and shell.get("status"):
        out["status"] = shell["status"]
    return out


def apply_line_edits(payload: dict, lines: list[dict]) -> dict:
    """Apply UI line edits onto changelist_response (sync lines + changes)."""
    out = dict(payload)
    mapped = []
    changes = []
    for idx, line in enumerate(lines):
        if not isinstance(line, dict):
            continue
        lid = str(line.get("id") or f"l{idx}")
        field = str(line.get("field") or "")
        from_v = line.get("from")
        to_v = line.get("to")
        reviewed = bool(line.get("reviewed", False))
        mapped.append(
            {
                "id": lid,
                "field": field,
                "from": from_v,
                "to": to_v,
                "reviewed": reviewed,
                "effectiveDate": line.get("effectiveDate") or line.get("effective_date"),
                "incomplete": bool(line.get("incomplete", False)),
                "recommendedSystem": line.get("recommendedSystem")
                or line.get("recommended_system"),
                "recommendedField": line.get("recommendedField")
                or line.get("recommended_field"),
            }
        )
        changes.append(
            {
                "id": lid,
                "field": field,
                "from": from_v,
                "to": to_v,
                "reviewed": reviewed,
                "effective_date": line.get("effectiveDate") or line.get("effective_date"),
                "incomplete": bool(line.get("incomplete", False)),
                "recommended_system": line.get("recommendedSystem")
                or line.get("recommended_system"),
                "recommended_field": line.get("recommendedField")
                or line.get("recommended_field"),
            }
        )
    out["lines"] = mapped
    out["changes"] = changes
    return out


def row_to_changelist_item(row: Mapping[str, Any]) -> dict:
    """Convert a workbench row dict to camelCase ChangeListItem keys.

    Prefers `changelist_response.lines`; falls back to `changes` (agent shape).
    """
    extracts = parse_extracts(row.get("sub_content"))
    client_id = extracts.get("client_id") or "unknown"
    subject = row.get("subject")
    title = (str(subject).strip() if subject else "") or "(no subject)"

    lines: list[dict] = []
    due_date = None
    status = None
    priority = None
    raw = row.get("changelist_response")
    if raw:
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            if payload.get("clientId"):
                client_id = str(payload["clientId"])
            else:
                params = payload.get("parameters")
                if isinstance(params, dict) and params.get("client_id") is not None:
                    client_id = str(params["client_id"])
            if payload.get("title"):
                title = str(payload["title"])
            if payload.get("due_date"):
                due_date = str(payload["due_date"])
            elif payload.get("dueDate"):
                due_date = str(payload["dueDate"])
            st = payload.get("status")
            if st in ("pending", "incomplete"):
                status = st
            if payload.get("priority_rate"):
                priority = map_priority_rate(str(payload.get("priority_rate")))

            raw_lines = payload.get("lines")
            if isinstance(raw_lines, list) and raw_lines:
                lines = _map_line_dicts(raw_lines)
            else:
                raw_changes = payload.get("changes")
                if isinstance(raw_changes, list) and raw_changes:
                    lines = _map_line_dicts(raw_changes)

    item: dict[str, Any] = {
        "id": str(row.get("message_id") or ""),
        "clientId": client_id,
        "title": title,
        "lines": lines,
    }
    if due_date:
        item["dueDate"] = due_date
    if status:
        item["status"] = status
    if priority is not None:
        item["priority"] = priority
    return item
