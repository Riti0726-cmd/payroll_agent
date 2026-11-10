"""Step-by-step trace of agent execution from Azure Foundry LLM to Snowflake MCP.

Shows every step the multi-agent pipeline performs:
  [Step 1] Ingested email retrieval from Neon DB
  [Step 2] Classifier node (Foundry Responses LLM)
  [Step 3] Validation agent node (Foundry LLM -> Snowflake MCP workforce verification)
  [Step 4] Routing decision (conditional branch)
  [Step 5] QA / Changelist specialist node (Foundry LLM -> Snowflake MCP payroll & benefits queries)
  [Step 6] Drafting specialist node (Foundry LLM executive response)
  [Step 7] Neon DB persistence & HITL status

Usage:
  python scripts/trace_agent_execution.py
  python scripts/trace_agent_execution.py --message-id MSG-SF-009-QA-NETPAY
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# If invoked with global/system python instead of the project venv, re-exec using .venv
_venv_python = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
    import subprocess
    sys.exit(subprocess.call([str(_venv_python)] + sys.argv))

PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.pop("PAYROLL_MCP_OFFLINE", None)

logging.basicConfig(level=logging.WARNING)
for name in ("azure", "azure.core", "httpx", "httpx2", "openai", "httpcore"):
    logging.getLogger(name).setLevel(logging.ERROR)

from db.database import get_session_factory
from db.models import EmailProcessing
from graph import build_chat_model
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from message_text import extract_message_text
from models import ChangelistBuildResult, ClassificationResult, ValidationResult
from nodes.classifier import make_classifier_node
from nodes.drafting import make_drafting_node
from nodes.qa import make_qa_node
from nodes.validation import make_validation_node
from prompts import (
    CLASSIFIER_INSTRUCTIONS,
    DRAFTER_INSTRUCTIONS,
    QA_INSTRUCTIONS,
    VALIDATION_INSTRUCTIONS,
)
from structured_output import with_structured
from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools


def _banner(title: str, step_num: int) -> None:
    print("\n" + "=" * 80)
    print(f"  [STEP {step_num}] {title}")
    print("=" * 80)


def _subheading(text: str) -> None:
    print(f"\n--- {text} ---")


def _print_tool_result(name: str, content: Any) -> None:
    """Print the complete, clean tool result without truncation, metadata noise, or encrypted thought tokens."""
    print(f"  <- [TOOL RESULT] {name}:")
    raw_text = None
    if isinstance(content, list) and content:
        if isinstance(content[0], dict) and "text" in content[0]:
            raw_text = content[0]["text"]
        elif isinstance(content[0], str):
            raw_text = "\n".join(content)
    elif isinstance(content, str):
        raw_text = content
    elif isinstance(content, dict) and "text" in content:
        raw_text = content["text"]

    if raw_text is not None:
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                # Snowflake agent responses format: {"content": [{"type": "text", ...}, {"type": "table", ...}]}
                if "content" in parsed and isinstance(parsed["content"], list):
                    for item in parsed["content"]:
                        if isinstance(item, dict):
                            if item.get("type") == "text" and item.get("text"):
                                for line in item["text"].strip().splitlines():
                                    print(f"       {line}")
                            elif "table" in item or item.get("type") == "table":
                                tbl = item.get("table") or item
                                rs = tbl.get("result_set", {})
                                meta = rs.get("resultSetMetaData", {})
                                cols = [c.get("name") for c in meta.get("rowType", [])]
                                rows = rs.get("data", [])
                                if cols:
                                    print(f"       [Table Columns]: {cols}")
                                if rows:
                                    print(f"       [Table Rows] ({len(rows)} returned):")
                                    for r in rows:
                                        print(f"         {r}")
                    return

                # Direct result_set format from sql_query_executor
                if "result_set" in parsed:
                    meta = parsed["result_set"].get("resultSetMetaData", {})
                    cols = [c.get("name") for c in meta.get("rowType", [])]
                    rows = parsed["result_set"].get("data", [])
                    print(f"       Columns ({len(cols)}): {cols}")
                    print(f"       Rows ({len(rows)} returned):")
                    for r in rows:
                        print(f"         {r}")
                    return
        except Exception:
            pass

        for line in raw_text.splitlines():
            print(f"       {line}")
        return

    # Fallback to plain string if structured
    print(f"       {content}")


async def run_trace(message_id: str) -> None:
    t_start = time.time()
    print("*" * 80)
    print(f"  AGENT END-TO-END EXECUTION TRACE")
    print(f"  Target Email: {message_id}")
    print("*" * 80)

    # -------------------------------------------------------------
    # STEP 1: Email Retrieval from Neon DB
    # -------------------------------------------------------------
    _banner("EMAIL INGESTION & CONTENT RETRIEVAL", 1)
    session = get_session_factory()()
    row = session.query(EmailProcessing).filter_by(message_id=message_id).first()
    if not row:
        print(f"[ERROR] Email {message_id} not found in database.")
        return

    print(f"Database Table : email_processing (PostgreSQL / Neon)")
    print(f"Message ID     : {row.message_id}")
    print(f"Sender         : {row.sender_email} ({row.name})")
    print(f"Subject        : {row.subject}")
    print(f"Ingested Time  : {row.ingestion_time}")
    _subheading("Raw Email Body")
    print(row.content)

    query = f"Subject: {row.subject}\n\n{row.content}".strip()

    # -------------------------------------------------------------
    # Initialize Foundry LLM and Snowflake MCP Tools
    # -------------------------------------------------------------
    print("\n[INIT] Initializing Azure Foundry LLM connection & Snowflake MCP runtime...")
    clear_qa_tools_cache()
    tools = get_qa_tools(force_reload=True)
    model = build_chat_model(disable_streaming=True)
    drafter_model = build_chat_model(disable_streaming=False)
    print(f"  • Azure Foundry Endpoint : {os.getenv('AZURE_AI_FOUNDRY_PROJECT_ENDPOINT', 'configured')}")
    print(f"  • Model Deployment       : {os.getenv('AZURE_AI_FOUNDRY_DEPLOYMENT', 'configured')}")
    print(f"  • Snowflake MCP Tools    : {[t.name for t in tools]}")

    # -------------------------------------------------------------
    # STEP 2: Classifier Node (Foundry LLM)
    # -------------------------------------------------------------
    _banner("CLASSIFIER AGENT (Foundry Responses API)", 2)
    print("Model invoked with structured output schema (ClassificationResult).")
    classifier_llm = with_structured(model, ClassificationResult)
    classifier_node = make_classifier_node(classifier_llm)

    t0 = time.time()
    c_res = await classifier_node({"query": query})
    c_elapsed = time.time() - t0
    triage = c_res.get("triage", {})

    print(f"Completed in {c_elapsed:.2f}s")
    _subheading("Classifier Extracts & Decision")
    print(f"  • Triaged Category : {triage.get('category', 'unknown').upper()}")
    print(f"  • Confidence       : {triage.get('confidence', 'N/A')}")
    print(f"  • Intent           : {triage.get('intent', 'N/A')}")
    print(f"  • Client ID        : {triage.get('client_id')}")
    print(f"  • Employee ID      : {triage.get('employee_id')}")
    print(f"  • Employee Name    : {triage.get('employee_name')}")
    print(f"  • Pay Period       : {triage.get('pay_period')}")

    # -------------------------------------------------------------
    # STEP 3: Validation Agent Node (Foundry LLM + Snowflake MCP)
    # -------------------------------------------------------------
    _banner("IDENTITY VALIDATION AGENT (Foundry LLM -> Snowflake MCP)", 3)
    val_model = with_structured(model, ValidationResult)
    val_node = make_validation_node(model, val_model, tools)

    category = triage.get("category", "qa")
    prompt = (
        f"Category: {category}\n"
        f"client_id: {triage.get('client_id')}\n"
        f"employee_id: {triage.get('employee_id')}\n"
        f"employee_name: {triage.get('employee_name')}\n"
        f"Inquiry:\n{query}\n\n"
        "Use sv_hr_workforce first to confirm this client_id and employee_id exist "
        "(return employee_id, client_id, full_name, status_class). "
        "Call sql_query_executor with the Analyst SQL. If Analyst errors or is unavailable, "
        "immediately call sql_query_executor directly with a SELECT query on "
        "PAYROLL_DB.PAYROLL_SCHEMA.SV_HR_WORKFORCE to confirm the client and employee exist. "
        "Identity validation does not require payroll history rows."
    )
    _subheading("Validation Agent Prompt (Sent to Foundry)")
    print(prompt)

    # We run the inner agent directly to capture every tool call & result
    v_agent = create_agent(model, tools=tools, system_prompt=VALIDATION_INSTRUCTIONS)
    t0 = time.time()
    v_run = await v_agent.ainvoke({"messages": [HumanMessage(content=prompt)]})
    v_elapsed = time.time() - t0

    _subheading(f"Validation Agent MCP Tool Trace ({v_elapsed:.2f}s)")
    v_msgs = v_run.get("messages", [])
    for msg in v_msgs:
        m_type = type(msg).__name__
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  -> [TOOL CALL] {tc.get('name')} with args:")
                for k, v in (tc.get("args") or {}).items():
                    print(f"       {k}: {v}")
        elif m_type == "ToolMessage":
            name = getattr(msg, "name", "tool")
            _print_tool_result(name, msg.content)

    # Structured evaluation
    v_final = await val_model.ainvoke([SystemMessage(content=VALIDATION_INSTRUCTIONS), *v_msgs])
    v_result = v_final.model_dump() if hasattr(v_final, "model_dump") else dict(v_final)
    _subheading("Final Structured Validation Decision")
    print(f"  • Validation Status : {v_result.get('status', 'unknown').upper()}")
    print(f"  • Client Verified   : {v_result.get('client_ok')}")
    print(f"  • Employee Verified : {v_result.get('employee_ok')}")
    print(f"  • Missing Fields    : {v_result.get('missing')}")
    print(f"  • Validation Notes  : {v_result.get('notes')}")

    # -------------------------------------------------------------
    # STEP 4: Conditional Graph Routing
    # -------------------------------------------------------------
    _banner("LANGGRAPH CONDITIONAL ROUTING", 4)
    v_status = str(v_result.get("status", "")).lower()
    if v_status in ("needs_clarification", "invalid"):
        next_node = "drafting_specialist (clarification mode)"
    elif category == "qa":
        next_node = "qa_specialist"
    elif category == "changelist":
        next_node = "changelist_agent"
    else:
        next_node = "routing_agent"

    print(f"Evaluation Rule : Category='{category}' AND Validation='{v_status}'")
    print(f"Routing Decision: Route to ==> [{next_node.upper()}]")

    # -------------------------------------------------------------
    # STEP 5: Specialist Node (QA Specialist + Snowflake MCP)
    # -------------------------------------------------------------
    _banner("SPECIALIST AGENT (QA Calculations via Snowflake MCP)", 5)
    qa_prompt = (
        f"Client ID: {triage.get('client_id')}\n"
        f"Employee ID: {triage.get('employee_id')}\n"
        f"Pay period: {triage.get('pay_period')}\n"
        f"Inquiry: {query}\n\n"
        "Use sv_employee_payroll (or workforce/benefits as needed). "
        "Call one Analyst tool, then sql_query_executor with that SQL. "
        "If Analyst errors or is unavailable, immediately call sql_query_executor directly with a SELECT query on "
        "PAYROLL_DB.PAYROLL_SCHEMA.SV_EMPLOYEE_PAYROLL, SV_HR_WORKFORCE, or SV_EMPLOYEE_BENEFITS. "
        "Compare gross/regular/OT/deductions from executed rows. Never invent figures."
    )

    qa_agent = create_agent(model, tools=tools, system_prompt=QA_INSTRUCTIONS)
    t0 = time.time()
    qa_run = await qa_agent.ainvoke({"messages": [HumanMessage(content=qa_prompt)]})
    qa_elapsed = time.time() - t0

    _subheading(f"QA Specialist MCP Tool Trace ({qa_elapsed:.2f}s)")
    qa_msgs = qa_run.get("messages", [])
    for msg in qa_msgs:
        m_type = type(msg).__name__
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  -> [TOOL CALL] {tc.get('name')} with args:")
                for k, v in (tc.get("args") or {}).items():
                    print(f"       {k}: {v}")
        elif m_type == "ToolMessage":
            name = getattr(msg, "name", "tool")
            _print_tool_result(name, msg.content)

    qa_findings_raw = ""
    for m in reversed(qa_msgs):
        if getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None):
            qa_findings_raw = m.content
            break

    qa_findings = extract_message_text(qa_findings_raw)

    _subheading("QA Findings Reconciled from Snowflake")
    print(qa_findings.strip() if qa_findings else "[No findings text generated]")

    # -------------------------------------------------------------
    # STEP 6: Drafting Specialist Node (Foundry LLM)
    # -------------------------------------------------------------
    _banner("DRAFTING SPECIALIST AGENT (Foundry Communication LLM)", 6)
    emp_id = triage.get("employee_id") or "General"
    period = triage.get("pay_period") or "not specified"
    header_instruction = (
        "IMPORTANT FORMATTING INSTRUCTION: You MUST start your response immediately with these two lines:\n"
        f"**Triaged Category:** {category.upper()}\n"
        f"**Employee ID:** {emp_id}\n\n"
    )
    draft_prompt = (
        f"{header_instruction}"
        f"Original Employee Inquiry:\n{query}\n\n"
        f"Category: QA\n"
        f"Employee ID: {emp_id}\n"
        f"Pay period: {period}\n\n"
        f"Snowflake / MCP findings:\n{qa_findings}\n\n"
        "Draft a professional payroll specialist email with an itemized deduction table only if those "
        "figures appear in the findings. Do not invent numbers."
    )

    t0 = time.time()
    draft_res = await drafter_model.ainvoke([
        SystemMessage(content=DRAFTER_INSTRUCTIONS),
        HumanMessage(content=draft_prompt),
    ])
    draft_elapsed = time.time() - t0
    final_draft = extract_message_text(draft_res.content)

    print(f"Completed in {draft_elapsed:.2f}s")
    _subheading("Final Generated Executive Email Draft")
    print(final_draft.strip() if final_draft else "[No draft content returned]")

    # -------------------------------------------------------------
    # STEP 7: Neon DB Persistence Verification
    # -------------------------------------------------------------
    _banner("NEON DB PERSISTENCE & AUDIT STATE", 7)
    refreshed_row = session.query(EmailProcessing).filter_by(message_id=message_id).first()
    print(f"Database Record State for {message_id}:")
    print(f"  • Category        : {refreshed_row.category}")
    print(f"  • Priority        : {refreshed_row.priority_rate}")
    print(f"  • HITL Status     : {refreshed_row.hitl_status} (pending = awaiting human specialist review)")
    print(f"  • Ingested Time   : {refreshed_row.ingestion_time}")
    print(f"  • Categorized At  : {refreshed_row.mail_categorization_time}")
    print(f"  • Drafted At      : {refreshed_row.mail_draft_time}")
    print(f"  • QA Response     : {'[SAVED]' if refreshed_row.qa_response else '[NULL]'}")
    print(f"  • Draft Content   : {'[SAVED]' if refreshed_row.draft_content else '[NULL]'}")

    t_total = time.time() - t_start
    print("\n" + "=" * 80)
    print(f"  TRACE COMPLETED SUCCESSFULLY IN {t_total:.2f}s")
    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace agent execution from Azure Foundry to Snowflake")
    parser.add_argument(
        "--message-id",
        default="MSG-SF-009-QA-NETPAY",
        help="Email message_id to trace (default: MSG-SF-009-QA-NETPAY)",
    )
    args = parser.parse_args()
    asyncio.run(run_trace(args.message_id))


if __name__ == "__main__":
    main()

