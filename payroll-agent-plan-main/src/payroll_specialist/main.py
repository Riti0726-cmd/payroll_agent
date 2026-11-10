# Copyright (c) Microsoft & EngageAI. All rights reserved.

"""LangGraph Payroll Specialist Engine — Foundry Hosted Agent (Responses protocol)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

# Suppress Live Metrics / QuickPulse export to prevent 403 Forbidden on Azure Monitor
# when the container's Managed Identity lacks the 'Monitoring Metrics Publisher' role.
os.environ["OTEL_AUTO_CONFIGURE_AZURE_MONITOR"] = "false"
os.environ["APPLICATIONINSIGHTS_ENABLE_LIVE_METRICS"] = "false"
os.environ["APPLICATIONINSIGHTS_LIVE_METRICS_ENABLED"] = "false"
os.environ["APPLICATIONINSIGHTS_STATSBEAT_DISABLED_ALL"] = "true"
os.environ["OTEL_METRICS_EXPORTER"] = "none"
os.environ.pop("APPLICATIONINSIGHTS_AUTHENTICATION_STRING", None)

try:
    import azure.monitor.opentelemetry.exporter._quickpulse as _qp

    _qp.enable_live_metrics = lambda **kwargs: None
except Exception:
    pass

try:
    import azure.monitor.opentelemetry.exporter._quickpulse._live_metrics as _qp_lm

    _qp_lm.enable_live_metrics = lambda **kwargs: None
except Exception:
    pass

try:
    from azure.monitor.opentelemetry.exporter._quickpulse._state import get_quickpulse_manager

    _qp_mgr = get_quickpulse_manager()
    _qp_mgr.initialize = lambda **kwargs: False
except Exception:
    pass

try:
    from azure.monitor.opentelemetry.exporter._quickpulse._exporter import _QuickpulseExporter
    from opentelemetry.sdk.metrics.export import MetricExportResult

    _QuickpulseExporter.export = lambda self, *args, **kwargs: MetricExportResult.SUCCESS
except Exception:
    pass

from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Repo-root .env (cwd may be src/payroll_specialist when launched from an IDE).
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")
load_dotenv()

# Pytest/conftest sets PAYROLL_MCP_OFFLINE=1; never keep that in the live host.
from tools.snowflake_mcp import prepare_host_mcp_runtime  # noqa: E402

prepare_host_mcp_runtime()

logging.basicConfig(level=logging.INFO, format="%(message)s")
for name in ("azure", "azure.core", "azure.identity", "httpx", "httpx2", "openai"):
    logging.getLogger(name).setLevel(logging.WARNING)

logger = logging.getLogger("payroll-specialist")


def create_graph() -> Any:
    """Create and compile the LangGraph agent for Foundry Responses hosting."""
    from graph import create_payroll_graph
    from telemetry import configure_telemetry

    configure_telemetry()
    return create_payroll_graph()


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph Payroll Specialist Hosted Agent")
    parser.add_argument("--test", type=str, help="Run a test query directly from command line.")
    args = parser.parse_args()

    graph = create_graph()

    if args.test:
        from langchain_core.messages import HumanMessage

        logger.info("Executing test query: %s", args.test)
        result = asyncio.run(graph.ainvoke({"messages": [HumanMessage(content=args.test)]}))
        print("\n=== LANGGRAPH WORKFLOW OUTPUT ===\n")
        messages = result.get("messages", [])
        if messages:
            print(messages[-1].content)
        else:
            print(result)
        return

    logger.info("Starting LangGraph Payroll Specialist on ResponsesHostServer (port 8088)...")
    try:
        from langchain_azure_ai.agents.hosting import ResponsesHostServer

        server = ResponsesHostServer(graph)
        from changelists_http import mount_changelists_routes
        from drafts_http import mount_drafts_routes
        from emails_http import mount_emails_routes
        from cors import mount_cors_middleware
        from history_http import mount_history_route
        from qa_http import mount_qa_route
        from queue_http import mount_queue_route
        from settings_http import mount_settings_routes
        from triage.graph_token_middleware import mount_graph_token_middleware
        from triage_http import mount_triage_stream_route

        mount_graph_token_middleware(server.app)
        mount_qa_route(server.app)
        mount_queue_route(server.app)
        mount_history_route(server.app)
        mount_settings_routes(server.app)
        mount_drafts_routes(server.app)
        mount_changelists_routes(server.app)
        mount_triage_stream_route(server.app)
        mount_emails_routes(server.app)
        # Added last so it is the outermost middleware and answers preflights.
        mount_cors_middleware(server.app)
        logger.info("Mounted standalone Q&A agent at POST /qa")
        logger.info("Mounted queue API at GET /queue")
        logger.info("Mounted history API at GET /history")
        logger.info("Mounted settings API at GET/PUT /settings")
        logger.info("Mounted drafts API at GET/PATCH /drafts")
        logger.info("Mounted changelists API at GET/PATCH /changelists")
        logger.info("Mounted triage stream at POST /triage/stream")
        logger.info("Mounted email lookup at GET /emails/lookup")
        server.run(port=8088)
    except ImportError:
        logger.warning(
            "langchain_azure_ai.agents.hosting not found. Falling back to agent_framework_foundry_hosting."
        )
        try:
            from agent_framework_foundry_hosting import ResponsesHostServer

            server = ResponsesHostServer(graph)
            from changelists_http import mount_changelists_routes
            from drafts_http import mount_drafts_routes
            from emails_http import mount_emails_routes
            from cors import mount_cors_middleware
            from history_http import mount_history_route
            from qa_http import mount_qa_route
            from queue_http import mount_queue_route
            from settings_http import mount_settings_routes
            from triage.graph_token_middleware import mount_graph_token_middleware
            from triage_http import mount_triage_stream_route

            mount_graph_token_middleware(server.app)
            mount_qa_route(server.app)
            mount_queue_route(server.app)
            mount_history_route(server.app)
            mount_settings_routes(server.app)
            mount_drafts_routes(server.app)
            mount_changelists_routes(server.app)
            mount_triage_stream_route(server.app)
            mount_emails_routes(server.app)
            # Added last so it is the outermost middleware and answers preflights.
            mount_cors_middleware(server.app)
            logger.info("Mounted standalone Q&A agent at POST /qa")
            logger.info("Mounted queue API at GET /queue")
            logger.info("Mounted history API at GET /history")
            logger.info("Mounted settings API at GET/PUT /settings")
            logger.info("Mounted drafts API at GET/PATCH /drafts")
            logger.info("Mounted changelists API at GET/PATCH /changelists")
            logger.info("Mounted triage stream at POST /triage/stream")
            logger.info("Mounted email lookup at GET /emails/lookup")
            server.run()
        except Exception as exc:
            logger.error("Could not start ResponsesHostServer: %s", exc)
            raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
