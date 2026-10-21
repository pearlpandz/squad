-- Retire only the original Silvy fixture. A later coworker using this name has a different id.
DELETE FROM knowledge_sources
WHERE owner_agent_id = 1
  AND EXISTS (SELECT 1 FROM agents WHERE id = 1 AND lower(username) = 'silvy');

DELETE FROM messages
WHERE sender_agent_id = 1
  AND EXISTS (SELECT 1 FROM agents WHERE id = 1 AND lower(username) = 'silvy');

DELETE FROM agents WHERE id = 1 AND lower(username) = 'silvy';

UPDATE app_settings SET value = '1.6.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('1.6.0', 'Retire the original seeded Silvy coworker');
