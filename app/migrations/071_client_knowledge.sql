-- Client Knowledge Hub — migration 071
-- Pre: client_knowledge was empty (0 rows), so we drop and recreate.

DROP TABLE IF EXISTS client_knowledge CASCADE;

-- Client datasources (one per source the user adds)
CREATE TABLE IF NOT EXISTS client_datasources (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL
        CHECK (source_type IN ('website_crawl', 'website_sitemap', 'text', 'file', 'product_feed')),
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    domain TEXT,
    sitemap_url TEXT,
    file_name TEXT,
    file_type TEXT,
    raw_text TEXT,
    feed_url TEXT,
    feed_splitting_tag TEXT,
    feed_identifier_tag TEXT,
    pages_found INTEGER DEFAULT 0,
    pages_processed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    error_detail TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

-- Client knowledge (chunks from all datasources)
CREATE TABLE IF NOT EXISTS client_knowledge (
    id BIGSERIAL PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
    datasource_id BIGINT REFERENCES client_datasources(id) ON DELETE CASCADE,
    source_url TEXT,
    page_title TEXT,
    chunk_text TEXT NOT NULL,
    embedding vector(1024),
    chunk_index INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    added_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_embedding
    ON client_knowledge USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_client
    ON client_knowledge(client_id);

CREATE INDEX IF NOT EXISTS idx_client_knowledge_datasource
    ON client_knowledge(datasource_id);

-- RPC for similarity search (optional; can also be done in app with raw SQL)
CREATE OR REPLACE FUNCTION match_client_knowledge (
    query_embedding vector(1024),
    match_client_id text,
    match_count int DEFAULT 5,
    similarity_threshold float DEFAULT 0.4
) RETURNS TABLE (
    chunk_text text,
    source_url text,
    page_title text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ck.chunk_text,
        ck.source_url,
        ck.page_title,
        1 - (ck.embedding <=> query_embedding) AS similarity
    FROM client_knowledge ck
    WHERE ck.client_id = match_client_id
      AND ck.is_active = true
      AND 1 - (ck.embedding <=> query_embedding) > similarity_threshold
    ORDER BY ck.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
