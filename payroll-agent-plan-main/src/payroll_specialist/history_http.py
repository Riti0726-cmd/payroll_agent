"""HTTP handler for History: GET /history."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from history_mapping import CLOSED_STATUSES, row_to_history_item
from mailbox_resolve import resolve_specialist_mailbox
from models import HistoryItemResponse, HistoryListResponse

logger = logging.getLogger("payroll-specialist")

HistoryListFn = Callable[[str, str, str], list[dict[str, Any]]]


def default_list_history(
    specialist_id: str,
    mailbox_override: str = "",
    status: str = "all",
) -> list[dict[str, Any]]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    mailbox = resolve_specialist_mailbox(specialist_id, mailbox_override)
    if not mailbox:
        return []
    return get_email_repository().list_history(
        specialist_mailbox=mailbox,
        status=status,
    )


def make_history_route(list_fn: Optional[HistoryListFn] = None) -> Callable[[Request], Any]:
    async def history_route(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)

        mailbox = (request.query_params.get("mailbox") or "").strip()
        status = (request.query_params.get("status") or "all").strip().lower() or "all"
        if status != "all" and status not in CLOSED_STATUSES:
            return JSONResponse(
                {
                    "detail": "status must be all, done, accepted, discarded, approved, or needs_clarification"
                },
                status_code=400,
            )

        try:
            rows = (
                list_fn(specialist_id, mailbox, status)
                if list_fn is not None
                else default_list_history(specialist_id, mailbox, status)
            )
            items = [HistoryItemResponse.model_validate(row_to_history_item(r)) for r in rows]
            return JSONResponse(HistoryListResponse(items=items).model_dump(), status_code=200)
        except Exception as exc:
            logger.exception("GET /history failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return history_route


def mount_history_route(app: Any, list_fn: Optional[HistoryListFn] = None) -> None:
    app.add_route("/history", make_history_route(list_fn=list_fn), methods=["GET"])
