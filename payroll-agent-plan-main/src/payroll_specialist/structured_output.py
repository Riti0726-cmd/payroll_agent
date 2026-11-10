"""Helpers for Foundry/OpenAI structured output."""

from __future__ import annotations

from typing import Any


def with_structured(model: Any, schema: type) -> Any:
    """Bind structured output using function_calling (strict json_schema rejects our models)."""
    if not hasattr(model, "with_structured_output"):
        return model
    try:
        return model.with_structured_output(schema, method="function_calling")
    except TypeError:
        return model.with_structured_output(schema)
