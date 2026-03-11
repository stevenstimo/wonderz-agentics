-- Migration 049: Add 'none' to permission_level CHECK
-- Voor blokkade van agents op document/client/agency niveau

ALTER TABLE knowledge_permissions
  DROP CONSTRAINT IF EXISTS knowledge_permissions_permission_level_check;

ALTER TABLE knowledge_permissions
  ADD CONSTRAINT knowledge_permissions_permission_level_check
  CHECK (permission_level IN ('read', 'write', 'admin', 'none'));
