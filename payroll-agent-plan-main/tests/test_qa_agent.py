import pytest

from models import QaChatMessage, QaChatResponse, QaSource
from prompts import QA_CHAT_INSTRUCTIONS
from qa_agent import (
    CANNOT_VERIFY,
    QaChatValidationError,
    parse_qa_messages,
    run_qa_chat,
)
from tools.snowflake_mcp import snowflake_mcp_unavailable


def test_parse_qa_messages_ok():
    msgs = parse_qa_messages(
        [
            {"role": "user", "content": "Why was August pay lower?"},
            {"role": "assistant", "content": "Checking."},
            {"role": "user", "content": "Break out deductions."},
        ]
    )
    assert len(msgs) == 3
    assert msgs[-1].role == "user"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        [{"role": "assistant", "content": "hi"}],
        [{"role": "user", "content": ""}],
        [{"role": "system", "content": "x"}],
        "not-a-list",
    ],
)
def test_parse_qa_messages_rejects_bad(payload):
    with pytest.raises(QaChatValidationError):
        parse_qa_messages(payload)


@pytest.mark.asyncio
async def test_run_qa_chat_uses_invoke_fn():
    async def fake(messages):
        assert messages[-1].content == "Break out deductions."
        return QaChatResponse(
            answer="Dental increased by $40.",
            sources=[QaSource(label="structured_lines", detail="EMP-1 Aug")],
        )

    result = await run_qa_chat(
        [
            QaChatMessage(role="user", content="Why lower?"),
            QaChatMessage(role="assistant", content="Checking."),
            QaChatMessage(role="user", content="Break out deductions."),
        ],
        invoke_fn=fake,
    )
    assert result.answer.startswith("Dental")
    assert result.sources[0].label == "structured_lines"


@pytest.mark.asyncio
async def test_run_qa_chat_invoke_fn_failure_path_via_exception_handler():
    def boom(_messages):
        raise RuntimeError("mcp down")

    # invoke_fn exceptions propagate unless agent path; use agent path mock by raising in invoke_fn
    # Spec: hard failure at HTTP is 502; agent path returns cannot-verify when agent.ainvoke fails.
    # Here invoke_fn failure should propagate to caller (HTTP catches it).
    with pytest.raises(RuntimeError, match="mcp down"):
        await run_qa_chat(
            [{"role": "user", "content": "pay?"}],
            invoke_fn=boom,
        )


@pytest.mark.asyncio
async def test_run_qa_chat_agent_exception_returns_cannot_verify():
    class BrokenAgent:
        async def ainvoke(self, _payload):
            raise RuntimeError("boom")

    result = await run_qa_chat(
        [{"role": "user", "content": "What is net pay?"}],
        agent=BrokenAgent(),
    )
    assert CANNOT_VERIFY in result.answer
    assert result.sources


@pytest.mark.asyncio
async def test_run_qa_chat_stub_only_tools_returns_cannot_verify():
    """Console Q&A must not treat the CI offline stub as a real Cortex answer."""
    calls = {"n": 0}

    class MustNotRun:
        async def ainvoke(self, _payload):
            calls["n"] += 1
            raise AssertionError("agent must not run with stub-only MCP tools")

    result = await run_qa_chat(
        [{"role": "user", "content": "What is net pay for EMP-1?"}],
        agent=MustNotRun(),
        tools=[snowflake_mcp_unavailable],
    )
    assert calls["n"] == 0
    assert CANNOT_VERIFY in result.answer
    assert any("mcp" in (s.label + s.detail).lower() for s in result.sources)


@pytest.mark.asyncio
async def test_run_qa_chat_builds_answer_from_final_ai_message():
    """Final AIMessage + tool traces drive the API response (no response_format)."""

    class Agent:
        async def ainvoke(self, _payload):
            return {
                "messages": [
                    {
                        "type": "ai",
                        "tool_calls": [
                            {
                                "name": "sv_employee_payroll",
                                "args": {"message": "highest gross"},
                                "id": "c1",
                            }
                        ],
                    },
                    {
                        "type": "tool",
                        "name": "sv_employee_payroll",
                        "tool_call_id": "c1",
                        "content": '{"interpretation": "ok"}',
                    },
                    {
                        "type": "ai",
                        "name": "payroll-qa-chat",
                        "content": "Employee EMP-9 had the highest gross pay.",
                    },
                ],
            }

    result = await run_qa_chat(
        [{"role": "user", "content": "Who had the highest gross?"}],
        agent=Agent(),
    )
    assert "EMP-9" in result.answer
    assert [s.label for s in result.sources] == ["sv_employee_payroll"]


@pytest.mark.asyncio
async def test_get_cached_qa_agent_reuses_instance(monkeypatch):
    from qa_agent import clear_qa_agent_cache, get_cached_qa_agent
    import qa_agent as qa_mod

    clear_qa_agent_cache()
    created = {"n": 0}

    def fake_create(model, tools=None):
        created["n"] += 1
        return object()

    monkeypatch.setattr(qa_mod, "create_qa_agent", fake_create)
    monkeypatch.setattr(qa_mod, "get_qa_tools", lambda: [snowflake_mcp_unavailable])

    class FakeModel:
        pass

    def fake_build(**_kwargs):
        return FakeModel()

    import graph

    monkeypatch.setattr(graph, "build_chat_model", fake_build)

    a1 = get_cached_qa_agent()
    a2 = get_cached_qa_agent()
    assert a1 is a2
    assert created["n"] == 1
    clear_qa_agent_cache()


def test_qa_chat_instructions_name_live_cortex_tools():
    text = QA_CHAT_INSTRUCTIONS.lower()
    assert "sv_hr_workforce" in text
    assert "sv_employee_payroll" in text
    assert "sv_employee_benefits" in text
    assert "structured_lines" not in text
