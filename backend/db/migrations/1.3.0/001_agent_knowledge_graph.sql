PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS agent_knowledge_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (agent_id, project_id, source_kind, source_id),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_knowledge_terms (
    agent_id INTEGER NOT NULL,
    node_id INTEGER NOT NULL,
    term TEXT NOT NULL,
    weight INTEGER NOT NULL,
    PRIMARY KEY (agent_id, node_id, term),
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES agent_knowledge_nodes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_terms_term
ON agent_knowledge_terms(agent_id, term);

UPDATE app_settings
SET value = '1.3.0', updated_at = datetime('now')
WHERE key = 'app.version';

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.3.0', 'Agent knowledge source and past-work graph');
