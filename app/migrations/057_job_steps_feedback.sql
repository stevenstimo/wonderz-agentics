-- Platform Spec V2: ensure job_steps.feedback exists for Talent 3x rejected (ceo_feedback)
ALTER TABLE job_steps ADD COLUMN IF NOT EXISTS feedback TEXT;
