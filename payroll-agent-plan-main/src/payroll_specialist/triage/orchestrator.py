"""Triage orchestration: dedupe → thread → full per-email graph (UC-007–015, 016–020)."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from store import get_triage_store
from telemetry import step_span
from triage.mailbox import GraphMailboxPort, MailMessage, get_mailbox_port
from triage.processed import ProcessedMailPort, get_processed_mail_port
from triage.thread import assemble_current_request
from triage.window import compute_processing_window

logger = logging.getLogger("payroll-specialist")

ProcessEmailFn = Callable[[str], Awaitable[dict[str, Any]]]
ProgressFn = Callable[[dict[str, Any]], None]


def _classify_email_text(
    text: str,
    classify_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Heuristic offline classifier used when no LLM classify_fn is provided."""
    if classify_fn is not None:
        return classify_fn(text)

    lower = text.lower()
    base = {
        "employee_id": None,
        "pay_period": None,
        "client_id": None,
        "employee_name": None,
        "effective_date": None,
    }
    if any(k in lower for k in ("benefit", "enrollment", "workers comp", "tax filing", "w-2 advice")):
        dest = (
            "benefits"
            if "benefit" in lower
            else "tax"
            if "tax" in lower
            else "workers_comp"
            if "workers" in lower
            else "other"
        )
        return {
            **base,
            "category": "out_of_scope",
            "intent": text[:200],
            "confidence": 0.7,
            "oos_destination": dest,
        }
    if any(k in lower for k in ("direct deposit", "bank account", "w-4", "address change")):
        return {
            **base,
            "category": "changelist",
            "intent": text[:200],
            "confidence": 0.7,
            "oos_destination": None,
        }
    if any(k in lower for k in ("approve", "timesheet", "off-cycle", "escalat")):
        return {
            **base,
            "category": "todo",
            "intent": text[:200],
            "confidence": 0.7,
            "oos_destination": None,
        }
    return {
        **base,
        "category": "qa",
        "intent": text[:200],
        "confidence": 0.7,
        "oos_destination": None,
    }


def _parse_received(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _prior_bodies_in_window(messages: list[MailMessage], current: MailMessage) -> list[str]:
    conv = current.conversation_id or current.id
    current_ts = _parse_received(current.received_at)
    priors: list[tuple[datetime, str]] = []
    for msg in messages:
        if msg.id == current.id:
            continue
        other_conv = msg.conversation_id or msg.id
        if other_conv != conv:
            continue
        try:
            ts = _parse_received(msg.received_at)
        except ValueError:
            continue
        if ts < current_ts:
            body = (msg.body or msg.body_preview or "").strip()
            if body:
                priors.append((ts, body))
    priors.sort(key=lambda x: x[0])
    return [body for _, body in priors]


def _format_summary(
    *,
    specialist_id: str,
    run_id: str,
    mailbox_id: str,
    window: dict,
    results: list[dict],
) -> str:
    skipped = sum(1 for item in results if item.get("skipped"))
    failed = sum(1 for item in results if item.get("status") == "failed")
    succeeded = sum(1 for item in results if item.get("status") == "succeeded")
    counts: dict[str, int] = {}
    for item in results:
        if item.get("skipped"):
            continue
        cat = item.get("category") or "unknown"
        counts[cat] = counts.get(cat, 0) + 1

    lines = [
        "**Triage Run Summary**",
        f"- Specialist: `{specialist_id}`",
        f"- Run ID: `{run_id}`",
        f"- Mailbox: `{mailbox_id}`",
        f"- Window: {window.get('window_start')} → {window.get('window_end')} ({window.get('basis')})",
        f"- Emails in window: {len(results)}",
        f"- Processed: {succeeded}, skipped: {skipped}, failed: {failed}",
        f"- Categories: {', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'none'}",
        "",
        "**Per-email results**",
    ]
    for item in results:
        if item.get("skipped"):
            lines.append(f"- `{item.get('message_id')}`: **skipped** (already processed)")
            continue
        if item.get("status") == "failed":
            lines.append(f"- `{item.get('message_id')}`: **failed**")
            continue
        oos = item.get("oos_destination")
        oos_bit = f" → {oos}" if oos else ""
        lines.append(
            f"- `{item.get('message_id')}`: **{item.get('category')}**{oos_bit} "
            f"(read={item.get('is_read')})"
        )
    if not results:
        lines.append("- (no messages in window)")
    return "\n".join(lines)


class TriageOrchestrator:
    def __init__(
        self,
        *,
        store=None,
        mailbox: GraphMailboxPort | None = None,
        classify_fn: Optional[Callable[[str], dict]] = None,
        process_email_fn: Optional[ProcessEmailFn] = None,
        processed_store: ProcessedMailPort | None = None,
        email_repo: Any = None,
    ) -> None:
        self.store = store or get_triage_store()
        self._mailbox = mailbox
        self.classify_fn = classify_fn
        self.process_email_fn = process_email_fn
        self.processed_store = processed_store
        self.email_repo = email_repo

    @property
    def mailbox(self) -> GraphMailboxPort:
        if self._mailbox is None:
            self._mailbox = get_mailbox_port()
        return self._mailbox

    @mailbox.setter
    def mailbox(self, value: GraphMailboxPort) -> None:
        self._mailbox = value

    def _resolved_processed(self, specialist_id: str) -> ProcessedMailPort:
        if self.processed_store is not None:
            return self.processed_store
        return get_processed_mail_port(specialist_id=specialist_id)

    def _resolved_email_repo(self) -> Any:
        if self.email_repo is not None:
            return self.email_repo
        if not os.environ.get("DATABASE_URL", "").strip():
            raise RuntimeError(
                "DATABASE_URL is required for triage Neon persistence. Demo/local email_repo fallback is disabled."
            )
        from db.repository import get_email_repository

        return get_email_repository()

    def _persist_queue_row(
        self,
        *,
        repo: Any,
        msg: MailMessage,
        mailbox_id: str,
        triage: dict,
        priority: str = "medium",
    ) -> None:
        from db.repository import IngestedEmailInput

        received: datetime | None
        try:
            received = datetime.fromisoformat(msg.received_at.replace("Z", "+00:00"))
        except ValueError:
            received = None

        repo.upsert_ingested_email(
            message=IngestedEmailInput(
                message_id=msg.id,
                sender_email=(msg.from_address or "unknown@invalid").strip() or "unknown@invalid",
                subject=msg.subject or None,
                body=(msg.body or msg.body_preview or None),
                recipients=[mailbox_id],
                conversation_id=msg.conversation_id or msg.id,
                received_at=received,
                internet_message_id=getattr(msg, "internet_message_id", "") or None,
            )
        )
        category = triage.get("category") or "todo"
        repo.save_classification(
            email_id=msg.id,
            categories=[category],
            priority=priority,
        )
        extracts = {
            key: triage.get(key)
            for key in (
                "employee_id",
                "client_id",
                "employee_name",
                "effective_date",
                "pay_period",
                "oos_destination",
                "change_type",
                "new_value",
                "previous_value",
                "system_target",
            )
            if triage.get(key) is not None
        }
        if extracts:
            repo.save_extracts(message_id=msg.id, extracts=extracts)

    def _persist_workbench_payloads(
        self,
        *,
        repo: Any,
        msg: MailMessage,
        triage: dict,
        payload: dict,
    ) -> None:
        draft = (payload.get("draft") or "").strip()
        if draft:
            repo.save_draft(email_id=msg.id, draft_content=draft)

        validation = payload.get("validation") or {}
        if str(validation.get("status") or "").lower() in (
            "needs_clarification",
            "invalid",
        ):
            setter = getattr(repo, "set_hitl_status", None)
            if callable(setter):
                try:
                    setter(msg.id, "needs_clarification")
                except Exception:
                    logger.exception("set_hitl_status failed message_id=%s", msg.id)

        if (triage.get("category") or "") != "changelist":
            return

        from changelists_mapping import merge_changelist_payload

        rich = payload.get("changelist")
        if isinstance(rich, dict) and (
            (isinstance(rich.get("changes"), list) and rich["changes"])
            or (isinstance(rich.get("lines"), list) and rich["lines"])
        ):
            shell = dict(rich)
            if not shell.get("title"):
                shell["title"] = (msg.subject or "").strip() or "(no subject)"
            if not shell.get("clientId"):
                shell["clientId"] = triage.get("client_id") or "unknown"
        else:
            shell = {
                "clientId": triage.get("client_id") or "unknown",
                "title": (msg.subject or "").strip() or "(no subject)",
                "lines": [],
                "status": "pending",
            }
            if isinstance(rich, dict):
                shell = {**shell, **{k: v for k, v in rich.items() if v is not None}}

        existing = None
        getter = getattr(repo, "get_changelist_response", None)
        if callable(getter):
            try:
                existing = getter(msg.id)
            except Exception:
                existing = None
        repo.save_changelist_response(msg.id, merge_changelist_payload(existing, shell))

    async def run(
        self,
        *,
        specialist_id: str,
        mailbox_id: str | None = None,
        on_progress: ProgressFn | None = None,
    ) -> dict[str, Any]:
        def emit(event: dict[str, Any]) -> None:
            if on_progress is None:
                return
            try:
                on_progress(event)
            except Exception:
                logger.exception("triage on_progress callback failed")

        with step_span("load_config", specialist_id=specialist_id):
            config = self.store.get_specialist_config(specialist_id)
            effective_mailbox = mailbox_id or config.get("mailbox_id") or f"mailbox-{specialist_id}"
            # Strip placeholder prefix when specialist_id is already an email (delegated Graph).
            if str(effective_mailbox).startswith("mailbox-"):
                candidate = str(effective_mailbox)[len("mailbox-") :]
                if "@" in candidate:
                    effective_mailbox = candidate
                elif "@" in str(specialist_id or ""):
                    effective_mailbox = str(specialist_id).strip()
            if mailbox_id and mailbox_id != config.get("mailbox_id"):
                config = self.store.save_specialist_config(
                    specialist_id, {**config, "mailbox_id": effective_mailbox}
                )
            self.mailbox.bind_specialist(specialist_id, effective_mailbox)

        processed = self._resolved_processed(specialist_id)

        with step_span("create_run", specialist_id=specialist_id):
            run_id = str(uuid.uuid4())
            self.store.create_run(
                specialist_id,
                {
                    "run_id": run_id,
                    "mailbox_id": effective_mailbox,
                    "status": "running",
                    "mode": config.get("mode", "manual"),
                },
            )

        with step_span("processing_window", specialist_id=specialist_id):
            last = self.store.get_last_successful_run(specialist_id)
            window = compute_processing_window(
                lookback_days=int(config.get("lookback_days") or 7),
                last_successful_run=last,
            )

        with step_span("retrieve_emails", mailbox_id=effective_mailbox):
            messages: list[MailMessage] = self.mailbox.list_messages(
                effective_mailbox,
                window_start=window["window_start"],
                window_end=window["window_end"],
            )

        total = len(messages)
        emit(
            {
                "type": "run_started",
                "runId": run_id,
                "mailbox": effective_mailbox,
                "total": total,
            }
        )

        results: list[dict] = []
        for index, msg in enumerate(messages, start=1):
            subject = (msg.subject or "").strip()
            emit(
                {
                    "type": "email_started",
                    "index": index,
                    "total": total,
                    "messageId": msg.id,
                    "subject": subject,
                }
            )
            with step_span("process_email", message_id=msg.id):
                imid = getattr(msg, "internet_message_id", "") or None
                if processed.is_processed(msg.id, internet_message_id=imid):
                    with step_span("dedupe_skip", message_id=msg.id):
                        row = {
                            "message_id": msg.id,
                            "conversation_id": msg.conversation_id or msg.id,
                            "is_read": msg.is_read,
                            "skipped": True,
                            "status": "skipped",
                            "category": None,
                        }
                        results.append(row)
                        emit(
                            {
                                "type": "email_finished",
                                "index": index,
                                "total": total,
                                "messageId": msg.id,
                                "subject": subject,
                                "status": "skipped",
                                "category": None,
                            }
                        )
                    continue

                body = (msg.body or msg.body_preview or "").strip()
                conv = msg.conversation_id or msg.id
                with step_span("thread_load", conversation_id=conv):
                    prior = _prior_bodies_in_window(messages, msg)
                    query = assemble_current_request(
                        subject=msg.subject or "",
                        current_body=body,
                        prior_bodies=prior,
                    )

                try:
                    if self.process_email_fn is not None:
                        payload = await self.process_email_fn(query)
                    else:
                        with step_span("classifier"):
                            triage = _classify_email_text(query, self.classify_fn)
                        payload = {"triage": triage, "draft": None, "qa_findings": None}

                    triage = payload.get("triage") or {}
                    cl = payload.get("changelist") if isinstance(payload.get("changelist"), dict) else {}
                    priority = str(cl.get("priority_rate") or "medium")
                    repo = self._resolved_email_repo()
                    with step_span("neon_persist", message_id=msg.id):
                        try:
                            self._persist_queue_row(
                                repo=repo,
                                msg=msg,
                                mailbox_id=effective_mailbox,
                                triage=triage,
                                priority=priority,
                            )
                            self._persist_workbench_payloads(
                                repo=repo,
                                msg=msg,
                                triage=triage,
                                payload=payload,
                            )
                        except Exception as neon_exc:
                            logger.exception(
                                "Neon queue persist failed message_id=%s", msg.id
                            )
                            row = {
                                "message_id": msg.id,
                                "conversation_id": conv,
                                "is_read": msg.is_read,
                                "skipped": False,
                                "status": "failed",
                                "error": f"Neon persist failed: {neon_exc}",
                                "category": triage.get("category"),
                            }
                            results.append(row)
                            emit(
                                {
                                    "type": "email_finished",
                                    "index": index,
                                    "total": total,
                                    "messageId": msg.id,
                                    "subject": subject,
                                    "status": "failed",
                                    "category": triage.get("category"),
                                    "error": row["error"],
                                }
                            )
                            continue

                    processed.mark_processed(msg.id, internet_message_id=imid)
                    row = {
                        "message_id": msg.id,
                        "conversation_id": conv,
                        "is_read": msg.is_read,
                        "skipped": False,
                        "status": "succeeded",
                        "category": triage.get("category"),
                        "intent": triage.get("intent"),
                        "confidence": triage.get("confidence"),
                        "employee_id": triage.get("employee_id"),
                        "client_id": triage.get("client_id"),
                        "employee_name": triage.get("employee_name"),
                        "effective_date": triage.get("effective_date"),
                        "pay_period": triage.get("pay_period"),
                        "oos_destination": triage.get("oos_destination"),
                        "draft": payload.get("draft"),
                        "qa_findings": payload.get("qa_findings"),
                    }
                    results.append(row)
                    emit(
                        {
                            "type": "email_finished",
                            "index": index,
                            "total": total,
                            "messageId": msg.id,
                            "subject": subject,
                            "status": "succeeded",
                            "category": triage.get("category"),
                        }
                    )
                except Exception as exc:
                    logger.exception("email processing failed message_id=%s", msg.id)
                    row = {
                        "message_id": msg.id,
                        "conversation_id": conv,
                        "is_read": msg.is_read,
                        "skipped": False,
                        "status": "failed",
                        "error": str(exc),
                        "category": None,
                    }
                    results.append(row)
                    emit(
                        {
                            "type": "email_finished",
                            "index": index,
                            "total": total,
                            "messageId": msg.id,
                            "subject": subject,
                            "status": "failed",
                            "category": None,
                            "error": str(exc),
                        }
                    )

        summary = _format_summary(
            specialist_id=specialist_id,
            run_id=run_id,
            mailbox_id=effective_mailbox,
            window=window,
            results=results,
        )

        succeeded_count = sum(1 for r in results if r.get("status") == "succeeded")
        failed_count = sum(1 for r in results if r.get("status") == "failed")
        skipped_count = sum(1 for r in results if r.get("skipped") or r.get("status") == "skipped")
        with step_span("finalize_run", run_id=run_id, email_count=succeeded_count):
            self.store.complete_run(
                specialist_id,
                run_id,
                {
                    "status": "succeeded",
                    "window_start": window["window_start"],
                    "window_end": window["window_end"],
                    "email_count": succeeded_count,
                    "results": results,
                    "summary": summary,
                },
            )

        emit(
            {
                "type": "run_finished",
                "runId": run_id,
                "succeeded": succeeded_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "summary": summary,
            }
        )

        return {
            "run_id": run_id,
            "mailbox_id": effective_mailbox,
            "specialist_config": config,
            "processing_window": window,
            "email_results": results,
            "triage_summary": summary,
        }


# Re-export for tests that may patch LocalProcessedMailStore via this module
from triage.processed import LocalProcessedMailStore  # noqa: E402

__all__ = ["TriageOrchestrator", "LocalProcessedMailStore", "_classify_email_text"]
