ALTER TABLE knowledge_usage_log
ADD COLUMN IF NOT EXISTS lesson_ids TEXT[];

