"""Smoke-test Microsoft Graph mailbox wiring (no secrets printed)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "payroll_specialist"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from triage.auth import graph_auth_mode, load_graph_auth
from triage.mailbox import get_mailbox_port


def main() -> int:
    print("GRAPH_AUTH_MODE=", graph_auth_mode())
    auth = load_graph_auth()
    if auth is None:
        print("load_graph_auth=None (missing tenant/client or app secret)")
        return 1
    allow = ",".join(auth.allowlist) if auth.allowlist else "none"
    print(
        f"load_graph_auth=mode={auth.mode} "
        f"tenant_set={bool(auth.tenant_id)} client_set={bool(auth.client_id)} "
        f"secret_set={bool(auth.client_secret)} allowlist={allow}"
    )

    port = get_mailbox_port()
    print("mailbox_port=", type(port).__name__)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    try:
        msgs = port.list_messages(
            "me",
            window_start=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            window_end=end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        print("list_messages OK count=", len(msgs))
        for msg in msgs[:5]:
            subj = (msg.subject or "")[:80]
            print(f" - {msg.received_at} | {subj}")
        return 0
    except Exception as exc:
        print("list_messages without bearer:", type(exc).__name__ + ":", str(exc)[:500])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
