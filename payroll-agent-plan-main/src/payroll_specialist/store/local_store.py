"""Local filesystem store for specialist config + triage runs (dev / when blob unset)."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_default_interval_hours, get_default_lookback_days


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_specialist_config(specialist_id: str, mailbox_id: str | None = None) -> dict[str, Any]:
    return {
        "specialist_id": specialist_id,
        "mailbox_id": mailbox_id or f"mailbox-{specialist_id}",
        "lookback_days": get_default_lookback_days(),
        "mode": "manual",  # manual | recurring
        "interval_hours": get_default_interval_hours(),
        "updated_at": _utc_now_iso(),
    }


def _read_json_file(path: Path) -> dict:
    # utf-8-sig strips a BOM that Windows editors sometimes write
    return json.loads(path.read_text(encoding="utf-8-sig"))


class LocalTriageStore:
    def __init__(self, root: str = ".local_store") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _config_path(self, specialist_id: str) -> Path:
        return self.root / "specialists" / specialist_id / "config.json"

    def _runs_dir(self, specialist_id: str) -> Path:
        path = self.root / "specialists" / specialist_id / "runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_specialist_config(self, specialist_id: str) -> dict:
        path = self._config_path(specialist_id)
        if not path.exists():
            cfg = default_specialist_config(specialist_id)
            self.save_specialist_config(specialist_id, cfg)
            return cfg
        with self._lock:
            return _read_json_file(path)

    def save_specialist_config(self, specialist_id: str, config: dict) -> dict:
        path = self._config_path(specialist_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        merged = {**config, "specialist_id": specialist_id, "updated_at": _utc_now_iso()}
        # Validate interval_hours ∈ {2,4,24}
        interval = int(merged.get("interval_hours") or get_default_interval_hours())
        if interval not in (2, 4, 24):
            interval = get_default_interval_hours()
        merged["interval_hours"] = interval
        mode = str(merged.get("mode") or "manual").lower()
        merged["mode"] = mode if mode in ("manual", "recurring") else "manual"
        with self._lock:
            path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        return merged

    def get_last_successful_run(self, specialist_id: str) -> dict | None:
        runs = self.list_runs(specialist_id, limit=100)
        for run in runs:
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
        path = self._runs_dir(specialist_id) / f"{run_id}.json"
        with self._lock:
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    def complete_run(self, specialist_id: str, run_id: str, updates: dict) -> dict:
        path = self._runs_dir(specialist_id) / f"{run_id}.json"
        with self._lock:
            if path.exists():
                record = _read_json_file(path)
            else:
                record = {"run_id": run_id, "specialist_id": specialist_id}
            record.update(updates)
            record["completed_at"] = updates.get("completed_at") or _utc_now_iso()
            path.write_text(json.dumps(record, indent=2), encoding="utf-8")
        return record

    def list_runs(self, specialist_id: str, limit: int = 20) -> list[dict]:
        runs_dir = self._runs_dir(specialist_id)
        files = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: list[dict] = []
        with self._lock:
            for path in files[:limit]:
                out.append(_read_json_file(path))
        return out
