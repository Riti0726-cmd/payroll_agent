"""HTTP handlers for Drafts: GET /drafts, PATCH /drafts/{message_id}."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from db.repository import EmailNotFoundError
from drafts_mapping import row_to_draft_item
from mailbox_resolve import resolve_specialist_mailbox
from models import DraftItemResponse, DraftListResponse

logger = logging.getLogger("payroll-specialist")

DraftsListFn = Callable[[str, str], list[dict[str, Any]]]
DraftPatchFn = Callable[[str, str, str, str | None], dict[str, Any]]

_ALLOWED_STATUS = frozenset({"accepted", "discarded"})


def default_list_drafts(specialist_id: str, mailbox_override: str = "") -> list[dict[str, Any]]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    mailbox = resolve_specialist_mailbox(specialist_id, mailbox_override)
    if not mailbox:
        return []
    return get_email_repository().list_pending_drafts(specialist_mailbox=mailbox)


def default_patch_draft(
    specialist_id: str,
    message_id: str,
    status: str,
    body: str | None,
) -> dict[str, Any]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    _ = specialist_id
    return get_email_repository().set_hitl_status(message_id, status, draft_body=body)


def make_drafts_list_route(list_fn: Optional[DraftsListFn] = None) -> Callable[[Request], Any]:
    async def drafts_list(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        mailbox = (request.query_params.get("mailbox") or "").strip()
        try:
            rows = (
                list_fn(specialist_id, mailbox)
                if list_fn is not None
                else default_list_drafts(specialist_id, mailbox)
            )
            items = [DraftItemResponse.model_validate(row_to_draft_item(r)) for r in rows]
            return JSONResponse(DraftListResponse(items=items).model_dump(), status_code=200)
        except Exception as exc:
            logger.exception("GET /drafts failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return drafts_list


def make_draft_patch_route(patch_fn: Optional[DraftPatchFn] = None) -> Callable[[Request], Any]:
    async def draft_patch(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        message_id = (request.path_params.get("message_id") or "").strip()
        if not message_id:
            return JSONResponse({"detail": "message_id is required"}, status_code=400)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "Request body must be JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"detail": "Request body must be a JSON object"}, status_code=400)
        status = str(body.get("status") or "").strip().lower()
        if status not in _ALLOWED_STATUS:
            return JSONResponse(
                {"detail": "status must be accepted or discarded"},
                status_code=400,
            )
        draft_body = body.get("body")
        if draft_body is not None and not isinstance(draft_body, str):
            return JSONResponse({"detail": "body must be a string"}, status_code=400)
        try:
            row = (
                patch_fn(specialist_id, message_id, status, draft_body)
                if patch_fn is not None
                else default_patch_draft(specialist_id, message_id, status, draft_body)
            )
            return JSONResponse(
                DraftItemResponse.model_validate(row_to_draft_item(row)).model_dump(),
                status_code=200,
            )
        except EmailNotFoundError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        except Exception as exc:
            logger.exception("PATCH /drafts failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return draft_patch


def mount_drafts_routes(
    app: Any,
    *,
    list_fn: Optional[DraftsListFn] = None,
    patch_fn: Optional[DraftPatchFn] = None,
) -> None:
    app.add_route("/drafts", make_drafts_list_route(list_fn=list_fn), methods=["GET"])
    app.add_route(
        "/drafts/{message_id}",
        make_draft_patch_route(patch_fn=patch_fn),
        methods=["PATCH"],
    )
