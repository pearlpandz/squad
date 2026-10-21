PRAGMA foreign_keys = ON;

ALTER TABLE humans ADD COLUMN username TEXT NOT NULL DEFAULT '';

ALTER TABLE agents ADD COLUMN username TEXT NOT NULL DEFAULT '';
ALTER TABLE agents ADD COLUMN agent_description TEXT NOT NULL DEFAULT '';

UPDATE humans
SET username = lower(replace(display_name, ' ', '.'))
WHERE username = '';

UPDATE agents
SET
    username = replace(handle, '@', ''),
    agent_description = knowledge_scope
WHERE username = '';

CREATE TABLE IF NOT EXISTS project_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    agent_id INTEGER NOT NULL,
    member_role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, agent_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_project_agents_project ON project_agents(project_id);
CREATE INDEX IF NOT EXISTS idx_project_agents_agent ON project_agents(agent_id);

INSERT OR IGNORE INTO project_agents (project_id, agent_id, member_role, status)
SELECT project_id, id, 'member', 'active'
FROM agents;

UPDATE app_settings
SET value = '1.2.0', updated_at = datetime('now')
WHERE key = 'app.version';

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.2.0', 'Reusable AI agents and project member management');
