"""Owner-scoped chat edits with revision history and permanent message deletion."""

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from app.db.session import get_connection
from app.core.config import settings
from app.repositories.chat_repository import _message_from_row


def change_message(project_id: int, message_id: int, human_id: int, content: str | None):
    with get_connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        query = """SELECT m.*, h.display_name AS human_name, h.role AS human_role,
                     NULL AS agent_name, NULL AS agent_handle, NULL AS agent_role
                   FROM messages m JOIN conversation_threads ct ON ct.id = m.thread_id
                   LEFT JOIN humans h ON h.id = m.sender_human_id
                   WHERE m.id = ? AND ct.project_id = ?"""
        row = connection.execute(query, (message_id, project_id)).fetchone()
        if row is None:
            raise HTTPException(404, 'Message not found in this project')
        cleanup_delete = content is None and settings.chat_cleanup_mode
        if not cleanup_delete and (row['sender_type'] != 'human' or row['sender_human_id'] != human_id):
            raise HTTPException(403, 'You can edit or delete only your own messages')
        if not connection.execute(
            "SELECT 1 FROM project_members WHERE project_id = ? AND human_id = ? AND status != 'removed'",
            (project_id, human_id),
        ).fetchone():
            raise HTTPException(403, 'Sender is not an active member of this project')
        metadata = json.loads(row['metadata_json'] or '{}')
        if metadata.get('deleted_at') and content is not None:
            raise HTTPException(409, 'This message has already been deleted')
        if connection.execute(
            """SELECT 1 FROM codex_runs cr JOIN tasks t ON t.id = cr.task_id
               WHERE t.project_id = ? AND cr.process_status IN ('queued', 'running')
                 AND CAST(json_extract(cr.command_json, '$.message_id') AS INTEGER) = ? LIMIT 1""",
            (project_id, message_id),
        ).fetchone():
            raise HTTPException(409, 'Wait for this message\'s queued or running work to finish before editing or deleting it')
        if content is not None and not content.strip():
            raise HTTPException(400, 'Message cannot be empty')
        if content is None:
            connection.execute('DELETE FROM messages WHERE id = ?', (message_id,))
            connection.execute("UPDATE conversation_threads SET updated_at = datetime('now') WHERE id = ?", (row['thread_id'],))
            return None
        now = datetime.now(timezone.utc).isoformat()
        metadata.setdefault('message_revisions', []).append({
            'content': row['content'], 'previous_edited_at': metadata.get('edited_at'),
            'action': 'edit', 'at': now, 'human_id': human_id,
        })
        metadata['edited_at'] = now
        connection.execute('UPDATE messages SET content = ?, metadata_json = ? WHERE id = ?',
                           (content.strip(), json.dumps(metadata), message_id))
        connection.execute("UPDATE conversation_threads SET updated_at = datetime('now') WHERE id = ?", (row['thread_id'],))
        return _message_from_row(connection.execute(query, (message_id, project_id)).fetchone())
