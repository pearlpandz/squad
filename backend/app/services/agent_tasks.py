"""Read coworker task state directly from persisted runs."""

import json
import re

from app.db.session import get_connection
from app.services.runtime_files import task_artifacts


def list_agent_tasks(agent_id: int, project_id: int | None = None) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT t.id, t.project_id, p.name AS project_name, t.title, t.prompt,
                      t.status, t.created_at, t.updated_at, cr.id AS run_id,
                      cr.process_status, cr.started_at, cr.finished_at,
                      cr.output_summary, cr.command_json
               FROM tasks t JOIN projects p ON p.id = t.project_id
               LEFT JOIN codex_runs cr ON cr.id = (SELECT MAX(id) FROM codex_runs WHERE task_id = t.id)
               WHERE (t.assigned_agent_id = ? OR EXISTS (
                 SELECT 1 FROM codex_runs participant WHERE participant.task_id = t.id
                 AND CAST(json_extract(participant.command_json, '$.agent_id') AS INTEGER) = ?
               )) AND (? IS NULL OR t.project_id = ?)
               ORDER BY t.created_at DESC, t.id DESC""",
            (agent_id, agent_id, project_id, project_id),
        ).fetchall()
        task_ids = [row["id"] for row in rows]
        events: dict[int, list[dict]] = {task_id: [] for task_id in task_ids}
        runs: dict[int, list[dict]] = {task_id: [] for task_id in task_ids}
        if task_ids:
            marks = ",".join("?" for _ in task_ids)
            for event in connection.execute(
                f"SELECT task_id, stage, detail, created_at FROM task_events WHERE task_id IN ({marks}) ORDER BY id",
                task_ids,
            ):
                events[event["task_id"]].append({key: event[key] for key in ("stage", "detail", "created_at")})
            for run in connection.execute(
                f"""SELECT id, task_id, process_status, started_at, finished_at, output_summary, created_at
                    FROM codex_runs WHERE task_id IN ({marks}) ORDER BY id DESC""",
                task_ids,
            ):
                runs[run["task_id"]].append({key: run[key] for key in
                                             ("id", "process_status", "started_at", "finished_at", "output_summary", "created_at")})
    result = []
    for row in rows:
        data = dict(row)
        command = json.loads(data.pop("command_json") or "{}") if data["run_id"] else {}
        data["kind"] = command.get("kind", "assignment")
        data["events"] = events[data["id"]]
        data["runs"] = runs[data["id"]]
        data["artifacts"] = task_artifacts(data["project_id"], data["id"])
        result.append(data)
    return result


def task_status_intent(message: str) -> bool:
    text = message.strip().lower()
    if not re.search(r"\b(task|tasks|queue|queued|assignment|assignments|working on|progress|artifact|artifacts)\b", text):
        return False
    return bool(re.search(r"^(what|which|show|list|tell|give|where|how|do you have|are you|can you show)\b", text)
                or re.search(r"\b(status|progress|artifacts?)\s+(?:of|for|on)\s+(?:task|assignment|#)", text)
                or re.search(r"\b(?:current|latest)\s+status\b.*\b(?:task|assignment|queue)", text)
                or re.search(r"\b(your|my)\s+(?:task|assignment|queue)", text))


def task_status_reply(agent_id: int, project_id: int | None = None, question: str = "") -> str:
    tasks = list_agent_tasks(agent_id, project_id)
    scope = "this project" if project_id is not None else "all projects"
    requested_id = re.search(r"(?:#|\btask\s+)(\d+)\b", question, re.IGNORECASE)
    if requested_id:
        task = next((item for item in tasks if item["id"] == int(requested_id.group(1))), None)
        if task is None:
            return f"I cannot find that task in {scope}."
        stages = " → ".join(event["stage"].replace("_", " ") for event in task["events"]) or "No progress recorded"
        result = task["output_summary"] or "The response is pending."
        files = "\n".join(f"- {item['name']}: {item['path']}" for item in task["artifacts"]) or "None yet."
        return (f"Task #{task['id']}: {task['title']} ({task['project_name']})\n"
                f"Status: {task['status'].replace('_', ' ')}. Run: {task['process_status'] or 'not started'}.\n"
                f"Progress: {stages}.\nResult: {result[:1500]}\n"
                f"Generated files:\n{files}")
    if not tasks:
        return f"I have no recorded tasks in {scope}."
    active = [task for task in tasks if task["status"] in ("queued", "in_progress")]
    lines = [f"My tasks in {scope}: {len(active)} active, {len(tasks)} total."]
    for task in (active + [task for task in tasks if task not in active])[:10]:
        stage = task["events"][-1]["detail"] if task["events"] else task["status"].replace("_", " ")
        lines.append(f"- #{task['id']} {task['title']} ({task['project_name']}): {task['status'].replace('_', ' ')}. {stage}")
    if len(tasks) > 10:
        lines.append(f"Showing 10 of {len(tasks)}. Open my Tasks page for the full list.")
    lines.append("Open my Tasks page to see each run, its response, and generated file paths.")
    return "\n".join(lines)
