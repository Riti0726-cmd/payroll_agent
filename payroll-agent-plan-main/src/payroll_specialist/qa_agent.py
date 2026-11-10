"""Standalone console Q&A agent — ReAct + Cortex MCP (no classifier/drafter)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable, Optional, Sequence

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from mcp_agent_invoke import _exception_text, ainvoke_mcp_agent
from mcp_required import has_live_mcp_tools
from message_text import extract_message_text
from models import QaChatMessage, QaChatResponse, QaSource
from prompts import QA_CHAT_INSTRUCTIONS
from tools.snowflake_mcp import get_qa_tools

logger = logging.getLogger("payroll-specialist")

# Reused across POST /qa requests (tools + model + compiled graph).
_qa_agent_cache: Any | None = None

CANNOT_VERIFY = (
    "I cannot verify the figures from Snowflake Cortex Analyst. "
    "Connection or tools are unavailable."
)

NOT_RETURNED = "Not returned by Cortex"

_QUERY_ARG_KEYS = ("message", "question", "query", "prompt", "input")
_INTERPRETATION_KEYS = (
    "interpretation",
    "analyst_interpretation",
    "explanation",
    "summary",
    "text",
)
_RESPONSE_KEYS = (
    "results",
    "result",
    "data",
    "rows",
    "table",
    "answer",
    "output",
    "content",
)
_SQL_KEYS = ("sql", "generated_sql", "query_sql", "statement")


class QaChatValidationError(ValueError):
    """Raised when the Q&A request body is invalid."""


def parse_qa_messages(raw: Any) -> list[QaChatMessage]:
    """Validate and normalize the request `messages` list."""
    if not isinstance(raw, list) or len(raw) == 0:
        raise QaChatValidationError("messages must be a non-empty array")

    parsed: list[QaChatMessage] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise QaChatValidationError(f"messages[{i}] must be an object")
        role = item.get("role")
        content = item.get("content")
        if role not in ("user", "assistant"):
            raise QaChatValidationError(
                f"messages[{i}].role must be 'user' or 'assistant'"
            )
        if not isinstance(content, str) or not content.strip():
            raise QaChatValidationError(f"messages[{i}].content must be non-empty text")
        parsed.append(QaChatMessage(role=role, content=content.strip()))

    if parsed[-1].role != "user":
        raise QaChatValidationError("messages must end with a user turn")
    return parsed


def _to_lc_messages(messages: Sequence[QaChatMessage]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for msg in messages:
        if msg.role == "user":
            out.append(HumanMessage(content=msg.content))
        else:
            out.append(AIMessage(content=msg.content))
    return out


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(block, "text", None)
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content).strip()


def _coerce_response(value: Any) -> QaChatResponse:
    if isinstance(value, QaChatResponse):
        return value
    if isinstance(value, dict):
        return QaChatResponse.model_validate(value)
    text = _message_text(getattr(value, "content", value))
    if not text:
        return QaChatResponse(answer=CANNOT_VERIFY, sources=[])
    return QaChatResponse(answer=text, sources=[])


def _as_pretty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, indent=2, default=str)
    except TypeError:
        return str(value).strip()


def _first_key(data: dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    lower_map = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        if key.lower() in lower_map and lower_map[key.lower()] not in (None, ""):
            return lower_map[key.lower()]
    return None


def _query_from_args(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    # Analyst tools use message/question; sql_query_executor uses sql/statement.
    for key in (*_QUERY_ARG_KEYS, *_SQL_KEYS):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    lower_map = {str(k).lower(): v for k, v in args.items()}
    for key in (*_QUERY_ARG_KEYS, *_SQL_KEYS):
        val = lower_map.get(key.lower())
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _is_snowflake_executor_payload(parsed: dict[str, Any]) -> bool:
    keys = {str(k).lower() for k in parsed}
    if keys & {"result_set", "resultset", "query_id", "queryid"}:
        return True
    if "data" in keys and keys & {"rowtype", "resultsetmetadata", "partitioninfo", "partition"}:
        return True
    return False


def _snowflake_result_set(parsed: dict[str, Any]) -> dict[str, Any]:
    for key, val in parsed.items():
        if str(key).lower() in ("result_set", "resultset") and isinstance(val, dict):
            return val
    return parsed


def _row_type_columns(result_set: dict[str, Any]) -> list[str]:
    lower = {str(k).lower(): v for k, v in result_set.items()}
    row_type = lower.get("rowtype")
    if not isinstance(row_type, list):
        meta = lower.get("resultsetmetadata")
        if isinstance(meta, dict):
            row_type = meta.get("rowType") or meta.get("rowtype")
    names: list[str] = []
    if isinstance(row_type, list):
        for i, col in enumerate(row_type):
            if isinstance(col, dict):
                names.append(str(col.get("name") or col.get("NAME") or f"col{i}"))
            else:
                names.append(f"col{i}")
    return names


def _format_snowflake_executor(
    parsed: dict[str, Any],
) -> tuple[str, str]:
    """Return (interpretation summary, response rows) for sql_query_executor payloads."""
    query_id = _first_key(parsed, ("query_id", "queryId", "QUERY_ID"))
    result_set = _snowflake_result_set(parsed)
    lower = {str(k).lower(): v for k, v in result_set.items()}
    data = lower.get("data")
    names = _row_type_columns(result_set)

    rows_out: list[Any] = []
    if isinstance(data, list):
        for row in data:
            if isinstance(row, (list, tuple)) and names:
                rows_out.append(
                    {
                        names[i]: row[i]
                        for i in range(min(len(names), len(row)))
                    }
                )
            else:
                rows_out.append(row)

    n_rows = len(rows_out) if rows_out else (len(data) if isinstance(data, list) else 0)
    parts: list[str] = []
    if query_id is not None and str(query_id).strip():
        parts.append(f"query_id={query_id}")
    parts.append(f"{n_rows} row(s) returned")
    if names:
        parts.append("columns: " + ", ".join(names))
    interpretation = "; ".join(parts)

    if rows_out:
        response = _as_pretty(rows_out)
    elif isinstance(data, list):
        response = _as_pretty(data)
    else:
        response = _as_pretty(result_set)
    return interpretation, response


def _block_has_analyst_fields(item: dict[str, Any]) -> bool:
    keys = {str(k).lower() for k in item}
    return bool(
        keys
        & {
            "text",
            "statement",
            "sql",
            "generated_sql",
            "interpretation",
            "analyst_interpretation",
            "explanation",
        }
    )


def _normalize_cortex_payload(loaded: Any) -> dict[str, Any] | None:
    """Flatten Cortex payloads (dict, or list of {text, statement} blocks) to one dict."""
    if isinstance(loaded, str):
        text = loaded.strip()
        if not text:
            return None
        try:
            return _normalize_cortex_payload(json.loads(text))
        except json.JSONDecodeError:
            return {"text": text}

    if isinstance(loaded, dict):
        for wrap_key in ("content", "result", "results", "data", "output", "message"):
            inner = loaded.get(wrap_key)
            if (
                isinstance(inner, list)
                and inner
                and isinstance(inner[0], dict)
                and any(
                    isinstance(i, dict) and _block_has_analyst_fields(i) for i in inner
                )
            ):
                unwrapped = _normalize_cortex_payload(inner)
                if unwrapped:
                    merged = {k: v for k, v in loaded.items() if k != wrap_key}
                    merged.update(unwrapped)
                    return merged
        return loaded

    if isinstance(loaded, list):
        texts: list[str] = []
        statements: list[Any] = []
        other_rows: list[Any] = []
        for item in loaded:
            if isinstance(item, dict) and _block_has_analyst_fields(item):
                interp = _first_key(
                    item,
                    (
                        "interpretation",
                        "analyst_interpretation",
                        "explanation",
                        "text",
                        "summary",
                    ),
                )
                if interp is not None and str(interp).strip():
                    texts.append(str(interp).strip())
                sql = _first_key(item, _SQL_KEYS)
                if sql is not None and sql != "":
                    statements.append(sql)
            elif isinstance(item, dict):
                other_rows.append(item)
            elif isinstance(item, str) and item.strip():
                texts.append(item.strip())

        merged: dict[str, Any] = {}
        if texts:
            merged["text"] = "\n\n".join(texts)
        if len(statements) == 1:
            merged["statement"] = statements[0]
        elif statements:
            merged["statement"] = statements
        if other_rows:
            merged["results"] = other_rows
        return merged or None

    return None


def parse_cortex_tool_trace(args: Any, tool_result: Any) -> dict[str, str]:
    """Extract MCP query / Analyst interpretation / response panes from tool I/O."""
    raw_text = _message_text(tool_result)
    parsed: dict[str, Any] | None = None
    if raw_text:
        try:
            parsed = _normalize_cortex_payload(json.loads(raw_text))
        except json.JSONDecodeError:
            parsed = None

    query = _query_from_args(args)
    interpretation = ""
    response = ""

    if parsed is not None:
        if not query:
            q = _first_key(parsed, (*_QUERY_ARG_KEYS, *_SQL_KEYS))
            if isinstance(q, str) and q.strip():
                query = q.strip()
            else:
                sql = _first_key(parsed, _SQL_KEYS)
                if sql:
                    query = _as_pretty(sql)

        if _is_snowflake_executor_payload(parsed):
            interpretation, response = _format_snowflake_executor(parsed)
        else:
            interp = _first_key(parsed, _INTERPRETATION_KEYS)
            if interp is not None:
                interpretation = _as_pretty(interp)

            resp = _first_key(parsed, _RESPONSE_KEYS)
            if resp is not None:
                response = _as_pretty(resp)
            else:
                sql = _first_key(parsed, _SQL_KEYS)
                if sql and query != _as_pretty(sql):
                    response = _as_pretty(sql)
                elif not interpretation:
                    leftover = {
                        k: v
                        for k, v in parsed.items()
                        if str(k).lower()
                        not in {
                            x.lower()
                            for x in (
                                *_QUERY_ARG_KEYS,
                                *_INTERPRETATION_KEYS,
                                *_SQL_KEYS,
                            )
                        }
                    }
                    if leftover:
                        response = _as_pretty(leftover)
    else:
        if raw_text:
            response = raw_text

    if not query:
        query = NOT_RETURNED
    if not interpretation:
        interpretation = NOT_RETURNED
    if not response:
        response = NOT_RETURNED

    # Prefer executed row preview on the chip for sql_query_executor.
    if (
        response != NOT_RETURNED
        and interpretation != NOT_RETURNED
        and interpretation.startswith("query_id=")
    ):
        summary_src = response
    else:
        summary_src = (
            interpretation
            if interpretation != NOT_RETURNED
            else response
            if response != NOT_RETURNED
            else query
        )
    detail = summary_src[:240] + ("…" if len(summary_src) > 240 else "")

    return {
        "query": query,
        "interpretation": interpretation,
        "response": response,
        "detail": detail,
    }


def sources_from_tool_messages(messages: Sequence[Any]) -> list[QaSource]:
    """Build expandable Q&A sources from agent tool call + tool result messages."""
    pending_args: dict[str, Any] = {}
    sources: list[QaSource] = []
    seen: set[str] = set()

    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls is None and isinstance(msg, dict):
            tool_calls = msg.get("tool_calls")
        if tool_calls:
            for call in tool_calls:
                if isinstance(call, dict):
                    call_id = str(call.get("id") or call.get("name") or "")
                    call_name = call.get("name")
                    call_args = call.get("args") or {}
                else:
                    call_id = str(
                        getattr(call, "id", None) or getattr(call, "name", "") or ""
                    )
                    call_name = getattr(call, "name", None)
                    call_args = getattr(call, "args", None) or {}
                if call_id:
                    pending_args[call_id] = {"name": call_name, "args": call_args}
                if call_name and str(call_name) not in seen:
                    seen.add(str(call_name))
                    panes = parse_cortex_tool_trace(call_args, "")
                    sources.append(
                        QaSource(
                            label=str(call_name),
                            detail=panes["detail"] or "Cortex MCP tool call",
                            query=panes["query"],
                            interpretation=panes["interpretation"],
                            response=panes["response"],
                        )
                    )
            continue

        # Only ToolMessage / tool results — not named AIMessages (e.g. payroll-qa-chat).
        call_id = getattr(msg, "tool_call_id", None) or (
            msg.get("tool_call_id") if isinstance(msg, dict) else None
        )
        msg_type = getattr(msg, "type", None) or (
            msg.get("type") if isinstance(msg, dict) else None
        )
        if not call_id and msg_type != "tool":
            continue

        name = getattr(msg, "name", None) or (
            msg.get("name") if isinstance(msg, dict) else None
        )
        if not name and call_id:
            name = pending_args.get(str(call_id), {}).get("name")
        if not name:
            continue

        content = _message_text(
            getattr(msg, "content", "")
            if not isinstance(msg, dict)
            else msg.get("content", "")
        )
        meta = pending_args.get(str(call_id or ""), {})
        args = meta.get("args") or {}
        panes = parse_cortex_tool_trace(args, content)

        key = str(name)
        updated = False
        for idx, existing in enumerate(sources):
            if existing.label == key:
                sources[idx] = QaSource(
                    label=key,
                    detail=panes["detail"] or existing.detail or "Cortex MCP tool result",
                    query=panes["query"],
                    interpretation=panes["interpretation"],
                    response=panes["response"],
                )
                updated = True
                break
        if not updated:
            seen.add(key)
            sources.append(
                QaSource(
                    label=key,
                    detail=panes["detail"] or "Cortex MCP tool result",
                    query=panes["query"],
                    interpretation=panes["interpretation"],
                    response=panes["response"],
                )
            )

    return sources


# Back-compat alias
_sources_from_tool_messages = sources_from_tool_messages


def _answer_from_messages(messages: Sequence[Any]) -> str:
    """Recover specialist-facing answer text from the final AI message(s)."""
    for msg in reversed(list(messages)):
        is_ai = isinstance(msg, AIMessage) or getattr(msg, "type", None) == "ai"
        if not is_ai and not (isinstance(msg, dict) and msg.get("type") == "ai"):
            continue
        content = (
            msg.get("content", "")
            if isinstance(msg, dict)
            else getattr(msg, "content", "")
        )
        text = extract_message_text(content)
        if text.strip():
            return text.strip()
    return ""


def create_qa_agent(
    model: Any,
    tools: Optional[Sequence[Any]] = None,
) -> Any:
    """Compile a standalone ReAct Q&A agent (answer from final AI; sources from tools)."""
    tool_list = list(tools) if tools is not None else get_qa_tools()
    return create_agent(
        model,
        tools=tool_list,
        system_prompt=QA_CHAT_INSTRUCTIONS,
        name="payroll-qa-chat",
    )


def clear_qa_agent_cache() -> None:
    """Drop the cached console Q&A agent (e.g. after MCP tools reload)."""
    global _qa_agent_cache
    _qa_agent_cache = None


def get_cached_qa_agent() -> Any:
    """Return a process-wide compiled Q&A agent, creating it on first use."""
    global _qa_agent_cache
    if _qa_agent_cache is not None:
        return _qa_agent_cache
    from graph import build_chat_model

    model = build_chat_model(disable_streaming=True)
    _qa_agent_cache = create_qa_agent(model, tools=get_qa_tools())
    return _qa_agent_cache


def _response_from_agent_result(result: Any) -> QaChatResponse:
    """Build API response from agent messages (no structured-output round)."""
    msgs = result.get("messages", []) if isinstance(result, dict) else []
    answer = _answer_from_messages(msgs)
    sources = sources_from_tool_messages(msgs)
    return QaChatResponse(answer=answer or CANNOT_VERIFY, sources=sources)


async def run_qa_chat(
    messages: Sequence[QaChatMessage] | Sequence[dict[str, Any]] | Any,
    *,
    agent: Any = None,
    model: Any = None,
    tools: Optional[Sequence[Any]] = None,
    invoke_fn: Optional[Callable[..., Any]] = None,
) -> QaChatResponse:
    """Run the standalone Q&A agent over a chat transcript."""
    started = time.perf_counter()
    parsed = (
        list(messages)
        if messages and isinstance(messages[0], QaChatMessage)
        else parse_qa_messages(messages)
    )

    if invoke_fn is not None:
        result = invoke_fn(parsed)
        if hasattr(result, "__await__"):
            result = await result
        response = _coerce_response(result)
        logger.info(
            "payroll-qa-chat finished in %.0f ms (invoke_fn)",
            (time.perf_counter() - started) * 1000,
        )
        return response

    effective_tools = list(tools) if tools is not None else None
    if agent is None and effective_tools is None:
        effective_tools = get_qa_tools()

    if effective_tools is not None and not has_live_mcp_tools(
        {t.name: t for t in effective_tools}
    ):
        return QaChatResponse(
            answer=CANNOT_VERIFY,
            sources=[
                QaSource(
                    label="snowflake_mcp",
                    detail="No live Cortex MCP tools bound (offline stub or empty tool list).",
                )
            ],
        )

    if agent is None:
        # Cache default host agent; tests that pass tools/model skip the shared cache.
        if tools is None and model is None:
            agent = get_cached_qa_agent()
        else:
            if model is None:
                from graph import build_chat_model

                model = build_chat_model(disable_streaming=True)
            agent = create_qa_agent(model, tools=effective_tools)

    lc_messages = _to_lc_messages(parsed)
    try:
        result = await ainvoke_mcp_agent(
            agent,
            {"messages": lc_messages},
            attempts=3,
            label="payroll-qa-chat",
        )
    except Exception as exc:
        detail = _exception_text(exc)
        logger.warning(
            "Q&A agent invocation failed after %.0f ms: %s",
            (time.perf_counter() - started) * 1000,
            detail,
        )
        return QaChatResponse(
            answer=CANNOT_VERIFY,
            sources=[QaSource(label="error", detail=detail[:500])],
        )

    response = _response_from_agent_result(result)
    logger.info(
        "payroll-qa-chat finished in %.0f ms (sources=%d)",
        (time.perf_counter() - started) * 1000,
        len(response.sources),
    )
    return response