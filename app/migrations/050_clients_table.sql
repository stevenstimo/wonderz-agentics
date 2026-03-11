-- Clients table: user-scoped client entities (agency_clients was legacy name)
-- Referenced by client_platform_configs.client_slug and client_integrations.client_slug
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL,
    client_name TEXT NOT NULL,
    slug TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);
CREATE INDEX IF NOT EXISTS idx_clients_slug ON clients(slug);
