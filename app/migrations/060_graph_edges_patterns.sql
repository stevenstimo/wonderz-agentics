-- Platform Spec V5: Knowledge Graph — graph_edges + patterns (sectie 8.2, 13)
-- Bij bestaande graph_edges (bijv. Supabase): CREATE IF NOT EXISTS wijzigt niets.

CREATE TABLE IF NOT EXISTS graph_edges (
  edge_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  from_id    TEXT NOT NULL,
  to_id      TEXT NOT NULL,
  edge_type  TEXT NOT NULL,
  attrs      JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_graph_edges_dedup
  ON graph_edges(from_id, to_id, edge_type);

CREATE INDEX IF NOT EXISTS idx_graph_from
  ON graph_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_graph_to
  ON graph_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_graph_type
  ON graph_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_graph_from_type
  ON graph_edges(from_id, edge_type);

-- Patterns tabel (voor PatternRegistered event)
CREATE TABLE IF NOT EXISTS patterns (
  pattern_id   TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  pattern_type TEXT CHECK (
    pattern_type IN ('pattern', 'anti_pattern')
  ) DEFAULT 'pattern',
  description  TEXT,
  tags         TEXT[] DEFAULT '{}',
  created_at   TIMESTAMPTZ DEFAULT now()
);
