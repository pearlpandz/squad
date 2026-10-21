import hashlib
import re
from collections import Counter

from app.db.session import get_connection
from app.services.knowledge_documents import (
    MAX_SOURCE_BYTES, SUPPORTED_EXTENSIONS, parse_knowledge_file, split_knowledge_text,
)
from app.services.semantic_search import EMBEDDING_INDEX_VERSION, embed_documents


MAX_NODE_CHARS = 30_000
STOP_WORDS = {
    "about", "after", "again", "also", "been", "from", "have", "into", "just",
    "more", "only", "other", "that", "their", "them", "there", "these", "this",
    "those", "through", "using", "were", "what", "when", "where", "which",
    "while", "with", "would", "your", "project", "agent", "task", "message",
}


def _source_text(relative_path: str) -> str:
    return parse_knowledge_file(relative_path).text


def _terms(content: str) -> Counter[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", content.lower())
    return Counter(word for word in words if word not in STOP_WORDS)


def _upsert_node(connection, agent_id: int, project_id: int, kind: str, source_id: str, title: str, content: str) -> str:
    content = content.strip()[:MAX_NODE_CHARS]
    if not content:
        removed = connection.execute(
            """DELETE FROM agent_knowledge_nodes WHERE agent_id = ? AND project_id = ?
            AND source_kind = ? AND source_id = ?""",
            (agent_id, project_id, kind, source_id),
        ).rowcount
        return "removed" if removed else "empty"
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    row = connection.execute(
        """SELECT id, checksum FROM agent_knowledge_nodes
        WHERE agent_id = ? AND project_id = ? AND source_kind = ? AND source_id = ?""",
        (agent_id, project_id, kind, source_id),
    ).fetchone()
    if row is not None and row["checksum"] == checksum:
        return "unchanged"
    outcome = "updated" if row is not None else "added"
    connection.execute(
        """INSERT INTO agent_knowledge_nodes
        (agent_id, project_id, source_kind, source_id, title, content, checksum)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id, project_id, source_kind, source_id) DO UPDATE SET
          title = excluded.title, content = excluded.content, checksum = excluded.checksum,
          updated_at = datetime('now')""",
        (agent_id, project_id, kind, source_id, title, content, checksum),
    )
    node = connection.execute(
        """SELECT id FROM agent_knowledge_nodes
        WHERE agent_id = ? AND project_id = ? AND source_kind = ? AND source_id = ?""",
        (agent_id, project_id, kind, source_id),
    ).fetchone()
    connection.execute("DELETE FROM agent_knowledge_terms WHERE agent_id = ? AND node_id = ?", (agent_id, node["id"]))
    connection.executemany(
        "INSERT INTO agent_knowledge_terms (agent_id, node_id, term, weight) VALUES (?, ?, ?, ?)",
        [(agent_id, node["id"], term, count) for term, count in _terms(f"{title} {content}").most_common(150)],
    )
    return outcome


def _sync_agent_graph(connection, agent_id: int, sources: list[dict], preserve_keys: set[str]) -> tuple[list[dict], dict]:
    connection.execute("INSERT OR IGNORE INTO agent_graphs (agent_id) VALUES (?)", (agent_id,))
    details: list[dict] = []
    seen = set(preserve_keys)
    for source in sources:
        key = source["source_key"]
        seen.add(key)
        content = source["content"].strip()
        if not content:
            continue
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = connection.execute(
            "SELECT checksum FROM agent_graph_sources WHERE agent_id = ? AND source_key = ?",
            (agent_id, key),
        ).fetchone()
        outcome = "unchanged" if existing and existing["checksum"] == checksum else "updated" if existing else "added"
        if outcome != "unchanged":
            connection.execute(
                """INSERT INTO agent_graph_sources
                (agent_id, source_key, project_id, project_name, source_kind, source_id, title, content, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id, source_key) DO UPDATE SET
                    project_id = excluded.project_id, project_name = excluded.project_name,
                    title = excluded.title, content = excluded.content, checksum = excluded.checksum,
                    updated_at = datetime('now')""",
                (agent_id, key, source["project_id"], source["project_name"],
                 source["source_kind"], source["source_id"], source["title"], content, checksum),
            )
            connection.execute(
                "DELETE FROM agent_graph_edges WHERE agent_id = ? AND source_key = ?", (agent_id, key),
            )
            terms = _terms(f"{source['title']} {content}").most_common(1500)
            connection.executemany(
                "INSERT OR IGNORE INTO agent_graph_concepts (agent_id, term) VALUES (?, ?)",
                [(agent_id, term) for term, _ in terms],
            )
            connection.executemany(
                "INSERT INTO agent_graph_edges (agent_id, source_key, term, weight) VALUES (?, ?, ?, ?)",
                [(agent_id, key, term, weight) for term, weight in terms],
            )
            connection.execute(
                """INSERT INTO agent_graph_history
                (agent_id, source_key, project_id, project_name, source_kind, source_id, title, checksum, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, key, source["project_id"], source["project_name"],
                 source["source_kind"], source["source_id"], source["title"], checksum, outcome),
            )
        chunk_state = connection.execute(
            """SELECT COUNT(*) AS chunk_count, MAX(LENGTH(content)) AS max_length
            FROM agent_graph_chunks WHERE agent_id = ? AND source_key = ?""",
            (agent_id, key),
        ).fetchone()
        rebuild_chunks = (outcome != "unchanged" or chunk_state["chunk_count"] == 0
                          or (chunk_state["max_length"] or 0) > 900)
        if rebuild_chunks:
            chunks = source["chunks"]
            embeddings = embed_documents([chunk.text for chunk in chunks])
            connection.execute(
                "DELETE FROM agent_graph_chunks WHERE agent_id = ? AND source_key = ?", (agent_id, key),
            )
            connection.executemany(
                """INSERT INTO agent_graph_chunks
                (agent_id, source_key, chunk_index, locator, content, checksum, embedding, embedding_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(agent_id, key, index, chunk.locator, chunk.text,
                  hashlib.sha256(chunk.text.encode("utf-8")).hexdigest(), embeddings[index], EMBEDDING_INDEX_VERSION)
                 for index, chunk in enumerate(chunks)],
            )
        else:
            missing = connection.execute(
                """SELECT chunk_index, content FROM agent_graph_chunks
                WHERE agent_id = ? AND source_key = ?
                  AND (embedding IS NULL OR embedding_model IS NULL OR embedding_model != ?)
                ORDER BY chunk_index""", (agent_id, key, EMBEDDING_INDEX_VERSION),
            ).fetchall()
            if missing:
                embeddings = embed_documents([row["content"] for row in missing])
                connection.executemany(
                    """UPDATE agent_graph_chunks SET embedding = ?, embedding_model = ?
                    WHERE agent_id = ? AND source_key = ? AND chunk_index = ?""",
                    [(embeddings[index], EMBEDDING_INDEX_VERSION, agent_id, key, row["chunk_index"])
                     for index, row in enumerate(missing)],
                )
        details.append({key_: source[key_] for key_ in ("project_id", "project_name", "source_kind", "source_id", "title")} |
                       {"outcome": outcome, "preview": " ".join(content.split())[:240]})

    for stale in connection.execute(
        """SELECT source_key, project_id, project_name, source_kind, source_id, title, checksum
        FROM agent_graph_sources WHERE agent_id = ?""", (agent_id,),
    ).fetchall():
        if stale["source_key"] in seen:
            continue
        connection.execute(
            "DELETE FROM agent_graph_sources WHERE agent_id = ? AND source_key = ?",
            (agent_id, stale["source_key"]),
        )
        connection.execute(
            """INSERT INTO agent_graph_history
            (agent_id, source_key, project_id, project_name, source_kind, source_id, title, checksum, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'removed')""",
            (agent_id, stale["source_key"], stale["project_id"], stale["project_name"],
             stale["source_kind"], stale["source_id"], stale["title"], stale["checksum"]),
        )
        details.append({key_: stale[key_] for key_ in ("project_id", "project_name", "source_kind", "source_id", "title")} |
                       {"outcome": "removed", "preview": ""})

    connection.execute(
        """DELETE FROM agent_graph_concepts WHERE agent_id = ? AND NOT EXISTS (
            SELECT 1 FROM agent_graph_edges e
            WHERE e.agent_id = agent_graph_concepts.agent_id AND e.term = agent_graph_concepts.term
        )""", (agent_id,),
    )
    connection.execute("UPDATE agent_graphs SET last_trained_at = datetime('now') WHERE agent_id = ?", (agent_id,))
    counts = {row["kind"]: row["count"] for row in connection.execute(
        """SELECT 'sources' AS kind, COUNT(*) AS count FROM agent_graph_sources WHERE agent_id = ?
        UNION ALL SELECT 'concepts', COUNT(*) FROM agent_graph_concepts WHERE agent_id = ?
        UNION ALL SELECT 'edges', COUNT(*) FROM agent_graph_edges WHERE agent_id = ?""",
        (agent_id, agent_id, agent_id),
    ).fetchall()}
    return details, counts


def _pending_training_items(connection, agent_id: int) -> list[dict]:
    """Describe pending work without parsing documents or running embeddings."""
    agent = connection.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if agent is None:
        return []
    existing = {row["source_key"]: row for row in connection.execute(
        "SELECT source_key, title, checksum, updated_at FROM agent_graph_sources WHERE agent_id = ?",
        (agent_id,),
    ).fetchall()}
    chunks = {row["source_key"] for row in connection.execute(
        "SELECT DISTINCT source_key FROM agent_graph_chunks WHERE agent_id = ? AND embedding_model = ?",
        (agent_id, EMBEDDING_INDEX_VERSION),
    ).fetchall()}
    pending: list[dict] = []
    seen: set[str] = set()

    def consider(key: str, title: str, kind: str, content: str | None = None,
                 updated_at: str | None = None) -> None:
        seen.add(key)
        previous = existing.get(key)
        changed = (content is not None and previous is not None and
                   hashlib.sha256(content.strip().encode("utf-8")).hexdigest() != previous["checksum"])
        changed = changed or bool(updated_at and previous and updated_at > previous["updated_at"])
        if previous is None or changed or key not in chunks:
            pending.append({"source_key": key, "title": title, "source_kind": kind,
                            "action": "added" if previous is None else "updated"})

    sources = connection.execute(
        "SELECT id, title, updated_at FROM agent_sources WHERE agent_id = ? AND approval_status = 'approved' ORDER BY id",
        (agent_id,),
    ).fetchall()
    for source in sources:
        consider(f"file:{source['id']}", source["title"], "file", updated_at=source["updated_at"])
    if not agent["is_template"]:
        for lesson in connection.execute(
            "SELECT id, title, content FROM agent_lessons WHERE agent_id = ? AND approval_status = 'approved'",
            (agent_id,),
        ).fetchall():
            consider(f"lesson:{lesson['id']}", lesson["title"], "lesson", lesson["content"])
        projects = connection.execute(
            """SELECT p.id FROM project_agents pa JOIN projects p ON p.id = pa.project_id
               WHERE pa.agent_id = ? AND pa.status != 'removed'
                 AND p.status != 'removed' AND p.removed_at IS NULL""", (agent_id,),
        ).fetchall()
        for project in projects:
            project_id = project["id"]
            for task in connection.execute(
                """SELECT t.id, t.title, t.prompt, cr.output_summary FROM tasks t
                   LEFT JOIN codex_runs cr ON cr.id = (
                       SELECT id FROM codex_runs WHERE task_id = t.id ORDER BY id DESC LIMIT 1)
                   WHERE t.project_id = ? AND t.assigned_agent_id = ? AND t.status IN ('completed', 'done')""",
                (project_id, agent_id),
            ).fetchall():
                consider(f"task:{project_id}:{task['id']}", task["title"], "task",
                         f"Task: {task['prompt']}\nOutcome: {task['output_summary'] or ''}")
            for message in connection.execute(
                """SELECT m.id, m.content FROM messages m
                   JOIN conversation_threads ct ON ct.id = m.thread_id
                   LEFT JOIN tasks t ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
                     AND t.project_id = ct.project_id
                   WHERE ct.project_id = ? AND (m.sender_agent_id = ? OR t.assigned_agent_id = ?)""",
                (project_id, agent_id, agent_id),
            ).fetchall():
                if message["content"].strip():
                    consider(f"chat:{project_id}:{message['id']}", f"Chat message {message['id']}",
                             "chat", message["content"])
    for key, previous in existing.items():
        if key not in seen:
            pending.append({"source_key": key, "title": previous["title"],
                            "source_kind": key.split(":", 1)[0], "action": "removed"})
    if agent["is_template"] and sources:
        latest = connection.execute(
            "SELECT * FROM agent_template_versions WHERE template_agent_id = ? ORDER BY version DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        if latest is None or any(latest[field] != agent[value] for field, value in (
            ("role_id", "role_id"), ("description", "agent_description"),
            ("knowledge_scope", "knowledge_scope"), ("instructions", "template_instructions"),
            ("tool_permissions_json", "tool_permissions_json"),
        )):
            pending.append({"source_key": "template:settings", "title": "Template instructions and settings",
                            "source_kind": "template", "action": "updated"})
    return pending


def get_agent_knowledge_index(agent_id: int) -> dict:
    with get_connection() as connection:
        graph = connection.execute(
            "SELECT created_at, last_trained_at FROM agent_graphs WHERE agent_id = ?", (agent_id,),
        ).fetchone()
        rows = connection.execute(
            """SELECT project_id, project_name, source_kind, source_id, title, updated_at
            FROM agent_graph_sources WHERE agent_id = ?
            ORDER BY project_name, source_kind, title""",
            (agent_id,),
        ).fetchall()
        concept_count = connection.execute(
            "SELECT COUNT(*) FROM agent_graph_concepts WHERE agent_id = ?", (agent_id,),
        ).fetchone()[0]
        edge_count = connection.execute(
            "SELECT COUNT(*) FROM agent_graph_edges WHERE agent_id = ?", (agent_id,),
        ).fetchone()[0]
        chunk_count = connection.execute(
            "SELECT COUNT(*) FROM agent_graph_chunks WHERE agent_id = ?", (agent_id,),
        ).fetchone()[0]
        pending_additions = connection.execute(
            """SELECT COUNT(*) FROM agent_sources a
            WHERE a.agent_id = ? AND a.approval_status = 'approved'
              AND NOT EXISTS (
                SELECT 1 FROM agent_graph_sources s
                WHERE s.agent_id = a.agent_id AND s.source_key = 'file:' || a.id
              )""", (agent_id,),
        ).fetchone()[0] + connection.execute(
            """SELECT COUNT(*) FROM agent_lessons l
               WHERE l.agent_id = ? AND l.approval_status = 'approved'
                 AND NOT EXISTS (SELECT 1 FROM agent_graph_sources s
                                 WHERE s.agent_id = l.agent_id AND s.source_key = 'lesson:' || l.id)""",
            (agent_id,),
        ).fetchone()[0]
        pending_removals = connection.execute(
            """SELECT COUNT(*) FROM agent_graph_sources s
            WHERE s.agent_id = ? AND s.source_kind = 'file'
              AND NOT EXISTS (
                SELECT 1 FROM agent_sources a
                WHERE a.agent_id = s.agent_id AND a.approval_status = 'approved'
                  AND s.source_key = 'file:' || a.id
              )""", (agent_id,),
        ).fetchone()[0] + connection.execute(
            """SELECT COUNT(*) FROM agent_graph_sources s
               WHERE s.agent_id = ? AND s.source_kind = 'lesson'
                 AND NOT EXISTS (SELECT 1 FROM agent_lessons l
                                 WHERE l.agent_id = s.agent_id AND l.approval_status = 'approved'
                                   AND s.source_key = 'lesson:' || l.id)""",
            (agent_id,),
        ).fetchone()[0]
        pending_items = _pending_training_items(connection, agent_id)
        history = connection.execute(
            """SELECT source_key, project_name, source_kind, title, outcome, recorded_at
            FROM agent_graph_history WHERE agent_id = ? ORDER BY id DESC LIMIT 50""",
            (agent_id,),
        ).fetchall()
    items = [dict(row) for row in rows]
    return {"knowledge_items": len(items), "items": items, "graph_exists": graph is not None,
            "last_trained_at": graph["last_trained_at"] if graph else None,
            "concept_count": concept_count, "edge_count": edge_count, "chunk_count": chunk_count,
            "pending_additions": pending_additions, "pending_removals": pending_removals,
            "pending_items": pending_items,
            "history": [dict(row) for row in history]}


def refresh_agent_knowledge(agent_id: int, *, build_graph: bool = False) -> dict:
    """Index template files, or coworker files and experience from active projects."""
    with get_connection() as connection:
        agent = connection.execute(
            "SELECT is_template FROM agents WHERE id = ?", (agent_id,),
        ).fetchone()
        if agent is None:
            raise ValueError("Agent not found")
        projects = connection.execute(
            """SELECT p.id, p.name FROM project_agents pa JOIN projects p ON p.id = pa.project_id
            WHERE pa.agent_id = ? AND pa.status != 'removed'
              AND p.status != 'removed' AND p.removed_at IS NULL
              AND ? = 0 ORDER BY p.id""",
            (agent_id, agent["is_template"]),
        ).fetchall()
        details: list[dict] = []
        errors: list[str] = []
        graph_sources: list[dict] = []
        preserve_graph_keys: set[str] = set()
        sources = connection.execute(
            """SELECT id, title, source_type, relative_path FROM agent_sources
            WHERE agent_id = ? AND approval_status = 'approved' ORDER BY id""", (agent_id,),
        ).fetchall()
        indexed_source_ids: set[int] = set()
        for source in sources:
            source_id = str(source["id"])
            def record_file(outcome: str, preview: str = "") -> None:
                details.append({"project_id": None, "project_name": "Agent knowledge",
                                "source_kind": "file", "source_id": source_id,
                                "title": source["title"], "outcome": outcome,
                                "preview": " ".join(preview.split())[:240]})
            if source["source_type"] not in {"file", "markdown"}:
                message = f"{source['title']}: source type {source['source_type']} is not supported yet"
                errors.append(message)
                record_file("error", message)
                continue
            try:
                parsed = parse_knowledge_file(source["relative_path"])
                full_content = parsed.text
                content = full_content[:MAX_NODE_CHARS]
                if not content:
                    connection.execute("DELETE FROM agent_source_index WHERE source_id = ?", (source["id"],))
                    record_file("empty")
                    continue
                indexed_source_ids.add(source["id"])
                checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
                existing = connection.execute("SELECT checksum FROM agent_source_index WHERE source_id = ?", (source["id"],)).fetchone()
                outcome = "unchanged" if existing and existing["checksum"] == checksum else "updated" if existing else "added"
                if outcome != "unchanged":
                    connection.execute(
                        """INSERT INTO agent_source_index (source_id, content, checksum) VALUES (?, ?, ?)
                        ON CONFLICT(source_id) DO UPDATE SET content = excluded.content,
                        checksum = excluded.checksum, updated_at = datetime('now')""",
                        (source["id"], content, checksum),
                    )
                record_file(outcome, content)
                if build_graph:
                    graph_sources.append({"source_key": f"file:{source_id}", "project_id": None,
                                          "project_name": "Agent knowledge", "source_kind": "file",
                                          "source_id": source_id, "title": source["title"],
                                          "content": full_content, "chunks": parsed.chunks})
            except (OSError, ValueError, KeyError) as exc:
                message = f"{source['title']}: {exc}"
                errors.append(message)
                record_file("error", message)
                preserve_graph_keys.add(f"file:{source_id}")
        stale_files = connection.execute(
            """SELECT i.source_id FROM agent_source_index i
            JOIN agent_sources s ON s.id = i.source_id WHERE s.agent_id = ?""", (agent_id,),
        ).fetchall()
        for stale in stale_files:
            if stale["source_id"] not in indexed_source_ids:
                connection.execute("DELETE FROM agent_source_index WHERE source_id = ?", (stale["source_id"],))
                details.append({"project_id": None, "project_name": "Agent knowledge",
                                "source_kind": "file", "source_id": str(stale["source_id"]),
                                "title": "Unavailable source", "outcome": "removed", "preview": ""})
        lessons = connection.execute(
            """SELECT id, title, content FROM agent_lessons
               WHERE agent_id = ? AND approval_status = 'approved' AND ? = 0 ORDER BY id""",
            (agent_id, agent["is_template"]),
        ).fetchall()
        for lesson in lessons:
            details.append({"project_id": None, "project_name": "Portable coworker memory",
                            "source_kind": "lesson", "source_id": str(lesson["id"]),
                            "title": lesson["title"], "outcome": "included",
                            "preview": " ".join(lesson["content"].split())[:240]})
            if build_graph:
                graph_sources.append({"source_key": f"lesson:{lesson['id']}", "project_id": None,
                                      "project_name": "Portable coworker memory", "source_kind": "lesson",
                                      "source_id": str(lesson["id"]), "title": lesson["title"],
                                      "content": lesson["content"],
                                      "chunks": split_knowledge_text(lesson["content"], "Lesson")})
        for project in projects:
            project_id = project["id"]
            current_ids: dict[str, set[str]] = {"task": set(), "chat": set()}
            def record(kind: str, source_id: str, title: str, outcome: str, preview: str = "") -> None:
                details.append({"project_id": project_id, "project_name": project["name"],
                                "source_kind": kind, "source_id": source_id, "title": title,
                                "outcome": outcome, "preview": " ".join(preview.split())[:240]})

            tasks = connection.execute(
                """SELECT t.id, t.title, t.prompt, cr.output_summary FROM tasks t
                LEFT JOIN codex_runs cr ON cr.id = (
                    SELECT id FROM codex_runs WHERE task_id = t.id ORDER BY id DESC LIMIT 1
                )
                WHERE t.project_id = ? AND t.assigned_agent_id = ?
                  AND t.status IN ('completed', 'done')
                ORDER BY t.id""",
                (project_id, agent_id),
            ).fetchall()
            for task in tasks:
                source_id = str(task["id"])
                current_ids["task"].add(source_id)
                content = f"Task: {task['prompt']}\nOutcome: {task['output_summary'] or ''}"
                record("task", source_id, task["title"],
                       _upsert_node(connection, agent_id, project_id, "task", source_id, task["title"], content), content)
                if build_graph:
                    graph_sources.append({"source_key": f"task:{project_id}:{source_id}",
                                          "project_id": project_id, "project_name": project["name"],
                                          "source_kind": "task", "source_id": source_id,
                                          "title": task["title"], "content": content,
                                          "chunks": split_knowledge_text(content, "Task")})

            messages = connection.execute(
                """SELECT m.id, m.content FROM messages m
                JOIN conversation_threads ct ON ct.id = m.thread_id
                LEFT JOIN tasks t ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
                  AND t.project_id = ct.project_id
                WHERE ct.project_id = ? AND (m.sender_agent_id = ? OR t.assigned_agent_id = ?)
                ORDER BY m.id""",
                (project_id, agent_id, agent_id),
            ).fetchall()
            for message in messages:
                source_id = str(message["id"])
                current_ids["chat"].add(source_id)
                title = f"Chat message {message['id']}"
                record("chat", source_id, title,
                       _upsert_node(connection, agent_id, project_id, "chat", source_id, title, message["content"]),
                       message["content"])
                if build_graph and message["content"].strip():
                    graph_sources.append({"source_key": f"chat:{project_id}:{source_id}",
                                          "project_id": project_id, "project_name": project["name"],
                                          "source_kind": "chat", "source_id": source_id,
                                          "title": title, "content": message["content"],
                                          "chunks": split_knowledge_text(message["content"], "Chat")})

            indexed = connection.execute(
                """SELECT id, source_kind, source_id FROM agent_knowledge_nodes
                WHERE agent_id = ? AND project_id = ?""",
                (agent_id, project_id),
            ).fetchall()
            for node in indexed:
                if node["source_kind"] in current_ids and node["source_id"] not in current_ids[node["source_kind"]]:
                    connection.execute("DELETE FROM agent_knowledge_nodes WHERE id = ?", (node["id"],))
                    record(node["source_kind"], node["source_id"], "Removed source", "removed")

        count = connection.execute(
            """SELECT COUNT(*) AS count FROM agent_knowledge_nodes n
            JOIN project_agents pa ON pa.agent_id = n.agent_id AND pa.project_id = n.project_id
            JOIN projects p ON p.id = n.project_id
            WHERE n.agent_id = ? AND n.source_kind != 'file' AND pa.status != 'removed'
              AND p.status != 'removed' AND p.removed_at IS NULL""", (agent_id,)
        ).fetchone()["count"] + connection.execute(
            """SELECT COUNT(*) AS count FROM agent_source_index i JOIN agent_sources s ON s.id = i.source_id
            WHERE s.agent_id = ?""", (agent_id,),
        ).fetchone()["count"]
        graph_counts = None
        if build_graph:
            details, graph_counts = _sync_agent_graph(connection, agent_id, graph_sources, preserve_graph_keys)
            count = graph_counts["sources"]
    outcomes = {key: sum(item["outcome"] == key for item in details)
                for key in ("added", "updated", "unchanged", "removed", "empty", "error")}
    return {"agent_id": agent_id, "project_count": len(projects), "knowledge_items": count,
            "updated_items": outcomes["added"] + outcomes["updated"], "outcomes": outcomes,
            "details": details, "errors": errors, "status": "done" if not errors else "done_with_errors",
            "graph": graph_counts}
