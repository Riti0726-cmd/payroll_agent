-- Add HITL review status for drafts / change lists (forward-only).
-- Apply with: psql "$DATABASE_URL" -f sql/002_add_hitl_status.sql

ALTER TABLE email_processing
    ADD COLUMN IF NOT EXISTS hitl_status TEXT NULL;
