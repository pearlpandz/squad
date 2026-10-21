"""Built-in project chat router; it has no project membership or knowledge graph."""

import re
import json
from dataclasses import dataclass

from app.db.session import get_connection
from app.services.semantic_search import _model
from app.services.runtime_files import task_artifacts


@dataclass(frozen=True)
class RouteDecision:
    action: str = "none"
    agent_id: int | None = None
    task_id: int | None = None
    reason: str = ""


def route_project_message(project_id: int, message: str, agent_id: int | None = None,
                          message_id: int | None = None) -> RouteDecision:
    """Select an existing task, a coworker for new work, or ask for clarification."""
    with get_connection() as connection:
        thread = connection.execute(
            """SELECT id FROM conversation_threads WHERE project_id = ? AND status = 'active'
               AND (? IS NULL OR id = (SELECT thread_id FROM messages WHERE id = ?))
               ORDER BY updated_at DESC, id DESC LIMIT 1""", (project_id, message_id, message_id),
        ).fetchone()
        if thread is None:
            return RouteDecision("clarify", reason="I could not find the current project discussion.")
        conversation = connection.execute(
            """SELECT m.id, m.sender_type, m.content, m.metadata_json,
                      COALESCE(a.name, h.display_name, 'Task Router') AS sender
               FROM messages m LEFT JOIN agents a ON a.id = m.sender_agent_id
               LEFT JOIN humans h ON h.id = m.sender_human_id
               WHERE m.thread_id = ? AND (? IS NULL OR m.id < ?)
                 AND json_extract(m.metadata_json, '$.deleted_at') IS NULL
               ORDER BY m.id DESC LIMIT 20""", (thread["id"], message_id, message_id),
        ).fetchall()
        agents = connection.execute(
            """SELECT a.id, a.name, a.handle, a.agent_description, a.knowledge_scope, a.template_scope, r.name AS role
               FROM project_agents pa JOIN agents a ON a.id = pa.agent_id
               JOIN agent_roles r ON r.id = a.role_id
               WHERE pa.project_id = ? AND pa.status = 'active' AND a.status = 'available'
               AND (? IS NULL OR a.id = ?)
               ORDER BY a.id""", (project_id, agent_id, agent_id),
        ).fetchall()
        tasks = connection.execute(
            """SELECT t.id, t.assigned_agent_id, t.title, t.prompt, t.status, t.updated_at,
                      cr.output_summary AS last_answer
               FROM tasks t JOIN project_agents pa ON pa.agent_id = t.assigned_agent_id
                 AND pa.project_id = t.project_id AND pa.status = 'active'
               JOIN agents a ON a.id = pa.agent_id AND a.status = 'available'
               LEFT JOIN codex_runs cr ON cr.id = (SELECT MAX(id) FROM codex_runs WHERE task_id = t.id)
               WHERE t.project_id = ? AND t.thread_id = ? AND (? IS NULL OR t.assigned_agent_id = ?)
                 AND (? IS NULL OR t.created_at <= (SELECT created_at FROM messages WHERE id = ?))
                 AND (t.status IN ('queued', 'in_progress', 'awaiting_input')
                 OR t.updated_at >= datetime('now', '-30 days'))
               ORDER BY CASE WHEN t.status IN ('queued', 'in_progress', 'awaiting_input') THEN 0 ELSE 1 END,
                        t.updated_at DESC, t.id DESC LIMIT 12""", (project_id, thread["id"], agent_id, agent_id, message_id, message_id),
        ).fetchall()
    if not agents:
        return RouteDecision("clarify", reason="There are no available coworkers in this project to handle the request.")
    direct = re.search(r"(?:#|\btask\s+)(\d+)\b", message, re.IGNORECASE)
    if direct:
        with get_connection() as connection:
            task = connection.execute(
                """SELECT t.id, t.assigned_agent_id FROM tasks t
                   JOIN project_agents pa ON pa.project_id = t.project_id AND pa.agent_id = t.assigned_agent_id
                   JOIN agents a ON a.id = pa.agent_id
                   WHERE t.id = ? AND t.project_id = ? AND pa.status = 'active' AND a.status = 'available'
                     AND (? IS NULL OR t.assigned_agent_id = ?)""",
                (int(direct.group(1)), project_id, agent_id, agent_id),
            ).fetchone()
        if task:
            return RouteDecision("followup", task["assigned_agent_id"], task["id"], "Explicit task reference")
        return RouteDecision("clarify", reason="I could not find that task among this project's recent coworker tasks.")
    task_by_id = {row["id"]: row for row in tasks}
    anchor = None
    latest_agent_text = ""
    for row in conversation:
        if row["sender_type"] == "agent" and not latest_agent_text:
            latest_agent_text = row["content"]
        task_id = json.loads(row["metadata_json"] or "{}").get("task_id")
        if anchor is None and task_id in task_by_id:
            anchor = task_by_id[task_id]
    if anchor is None and agent_id is not None and tasks:
        anchor = max(tasks, key=lambda row: (row["updated_at"], row["id"]))
    text = message.strip()
    new_topic = bool(re.search(r"\b(?:new|separate|another|different|unrelated)\s+(?:task|work|topic|request|document|brd|fdd|project)\b", text, re.I))
    followup = bool(re.search(
        r"\b(?:retry|again|continue|resume|revise|refine|correct|align|generated|existing|previous|above|already|shared)\b"
        r"|\b(?:update|check|review|verify|fix|use|start)\b.{0,60}\b(?:it|this|that|the|those|these)\b"
        r"|\b(?:it|this|that|those|these)\b.{0,60}\b(?:template|document|fdd|brd|result|output|allowed|retry)\b"
        r"|\b(?:I asked you|inputs? (?:are|is)|documents? (?:are|is))\b", text, re.I))
    waiting_for_input = bool(re.search(r"\?|\b(?:please (?:provide|share|confirm)|need (?:your|the)|missing inputs?)\b", latest_agent_text, re.I))
    social = bool(re.fullmatch(r"(?:hi|hello|hey|thanks|thank you|ok|okay|noted|yes|no)[.! ]*", text, re.I))
    if social and not (anchor is not None and waiting_for_input and re.fullmatch(r"(?:ok|okay|yes|no)[.! ]*", text, re.I)):
        return RouteDecision()
    actionable = bool(re.search(
        r"\b(?:please|can you|could you|would you|prepare|create|generate|write|review|check|verify|align|update|fix|retry|continue|start|use|find|explain|summarize|help|need|want)\b", text, re.I))
    supplied_input = waiting_for_input and bool(text) and not social
    if anchor is not None and not new_topic and (followup or supplied_input or (social and waiting_for_input)):
        if len(agents) > 1 and actionable:
            # A concrete change of subject can require another role even when
            # the message begins with a continuation verb such as "review".
            try:
                model = _model()
                query = model.encode_query(text, normalize_embeddings=True, convert_to_numpy=True)
                roles = [f"{row['role']}. {row['agent_description']}. {row['template_scope'] or row['knowledge_scope']}" for row in agents]
                vectors = model.encode_document(roles + [f"{anchor['title']}. {anchor['prompt'][:800]}"],
                                                normalize_embeddings=True, convert_to_numpy=True)
                scores = vectors @ query
                ranked = sorted(((float(scores[index]), row) for index, row in enumerate(agents)),
                                key=lambda item: item[0], reverse=True)
                top, coworker = ranked[0]
                if (coworker["id"] != anchor["assigned_agent_id"] and top >= 0.35
                        and top - ranked[1][0] >= 0.12 and top - float(scores[-1]) >= 0.08):
                    return RouteDecision("new", coworker["id"], reason="The new subject matches another coworker's responsibility")
            except (RuntimeError, OSError, ValueError):
                pass
        if followup and not task_artifacts(project_id, anchor["id"]):
            # Older routers created empty tasks for revisions. Resolve the actual
            # deliverable only within the same discussion and coworker's tasks.
            document_terms = set(re.findall(r"\b(?:fdd|brd|tdd|document|report|template)\b", text.lower()))
            if document_terms:
                candidates = []
                for candidate in tasks:
                    if candidate["assigned_agent_id"] != anchor["assigned_agent_id"]:
                        continue
                    files = task_artifacts(project_id, candidate["id"])
                    specific = document_terms - {"document", "template", "report"}
                    if files and (not specific or any(term in item["name"].lower() for item in files for term in specific)):
                        candidates.append(candidate)
                if len(candidates) == 1:
                    anchor = candidates[0]
                elif len(candidates) > 1:
                    choices = ", ".join(f"#{row['id']}" for row in candidates)
                    return RouteDecision("clarify", reason=f"Several tasks have existing deliverables: {choices}. Which should I revise?")
        return RouteDecision("followup", anchor["assigned_agent_id"], anchor["id"],
                             "Continuation of the task in the current discussion")
    # There is no coworker selection ambiguity when exactly one is available.
    # Keep social-only messages silent and preserve task/deliverable checks above.
    if len(agents) == 1:
        if anchor is not None and not new_topic:
            return RouteDecision("followup", agents[0]["id"], anchor["id"],
                                 "Default to the only available coworker in the current discussion")
        return RouteDecision("new", agents[0]["id"],
                             reason="Default to the only available coworker")
    task_texts = [f"{row['title']}. {row['prompt'][:800]}. {(row['last_answer'] or '')[:800]}" for row in tasks]
    agent_texts = [f"{row['name']}. {row['role']}. {row['agent_description']}. {row['template_scope'] or row['knowledge_scope']}" for row in agents]
    intents = ["Please prepare, create, review or complete this work item.",
               "I am providing the requested information or correcting the previous result.",
               "Hello team. Thanks for the update. This is general discussion with no action requested."]
    try:
        model = _model()
        query = model.encode_query(text, normalize_embeddings=True, convert_to_numpy=True)
        vectors = model.encode_document(task_texts + agent_texts + intents, normalize_embeddings=True, convert_to_numpy=True)
        scores = vectors @ query
    except (RuntimeError, OSError, ValueError):
        return RouteDecision("clarify", reason="I cannot confidently route this request locally. Which task or coworker should handle it?")
    task_scores = sorted(((float(scores[index]), row) for index, row in enumerate(tasks)), key=lambda item: item[0], reverse=True)
    offset = len(tasks)
    agent_scores = sorted(((float(scores[offset + index]), row) for index, row in enumerate(agents)), key=lambda item: item[0], reverse=True)
    work_score = max(float(scores[-3]), float(scores[-2]))
    discussion_score = float(scores[-1])
    if not actionable and not new_topic and discussion_score > work_score + 0.08:
        return RouteDecision()
    if not new_topic and task_scores and task_scores[0][0] >= 0.35:
        top, task = task_scores[0]
        next_score = task_scores[1][0] if len(task_scores) > 1 else 0.0
        if top - next_score >= 0.05:
            return RouteDecision("followup", task["assigned_agent_id"], task["id"], "Local intent matched an existing project task")
        close = [row for score, row in task_scores if top - score < 0.05]
        if anchor is not None and anchor["id"] in {row["id"] for row in close}:
            return RouteDecision("followup", anchor["assigned_agent_id"], anchor["id"], "Discussion context resolved similar task matches")
        return RouteDecision("clarify", reason="This could relate to several existing tasks. Which result should I update?")
    top, agent = agent_scores[0]
    second = agent_scores[1][0] if len(agent_scores) > 1 else 0.0
    if top >= 0.25 and top - second >= 0.05 and (actionable or work_score >= discussion_score):
        return RouteDecision("new", agent["id"], reason="Local intent matched this coworker's role and responsibility")
    if actionable or new_topic or work_score >= discussion_score:
        names = ", ".join(row["name"] for row in agents)
        return RouteDecision("clarify", reason=f"Which coworker should handle this request? Available: {names}.")
    return RouteDecision()
