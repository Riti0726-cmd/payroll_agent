"""Wipe Neon rows for previously injected Outlook sample mails, then re-triage.

Uses Graph message IDs from fixtures/e2e_outlook_inject_result.json.
Forces a lookback window (ignores last successful run) so inbox mails are re-fetched.

Usage (repo root)::

  .\\.venv\\Scripts\\python.exe scripts\\rerun_injected_outlook.py
  .\\.venv\\Scripts\\python.exe scripts\\rerun_injected_outlook.py --lookback-days 60
  .\\.venv\\Scripts\\python.exe scripts\\rerun_injected_outlook.py --dry-wipe
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "payroll_specialist"
sys.path.insert(0, str(PKG))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
os.environ.pop("PAYROLL_MCP_OFFLINE", None)


def _prefer_local_nodejs() -> None:
    """Put a usable Node ahead of broken cross-user PATH entries (Windows)."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "nodejs" / "node-v24.19.0-win-x64",
        Path(r"C:\Users\HarshdeepBhatia\AppData\Local\nodejs\node-v24.19.0-win-x64"),
    ]
    # Prefer any LocalAppData\nodejs\*\node.exe
    local_nodejs = Path(os.environ.get("LOCALAPPDATA", "")) / "nodejs"
    if local_nodejs.is_dir():
        for child in sorted(local_nodejs.glob("node-v*"), reverse=True):
            candidates.insert(0, child)

    chosen = next((p for p in candidates if (p / "node.exe").is_file()), None)
    if chosen is None:
        return
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    cleaned = [p for p in parts if "RaghavMehta" not in p and p.rstrip("\\/") != str(chosen)]
    os.environ["PATH"] = os.pathsep.join([str(chosen), *cleaned])
    print(f"PATH: prefer Node at {chosen}")


_prefer_local_nodejs()

INJECT_RESULT = ROOT / "fixtures" / "e2e_outlook_inject_result.json"


def _device_code_token(tenant: str, client_id: str) -> str:
    """Interactive device login for Mail.Read (same pattern as inject_e2e_outlook)."""
    import time

    import httpx

    scope = "https://graph.microsoft.com/Mail.Read offline_access openid profile"
    with httpx.Client(timeout=30.0) as client:
        start = client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
            data={"client_id": client_id, "scope": scope},
        )
        start.raise_for_status()
        payload = start.json()
        print(payload.get("message") or payload, flush=True)
        print(
            f"VERIFICATION_URI={payload.get('verification_uri')} "
            f"USER_CODE={payload.get('user_code')}",
            flush=True,
        )
        interval = int(payload.get("interval") or 5)
        device_code = payload["device_code"]
        deadline = time.time() + int(payload.get("expires_in") or 900)
        while time.time() < deadline:
            time.sleep(interval)
            token_resp = client.post(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": client_id,
                    "device_code": device_code,
                },
            )
            body = token_resp.json()
            if token_resp.status_code == 200 and body.get("access_token"):
                print("Device login OK", flush=True)
                return str(body["access_token"])
            err = body.get("error")
            if err in ("authorization_pending", "slow_down"):
                if err == "slow_down":
                    interval += 2
                print(".", end="", flush=True)
                continue
            raise RuntimeError(f"Device code failed: {body}")
        raise RuntimeError("Device code timed out waiting for login")


def _resolve_graph_token(*, device_code: bool, explicit: str | None) -> str | None:
    if explicit:
        return explicit.strip()
    env_tok = (os.environ.get("GRAPH_ACCESS_TOKEN") or "").strip()
    if env_tok:
        return env_tok
    if not device_code:
        return None
    tenant = (os.environ.get("GRAPH_TENANT_ID") or "").strip()
    client_id = (os.environ.get("GRAPH_CLIENT_ID") or "").strip()
    if not (tenant and client_id):
        raise SystemExit("Device code needs GRAPH_TENANT_ID + GRAPH_CLIENT_ID")
    return _device_code_token(tenant, client_id)


class _ForceLookbackStore:
    """Delegate triage store but always treat this as a first run (lookback window)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def get_last_successful_run(self, specialist_id: str) -> dict | None:
        _ = specialist_id
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class _InjectedOnlyMailbox:
    """Real Graph fetch, then keep only previously injected sample message IDs."""

    def __init__(self, inner: Any, allowed_ids: set[str]) -> None:
        self._inner = inner
        self._allowed = allowed_ids

    def list_messages(self, *args: Any, **kwargs: Any) -> list[Any]:
        messages = self._inner.list_messages(*args, **kwargs)
        kept = [m for m in messages if getattr(m, "id", None) in self._allowed]
        print(
            f"Graph returned {len(messages)} in window; "
            f"keeping {len(kept)} injected samples"
        )
        return kept

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _graph_ids() -> tuple[str, list[str]]:
    data = json.loads(INJECT_RESULT.read_text(encoding="utf-8"))
    mailbox = str(data.get("mailbox") or "payroll@peoservices.com")
    ids = [
        str(r["graph_id"])
        for r in (data.get("results") or [])
        if r.get("ok") and r.get("graph_id")
    ]
    return mailbox, ids


def wipe_neon(message_ids: list[str], *, dry: bool) -> int:
    from sqlalchemy import bindparam, create_engine, text

    db_url = (os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or "").strip()
    if not db_url:
        raise SystemExit("DATABASE_URL is required")
    if not message_ids:
        print("No Graph IDs to wipe")
        return 0
    engine = create_engine(db_url)
    select_stmt = text(
        "SELECT message_id, category, is_processed FROM email_processing "
        "WHERE message_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    delete_stmt = text(
        "DELETE FROM email_processing WHERE message_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))

    if dry:
        with engine.connect() as conn:
            rows = conn.execute(select_stmt, {"ids": message_ids}).mappings().all()
        print(f"dry-wipe: {len(rows)} matching Neon rows")
        for row in rows:
            print(
                f"  {row['message_id'][:40]}... "
                f"cat={row['category']} processed={row['is_processed']}"
            )
        return len(rows)

    with engine.begin() as conn:
        deleted = int(conn.execute(delete_stmt, {"ids": message_ids}).rowcount or 0)
    print(f"Neon deleted {deleted} rows for {len(message_ids)} injected Graph IDs")
    return deleted


def build_orchestrator(
    lookback_days: int,
    mailbox: str,
    specialist_id: str,
    *,
    allowed_ids: set[str] | None,
):
    from graph import build_chat_model
    from models import ChangelistBuildResult, ClassificationResult, ValidationResult
    from store import get_triage_store
    from structured_output import with_structured
    from tools.snowflake_mcp import clear_qa_tools_cache, get_qa_tools
    from triage.email_graph import build_email_processing_graph, run_email_graph
    from triage.mailbox import get_mailbox_port
    from triage.orchestrator import TriageOrchestrator
    from triage.processed import get_processed_mail_port

    store = _ForceLookbackStore(get_triage_store())
    cfg = store.get_specialist_config(specialist_id)
    store.save_specialist_config(
        specialist_id,
        {
            **cfg,
            "mailbox_id": mailbox,
            "lookback_days": lookback_days,
            "mode": "manual",
        },
    )

    clear_qa_tools_cache()
    tools = get_qa_tools(force_reload=True)
    print(f"MCP tools: {[t.name for t in tools]}")

    classifier_model = build_chat_model(disable_streaming=True)
    qa_model = build_chat_model(disable_streaming=True)
    drafter_model = build_chat_model(disable_streaming=False)
    routing_model = build_chat_model(disable_streaming=True)

    email_graph = build_email_processing_graph(
        classifier_llm=with_structured(classifier_model, ClassificationResult),
        qa_llm=qa_model.bind_tools(tools) if tools else qa_model,
        qa_model=qa_model,
        qa_tools=tools,
        drafter_model=drafter_model,
        routing_model=routing_model,
        validation_llm=qa_model.bind_tools(tools) if tools else qa_model,
        validation_model=with_structured(qa_model, ValidationResult),
        changelist_llm=qa_model.bind_tools(tools) if tools else qa_model,
        changelist_model=with_structured(qa_model, ChangelistBuildResult),
    )

    async def process_email_fn(query: str) -> dict:
        return await run_email_graph(email_graph, query)

    mailbox_port: Any = get_mailbox_port()
    if allowed_ids is not None:
        mailbox_port = _InjectedOnlyMailbox(mailbox_port, allowed_ids)

    return TriageOrchestrator(
        store=store,
        mailbox=mailbox_port,
        process_email_fn=process_email_fn,
        processed_store=get_processed_mail_port(specialist_id=specialist_id),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--specialist-id", default="default")
    parser.add_argument("--lookback-days", type=int, default=60)
    parser.add_argument("--dry-wipe", action="store_true", help="List matching Neon rows only")
    parser.add_argument("--wipe-only", action="store_true", help="Wipe Neon; do not run triage")
    parser.add_argument(
        "--all-inbox",
        action="store_true",
        help="Process every unprocessed message in the window (default: injected samples only)",
    )
    parser.add_argument("--device-code", action="store_true", help="Interactive Graph login")
    parser.add_argument("--token", default=None, help="Delegated Graph Bearer token")
    args = parser.parse_args()

    mailbox, ids = _graph_ids()
    print("=== Rerun injected Outlook samples ===")
    print(f"mailbox={mailbox} injected={len(ids)} lookback_days={args.lookback_days}")
    wipe_neon(ids, dry=args.dry_wipe)
    if args.dry_wipe or args.wipe_only:
        print("--- done (no triage) ---")
        return

    token = _resolve_graph_token(device_code=args.device_code, explicit=args.token)
    if token:
        from triage.request_context import set_graph_access_token

        set_graph_access_token(token)
        print("Graph delegated token ready")
    elif (os.environ.get("GRAPH_AUTH_MODE") or "delegated").strip().lower() != "app":
        raise SystemExit(
            "Delegated Graph needs a token. Re-run with --device-code "
            "(sign in as payroll@peoservices.com) or --token / GRAPH_ACCESS_TOKEN."
        )

    print("Building live triage orchestrator (Graph + LLM + MCP)...")
    orch = build_orchestrator(
        args.lookback_days,
        mailbox,
        args.specialist_id,
        allowed_ids=None if args.all_inbox else set(ids),
    )

    def on_progress(event: dict[str, Any]) -> None:
        et = event.get("type")
        if et in ("run_started", "email_finished", "run_finished", "error"):
            print(json.dumps(event, default=str))

    print("Running triage...")
    result = asyncio.run(
        orch.run(
            specialist_id=args.specialist_id,
            mailbox_id=mailbox,
            on_progress=on_progress,
        )
    )
    email_results = result.get("email_results") or []
    print("--- summary ---")
    print(
        json.dumps(
            {
                "run_id": result.get("run_id"),
                "window": result.get("processing_window"),
                "total": len(email_results),
                "succeeded": sum(1 for r in email_results if r.get("status") == "succeeded"),
                "skipped": sum(1 for r in email_results if r.get("status") == "skipped"),
                "failed": sum(1 for r in email_results if r.get("status") == "failed"),
            },
            indent=2,
            default=str,
        )
    )
    matched = [r for r in email_results if r.get("message_id") in set(ids)]
    print(f"injected-mail outcomes in this run: {len(matched)}/{len(ids)}")
    for row in matched:
        print(
            f"  {row.get('status')} cat={row.get('category')} "
            f"id={str(row.get('message_id'))[:48]}..."
        )
    print("--- done ---")


if __name__ == "__main__":
    main()
