-- Create the reusable role identity. The startup backfill copies only trained,
-- reusable FDD material from an existing BA coworker when it is available.
INSERT INTO agents
    (project_id, role_id, is_template, name, username, handle, status,
     agent_description, knowledge_scope, template_instructions)
SELECT p.id, r.id, 1, 'Business Analyst', 'business-analyst-template',
       '@business-analyst-template', 'available',
       'Analyze business requirements, prepare meeting notes, BRDs, and functional design documents.',
       'Business analysis, requirements, meeting notes, BRDs, and functional design documents.',
       'Use approved role knowledge and the relevant trained template for each task. For an FDD, obtain and read an accessible Business Requirements Document before drafting; ask for it if missing. Ask whether other supporting documents or links are available, but do not block on optional sources. Follow the trained FDD template, trace in-scope requirements, flag unresolved business decisions, validate the output, and share verified artifact paths. For other BA work, check the inputs required by the relevant trained skill. Keep project-specific facts and prior coworker experience separate from shared role knowledge.'
FROM projects p JOIN agent_roles r ON r.code = 'business-analyst'
WHERE p.code = '_agent-pool'
  AND NOT EXISTS (
      SELECT 1 FROM agents WHERE is_template = 1 AND role_id = r.id AND status != 'deleted'
  );

UPDATE app_settings SET value = '2.4.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.4.0', 'Seed reusable Business Analyst template identity');
