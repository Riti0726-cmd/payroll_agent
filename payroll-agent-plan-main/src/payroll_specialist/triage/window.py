"""Processing window calculation (UC-009)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_processing_window(
    *,
    lookback_days: int,
    last_successful_run: dict[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, str]:
    """First success → lookback_days; later → last successful end → now."""
    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    start: datetime
    if last_successful_run and last_successful_run.get("window_end"):
        parsed = _parse_iso(str(last_successful_run["window_end"]))
        if parsed is not None:
            start = parsed
        else:
            start = end - timedelta(days=max(1, int(lookback_days)))
    elif last_successful_run and last_successful_run.get("completed_at"):
        parsed = _parse_iso(str(last_successful_run["completed_at"]))
        start = parsed if parsed is not None else end - timedelta(days=max(1, int(lookback_days)))
    else:
        start = end - timedelta(days=max(1, int(lookback_days)))

    if start > end:
        start = end

    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "basis": "last_success" if last_successful_run else "lookback",
    }
