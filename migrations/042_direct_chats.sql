-- Migration 042: Direct Chat (Platform Spec v1.1 — Direct Chat Feature)
-- Run: psql "$DATABASE_URL" -f migrations/042_direct_chats.sql
-- Chat ID format: DC-YYYY-MM-### (e.g. DC-2026-02-001)

CREATE TABLE IF NOT EXISTS direct_chats (
  chat_id          TEXT PRIMARY KEY,
  agent_id         TEXT NOT NULL REFERENCES hired_agents(agent_id) ON DELETE CASCADE,
  user_id          TEXT NOT NULL,
  title            TEXT,
  message_count    INTEGER DEFAULT 0,
  token_used       INTEGER DEFAULT 0,
  created_at       TIMESTAMPTZ DEFAULT now(),
  last_message_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS direct_chat_messages (
  message_id   BIGSERIAL PRIMARY KEY,
  chat_id      TEXT NOT NULL REFERENCES direct_chats(chat_id) ON DELETE CASCADE,
  role         TEXT NOT NULL CHECK (role IN ('user', 'agent')),
  content      TEXT NOT NULL,
  token_usage  INTEGER DEFAULT 0,
  created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_direct_chats_agent ON direct_chats(agent_id);
CREATE INDEX IF NOT EXISTS idx_direct_chats_user ON direct_chats(user_id);
CREATE INDEX IF NOT EXISTS idx_direct_chats_last_message ON direct_chats(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_direct_chat_messages_chat ON direct_chat_messages(chat_id);
