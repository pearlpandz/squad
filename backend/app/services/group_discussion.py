"""Explicit team invitations and bounded, persisted discussion turns."""

import json
import re

from app.db.session import get_connection


def discussion_participants(content: str, mentioned: list, available: list,
                            previous: list[int]) -> list[int]:
    invited = [row['id'] for row in mentioned]
    explicit = bool(re.match(r'^\s*/discuss\b', content, re.I))
    if not explicit and not invited and (re.fullmatch(
        r'\s*(?:hi|hello|hey|thanks|thank you|ok|okay|noted)[.! ]*', content, re.I)
        or content.lstrip().startswith('/assign')):
        return []
    addressed_together = bool(re.match(
        r'^\s*(?:/assign\s+)?(?:@[\w.-]+\s*(?:,|&|\band\b)?\s*){2,}', content, re.I))
    team_intent = bool(re.search(r'\b(?:both|together|discuss|discussion|collaborate|everyone)\b', content, re.I))
    if explicit:
        selected = invited or [row['id'] for row in available]
    elif len(invited) > 1 and (addressed_together or team_intent):
        selected = invited
    elif not invited:
        selected = previous
    else:
        selected = []
    active = {row['id'] for row in available}
    return list(dict.fromkeys(agent_id for agent_id in selected if agent_id in active))


def previous_discussion(project_id: int, thread_id: int) -> list[int]:
    with get_connection() as connection:
        row = connection.execute(
            """SELECT m.metadata_json FROM messages m JOIN conversation_threads ct ON ct.id = m.thread_id
               WHERE ct.project_id = ? AND ct.id = ? AND m.sender_type = 'human'
                 AND json_extract(m.metadata_json, '$.deleted_at') IS NULL
               ORDER BY m.id DESC LIMIT 1""", (project_id, thread_id),
        ).fetchone()
    return json.loads(row['metadata_json']).get('discussion_agent_ids', []) if row else []


def discussion_entries(project_id: int, task_id: int, run_id: int,
                       discussion_id: int) -> list[tuple[str, str]]:
    """Include only earlier replies to this invitation, never later human messages."""
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT cr.id, a.name, cr.process_status, cr.output_summary FROM codex_runs cr
               JOIN tasks t ON t.id = cr.task_id
               JOIN agents a ON a.id = CAST(json_extract(cr.command_json, '$.agent_id') AS INTEGER)
               WHERE t.project_id = ? AND cr.task_id = ? AND cr.id < ?
                 AND CAST(json_extract(cr.command_json, '$.discussion.message_id') AS INTEGER) = ?
                 AND cr.process_status IN ('completed', 'failed') ORDER BY cr.id""",
            (project_id, task_id, run_id, discussion_id),
        ).fetchall()
    return [(f"discussion:run:{row['id']}",
             f"{row['name']} ({row['process_status']}): {row['output_summary'] or 'No response recorded.'}")
            for row in rows]
