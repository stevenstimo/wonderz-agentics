-- HR blocked-job notifier: dedup key columns + unique index (concurrent inserts from job_pipeline + nexus_pipeline).
-- Run: psql "$DATABASE_URL" -f migrations/050_agent_improvements_hr_blocked_dedup.sql

ALTER TABLE agent_improvements ADD COLUMN IF NOT EXISTS hr_blocked_job_id UUID;
ALTER TABLE agent_improvements ADD COLUMN IF NOT EXISTS hr_missing_role_key TEXT;

-- Remove duplicate rows for same job + slot (keep newest by created_at).
DELETE FROM agent_improvements a
WHERE a.id IN (
    SELECT id
    FROM (
        SELECT
            ai.id,
            ROW_NUMBER() OVER (
                PARTITION BY
                    (NULLIF(trim(ai.details::text), '')::jsonb->>'job_id'),
                    (NULLIF(trim(ai.details::text), '')::jsonb->>'missing_role_key')
                ORDER BY ai.created_at DESC NULLS LAST, ai.id DESC
            ) AS rn
        FROM agent_improvements ai
        WHERE ai.source = 'hr_blocked_job_notifier'
          AND ai.details IS NOT NULL
          AND trim(ai.details::text) <> ''
          AND left(trim(ai.details::text), 1) = '{'
    ) t
    WHERE t.rn > 1
);

UPDATE agent_improvements
SET
    hr_blocked_job_id = (NULLIF(trim(details::text), '')::jsonb->>'job_id')::uuid,
    hr_missing_role_key = NULLIF(
        trim((NULLIF(trim(details::text), '')::jsonb->>'missing_role_key')),
        ''
    )
WHERE source = 'hr_blocked_job_notifier'
  AND details IS NOT NULL
  AND trim(details::text) <> ''
  AND left(trim(details::text), 1) = '{'
  AND (NULLIF(trim(details::text), '')::jsonb ? 'job_id')
  AND hr_blocked_job_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_improvements_hr_blocked_job_role
ON agent_improvements (hr_blocked_job_id, hr_missing_role_key)
WHERE hr_blocked_job_id IS NOT NULL AND hr_missing_role_key IS NOT NULL;
