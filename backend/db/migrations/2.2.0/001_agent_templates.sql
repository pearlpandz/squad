CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO clients (id, code, name) VALUES (1, 'local', 'Local workspace');

ALTER TABLE projects ADD COLUMN client_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE agents ADD COLUMN client_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE agents ADD COLUMN is_template INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agents ADD COLUMN template_agent_id INTEGER REFERENCES agents(id);
ALTER TABLE agents ADD COLUMN template_version INTEGER;
ALTER TABLE agents ADD COLUMN template_instructions TEXT NOT NULL DEFAULT '';
ALTER TABLE agents ADD COLUMN template_description TEXT NOT NULL DEFAULT '';
ALTER TABLE agents ADD COLUMN template_scope TEXT NOT NULL DEFAULT '';
ALTER TABLE agents ADD COLUMN published_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE agent_sources ADD COLUMN template_source_id INTEGER;

CREATE TABLE IF NOT EXISTS agent_template_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_agent_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    knowledge_scope TEXT NOT NULL,
    instructions TEXT NOT NULL,
    tool_permissions_json TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (template_agent_id, version),
    FOREIGN KEY (template_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES agent_roles(id)
);

CREATE INDEX IF NOT EXISTS idx_agents_client_template ON agents(client_id, template_agent_id);
CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_agent_sources_template_source ON agent_sources(template_source_id);

UPDATE app_settings SET value = '2.2.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.2.0', 'Versioned coworker templates and client ownership foundation');
