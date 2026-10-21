ALTER TABLE agent_graph_chunks ADD COLUMN embedding BLOB;
ALTER TABLE agent_graph_chunks ADD COLUMN embedding_model TEXT;

UPDATE app_settings SET value = '1.9.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.9.0', 'Store per-agent semantic embeddings for graph chunks');
