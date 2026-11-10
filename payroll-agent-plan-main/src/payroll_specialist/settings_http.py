"""HTTP handlers for specialist settings: GET/PUT /settings."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from models import SettingsResponse, SettingsUpdateRequest

logger = logging.getLogger("payroll-specialist")

SettingsGetFn = Callable[[str], dict[str, Any]]
SettingsPutFn = Callable[[str, SettingsUpdateRequest], dict[str, Any]]


def _map_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for run in runs:
        summary = str(run.get("summary") or run.get("result") or "")
        if len(summary) > 200:
            summary = summary[:200]
        out.append(
            {
                "runId": str(run.get("run_id") or run.get("runId") or ""),
                "startedAt": str(
                    run.get("created_at") or run.get("startedAt") or run.get("started_at") or ""
                ),
                "status": str(run.get("status") or "unknown"),
                "result": summary,
            }
        )
    return out


def default_get_settings(specialist_id: str) -> dict[str, Any]:
    from store import get_triage_store

    store = get_triage_store()
    config = store.get_specialist_config(specialist_id) or {}
    runs = store.list_runs(specialist_id, limit=20)
    interval = int(config.get("interval_hours") or 2)
    if interval not in (2, 4, 24):
        interval = 2
    mode = str(config.get("mode") or "manual").lower()
    if mode not in ("manual", "recurring"):
        mode = "manual"
    return {
        "lookbackDays": int(config.get("lookback_days") or 7),
        "mode": mode,
        "intervalHours": interval,
        "runs": _map_runs(runs),
    }


def default_put_settings(specialist_id: str, payload: SettingsUpdateRequest) -> dict[str, Any]:
    from store import get_triage_store

    store = get_triage_store()
    existing = store.get_specialist_config(specialist_id) or {}
    merged = {
        **existing,
        "lookback_days": payload.lookbackDays,
        "mode": payload.mode,
        "interval_hours": payload.intervalHours,
    }
    store.save_specialist_config(specialist_id, merged)
    return default_get_settings(specialist_id)


def make_settings_get_route(
    get_fn: Optional[SettingsGetFn] = None,
) -> Callable[[Request], Any]:
    async def settings_get(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        try:
            data = get_fn(specialist_id) if get_fn is not None else default_get_settings(specialist_id)
            return JSONResponse(SettingsResponse.model_validate(data).model_dump(), status_code=200)
        except Exception as exc:
            logger.exception("GET /settings failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return settings_get


def make_settings_put_route(
    put_fn: Optional[SettingsPutFn] = None,
) -> Callable[[Request], Any]:
    async def settings_put(request: Request) -> Response:
        specialist_id = (request.query_params.get("specialist_id") or "").strip()
        if not specialist_id:
            return JSONResponse({"detail": "specialist_id is required"}, status_code=400)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "Request body must be JSON"}, status_code=400)
        if not isinstance(body, dict):
            return JSONResponse({"detail": "Request body must be a JSON object"}, status_code=400)
        try:
            payload = SettingsUpdateRequest.model_validate(body)
        except ValidationError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)
        try:
            data = (
                put_fn(specialist_id, payload)
                if put_fn is not None
                else default_put_settings(specialist_id, payload)
            )
            return JSONResponse(SettingsResponse.model_validate(data).model_dump(), status_code=200)
        except Exception as exc:
            logger.exception("PUT /settings failed")
            return JSONResponse({"detail": str(exc)}, status_code=503)

    return settings_put


def mount_settings_routes(
    app: Any,
    *,
    get_fn: Optional[SettingsGetFn] = None,
    put_fn: Optional[SettingsPutFn] = None,
) -> None:
    app.add_route("/settings", make_settings_get_route(get_fn=get_fn), methods=["GET"])
    app.add_route("/settings", make_settings_put_route(put_fn=put_fn), methods=["PUT"])
