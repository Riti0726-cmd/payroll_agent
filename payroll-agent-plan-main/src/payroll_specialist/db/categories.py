"""Category CSV helpers — keep compatible with POC-Payroll serialize/parse."""

from __future__ import annotations

from typing import Any

ALLOWED_CATEGORIES = frozenset({"qa", "changelist", "todo", "out_of_scope"})


def serialize_categories(categories: list[Any] | None) -> str:
    if not categories:
        return ""
    tokens: list[str] = []
    for item in categories:
        token = str(getattr(item, "value", item)).lower().strip()
        if token and token in ALLOWED_CATEGORIES and token not in tokens:
            tokens.append(token)
    return ",".join(tokens)


def parse_categories(value: str | None) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for part in value.split(","):
        token = part.lower().strip()
        if token and token in ALLOWED_CATEGORIES and token not in out:
            out.append(token)
    return out
