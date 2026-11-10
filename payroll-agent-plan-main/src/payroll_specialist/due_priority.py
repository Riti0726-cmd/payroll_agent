"""Due date and priority helpers for changelist triage (UC-062 / UC-022–025)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

PriorityRate = Literal["high", "medium", "low"]
DueDateSource = Literal["explicit_email", "payroll_calendar", "default_cutoff", "unknown"]

_EXPLICIT_DUE = re.compile(
    r"(?:due|deadline|by)\s*(?:date)?\s*[:=]?\s*"
    r"(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_loose_date(raw: str) -> date | None:
    raw = raw.strip()
    iso = _parse_iso_date(raw)
    if iso:
        return iso
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def extract_explicit_due_date(query: str) -> date | None:
    """Parse an explicit due/deadline date from email text when present."""
    match = _EXPLICIT_DUE.search(query or "")
    if not match:
        return None
    return _parse_loose_date(match.group(1))


def compute_due_date(
    *,
    query: str = "",
    effective_date: str | None = None,
    calendar_cutoff: str | None = None,
    default_day_of_month: int = 20,
    today: date | None = None,
) -> tuple[str | None, DueDateSource]:
    """Return (ISO due date or None, source).

    Order: explicit email → payroll calendar cutoff → default cutoff from effective/today → unknown.
    """
    explicit = extract_explicit_due_date(query)
    if explicit:
        return explicit.isoformat(), "explicit_email"

    cal = _parse_iso_date(calendar_cutoff)
    if cal:
        return cal.isoformat(), "payroll_calendar"

    anchor = _parse_iso_date(effective_date) or today or date.today()
    day = max(1, min(28, int(default_day_of_month)))
    try:
        cutoff = anchor.replace(day=day)
    except ValueError:
        return None, "unknown"
    if cutoff < anchor:
        if anchor.month == 12:
            cutoff = date(anchor.year + 1, 1, day)
        else:
            cutoff = date(anchor.year, anchor.month + 1, day)
    return cutoff.isoformat(), "default_cutoff"


def compute_priority_rate(
    *,
    due_date: str | None = None,
    change_count: int = 1,
    client_active_employees: int | None = None,
    urgency_in_query: bool = False,
    today: date | None = None,
) -> PriorityRate:
    """Map deadline proximity, complexity, client size, urgency → high|medium|low."""
    score = 0
    due = _parse_iso_date(due_date)
    now = today or date.today()
    if due is not None:
        delta = (due - now).days
        if delta <= 2:
            score += 3
        elif delta <= 7:
            score += 2
        elif delta <= 14:
            score += 1
    if change_count >= 3:
        score += 2
    elif change_count >= 2:
        score += 1
    if client_active_employees is not None:
        if client_active_employees >= 500:
            score += 2
        elif client_active_employees >= 100:
            score += 1
    if urgency_in_query:
        score += 2

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    if due is None and not urgency_in_query:
        return "medium"
    return "low"


def urgency_signals(query: str) -> bool:
    lower = (query or "").lower()
    return any(
        k in lower
        for k in ("urgent", "asap", "immediately", "rush", "today", "eod", "end of day")
    )


def apply_due_and_priority(changelist: dict[str, Any], *, query: str = "") -> dict[str, Any]:
    """Copy changelist payload with due_date and priority_rate filled."""
    out = dict(changelist)
    params = out.get("parameters") if isinstance(out.get("parameters"), dict) else {}
    changes = out.get("changes") if isinstance(out.get("changes"), list) else []
    due, source = compute_due_date(
        query=query,
        effective_date=params.get("effective_date") or out.get("effective_date"),
        calendar_cutoff=out.get("calendar_cutoff"),
    )
    out["due_date"] = due
    out["due_date_source"] = source
    out["priority_rate"] = compute_priority_rate(
        due_date=due,
        change_count=len(changes) or 1,
        client_active_employees=out.get("client_active_employees"),
        urgency_in_query=urgency_signals(query),
    )
    return out
