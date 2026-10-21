"""Load approved coworker skill instructions from its trained file index."""


def trained_skill_instructions(connection, agent_id: int, max_chars: int = 24000) -> str:
    rows = connection.execute(
        """SELECT s.title, i.content FROM agent_sources s
           JOIN agent_source_index i ON i.source_id = s.id
           WHERE s.agent_id = ? AND s.approval_status = 'approved'
             AND lower(s.title) IN ('skill.md', 'instructions.md', 'boundaries.md')
           ORDER BY CASE lower(s.title) WHEN 'boundaries.md' THEN 1 ELSE 0 END, s.id""",
        (agent_id,),
    ).fetchall()
    parts = []
    for row in rows:
        passage = f"Skill source: {row['title']}\n{row['content']}"
        parts.append(passage)
    result = "\n\n".join(parts)
    if len(result) > max_chars:
        raise RuntimeError("Approved skill instructions and boundaries exceed the safe context budget; no policy was truncated.")
    return result


def trained_template_documents(connection, agent_id: int) -> str:
    """Always include approved trained template text, rather than ranking its chunks."""
    rows = connection.execute(
        """SELECT s.title, s.relative_path, i.content FROM agent_sources s
           JOIN agent_source_index i ON i.source_id = s.id
           WHERE s.agent_id = ? AND s.approval_status = 'approved'
             AND lower(s.title) LIKE '%template%' ORDER BY s.id""", (agent_id,),
    ).fetchall()
    result = "\n\n".join(f"Approved template: {row['title']}\nSource: {row['relative_path']}\n{row['content']}"
                           for row in rows)
    if len(result) > 60000:
        raise RuntimeError("Approved templates exceed the safe context budget. Select the template to use; no template was truncated.")
    return result
