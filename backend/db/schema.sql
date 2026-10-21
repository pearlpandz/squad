PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string',
    description TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS humans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    email TEXT UNIQUE,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL DEFAULT 1 REFERENCES clients(id),
    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 2 AND 160),
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL DEFAULT 1 REFERENCES teams(id),
    client_id INTEGER NOT NULL DEFAULT 1,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    business_domain TEXT NOT NULL DEFAULT '',
    repository_url TEXT NOT NULL DEFAULT '',
    delivery_stage TEXT NOT NULL DEFAULT 'discovery',
    priority TEXT NOT NULL DEFAULT 'medium',
    tech_stack_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by_human_id INTEGER,
    updated_by_human_id INTEGER,
    removed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by_human_id) REFERENCES humans(id),
    FOREIGN KEY (updated_by_human_id) REFERENCES humans(id)
);

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

CREATE TABLE IF NOT EXISTS agent_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    default_instructions TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL DEFAULT 1,
    project_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    is_template INTEGER NOT NULL DEFAULT 0,
    template_agent_id INTEGER,
    template_version INTEGER,
    template_instructions TEXT NOT NULL DEFAULT '',
    template_description TEXT NOT NULL DEFAULT '',
    template_scope TEXT NOT NULL DEFAULT '',
    published_version INTEGER NOT NULL DEFAULT 0,
    name TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    handle TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    agent_description TEXT NOT NULL DEFAULT '',
    knowledge_scope TEXT NOT NULL,
    tool_permissions_json TEXT NOT NULL DEFAULT '["web_search","confluence_read","oracle_read"]',
    review_boundaries_json TEXT NOT NULL DEFAULT '[]',
    onboarded_by_human_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, handle),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (template_agent_id) REFERENCES agents(id),
    FOREIGN KEY (role_id) REFERENCES agent_roles(id),
    FOREIGN KEY (onboarded_by_human_id) REFERENCES humans(id)
);

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

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    owner_agent_id INTEGER,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    version_label TEXT NOT NULL DEFAULT '1.0',
    approval_status TEXT NOT NULL DEFAULT 'approved',
    checksum TEXT,
    effective_from TEXT,
    effective_to TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, relative_path, version_label),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (owner_agent_id) REFERENCES agents(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agent_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    template_source_id INTEGER,
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

CREATE TABLE IF NOT EXISTS agent_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('self_train', 'trial')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    request_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_source_index (
    source_id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES agent_sources(id) ON DELETE CASCADE
);

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

CREATE TABLE IF NOT EXISTS agent_graph_chunks (
    agent_id INTEGER NOT NULL,
    source_key TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    locator TEXT NOT NULL,
    content TEXT NOT NULL,
    checksum TEXT NOT NULL,
    embedding BLOB,
    embedding_model TEXT,
    PRIMARY KEY (agent_id, source_key, chunk_index),
    FOREIGN KEY (agent_id, source_key) REFERENCES agent_graph_sources(agent_id, source_key) ON DELETE CASCADE
);

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

CREATE TABLE IF NOT EXISTS model_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL,
    default_reasoning TEXT NOT NULL,
    intended_use TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_routing_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complexity TEXT NOT NULL UNIQUE,
    intent_hint TEXT NOT NULL,
    selected_model_id INTEGER NOT NULL,
    reasoning TEXT NOT NULL,
    min_confidence REAL NOT NULL DEFAULT 0.70,
    escalation_complexity TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (selected_model_id) REFERENCES model_catalog(id)
);

CREATE TABLE IF NOT EXISTS conversation_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_by_human_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_human_id) REFERENCES humans(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    sender_type TEXT NOT NULL,
    sender_human_id INTEGER,
    sender_agent_id INTEGER,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (thread_id) REFERENCES conversation_threads(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_human_id) REFERENCES humans(id),
    FOREIGN KEY (sender_agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    thread_id INTEGER,
    assigned_agent_id INTEGER,
    title TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    complexity TEXT,
    selected_model_id INTEGER,
    reasoning TEXT,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (thread_id) REFERENCES conversation_threads(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_agent_id) REFERENCES agents(id) ON DELETE SET NULL,
    FOREIGN KEY (selected_model_id) REFERENCES model_catalog(id)
);

CREATE TABLE IF NOT EXISTS task_workflows (
    thread_id INTEGER PRIMARY KEY REFERENCES conversation_threads(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    brd_key TEXT
);

CREATE TABLE IF NOT EXISTS codex_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    command_json TEXT NOT NULL,
    process_status TEXT NOT NULL DEFAULT 'created',
    started_at TEXT,
    finished_at TEXT,
    output_summary TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);


CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_project ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_project_members_human ON project_members(human_id);
CREATE INDEX IF NOT EXISTS idx_project_agents_project ON project_agents(project_id);
CREATE INDEX IF NOT EXISTS idx_project_agents_agent ON project_agents(agent_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_agent ON knowledge_sources(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, id);
CREATE INDEX IF NOT EXISTS idx_agents_client_template ON agents(client_id, template_agent_id);
CREATE INDEX IF NOT EXISTS idx_projects_client ON projects(client_id);
CREATE INDEX IF NOT EXISTS idx_agent_sources_template_source ON agent_sources(template_source_id);
CREATE INDEX IF NOT EXISTS idx_agent_lessons_agent ON agent_lessons(agent_id, approval_status);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_agent_status ON agent_jobs(agent_id, status, id);

CREATE TABLE IF NOT EXISTS trial_sessions (
    id TEXT PRIMARY KEY,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trial_sessions_agent ON trial_sessions(agent_id, updated_at);
CREATE TABLE IF NOT EXISTS trial_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES trial_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trial_messages_session ON trial_messages(session_id, id);
CREATE TABLE IF NOT EXISTS context_compactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    through_count INTEGER NOT NULL,
    prefix_checksum TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_context_compactions_scope ON context_compactions(scope, agent_id, id);

CREATE TABLE IF NOT EXISTS team_agents (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, agent_id)
);
CREATE INDEX IF NOT EXISTS idx_team_agents_agent ON team_agents(agent_id);
CREATE TABLE IF NOT EXISTS team_humans (
    team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    human_id INTEGER NOT NULL REFERENCES humans(id),
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (team_id, human_id)
);
CREATE TABLE IF NOT EXISTS agent_project_memory (
    agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    snapshot_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agent_id, project_id)
);


CREATE TRIGGER IF NOT EXISTS project_team_insert BEFORE INSERT ON projects
WHEN NOT EXISTS (SELECT 1 FROM teams WHERE id = NEW.team_id AND client_id = NEW.client_id)
BEGIN SELECT RAISE(ABORT, 'Project and team must belong to the same workspace'); END;
CREATE TRIGGER IF NOT EXISTS project_team_update BEFORE UPDATE OF team_id, client_id ON projects
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
CREATE TRIGGER IF NOT EXISTS team_agent_insert BEFORE INSERT ON team_agents
WHEN NOT EXISTS (SELECT 1 FROM agents a JOIN teams t ON t.client_id = a.client_id
    WHERE t.id = NEW.team_id AND a.id = NEW.agent_id AND a.is_template = 0 AND a.status != 'deleted')
BEGIN SELECT RAISE(ABORT, 'Choose a coworker from the same workspace'); END;
CREATE TRIGGER IF NOT EXISTS team_agent_remove BEFORE DELETE ON team_agents
WHEN EXISTS (SELECT 1 FROM project_agents pa JOIN projects p ON p.id = pa.project_id
    WHERE p.team_id = OLD.team_id AND pa.agent_id = OLD.agent_id AND pa.status != 'removed'
    AND p.status != 'removed' AND p.removed_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'Remove the coworker from active team projects first'); END;
CREATE TRIGGER IF NOT EXISTS team_human_remove BEFORE DELETE ON team_humans
WHEN EXISTS (SELECT 1 FROM project_members pm JOIN projects p ON p.id = pm.project_id
    WHERE p.team_id = OLD.team_id AND pm.human_id = OLD.human_id AND pm.status != 'removed'
    AND p.status != 'removed' AND p.removed_at IS NULL)
BEGIN SELECT RAISE(ABORT, 'Remove the human from active team projects first'); END;

CREATE TRIGGER IF NOT EXISTS project_agents_team_insert BEFORE INSERT ON project_agents
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_agents tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.agent_id = NEW.agent_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER IF NOT EXISTS project_agents_team_update BEFORE UPDATE ON project_agents
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_agents tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.agent_id = NEW.agent_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER IF NOT EXISTS project_members_team_insert BEFORE INSERT ON project_members
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_humans tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.human_id = NEW.human_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE TRIGGER IF NOT EXISTS project_members_team_update BEFORE UPDATE ON project_members
WHEN NEW.status != 'removed' AND NOT EXISTS (
    SELECT 1 FROM projects p JOIN team_humans tm ON tm.team_id = p.team_id
    WHERE p.id = NEW.project_id AND tm.human_id = NEW.human_id)
BEGIN SELECT RAISE(ABORT, 'Add the member to the project team before assigning this project'); END;

CREATE INDEX IF NOT EXISTS idx_projects_team ON projects(team_id);

CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    credential_version TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_login_attempts (
    client_address TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    window_started_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    human_id INTEGER NOT NULL REFERENCES humans(id),
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expiry ON user_sessions(expires_at);
