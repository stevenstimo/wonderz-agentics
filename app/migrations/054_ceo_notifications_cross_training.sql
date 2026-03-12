-- P8: A/B validation + Cross-agent learning
-- ceo_notifications: CEO notificaties (o.a. training_ineffective)
CREATE TABLE IF NOT EXISTS ceo_notifications (
  notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  related_id TEXT,
  is_read BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ceo_notifications_unread ON ceo_notifications(is_read) WHERE is_read = false;

-- cross_training_proposals: voorstellen voor cross-agent training
CREATE TABLE IF NOT EXISTS cross_training_proposals (
  proposal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lesson_id TEXT NOT NULL,
  source_agent_id TEXT,
  target_agent_ids JSONB NOT NULL DEFAULT '[]',
  reason TEXT,
  status TEXT CHECK (status IN ('pending', 'approved', 'rejected', 'completed')) DEFAULT 'pending',
  approved_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cross_training_proposals_status ON cross_training_proposals(status);
CREATE INDEX IF NOT EXISTS idx_cross_training_proposals_lesson ON cross_training_proposals(lesson_id);

-- development_points: ensure updated_at is set on status change (used by A/B validation)
ALTER TABLE development_points ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
-- Backfill: set updated_at = created_at where null
UPDATE development_points SET updated_at = COALESCE(updated_at, created_at, now()) WHERE updated_at IS NULL;
