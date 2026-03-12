-- Inbox feature: chat_id on inbound_emails, extended status, inbox_allowed_senders.
-- Run after 065. Jobs PK is id (UUID); we reference jobs(id).

-- 1a. Add chat_id to inbound_emails
ALTER TABLE inbound_emails
  ADD COLUMN IF NOT EXISTS chat_id TEXT REFERENCES direct_chats(chat_id) ON DELETE SET NULL;

-- 1a. Extend status: drop old CHECK, add new one (keep old values for existing rows)
ALTER TABLE inbound_emails DROP CONSTRAINT IF EXISTS inbound_emails_status_check;
ALTER TABLE inbound_emails ADD CONSTRAINT inbound_emails_status_check CHECK (status IN (
  'pending',
  'accepted',
  'rejected_sender',
  'rejected_duplicate',
  'error',
  'new',
  'analyzing',
  'in_chat',
  'plan_ready',
  'converted_to_job'
));

-- 1b. Allowed senders (allowlist for inbox)
CREATE TABLE IF NOT EXISTS inbox_allowed_senders (
  sender_id    BIGSERIAL PRIMARY KEY,
  email        TEXT NOT NULL UNIQUE,
  user_id      TEXT NOT NULL,
  display_name TEXT,
  is_active    BOOLEAN DEFAULT true,
  added_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_inbox_senders_email ON inbox_allowed_senders(email);

-- Seed: only inserts when the user exists in public.users (no hardcoded UUIDs).
-- Ensure stevenstimo@gmail.com, timo@newfoundterritory.nl and neil@newfoundterritory.nl
-- exist in public.users (or sync from auth) before/after running this migration.
INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'stevenstimo@gmail.com', id::TEXT, 'Timo'
FROM users WHERE LOWER(email) = 'stevenstimo@gmail.com' LIMIT 1
ON CONFLICT (email) DO NOTHING;

INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'timo@newfoundterritory.nl', (SELECT id::TEXT FROM users WHERE LOWER(email) = 'stevenstimo@gmail.com' LIMIT 1), 'Timo (NFT)'
FROM users WHERE LOWER(email) = 'stevenstimo@gmail.com' LIMIT 1
ON CONFLICT (email) DO NOTHING;

INSERT INTO inbox_allowed_senders (email, user_id, display_name)
SELECT 'neil@newfoundterritory.nl', id::TEXT, 'Neil'
FROM users WHERE LOWER(email) = 'neil@newfoundterritory.nl' LIMIT 1
ON CONFLICT (email) DO NOTHING;
