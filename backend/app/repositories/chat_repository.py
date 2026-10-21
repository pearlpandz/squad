import json
import sqlite3
from typing import Any

from app.db.session import get_connection
from app.core.config import settings
from app.models.chat import ChatMessage, ChatMessageCreate, ChatThread, ProjectChat, CoworkerActivity


def _loads_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _thread_from_row(row: sqlite3.Row) -> ChatThread:
    return ChatThread(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _message_from_row(row: sqlite3.Row) -> ChatMessage:
    metadata = _loads_dict(row["metadata_json"])
    metadata.pop('message_revisions', None)
    sender_name = row["human_name"] or row["agent_name"] or ("Task Router" if row["sender_type"] == "system" else "Unknown")
    return ChatMessage(
        id=row["id"],
        thread_id=row["thread_id"],
        sender_type=row["sender_type"],
        sender_human_id=row["sender_human_id"],
        sender_agent_id=row["sender_agent_id"],
        sender_name=sender_name,
        sender_role=row["human_role"] or row["agent_role"],
        sender_handle=row["agent_handle"],
        content="Message deleted" if metadata.get('deleted_at') else row["content"],
        metadata=metadata,
        created_at=row["created_at"],
    )


def get_or_create_project_thread(project_id: int) -> ChatThread | None:
    with get_connection() as connection:
        project = connection.execute(
            "SELECT id, name FROM projects WHERE id = ? AND status != 'removed' AND removed_at IS NULL",
            (project_id,),
        ).fetchone()
        if project is None:
            return None

        row = connection.execute(
            """
            SELECT *
            FROM conversation_threads
            WHERE project_id = ?
              AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            cursor = connection.execute(
                """
                INSERT INTO conversation_threads (project_id, title, status, created_by_human_id)
                VALUES (?, ?, 'active', NULL)
                """,
                (project_id, f"{project['name']} Collaboration Thread"),
            )
            row = connection.execute(
                "SELECT * FROM conversation_threads WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()

    return _thread_from_row(row) if row is not None else None


def list_thread_messages(thread_id: int) -> list[ChatMessage]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                messages.*,
                humans.display_name AS human_name,
                humans.role AS human_role,
                agents.name AS agent_name,
                agents.handle AS agent_handle,
                agent_roles.code AS agent_role
            FROM messages
            LEFT JOIN humans ON humans.id = messages.sender_human_id
            LEFT JOIN agents ON agents.id = messages.sender_agent_id
            LEFT JOIN agent_roles ON agent_roles.id = agents.role_id
            WHERE messages.thread_id = ?
            ORDER BY messages.created_at ASC, messages.id ASC
            """,
            (thread_id,),
        ).fetchall()
    return [_message_from_row(row) for row in rows]


def get_project_chat(project_id: int) -> ProjectChat | None:
    thread = get_or_create_project_thread(project_id)
    if thread is None:
        return None
    with get_connection() as connection:
        active = connection.execute(
            """SELECT a.id AS agent_id, a.name, cr.id AS run_id, cr.process_status AS status
               FROM codex_runs cr JOIN tasks t ON t.id = cr.task_id
               JOIN agents a ON a.id = COALESCE(
                 CAST(json_extract(cr.command_json, '$.agent_id') AS INTEGER), t.assigned_agent_id)
               WHERE t.project_id = ? AND t.thread_id = ?
                 AND cr.process_status IN ('queued', 'running')
               ORDER BY CASE cr.process_status WHEN 'running' THEN 0 ELSE 1 END, cr.id""",
            (project_id, thread.id),
        ).fetchall()
    coworkers = {}
    for row in active:
        coworkers.setdefault(row['agent_id'], CoworkerActivity(**dict(row)))
    return ProjectChat(thread=thread, messages=list_thread_messages(thread.id),
                       active_coworkers=list(coworkers.values()), cleanup_mode=settings.chat_cleanup_mode)


def create_project_chat_message(project_id: int, payload: ChatMessageCreate) -> ChatMessage | None:
    thread = get_or_create_project_thread(project_id)
    if thread is None:
        return None

    sender_type = "agent" if payload.sender_agent_id else "human"
    sender_human_id = None if payload.sender_agent_id else payload.sender_human_id

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (
                thread_id,
                sender_type,
                sender_human_id,
                sender_agent_id,
                content,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                thread.id,
                sender_type,
                sender_human_id,
                payload.sender_agent_id,
                payload.content.strip(),
                json.dumps(payload.metadata),
            ),
        )
        connection.execute(
            "UPDATE conversation_threads SET updated_at = datetime('now') WHERE id = ?",
            (thread.id,),
        )
        row = connection.execute(
            """
            SELECT
                messages.*,
                humans.display_name AS human_name,
                humans.role AS human_role,
                agents.name AS agent_name,
                agents.handle AS agent_handle,
                agent_roles.code AS agent_role
            FROM messages
            LEFT JOIN humans ON humans.id = messages.sender_human_id
            LEFT JOIN agents ON agents.id = messages.sender_agent_id
            LEFT JOIN agent_roles ON agent_roles.id = agents.role_id
            WHERE messages.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()

    return _message_from_row(row) if row is not None else None


def create_project_system_message(project_id: int, content: str, metadata: dict[str, Any]) -> ChatMessage | None:
    """Record a built-in router reply without adding a project coworker."""
    thread = get_or_create_project_thread(project_id)
    if thread is None:
        return None
    with get_connection() as connection:
        cursor = connection.execute(
            """INSERT INTO messages (thread_id, sender_type, content, metadata_json)
               VALUES (?, 'system', ?, ?)""",
            (thread.id, content, json.dumps(metadata)),
        )
        connection.execute("UPDATE conversation_threads SET updated_at = datetime('now') WHERE id = ?", (thread.id,))
        row = connection.execute(
            """SELECT messages.*, humans.display_name AS human_name, humans.role AS human_role,
                      agents.name AS agent_name, agents.handle AS agent_handle,
                      agent_roles.code AS agent_role
               FROM messages LEFT JOIN humans ON humans.id = messages.sender_human_id
               LEFT JOIN agents ON agents.id = messages.sender_agent_id
               LEFT JOIN agent_roles ON agent_roles.id = agents.role_id
               WHERE messages.id = ?""",
            (cursor.lastrowid,),
        ).fetchone()
    return _message_from_row(row)
