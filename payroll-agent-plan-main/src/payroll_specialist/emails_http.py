"""HTTP handler for the Outlook add-in: GET /emails/lookup."""

from __future__ import annotations

import logging
from typing import Any, Callable, Mapping, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from changelists_mapping import row_to_changelist_item
from db.categories import parse_categories
from db.repository import EmailNotFoundError
from drafts_mapping import row_to_draft_item
from mailbox_resolve import resolve_specialist_mailbox
from models import EmailRecordResponse
from queue_mapping import row_to_queue_item

logger = logging.getLogger("payroll-specialist")

# lookup_fn(specialist_id, mailbox_override, rest_id, internet_message_id) -> row
EmailLookupFn = Callable[[str, str, str, str], dict[str, Any]]

_CLOSED_STATUS = frozenset({"done", "accepted", "discarded", "approved", "sent"})


def default_lookup_email(
    specialist_id: str,
    mailbox_override: str,
    rest_id: str,
    internet_message_id: str,
) -> dict[str, Any]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    mailbox = resolve_specialist_mailbox(specialist_id, mailbox_override)
    return get_email_repository().get_email_record(
        specialist_mailbox=mailbox,
        message_id=rest_id,
        internet_message_id=internet_message_id,
    )


def row_to_email_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Combine queue, draft and changelist mappings into one EmailRecord dict."""
    queue_item = row_to_queue_item(row)
    categories = parse_categories(row.get("category"))
    status = (row.get("hitl_status") or "").strip().lower() or None
    triaged = bool(row.get("is_categorized")) and bool(categories)

    record: dict[str, Any] = {
        "id": queue_item["id"],
        "subject": queue_item["subject"],
        "triaged": triaged,
        "category": categories[0] if categories else None,
        "priority": queue_item["priority"],
        "receivedAt": queue_item["receivedAt"],
        "status": status,
        "done": status in _CLOSED_STATUS or bool(row.get("is_processed")),
    }
    for key in ("clientId", "employeeId", "extracted"):
        if key in queue_item:
            record[key] = queue_item[key]
    if (row.get("draft_content") or "").strip():
        record["draft"] = row_to_draft_item(row)
    if "changelist" in categories:
        record["changeList"] = row_to_changelist_item(row)
    return record


def make_email_lookup_route(lookup_fn: Optional[EmailLookupFn] = None) -> Callable[[Request], Any]:
    async def email_lookup(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        rest_id = (request.query_params.get("rest_id") or "").strip()
        internet_message_id = (request.query_params.get("internet_message_id") or "").strip()
        if not rest_id and not internet_message_id:
            return JSONResponse(
                {"detail": "Provide rest_id and/or internet_message_id"},
                status_code=400,
            )
        mailbox = (request.query_params.get("mailbox") or "").strip()
        try:
            row = (
                lookup_fn(specialist_id, mailbox, rest_id, internet_message_id)
                if lookup_fn is not None
                else default_lookup_email(specialist_id, mailbox, rest_id, internet_message_id)
            )
            record = EmailRecordResponse.model_validate(row_to_email_record(row))
            return JSONResponse(
                record.model_dump(by_alias=True, exclude_none=True),
                status_code=200,
            )
        except EmailNotFoundError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        except Exception as exc:
            logger.exception("GET /emails/lookup failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return email_lookup


def mount_emails_routes(app: Any, *, lookup_fn: Optional[EmailLookupFn] = None) -> None:
    app.add_route("/emails/lookup", make_email_lookup_route(lookup_fn=lookup_fn), methods=["GET"])
