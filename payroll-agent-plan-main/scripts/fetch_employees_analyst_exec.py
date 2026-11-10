"""Fetch 10 employees: Cortex Analyst SQL → sql_query_executor (exact statement)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.pop("PAYROLL_MCP_OFFLINE", None)

from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools

QUESTION = (
    "List 10 distinct employees where status_class is not 'T'. "
    "Return columns: employee_id, client_id, client_name, employment_type, status_class. "
    "Order by client_id, employee_id."
)


def _as_text(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        parts = []
        for block in result:
            if isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    if isinstance(result, dict):
        return str(result.get("text") or result)
    return str(result)


def _extract_sql(analyst_result: object) -> str | None:
    """Pull Analyst `statement` from nested MCP / LangChain content shapes."""
    text = _as_text(analyst_result).strip()
    # Outer payload may be a JSON array string inside text
    candidates: list[object] = [analyst_result, text]
    try:
        candidates.append(json.loads(text))
    except Exception:
        pass

    def walk(obj: object) -> str | None:
        if isinstance(obj, dict):
            stmt = obj.get("statement") or obj.get("sql")
            if isinstance(stmt, str) and "select" in stmt.lower():
                return stmt.strip()
            for v in obj.values():
                found = walk(v)
                if found:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = walk(item)
                if found:
                    return found
        elif isinstance(obj, str):
            s = obj.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    return walk(json.loads(s))
                except Exception:
                    pass
        return None

    for c in candidates:
        found = walk(c)
        if found:
            return found
    return None


def _parse_employee_rows(executor_result: object) -> list[dict]:
    text = _as_text(executor_result)
    # Try JSON with data rows
    try:
        payload = json.loads(text) if text.startswith("{") or text.startswith("[") else None
    except Exception:
        payload = None
    rows: list[dict] = []
    if isinstance(payload, dict):
        data = payload.get("data") or payload.get("rows")
        meta = (
            (payload.get("resultSetMetaData") or {}).get("rowType")
            or payload.get("rowType")
            or []
        )
        names = [c.get("name") for c in meta if isinstance(c, dict)]
        if data and names:
            for row in data:
                rows.append({str(names[i]).lower(): row[i] for i in range(min(len(names), len(row)))})
            return rows
    # Fallback: look for nested JSON in text blocks
    try:
        outer = json.loads(text) if isinstance(executor_result, str) else executor_result
        if isinstance(outer, list):
            for block in outer:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    inner = json.loads(block["text"])
                    return _parse_employee_rows(inner)
    except Exception:
        pass
    return rows


def main() -> None:
    clear_qa_tools_cache()
    tools = {t.name: t for t in get_qa_tools(force_reload=True)}
    analyst = tools["sv_hr_workforce"]
    executor = tools["sql_query_executor"]

    import asyncio

    async def _ainvoke(tool, kwargs):
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(kwargs)
        return tool.invoke(kwargs)

    print("1) Analyst...")
    analyst_out = asyncio.run(_ainvoke(analyst, {"message": QUESTION}))
    sql = _extract_sql(analyst_out)
    if not sql:
        raise SystemExit("No Analyst SQL statement found")
    print(sql)
    print("---")

    print("2) sql_query_executor...")
    # Discover arg name
    schema = getattr(executor, "args_schema", None)
    fields: list[str] = []
    if schema is not None:
        try:
            fields = list(schema.model_json_schema().get("properties", {}).keys())
        except Exception:
            fields = []
    arg = "sql"
    for candidate in ("sql", "statement", "query", "message"):
        if not fields or candidate in fields:
            arg = candidate
            break
    rows_out = asyncio.run(_ainvoke(executor, {arg: sql}))
    print(_as_text(rows_out)[:2500])
    employees = _parse_employee_rows(rows_out)

    # Also try parsing from raw if empty
    if not employees:
        # Heuristic: Snowflake result often embeds JSON with "data":[[...]]
        raw = _as_text(rows_out)
        try:
            # Find first { ... } with data
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                employees = _parse_employee_rows(json.loads(raw[start : end + 1]))
        except Exception:
            pass

    out = {
        "question": QUESTION,
        "sql": sql,
        "employees": employees,
        "raw_preview": _as_text(rows_out)[:20000],
    }
    path = ROOT / "fixtures" / "e2e_employees_live.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print("Wrote", path, "employees=", len(employees))
    for e in employees:
        print(e)


if __name__ == "__main__":
    main()
