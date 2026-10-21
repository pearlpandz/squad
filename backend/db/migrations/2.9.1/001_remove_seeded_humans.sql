BEGIN IMMEDIATE;

-- Match the two original sample identities, preserving similarly named real users.
CREATE TEMP TABLE removed_seeded_humans AS
SELECT id, username FROM humans
WHERE (display_name = 'Sarah Chen' AND username = 'sarah.chen' AND email = 'sarah.chen@example.local')
   OR (display_name = 'Muthu' AND username = 'muthu' AND email = 'muthu@example.local');

CREATE TEMP TABLE replacement_human AS
SELECT id FROM humans WHERE display_name = 'Muthupandi Velmurugan' AND username = 'muvelmur' AND status = 'active';

-- Transfer Muthu's memberships before removing the sample identity.
INSERT OR IGNORE INTO team_humans (team_id, human_id)
SELECT th.team_id, replacement.id FROM team_humans th CROSS JOIN replacement_human replacement
WHERE th.human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu');
INSERT OR IGNORE INTO team_humans (team_id, human_id)
SELECT p.team_id, replacement.id FROM project_members pm JOIN projects p ON p.id = pm.project_id
CROSS JOIN replacement_human replacement
WHERE pm.human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu');
INSERT OR IGNORE INTO project_members (project_id, human_id, member_role, status, created_at, updated_at)
SELECT pm.project_id, replacement.id, pm.member_role, pm.status, pm.created_at, pm.updated_at
FROM project_members pm CROSS JOIN replacement_human replacement
WHERE pm.human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu');

DELETE FROM project_members WHERE human_id IN (SELECT id FROM removed_seeded_humans);
DELETE FROM team_humans WHERE human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE projects SET created_by_human_id = CASE
    WHEN created_by_human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
    THEN (SELECT id FROM replacement_human) ELSE NULL END
WHERE created_by_human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE projects SET updated_by_human_id = CASE
    WHEN updated_by_human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
    THEN (SELECT id FROM replacement_human) ELSE NULL END
WHERE updated_by_human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE agents SET onboarded_by_human_id = CASE
    WHEN onboarded_by_human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
    THEN (SELECT id FROM replacement_human) ELSE NULL END
WHERE onboarded_by_human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE conversation_threads SET created_by_human_id = CASE
    WHEN created_by_human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
    THEN (SELECT id FROM replacement_human) ELSE NULL END
WHERE created_by_human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE messages SET sender_human_id = CASE
    WHEN sender_human_id IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
    THEN (SELECT id FROM replacement_human) ELSE NULL END
WHERE sender_human_id IN (SELECT id FROM removed_seeded_humans);
UPDATE codex_runs SET command_json = CASE
    WHEN json_extract(command_json, '$.requester_human_id') IN (SELECT id FROM removed_seeded_humans WHERE username = 'muthu')
      AND EXISTS (SELECT 1 FROM replacement_human)
    THEN json_set(command_json, '$.requester_human_id', (SELECT id FROM replacement_human))
    ELSE json_remove(command_json, '$.requester_human_id') END
WHERE json_extract(command_json, '$.requester_human_id') IN (SELECT id FROM removed_seeded_humans);

-- Rebuild affected memory from the surviving roster on its next read.
DELETE FROM agent_project_memory
WHERE EXISTS (
    SELECT 1 FROM json_each(snapshot_json, '$.members.humans') member
    WHERE json_extract(member.value, '$.id') IN (SELECT id FROM removed_seeded_humans)
);

DELETE FROM humans WHERE id IN (SELECT id FROM removed_seeded_humans);
DROP TABLE removed_seeded_humans;
DROP TABLE replacement_human;

UPDATE app_settings SET value = '2.9.1', updated_at = datetime('now') WHERE key = 'app.version';
INSERT INTO schema_migrations (version, description)
VALUES ('2.9.1', 'Remove seeded Sarah Chen and Muthu identities without deleting project history');
COMMIT;
