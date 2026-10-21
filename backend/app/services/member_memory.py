"""Persist each coworker's project facts and progress, with explicit project provenance."""

import json

from app.db.session import get_connection


def refresh_member_memory(agent_id: int) -> list[dict]:
    snapshots = []
    with get_connection() as connection:
        projects = connection.execute("""
            SELECT p.id, p.team_id, p.code, p.name, p.description, p.status, p.business_domain,
                   p.repository_url, p.delivery_stage, p.priority, p.tech_stack_json, p.metadata_json,
                   p.updated_at, t.name AS team_name
            FROM projects p JOIN project_agents pa ON pa.project_id = p.id
            JOIN team_agents ta ON ta.team_id = p.team_id AND ta.agent_id = pa.agent_id
            JOIN teams t ON t.id = p.team_id
            JOIN agents a ON a.id = pa.agent_id AND a.client_id = p.client_id
            WHERE pa.agent_id = ? AND pa.status = 'active' AND a.is_template = 0
              AND a.status = 'available' AND p.status != 'removed' AND p.removed_at IS NULL
              AND p.code != '_agent-pool' ORDER BY p.id
        """, (agent_id,)).fetchall()
        for project in projects:
            snapshot = dict(project)
            snapshot['tech_stack'] = json.loads(snapshot.pop('tech_stack_json'))
            snapshot['metadata'] = json.loads(snapshot.pop('metadata_json'))
            snapshot['members'] = {
                'agents': [dict(row) for row in connection.execute("""SELECT a.id, a.name, pa.member_role
                    FROM project_agents pa JOIN agents a ON a.id = pa.agent_id
                    WHERE pa.project_id = ? AND pa.status = 'active' ORDER BY a.id""", (project['id'],))],
                'humans': [dict(row) for row in connection.execute("""SELECT h.id, h.display_name AS name, pm.member_role
                    FROM project_members pm JOIN humans h ON h.id = pm.human_id
                    WHERE pm.project_id = ? AND pm.status = 'active' ORDER BY h.id""", (project['id'],))],
            }
            snapshot['tasks'] = [dict(row) for row in connection.execute("""
                SELECT t.id, t.title, t.status, t.updated_at,
                  (SELECT cr.process_status FROM codex_runs cr WHERE cr.task_id = t.id ORDER BY cr.id DESC LIMIT 1) AS run_status,
                  (SELECT e.detail FROM task_events e WHERE e.task_id = t.id ORDER BY e.id DESC LIMIT 1) AS latest_progress
                FROM tasks t WHERE t.project_id = ? ORDER BY t.id
            """, (project['id'],))]
            snapshot['progress'] = {}
            for task in snapshot['tasks']:
                status = task['status']
                snapshot['progress'][status] = snapshot['progress'].get(status, 0) + 1
            snapshot['my_task_ids'] = [row['id'] for row in connection.execute("""
                SELECT t.id FROM tasks t WHERE t.project_id = ? AND (t.assigned_agent_id = ? OR EXISTS (
                    SELECT 1 FROM codex_runs cr WHERE cr.task_id = t.id
                    AND CAST(json_extract(cr.command_json, '$.agent_id') AS INTEGER) = ?)) ORDER BY t.id
            """, (project['id'], agent_id, agent_id))]
            connection.execute("""INSERT INTO agent_project_memory (agent_id, project_id, snapshot_json)
                VALUES (?, ?, ?) ON CONFLICT(agent_id, project_id) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json, updated_at = datetime('now')""",
                               (agent_id, project['id'], json.dumps(snapshot, ensure_ascii=False)))
            snapshots.append(snapshot)
    return snapshots


def current_project_memory(project_id: int, agent_id: int) -> str:
    snapshots = refresh_member_memory(agent_id)
    snapshot = next((item for item in snapshots if item['id'] == project_id), None)
    if snapshot is None:
        return "No active membership memory for this project."
    return json.dumps(snapshot, ensure_ascii=False)
