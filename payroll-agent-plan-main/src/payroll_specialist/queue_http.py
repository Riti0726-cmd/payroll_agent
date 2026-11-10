"""HTTP handlers for Queue: GET /queue, PATCH /queue/{message_id}."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from db.repository import EmailNotFoundError
from mailbox_resolve import resolve_specialist_mailbox
from models import QueueItemResponse, QueueListResponse
from queue_mapping import row_to_queue_item

logger = logging.getLogger("payroll-specialist")

# list_fn(specialist_id, mailbox_override)
QueueListFn = Callable[[str, str], list[dict[str, Any]]]
QueuePatchFn = Callable[[str, bool | None, int | None], dict[str, Any]]


def default_list_queue(specialist_id: str, mailbox_override: str = "") -> list[dict[str, Any]]:
    """Load open queue rows from Neon for the specialist's mailbox."""
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()  # raises if DATABASE_URL missing
    mailbox = resolve_specialist_mailbox(specialist_id, mailbox_override)
    if not mailbox:
        return []
    return get_email_repository().list_open_queue(specialist_mailbox=mailbox)


def default_patch_queue(
    message_id: str,
    done: bool | None,
    priority: int | None,
) -> dict[str, Any]:
    from db.database import get_database_url
    from db.repository import get_email_repository

    get_database_url()
    return get_email_repository().patch_queue_item(
        message_id=message_id,
        done=done,
        priority=priority,
    )


def make_queue_route(list_fn: Optional[QueueListFn] = None) -> Callable[[Request], Any]:
    """Build a Starlette route for GET /queue."""

    async def queue_route(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)

        mailbox = (request.query_params.get("mailbox") or "").strip()

        try:
            if list_fn is not None:
                rows = list_fn(specialist_id, mailbox)
            else:
                rows = default_list_queue(specialist_id, mailbox)
            items = [QueueItemResponse.model_validate(row_to_queue_item(r)) for r in rows]
            return JSONResponse(
                QueueListResponse(items=items).model_dump(),
                status_code=200,
            )
        except Exception as exc:
            logger.exception("GET /queue failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return queue_route


def make_queue_patch_route(patch_fn: Optional[QueuePatchFn] = None) -> Callable[[Request], Any]:
    async def queue_patch(request: Request) -> Response:
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

        done_raw = body.get("done")
        priority_raw = body.get("priority")
        done: bool | None = None
        priority: int | None = None

        if done_raw is not None:
            if not isinstance(done_raw, bool):
                return JSONResponse({"detail": "done must be a boolean"}, status_code=400)
            done = done_raw
        if priority_raw is not None:
            try:
                priority = int(priority_raw)
            except (TypeError, ValueError):
                return JSONResponse({"detail": "priority must be an integer 1-5"}, status_code=400)
            if priority not in (1, 2, 3, 4, 5):
                return JSONResponse({"detail": "priority must be an integer 1-5"}, status_code=400)

        if done is None and priority is None:
            return JSONResponse(
                {"detail": "Provide done and/or priority"},
                status_code=400,
            )

        try:
            row = (
                patch_fn(message_id, done, priority)
                if patch_fn is not None
                else default_patch_queue(message_id, done, priority)
            )
            item = QueueItemResponse.model_validate(row_to_queue_item(row))
            return JSONResponse(item.model_dump(), status_code=200)
        except EmailNotFoundError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=404)
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        except Exception as exc:
            logger.exception("PATCH /queue failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return queue_patch


def mount_queue_route(
    app: Any,
    list_fn: Optional[QueueListFn] = None,
    patch_fn: Optional[QueuePatchFn] = None,
) -> None:
    """Register GET /queue and PATCH /queue/{message_id}."""
    app.add_route("/queue", make_queue_route(list_fn=list_fn), methods=["GET"])
    app.add_route(
        "/queue/{message_id}",
        make_queue_patch_route(patch_fn=patch_fn),
        methods=["PATCH"],
    )
