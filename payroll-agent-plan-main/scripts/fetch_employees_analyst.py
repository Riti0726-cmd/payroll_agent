"""Fetch sample employees via Cortex Analyst only (no hand-written SQL)."""

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
    "Execute and return data rows (not just SQL): List 10 distinct active employees "
    "(where status_class is not 'T') showing employee_id, client_id, client_name, "
    "employment_type, and status_class, ordered by client_id and employee_id. "
    "Return the actual result table."
)


def main() -> None:
    clear_qa_tools_cache()
    tools = get_qa_tools(force_reload=True)
    by_name = {t.name: t for t in tools}
    if "sv_hr_workforce" not in by_name:
        print("ERROR: sv_hr_workforce not in tools:", list(by_name))
        sys.exit(1)

    tool = by_name["sv_hr_workforce"]
    print("Calling Cortex Analyst tool: sv_hr_workforce")
    print("Question:", QUESTION)
    print("---")

    # LangChain tools accept kwargs matching schema; try common analyst arg names
    schema = getattr(tool, "args_schema", None)
    fields: list[str] = []
    if schema is not None:
        try:
            fields = list(schema.model_json_schema().get("properties", {}).keys())
        except Exception:
            fields = []
    print("Tool args:", fields or "(unknown)")

    kwargs = {}
    for candidate in ("message", "question", "query", "prompt", "input"):
        if not fields or candidate in fields:
            kwargs[candidate] = QUESTION
            break
    if not kwargs and fields:
        kwargs[fields[0]] = QUESTION

    # Cortex Analyst MCP expects `message`
    if "message" not in kwargs:
        kwargs = {"message": QUESTION}

    print("Invoke kwargs keys:", list(kwargs))

    async def _run():
        if hasattr(tool, "ainvoke"):
            return await tool.ainvoke(kwargs)
        return tool.invoke(kwargs)

    import asyncio

    result = asyncio.run(_run())
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(str(result))


if __name__ == "__main__":
    main()
