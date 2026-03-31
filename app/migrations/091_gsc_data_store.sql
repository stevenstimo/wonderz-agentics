-- GSC data store: dagelijkse performance per pagina per client
CREATE TABLE IF NOT EXISTS gsc_data_store (
  id              BIGSERIAL PRIMARY KEY,
  client_slug     TEXT NOT NULL,
  date            DATE NOT NULL,
  page            TEXT NOT NULL,
  query           TEXT,
  clicks          INTEGER NOT NULL DEFAULT 0,
  impressions     INTEGER NOT NULL DEFAULT 0,
  ctr             NUMERIC(6,4),
  position        NUMERIC(6,2),
  site_url        TEXT NOT NULL,
  fetched_at      TIMESTAMPTZ DEFAULT now(),
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Unieke constraint: één rij per client + datum + pagina + query
CREATE UNIQUE INDEX IF NOT EXISTS idx_gsc_data_store_unique
  ON gsc_data_store(client_slug, date, page, COALESCE(query, ''));

-- Index voor snelle lookups per client + periode
CREATE INDEX IF NOT EXISTS idx_gsc_data_store_client_date
  ON gsc_data_store(client_slug, date DESC);

-- Index voor pagina-niveau queries
CREATE INDEX IF NOT EXISTS idx_gsc_data_store_page
  ON gsc_data_store(client_slug, page, date DESC);

-- Backfill tracking: welke dagen zijn al opgehaald per client
CREATE TABLE IF NOT EXISTS gsc_sync_log (
  id              BIGSERIAL PRIMARY KEY,
  client_slug     TEXT NOT NULL,
  sync_date       DATE NOT NULL,
  rows_inserted   INTEGER DEFAULT 0,
  rows_updated    INTEGER DEFAULT 0,
  status          TEXT NOT NULL DEFAULT 'completed',
  error_message   TEXT,
  synced_at       TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_gsc_sync_log_unique
  ON gsc_sync_log(client_slug, sync_date);
