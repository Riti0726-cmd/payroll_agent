"""Inject fixture emails into an Outlook mailbox via Microsoft Graph.

Creates messages under Inbox (for triage to pick up). Auth options (first match wins):

1) ``GRAPH_ACCESS_TOKEN`` / ``--token`` — delegated Bearer with Mail.ReadWrite
2) ``GRAPH_AUTH_MODE=app`` + ``GRAPH_CLIENT_SECRET`` — app-only Mail.ReadWrite
3) ``--device-code`` — interactive device login requesting Mail.ReadWrite

Usage (repo root)::

  .\\.venv\\Scripts\\python.exe scripts\\inject_e2e_outlook.py
  .\\.venv\\Scripts\\python.exe scripts\\inject_e2e_outlook.py --limit 4
  .\\.venv\\Scripts\\python.exe scripts\\inject_e2e_outlook.py --email-id e2e-01
  .\\.venv\\Scripts\\python.exe scripts\\inject_e2e_outlook.py --device-code

Then sign into the workbench as the mailbox user and Run triage.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Ensure device-code prompts show immediately in CI/agent terminals.
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None

GRAPH = "https://graph.microsoft.com/v1.0"
FIXTURES = ROOT / "fixtures" / "e2e_triage_emails.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _app_token(tenant: str, client_id: str, secret: str) -> str:
    url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": client_id,
        "client_secret": secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, data=data)
        resp.raise_for_status()
        return str(resp.json()["access_token"])


def _device_code_token(tenant: str, client_id: str) -> str:
    """Public-client device code flow for Mail.ReadWrite (no secret)."""
    scope = "https://graph.microsoft.com/Mail.ReadWrite offline_access openid profile"
    with httpx.Client(timeout=30.0) as client:
        start = client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode",
            data={"client_id": client_id, "scope": scope},
        )
        start.raise_for_status()
        payload = start.json()
        msg = payload.get("message") or (
            f"Open {payload.get('verification_uri')} and enter code {payload.get('user_code')}"
        )
        print(msg, flush=True)
        print(
            f"VERIFICATION_URI={payload.get('verification_uri')} "
            f"USER_CODE={payload.get('user_code')}",
            flush=True,
        )
        interval = int(payload.get("interval") or 5)
        device_code = payload["device_code"]
        import time

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


def resolve_token(*, device_code: bool, explicit: str | None) -> tuple[str, str]:
    """Return (token, auth_mode_label)."""
    if explicit:
        return explicit.strip(), "cli-token"
    env_tok = (os.environ.get("GRAPH_ACCESS_TOKEN") or "").strip()
    if env_tok:
        return env_tok, "env-token"

    tenant = (os.environ.get("GRAPH_TENANT_ID") or "").strip()
    client_id = (os.environ.get("GRAPH_CLIENT_ID") or "").strip()
    secret = (os.environ.get("GRAPH_CLIENT_SECRET") or "").strip()
    mode = (os.environ.get("GRAPH_AUTH_MODE") or "delegated").strip().lower()

    if device_code:
        if not (tenant and client_id):
            raise SystemExit("Device code needs GRAPH_TENANT_ID + GRAPH_CLIENT_ID")
        return _device_code_token(tenant, client_id), "device-code"

    if mode == "app" and tenant and client_id and secret:
        return _app_token(tenant, client_id, secret), "app"

    raise SystemExit(
        "No Graph write token available.\n"
        "Provide one of:\n"
        "  --device-code          (sign in as mailbox user; needs Mail.ReadWrite on app reg)\n"
        "  --token <bearer>      or GRAPH_ACCESS_TOKEN=...\n"
        "  GRAPH_AUTH_MODE=app + GRAPH_CLIENT_SECRET (app Mail.ReadWrite on mailbox)\n"
    )


def mailbox_base(token: str, mailbox: str, auth_label: str) -> str:
    """Choose /me vs /users/{mailbox} depending on token type."""
    if auth_label == "app":
        return f"{GRAPH}/users/{quote(mailbox)}"
    # Delegated: prefer /me so the signed-in specialist's inbox is used.
    # If mailbox differs from signed-in user, try /users/{mailbox} (needs Mail.ReadWrite.Shared).
    return f"{GRAPH}/me"


def create_inbox_message(
    *,
    client: httpx.Client,
    base: str,
    subject: str,
    body: str,
    from_address: str,
    fixture_id: str,
) -> dict:
    # Create under Inbox so triage list_messages can see it.
    url = f"{base}/mailFolders/inbox/messages"
    payload = {
        "subject": subject,
        "body": {"contentType": "Text", "content": body},
        "bodyPreview": body[:180],
        "from": {"emailAddress": {"address": from_address, "name": from_address}},
        "sender": {"emailAddress": {"address": from_address, "name": from_address}},
        "isRead": False,
        "singleValueExtendedProperties": [
            {
                "id": "String {66f5a359-4659-4830-9070-00047ec6ac6e} Name E2eFixtureId",
                "value": fixture_id,
            }
        ],
    }
    # Extended properties often need prior definition; keep create resilient without them.
    bare = {
        "subject": f"[E2E {fixture_id}] {subject}",
        "body": {"contentType": "Text", "content": body},
        "isRead": False,
    }
    resp = client.post(url, json=bare)
    if resp.status_code >= 400:
        raise RuntimeError(f"{resp.status_code} {resp.text[:500]}")
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mailbox", default=None, help="Target mailbox (app mode)")
    parser.add_argument("--email-id", action="append", help="Fixture id (repeatable)")
    parser.add_argument("--limit", type=int, default=0, help="Inject first N fixtures")
    parser.add_argument("--token", default=None, help="Delegated Graph Bearer token")
    parser.add_argument("--device-code", action="store_true", help="Interactive device login")
    args = parser.parse_args()

    fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
    mailbox = args.mailbox or fixtures.get("mailbox") or "payroll@peoservices.com"
    emails = list(fixtures.get("emails") or [])
    if args.email_id:
        wanted = set(args.email_id)
        emails = [e for e in emails if e.get("id") in wanted]
    if args.limit and args.limit > 0:
        emails = emails[: args.limit]
    if not emails:
        raise SystemExit("No fixture emails selected")

    token, auth_label = resolve_token(device_code=args.device_code, explicit=args.token)
    base = mailbox_base(token, mailbox, auth_label)
    print(f"auth={auth_label} mailbox={mailbox} base={base} count={len(emails)}")
    print(f"started={_utc_now_iso()}")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    results: list[dict] = []
    with httpx.Client(timeout=60.0, headers=headers) as client:
        # Who am I?
        me = client.get(f"{GRAPH}/me")
        if me.status_code == 200:
            print("signed_in_as=", me.json().get("mail") or me.json().get("userPrincipalName"))
        elif auth_label == "app":
            print("app token OK (no /me)")
        else:
            print("WARN /me:", me.status_code, me.text[:200])

        for email in emails:
            fid = email["id"]
            try:
                created = create_inbox_message(
                    client=client,
                    base=base,
                    subject=str(email.get("subject") or ""),
                    body=str(email.get("body") or ""),
                    from_address=str(email.get("from") or "noreply@example.com"),
                    fixture_id=fid,
                )
                mid = created.get("id", "")
                print(f"OK {fid} message_id={mid[:24]}… subject={email.get('subject', '')[:60]}")
                results.append({"id": fid, "ok": True, "graph_id": mid})
            except Exception as exc:
                print(f"FAIL {fid}: {exc}")
                results.append({"id": fid, "ok": False, "error": str(exc)})

    ok = sum(1 for r in results if r.get("ok"))
    print(f"--- done injected={ok}/{len(results)} ---")
    print("Next: open the workbench, sign in as this mailbox, Run triage.")
    out = ROOT / "fixtures" / "e2e_outlook_inject_result.json"
    out.write_text(json.dumps({"mailbox": mailbox, "results": results}, indent=2), encoding="utf-8")
    print("Wrote", out)
    if ok == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
