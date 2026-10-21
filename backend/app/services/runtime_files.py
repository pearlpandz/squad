"""Persistent project deliverables under the repository runtime directory."""

from pathlib import Path

from app.core.runtime import runtime_project_root
from app.db.session import get_connection


def task_workspace(project_id: int, task_id: int) -> Path:
    if project_id < 1 or task_id < 1:
        raise ValueError("Project and task IDs must be positive")
    root = runtime_project_root(project_id).resolve()
    path = root / "tasks" / f"task-{task_id}"
    if not path.resolve().is_relative_to(root):
        raise ValueError("Task workspace must stay inside runtime projects")
    return path


def task_artifacts(project_id: int, task_id: int) -> list[dict[str, str]]:
    workspace = task_workspace(project_id, task_id)
    if not workspace.is_dir():
        return []
    root = workspace.resolve()
    return [
        {"name": path.relative_to(workspace).as_posix(), "path": str(path.resolve())}
        for path in sorted(workspace.rglob("*"))
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)
        and not any(part.startswith(".") or part in {"node_modules", "__pycache__"}
                    for part in path.relative_to(workspace).parts)
    ]


def coworker_writable_workspaces(project_id: int, agent_id: int) -> list[Path]:
    """Only this coworker's task folders in this project may be added as write roots."""
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id FROM tasks WHERE project_id = ? AND assigned_agent_id = ? ORDER BY id",
            (project_id, agent_id),
        ).fetchall()
    return [task_workspace(project_id, row["id"]).resolve() for row in rows]


def coworker_task_file_context(project_id: int, agent_id: int, task_id: int) -> str:
    """List the coworker's task files in the current discussion."""
    with get_connection() as connection:
        rows = connection.execute(
            """SELECT id, title FROM tasks WHERE project_id = ? AND assigned_agent_id = ?
               AND thread_id = (SELECT thread_id FROM tasks WHERE id = ? AND project_id = ?)
               AND id <= ? ORDER BY id DESC""",
            (project_id, agent_id, task_id, project_id, task_id),
        ).fetchall()
    blocks = []
    for row in rows:
        files = task_artifacts(project_id, row["id"])
        if files:
            label = "Current task" if row["id"] == task_id else "Earlier coworker task (writable)"
            blocks.append(f"{label} #{row['id']}: {row['title']}\n" +
                          "\n".join(f"- {item['name']}: {item['path']}" for item in files))
    return "\n\n".join(blocks) or "No saved deliverables found for this coworker in this discussion."
