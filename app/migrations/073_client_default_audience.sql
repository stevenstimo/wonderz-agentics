-- Add default_audience to clients for SEO Tool pre-fill and client settings
ALTER TABLE clients
ADD COLUMN IF NOT EXISTS default_audience TEXT;
