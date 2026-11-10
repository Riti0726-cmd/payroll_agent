"""Tests for Foundry Responses / chat content text extraction."""

from __future__ import annotations

from message_text import extract_message_text


def test_extract_plain_string():
    assert extract_message_text("  Hello  ") == "Hello"


def test_extract_prefers_final_answer_block():
    content = [
        {
            "id": "rs_1",
            "type": "reasoning",
            "summary": [],
            "content": [],
            "encrypted_content": "secret",
        },
        {
            "type": "text",
            "text": "**Triaged Category:** CHANGELIST\n\nHello team,",
            "phase": "final_answer",
            "id": "msg_1",
        },
    ]
    out = extract_message_text(content)
    assert out.startswith("**Triaged Category:** CHANGELIST")
    assert "encrypted_content" not in out
    assert "secret" not in out


def test_extract_list_of_strings():
    assert extract_message_text(["a", "b"]) == "a\nb"


def test_extract_stringified_python_list_blob():
    """DB / provider sometimes persists str(list-of-blocks) with single quotes."""
    blob = (
        "[{'id': 'rs_1', 'summary': [], 'type': 'reasoning', 'content': [], "
        "'encrypted_content': 'secret'}, "
        "{'type': 'text', 'text': '**Triaged Category:** QA\\n\\nHello,', "
        "'phase': 'final_answer', 'index': 1, 'id': 'msg_1'}]"
    )
    out = extract_message_text(blob)
    assert out.startswith("**Triaged Category:** QA")
    assert "encrypted_content" not in out
    assert "secret" not in out


def test_extract_skips_empty_list_content_on_reasoning():
    content = [
        {"type": "reasoning", "content": [], "encrypted_content": "x"},
        {"type": "text", "text": "Only this", "phase": "final_answer"},
    ]
    assert extract_message_text(content) == "Only this"
