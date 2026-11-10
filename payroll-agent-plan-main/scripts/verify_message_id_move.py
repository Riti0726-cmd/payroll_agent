"""Live check: does a Graph message id change on folder move, and does our dedupe/lookup
key (internetMessageId) survive it?

Touches no real mail. In the signed-in mailbox it:
  1. creates a throwaway message in the Inbox ("[ID move test] safe to delete"),
  2. creates a temporary folder and moves the message into it,
  3. compares id / internetMessageId / immutable id before and after the move,
  4. runs the app's own code on the real ids (RealGraphMailbox parsing and the
     processed-mail dedupe),
  5. deletes the test message and folder (normal delete -> Deleted Items).

Usage (sign in as the mailbox user; needs Mail.ReadWrite on the app registration):
  .\\.venv\\Scripts\\python.exe scripts\\verify_message_id_move.py --device-code
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "payroll_specialist"))
sys.path.insert(0, str(ROOT / "scripts"))

from inject_e2e_outlook import GRAPH, resolve_token  # noqa: E402  (also loads .env)

IMMUTABLE = {"Prefer": 'IdType="ImmutableId"'}


def _short(value: str | None, keep: int = 18) -> str:
    if not value:
        return "(none)"
    return value if len(value) <= 2 * keep + 3 else f"{value[:keep]}...{value[-keep:]}"


def _get(client: httpx.Client, url: str, **kw) -> httpx.Response:
    return client.get(url, **kw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device-code", action="store_true", help="Interactive device login")
    parser.add_argument("--token", default=None, help="Delegated Graph bearer (Mail.ReadWrite)")
    parser.add_argument("--keep", action="store_true", help="Do not delete the test message/folder")
    parser.add_argument(
        "--dump",
        default=None,
        help="Directory to save the raw Graph JSON responses (before_move.json, after_move.json)",
    )
    args = parser.parse_args()

    token, auth_label = resolve_token(device_code=args.device_code, explicit=args.token)
    if auth_label == "app":
        raise SystemExit("Use a delegated token (--device-code); this test runs against /me.")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base = f"{GRAPH}/me"
    checks: list[tuple[str, bool | None, str]] = []
    message_id = folder_id = None

    with httpx.Client(timeout=30.0, headers=headers) as client:
        try:
            # 1. Throwaway message in the Inbox (same pattern as inject_e2e_outlook.py).
            created = client.post(
                f"{base}/mailFolders/inbox/messages",
                json={
                    "subject": f"[ID move test] safe to delete {stamp}",
                    "body": {"contentType": "Text", "content": "Created by verify_message_id_move.py."},
                },
            )
            created.raise_for_status()
            before = created.json()
            message_id = before["id"]
            imid_before = before.get("internetMessageId") or ""
            imm_resp = _get(client, f"{base}/messages/{message_id}?$select=id", headers=IMMUTABLE)
            immutable_before = imm_resp.json()["id"]
            # Graph echoes Preference-Applied when it honoured the ImmutableId preference.
            immutable_applied = "immutableid" in imm_resp.headers.get("Preference-Applied", "").lower()
            print("Created test message in Inbox")

            # 2. Temporary folder + move.
            folder = client.post(f"{base}/mailFolders", json={"displayName": f"ID move test {stamp}"})
            folder.raise_for_status()
            folder_id = folder.json()["id"]
            moved = client.post(f"{base}/messages/{message_id}/move", json={"destinationId": folder_id})
            moved.raise_for_status()
            after = moved.json()
            new_id = after["id"]
            message_id = new_id  # for cleanup
            imid_after = after.get("internetMessageId") or ""
            immutable_after = _get(
                client, f"{base}/messages/{new_id}?$select=id", headers=IMMUTABLE
            ).json()["id"]
            old_lookup = _get(client, f"{base}/messages/{before['id']}?$select=id")
            if args.dump:
                out_dir = Path(args.dump)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "before_move.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
                (out_dir / "after_move.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
                (out_dir / "old_id_after_move.json").write_text(
                    json.dumps({"status": old_lookup.status_code, "body": old_lookup.json()}, indent=2),
                    encoding="utf-8",
                )
                print(f"Saved raw Graph responses to {out_dir}")
            print("Moved it to a temporary folder\n")

            print(f"{'':22}{'before move':44}after move")
            print(f"{'Graph id':22}{_short(before['id']):44}{_short(new_id)}")
            print(f"{'internetMessageId':22}{_short(imid_before):44}{_short(imid_after)}")
            print(f"{'Immutable id':22}{_short(immutable_before):44}{_short(immutable_after)}\n")

            checks.append(("Graph id changed on move", before["id"] != new_id, ""))
            checks.append(
                ("Old Graph id no longer resolves", old_lookup.status_code == 404, f"HTTP {old_lookup.status_code}")
            )
            checks.append(("internetMessageId present", bool(imid_before), ""))
            checks.append(("internetMessageId unchanged on move", imid_before == imid_after, ""))
            if immutable_applied:
                checks.append(("Immutable id unchanged on move", immutable_before == immutable_after, ""))
            else:
                checks.append(
                    (
                        "Immutable id unchanged on move",
                        None,  # informational: the app does not use immutable ids
                        "Graph did not apply the ImmutableId preference (no Preference-Applied)",
                    )
                )

            # 3. App code on the real ids.
            from triage.mailbox import RealGraphMailbox
            from triage.processed import LocalProcessedMailStore
            from triage.request_context import graph_access_token_scope

            now = datetime.now(timezone.utc)
            with graph_access_token_scope(token):
                listed = RealGraphMailbox().list_messages(
                    "me",
                    window_start=(now - timedelta(hours=1)).isoformat(),
                    window_end=(now + timedelta(minutes=5)).isoformat(),
                )
            seen = next((m for m in listed if m.id == new_id), None)
            checks.append(
                (
                    "RealGraphMailbox returns moved message with internet_message_id",
                    bool(seen and seen.internet_message_id == imid_before),
                    "" if seen else "not in list_messages window",
                )
            )

            with tempfile.TemporaryDirectory() as tmp:
                store = LocalProcessedMailStore(tmp, specialist_id="id-move-test")
                store.mark_processed(before["id"], internet_message_id=imid_before)  # triaged in Inbox
                checks.append(
                    (
                        "Dedupe skips moved copy (new id + internetMessageId)",
                        store.is_processed(new_id, internet_message_id=imid_after),
                        "",
                    )
                )
                checks.append(
                    (
                        "Old behaviour (Graph id only) would re-triage it",
                        not store.is_processed(new_id),
                        "",
                    )
                )
        finally:
            if not args.keep:
                if message_id:
                    client.delete(f"{base}/messages/{message_id}")
                if folder_id:
                    client.delete(f"{base}/mailFolders/{folder_id}")
                print("Cleaned up test message and folder (moved to Deleted Items)\n")

    width = max(len(name) for name, _, _ in checks)
    for name, ok, note in checks:
        label = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
        print(f"[{label}] {name.ljust(width)} {note}")
    return 0 if all(ok is not False for _, ok, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
