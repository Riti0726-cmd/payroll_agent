"""CORS for browser clients on other origins (Outlook add-in task pane)."""

from __future__ import annotations

import logging
import os
from typing import Any

from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger("payroll-specialist")


def cors_allowed_origins() -> list[str]:
    """Comma-separated CORS_ALLOWED_ORIGINS, e.g. ``https://localhost:3000``."""
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def mount_cors_middleware(app: Any) -> None:
    """Allow listed origins only; no-op when CORS_ALLOWED_ORIGINS is unset."""
    origins = cors_allowed_origins()
    if not origins or getattr(app, "_payroll_cors_mw", False):
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app._payroll_cors_mw = True
    logger.info("Mounted CORS for origins: %s", ", ".join(origins))
