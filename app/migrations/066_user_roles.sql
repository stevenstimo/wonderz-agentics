-- User roles table for auth middleware (role lookup per user)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id  UUID PRIMARY KEY,
    role     TEXT NOT NULL DEFAULT 'member',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);
