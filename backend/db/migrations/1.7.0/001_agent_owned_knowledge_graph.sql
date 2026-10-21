CREATE TABLE IF NOT EXISTS agent_graphs (
    agent_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_trained_at TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_graph_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    project_id INTEGER,
    project_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (agent_id, source_key),
    FOREIGN KEY (agent_id) REFERENCES agent_graphs(agent_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_graph_concepts (
    agent_id INTEGER NOT NULL,
    term TEXT NOT NULL,
    PRIMARY KEY (agent_id, term),
    FOREIGN KEY (agent_id) REFERENCES agent_graphs(agent_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_graph_edges (
    agent_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    term TEXT NOT NULL,
    weight INTEGER NOT NULL,
    PRIMARY KEY (agent_id, source_key, term),
    FOREIGN KEY (agent_id, source_key) REFERENCES agent_graph_sources(agent_id, source_key) ON DELETE CASCADE,
    FOREIGN KEY (agent_id, term) REFERENCES agent_graph_concepts(agent_id, term) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_graph_edges_term ON agent_graph_edges(agent_id, term);

CREATE TABLE IF NOT EXISTS agent_graph_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    project_id INTEGER,
    project_name TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    checksum TEXT,
    outcome TEXT NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (agent_id) REFERENCES agent_graphs(agent_id) ON DELETE CASCADE
);

UPDATE app_settings SET value = '1.7.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.7.0', 'One incrementally updated knowledge graph per AI coworker');
