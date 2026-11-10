"""List tools from mcp_config.json (mcp-remote + Snowflake OAuth).

Usage (from repo root):
  .\\.venv\\Scripts\\python.exe scripts\\list_mcp_tools.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

# Allow live MCP for this script
os.environ.pop("PAYROLL_MCP_OFFLINE", None)

from tools.mcp_config import resolve_mcp_auth_mode  # noqa: E402
from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools  # noqa: E402


def main() -> None:
    clear_qa_tools_cache()
    print(f"SNOWFLAKE_MCP_AUTH={resolve_mcp_auth_mode()}")
    tools = get_qa_tools(force_reload=True)
    print(f"Loaded {len(tools)} tool(s):")
    for t in tools:
        print(f"  - {t.name}")


if __name__ == "__main__":
    main()
