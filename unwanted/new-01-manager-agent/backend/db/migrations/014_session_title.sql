-- Add editable title column to manager_sessions

ALTER TABLE manager_sessions ADD COLUMN IF NOT EXISTS title TEXT;
