-- Platform Spec V6: Artifact tracking — evidence persistent opslaan (sectie 10)

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id   TEXT PRIMARY KEY,
  artifact_type TEXT NOT NULL,
  locator       TEXT NOT NULL,
  checksum      TEXT,
  git_commit    TEXT,
  file_path     TEXT,
  line_start    INTEGER,
  line_end      INTEGER,
  symbol_name   TEXT,
  is_stale      BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS citations (
  citation_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id           TEXT,
  job_id            TEXT,
  artifact_id       TEXT REFERENCES artifacts(artifact_id),
  location          TEXT,
  file_path         TEXT,
  line_start        INTEGER,
  line_end          INTEGER,
  git_commit        TEXT,
  symbol_name       TEXT,
  excerpt_summary   TEXT,
  is_stale          BOOLEAN DEFAULT false,
  created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_citations_task ON citations(task_id);
CREATE INDEX IF NOT EXISTS idx_citations_artifact ON citations(artifact_id);
