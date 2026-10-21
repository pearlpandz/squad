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
    email TEXT UNIQUE,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_by_human_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by_human_id) REFERENCES humans(id)
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
    project_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    handle TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    knowledge_scope TEXT NOT NULL,
    tool_permissions_json TEXT NOT NULL DEFAULT '[]',
    review_boundaries_json TEXT NOT NULL DEFAULT '[]',
    onboarded_by_human_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (project_id, handle),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES agent_roles(id),
    FOREIGN KEY (onboarded_by_human_id) REFERENCES humans(id)
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

CREATE INDEX IF NOT EXISTS idx_agents_project ON agents(project_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_agent ON knowledge_sources(owner_agent_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project_status ON tasks(project_id, status);

INSERT OR IGNORE INTO app_settings (key, value, value_type, description)
VALUES
    ('app.version', '1.0.0', 'string', 'Current application schema version'),
    ('routing.default_classifier_model', 'gpt-6-luna', 'string', 'Lowest-cost model used to classify intent and complexity'),
    ('knowledge.storage_mode', 'relative-path', 'string', 'Knowledge source files remain on disk; only relative paths are stored in SQLite');

INSERT OR IGNORE INTO humans (id, display_name, email, role, status)
VALUES
    (1, 'Sarah Chen', 'sarah.chen@example.local', 'lead-staff-engineer', 'active'),
    (2, 'Muthu', 'muthu@example.local', 'product-owner', 'active');

INSERT OR IGNORE INTO projects (id, code, name, description, status, created_by_human_id)
VALUES
    (1, 'project-atlas', 'Project Atlas', 'Initial project workspace for AI coworkers and human review.', 'active', 2),
    (2, 'payments-v3', 'Payments V3', 'Seed inactive project used for sidebar navigation.', 'inactive', 2),
    (3, 'mobile-core', 'Mobile Core', 'Seed inactive project used for sidebar navigation.', 'inactive', 2);

INSERT OR IGNORE INTO agent_roles (id, code, name, description, default_instructions)
VALUES
    (1, 'business-analyst', 'Business Analyst', 'Owns requirements, business rules, acceptance criteria, decision logs, and stakeholder clarifications.', 'Read approved project knowledge first. Cite sources for every requirement conclusion. Ask for BA decision when sources conflict.'),
    (2, 'technical-lead', 'Technical Lead', 'Owns architecture, integration contracts, delivery plans, and technical risk review.', 'Prefer existing project patterns. Escalate high-impact architecture and production-risk decisions for human review.'),
    (3, 'qa-analyst', 'QA Analyst', 'Owns quality checks, test strategy, release readiness, and defect risk notes.', 'Review acceptance criteria and evidence. Stay silent when no action is required.');

INSERT OR IGNORE INTO agents (id, project_id, role_id, name, handle, status, knowledge_scope, tool_permissions_json, review_boundaries_json, onboarded_by_human_id)
VALUES
    (1, 1, 1, 'Silvy', '@Silvy', 'available', 'project requirements, business rules, decisions, process docs', '["read_knowledge","draft_requirements","ask_clarifying_questions"]', '["source_conflict","missing_approval","scope_change"]', 2),
    (2, 1, 2, 'Arun', '@Arun', 'available', 'architecture, technical decisions, integration contracts', '["read_knowledge","draft_architecture","route_codex_task"]', '["production_risk","security_risk","large_refactor"]', 2),
    (3, 1, 3, 'QA-Sentinel', '@QA-Sentinel', 'idle', 'acceptance criteria, release readiness, defect evidence', '["read_knowledge","review_acceptance_criteria"]', '["release_blocker","missing_evidence"]', 2);

INSERT OR IGNORE INTO knowledge_sources (id, project_id, owner_agent_id, title, source_type, relative_path, version_label, approval_status, checksum, effective_from)
VALUES
    (1, 1, 1, 'Business Requirements', 'markdown', 'knowledge/project-atlas/business-requirements.md', '1.0', 'approved', NULL, '2026-09-29'),
    (2, 1, 1, 'Business Rules', 'markdown', 'knowledge/project-atlas/business-rules.md', '1.0', 'approved', NULL, '2026-09-29'),
    (3, 1, 2, 'Architecture Notes', 'markdown', 'knowledge/project-atlas/architecture-notes.md', '1.0', 'approved', NULL, '2026-09-29'),
    (4, 1, 3, 'Acceptance Criteria', 'markdown', 'knowledge/project-atlas/acceptance-criteria.md', '1.0', 'draft', NULL, '2026-09-29');

INSERT OR IGNORE INTO model_catalog (id, model_name, tier, default_reasoning, intended_use, is_active)
VALUES
    (1, 'gpt-6-luna', 'low', 'low', 'Classification, extraction, simple explanation, low-risk drafting.', 1),
    (2, 'gpt-5.6-terra', 'medium', 'medium', 'Balanced general work when intent is unclear or moderate reasoning is needed.', 1),
    (3, 'gpt-6-sol', 'high', 'high', 'Coding, debugging, integration, and multi-step technical reasoning.', 1),
    (4, 'gpt-6-astra', 'xhigh', 'xhigh', 'High-impact architecture, security, production, and ambiguous complex work.', 1);

INSERT OR IGNORE INTO model_routing_rules (id, complexity, intent_hint, selected_model_id, reasoning, min_confidence, escalation_complexity)
VALUES
    (1, 'low', 'clear informational or extraction task', 1, 'low', 0.70, 'medium'),
    (2, 'medium', 'general task with moderate ambiguity', 2, 'medium', 0.70, 'high'),
    (3, 'high', 'engineering task requiring coding or tool reasoning', 3, 'high', 0.75, 'xhigh'),
    (4, 'xhigh', 'architecture, security, production, migration, or high-risk task', 4, 'xhigh', 0.80, NULL);

INSERT OR IGNORE INTO conversation_threads (id, project_id, title, status, created_by_human_id)
VALUES
    (1, 1, 'Sprint 14 Execution Thread', 'active', 1);

INSERT OR IGNORE INTO messages (id, thread_id, sender_type, sender_human_id, sender_agent_id, content, metadata_json)
VALUES
    (1, 1, 'human', 1, NULL, 'Hey team, we need to finalize the caching topology before tomorrow staging release.', '{"mentions":["@Silvy","@Arun"]}'),
    (2, 1, 'agent', NULL, 2, 'I will review the architecture notes and route the implementation work with the lowest sufficient model.', '{"model":"gpt-6-sol"}');

INSERT OR IGNORE INTO tasks (id, project_id, thread_id, assigned_agent_id, title, prompt, status, complexity, selected_model_id, reasoning, confidence)
VALUES
    (1, 1, 1, 1, 'Prepare BA onboarding knowledge map', 'Identify required BA knowledge sources for Project Atlas and flag missing approved documents.', 'queued', 'medium', 2, 'medium', 0.74);

INSERT OR IGNORE INTO codex_runs (id, task_id, command_json, process_status)
VALUES
    (1, 1, '{"command":["codex","exec","--model","gpt-5.6-terra","--json","Identify required BA knowledge sources for Project Atlas."]}', 'created');

INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.0.0', 'Zero-day SQLite schema and seed data');
