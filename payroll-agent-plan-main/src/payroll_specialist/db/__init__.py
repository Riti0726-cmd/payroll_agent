"""Neon/Postgres email_processing pipeline store (not payroll analytics)."""

from __future__ import annotations

from db.database import get_engine, get_session_factory, init_db
from db.repository import EmailRepository, get_email_repository

__all__ = [
    "EmailRepository",
    "get_email_repository",
    "get_engine",
    "get_session_factory",
    "init_db",
]
