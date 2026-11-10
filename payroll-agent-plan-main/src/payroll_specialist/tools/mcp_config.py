"""Load Cursor-style mcp_config.json and build MCP client connections."""

from __future__ import annotations

import json
import logging
import os
import platform
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("payroll-specialist")

_DEFAULT_CONFIG_NAMES = ("mcp_config.json", ".cursor/mcp.json", "mcp.json")


def find_mcp_config_path(explicit: str | None = None) -> Path | None:
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None

    env_path = os.environ.get("MCP_CONFIG_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.is_file():
            return path

    # Walk from package dir up to repo root, then cwd
    candidates: list[Path] = []
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        for name in _DEFAULT_CONFIG_NAMES:
            candidates.append(parent / name)
    candidates.append(Path.cwd() / "mcp_config.json")

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        if path.is_file():
            return path
    return None


def load_mcp_config(path: Path | None = None) -> dict[str, Any]:
    resolved = path or find_mcp_config_path()
    if resolved is None:
        raise FileNotFoundError(
            "mcp_config.json not found. Set MCP_CONFIG_PATH or place mcp_config.json at the repo root."
        )
    raw = resolved.read_text(encoding="utf-8").strip()
    # Tolerate a bare "mcpServers": {...} fragment
    if raw.startswith('"mcpServers"'):
        raw = "{" + raw + "}"
    data = json.loads(raw)
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        raise ValueError(f"{resolved} missing mcpServers object")
    return data


def _parse_static_oauth_client_info(args: list[str]) -> dict[str, str]:
    for idx, arg in enumerate(args):
        if arg == "--static-oauth-client-info" and idx + 1 < len(args):
            try:
                info = json.loads(args[idx + 1])
            except json.JSONDecodeError:
                return {}
            if isinstance(info, dict):
                return {
                    "client_id": str(info.get("client_id") or "").strip(),
                    "client_secret": str(info.get("client_secret") or "").strip(),
                }
    return {}


def _extract_remote_url(args: list[str]) -> str | None:
    for arg in args:
        if isinstance(arg, str) and arg.startswith("https://") and "mcp-servers" in arg:
            return arg
    for arg in args:
        if isinstance(arg, str) and arg.startswith("https://"):
            return arg
    return None


def apply_mcp_config_to_env(config: dict[str, Any] | None = None) -> dict[str, str]:
    """Populate SNOWFLAKE_* env vars from mcp_config when unset."""
    data = config or load_mcp_config()
    applied: dict[str, str] = {}
    servers = data.get("mcpServers") or {}
    for _name, server in servers.items():
        args = list(server.get("args") or [])
        url = _extract_remote_url(args)
        oauth = _parse_static_oauth_client_info(args)
        if url and not os.environ.get("SNOWFLAKE_MCP_SERVER_URL", "").strip():
            os.environ["SNOWFLAKE_MCP_SERVER_URL"] = url
            applied["SNOWFLAKE_MCP_SERVER_URL"] = url
            # Derive account host
            m = re.match(r"https://([^/]+)", url)
            if m and not os.environ.get("SNOWFLAKE_ACCOUNT", "").strip():
                host = m.group(1)
                account = host.replace(".snowflakecomputing.com", "")
                os.environ["SNOWFLAKE_ACCOUNT"] = account
                applied["SNOWFLAKE_ACCOUNT"] = account
        if oauth.get("client_id") and not os.environ.get("SNOWFLAKE_OAUTH_CLIENT_ID", "").strip():
            os.environ["SNOWFLAKE_OAUTH_CLIENT_ID"] = oauth["client_id"]
            applied["SNOWFLAKE_OAUTH_CLIENT_ID"] = oauth["client_id"]
        if oauth.get("client_secret") and not os.environ.get("SNOWFLAKE_OAUTH_CLIENT_SECRET", "").strip():
            os.environ["SNOWFLAKE_OAUTH_CLIENT_SECRET"] = oauth["client_secret"]
            applied["SNOWFLAKE_OAUTH_CLIENT_SECRET"] = "***"
        break
    return applied


def normalize_stdio_connection(server: dict[str, Any]) -> dict[str, Any]:
    """Build a langchain-mcp-adapters / MCP stdio connection from one mcpServers entry.

    Unwraps Windows `cmd /c npx ...` to plain `npx` on non-Windows (Foundry Linux).
    """
    command = str(server.get("command") or "").strip()
    args = [str(a) for a in (server.get("args") or [])]
    env = dict(server.get("env") or {})

    if command.lower() == "cmd" and args[:1] == ["/c"]:
        rest = args[1:]
        if platform.system() != "Windows" and rest:
            command = rest[0]
            args = rest[1:]
        # else keep cmd /c on Windows so npx.cmd resolves

    if not command:
        raise ValueError("mcp server entry missing command")

    return {
        "transport": "stdio",
        "command": command,
        "args": args,
        "env": env or None,
    }


def resolve_mcp_auth_mode() -> str:
    """Return ``oauth`` (default) or ``pat`` from ``SNOWFLAKE_MCP_AUTH``."""
    raw = os.environ.get("SNOWFLAKE_MCP_AUTH", "oauth").strip().lower()
    if raw in ("", "oauth", "oauth2"):
        return "oauth"
    if raw in ("pat", "token", "bearer"):
        return "pat"
    raise ValueError(
        f"Invalid SNOWFLAKE_MCP_AUTH={raw!r}. Use 'oauth' (mcp-remote) or 'pat' (Bearer PAT)."
    )


def _pat_bearer_token() -> str:
    token = (
        os.environ.get("SNOWFLAKE_PAT", "").strip()
        or os.environ.get("SNOWFLAKE_OAUTH_TOKEN", "").strip()
    )
    if not token:
        raise ValueError(
            "SNOWFLAKE_MCP_AUTH=pat requires SNOWFLAKE_PAT (or SNOWFLAKE_OAUTH_TOKEN) to be set."
        )
    return token


def _build_pat_connections(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """HTTP connection using Bearer PAT; URL from env or first mcpServers entry."""
    apply_mcp_config_to_env(data)
    url = os.environ.get("SNOWFLAKE_MCP_SERVER_URL", "").strip()
    name = "snowflake"
    servers = data.get("mcpServers") or {}
    for server_name, server in servers.items():
        if not isinstance(server, dict):
            continue
        name = str(server_name)
        if not url:
            args = list(server.get("args") or [])
            url = (_extract_remote_url(args) or str(server.get("url") or "").strip())
        break
    if not url:
        raise ValueError(
            "SNOWFLAKE_MCP_AUTH=pat requires SNOWFLAKE_MCP_SERVER_URL "
            "(or a URL in mcp_config.json)."
        )
    token = _pat_bearer_token()
    return {
        name: {
            "transport": "streamable_http",
            "url": url,
            "headers": {"Authorization": f"Bearer {token}"},
        }
    }


def build_mcp_connections(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return MultiServerMCPClient connections keyed by server name.

    ``SNOWFLAKE_MCP_AUTH=oauth`` (default): stdio mcp-remote / HTTP entries from config.
    ``SNOWFLAKE_MCP_AUTH=pat``: single streamable HTTP connection with Bearer PAT.
    """
    data = config or load_mcp_config()
    mode = resolve_mcp_auth_mode()
    if mode == "pat":
        return _build_pat_connections(data)

    apply_mcp_config_to_env(data)
    connections: dict[str, dict[str, Any]] = {}
    for name, server in (data.get("mcpServers") or {}).items():
        if not isinstance(server, dict):
            continue
        # Prefer stdio (mcp-remote) when command is present — matches Cursor config
        if server.get("command"):
            connections[name] = normalize_stdio_connection(server)
            continue
        # HTTP / SSE style entries
        url = str(server.get("url") or "").strip()
        if url:
            entry: dict[str, Any] = {
                "transport": server.get("transport") or "streamable_http",
                "url": url,
            }
            headers = server.get("headers")
            if isinstance(headers, dict):
                entry["headers"] = headers
            connections[name] = entry
    if not connections:
        raise ValueError("No usable MCP server entries in mcp_config.json")
    return connections
