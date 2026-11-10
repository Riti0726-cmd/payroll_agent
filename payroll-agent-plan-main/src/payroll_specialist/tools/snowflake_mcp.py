"""Snowflake / Cortex QA tools via MCP (mcp_config.json → mcp-remote OAuth)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger("payroll-specialist")

MCP_UNAVAILABLE = (
    "Snowflake MCP is not configured. Provide mcp_config.json (Cursor-style mcpServers "
    "with mcp-remote + --static-oauth-client-info), or set SNOWFLAKE_MCP_SERVER_URL "
    "with OAuth credentials. For PAT auth set SNOWFLAKE_MCP_AUTH=pat and SNOWFLAKE_PAT."
)

_tools_cache: list[Any] | None = None


class SnowflakeMcpConfigError(ValueError):
    """Raised when Snowflake Cortex MCP settings are missing or invalid."""


def mcp_unavailable_payload() -> str:
    return json.dumps({"status": "error", "error": MCP_UNAVAILABLE})


def _run_coro_sync(coro: Any) -> Any:
    """Run an async coroutine from sync code (graph build / tool factory)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=120)


async def _load_tools_from_mcp_config() -> list[Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    from tools.mcp_config import build_mcp_connections, find_mcp_config_path, load_mcp_config

    path = find_mcp_config_path()
    if path is None:
        raise SnowflakeMcpConfigError(MCP_UNAVAILABLE)

    config = load_mcp_config(path)
    connections = build_mcp_connections(config)
    logger.info(
        "Connecting MCP via %s (%s)",
        path,
        ", ".join(connections.keys()),
    )
    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    if not tools:
        raise SnowflakeMcpConfigError("MCP connected but returned no tools.")
    logger.info("Loaded %d MCP tool(s): %s", len(tools), [t.name for t in tools])
    return list(tools)


@tool
def snowflake_mcp_unavailable() -> str:
    """Report that Snowflake Cortex MCP is not configured. Do not invent payroll data."""
    return mcp_unavailable_payload()


def clear_qa_tools_cache() -> None:
    global _tools_cache
    _tools_cache = None
    try:
        from qa_agent import clear_qa_agent_cache

        clear_qa_agent_cache()
    except ImportError:
        pass


def prepare_host_mcp_runtime() -> None:
    """Clear CI/offline MCP stubs so the host and POST /qa use live Snowflake tools.

    ``PAYROLL_MCP_OFFLINE`` is set by pytest ``conftest`` and is easy to leave in a
    developer shell; the API process must never keep it.
    """
    prior = os.environ.pop("PAYROLL_MCP_OFFLINE", None)
    if prior and str(prior).strip():
        logger.warning(
            "Cleared PAYROLL_MCP_OFFLINE=%r for live host / Q&A MCP runtime",
            prior,
        )
    clear_qa_tools_cache()


def get_qa_tools(*, force_reload: bool = False) -> list[Any]:
    """Return LangChain tools from mcp_config.json (mcp-remote OAuth).

    Raises on failure — no silent stub tools in production.
    ``PAYROLL_MCP_OFFLINE=1`` is test/CI only and returns the unavailable stub tool.
    """
    global _tools_cache

    if os.environ.get("PAYROLL_MCP_OFFLINE", "").strip().lower() in ("1", "true", "yes"):
        logger.warning("PAYROLL_MCP_OFFLINE=1 — returning unavailable stub (test/CI only)")
        return [snowflake_mcp_unavailable]

    if _tools_cache is not None and not force_reload:
        return _tools_cache

    try:
        tools = _run_coro_sync(_load_tools_from_mcp_config())
        _tools_cache = tools
        return tools
    except Exception as exc:
        logger.exception("MCP tool load failed")
        raise SnowflakeMcpConfigError(f"Snowflake MCP unavailable: {exc}") from exc


# --- Compat helpers used by older HTTP/OAuth unit tests (optional path) ---

def get_snowflake_mcp_url() -> str:
    from tools.mcp_config import apply_mcp_config_to_env, find_mcp_config_path, load_mcp_config

    if find_mcp_config_path() is not None:
        apply_mcp_config_to_env(load_mcp_config())
    url = os.getenv("SNOWFLAKE_MCP_SERVER_URL", "").strip()
    if not url:
        raise SnowflakeMcpConfigError(MCP_UNAVAILABLE)
    return url


def assert_snowflake_oauth_configured() -> None:
    from tools.mcp_config import find_mcp_config_path, resolve_mcp_auth_mode

    if find_mcp_config_path() is not None:
        if resolve_mcp_auth_mode() == "pat":
            if not (
                os.getenv("SNOWFLAKE_PAT", "").strip()
                or os.getenv("SNOWFLAKE_OAUTH_TOKEN", "").strip()
            ):
                raise SnowflakeMcpConfigError(MCP_UNAVAILABLE)
        return
    if os.getenv("SNOWFLAKE_MCP_SERVER_URL", "").strip() and (
        os.getenv("SNOWFLAKE_OAUTH_TOKEN", "").strip()
        or os.getenv("SNOWFLAKE_PAT", "").strip()
        or (
            os.getenv("SNOWFLAKE_OAUTH_CLIENT_ID", "").strip()
            and os.getenv("SNOWFLAKE_OAUTH_CLIENT_SECRET", "").strip()
        )
    ):
        return
    raise SnowflakeMcpConfigError(MCP_UNAVAILABLE)
