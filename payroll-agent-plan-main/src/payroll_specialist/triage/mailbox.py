"""Graph mailbox port — MockGraph (tests) + RealGraph (delegated or app)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import quote

from triage.auth import load_graph_auth, mailbox_allowed
from triage.request_context import get_graph_access_token

logger = logging.getLogger("payroll-specialist")


@dataclass
class MailMessage:
    id: str
    received_at: str
    from_address: str = ""
    subject: str = ""
    body_preview: str = ""
    body: str = ""
    conversation_id: str = ""
    is_read: bool = False
    web_link: str = ""
    internet_message_id: str = ""


@dataclass
class MailboxBinding:
    specialist_id: str
    mailbox_id: str
    display_name: str = ""


class GraphMailboxPort(Protocol):
    def bind_specialist(self, specialist_id: str, mailbox_id: str) -> MailboxBinding: ...

    def get_binding(self, specialist_id: str) -> MailboxBinding | None: ...

    def list_messages(
        self,
        mailbox_id: str,
        *,
        window_start: str,
        window_end: str,
    ) -> list[MailMessage]: ...


class MockGraphMailbox:
    """In-memory Graph stand-in for **unit tests only** — never used by production wiring."""

    def __init__(self, messages: list[MailMessage] | None = None) -> None:
        self._bindings: dict[str, MailboxBinding] = {}
        self._messages: list[MailMessage] = list(messages or [])

    def seed_messages(self, messages: list[MailMessage]) -> None:
        self._messages = list(messages)

    def bind_specialist(self, specialist_id: str, mailbox_id: str) -> MailboxBinding:
        binding = MailboxBinding(
            specialist_id=specialist_id,
            mailbox_id=mailbox_id,
            display_name=f"Mock mailbox {mailbox_id}",
        )
        self._bindings[specialist_id] = binding
        return binding

    def get_binding(self, specialist_id: str) -> MailboxBinding | None:
        return self._bindings.get(specialist_id)

    def list_messages(
        self,
        mailbox_id: str,
        *,
        window_start: str,
        window_end: str,
    ) -> list[MailMessage]:
        start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
        out: list[MailMessage] = []
        for msg in self._messages:
            received = datetime.fromisoformat(msg.received_at.replace("Z", "+00:00"))
            if start <= received <= end:
                out.append(msg)
        return out


class RealGraphMailbox:
    """Microsoft Graph mail reader (read + unread, paginated) for UC-010."""

    def __init__(self) -> None:
        settings = load_graph_auth()
        if settings is None:
            raise RuntimeError(
                "Graph auth not configured. For delegated mode set GRAPH_TENANT_ID and "
                "GRAPH_CLIENT_ID (caller must send Bearer token with Mail.Read). "
                "For app mode also set GRAPH_CLIENT_SECRET and GRAPH_AUTH_MODE=app."
            )
        self._settings = settings
        self._bindings: dict[str, MailboxBinding] = {}

    def _token(self) -> str:
        if self._settings.mode == "delegated":
            token = get_graph_access_token()
            if not token:
                raise RuntimeError(
                    "Delegated Graph requires a Bearer access token with Mail.Read "
                    "(sign in via the workbench and Run triage so Authorization is forwarded)."
                )
            return token

        import httpx

        url = (
            f"https://login.microsoftonline.com/{self._settings.tenant_id}/oauth2/v2.0/token"
        )
        data = {
            "client_id": self._settings.client_id,
            "client_secret": self._settings.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, data=data)
            resp.raise_for_status()
            return resp.json()["access_token"]

    def bind_specialist(self, specialist_id: str, mailbox_id: str) -> MailboxBinding:
        if not mailbox_allowed(mailbox_id, self._settings.allowlist):
            raise PermissionError(f"Mailbox {mailbox_id} is not on GRAPH_MAILBOX_ALLOWLIST.")
        binding = MailboxBinding(specialist_id=specialist_id, mailbox_id=mailbox_id)
        self._bindings[specialist_id] = binding
        return binding

    def get_binding(self, specialist_id: str) -> MailboxBinding | None:
        return self._bindings.get(specialist_id)

    def list_messages(
        self,
        mailbox_id: str,
        *,
        window_start: str,
        window_end: str,
    ) -> list[MailMessage]:
        if not mailbox_allowed(mailbox_id, self._settings.allowlist):
            raise PermissionError(f"Mailbox {mailbox_id} is not on GRAPH_MAILBOX_ALLOWLIST.")

        import httpx

        token = self._token()
        headers = {"Authorization": f"Bearer {token}"}
        filt = (
            f"receivedDateTime ge {window_start} and receivedDateTime le {window_end}"
        )
        select = (
            "id,internetMessageId,receivedDateTime,from,subject,bodyPreview,body,conversationId,"
            "isRead,webLink"
        )
        if self._settings.mode == "delegated":
            # Signed-in specialist mailbox (/me)
            url = (
                f"https://graph.microsoft.com/v1.0/me/messages"
                f"?$filter={quote(filt)}"
                f"&$select={select}"
                f"&$orderby=receivedDateTime asc"
                f"&$top=50"
            )
        else:
            user = quote(mailbox_id)
            url = (
                f"https://graph.microsoft.com/v1.0/users/{user}/messages"
                f"?$filter={quote(filt)}"
                f"&$select={select}"
                f"&$orderby=receivedDateTime asc"
                f"&$top=50"
            )
        out: list[MailMessage] = []
        with httpx.Client(timeout=60.0, headers=headers) as client:
            next_url: str | None = url
            while next_url:
                resp = client.get(next_url)
                resp.raise_for_status()
                payload = resp.json()
                for item in payload.get("value", []):
                    from_obj = item.get("from") or {}
                    addr = ((from_obj.get("emailAddress") or {}).get("address")) or ""
                    body_obj = item.get("body") or {}
                    body_content = ""
                    if isinstance(body_obj, dict):
                        body_content = body_obj.get("content") or ""
                    preview = item.get("bodyPreview") or ""
                    out.append(
                        MailMessage(
                            id=item.get("id", ""),
                            received_at=item.get("receivedDateTime", ""),
                            from_address=addr,
                            subject=item.get("subject") or "",
                            body_preview=preview,
                            body=body_content or preview,
                            conversation_id=item.get("conversationId") or "",
                            is_read=bool(item.get("isRead")),
                            web_link=item.get("webLink") or "",
                            internet_message_id=item.get("internetMessageId") or "",
                        )
                    )
                next_url = payload.get("@odata.nextLink")
        return out


def get_mailbox_port(*, prefer_mock: bool = False) -> GraphMailboxPort:
    """Return the real Microsoft Graph mailbox client.

    ``prefer_mock`` is rejected at runtime — there is no demo Graph path.
    Unit tests must inject ``MockGraphMailbox`` explicitly.
    """
    if prefer_mock:
        raise RuntimeError(
            "Mock Graph is not allowed at runtime. Inject MockGraphMailbox only in tests."
        )
    if load_graph_auth() is None:
        raise RuntimeError(
            "Microsoft Graph is not configured. Set GRAPH_AUTH_MODE=delegated (default) with "
            "GRAPH_TENANT_ID + GRAPH_CLIENT_ID, and send a Bearer Mail.Read token on triage. "
            "Or set GRAPH_AUTH_MODE=app with GRAPH_CLIENT_SECRET."
        )
    return RealGraphMailbox()
