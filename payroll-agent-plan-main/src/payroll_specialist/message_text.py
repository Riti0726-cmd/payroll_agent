"""Extract plain text from chat / Foundry Responses message content."""

from __future__ import annotations

import ast
import json
from typing import Any


def _block_text(block: Any) -> tuple[str, Any, Any]:
    """Return (text, phase, block_type) for one content block."""
    if isinstance(block, str):
        return block, None, None
    if isinstance(block, dict):
        block_type = block.get("type")
        if block_type in ("reasoning", "thinking", "thought") or "thought" in block:
            return "", block.get("phase"), block_type or "thought"
        raw = block.get("text")
        if raw is None:
            raw = block.get("content")
        # Empty lists / nested structures are not draft text.
        if isinstance(raw, list):
            text = ""
        else:
            text = str(raw or "").strip()
        return text, block.get("phase"), block_type
    text = str(getattr(block, "text", None) or "").strip()
    block_type = getattr(block, "type", None)
    if block_type in ("reasoning", "thinking", "thought"):
        return "", getattr(block, "phase", None), block_type
    if not text:
        content_attr = getattr(block, "content", None)
        if isinstance(content_attr, list):
            text = ""
        else:
            text = str(content_attr or "").strip()
    return text, getattr(block, "phase", None), block_type


def _extract_from_blocks(content: list) -> str:
    final_parts: list[str] = []
    other_parts: list[str] = []
    for block in content:
        text, phase, block_type = _block_text(block)
        if not text:
            continue
        if block_type in ("reasoning", "thinking", "thought"):
            continue
        if phase == "final_answer":
            final_parts.append(text)
        else:
            other_parts.append(text)
    return "\n".join(final_parts or other_parts).strip()


def _coerce_structured(content: str) -> Any | None:
    """Parse stringified Responses / Python list blobs into structured content."""
    s = content.strip()
    if not s or s[0] not in "[|{":
        return None
    # Prefer JSON (double quotes); fall back to Python literal (single quotes).
    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(s)
        except (json.JSONDecodeError, SyntaxError, ValueError, TypeError, MemoryError):
            continue
        if isinstance(parsed, (list, dict)):
            return parsed
    return None


def extract_message_text(content: Any) -> str:
    """Normalize model message content to a single plain-text string.

    Foundry Responses often returns a list of blocks (reasoning + text). Prefer
    blocks with phase=final_answer when present; never persist raw list reprs.
    Also unwrap stringified list/dict blobs already saved to the DB.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        parsed = _coerce_structured(content)
        if parsed is not None:
            return extract_message_text(parsed)
        return content.strip()
    if isinstance(content, dict):
        # Single Responses item or wrapper.
        if "text" in content or content.get("type") in ("text", "output_text"):
            return _extract_from_blocks([content])
        inner = content.get("content") or content.get("output") or content.get("parts")
        if inner is not None and inner is not content:
            return extract_message_text(inner)
        return ""
    if isinstance(content, list):
        return _extract_from_blocks(content)
    return str(content).strip()
