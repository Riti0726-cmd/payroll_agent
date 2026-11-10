-- Stable RFC 822 Message-ID so the Outlook add-in can find a row after the
-- email is moved between folders (Graph REST ids change on move). Forward-only.
-- Apply with: psql "$DATABASE_URL" -f sql/003_add_internet_message_id.sql

ALTER TABLE email_processing
    ADD COLUMN IF NOT EXISTS internet_message_id TEXT NULL;

CREATE INDEX IF NOT EXISTS ix_email_processing_internet_message_id
    ON email_processing (internet_message_id);
