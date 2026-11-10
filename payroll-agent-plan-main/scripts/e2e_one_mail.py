"""One-mail E2E: fixture email → live email graph (LLM+MCP) → Neon persist.

Skips Outlook/Graph fetch (uses MockGraphMailbox). UI triage still needs real inbox mail.

Usage (repo root):
  .\\.venv\\Scripts\\python.exe scripts\\e2e_one_mail.py
  .\\.venv\\Scripts\\python.exe scripts\\e2e_one_mail.py --email-id e2e-01
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.pop("PAYROLL_MCP_OFFLINE", None)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email-id", default="e2e-03", help="Fixture id from e2e_triage_emails.json")
    args = parser.parse_args()

    fixtures = json.loads((ROOT / "fixtures" / "e2e_triage_emails.json").read_text(encoding="utf-8"))
    mailbox = fixtures["mailbox"]
    email = next((e for e in fixtures["emails"] if e["id"] == args.email_id), None)
    if email is None:
        raise SystemExit(f"Unknown email id: {args.email_id}")

    message_id = f"e2e-seed-{email['id']}"
    print("=== E2E one-mail ===")
    print(f"fixture={email['id']} expected={email['expected_category']} message_id={message_id}")
    print(f"mailbox={mailbox}")
    print(f"subject={email['subject'].encode('ascii', 'replace').decode('ascii')}")
    print("---")

    # 1) Clean Neon row for this message only
    from sqlalchemy import create_engine, text

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url)
    with engine.begin() as conn:
        deleted = conn.execute(
            text("DELETE FROM email_processing WHERE message_id = :mid"),
            {"mid": message_id},
        ).rowcount
    print(f"Neon deleted rows for {message_id}: {deleted}")

    # 2) Clear local processed marker
    from store.local_store import LocalTriageStore
    from triage.mailbox import MailMessage, MockGraphMailbox
    from triage.orchestrator import TriageOrchestrator
    from triage.processed import LocalProcessedMailStore

    store_root = ROOT / ".local_store" / "e2e_one_mail"
    store_root.mkdir(parents=True, exist_ok=True)
    # Wipe before constructing the store (constructor loads IDs into memory).
    for p in (store_root / "processed").rglob("*"):
        if p.is_file():
            p.unlink()
    processed = LocalProcessedMailStore(store_root / "processed", specialist_id="e2e-specialist")

    store = LocalTriageStore(str(store_root / "triage"))
    store.save_specialist_config(
        "e2e-specialist",
        {
            "mailbox_id": mailbox,
            "lookback_days": 30,
            "mode": "manual",
            "interval_hours": 4,
        },
    )

    msg = MailMessage(
        id=message_id,
        received_at=_utc_now_iso(),
        from_address=email["from"],
        subject=email["subject"],
        body=email["body"],
        body_preview=email["body"][:180],
        conversation_id=f"conv-{email['id']}",
        is_read=False,
    )
    mailbox_port = MockGraphMailbox([msg])

    # 3) Live graph (Foundry LLM + Snowflake MCP)
    print("Building live payroll graph (LLM + MCP)...")
    from graph import build_chat_model
    from models import ChangelistBuildResult, ClassificationResult, ValidationResult
    from structured_output import with_structured
    from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools
    from triage.email_graph import build_email_processing_graph, run_email_graph

    clear_qa_tools_cache()
    tools = get_qa_tools(force_reload=True)
    print(f"MCP tools: {[t.name for t in tools]}")

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

    async def process_email_fn(query: str) -> dict:
        print("Running email subgraph...")
        out = await run_email_graph(email_graph, query)
        print(
            "subgraph:",
            {
                "category": (out.get("triage") or {}).get("category"),
                "validation": (out.get("validation") or {}).get("status"),
                "snowflake_fetched": (out.get("changelist") or {}).get("snowflake_fetched"),
                "changes": len((out.get("changelist") or {}).get("changes") or []),
                "has_draft": bool(out.get("draft")),
                "qa_snowflake": "qa_findings" in out and bool(out.get("qa_findings")),
            },
        )
        return out

    from db.repository import get_email_repository

    orch = TriageOrchestrator(
        store=store,
        mailbox=mailbox_port,
        process_email_fn=process_email_fn,
        processed_store=processed,
        email_repo=get_email_repository(),
    )

    import asyncio

    print("Running triage orchestrator...")
    result = asyncio.run(orch.run(specialist_id="e2e-specialist", mailbox_id=mailbox))
    print(json.dumps(result.get("email_results"), indent=2, default=str))

    # 4) Read back from Neon
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT message_id, category, priority_rate, is_categorized, is_drafted, "
                "hitl_status, left(draft_content, 200) AS draft_preview, "
                "left(changelist_response, 500) AS cl_preview "
                "FROM email_processing WHERE message_id = :mid"
            ),
            {"mid": message_id},
        ).mappings().first()
    print("--- Neon row ---")
    print(json.dumps(dict(row) if row else {"error": "not found"}, indent=2, default=str))
    print("--- done ---")


if __name__ == "__main__":
    main()
