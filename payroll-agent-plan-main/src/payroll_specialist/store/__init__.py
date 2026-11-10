"""Durable specialist config + triage run stores."""

from __future__ import annotations

import os
from typing import Protocol


class TriageStore(Protocol):
    def get_specialist_config(self, specialist_id: str) -> dict: ...

    def save_specialist_config(self, specialist_id: str, config: dict) -> dict: ...

    def get_last_successful_run(self, specialist_id: str) -> dict | None: ...

    def create_run(self, specialist_id: str, run: dict) -> dict: ...

    def complete_run(self, specialist_id: str, run_id: str, updates: dict) -> dict: ...

    def list_runs(self, specialist_id: str, limit: int = 20) -> list[dict]: ...


def get_triage_store() -> TriageStore:
    """Prefer Azure Blob when connection string is set; otherwise local filesystem store."""
    conn = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    container = os.environ.get("TRIAGE_BLOB_CONTAINER", "payroll-triage").strip() or "payroll-triage"
    if conn:
        from store.blob_store import BlobTriageStore

        return BlobTriageStore(connection_string=conn, container=container)
    from store.local_store import LocalTriageStore

    root = os.environ.get("TRIAGE_LOCAL_STORE_PATH", ".local_store").strip() or ".local_store"
    return LocalTriageStore(root=root)
