"""Verify specialist credentials against Snowflake sv_user_credentials.

This module provides a credential-check tool that the validation node
can invoke to confirm a specialist is authorized for a specific client
before the QA / Changelist agents run queries.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("payroll-specialist")


async def verify_credentials_via_mcp(
    mcp_tools: dict[str, Any],
    username: str,
    client_id: str,
) -> dict[str, Any]:
    """Query sv_user_credentials through Cortex Analyst MCP tools.

    Returns dict with keys: is_authorized, role, allowed_clients, error.
    """
    analyst_tool = None
    executor_tool = None
    for name, tool in mcp_tools.items():
        lower = name.lower()
        if "analyst" in lower and "sql" not in lower:
            analyst_tool = tool
        if "sql" in lower or "executor" in lower:
            executor_tool = tool

    if not analyst_tool or not executor_tool:
        return {
            "is_authorized": False,
            "role": None,
            "allowed_clients": [],
            "error": "Cortex Analyst or sql_query_executor tool not found in MCP tools.",
        }

    # Step 1: Ask Analyst to generate SQL for credential check
    try:
        analyst_query = (
            f"Check if username '{username}' exists in sv_user_credentials "
            f"and is active. Return username, role, client_ids, is_active."
        )
        analyst_result = await analyst_tool.ainvoke({"message": analyst_query})

        # Step 2: Extract SQL and execute
        if isinstance(analyst_result, str):
            parsed = json.loads(analyst_result)
        else:
            parsed = analyst_result

        sql = None
        if isinstance(parsed, dict):
            for key in ("sql", "generated_sql", "statement", "query_sql"):
                if key in parsed and parsed[key]:
                    sql = parsed[key]
                    break

        if not sql:
            # Fallback: direct SQL query
            sql = (
                f"SELECT username, role, client_ids, is_active "
                f"FROM sv_user_credentials "
                f"WHERE username = '{username}' AND is_active = TRUE"
            )

        exec_result = await executor_tool.ainvoke({"statement": sql})

        if isinstance(exec_result, str):
            exec_parsed = json.loads(exec_result)
        else:
            exec_parsed = exec_result

        # Step 3: Parse result rows
        rows = []
        if isinstance(exec_parsed, dict):
            result_set = exec_parsed.get("result_set", exec_parsed)
            data = result_set.get("data", [])
            if isinstance(data, list):
                rows = data

        if not rows:
            return {
                "is_authorized": False,
                "role": None,
                "allowed_clients": [],
                "error": f"No active user found for username '{username}'.",
            }

        # First matching row
        row = rows[0]
        if isinstance(row, (list, tuple)):
            # Positional: username, role, client_ids, is_active
            user_role = row[1] if len(row) > 1 else None
            raw_clients = row[2] if len(row) > 2 else []
        elif isinstance(row, dict):
            user_role = row.get("ROLE") or row.get("role")
            raw_clients = row.get("CLIENT_IDS") or row.get("client_ids") or []
        else:
            return {"is_authorized": False, "role": None, "allowed_clients": [], "error": "Unexpected row format."}

        if isinstance(raw_clients, str):
            try:
                allowed = json.loads(raw_clients)
            except json.JSONDecodeError:
                allowed = [raw_clients]
        elif isinstance(raw_clients, list):
            allowed = raw_clients
        else:
            allowed = []

        is_authorized = client_id in allowed or user_role == "admin"

        return {
            "is_authorized": is_authorized,
            "role": user_role,
            "allowed_clients": allowed,
            "error": None if is_authorized else f"User '{username}' not authorized for client '{client_id}'.",
        }

    except Exception as exc:
        logger.warning("Credential verification failed: %s", exc)
        return {
            "is_authorized": False,
            "role": None,
            "allowed_clients": [],
            "error": f"Credential check failed: {exc}",
        }
