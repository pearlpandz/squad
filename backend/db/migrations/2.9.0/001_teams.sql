PRAGMA foreign_keys = OFF;
BEGIN;
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL DEFAULT 1 REFERENCES clients(id),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 2 AND 160),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO teams (id, client_id, name, description)
SELECT id, id, 'Default Team', 'Existing projects and members' FROM clients;
ALTER TABLE projects ADD COLUMN team_id INTEGER NOT NULL DEFAULT 1 REFERENCES teams(id);
UPDATE projects SET team_id = client_id;
CREATE INDEX idx_projects_team ON projects(team_id);
CREATE TABLE team_agents (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, agent_id)
);
CREATE INDEX idx_team_agents_agent ON team_agents(agent_id);
CREATE TABLE team_humans (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    human_id INTEGER NOT NULL REFERENCES humans(id),
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, human_id)
);
INSERT OR IGNORE INTO team_agents (team_id, agent_id)
SELECT client_id, id FROM agents WHERE is_template = 0 AND status != 'deleted';
INSERT OR IGNORE INTO team_humans (team_id, human_id)
SELECT p.team_id, pm.human_id FROM project_members pm JOIN projects p ON p.id = pm.project_id;
INSERT OR IGNORE INTO team_humans (team_id, human_id)
SELECT 1, id FROM humans WHERE status = 'active';
CREATE TABLE agent_project_memory (
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agent_id, project_id)
);

CREATE TRIGGER project_team_insert BEFORE INSERT ON projects
WHEN NOT EXISTS (SELECT 1 FROM teams WHERE id = NEW.team_id AND client_id = NEW.client_id)
BEGIN SELECT RAISE(ABORT, 'Project and team must belong to the same workspace'); END;
CREATE TRIGGER project_team_update BEFORE UPDATE OF team_id, client_id ON projects
BEGIN
    SELECT RAISE(ABORT, 'Project and team must belong to the same workspace')
    WHERE NOT EXISTS (SELECT 1 FROM teams WHERE id = NEW.team_id AND client_id = NEW.client_id);
    SELECT RAISE(ABORT, 'Add existing project coworkers to the new team before moving the project')
    WHERE EXISTS (SELECT 1 FROM project_agents pa WHERE pa.project_id = NEW.id AND pa.status != 'removed'
        AND NOT EXISTS (SELECT 1 FROM team_agents ta WHERE ta.team_id = NEW.team_id AND ta.agent_id = pa.agent_id));
    SELECT RAISE(ABORT, 'Add existing project humans to the new team before moving the project')
    WHERE EXISTS (SELECT 1 FROM project_members pm WHERE pm.project_id = NEW.id AND pm.status != 'removed'
        AND NOT EXISTS (SELECT 1 FROM team_humans th WHERE th.team_id = NEW.team_id AND th.human_id = pm.human_id));
END;
CREATE TRIGGER team_agent_insert BEFORE INSERT ON team_agents
WHEN NOT EXISTS (SELECT 1 FROM agents a JOIN teams t ON t.client_id = a.client_id
    WHERE t.id = NEW.team_id AND a.id = NEW.agent_id AND a.is_template = 0 AND a.status != 'deleted')
BEGIN SELECT RAISE(ABORT, 'Choose a coworker from the same workspace'); END;
CREATE TRIGGER team_agent_remove BEFORE DELETE ON team_agents
WHEN EXISTS (SELECT 1 FROM project_agents pa JOIN projects p ON p.id = pa.project_id
    WHERE p.team_id = OLD.team_id AND pa.agent_id = OLD.agent_id AND pa.status != 'removed'
    AND p.status != 'removed' AND p.removed_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'Remove the coworker from active team projects first'); END;
CREATE TRIGGER team_human_remove BEFORE DELETE ON team_humans
WHEN EXISTS (SELECT 1 FROM project_members pm JOIN projects p ON p.id = pm.project_id
    WHERE p.team_id = OLD.team_id AND pm.human_id = OLD.human_id AND pm.status != 'removed'
    AND p.status != 'removed' AND p.removed_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'Remove the human from active team projects first'); END;

CREATE TRIGGER project_agents_team_insert BEFORE INSERT ON project_agents
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_agents tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.agent_id = NEW.agent_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER project_agents_team_update BEFORE UPDATE ON project_agents
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_agents tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.agent_id = NEW.agent_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER project_members_team_insert BEFORE INSERT ON project_members
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_humans tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.human_id = NEW.human_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER project_members_team_update BEFORE UPDATE ON project_members
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_humans tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.human_id = NEW.human_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

UPDATE app_settings SET value = '2.9.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT INTO schema_migrations (version, description) VALUES ('2.9.0', 'Teams, project membership hierarchy and coworker project memory');
COMMIT;

PRAGMA foreign_keys = ON;
