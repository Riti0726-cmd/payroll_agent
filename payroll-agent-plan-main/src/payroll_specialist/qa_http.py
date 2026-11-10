"""HTTP handler for standalone Q&A: POST /qa."""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from models import QaChatResponse
from qa_agent import QaChatValidationError, parse_qa_messages, run_qa_chat

logger = logging.getLogger("payroll-specialist")

QaRunner = Callable[..., Awaitable[QaChatResponse] | QaChatResponse]


def make_qa_route(runner: Optional[QaRunner] = None) -> Callable[[Request], Awaitable[Response]]:
    """Build a Starlette route for POST /qa."""

    async def qa_route(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"detail": "Request body must be JSON"}, status_code=400)

        if not isinstance(body, dict):
            return JSONResponse({"detail": "Request body must be a JSON object"}, status_code=400)

        try:
            messages = parse_qa_messages(body.get("messages"))
        except QaChatValidationError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=400)

        try:
            if runner is not None:
                result = runner(messages)
                if hasattr(result, "__await__"):
                    result = await result  # type: ignore[misc]
                response = result if isinstance(result, QaChatResponse) else QaChatResponse.model_validate(result)
            else:
                response = await run_qa_chat(messages)
        except Exception as exc:
            logger.exception("POST /qa failed")
            return JSONResponse(
                {"detail": f"Q&A agent unavailable: {exc}"},
                status_code=502,
            )

        return JSONResponse(response.model_dump(), status_code=200)

    return qa_route


def mount_qa_route(app: Any, runner: Optional[QaRunner] = None) -> None:
    """Register POST /qa on a ResponsesAgentServerHost (or compatible Starlette app)."""
    app.add_route("/qa", make_qa_route(runner=runner), methods=["POST"])
