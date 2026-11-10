"""Process ingested emails from Neon DB through the full LangGraph agent pipeline.

Usage (from repo root):
  # Process the next 5 unclassified emails:
  .\\.venv\\Scripts\\python.exe scripts\\process_neon_emails.py --limit 5

  # Process a single email by ID:
  .\\.venv\\Scripts\\python.exe scripts\\process_neon_emails.py --message-id MSG-0001-QA-PAYCHECK

  # Re-process specific emails (comma-separated):
  .\\.venv\\Scripts\\python.exe scripts\\process_neon_emails.py --message-id MSG-0001-QA-PAYCHECK,MSG-0002-QA-DEDUCTION,MSG-0003-QA-OVERTIME,MSG-0004-QA-BONUS,MSG-0005-QA-RETRO

  # Dry run (preview results without updating Neon DB):
  .\\.venv\\Scripts\\python.exe scripts\\process_neon_emails.py --limit 5 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
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

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.pop("PAYROLL_MCP_OFFLINE", None)

logging.basicConfig(level=logging.INFO, format="%(message)s")
for name in ("azure", "azure.core", "azure.identity", "httpx", "httpx2", "openai", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)

from changelists_mapping import merge_changelist_payload
from db.repository import EmailData, get_email_repository
from graph import build_chat_model
from models import ChangelistBuildResult, ClassificationResult, ValidationResult
from structured_output import with_structured
from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools
from triage.email_graph import build_email_processing_graph, run_email_graph


def build_pipeline():
    """Compile the multi-agent graph with live LLM and Snowflake MCP tools."""
    print("Initializing LLM and Snowflake MCP tools...")
    clear_qa_tools_cache()
    tools = get_qa_tools(force_reload=True)
    tool_names = [t.name for t in tools]
    print(f"[OK] Loaded {len(tools)} Snowflake tool(s): {tool_names}")

    classifier_model = build_chat_model(disable_streaming=True)
    qa_model = build_chat_model(disable_streaming=True)
    drafter_model = build_chat_model(disable_streaming=False)
    routing_model = build_chat_model(disable_streaming=True)
    qa_tools = tools

    email_graph = build_email_processing_graph(
        classifier_llm=with_structured(classifier_model, ClassificationResult),
        qa_llm=qa_model.bind_tools(qa_tools) if qa_tools else qa_model,
        qa_model=qa_model,
        qa_tools=qa_tools,
        drafter_model=drafter_model,
        routing_model=routing_model,
        validation_llm=qa_model.bind_tools(qa_tools) if qa_tools else qa_model,
        validation_model=with_structured(qa_model, ValidationResult),
        changelist_llm=qa_model.bind_tools(qa_tools) if qa_tools else qa_model,
        changelist_model=with_structured(qa_model, ChangelistBuildResult),
    )
    return email_graph


async def process_single_email(
    graph: Any,
    email: EmailData,
    repo: Any,
    dry_run: bool = False,
) -> dict[str, Any]:
    print("\n" + "=" * 70)
    print(f"PROCESSING: {email.email_id}")
    print(f"From:    {email.sender}")
    print(f"Subject: {email.subject}")
    print("-" * 70)

    query = f"Subject: {email.subject}\n\n{email.body}".strip()
    print("Running multi-agent email graph (Classifier -> Validation -> QA/CL/Route -> Drafter)...")
    out = await run_email_graph(graph, query)

    triage = out.get("triage") or {}
    validation = out.get("validation") or {}
    changelist = out.get("changelist") or {}
    draft = out.get("draft") or ""
    qa_findings = out.get("qa_findings")

    category = triage.get("category") or "todo"
    cl_dict = changelist if isinstance(changelist, dict) else {}
    priority = str(cl_dict.get("priority_rate") or "medium")

    print("\n--- AGENT RESULTS ---")
    print(f"Category:   {category} (confidence: {triage.get('confidence', 'N/A')})")
    print(f"Priority:   {priority}")
    print(f"Intent:     {triage.get('intent', 'N/A')}")
    print(f"Validation: {validation.get('status', 'N/A')}")
    if qa_findings:
        print(f"QA Findings:\n{qa_findings}")
    if cl_dict.get("changes"):
        print(f"Changelist changes ({len(cl_dict['changes'])}): {json.dumps(cl_dict['changes'], indent=2)}")
    if draft:
        print(f"\nGenerated Draft Preview:\n{draft[:350]}...\n")

    if dry_run:
        print("[DRY-RUN] Skipping database updates.")
        return out

    # Persist to Neon DB
    print("Persisting results to Neon DB (email_processing table)...")
    repo.save_classification(
        email_id=email.email_id,
        categories=[category],
        priority=priority,
    )

    extracts = {
        k: triage.get(k)
        for k in (
            "employee_id",
            "client_id",
            "employee_name",
            "effective_date",
            "pay_period",
            "oos_destination",
            "change_type",
            "new_value",
            "previous_value",
            "system_target",
        )
        if triage.get(k) is not None
    }
    if extracts:
        repo.save_extracts(message_id=email.email_id, extracts=extracts)

    if draft:
        repo.save_draft(email_id=email.email_id, draft_content=draft)

    if str(validation.get("status") or "").lower() in ("needs_clarification", "invalid"):
        repo.set_hitl_status(email.email_id, "needs_clarification")
    else:
        repo.set_hitl_status(email.email_id, "pending")

    if category == "changelist":
        if isinstance(changelist, dict) and (changelist.get("changes") or changelist.get("lines")):
            shell = dict(changelist)
            if not shell.get("title"):
                shell["title"] = email.subject or "(no subject)"
            if not shell.get("clientId"):
                shell["clientId"] = triage.get("client_id") or "unknown"
        else:
            shell = {
                "clientId": triage.get("client_id") or "unknown",
                "title": email.subject or "(no subject)",
                "lines": [],
                "status": "pending",
            }
            if isinstance(changelist, dict):
                shell = {**shell, **{k: v for k, v in changelist.items() if v is not None}}
        existing = repo.get_changelist_response(email.email_id)
        repo.save_changelist_response(email.email_id, merge_changelist_payload(existing, shell))

    if qa_findings:
        repo.save_qa_response(email.email_id, {"findings": qa_findings})

    print(f"[OK] Successfully processed and updated {email.email_id} in Neon DB.")
    return out


async def main_async():
    parser = argparse.ArgumentParser(description="Process Neon DB ingested emails through the multi-agent pipeline")
    parser.add_argument("--message-id", help="Process specific message_id(s) (comma-separated, e.g. MSG-0001,MSG-0002)")
    parser.add_argument("--limit", type=int, default=5, help="Number of unclassified emails to process (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Run without persisting changes to DB")
    args = parser.parse_args()

    repo = get_email_repository()

    emails: list[EmailData] = []
    if args.message_id:
        mids = [m.strip() for m in args.message_id.split(",") if m.strip()]
        for mid in mids:
            try:
                emails.append(repo.get_email(mid))
            except Exception as e:
                print(f"[WARN] Could not load message '{mid}': {e}")
        if not emails:
            print("[ERROR] No valid emails found to process.")
            return
    else:
        emails = repo.get_unclassified_emails(limit=args.limit)
        if not emails:
            print("No unclassified emails found in Neon DB.")
            return

    print(f"Found {len(emails)} email(s) to process:")
    for e in emails:
        print(f"  • {e.email_id}: {e.subject}")

    graph = build_pipeline()

    success_count = 0
    for idx, email in enumerate(emails, start=1):
        print(f"\n[{idx}/{len(emails)}] Processing...")
        try:
            await process_single_email(graph, email, repo, dry_run=args.dry_run)
            success_count += 1
        except Exception as exc:
            print(f"[ERROR] Failed processing {email.email_id}: {exc}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"DONE: Successfully processed {success_count}/{len(emails)} email(s).")
    print("=" * 70)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
