UPDATE knowledge_sources
SET relative_path = 'knowledge/agents/silvy/business-requirements.md',
    updated_at = datetime('now')
WHERE id = 1 AND owner_agent_id = 1
  AND relative_path = 'knowledge/project-atlas/business-requirements.md';

UPDATE knowledge_sources
SET relative_path = 'knowledge/agents/silvy/business-rules.md',
    updated_at = datetime('now')
WHERE id = 2 AND owner_agent_id = 1
  AND relative_path = 'knowledge/project-atlas/business-rules.md';

UPDATE app_settings SET value = '1.4.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.4.0', 'Relocate Silvy seed source paths into the agent knowledge folder');
