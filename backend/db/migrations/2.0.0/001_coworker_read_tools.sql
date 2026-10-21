UPDATE agents
SET tool_permissions_json = '["web_search","confluence_read","oracle_read"]',
    updated_at = datetime('now')
WHERE status != 'deleted';

UPDATE app_settings SET value = '2.0.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.0.0', 'Grant read-only retrieval tools to existing coworkers');
