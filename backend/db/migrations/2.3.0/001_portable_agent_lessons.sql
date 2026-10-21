CREATE TABLE IF NOT EXISTS agent_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    source_project_id INTEGER,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    checksum TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (source_project_id) REFERENCES projects(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_lessons_agent ON agent_lessons(agent_id, approval_status);

UPDATE app_settings SET value = '2.3.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.3.0', 'Portable coworker lessons linked to source projects');
