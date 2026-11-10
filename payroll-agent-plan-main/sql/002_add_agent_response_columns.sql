-- Phase 2 agent JSON columns (safe if already present on Neon).
ALTER TABLE email_processing ADD COLUMN IF NOT EXISTS qa_response TEXT;
ALTER TABLE email_processing ADD COLUMN IF NOT EXISTS changelist_response TEXT;
