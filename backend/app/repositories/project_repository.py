import json
import re
import sqlite3
from typing import Any
from uuid import uuid4

from app.db.session import get_connection
from app.models.project import (
    AiMemberCreate,
    AiMemberUpdate,
    HumanMemberCreate,
    HumanMemberUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
)


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def _loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _summary_from_row(row: sqlite3.Row) -> ProjectSummary:
    return ProjectSummary(
        id=row["id"],
        team_id=row["team_id"],
        team_name=row["team_name"],
        code=row["code"],
        name=row["name"],
        description=row["description"],
        status=row["status"],
        business_domain=row["business_domain"],
        delivery_stage=row["delivery_stage"],
        priority=row["priority"],
        tech_stack=_loads_list(row["tech_stack_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        created_by=row["created_by"],
        updated_by=row["updated_by"],
        human_member_count=row["human_member_count"],
        ai_member_count=row["ai_member_count"],
    )


def _project_query(where_clause: str = "") -> str:
    return f"""
        SELECT
            projects.*,
            teams.name AS team_name,
            created_by.display_name AS created_by,
            updated_by.display_name AS updated_by,
            (
                SELECT COUNT(*)
                FROM project_members
                WHERE project_members.project_id = projects.id
                  AND project_members.status != 'removed'
            ) AS human_member_count,
            (
                SELECT COUNT(*)
                FROM project_agents
                WHERE project_agents.project_id = projects.id
                  AND project_agents.status != 'removed'
            ) AS ai_member_count
        FROM projects
        JOIN teams ON teams.id = projects.team_id
        LEFT JOIN humans created_by ON created_by.id = projects.created_by_human_id
        LEFT JOIN humans updated_by ON updated_by.id = projects.updated_by_human_id
        {where_clause}
        ORDER BY projects.updated_at DESC, projects.id DESC
    """


def list_projects(include_removed: bool = False) -> list[ProjectSummary]:
    where_clause = "" if include_removed else "WHERE projects.status != 'removed' AND projects.removed_at IS NULL"
    with get_connection() as connection:
        rows = connection.execute(_project_query(where_clause)).fetchall()
    return [_summary_from_row(row) for row in rows]


def get_project(project_id: int) -> ProjectDetail | None:
    with get_connection() as connection:
        row = connection.execute(
            _project_query("WHERE projects.id = ?"),
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        human_rows = connection.execute(
            """
            SELECT
                humans.id,
                humans.display_name,
                humans.username,
                humans.email,
                humans.role,
                project_members.member_role,
                project_members.status
            FROM project_members
            JOIN humans ON humans.id = project_members.human_id
            WHERE project_members.project_id = ?
              AND project_members.status != 'removed'
            ORDER BY project_members.id
            """,
            (project_id,),
        ).fetchall()
        ai_rows = connection.execute(
            """
            SELECT
                agents.id,
                agents.name,
                agents.username,
                agents.handle,
                agent_roles.code AS role,
                agents.status,
                agents.agent_description,
                agents.knowledge_scope
            FROM project_agents
            JOIN agents ON agents.id = project_agents.agent_id
            JOIN agent_roles ON agent_roles.id = agents.role_id
            WHERE project_agents.project_id = ?
              AND project_agents.status != 'removed'
            ORDER BY project_agents.id
            """,
            (project_id,),
        ).fetchall()

    summary = _summary_from_row(row)
    return ProjectDetail(
        **summary.model_dump(),
        repository_url=row["repository_url"],
        metadata=_loads_dict(row["metadata_json"]),
        removed_at=row["removed_at"],
        human_members=[dict(member) for member in human_rows],
        ai_members=[dict(member) for member in ai_rows],
    )


def create_project(payload: ProjectCreate) -> ProjectDetail:
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")[:60] or "project"
    code = payload.code or f"{slug}-{uuid4().hex[:8]}"
    selected_agents = list(dict.fromkeys(payload.agent_member_ids))
    with get_connection() as connection:
        agents = []
        if connection.execute("SELECT 1 FROM teams WHERE id = ? AND client_id = 1", (payload.team_id,)).fetchone() is None:
            raise ValueError("Team not found")
        if selected_agents:
            agents = connection.execute(
                f"""SELECT a.id, r.name AS role FROM agents a
                    JOIN agent_roles r ON r.id = a.role_id
                    WHERE a.id IN ({','.join('?' for _ in selected_agents)})
                      AND a.status = 'available' AND a.is_template = 0 AND a.client_id = 1
                      AND EXISTS (SELECT 1 FROM team_agents ta WHERE ta.agent_id = a.id AND ta.team_id = ?)""",
                [*selected_agents, payload.team_id],
            ).fetchall()
            if len(agents) != len(selected_agents):
                raise ValueError("Choose available AI coworkers from the selected team")
        cursor = connection.execute(
            """
            INSERT INTO projects (
                team_id,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.team_id,
                code,
                payload.name,
                payload.description,
                payload.status,
                payload.business_domain,
                payload.repository_url,
                payload.delivery_stage,
                payload.priority,
                json.dumps(payload.tech_stack),
                json.dumps(payload.metadata),
                payload.created_by_human_id,
                payload.created_by_human_id,
            ),
        )
        project_id = cursor.lastrowid
        if payload.created_by_human_id is not None:
            connection.execute("INSERT OR IGNORE INTO team_humans (team_id, human_id) VALUES (?, ?)",
                               (payload.team_id, payload.created_by_human_id))
        human_ids = list(dict.fromkeys([*payload.human_member_ids,
                                        *([payload.created_by_human_id] if payload.created_by_human_id else [])]))
        _replace_members(connection, project_id, human_ids)
        connection.executemany(
            """INSERT INTO project_agents (project_id, agent_id, member_role, status)
               VALUES (?, ?, ?, 'active')""",
            [(project_id, agent["id"], agent["role"]) for agent in agents],
        )
    project = get_project(project_id)
    if project is None:
        raise RuntimeError("Project was not created")
    return project


def update_project(project_id: int, payload: ProjectUpdate) -> ProjectDetail | None:
    existing = get_project(project_id)
    if existing is None:
        return None

    values = payload.model_dump(exclude_unset=True)
    human_member_ids = values.pop("human_member_ids", None)
    assignments: list[str] = []
    params: list[Any] = []
    json_fields = {"tech_stack": "tech_stack_json", "metadata": "metadata_json"}

    for field, value in values.items():
        column = json_fields.get(field, field)
        assignments.append(f"{column} = ?")
        params.append(json.dumps(value) if field in json_fields else value)

    assignments.append("updated_at = datetime('now')")

    with get_connection() as connection:
        if assignments:
            connection.execute(
                f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?",
                (*params, project_id),
            )
        if human_member_ids is not None:
            _replace_members(connection, project_id, human_member_ids)

    return get_project(project_id)


def remove_project(project_id: int, updated_by_human_id: int | None = None) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE projects
            SET status = 'removed',
                removed_at = datetime('now'),
                updated_at = datetime('now'),
                updated_by_human_id = COALESCE(?, updated_by_human_id)
            WHERE id = ?
            """,
            (updated_by_human_id, project_id),
        )
    return get_project(project_id)


def _replace_members(connection: sqlite3.Connection, project_id: int, human_ids: list[int]) -> None:
    connection.execute("DELETE FROM project_members WHERE project_id = ?", (project_id,))
    for human_id in human_ids:
        connection.execute(
            """
            INSERT OR IGNORE INTO project_members (project_id, human_id, member_role, status)
            VALUES (?, ?, 'member', 'active')
            """,
            (project_id, human_id),
        )


def add_human_member(project_id: int, payload: HumanMemberCreate) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None
    username = payload.username.strip().lower()
    with get_connection() as connection:
        # New human creation here also enrolls that identity into the parent team.
        row = connection.execute("SELECT id FROM humans WHERE username = ?", (username,)).fetchone()
        if row is None:
            cursor = connection.execute(
                """
                INSERT INTO humans (display_name, username, email, role, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (payload.name, username, payload.email, payload.role),
            )
            human_id = cursor.lastrowid
        else:
            human_id = row["id"]
            connection.execute(
                """
                UPDATE humans
                SET display_name = ?,
                    email = COALESCE(?, email),
                    role = ?,
                    status = 'active',
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (payload.name, payload.email, payload.role, human_id),
            )
        connection.execute("""INSERT OR IGNORE INTO team_humans (team_id, human_id)
            SELECT team_id, ? FROM projects WHERE id = ?""", (human_id, project_id))
        connection.execute(
            """
            INSERT INTO project_members (project_id, human_id, member_role, status)
            VALUES (?, ?, ?, 'active')
            ON CONFLICT(project_id, human_id) DO UPDATE SET
                member_role = excluded.member_role,
                status = 'active',
                updated_at = datetime('now')
            """,
            (project_id, human_id, payload.role),
        )
    return get_project(project_id)


def remove_human_member(project_id: int, human_id: int) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE project_members
            SET status = 'removed',
                updated_at = datetime('now')
            WHERE project_id = ?
              AND human_id = ?
            """,
            (project_id, human_id),
        )
    return get_project(project_id)


def update_human_member(
    project_id: int, human_id: int, payload: HumanMemberUpdate
) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None

    values = payload.model_dump(exclude_unset=True)
    with get_connection() as connection:
        membership = connection.execute(
            """
            SELECT 1 FROM project_members
            WHERE project_id = ? AND human_id = ? AND status != 'removed'
            """,
            (project_id, human_id),
        ).fetchone()
        if membership is None:
            return None

        updates: list[str] = []
        parameters: list[object] = []
        if "name" in values:
            updates.append("display_name = ?")
            parameters.append(values["name"])
        if "username" in values:
            updates.append("username = ?")
            parameters.append(values["username"].strip().lower())
        if "email" in values:
            updates.append("email = ?")
            parameters.append(values["email"])
        if "role" in values:
            updates.append("role = ?")
            parameters.append(values["role"])

        if updates:
            connection.execute(
                f"UPDATE humans SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?",
                (*parameters, human_id),
            )
        if "role" in values:
            connection.execute(
                """
                UPDATE project_members
                SET member_role = ?, updated_at = datetime('now')
                WHERE project_id = ? AND human_id = ?
                """,
                (values["role"], project_id, human_id),
            )
    return get_project(project_id)


def add_ai_member(project_id: int, payload: AiMemberCreate) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None
    username = payload.username.strip().lower()
    handle = f"@{payload.username.strip().lstrip('@')}"
    role_code = payload.role.strip().lower().replace(" ", "-")
    with get_connection() as connection:
        role = connection.execute("SELECT id FROM agent_roles WHERE code = ?", (role_code,)).fetchone()
        if role is None:
            cursor = connection.execute(
                """
                INSERT INTO agent_roles (code, name, description, default_instructions)
                VALUES (?, ?, ?, ?)
                """,
                (
                    role_code,
                    payload.role,
                    f"{payload.role} AI coworker role.",
                    "Use approved project knowledge. Ask humans when project scope or approvals are unclear.",
                ),
            )
            role_id = cursor.lastrowid
        else:
            role_id = role["id"]

        row = connection.execute("SELECT id, status, is_template FROM agents WHERE username = ?", (username,)).fetchone()
        if row is None:
            cursor = connection.execute(
                """
                INSERT INTO agents (
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
                VALUES (?, ?, ?, ?, ?, 'available', ?, ?, '["web_search","confluence_read","oracle_read"]', '[]', NULL)
                """,
                (
                    project_id,
                    role_id,
                    payload.name,
                    username,
                    handle,
                    payload.agent_description,
                    payload.agent_description or payload.role,
                ),
            )
            agent_id = cursor.lastrowid
        else:
            if row["is_template"]:
                raise ValueError("Create a coworker from this template before adding it to a project")
            if row["status"] == "deleted":
                raise ValueError("This agent was deleted; use a different username for a new agent")
            agent_id = row["id"]
            connection.execute(
                """
                UPDATE agents
                SET role_id = ?,
                    name = ?,
                    handle = ?,
                    status = 'available',
                    agent_description = ?,
                    knowledge_scope = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    role_id,
                    payload.name,
                    handle,
                    payload.agent_description,
                    payload.agent_description or payload.role,
                    agent_id,
                ),
            )

        connection.execute("""INSERT OR IGNORE INTO team_agents (team_id, agent_id)
            SELECT team_id, ? FROM projects WHERE id = ?""", (agent_id, project_id))
        connection.execute(
            """
            INSERT INTO project_agents (project_id, agent_id, member_role, status)
            VALUES (?, ?, ?, 'active')
            ON CONFLICT(project_id, agent_id) DO UPDATE SET
                member_role = excluded.member_role,
                status = 'active',
                updated_at = datetime('now')
            """,
            (project_id, agent_id, payload.role),
        )
    return get_project(project_id)


def remove_ai_member(project_id: int, agent_id: int) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE project_agents
            SET status = 'removed',
                updated_at = datetime('now')
            WHERE project_id = ?
              AND agent_id = ?
            """,
            (project_id, agent_id),
        )
    return get_project(project_id)


def update_ai_member(
    project_id: int, agent_id: int, payload: AiMemberUpdate
) -> ProjectDetail | None:
    if get_project(project_id) is None:
        return None

    values = payload.model_dump(exclude_unset=True)
    with get_connection() as connection:
        membership = connection.execute(
            """
            SELECT 1 FROM project_agents
            WHERE project_id = ? AND agent_id = ? AND status != 'removed'
            """,
            (project_id, agent_id),
        ).fetchone()
        if membership is None:
            return None

        updates: list[str] = []
        parameters: list[object] = []
        if "name" in values:
            updates.append("name = ?")
            parameters.append(values["name"])
        if "username" in values:
            username = values["username"].strip().lower()
            updates.extend(["username = ?", "handle = ?"])
            parameters.extend([username, f"@{username.lstrip('@')}"])
        if "agent_description" in values:
            description = values["agent_description"]
            updates.extend(["agent_description = ?", "knowledge_scope = ?"])
            parameters.extend([description, description or "FDD project knowledge"])
        if "role" in values:
            role_code = values["role"].strip().lower().replace(" ", "-")
            role = connection.execute(
                "SELECT id FROM agent_roles WHERE code = ?", (role_code,)
            ).fetchone()
            if role is None:
                cursor = connection.execute(
                    """
                    INSERT INTO agent_roles (code, name, description, default_instructions)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        role_code,
                        values["role"],
                        f"{values['role']} AI coworker role.",
                        "Use approved project knowledge. Ask humans when project scope or approvals are unclear.",
                    ),
                )
                role_id = cursor.lastrowid
            else:
                role_id = role["id"]
            updates.append("role_id = ?")
            parameters.append(role_id)

        if updates:
            connection.execute(
                f"UPDATE agents SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?",
                (*parameters, agent_id),
            )
        if "role" in values:
            connection.execute(
                """
                UPDATE project_agents
                SET member_role = ?, updated_at = datetime('now')
                WHERE project_id = ? AND agent_id = ?
                """,
                (values["role"], project_id, agent_id),
            )
    return get_project(project_id)
