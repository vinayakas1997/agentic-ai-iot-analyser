-- Per-turn UI and schema snapshots for Model B frontend sync.

ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS turn_index INTEGER;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS ui_snapshot JSONB;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS schema_snapshot JSONB;

CREATE INDEX IF NOT EXISTS idx_chat_history_session_turn ON chat_history(session_id, turn_index);
