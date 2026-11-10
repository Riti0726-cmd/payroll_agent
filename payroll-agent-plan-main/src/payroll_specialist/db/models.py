"""ORM for Neon `email_processing` — pipeline state only (not Snowflake payroll)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.timeutil import ISTDateTime, now_ist


class Base(DeclarativeBase):
    pass


class EmailProcessing(Base):
    __tablename__ = "email_processing"

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    # RFC 822 Message-ID; stable across folder moves (Graph REST ids are not).
    internet_message_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    sender_email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_cc: Mapped[str | None] = mapped_column(Text, nullable=True)
    payroll_specialist_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_categorized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_drafted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_time: Mapped[datetime] = mapped_column(
        ISTDateTime,
        nullable=False,
        default=now_ist,
    )
    email_received_dttm: Mapped[datetime | None] = mapped_column(ISTDateTime, nullable=True)
    email_sent_dttm: Mapped[datetime | None] = mapped_column(ISTDateTime, nullable=True)
    mail_categorization_time: Mapped[datetime | None] = mapped_column(ISTDateTime, nullable=True)
    mail_draft_time: Mapped[datetime | None] = mapped_column(ISTDateTime, nullable=True)
    mail_send_time: Mapped[datetime | None] = mapped_column(ISTDateTime, nullable=True)
    priority_rate: Mapped[str | None] = mapped_column(Text, nullable=True)
    qa_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    changelist_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    hitl_status: Mapped[str | None] = mapped_column(Text, nullable=True)
