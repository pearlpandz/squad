from app.db.session import get_connection


def list_agent_profiles() -> list[dict[str, str]]:
    query = """
        SELECT
            agents.name,
            agent_roles.code AS role,
            agents.status,
            agents.knowledge_scope
        FROM agents
        JOIN agent_roles ON agent_roles.id = agents.role_id
        JOIN projects ON projects.id = agents.project_id
        WHERE projects.status = 'active' AND agents.status != 'deleted'
        ORDER BY agents.id
    """
    with get_connection() as connection:
        rows = connection.execute(query).fetchall()
    return [dict(row) for row in rows]
