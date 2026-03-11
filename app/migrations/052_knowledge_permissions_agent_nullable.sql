-- Allow role-based permissions: agent_id can be NULL when role is set
ALTER TABLE knowledge_permissions ALTER COLUMN agent_id DROP NOT NULL;
