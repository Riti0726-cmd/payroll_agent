"""Azure Blob-backed specialist config + triage run store (UC-004–009 durable)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from store.local_store import default_specialist_config

logger = logging.getLogger("payroll-specialist")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BlobTriageStore:
    def __init__(self, connection_string: str, container: str = "payroll-triage") -> None:
        from azure.storage.blob import BlobServiceClient, ContentSettings

        self._ContentSettings = ContentSettings
        self._service = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container
        self._container = self._service.get_container_client(container)
        try:
            self._container.create_container()
        except Exception:
            # Container may already exist
            pass

    def _blob(self, path: str):
        return self._container.get_blob_client(path)

    def _read_json(self, path: str) -> dict | None:
        try:
            data = self._blob(path).download_blob().readall()
            return json.loads(data.decode("utf-8-sig"))
        except Exception:
            return None

    def _write_json(self, path: str, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self._blob(path).upload_blob(
            body,
            overwrite=True,
            content_settings=self._ContentSettings(content_type="application/json"),
        )

    def _config_key(self, specialist_id: str) -> str:
        return f"specialists/{specialist_id}/config.json"

    def _run_key(self, specialist_id: str, run_id: str) -> str:
        return f"specialists/{specialist_id}/runs/{run_id}.json"

    def get_specialist_config(self, specialist_id: str) -> dict:
        existing = self._read_json(self._config_key(specialist_id))
        if existing:
            return existing
        cfg = default_specialist_config(specialist_id)
        return self.save_specialist_config(specialist_id, cfg)

    def save_specialist_config(self, specialist_id: str, config: dict) -> dict:
        merged = {**config, "specialist_id": specialist_id, "updated_at": _utc_now_iso()}
        interval = int(merged.get("interval_hours") or 4)
        if interval not in (2, 4, 24):
            interval = 4
        merged["interval_hours"] = interval
        mode = str(merged.get("mode") or "manual").lower()
        merged["mode"] = mode if mode in ("manual", "recurring") else "manual"
        self._write_json(self._config_key(specialist_id), merged)
        return merged

    def get_last_successful_run(self, specialist_id: str) -> dict | None:
        for run in self.list_runs(specialist_id, limit=100):
            if run.get("status") == "succeeded":
                return run
        return None

    def create_run(self, specialist_id: str, run: dict) -> dict:
        run_id = str(run.get("run_id") or uuid.uuid4())
        record = {
            **run,
            "run_id": run_id,
            "specialist_id": specialist_id,
            "status": run.get("status") or "running",
            "created_at": run.get("created_at") or _utc_now_iso(),
        }
        self._write_json(self._run_key(specialist_id, run_id), record)
        return record

    def complete_run(self, specialist_id: str, run_id: str, updates: dict) -> dict:
        key = self._run_key(specialist_id, run_id)
        record = self._read_json(key) or {"run_id": run_id, "specialist_id": specialist_id}
        record.update(updates)
        record["completed_at"] = updates.get("completed_at") or _utc_now_iso()
        self._write_json(key, record)
        return record

    def list_runs(self, specialist_id: str, limit: int = 20) -> list[dict]:
        prefix = f"specialists/{specialist_id}/runs/"
        blobs = list(self._container.list_blobs(name_starts_with=prefix))
        blobs.sort(key=lambda b: getattr(b, "last_modified", None) or datetime.min, reverse=True)
        out: list[dict] = []
        for blob in blobs[:limit]:
            data = self._read_json(blob.name)
            if data:
                out.append(data)
        return out
