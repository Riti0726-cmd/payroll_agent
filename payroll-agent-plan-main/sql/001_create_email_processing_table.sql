-- Bootstrap email_processing (forward-only). Prefer ORM if this drifts.
-- Apply with: psql "postgresql://..." -f sql/001_create_email_processing_table.sql

CREATE TABLE IF NOT EXISTS email_processing (
    message_id TEXT PRIMARY KEY,
    sender_email TEXT NOT NULL,
    name TEXT,
    subject TEXT,
    content TEXT,
    sub_content TEXT,
    email_cc TEXT,
    payroll_specialist_email TEXT,
    conversation_id TEXT,
    category TEXT,
    draft_content TEXT,
    is_categorized BOOLEAN NOT NULL DEFAULT FALSE,
    is_drafted BOOLEAN NOT NULL DEFAULT FALSE,
    is_processed BOOLEAN NOT NULL DEFAULT FALSE,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    email_received_dttm TIMESTAMPTZ,
    email_sent_dttm TIMESTAMPTZ,
    mail_categorization_time TIMESTAMPTZ,
    mail_draft_time TIMESTAMPTZ,
    mail_send_time TIMESTAMPTZ,
    priority_rate TEXT,
    qa_response TEXT,
    changelist_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_processing_category ON email_processing (category);
CREATE INDEX IF NOT EXISTS idx_email_processing_conversation ON email_processing (conversation_id);
CREATE INDEX IF NOT EXISTS idx_email_processing_queue
    ON email_processing (is_processed, is_drafted, priority_rate DESC, mail_categorization_time);
