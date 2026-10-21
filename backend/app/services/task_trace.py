"""Run-scoped execution logs, separate from task deliverables."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.runtime import runtime_project_root
from app.db.session import get_connection


def task_trace_directory(project_id: int, task_id: int, run_id: int) -> Path:
    if min(project_id, task_id, run_id) < 1:
        raise ValueError("Trace IDs must be positive")
    return runtime_project_root(project_id) / "logs" / f"task-{task_id}" / f"run-{run_id}"


def record_trace(directory: Path, stage: str, detail: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                 "stage": stage, "detail": detail}) + "\n")


def read_trace(directory: Path) -> dict:
    files = []
    if directory.is_dir():
        root = directory.resolve()
        for path in sorted(directory.iterdir()):
            if path.suffix not in {".log", ".jsonl"} or path.is_symlink() or not path.is_file():
                continue
            if not path.resolve().is_relative_to(root):
                continue
            size = path.stat().st_size
            with path.open("rb") as stream:
                stream.seek(max(0, size - 262144))
                content = stream.read(262144).decode("utf-8", errors="replace")
            files.append({"name": path.name, "path": str(path.resolve()), "content": content,
                          "truncated": size > 262144})
    return {"directory": str(directory.resolve()), "files": files}


def read_run_trace(project_id: int, task_id: int, run_id: int) -> dict:
    directory = task_trace_directory(project_id, task_id, run_id)
    trace = read_trace(directory)
    with get_connection() as connection:
        run = connection.execute(
            """SELECT cr.*, t.title, t.prompt FROM codex_runs cr JOIN tasks t ON t.id = cr.task_id
               WHERE cr.id = ? AND t.id = ? AND t.project_id = ?""",
            (run_id, task_id, project_id),
        ).fetchone()
        if run is None:
            return trace
        events = [dict(row) for row in connection.execute(
            """SELECT created_at, stage, detail FROM task_events WHERE task_id = ?
               AND created_at >= ? AND (? IS NULL OR created_at <= ?) ORDER BY id""",
            (task_id, run["created_at"], run["finished_at"], run["finished_at"]),
        )]
        project_runs = connection.execute(
            """SELECT cr.id, cr.finished_at FROM codex_runs cr JOIN tasks t ON t.id = cr.task_id
               WHERE t.project_id = ? AND cr.finished_at IS NOT NULL""", (project_id,),
        ).fetchall()
    recovery = ""
    if not trace["files"] and run["finished_at"]:
        # Old runners wrote UUID logs at completion. Recover only a unique time match
        # that cannot also belong to another run in this project.
        finished = datetime.fromisoformat(run["finished_at"]).replace(tzinfo=timezone.utc).timestamp()
        candidates = []
        for path in sorted((runtime_project_root(project_id) / "logs").glob("codex-*.stdout.log")):
            if path.is_symlink() or abs(path.stat().st_mtime - finished) > 2:
                continue
            matching = [row["id"] for row in project_runs if abs(
                datetime.fromisoformat(row["finished_at"]).replace(tzinfo=timezone.utc).timestamp()
                - path.stat().st_mtime) <= 2]
            if matching == [run_id]:
                candidates.append(path)
        if len(candidates) == 1:
            legacy = read_trace(candidates[0].parent)
            prefix = candidates[0].name.removesuffix(".stdout.log")
            trace["files"] = [file for file in legacy["files"]
                              if file["name"] in {f"{prefix}.stdout.log", f"{prefix}.stderr.log"}]
            recovery = "Legacy CLI logs recovered by a unique project/run completion-time match (within two seconds)."
    command = json.loads(run["command_json"] or "{}")
    trace["files"].sort(key=lambda file: (
        0 if file["name"] == "events.jsonl" else
        1 if file["name"].endswith(".stdout.log") else
        2 if file["name"].endswith(".stderr.log") else 3,
        file["name"],
    ))
    overview = (f"TASK #{task_id} / RUN #{run_id}\nTitle: {run['title']}\n"
                f"Status: {run['process_status']}\nReceived: {run['created_at']} UTC\n"
                f"Started: {run['started_at'] or 'Not started'} UTC\n"
                f"Finished: {run['finished_at'] or 'Pending'} UTC\n\n"
                f"RECEIVED INPUT\n{command.get('request', run['prompt'])}\n\n"
                f"ROUTING METADATA\n{json.dumps(command, indent=2, ensure_ascii=False)}\n\n"
                "RECORDED TASK PROGRESS DURING THIS RUN\n" +
                "\n".join(f"[{event['created_at']} UTC] {event['stage']}: {event['detail']}" for event in events) +
                f"\n\nRESULT / FAILURE\n{run['output_summary'] or 'Pending'}\n")
    trace["files"].insert(0, {"name": "run-overview.log", "path": None,
                              "content": overview, "truncated": False})
    trace["recovery"] = recovery
    trace["has_cli_logs"] = any(file["name"].endswith(".stdout.log") for file in trace["files"])
    return trace
