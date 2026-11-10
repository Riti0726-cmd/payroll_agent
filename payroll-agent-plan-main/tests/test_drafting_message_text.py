"""Drafting node extracts plain text from Foundry Responses content blocks."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from nodes.drafting import make_drafting_node


class _ResponsesDrafter:
    async def ainvoke(self, messages, config=None, **kwargs):
        return AIMessage(
            content=[
                {
                    "id": "rs_1",
                    "type": "reasoning",
                    "encrypted_content": "do-not-persist",
                    "content": [],
                },
                {
                    "type": "text",
                    "text": (
                        "**Triaged Category:** CHANGELIST\n"
                        "**Employee ID:** B02090\n\n"
                        "Hello, draft body here."
                    ),
                    "phase": "final_answer",
                },
            ]
        )


@pytest.mark.asyncio
async def test_drafting_persists_final_answer_text_not_raw_blocks():
    node = make_drafting_node(_ResponsesDrafter())
    out = await node(
        {
            "query": "update DD",
            "triage": {
                "category": "changelist",
                "employee_id": "B02090",
                "intent": "direct deposit",
            },
            "validation": {"status": "ok"},
            "changelist": {"changes": [], "findings": "none"},
        }
    )
    draft = out["draft"]
    assert "Hello, draft body here." in draft
    assert "encrypted_content" not in draft
    assert "do-not-persist" not in draft
    assert draft.startswith("**Triaged Category:** CHANGELIST")
