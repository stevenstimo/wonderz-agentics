-- GSC feedback loop: published URL on jobs + per-URL performance snapshots.
-- Applied: 2026-03

ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_url TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS job_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    measured_at TIMESTAMPTZ DEFAULT now(),
    url TEXT NOT NULL,
    clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    ctr DOUBLE PRECISION DEFAULT 0,
    average_position DOUBLE PRECISION,
    date_range_start DATE,
    date_range_end DATE,
    raw_data JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_job_performance_job ON job_performance(job_id);
CREATE INDEX IF NOT EXISTS idx_job_performance_url ON job_performance(url);
CREATE INDEX IF NOT EXISTS idx_jobs_published_url ON jobs(published_url)
    WHERE published_url IS NOT NULL;
