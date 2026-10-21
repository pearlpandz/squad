-- Keep legacy project source and index rows intact. New agent sources are independent.
INSERT OR IGNORE INTO projects (code, name, description, status)
VALUES ('_agent-pool', 'Agent pool', 'Internal parent for coworkers without an assigned project.', 'removed');

CREATE TABLE IF NOT EXISTS agent_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    legacy_source_id INTEGER UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (agent_id, relative_path),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_source_index (
    source_id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES agent_sources(id) ON DELETE CASCADE
);

INSERT OR IGNORE INTO agent_sources
    (agent_id, title, source_type, relative_path, approval_status, legacy_source_id, created_at, updated_at)
SELECT owner_agent_id, title, source_type, relative_path, approval_status, id, created_at, updated_at
FROM knowledge_sources WHERE owner_agent_id IS NOT NULL;

UPDATE app_settings SET value = '1.5.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.5.0', 'Add independent coworker sources and retain legacy project source records');
