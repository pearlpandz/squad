"""Team rosters reuse coworker identities without copying their individual memory."""

from app.db.session import get_connection
from app.models.team import TeamCreate


def list_teams() -> list[dict]:
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("""
            SELECT t.*,
              (SELECT COUNT(*) FROM projects p WHERE p.team_id = t.id
               AND p.code != '_agent-pool' AND p.status != 'removed' AND p.removed_at IS NULL) AS project_count,
              (SELECT COUNT(*) FROM team_agents ta JOIN agents a ON a.id = ta.agent_id
               WHERE ta.team_id = t.id AND a.status != 'deleted' AND a.is_template = 0) AS ai_member_count,
              (SELECT COUNT(*) FROM team_humans th JOIN humans h ON h.id = th.human_id
               WHERE th.team_id = t.id AND h.status = 'active') AS human_member_count
            FROM teams t WHERE t.client_id = 1 ORDER BY t.name, t.id
        """)]


def require_team(connection, team_id: int):
    row = connection.execute("SELECT * FROM teams WHERE id = ? AND client_id = 1", (team_id,)).fetchone()
    if row is None:
        raise ValueError("Team not found")
    return row


def get_team(team_id: int) -> dict:
    from app.repositories.project_repository import list_projects

    with get_connection() as connection:
        team = dict(require_team(connection, team_id))
        ai_members = [dict(row) for row in connection.execute("""
            SELECT a.id, a.name, a.username, a.handle, r.name AS role, a.status,
                   a.agent_description AS description
            FROM team_agents ta JOIN agents a ON a.id = ta.agent_id
            JOIN agent_roles r ON r.id = a.role_id
            WHERE ta.team_id = ? AND a.status != 'deleted' AND a.is_template = 0 ORDER BY a.name, a.id
        """, (team_id,))]
        human_members = [dict(row) for row in connection.execute("""
            SELECT h.id, h.display_name AS name, h.username, '@' || h.username AS handle,
                   h.role, h.status, COALESCE(h.email, '') AS description
            FROM team_humans th JOIN humans h ON h.id = th.human_id
            WHERE th.team_id = ? AND h.status = 'active' ORDER BY h.display_name, h.id
        """, (team_id,))]
        for members, table, column in [(ai_members, "project_agents", "agent_id"),
                                        (human_members, "project_members", "human_id")]:
            for member in members:
                member["projects"] = [dict(row) for row in connection.execute(f"""
                    SELECT p.id, p.name, p.status, p.delivery_stage
                    FROM projects p JOIN {table} m ON m.project_id = p.id
                    WHERE p.team_id = ? AND m.{column} = ? AND m.status != 'removed'
                      AND p.code != '_agent-pool' AND p.status != 'removed' AND p.removed_at IS NULL
                    ORDER BY p.name, p.id
                """, (team_id, member["id"]))]
    team.update(ai_members=ai_members, human_members=human_members,
                projects=[p.model_dump() for p in list_projects() if p.team_id == team_id])
    return team


def create_team(payload: TeamCreate) -> dict:
    with get_connection() as connection:
        team_id = connection.execute("INSERT INTO teams (name, description) VALUES (?, ?)",
                                     (payload.name, payload.description)).lastrowid
    return get_team(team_id)


def add_team_members(team_id: int, agent_ids: list[int], human_ids: list[int]) -> dict:
    with get_connection() as connection:
        require_team(connection, team_id)
        for agent_id in set(agent_ids):
            if connection.execute("""SELECT 1 FROM agents WHERE id = ? AND client_id = 1
                    AND is_template = 0 AND status = 'available'""", (agent_id,)).fetchone() is None:
                raise ValueError("Choose an available coworker from this workspace")
            connection.execute("INSERT OR IGNORE INTO team_agents (team_id, agent_id) VALUES (?, ?)", (team_id, agent_id))
        for human_id in set(human_ids):
            if connection.execute("SELECT 1 FROM humans WHERE id = ? AND status = 'active'", (human_id,)).fetchone() is None:
                raise ValueError("Human member not found")
            connection.execute("INSERT OR IGNORE INTO team_humans (team_id, human_id) VALUES (?, ?)", (team_id, human_id))
    return get_team(team_id)


def create_team_human(team_id: int, payload) -> dict:
    username = payload.username.strip().lstrip('@').lower()
    if not username:
        raise ValueError("Enter a username")
    with get_connection() as connection:
        require_team(connection, team_id)
        row = connection.execute("SELECT id FROM humans WHERE lower(username) = ?", (username,)).fetchone()
        if row is None:
            human_id = connection.execute("""INSERT INTO humans (display_name, username, email, role)
                VALUES (?, ?, ?, ?)""", (payload.name, username, payload.email or None, payload.role)).lastrowid
        else:
            human_id = row['id']
            if connection.execute("SELECT 1 FROM humans WHERE id = ? AND status = 'active'", (human_id,)).fetchone() is None:
                raise ValueError("This human is inactive")
        connection.execute("INSERT OR IGNORE INTO team_humans (team_id, human_id) VALUES (?, ?)", (team_id, human_id))
    return get_team(team_id)


def remove_team_member(team_id: int, member_id: int, kind: str) -> dict:
    table, column = ("team_agents", "agent_id") if kind == "agents" else ("team_humans", "human_id")
    with get_connection() as connection:
        require_team(connection, team_id)
        connection.execute(f"DELETE FROM {table} WHERE team_id = ? AND {column} = ?", (team_id, member_id))
    return get_team(team_id)


def move_project(team_id: int, project_id: int, include_existing_members: bool) -> dict:
    with get_connection() as connection:
        require_team(connection, team_id)
        project = connection.execute("""SELECT id FROM projects WHERE id = ? AND client_id = 1
            AND code != '_agent-pool' AND status != 'removed' AND removed_at IS NULL""", (project_id,)).fetchone()
        if project is None:
            raise ValueError("Project not found")
        if include_existing_members:
            connection.execute("""INSERT OR IGNORE INTO team_agents (team_id, agent_id)
                SELECT ?, agent_id FROM project_agents WHERE project_id = ? AND status != 'removed'""", (team_id, project_id))
            connection.execute("""INSERT OR IGNORE INTO team_humans (team_id, human_id)
                SELECT ?, human_id FROM project_members WHERE project_id = ? AND status != 'removed'""", (team_id, project_id))
        connection.execute("UPDATE projects SET team_id = ?, updated_at = datetime('now') WHERE id = ?", (team_id, project_id))
    return get_team(team_id)
