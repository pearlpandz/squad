CREATE TABLE IF NOT EXISTS trial_sessions (
    id TEXT PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trial_sessions_agent ON trial_sessions(agent_id, updated_at);
CREATE TABLE IF NOT EXISTS trial_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES trial_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trial_messages_session ON trial_messages(session_id, id);
CREATE TABLE IF NOT EXISTS context_compactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    through_count INTEGER NOT NULL,
    prefix_checksum TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_context_compactions_scope ON context_compactions(scope, agent_id, id);
UPDATE app_settings SET value = '2.7.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.7.0', 'Persistent trial sessions and scoped conversation compaction');
