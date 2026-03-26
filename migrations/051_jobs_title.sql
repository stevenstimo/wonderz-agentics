-- Add human-readable title for jobs list/detail.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS title TEXT;

