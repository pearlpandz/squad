-- Templates are seeded after the coworker read-tool migration, so set their
-- default read capabilities explicitly without changing user-customized ones.
UPDATE agents
SET tool_permissions_json = '["web_search","confluence_read","oracle_read"]',
    updated_at = datetime('now')
WHERE is_template = 1 AND username = 'business-analyst-template'
  AND tool_permissions_json = '[]';

INSERT INTO agent_template_versions
    (template_agent_id, version, role_id, description, knowledge_scope,
     instructions, tool_permissions_json, source_ids_json)
SELECT a.id, a.published_version + 1, a.role_id, a.agent_description,
       a.knowledge_scope, a.template_instructions, a.tool_permissions_json,
       old.source_ids_json
FROM agents a JOIN agent_template_versions old
  ON old.template_agent_id = a.id AND old.version = a.published_version
WHERE a.is_template = 1 AND a.username = 'business-analyst-template'
  AND old.tool_permissions_json != a.tool_permissions_json;

UPDATE agents SET published_version = (
    SELECT MAX(version) FROM agent_template_versions WHERE template_agent_id = agents.id
), updated_at = datetime('now')
WHERE is_template = 1 AND username = 'business-analyst-template'
  AND EXISTS (SELECT 1 FROM agent_template_versions WHERE template_agent_id = agents.id);

UPDATE agents SET template_version = (
    SELECT published_version FROM agents t WHERE t.id = agents.template_agent_id
), updated_at = datetime('now')
WHERE lower(username) = 'silvy' AND is_template = 0
  AND template_agent_id IN (
      SELECT id FROM agents WHERE is_template = 1 AND username = 'business-analyst-template'
  );

UPDATE app_settings SET value = '2.5.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.5.0', 'Set default read permissions for seeded BA template');
