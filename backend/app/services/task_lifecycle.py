"""Keep a requirement-to-deliverable workflow together across chat turns."""

import re
from urllib.parse import parse_qs, urlsplit, unquote


def brd_identity(content: str) -> str | None:
    """Only BRD-labelled links identify input; supporting links do not split tasks."""
    for match in re.finditer(r"https?://[^\s<>\"'\\]+", content):
        raw = match.group().rstrip(".,;:)")
        context = content[max(0, match.start() - 160):match.end() + 80]
        if not re.search(r"\bbrd\b|business requirements?", context, re.I):
            continue
        url = urlsplit(raw)
        page_id = parse_qs(url.query).get("pageId")
        if page_id:
            return f"{url.netloc.lower()}:page:{page_id[0]}"
        return f"{url.netloc.lower()}{unquote(url.path).rstrip('/')}?{url.query}"
    return None


def workflow_task(connection, project_id: int, message_id: int, content: str,
                  suggested_task_id: int | None) -> tuple[int | None, str | None]:
    thread = connection.execute(
        "SELECT thread_id FROM messages WHERE id = ?", (message_id,),
    ).fetchone()
    thread_id = thread["thread_id"]
    current = connection.execute(
        "SELECT task_id, brd_key FROM task_workflows WHERE thread_id = ?", (thread_id,),
    ).fetchone()
    identity = brd_identity(content)
    changed = bool(re.search(
        r"\b(?:new|different|changed|revised|updated|replace[ds]?)\s+(?:the\s+)?BRD\b|"
        r"\bBRD\s+(?:has\s+|is\s+)?(?:changed|revised|updated|replaced)\b", content, re.I,
    ))
    # A revision at the same URL needs an explicit input-change statement.
    if current:
        if changed or (identity and current["brd_key"] and identity != current["brd_key"]):
            return None, identity or f"revision:message:{message_id}"
        return current["task_id"], identity or current["brd_key"]
    if changed:
        return None, identity or f"revision:message:{message_id}"
    if suggested_task_id is not None:
        existing = connection.execute(
            "SELECT id FROM tasks WHERE id = ? AND project_id = ? AND thread_id = ?",
            (suggested_task_id, project_id, thread_id),
        ).fetchone()
        if existing:
            return existing["id"], identity
    # Bootstrap existing discussions without moving or deleting historical runs/files.
    previous = connection.execute(
        """SELECT t.id, m.content FROM messages m JOIN tasks t
           ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
           WHERE m.thread_id = ? AND t.project_id = ? AND m.id < ?
           AND m.sender_type = 'human'
           AND json_extract(m.metadata_json, '$.deleted_at') IS NULL
           ORDER BY m.id DESC LIMIT 1""",
        (thread_id, project_id, message_id),
    ).fetchone()
    if previous:
        old_identity = brd_identity(previous["content"])
        if identity and old_identity and identity != old_identity:
            return None, identity
        return previous["id"], identity or old_identity
    return None, identity


def bind_workflow(connection, message_id: int, task_id: int, brd_key: str | None) -> None:
    connection.execute(
        """INSERT INTO task_workflows (thread_id, task_id, brd_key)
           VALUES ((SELECT thread_id FROM messages WHERE id = ?), ?, ?)
           ON CONFLICT(thread_id) DO UPDATE SET task_id = excluded.task_id,
             brd_key = excluded.brd_key""", (message_id, task_id, brd_key),
    )
