CREATE TABLE IF NOT EXISTS agent_graph_chunks (
    agent_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    locator TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    PRIMARY KEY (agent_id, source_key, chunk_index),
    FOREIGN KEY (agent_id, source_key) REFERENCES agent_graph_sources(agent_id, source_key) ON DELETE CASCADE
);

UPDATE app_settings SET value = '1.8.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.8.0', 'Store parsed and split knowledge graph chunks');
