PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO app_settings (key, value, value_type, description)
VALUES
    ('app.version', '1.1.0', 'string', 'Current application schema version'),
    ('routing.default_classifier_model', 'gpt-6-luna', 'string', 'Lowest-cost model used to classify intent and complexity'),
    ('knowledge.storage_mode', 'relative-path', 'string', 'Knowledge source files remain on disk; only relative paths are stored in SQLite');

INSERT OR IGNORE INTO humans (id, display_name, username, email, role, status)
VALUES
    (1, 'Sarah Chen', 'sarah.chen', 'sarah.chen@example.local', 'lead-staff-engineer', 'active'),
    (2, 'Muthu', 'muthu', 'muthu@example.local', 'product-owner', 'active');

INSERT OR IGNORE INTO projects (
    id,
    code,
    name,
    description,
    status,
    business_domain,
    repository_url,
    delivery_stage,
    priority,
    tech_stack_json,
    metadata_json,
    created_by_human_id,
    updated_by_human_id
)
VALUES
    (1, 'project-atlas', 'Project Atlas', 'Initial project workspace for AI coworkers and human review.', 'active', 'retail banking', 'https://example.local/acme/project-atlas', 'execution', 'high', '["Next.js","FastAPI","LangChain","SQLite","Codex CLI"]', '{"source":"seed","program":"multi-agent-team","visibility":"internal"}', 2, 2),
    (2, 'payments-v3', 'Payments V3', 'Seed inactive project used for sidebar navigation.', 'inactive', 'payments', '', 'planning', 'medium', '["FastAPI","Oracle","Kafka"]', '{"source":"seed","visibility":"internal"}', 2, 2),
    (3, 'mobile-core', 'Mobile Core', 'Seed inactive project used for sidebar navigation.', 'inactive', 'mobile banking', '', 'discovery', 'medium', '["React Native","FastAPI"]', '{"source":"seed","visibility":"internal"}', 2, 2);

INSERT OR IGNORE INTO project_members (project_id, human_id, member_role, status)
VALUES
    (1, 1, 'lead-staff-engineer', 'active'),
    (1, 2, 'product-owner', 'active'),
    (2, 2, 'product-owner', 'active'),
    (3, 2, 'product-owner', 'active');

INSERT OR IGNORE INTO agent_roles (id, code, name, description, default_instructions)
VALUES
    (
        1,
        'business-analyst',
        'Business Analyst',
        'Owns requirements, business rules, acceptance criteria, decision logs, and stakeholder clarifications.',
        'Read approved project knowledge first. Cite sources for every requirement conclusion. Ask for BA decision when sources conflict.'
    ),
    (
        2,
        'technical-lead',
        'Technical Lead',
        'Owns architecture, integration contracts, delivery plans, and technical risk review.',
        'Prefer existing project patterns. Escalate high-impact architecture and production-risk decisions for human review.'
    ),
    (
        3,
        'qa-analyst',
        'QA Analyst',
        'Owns quality checks, test strategy, release readiness, and defect risk notes.',
        'Review acceptance criteria and evidence. Stay silent when no action is required.'
    );

INSERT OR IGNORE INTO agents (
    id,
    project_id,
    role_id,
    name,
    username,
    handle,
    status,
    agent_description,
    knowledge_scope,
    tool_permissions_json,
    review_boundaries_json,
    onboarded_by_human_id
)
VALUES
    (
        2,
        1,
        2,
        'Arun',
        'arun',
        '@Arun',
        'available',
        'Technical lead AI co-worker for architecture and integration contracts.',
        'architecture, technical decisions, integration contracts',
        '["read_knowledge","draft_architecture","route_codex_task"]',
        '["production_risk","security_risk","large_refactor"]',
        2
    ),
    (
        3,
        1,
        3,
        'QA-Sentinel',
        'qa-sentinel',
        '@QA-Sentinel',
        'idle',
        'QA AI co-worker for acceptance criteria and release readiness.',
        'acceptance criteria, release readiness, defect evidence',
        '["read_knowledge","review_acceptance_criteria"]',
        '["release_blocker","missing_evidence"]',
        2
    );

INSERT OR IGNORE INTO project_agents (project_id, agent_id, member_role, status)
VALUES
    (1, 2, 'technical-lead', 'active'),
    (1, 3, 'qa-analyst', 'active');

INSERT OR IGNORE INTO knowledge_sources (
    id,
    project_id,
    owner_agent_id,
    title,
    source_type,
    relative_path,
    version_label,
    approval_status,
    checksum,
    effective_from
)
VALUES
    (3, 1, 2, 'Architecture Notes', 'markdown', 'knowledge/project-atlas/architecture-notes.md', '1.0', 'approved', NULL, '2026-09-29'),
    (4, 1, 3, 'Acceptance Criteria', 'markdown', 'knowledge/project-atlas/acceptance-criteria.md', '1.0', 'draft', NULL, '2026-09-29');

INSERT OR IGNORE INTO model_catalog (id, model_name, tier, default_reasoning, intended_use, is_active)
VALUES
    (1, 'gpt-6-luna', 'low', 'low', 'Classification, extraction, simple explanation, low-risk drafting.', 1),
    (2, 'gpt-5.6-terra', 'medium', 'medium', 'Balanced general work when intent is unclear or moderate reasoning is needed.', 1),
    (3, 'gpt-6-sol', 'high', 'high', 'Coding, debugging, integration, and multi-step technical reasoning.', 1),
    (4, 'gpt-6-astra', 'xhigh', 'xhigh', 'High-impact architecture, security, production, and ambiguous complex work.', 1);

INSERT OR IGNORE INTO model_routing_rules (
    id,
    complexity,
    intent_hint,
    selected_model_id,
    reasoning,
    min_confidence,
    escalation_complexity
)
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
    (
        1,
        1,
        'human',
        1,
        NULL,
        'Hey team, we need to finalize the caching topology before tomorrow staging release.',
        '{"mentions":["@Arun"]}'
    ),
    (
        2,
        1,
        'agent',
        NULL,
        2,
        'I will review the architecture notes and route the implementation work with the lowest sufficient model.',
        '{"model":"gpt-6-sol"}'
    );

INSERT OR IGNORE INTO tasks (
    id,
    project_id,
    thread_id,
    assigned_agent_id,
    title,
    prompt,
    status,
    complexity,
    selected_model_id,
    reasoning,
    confidence
)
VALUES
    (
        1,
        1,
        1,
        NULL,
        'Prepare BA onboarding knowledge map',
        'Identify required BA knowledge sources for Project Atlas and flag missing approved documents.',
        'queued',
        'medium',
        2,
        'medium',
        0.74
    );

INSERT OR IGNORE INTO codex_runs (id, task_id, command_json, process_status)
VALUES
    (
        1,
        1,
        '{"command":["codex","exec","--model","gpt-5.6-terra","--json","Identify required BA knowledge sources for Project Atlas."]}',
        'created'
    );
