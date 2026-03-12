-- Platform Spec V3: Lessons lifecycle — lesson_status, usage_count, conflicts (sectie 14.1)
-- Run only when lessons table exists (e.g. after Supabase/platform schema).

-- Uitbreidingen op lessons tabel (platform spec sectie 14.1)
ALTER TABLE lessons
  ADD COLUMN IF NOT EXISTS lesson_status TEXT DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_confirmed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS superseded_by TEXT REFERENCES lessons(lesson_id);

ALTER TABLE lessons DROP CONSTRAINT IF EXISTS chk_lessons_lesson_status;
ALTER TABLE lessons ADD CONSTRAINT chk_lessons_lesson_status
  CHECK (lesson_status IS NULL OR lesson_status IN (
    'active', 'superseded', 'invalidated', 'stale', 'pending', 'rejected'
  ));

-- Conflict tracking tabel
CREATE TABLE IF NOT EXISTS lesson_conflicts (
  conflict_id BIGSERIAL PRIMARY KEY,
  lesson_a TEXT REFERENCES lessons(lesson_id),
  lesson_b TEXT REFERENCES lessons(lesson_id),
  detected_at TIMESTAMPTZ DEFAULT now(),
  resolved_by TEXT,
  resolution TEXT CHECK (resolution IN (
    'a_prevails', 'b_prevails',
    'both_invalidated', 'merged'
  )),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_lc_lesson_a ON lesson_conflicts(lesson_a);
CREATE INDEX IF NOT EXISTS idx_lc_lesson_b ON lesson_conflicts(lesson_b);
