"""Human-supplied inputs and retry intent from the current project discussion."""

import re

from app.db.session import get_connection


_URL = re.compile(r"https?://[^\s<>\"'\\]+", re.I)
_RETRY = re.compile(
    r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:retry|try (?:it |that |this )?again|repeat (?:it|that|this))"
    r"(?:\s+(?:the\s+)?task\s*#?\s*\d+)?(?:\s+(?:now|please))?[?.! ]*$", re.I,
)


def _retry_intent(text: str) -> bool:
    if _RETRY.fullmatch(text.strip()):
        return True
    # Accept an operational preface such as "workspace access updated, please retry"
    # without treating "retry count is three" as a request to repeat the whole task.
    return bool(re.search(r'(?:^|[,;.!]\s*|\bplease\s+)(?:retry|try again|resume)(?:\s+(?:now|please|the task|task\s*#?\s*\d+))?[?.! ]*$', text, re.I))


def project_working_memory(project_id: int, agent_id: int, message_id: int | None,
                           request: str) -> tuple[str, str]:
    with get_connection() as connection:
        thread = connection.execute(
            """SELECT id FROM conversation_threads WHERE project_id = ?
               AND (? IS NULL OR id = (SELECT thread_id FROM messages WHERE id = ?))
               ORDER BY updated_at DESC, id DESC LIMIT 1""", (project_id, message_id, message_id),
        ).fetchone()
        if thread is None:
            return request, "No saved human inputs in this discussion."
        rows = connection.execute(
            """SELECT m.id, m.content, t.assigned_agent_id FROM messages m
               LEFT JOIN tasks t ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
                 AND t.project_id = ?
               WHERE m.thread_id = ? AND m.sender_type = 'human'
                 AND json_extract(m.metadata_json, '$.deleted_at') IS NULL
                 AND (? IS NULL OR m.id < ?) ORDER BY m.id""",
            (project_id, thread["id"], message_id, message_id),
        ).fetchall()
        agent = connection.execute("SELECT handle FROM agents WHERE id = ?", (agent_id,)).fetchone()
    references: dict[str, list[str]] = {}
    for row in [*rows, {"id": message_id or "current", "content": request}]:
        for match in _URL.finditer(row["content"].replace("\\n", "\n")):
            url = match.group().rstrip(".,;)")
            references.setdefault(url, []).append(str(row["id"]))
    inventory = "\n".join(f"- {url} (human messages: {', '.join(dict.fromkeys(ids))})"
                          for url, ids in references.items()) or "No shared source URLs recorded."
    inventory = ("The user already supplied these source references. A supplied link is not proof of its contents; "
                 "read it through permitted tools if needed. Ask about access failures, not for the same URL again.\n" + inventory)
    if _retry_intent(request):
        for row in reversed(rows):
            if row["assigned_agent_id"] != agent_id and not (agent and agent["handle"].lower() in row["content"].lower()):
                continue
            content = re.sub(r"(?<![\w@])@[\w.-]+", "", row["content"]).strip()
            content = re.sub(r"^/assign\b", "", content, flags=re.I).strip()
            if _retry_intent(content):
                continue
            if re.search(r"\b(?:prepare|create|generate|write|review|verify|align|revise|update|fix|check|summarize)\b", content, re.I):
                request += f"\n\nEarlier user work to resume (message #{row['id']}):\n{content}"
                break
    return request, inventory
