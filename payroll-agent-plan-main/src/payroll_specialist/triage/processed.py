"""Processed-mail tracking for triage dedupe (UC-011)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol

logger = logging.getLogger("payroll-specialist")


class ProcessedMailPort(Protocol):
    """Dedupe by Graph message id, or by RFC 822 internetMessageId when given.

    Graph ids change when a message moves folders; internetMessageId does not, so
    a moved email is still recognised as already processed.
    """

    def is_processed(self, message_id: str, *, internet_message_id: str | None = None) -> bool: ...

    def mark_processed(self, message_id: str, *, internet_message_id: str | None = None) -> None: ...


class LocalProcessedMailStore:
    """JSON set of processed ids per specialist (offline / no Neon).

    Holds Graph ids and internetMessageIds in one set; the latter are ``<...@...>``
    so the two never collide.
    """

    def __init__(self, root: str | Path, *, specialist_id: str) -> None:
        self._dir = Path(root) / "processed"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{specialist_id}.json"
        self._ids = self._load()

    def _load(self) -> set[str]:
        if not self._path.exists():
            return set()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return {str(x) for x in data}
            if isinstance(data, dict) and isinstance(data.get("ids"), list):
                return {str(x) for x in data["ids"]}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("processed store load failed: %s", exc)
        return set()

    def _save(self) -> None:
        self._path.write_text(
            json.dumps(sorted(self._ids), indent=2),
            encoding="utf-8",
        )

    def is_processed(self, message_id: str, *, internet_message_id: str | None = None) -> bool:
        if str(message_id) in self._ids:
            return True
        return bool(internet_message_id) and str(internet_message_id) in self._ids

    def mark_processed(self, message_id: str, *, internet_message_id: str | None = None) -> None:
        self._ids.add(str(message_id))
        if internet_message_id:
            self._ids.add(str(internet_message_id))
        self._save()


class NeonProcessedMailPort:
    """Thin wrapper over EmailRepository for processed state."""

    def __init__(self, repository: object) -> None:
        self._repo = repository

    def is_processed(self, message_id: str, *, internet_message_id: str | None = None) -> bool:
        return bool(
            self._repo.is_processed(  # type: ignore[attr-defined]
                message_id, internet_message_id=internet_message_id
            )
        )

    def mark_processed(self, message_id: str, *, internet_message_id: str | None = None) -> None:
        # The Neon row already stores internet_message_id from ingest.
        _ = internet_message_id
        self._repo.mark_processed(email_id=message_id)  # type: ignore[attr-defined]


def get_processed_mail_port(
    *,
    specialist_id: str,
    local_root: str | Path | None = None,
) -> ProcessedMailPort:
    """Require Neon for processed-mail dedupe. Local JSON is for injected test stores only."""
    _ = specialist_id
    _ = local_root
    database_url = (os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required for triage dedupe. Local processed-mail fallback is disabled."
        )
    from db.repository import get_email_repository

    return NeonProcessedMailPort(get_email_repository())
