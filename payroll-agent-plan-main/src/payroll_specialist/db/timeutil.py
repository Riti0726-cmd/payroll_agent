"""IST-aware datetime helpers for email_processing timestamps."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def ensure_ist(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


class ISTDateTime(TypeDecorator):
    """Persist timestamptz; always bind/load as Asia/Kolkata."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:  # noqa: ANN001
        return ensure_ist(value)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:  # noqa: ANN001
        return ensure_ist(value)
