-- Email Intake Channel §3.2: jobs table — intake source and link to inbound email.
-- Backwards-compatible: existing rows get intake_source = 'browser'.

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS intake_source TEXT NOT NULL DEFAULT 'browser'
    CHECK (intake_source IN ('browser', 'email')),
  ADD COLUMN IF NOT EXISTS inbound_email_id TEXT REFERENCES inbound_emails(email_id);
