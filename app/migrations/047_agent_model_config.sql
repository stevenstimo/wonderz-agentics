ALTER TABLE hired_agents
ADD COLUMN IF NOT EXISTS model_config JSONB DEFAULT '{
  "model": "claude-sonnet-4-5-20251001",
  "temperature": 0.7,
  "max_tokens": 4096
}'::jsonb;
