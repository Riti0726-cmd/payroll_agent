"""HTTP handlers for Change lists: GET /changelists, PATCH /changelists/{message_id}."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from changelists_mapping import row_to_changelist_item
from db.repository import EmailNotFoundError
from mailbox_resolve import resolve_specialist_mailbox
from models import ChangeListItemResponse, ChangeListListResponse

logger = logging.getLogger("payroll-specialist")

ChangelistsListFn = Callable[[str, str], list[dict[str, Any]]]
# patch_fn(specialist_id, message_id, status|None, lines|None) -> row
ChangelistPatchFn = Callable[[str, str, str | None, list | None], dict[str, Any]]

_ALLOWED_STATUS = frozenset({"approved", "needs_clarification"})


def default_list_changelists(
    specialist_id: str, mailbox_override: str = ""
) -> list[dict[str, Any]]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    mailbox = resolve_specialist_mailbox(specialist_id, mailbox_override)
    if not mailbox:
        return []
    return get_email_repository().list_pending_changelists(specialist_mailbox=mailbox)


def default_patch_changelist(
    specialist_id: str,
    message_id: str,
    status: str | None,
    lines: list | None,
) -> dict[str, Any]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    _ = specialist_id
    return get_email_repository().patch_changelist_item(
        message_id, status=status, lines=lines
    )


def make_changelists_list_route(
    list_fn: Optional[ChangelistsListFn] = None,
) -> Callable[[Request], Any]:
    async def changelists_list(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        mailbox = (request.query_params.get("mailbox") or "").strip()
        try:
            rows = (
                list_fn(specialist_id, mailbox)
                if list_fn is not None
                else default_list_changelists(specialist_id, mailbox)
            )
            items = [
                ChangeListItemResponse.model_validate(row_to_changelist_item(r)) for r in rows
            ]
            return JSONResponse(
                ChangeListListResponse(items=items).model_dump(by_alias=True, exclude_none=True),
                status_code=200,
            )
        except Exception as exc:
            logger.exception("GET /changelists failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return changelists_list


def make_changelist_patch_route(
    patch_fn: Optional[ChangelistPatchFn] = None,
) -> Callable[[Request], Any]:
    async def changelist_patch(request: Request) -> Response:
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

        status_raw = body.get("status")
        status: str | None = None
        if status_raw is not None and str(status_raw).strip() != "":
            status = str(status_raw).strip().lower()
            if status not in _ALLOWED_STATUS:
                return JSONResponse(
                    {"detail": "status must be approved or needs_clarification"},
                    status_code=400,
                )

        lines = body.get("lines")
        if lines is not None and not isinstance(lines, list):
            return JSONResponse({"detail": "lines must be an array"}, status_code=400)

        if status is None and lines is None:
            return JSONResponse(
                {"detail": "Provide status and/or lines"},
                status_code=400,
            )

        try:
            row = (
                patch_fn(specialist_id, message_id, status, lines)
                if patch_fn is not None
                else default_patch_changelist(specialist_id, message_id, status, lines)
            )
            return JSONResponse(
                ChangeListItemResponse.model_validate(row_to_changelist_item(row)).model_dump(
                    by_alias=True, exclude_none=True
                ),
                status_code=200,
            )
        except EmailNotFoundError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        except Exception as exc:
            logger.exception("PATCH /changelists failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return changelist_patch


def mount_changelists_routes(
    app: Any,
    *,
    list_fn: Optional[ChangelistsListFn] = None,
    patch_fn: Optional[ChangelistPatchFn] = None,
) -> None:
    app.add_route("/changelists", make_changelists_list_route(list_fn=list_fn), methods=["GET"])
    app.add_route(
        "/changelists/{message_id}",
        make_changelist_patch_route(patch_fn=patch_fn),
        methods=["PATCH"],
    )
