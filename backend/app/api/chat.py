import json
import re
import traceback
import logging

from fastapi import APIRouter, HTTPException, Request

from app.db.session import get_connection
from app.models.chat import ChatMessage, ChatMessageCreate, ProjectChat, ChatMessageActor, ChatMessageEdit
from app.repositories.chat_repository import create_project_chat_message, create_project_system_message, get_project_chat
from app.services.project_agent import invoke_project_agent
from app.services.agent_tasks import task_status_intent, task_status_reply
from app.services.chat_router import RouteDecision, route_project_message
from app.services.agent_jobs import submit_agent_work, submit_router_work
from app.services.task_trace import task_trace_directory, record_trace
from app.services.task_lifecycle import workflow_task, bind_workflow
from app.services.group_discussion import discussion_participants, previous_discussion
from app.services.chat_message_actions import change_message
from app.services.member_memory import refresh_member_memory

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])


def _record_task_event(task_id: int, stage: str, detail: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO task_events (task_id, stage, detail) VALUES (?, ?, ?)",
            (task_id, stage, detail),
        )
        connection.execute(
            "UPDATE tasks SET updated_at = datetime('now') WHERE id = ? AND status = 'in_progress'",
            (task_id,),
        )


def _recover_stale_runs(project_id: int) -> None:
    """Close orphaned work so project chat never waits indefinitely for a reply."""
    expired: list[tuple[int, int, int]] = []
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT t.id AS task_id, t.assigned_agent_id, cr.id AS run_id
               FROM tasks t JOIN codex_runs cr ON cr.id = (
                 SELECT id FROM codex_runs WHERE task_id = t.id AND process_status = 'running'
                 ORDER BY id LIMIT 1
               )
               WHERE t.project_id = ? AND t.assigned_agent_id IS NOT NULL
                 AND t.status = 'in_progress'
                 AND t.updated_at <= datetime('now', '-3 minutes')""",
            (project_id,),
        ).fetchall()
        for row in rows:
            changed = connection.execute(
                """UPDATE tasks SET status = 'failed', updated_at = datetime('now')
                   WHERE id = ? AND status IN ('queued', 'in_progress')""", (row["task_id"],),
            ).rowcount
            if changed:
                connection.execute(
                    """UPDATE codex_runs SET process_status = 'failed', finished_at = datetime('now'),
                       output_summary = 'The coworker run stalled before a reply was recorded.'
                       WHERE id = ?""", (row["run_id"],),
                )
                connection.execute(
                    """UPDATE codex_runs SET process_status = 'failed', finished_at = datetime('now'),
                       output_summary = 'A prior run stalled; please resend this follow-up.'
                       WHERE task_id = ? AND process_status = 'queued'""",
                    (row["task_id"],),
                )
                connection.execute(
                    "INSERT INTO task_events (task_id, stage, detail) VALUES (?, 'failed', 'Run stalled and was stopped.')",
                    (row["task_id"],),
                )
                expired.append((row["task_id"], row["assigned_agent_id"], row["run_id"]))
    for task_id, agent_id, run_id in expired:
        create_project_chat_message(project_id, ChatMessageCreate(
            content="I couldn't finish this request because the run stalled. Please try again.",
            sender_agent_id=agent_id,
            metadata={"source": "project-agent", "task_id": task_id, "run_id": run_id, "status": "failed"},
        ))


def _run_project_agent(project_id: int, agent_id: int, task_id: int, run_id: int,
                       request: str, history: list[str], assignment: bool,
                       requester_human_id: int | None = None) -> None:
    """Run one task at a time and drain follow-ups queued while it was running."""
    while True:
        with get_connection() as connection:
            changed = connection.execute(
                "UPDATE tasks SET status = 'in_progress', updated_at = datetime('now') WHERE id = ? AND status = 'queued'",
                (task_id,),
            ).rowcount
            if not changed:
                return
            connection.execute("UPDATE tasks SET assigned_agent_id = ? WHERE id = ?", (agent_id, task_id))
            connection.execute(
                "UPDATE codex_runs SET process_status = 'running', started_at = datetime('now') WHERE id = ? AND process_status = 'queued'",
                (run_id,),
            )
        trace_directory = task_trace_directory(project_id, task_id, run_id)
        def report(stage: str, detail: str) -> None:
            _record_task_event(task_id, stage, detail)
            record_trace(trace_directory, stage, detail)

        report("running", "Preparing the coworker request.")
        try:
            with get_connection() as connection:
                run_request = connection.execute('SELECT command_json FROM codex_runs WHERE id = ?', (run_id,)).fetchone()
                run_command = json.loads(run_request['command_json']) if run_request else {}
                context_message_id = run_command.get('message_id')
                continuation = connection.execute(
                    """SELECT 1 FROM codex_runs WHERE task_id = ? AND id != ?
                       AND process_status = 'completed' LIMIT 1""",
                    (task_id, run_id),
                ).fetchone() is not None
            answer = invoke_project_agent(project_id, agent_id, request, history, assignment,
                                          continuation=continuation,
                                          requester_human_id=requester_human_id,
                                          progress=report, trace_directory=trace_directory,
                                          task_id=task_id, context_message_id=context_message_id,
                                          discussion=run_command.get('discussion'), run_id=run_id)
            status = "completed"
        except HTTPException as exc:
            record_trace(trace_directory, "failed", traceback.format_exc())
            answer = f"Unable to complete this request: {exc.detail}"
            status = "failed"
        except Exception:
            record_trace(trace_directory, "failed", traceback.format_exc())
            answer = "Unable to complete this request. Check the backend log and retry."
            status = "failed"
        record_trace(trace_directory, status, answer)
        with get_connection() as connection:
            changed = connection.execute(
                "UPDATE tasks SET status = ?, updated_at = datetime('now') WHERE id = ? AND status = 'in_progress'",
                (status, task_id),
            ).rowcount
            if not changed:
                return
            connection.execute(
                """UPDATE codex_runs SET process_status = ?, finished_at = datetime('now'),
                   output_summary = ? WHERE id = ?""", (status, answer, run_id),
            )
            connection.execute(
                "INSERT INTO task_events (task_id, stage, detail) VALUES (?, ?, ?)",
                (task_id, status, "Response saved in project chat." if status == "completed" else "Run failed; review the response."),
            )
            next_run = connection.execute(
                "SELECT id, command_json FROM codex_runs WHERE task_id = ? AND process_status = 'queued' ORDER BY id LIMIT 1",
                (task_id,),
            ).fetchone()
            if next_run:
                connection.execute("UPDATE tasks SET status = 'queued', updated_at = datetime('now') WHERE id = ?", (task_id,))
        display_answer = answer if len(answer) <= 49000 else answer[:49000] + "\n\n[Response truncated in chat.]"
        create_project_chat_message(project_id, ChatMessageCreate(
            content=display_answer, sender_agent_id=agent_id,
            metadata={"source": "project-agent", "task_id": task_id, "run_id": run_id, "status": status,
                      "assignment": assignment},
        ))
        try:
            refresh_member_memory(agent_id)
        except Exception:
            logging.getLogger(__name__).exception("Unable to refresh coworker project memory after run %s", run_id)
        if not next_run:
            return
        run_id = next_run["id"]
        command = json.loads(next_run["command_json"])
        request = command["request"]
        assignment = bool(command.get("assignment", True))
        requester_human_id = command.get("requester_human_id")
        history = _task_history(project_id, task_id)
        next_agent_id = command.get("agent_id", agent_id)
        if next_agent_id != agent_id:
            submit_agent_work(next_agent_id, _run_project_agent, project_id, next_agent_id,
                              task_id, run_id, request, history, assignment, requester_human_id)
            return


def _task_history(project_id: int, task_id: int) -> list[str]:
    chat = get_project_chat(project_id)
    if chat is None:
        return []
    history = [f"{item.sender_name}: {item.content}" for item in chat.messages
               if item.metadata.get("task_id") == task_id and not item.metadata.get('deleted_at')]
    with get_connection() as connection:
        previous = connection.execute(
            """SELECT output_summary FROM codex_runs
               WHERE task_id = ? AND process_status = 'completed' AND output_summary IS NOT NULL
               ORDER BY id DESC LIMIT 1""", (task_id,),
        ).fetchone()
    if previous and not any(previous["output_summary"][:150] in item for item in history):
        history.append(f"Previous coworker response: {previous['output_summary']}")
    return history


def _route_untagged_message(project_id: int, message_id: int, content: str,
                            metadata: dict, history: list[str],
                            agent_id_hint: int | None = None,
                            explicit_assignment: bool = False,
                            discussion_agents: list[int] | None = None) -> None:
    """Route after saving the human message; the router is built in to every project."""
    with get_connection() as connection:
        saved = connection.execute('SELECT metadata_json FROM messages WHERE id = ?', (message_id,)).fetchone()
    if saved is None or any(json.loads(saved['metadata_json']).get(key) for key in ('edited_at', 'deleted_at')):
        return
    decision = (RouteDecision("new", agent_id_hint, reason="Explicit assignment")
                if explicit_assignment or discussion_agents else
                route_project_message(project_id, content, agent_id=agent_id_hint, message_id=message_id))
    if agent_id_hint is not None and decision.action == "none":
        decision = RouteDecision("new", agent_id_hint, reason="Direct coworker mention")
    if decision.action == "none":
        return
    if decision.action == "clarify":
        create_project_system_message(project_id, decision.reason, {"source": "task-router", "status": "clarify"})
        return
    if metadata.get("attachments"):
        create_project_system_message(
            project_id,
            "Chat attachments are not available to coworkers. Upload the document to the coworker or its agent template, run Self Train, then send your request again.",
            {"source": "task-router", "status": "needs-input"},
        )
        return
    agent_id = decision.agent_id
    if agent_id is None:
        return
    with get_connection() as connection:
        sender = connection.execute("SELECT sender_human_id FROM messages WHERE id = ?", (message_id,)).fetchone()
    requester_human_id = sender["sender_human_id"] if sender else None
    if task_status_intent(content) and not discussion_agents:
        create_project_chat_message(project_id, ChatMessageCreate(
            content=task_status_reply(agent_id, project_id, content), sender_agent_id=agent_id,
            metadata={"source": "task-status"},
        ))
        return
    with get_connection() as connection:
        # Resolve workflow identity in the same write transaction as run creation.
        connection.execute("BEGIN IMMEDIATE")
        saved = connection.execute('SELECT metadata_json FROM messages WHERE id = ?', (message_id,)).fetchone()
        if saved is None or any(json.loads(saved['metadata_json']).get(key) for key in ('edited_at', 'deleted_at')):
            return
        workflow_id, brd_key = workflow_task(connection, project_id, message_id, content, decision.task_id)
        previous_owner = connection.execute(
            """SELECT COALESCE(m.sender_agent_id, t.assigned_agent_id) AS agent_id
               FROM messages m JOIN conversation_threads ct ON ct.id = m.thread_id
               LEFT JOIN tasks t ON t.id = CAST(json_extract(m.metadata_json, '$.task_id') AS INTEGER)
                 AND t.project_id = ct.project_id
               JOIN project_agents pa ON pa.project_id = ct.project_id
                 AND pa.agent_id = COALESCE(m.sender_agent_id, t.assigned_agent_id) AND pa.status = 'active'
               JOIN agents a ON a.id = pa.agent_id AND a.status = 'available'
               WHERE ct.project_id = ? AND m.thread_id = (SELECT thread_id FROM messages WHERE id = ?)
                 AND m.id < ? AND m.sender_type != 'system'
               ORDER BY m.id DESC LIMIT 1""", (project_id, message_id, message_id),
        ).fetchone()
        if workflow_id is not None:
            task = connection.execute(
                "SELECT id, status, assigned_agent_id FROM tasks WHERE id = ? AND project_id = ?",
                (workflow_id, project_id),
            ).fetchone()
            if task is None:
                return
            task_id = task["id"]
            start_now = task["status"] not in ("queued", "in_progress")
            if start_now:
                connection.execute("UPDATE tasks SET status = 'queued', updated_at = datetime('now') WHERE id = ?", (task_id,))
            assignment = True
            kind = "followup"
        else:
            chat = get_project_chat(project_id)
            if chat is None:
                return
            task_id = connection.execute(
                """INSERT INTO tasks (project_id, thread_id, assigned_agent_id, title, prompt, status)
                   VALUES (?, ?, ?, ?, ?, 'queued')""",
                (project_id, chat.thread.id, agent_id, content[:120], content),
            ).lastrowid
            start_now = True
            assignment = explicit_assignment or agent_id_hint is None
            kind = "assignment" if explicit_assignment else "chat" if agent_id_hint else "routed-assignment"
        bind_workflow(connection, message_id, task_id, brd_key)
        run_ids = []
        for index, participant_id in enumerate(discussion_agents or [agent_id]):
            command = {"kind": "discussion" if discussion_agents else kind, "agent_id": participant_id,
                       "message_id": message_id, "request": content, "assignment": assignment,
                       "requester_human_id": requester_human_id}
            if discussion_agents:
                command['discussion'] = {"message_id": message_id, "agent_ids": discussion_agents,
                                         "turn": index + 1, "total": len(discussion_agents)}
            run_ids.append(connection.execute(
                "INSERT INTO codex_runs (task_id, command_json, process_status) VALUES (?, ?, 'queued')",
                (task_id, json.dumps(command)),
            ).lastrowid)
        run_id = run_ids[0]
        connection.execute(
            "INSERT INTO task_events (task_id, stage, detail) VALUES (?, 'routed', ?)",
            (task_id, "Built-in router matched the follow-up to this task." if kind == "followup"
             else "Built-in router assigned this request to the coworker."),
        )
        connection.execute(
            "UPDATE messages SET metadata_json = ? WHERE id = ?",
            (json.dumps({**metadata, "task_id": task_id, "assignment": kind != "followup",
                         "routed": True, "discussion_agent_ids": discussion_agents or [],
                         "run_ids": run_ids}), message_id),
        )
        agent = connection.execute("SELECT name FROM agents WHERE id = ?", (agent_id,)).fetchone()
    name = agent["name"] if agent else "the coworker"
    note = (f"Routed to {name} for task #{task_id}." if start_now
            else f"Added to task #{task_id} for {name}; it will run after the current response.")
    if previous_owner is None or previous_owner["agent_id"] != agent_id:
        create_project_system_message(project_id, note, {"source": "task-router", "task_id": task_id,
                                                       "agent_id": agent_id})
    record_trace(task_trace_directory(project_id, task_id, run_id), "routed", note)
    record_trace(task_trace_directory(project_id, task_id, run_id), "input", json.dumps({
        "request": content, "message_id": message_id, "requester_human_id": requester_human_id,
        "agent_id": agent_id, "route_reason": decision.reason, "kind": kind,
        "attachments": metadata.get("attachments", []),
    }, ensure_ascii=False))
    if discussion_agents:
        for participant_id, participant_run in zip(discussion_agents, run_ids):
            directory = task_trace_directory(project_id, task_id, participant_run)
            record_trace(directory, 'discussion_queued', json.dumps({
                'message_id': message_id, 'agent_id': participant_id,
                'participants': discussion_agents, 'request': content,
            }, ensure_ascii=False))
    if start_now:
        run_history = (_task_history(project_id, task_id) if kind == "followup" else history)
        submit_agent_work(agent_id, _run_project_agent, project_id, agent_id, task_id,
                          run_id, content, run_history, assignment, requester_human_id)


@router.get("", response_model=ProjectChat)
def project_chat(project_id: int) -> ProjectChat:
    _recover_stale_runs(project_id)
    chat = get_project_chat(project_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return chat


@router.patch('/messages/{message_id}', response_model=ChatMessage)
def edit_message(project_id: int, message_id: int, payload: ChatMessageEdit, request: Request) -> ChatMessage:
    payload.sender_human_id = request.state.user["human_id"]
    return change_message(project_id, message_id, payload.sender_human_id, payload.content)


@router.delete('/messages/{message_id}')
def delete_message(project_id: int, message_id: int, payload: ChatMessageActor, request: Request) -> dict:
    payload.sender_human_id = request.state.user["human_id"]
    change_message(project_id, message_id, payload.sender_human_id, None)
    return {'deleted_message_id': message_id}


@router.post("/messages", response_model=ChatMessage, status_code=201)
def create_message(project_id: int, payload: ChatMessageCreate, request: Request) -> ChatMessage:
    payload.sender_human_id = request.state.user["human_id"]
    if payload.sender_agent_id is not None:
        raise HTTPException(status_code=400, detail="Agent replies are created by the system")
    if payload.sender_human_id is None:
        raise HTTPException(status_code=400, detail="Select a human project member")
    if len(payload.content) > 8000:
        raise HTTPException(status_code=400, detail="Project messages are limited to 8,000 characters")
    with get_connection() as connection:
        member = connection.execute(
            """SELECT 1 FROM project_members WHERE project_id = ? AND human_id = ?
               AND status != 'removed'""", (project_id, payload.sender_human_id),
        ).fetchone()
        if member is None:
            raise HTTPException(status_code=403, detail="Sender is not a member of this project")
        handles = connection.execute(
            """SELECT a.id, a.handle FROM project_agents pa JOIN agents a ON a.id = pa.agent_id
               WHERE pa.project_id = ? AND pa.status = 'active' AND a.status = 'available'""",
            (project_id,),
        ).fetchall()
    # The first coworker mention is the addressee; later mentions are references
    # (for example, asking Sylvie to review a story prepared by Leo).
    matches = []
    for row in handles:
        match = re.search(rf"(?<![\w@]){re.escape(row['handle'])}(?![\w])", payload.content, re.IGNORECASE)
        if match:
            matches.append((match.start(), row))
    mentioned = [row for _, row in sorted(matches, key=lambda item: item[0])]
    chat = get_project_chat(project_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Project not found")
    participants = discussion_participants(
        payload.content, mentioned, handles, previous_discussion(project_id, chat.thread.id))
    if len(participants) > 1:
        payload.metadata = {**payload.metadata, 'discussion_agent_ids': participants}
        message = create_project_chat_message(project_id, payload)
        if message is None:
            raise HTTPException(status_code=404, detail="Project not found")
        request = re.sub(r'^\s*/discuss\b', '', payload.content, flags=re.I).strip()
        history = [f"{item.sender_name}: {item.content}" for item in chat.messages]
        submit_router_work(_route_untagged_message, project_id, message.id, request,
                           payload.metadata, history, participants[0], False, participants)
        return message
    # Client metadata cannot turn a direct request into a persistent team invitation.
    payload.metadata = {**payload.metadata, 'discussion_agent_ids': []}
    assignment = payload.content.strip().lower().startswith("/assign")
    if assignment and not mentioned:
        raise HTTPException(status_code=400, detail="Use /assign with an active coworker @mention as the recipient")
    if not mentioned:
        message = create_project_chat_message(project_id, payload)
        if message is None:
            raise HTTPException(status_code=404, detail="Project not found")
        chat = get_project_chat(project_id)
        history = [f"{item.sender_name}: {item.content}" for item in
                   ([item for item in chat.messages if item.id < message.id] if chat else [])]
        submit_router_work(_route_untagged_message, project_id, message.id,
                           payload.content.strip(), payload.metadata, history)
        return message

    agent_id = mentioned[0]["id"]
    request = re.sub(rf"(?<![\w@]){re.escape(mentioned[0]['handle'])}(?![\w])",
                     "", payload.content, count=1, flags=re.IGNORECASE).strip()
    if assignment:
        request = re.sub(r"^/assign\b", "", request, flags=re.IGNORECASE).strip()
    if not request:
        raise HTTPException(status_code=400, detail="Enter a request after the coworker mention")
    if not assignment and task_status_intent(request):
        message = create_project_chat_message(project_id, payload)
        if message is None:
            raise HTTPException(status_code=404, detail="Project not found")
        create_project_chat_message(project_id, ChatMessageCreate(
            content=task_status_reply(agent_id, project_id, request), sender_agent_id=agent_id,
            metadata={"source": "task-status"},
        ))
        return message
    chat = get_project_chat(project_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Project not found")
    history = [f"{item.sender_name}: {item.content}" for item in chat.messages]
    message = create_project_chat_message(project_id, payload)
    if message is None:
        raise HTTPException(status_code=404, detail="Project not found")
    submit_router_work(_route_untagged_message, project_id, message.id, request,
                       payload.metadata, history, agent_id, assignment)
    return message
