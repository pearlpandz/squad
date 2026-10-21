"""Published coworker templates and independent, pinned coworker copies."""

import json
import sqlite3
import shutil
import time
from pathlib import Path

from app.core.runtime import runtime_project_root
from app.db.session import get_connection, project_root


def bootstrap_business_analyst_template() -> None:
    """Run the one-time backfill; tolerate a simultaneous backend reload."""
    try:
        _bootstrap_business_analyst_template()
    except (sqlite3.OperationalError, sqlite3.IntegrityError):
        for _ in range(15):
            time.sleep(1)
            try:
                with get_connection() as connection:
                    finished = connection.execute(
                        """SELECT 1 FROM app_settings
                           WHERE key = 'ba_template_source_backfill_done'""",
                    ).fetchone()
                if finished:
                    return
            except sqlite3.OperationalError:
                continue
        raise


def _bootstrap_business_analyst_template() -> None:
    """Move Silvy's trained source set to a shared BA template, not her experience."""
    with get_connection() as connection:
        template = connection.execute(
            """SELECT a.* FROM agents a JOIN agent_roles r ON r.id = a.role_id
               WHERE a.is_template = 1 AND a.username = 'business-analyst-template'
                 AND r.code = 'business-analyst'
                 AND a.status != 'deleted' ORDER BY a.id LIMIT 1""",
        ).fetchone()
        if template is None:
            return
        if connection.execute(
            "SELECT 1 FROM app_settings WHERE key = 'ba_template_source_backfill_done'",
        ).fetchone():
            return
        silvy = connection.execute(
            """SELECT id FROM agents WHERE lower(username) = 'silvy' AND role_id = ?
               AND is_template = 0 AND status != 'deleted' LIMIT 1""",
            (template["role_id"],),
        ).fetchone()
        if silvy is None:
            connection.execute(
                """INSERT INTO app_settings (key, value, description)
                   VALUES ('ba_template_source_backfill_done', 'no-silvy',
                           'No existing BA coworker sources to migrate')""",
            )
            return
        sources = connection.execute(
            """SELECT s.* FROM agent_sources s
               JOIN agent_graph_sources g ON g.agent_id = s.agent_id
                 AND g.source_key = 'file:' || s.id
               WHERE s.agent_id = ? AND s.approval_status = 'approved'
               ORDER BY s.id""",
            (silvy["id"],),
        ).fetchall() if silvy is not None else []
        copied_titles = {row["title"] for row in connection.execute(
            "SELECT title FROM agent_sources WHERE agent_id = ?", (template["id"],),
        )}
        missing_sources = [source for source in sources
                           if source["template_source_id"] is None
                           and source["title"] not in copied_titles]
    if missing_sources:
        targets = []
        for source in missing_sources:
            original = (project_root() / source["relative_path"]).resolve()
            if not original.is_relative_to(project_root().resolve()) or not original.is_file():
                return
            target = (runtime_project_root(template["project_id"]) / "knowledge"
                      / "business-analyst-template" / f"{source['id']}-{Path(source['relative_path']).name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                if Path(source["relative_path"]).suffix.lower() == ".md":
                    content = original.read_text(encoding="utf-8")
                    target.write_text(content.replace("@silvy", "@assigned-coworker")
                                      .replace("Silvy", "Business Analyst coworker"), encoding="utf-8")
                else:
                    shutil.copyfile(original, target)
            targets.append((source, target.relative_to(project_root()).as_posix()))
        with get_connection() as connection:
            _copy_template_sources(connection, silvy["id"], template["id"],
                                   [source["id"] for source, _ in targets])
            for source, relative_path in targets:
                connection.execute(
                    """UPDATE agent_sources SET template_source_id = NULL, relative_path = ?
                       WHERE agent_id = ? AND template_source_id = ?""",
                    (relative_path, template["id"], source["id"]),
                )
    with get_connection() as connection:
        ready = connection.execute(
            "SELECT 1 FROM agent_sources WHERE agent_id = ? AND approval_status = 'approved' LIMIT 1",
            (template["id"],),
        ).fetchone() is not None
    if not ready:
        return
    if missing_sources or not template["published_version"]:
        from app.services.agent_training import refresh_agent_knowledge
        result = refresh_agent_knowledge(template["id"], build_graph=True)
        if result["errors"]:
            return
    version = publish_template(template["id"])
    with get_connection() as connection:
        if silvy is not None:
            for inherited in connection.execute(
                "SELECT id, template_source_id FROM agent_sources WHERE agent_id = ?",
                (template["id"],),
            ).fetchall():
                if inherited["template_source_id"] is not None:
                    continue
                original = connection.execute(
                    """SELECT id FROM agent_sources WHERE agent_id = ? AND title = (
                         SELECT title FROM agent_sources WHERE id = ?)
                       AND template_source_id IS NULL LIMIT 1""",
                    (silvy["id"], inherited["id"]),
                ).fetchone()
                if original is not None:
                    connection.execute(
                        "UPDATE agent_sources SET template_source_id = ? WHERE id = ?",
                        (inherited["id"], original["id"]),
                    )
        connection.execute(
            """UPDATE agents SET template_agent_id = ?, template_version = ?,
               template_instructions = ?, template_description = ?, template_scope = ?,
               updated_at = datetime('now')
               WHERE lower(username) = 'silvy' AND role_id = ? AND is_template = 0
                 AND (template_agent_id IS NULL OR template_agent_id = ?)""",
            (template["id"], version, template["template_instructions"],
             template["agent_description"], template["knowledge_scope"], template["role_id"],
             template["id"]),
        )
        connection.execute(
            """INSERT OR REPLACE INTO app_settings (key, value, description)
               VALUES ('ba_template_source_backfill_done', 'complete',
                       'Existing BA source files copied to the reusable template')""",
        )


def publish_template(template_id: int) -> int:
    """Snapshot the trained template after Start Self Train completes."""
    with get_connection() as connection:
        template = connection.execute(
            "SELECT * FROM agents WHERE id = ? AND is_template = 1 AND status != 'deleted'",
            (template_id,),
        ).fetchone()
        if template is None:
            raise ValueError("Template not found")
        sources = connection.execute(
            "SELECT id FROM agent_sources WHERE agent_id = ? AND approval_status = 'approved' ORDER BY id",
            (template_id,),
        ).fetchall()
        if not sources:
            raise ValueError("Add and train at least one template knowledge resource before publishing")
        missing = [row["id"] for row in sources if connection.execute(
            "SELECT 1 FROM agent_graph_sources WHERE agent_id = ? AND source_key = ?",
            (template_id, f"file:{row['id']}"),
        ).fetchone() is None]
        if missing:
            raise ValueError("Template resources must be trained before publishing")
        source_ids_json = json.dumps([row["id"] for row in sources])
        latest = connection.execute(
            """SELECT * FROM agent_template_versions
               WHERE template_agent_id = ? ORDER BY version DESC LIMIT 1""",
            (template_id,),
        ).fetchone()
        if latest and all((latest[key] == value for key, value in (
            ("role_id", template["role_id"]),
            ("description", template["agent_description"]),
            ("knowledge_scope", template["knowledge_scope"]),
            ("instructions", template["template_instructions"]),
            ("tool_permissions_json", template["tool_permissions_json"]),
            ("source_ids_json", source_ids_json),
        ))):
            return latest["version"]
        next_version = template["published_version"] + 1
        connection.execute(
            """INSERT INTO agent_template_versions
               (template_agent_id, version, role_id, description, knowledge_scope,
                instructions, tool_permissions_json, source_ids_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (template_id, next_version, template["role_id"], template["agent_description"],
             template["knowledge_scope"], template["template_instructions"],
             template["tool_permissions_json"], source_ids_json),
        )
        connection.execute(
            "UPDATE agents SET published_version = ?, updated_at = datetime('now') WHERE id = ?",
            (next_version, template_id),
        )
    return next_version


def _copy_template_sources(connection, template_id: int, agent_id: int,
                           source_ids: list[int]) -> None:
    """Copy source references and trained vectors; later coworker training remains independent."""
    connection.execute("INSERT OR IGNORE INTO agent_graphs (agent_id) VALUES (?)", (agent_id,))
    connection.execute(
        "UPDATE agent_graphs SET last_trained_at = datetime('now') WHERE agent_id = ?", (agent_id,),
    )
    for source_id in source_ids:
        source = connection.execute(
            "SELECT * FROM agent_sources WHERE id = ? AND agent_id = ?",
            (source_id, template_id),
        ).fetchone()
        if source is None:
            raise ValueError("A published template resource is unavailable")
        old_key = f"file:{source_id}"
        graph = connection.execute(
            "SELECT * FROM agent_graph_sources WHERE agent_id = ? AND source_key = ?",
            (template_id, old_key),
        ).fetchone()
        if graph is None:
            raise ValueError("Published template knowledge is not trained")
        new_source_id = connection.execute(
            """INSERT INTO agent_sources
               (agent_id, template_source_id, title, source_type, relative_path, approval_status)
               VALUES (?, ?, ?, ?, ?, 'approved')""",
            (agent_id, source_id, source["title"], source["source_type"], source["relative_path"]),
        ).lastrowid
        new_key = f"file:{new_source_id}"
        connection.execute(
            """INSERT INTO agent_graph_sources
               (agent_id, source_key, project_id, project_name, source_kind, source_id,
                title, content, checksum, updated_at)
               VALUES (?, ?, NULL, 'Agent knowledge', 'file', ?, ?, ?, ?, datetime('now'))""",
            (agent_id, new_key, str(new_source_id), graph["title"], graph["content"], graph["checksum"]),
        )
        connection.execute(
            """INSERT INTO agent_graph_chunks
               (agent_id, source_key, chunk_index, locator, content, checksum, embedding, embedding_model)
               SELECT ?, ?, chunk_index, locator, content, checksum, embedding, embedding_model
               FROM agent_graph_chunks WHERE agent_id = ? AND source_key = ?""",
            (agent_id, new_key, template_id, old_key),
        )
        connection.execute(
            """INSERT OR IGNORE INTO agent_graph_concepts (agent_id, term)
               SELECT ?, term FROM agent_graph_edges WHERE agent_id = ? AND source_key = ?""",
            (agent_id, template_id, old_key),
        )
        connection.execute(
            """INSERT INTO agent_graph_edges (agent_id, source_key, term, weight)
               SELECT ?, ?, term, weight FROM agent_graph_edges
               WHERE agent_id = ? AND source_key = ?""",
            (agent_id, new_key, template_id, old_key),
        )
        connection.execute(
            """INSERT INTO agent_graph_history
               (agent_id, source_key, project_id, project_name, source_kind, source_id,
                title, checksum, outcome)
               VALUES (?, ?, NULL, 'Agent knowledge', 'file', ?, ?, ?, 'added')""",
            (agent_id, new_key, str(new_source_id), graph["title"], graph["checksum"]),
        )
        connection.execute(
            """INSERT INTO agent_source_index (source_id, content, checksum)
               SELECT ?, content, checksum FROM agent_source_index WHERE source_id = ?""",
            (new_source_id, source_id),
        )


def clone_template(template_id: int, name: str, username: str,
                   project_id: int | None = None) -> int:
    with get_connection() as connection:
        template = connection.execute(
            "SELECT * FROM agents WHERE id = ? AND is_template = 1 AND published_version > 0",
            (template_id,),
        ).fetchone()
        if template is None:
            raise ValueError("Publish the template with Start Self Train before creating a coworker")
        version = connection.execute(
            """SELECT * FROM agent_template_versions
               WHERE template_agent_id = ? AND version = ?""",
            (template_id, template["published_version"]),
        ).fetchone()
        pool = connection.execute(
            "SELECT id FROM projects WHERE code = '_agent-pool'",
        ).fetchone()
        if pool is None:
            raise ValueError("Agent pool migration is not applied")
        project = None
        if project_id is not None:
            project = connection.execute(
                """SELECT id FROM projects WHERE id = ? AND code != '_agent-pool' AND status != 'removed'
                   AND removed_at IS NULL AND client_id = 1""",
                (project_id,),
            ).fetchone()
            if project is None:
                raise ValueError("Project not found")
        clean_username = username.strip().lstrip("@").lower()
        if connection.execute(
            "SELECT 1 FROM agents WHERE lower(username) = ?",
            (clean_username,),
        ).fetchone():
            raise ValueError("Username already exists")
        agent_id = connection.execute(
            """INSERT INTO agents
               (client_id, project_id, role_id, name, username, handle, status,
                agent_description, knowledge_scope, tool_permissions_json,
                review_boundaries_json, template_agent_id, template_version,
                template_instructions, template_description, template_scope)
               VALUES (?, ?, ?, ?, ?, ?, 'available', ?, ?, ?, '[]', ?, ?, ?, ?, ?)""",
            (1, pool["id"], version["role_id"], name.strip(), clean_username,
             f"@{clean_username}", version["description"], version["knowledge_scope"],
             version["tool_permissions_json"], template_id, version["version"],
             version["instructions"], version["description"], version["knowledge_scope"]),
        ).lastrowid
        _copy_template_sources(connection, template_id, agent_id,
                               json.loads(version["source_ids_json"]))
        if project is not None:
            connection.execute("""INSERT OR IGNORE INTO team_agents (team_id, agent_id)
                SELECT team_id, ? FROM projects WHERE id = ?""", (agent_id, project_id))
            role = connection.execute(
                "SELECT name FROM agent_roles WHERE id = ?", (version["role_id"],),
            ).fetchone()
            connection.execute(
                """INSERT INTO project_agents (project_id, agent_id, member_role, status)
                   VALUES (?, ?, ?, 'active')""",
                (project_id, agent_id, role["name"]),
            )
    return agent_id


def upgrade_clone(agent_id: int) -> int:
    """Replace only inherited defaults; preserve personal sources, tasks, and memory."""
    with get_connection() as connection:
        agent = connection.execute(
            "SELECT * FROM agents WHERE id = ? AND template_agent_id IS NOT NULL", (agent_id,),
        ).fetchone()
        if agent is None:
            raise ValueError("Coworker is not a template copy")
        template = connection.execute(
            "SELECT * FROM agents WHERE id = ? AND is_template = 1",
            (agent["template_agent_id"],),
        ).fetchone()
        if template is None or template["published_version"] <= agent["template_version"]:
            raise ValueError("No newer published template version is available")
        version = connection.execute(
            """SELECT * FROM agent_template_versions
               WHERE template_agent_id = ? AND version = ?""",
            (template["id"], template["published_version"]),
        ).fetchone()
        previous = connection.execute(
            """SELECT * FROM agent_template_versions
               WHERE template_agent_id = ? AND version = ?""",
            (template["id"], agent["template_version"]),
        ).fetchone()
        inherited = connection.execute(
            "SELECT id FROM agent_sources WHERE agent_id = ? AND template_source_id IS NOT NULL",
            (agent_id,),
        ).fetchall()
        for source in inherited:
            connection.execute(
                "DELETE FROM agent_graph_sources WHERE agent_id = ? AND source_key = ?",
                (agent_id, f"file:{source['id']}"),
            )
            connection.execute("DELETE FROM agent_sources WHERE id = ?", (source["id"],))
        _copy_template_sources(connection, template["id"], agent_id,
                               json.loads(version["source_ids_json"]))
        role_id = version["role_id"] if previous and agent["role_id"] == previous["role_id"] else agent["role_id"]
        description = (version["description"] if agent["agent_description"] == agent["template_description"]
                       else agent["agent_description"])
        scope = (version["knowledge_scope"] if agent["knowledge_scope"] == agent["template_scope"]
                 else agent["knowledge_scope"])
        permissions = (version["tool_permissions_json"] if previous and
                       agent["tool_permissions_json"] == previous["tool_permissions_json"]
                       else agent["tool_permissions_json"])
        connection.execute(
            """UPDATE agents SET role_id = ?, agent_description = ?, knowledge_scope = ?,
               tool_permissions_json = ?, template_version = ?, template_instructions = ?,
               template_description = ?, template_scope = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (role_id, description, scope, permissions, version["version"], version["instructions"],
             version["description"], version["knowledge_scope"], agent_id),
        )
        if previous and role_id != agent["role_id"]:
            role = connection.execute("SELECT name FROM agent_roles WHERE id = ?", (role_id,)).fetchone()
            connection.execute(
                "UPDATE project_agents SET member_role = ? WHERE agent_id = ?",
                (role["name"], agent_id),
            )
        connection.execute(
            """DELETE FROM agent_graph_concepts WHERE agent_id = ? AND NOT EXISTS (
                 SELECT 1 FROM agent_graph_edges e WHERE e.agent_id = agent_graph_concepts.agent_id
                   AND e.term = agent_graph_concepts.term
               )""",
            (agent_id,),
        )
    return version["version"]
