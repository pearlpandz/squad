PRAGMA foreign_keys = ON;

ALTER TABLE projects ADD COLUMN business_domain TEXT NOT NULL DEFAULT '';
ALTER TABLE projects ADD COLUMN repository_url TEXT NOT NULL DEFAULT '';
ALTER TABLE projects ADD COLUMN delivery_stage TEXT NOT NULL DEFAULT 'discovery';
ALTER TABLE projects ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium';
ALTER TABLE projects ADD COLUMN tech_stack_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE projects ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE projects ADD COLUMN updated_by_human_id INTEGER REFERENCES humans(id);
ALTER TABLE projects ADD COLUMN removed_at TEXT;

CREATE TABLE IF NOT EXISTS project_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    human_id INTEGER NOT NULL,
    member_role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, human_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (human_id) REFERENCES humans(id)
);

CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_human ON project_members(human_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

UPDATE projects
SET
    business_domain = 'retail banking',
    repository_url = 'https://example.local/acme/project-atlas',
    delivery_stage = 'execution',
    priority = 'high',
    tech_stack_json = '["Next.js","FastAPI","LangChain","SQLite","Codex CLI"]',
    metadata_json = '{"source":"seed","program":"multi-agent-team","visibility":"internal"}',
    updated_by_human_id = 2
WHERE code = 'project-atlas';

UPDATE projects
SET
    business_domain = 'payments',
    delivery_stage = 'planning',
    priority = 'medium',
    tech_stack_json = '["FastAPI","Oracle","Kafka"]',
    metadata_json = '{"source":"seed","visibility":"internal"}',
    updated_by_human_id = 2
WHERE code = 'payments-v3';

UPDATE projects
SET
    business_domain = 'mobile banking',
    delivery_stage = 'discovery',
    priority = 'medium',
    tech_stack_json = '["React Native","FastAPI"]',
    metadata_json = '{"source":"seed","visibility":"internal"}',
    updated_by_human_id = 2
WHERE code = 'mobile-core';

INSERT OR IGNORE INTO project_members (project_id, human_id, member_role, status)
VALUES
    (1, 1, 'lead-staff-engineer', 'active'),
    (1, 2, 'product-owner', 'active'),
    (2, 2, 'product-owner', 'active'),
    (3, 2, 'product-owner', 'active');

UPDATE app_settings
SET value = '1.1.0', updated_at = datetime('now')
WHERE key = 'app.version';

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.1.0', 'Projects CRUD metadata and human membership');
