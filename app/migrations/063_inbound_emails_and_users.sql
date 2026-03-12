-- Email Intake Channel §3.1: users table (for SenderMatcher) + inbound_emails audit trail.
-- users must exist before inbound_emails because inbound_emails.user_id REFERENCES users(id).

-- Users: id + email for SenderMatcher (email → user_id). Sync from auth on login or via trigger.
CREATE TABLE IF NOT EXISTS users (
  id    UUID PRIMARY KEY,
  email TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_users_email_lower ON users (LOWER(email));

-- Inbound emails: audit log of all received emails (accepted and rejected).
-- email_id = 'email:<message_id_hash>'; job_id references jobs(id) (app jobs PK is id).
CREATE TABLE IF NOT EXISTS inbound_emails (
  email_id           TEXT PRIMARY KEY,
  message_id         TEXT UNIQUE NOT NULL,
  from_address       TEXT NOT NULL,
  from_name          TEXT,
  subject            TEXT NOT NULL,
  body_raw           TEXT NOT NULL,
  body_clean         TEXT NOT NULL,
  received_at        TIMESTAMPTZ NOT NULL,
  processed_at        TIMESTAMPTZ,
  status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending',
    'accepted',
    'rejected_sender',
    'rejected_duplicate',
    'error'
  )),
  user_id            UUID REFERENCES users(id),
  job_id             UUID REFERENCES jobs(id),
  completeness_score FLOAT,
  error_detail       TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inbound_emails_status   ON inbound_emails (status);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_from     ON inbound_emails (from_address);
CREATE INDEX IF NOT EXISTS idx_inbound_emails_received ON inbound_emails (received_at DESC);
