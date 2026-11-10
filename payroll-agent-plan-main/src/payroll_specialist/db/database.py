"""SQLAlchemy engine/session for Neon DATABASE_URL."""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base


def _normalize_database_url(url: str) -> str:
    """Accept plain postgresql:// or SQLAlchemy postgresql+psycopg2:// forms."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg2" not in url and "+psycopg" not in url:
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


def get_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. Add a Neon URI to .env "
            "(postgresql+psycopg2://… or postgresql://…)."
        )
    return _normalize_database_url(raw)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    engine = create_engine(
        get_database_url(),
        echo=False,
        pool_pre_ping=True,
        future=True,
    )

    if engine.dialect.name == "postgresql":

        @event.listens_for(engine, "connect")
        def _set_ist_timezone(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("SET TIME ZONE 'Asia/Kolkata'")
            cursor.close()

    return engine


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create tables if missing (forward-safe). Prefer SQL migrations for prod."""
    Base.metadata.create_all(get_engine())
