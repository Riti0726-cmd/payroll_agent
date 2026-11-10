import json
from pathlib import Path

import pytest

from tools.mcp_config import (
    apply_mcp_config_to_env,
    build_mcp_connections,
    load_mcp_config,
    normalize_stdio_connection,
)
from tools.snowflake_mcp import (
    clear_qa_tools_cache,
    get_qa_tools,
    prepare_host_mcp_runtime,
    snowflake_mcp_unavailable,
)


def test_load_repo_mcp_config():
    root = Path(__file__).resolve().parents[1]
    config = load_mcp_config(root / "mcp_config.json")
    assert "snowflake-engage-knowledge-mcp-server" in config["mcpServers"]


def test_build_connections_stdio(tmp_path, monkeypatch):
    cfg = {
        "mcpServers": {
            "snowflake-engage-knowledge-mcp-server": {
                "command": "cmd",
                "args": [
                    "/c",
                    "npx",
                    "-y",
                    "mcp-remote",
                    "https://example.snowflakecomputing.com/api/v2/databases/D/schemas/S/mcp-servers/M",
                    "3336",
                    "--host",
                    "localhost",
                    "--static-oauth-client-info",
                    json.dumps({"client_id": "cid", "client_secret": "csecret"}),
                ],
            }
        }
    }
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.delenv("SNOWFLAKE_MCP_SERVER_URL", raising=False)
    monkeypatch.delenv("SNOWFLAKE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("SNOWFLAKE_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SNOWFLAKE_MCP_AUTH", raising=False)
    monkeypatch.setenv("SNOWFLAKE_MCP_AUTH", "oauth")
    monkeypatch.delenv("SNOWFLAKE_PAT", raising=False)

    applied = apply_mcp_config_to_env(cfg)
    assert "SNOWFLAKE_MCP_SERVER_URL" in applied
    assert "mcp-servers/M" in applied["SNOWFLAKE_MCP_SERVER_URL"]

    connections = build_mcp_connections(load_mcp_config(path))
    assert "snowflake-engage-knowledge-mcp-server" in connections
    conn = connections["snowflake-engage-knowledge-mcp-server"]
    assert conn["transport"] == "stdio"
    assert conn["command"] in ("cmd", "npx")
    blob = " ".join([conn["command"], *conn["args"]])
    assert "mcp-remote" in blob


def test_normalize_unwraps_cmd_on_non_windows(monkeypatch):
    monkeypatch.setattr("tools.mcp_config.platform.system", lambda: "Linux")
    conn = normalize_stdio_connection(
        {
            "command": "cmd",
            "args": ["/c", "npx", "-y", "mcp-remote", "https://x.example/mcp"],
        }
    )
    assert conn["command"] == "npx"
    assert conn["args"][0] == "-y"


def test_qa_tools_offline_stub(monkeypatch):
    clear_qa_tools_cache()
    monkeypatch.setenv("PAYROLL_MCP_OFFLINE", "1")
    tools = get_qa_tools(force_reload=True)
    assert len(tools) == 1
    assert tools[0].name == snowflake_mcp_unavailable.name


def test_prepare_host_mcp_runtime_clears_offline_stub(monkeypatch):
    """Host/API must not keep PAYROLL_MCP_OFFLINE from a prior pytest/shell session."""
    monkeypatch.setenv("PAYROLL_MCP_OFFLINE", "1")
    clear_qa_tools_cache()
    assert get_qa_tools(force_reload=True)[0].name == snowflake_mcp_unavailable.name

    prepare_host_mcp_runtime()
    assert "PAYROLL_MCP_OFFLINE" not in __import__("os").environ
    # After prepare, offline stub path is disabled (live load may still fail without MCP).
    clear_qa_tools_cache()
    monkeypatch.setenv("PAYROLL_MCP_OFFLINE", "1")
    prepare_host_mcp_runtime()
    assert __import__("os").environ.get("PAYROLL_MCP_OFFLINE") in (None, "")


def _oauth_stdio_cfg() -> dict:
    return {
        "mcpServers": {
            "snowflake-engage-knowledge-mcp-server": {
                "command": "cmd",
                "args": [
                    "/c",
                    "npx",
                    "-y",
                    "mcp-remote",
                    "https://example.snowflakecomputing.com/api/v2/databases/D/schemas/S/mcp-servers/M",
                    "3336",
                    "--host",
                    "localhost",
                    "--static-oauth-client-info",
                    json.dumps({"client_id": "cid", "client_secret": "csecret"}),
                ],
            }
        }
    }


def test_build_connections_auth_oauth_default(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(_oauth_stdio_cfg()), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.delenv("SNOWFLAKE_MCP_AUTH", raising=False)
    monkeypatch.delenv("SNOWFLAKE_MCP_SERVER_URL", raising=False)

    connections = build_mcp_connections(load_mcp_config(path))
    conn = connections["snowflake-engage-knowledge-mcp-server"]
    assert conn["transport"] == "stdio"


def test_build_connections_auth_pat(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(_oauth_stdio_cfg()), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.setenv("SNOWFLAKE_MCP_AUTH", "pat")
    monkeypatch.setenv("SNOWFLAKE_PAT", "pat-secret-token")
    monkeypatch.delenv("SNOWFLAKE_MCP_SERVER_URL", raising=False)
    monkeypatch.delenv("SNOWFLAKE_OAUTH_TOKEN", raising=False)

    connections = build_mcp_connections(load_mcp_config(path))
    assert len(connections) == 1
    name, conn = next(iter(connections.items()))
    assert name == "snowflake-engage-knowledge-mcp-server"
    assert conn["transport"] == "streamable_http"
    assert conn["url"].endswith("/mcp-servers/M")
    assert conn["headers"]["Authorization"] == "Bearer pat-secret-token"


def test_build_connections_auth_pat_uses_oauth_token_fallback(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(_oauth_stdio_cfg()), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.setenv("SNOWFLAKE_MCP_AUTH", "pat")
    monkeypatch.delenv("SNOWFLAKE_PAT", raising=False)
    monkeypatch.setenv("SNOWFLAKE_OAUTH_TOKEN", "legacy-bearer")
    monkeypatch.delenv("SNOWFLAKE_MCP_SERVER_URL", raising=False)

    connections = build_mcp_connections(load_mcp_config(path))
    conn = next(iter(connections.values()))
    assert conn["headers"]["Authorization"] == "Bearer legacy-bearer"


def test_build_connections_auth_pat_missing_token(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(_oauth_stdio_cfg()), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.setenv("SNOWFLAKE_MCP_AUTH", "pat")
    monkeypatch.delenv("SNOWFLAKE_PAT", raising=False)
    monkeypatch.delenv("SNOWFLAKE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("SNOWFLAKE_MCP_SERVER_URL", raising=False)

    with pytest.raises(ValueError, match="SNOWFLAKE_PAT"):
        build_mcp_connections(load_mcp_config(path))


def test_build_connections_auth_invalid(tmp_path, monkeypatch):
    path = tmp_path / "mcp_config.json"
    path.write_text(json.dumps(_oauth_stdio_cfg()), encoding="utf-8")
    monkeypatch.setenv("MCP_CONFIG_PATH", str(path))
    monkeypatch.setenv("SNOWFLAKE_MCP_AUTH", "kerberos")

    with pytest.raises(ValueError, match="SNOWFLAKE_MCP_AUTH"):
        build_mcp_connections(load_mcp_config(path))
