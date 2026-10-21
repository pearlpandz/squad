CREATE TABLE IF NOT EXISTS agent_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('self_train', 'trial')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    request_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_agent_status ON agent_jobs(agent_id, status, id);

UPDATE app_settings SET value = '2.6.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.6.0', 'Agent execution and self-train background jobs');
