"""EmailRepository — operational pipeline access to Neon `email_processing`."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, sessionmaker

from db.categories import parse_categories, serialize_categories
from db.database import get_session_factory
from db.models import EmailProcessing
from db.timeutil import ensure_ist, now_ist


class EmailNotFoundError(RuntimeError):
    pass


class UpsertResult(str, Enum):
    inserted = "inserted"
    skipped = "skipped"


@dataclass(frozen=True)
class IngestedEmailInput:
    """Minimal Graph-ingest payload (no schema changes)."""

    message_id: str
    sender_email: str
    sender_name: str | None = None
    subject: str | None = None
    body: str | None = None
    recipients: Sequence[str] = field(default_factory=list)
    cc: Sequence[str] = field(default_factory=list)
    conversation_id: str | None = None
    received_at: datetime | None = None
    sent_at: datetime | None = None
    internet_message_id: str | None = None


@dataclass(frozen=True)
class EmailData:
    email_id: str
    thread_id: str
    sender: str
    recipients: list[str]
    cc: list[str]
    subject: str
    body: str
    received_at: datetime


def _join_addresses(values: Sequence[str] | None) -> str | None:
    if not values:
        return None
    parts = [v.strip() for v in values if v and str(v).strip()]
    return ",".join(parts) if parts else None


def _split_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


class EmailRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _normalize_priority(priority: str | None) -> str:
        normalized = (priority or "").lower().strip()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return "medium"

    @staticmethod
    def _row_to_email_data(row: EmailProcessing) -> EmailData:
        received = row.email_received_dttm or row.ingestion_time
        return EmailData(
            email_id=row.message_id,
            thread_id=row.conversation_id or row.message_id,
            sender=row.sender_email,
            recipients=_split_addresses(row.payroll_specialist_email),
            cc=_split_addresses(row.email_cc),
            subject=row.subject or "",
            body=row.content or "",
            received_at=ensure_ist(received) or received,
        )

    def get_email(self, email_id: str) -> EmailData:
        with self._session_factory() as session:
            row = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(email_id))
            ).scalar_one_or_none()
            if row is None:
                raise EmailNotFoundError(f"Email {email_id} not found")
            return self._row_to_email_data(row)

    def is_processed(self, message_id: str, *, internet_message_id: str | None = None) -> bool:
        """True if this message was processed, under its current Graph id or, after a
        folder move gave it a new id, under the same internetMessageId."""
        match = EmailProcessing.message_id == str(message_id)
        if internet_message_id:
            match = match | (EmailProcessing.internet_message_id == str(internet_message_id))
        with self._session_factory() as session:
            row = session.execute(
                select(EmailProcessing)
                .where(match)
                .where(EmailProcessing.is_processed.is_(True))
                .limit(1)
            ).scalar_one_or_none()
            return row is not None

    def get_thread(self, conversation_id: str, *, limit: int | None = None) -> list[EmailData]:
        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.conversation_id == conversation_id)
                .order_by(EmailProcessing.ingestion_time.asc())
            )
            rows = list(session.execute(stmt).scalars().all())
            if limit is not None:
                rows = rows[-limit:]
            return [self._row_to_email_data(row) for row in rows]

    def get_unclassified_emails(self, limit: int = 50) -> list[EmailData]:
        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.is_categorized.is_(False))
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_email_data(row) for row in rows]

    def upsert_ingested_email(self, *, message: IngestedEmailInput) -> UpsertResult:
        """Insert if new message_id; skip if exists (preserve classification)."""
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == message.message_id)
            ).scalar_one_or_none()
            if existing is not None:
                # Backfill rows ingested before internet_message_id was captured.
                if message.internet_message_id and not existing.internet_message_id:
                    existing.internet_message_id = message.internet_message_id
                    session.commit()
                return UpsertResult.skipped

            now = now_ist()
            received = ensure_ist(message.received_at) or now
            conv = message.conversation_id or message.message_id
            session.add(
                EmailProcessing(
                    message_id=message.message_id,
                    internet_message_id=message.internet_message_id or None,
                    sender_email=message.sender_email,
                    name=message.sender_name,
                    payroll_specialist_email=_join_addresses(message.recipients),
                    email_cc=_join_addresses(message.cc),
                    conversation_id=conv,
                    subject=message.subject,
                    content=message.body,
                    email_received_dttm=received,
                    email_sent_dttm=ensure_ist(message.sent_at),
                    ingestion_time=now,
                    is_categorized=False,
                    is_drafted=False,
                    is_processed=False,
                )
            )
            session.commit()
            return UpsertResult.inserted

    def save_classification(
        self,
        *,
        email_id: str,
        categories: list[Any] | str,
        priority: str = "medium",
    ) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(email_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {email_id} not found")

            if isinstance(categories, str):
                existing.category = serialize_categories(parse_categories(categories) or [categories])
            else:
                existing.category = serialize_categories(categories)
            existing.priority_rate = self._normalize_priority(priority)
            existing.is_categorized = True
            existing.mail_categorization_time = now_ist()
            session.commit()

    def save_qa_response(self, message_id: str, payload: dict) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")
            existing.qa_response = json.dumps(payload, default=str)
            session.commit()

    def save_changelist_response(self, message_id: str, payload: dict) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")
            existing.changelist_response = json.dumps(payload, default=str)
            session.commit()

    def get_changelist_response(self, message_id: str) -> dict | None:
        """Return parsed changelist_response JSON, or None if missing/invalid."""
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None or not existing.changelist_response:
                return None
            raw = existing.changelist_response
            try:
                payload = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                return None
            return payload if isinstance(payload, dict) else None

    def save_draft(self, *, email_id: str, draft_content: str) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(email_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {email_id} not found")
            existing.draft_content = draft_content
            existing.is_drafted = True
            existing.is_processed = False
            existing.mail_draft_time = now_ist()
            existing.hitl_status = "pending"
            session.commit()

    def set_hitl_status(
        self,
        message_id: str,
        status: str,
        *,
        draft_body: str | None = None,
    ) -> dict:
        """Update HITL status; optionally replace draft body. Returns workbench row dict."""
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")
            existing.hitl_status = status
            if draft_body is not None:
                existing.draft_content = draft_body
            session.commit()
            return self._row_to_workbench_dict(existing)

    def patch_changelist_item(
        self,
        message_id: str,
        *,
        status: str | None = None,
        lines: list[dict] | None = None,
    ) -> dict:
        """Update HITL status and/or changelist line edits. Returns workbench row dict."""
        from changelists_mapping import apply_line_edits

        if status is None and lines is None:
            raise ValueError("Provide status and/or lines")
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")
            if status is not None:
                existing.hitl_status = status
            if lines is not None:
                raw = existing.changelist_response
                try:
                    payload = json.loads(raw) if isinstance(raw, str) and raw else {}
                except (json.JSONDecodeError, TypeError):
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                existing.changelist_response = json.dumps(
                    apply_line_edits(payload, lines), default=str
                )
            session.commit()
            return self._row_to_workbench_dict(existing)

    def list_pending_drafts(self, *, specialist_mailbox: str, limit: int = 200) -> list[dict]:
        """Drafted rows awaiting HITL (pending or null status)."""
        mailbox = (specialist_mailbox or "").strip()
        if not mailbox:
            return []
        needle = f"%{mailbox.lower()}%"
        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.is_drafted.is_(True))
                .where(EmailProcessing.draft_content.is_not(None))
                .where(
                    (EmailProcessing.hitl_status.is_(None))
                    | (EmailProcessing.hitl_status == "pending")
                )
                .where(func.lower(EmailProcessing.payroll_specialist_email).like(needle))
                .order_by(
                    EmailProcessing.mail_draft_time.desc().nulls_last(),
                    EmailProcessing.email_received_dttm.desc().nulls_last(),
                )
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_workbench_dict(row) for row in rows]

    def list_pending_changelists(self, *, specialist_mailbox: str, limit: int = 200) -> list[dict]:
        """Categorized changelist rows awaiting HITL."""
        mailbox = (specialist_mailbox or "").strip()
        if not mailbox:
            return []
        needle = f"%{mailbox.lower()}%"
        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.category.is_not(None))
                .where(func.lower(EmailProcessing.category).like("%changelist%"))
                .where(
                    (EmailProcessing.hitl_status.is_(None))
                    | (EmailProcessing.hitl_status == "pending")
                )
                .where(func.lower(EmailProcessing.payroll_specialist_email).like(needle))
                .order_by(EmailProcessing.email_received_dttm.desc().nulls_last())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            out: list[dict] = []
            for row in rows:
                cats = parse_categories(row.category) or []
                if "changelist" not in cats:
                    continue
                out.append(self._row_to_workbench_dict(row))
            return out

    @staticmethod
    def _row_to_workbench_dict(row: EmailProcessing) -> dict:
        return {
            "message_id": row.message_id,
            "subject": row.subject,
            "sender_email": row.sender_email,
            "draft_content": row.draft_content,
            "hitl_status": row.hitl_status,
            "category": row.category,
            "sub_content": row.sub_content,
            "changelist_response": row.changelist_response,
            "email_received_dttm": row.email_received_dttm,
        }

    def save_extracts(self, *, message_id: str, extracts: dict[str, Any]) -> None:
        """Persist extracts as JSON in sub_content (string values only)."""
        payload = {str(k): str(v) for k, v in extracts.items() if v is not None}
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")
            existing.sub_content = json.dumps(payload, default=str) if payload else None
            session.commit()

    def list_open_queue(self, *, specialist_mailbox: str, limit: int = 200) -> list[dict]:
        """Return open categorized rows for a specialist mailbox as queue-mapping dicts."""
        mailbox = (specialist_mailbox or "").strip()
        if not mailbox:
            return []

        priority_order = case(
            (EmailProcessing.priority_rate == "high", 1),
            (EmailProcessing.priority_rate == "medium", 2),
            (EmailProcessing.priority_rate == "low", 3),
            else_=2,
        )
        needle = f"%{mailbox.lower()}%"

        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.is_categorized.is_(True))
                .where(
                    (EmailProcessing.hitl_status.is_(None))
                    | (
                        func.lower(EmailProcessing.hitl_status).in_(
                            ("pending", "needs_clarification")
                        )
                    )
                )
                .where(func.lower(EmailProcessing.payroll_specialist_email).like(needle))
                .order_by(priority_order.asc(), EmailProcessing.email_received_dttm.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_queue_dict(row) for row in rows]

    @staticmethod
    def _row_to_queue_dict(row: EmailProcessing) -> dict:
        return {
            "message_id": row.message_id,
            "subject": row.subject,
            "category": row.category,
            "priority_rate": row.priority_rate,
            "email_received_dttm": row.email_received_dttm,
            "content": row.content,
            "sub_content": row.sub_content,
            "is_drafted": row.is_drafted,
            "draft_content": row.draft_content,
        }

    def patch_queue_item(
        self,
        *,
        message_id: str,
        done: bool | None = None,
        priority: int | None = None,
    ) -> dict:
        """Update open-queue fields. Returns queue-mapping dict for the row."""
        from queue_mapping import priority_to_rate

        if done is None and priority is None:
            raise ValueError("Provide done and/or priority")

        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(message_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {message_id} not found")

            if priority is not None:
                existing.priority_rate = priority_to_rate(int(priority))
            if done is True:
                existing.is_processed = True
                existing.hitl_status = "done"
            session.commit()
            return self._row_to_queue_dict(existing)

    def get_email_record(
        self,
        *,
        specialist_mailbox: str,
        message_id: str | None = None,
        internet_message_id: str | None = None,
    ) -> dict:
        """Single row for the Outlook add-in: REST id first, then internet_message_id.

        Scoped to the specialist mailbox so a caller cannot read another mailbox's rows.
        """
        mailbox = (specialist_mailbox or "").strip()
        rest_id = (message_id or "").strip()
        imid = (internet_message_id or "").strip()
        if not mailbox or not (rest_id or imid):
            raise EmailNotFoundError("Email not found")
        needle = f"%{mailbox.lower()}%"
        with self._session_factory() as session:
            row = None
            for column, value in (
                (EmailProcessing.message_id, rest_id),
                (EmailProcessing.internet_message_id, imid),
            ):
                if not value:
                    continue
                row = session.execute(
                    select(EmailProcessing)
                    .where(column == value)
                    .where(func.lower(EmailProcessing.payroll_specialist_email).like(needle))
                    .order_by(EmailProcessing.ingestion_time.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if row is not None:
                    break
            if row is None:
                raise EmailNotFoundError("Email not found")
            out = self._row_to_workbench_dict(row)
            out.update(self._row_to_queue_dict(row))
            out["is_categorized"] = row.is_categorized
            out["is_processed"] = row.is_processed
            return out

    def mark_processed(self, *, email_id: str, sent: bool = False) -> None:
        with self._session_factory() as session:
            existing = session.execute(
                select(EmailProcessing).where(EmailProcessing.message_id == str(email_id))
            ).scalar_one_or_none()
            if existing is None:
                raise EmailNotFoundError(f"Email {email_id} not found")
            existing.is_processed = True
            if sent:
                existing.mail_send_time = now_ist()
            session.commit()

    def list_history(
        self,
        *,
        specialist_mailbox: str,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Closed HITL rows for History workbench."""
        closed = ("done", "accepted", "discarded", "approved", "needs_clarification")
        mailbox = (specialist_mailbox or "").strip()
        if not mailbox:
            return []
        status_filter = (status or "").strip().lower()
        if status_filter in ("", "all"):
            statuses = closed
        elif status_filter in closed:
            statuses = (status_filter,)
        else:
            return []

        needle = f"%{mailbox.lower()}%"
        with self._session_factory() as session:
            stmt = (
                select(EmailProcessing)
                .where(EmailProcessing.hitl_status.in_(statuses))
                .where(func.lower(EmailProcessing.payroll_specialist_email).like(needle))
                .order_by(EmailProcessing.email_received_dttm.desc().nulls_last())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            return [self._row_to_history_dict(row) for row in rows]

    @staticmethod
    def _row_to_history_dict(row: EmailProcessing) -> dict:
        return {
            "message_id": row.message_id,
            "subject": row.subject,
            "category": row.category,
            "hitl_status": row.hitl_status,
            "priority_rate": row.priority_rate,
            "email_received_dttm": row.email_received_dttm,
            "content": row.content,
            "sub_content": row.sub_content,
        }

    def count_pipeline(self) -> dict[str, int]:
        with self._session_factory() as session:
            total = session.execute(select(func.count()).select_from(EmailProcessing)).scalar_one()
            categorized = session.execute(
                select(func.count())
                .select_from(EmailProcessing)
                .where(EmailProcessing.is_categorized.is_(True))
            ).scalar_one()
            drafted = session.execute(
                select(func.count())
                .select_from(EmailProcessing)
                .where(EmailProcessing.is_drafted.is_(True))
            ).scalar_one()
            open_queue = session.execute(
                select(func.count())
                .select_from(EmailProcessing)
                .where(EmailProcessing.is_categorized.is_(True))
                .where(
                    (EmailProcessing.hitl_status.is_(None))
                    | (
                        func.lower(EmailProcessing.hitl_status).in_(
                            ("pending", "needs_clarification")
                        )
                    )
                )
            ).scalar_one()
            return {
                "total": int(total or 0),
                "categorized": int(categorized or 0),
                "drafted": int(drafted or 0),
                "open_queue": int(open_queue or 0),
            }


@lru_cache(maxsize=1)
def get_email_repository() -> EmailRepository:
    return EmailRepository(get_session_factory())
