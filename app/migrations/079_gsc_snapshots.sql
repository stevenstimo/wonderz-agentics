-- GSC full snapshots for storage (500 rows); UI still gets top 10 via dashboard API.
CREATE TABLE IF NOT EXISTS gsc_snapshots (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL,
    date_range_start DATE,
    date_range_end DATE,
    queries JSONB,
    pages JSONB,
    totals JSONB,
    fetched_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gsc_snapshots_client ON gsc_snapshots(client_id);
CREATE INDEX IF NOT EXISTS idx_gsc_snapshots_fetched ON gsc_snapshots(fetched_at DESC);
