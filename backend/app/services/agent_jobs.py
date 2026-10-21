"""Independent backend threads for coworker execution and training."""

import json
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.db.session import get_connection


_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="coworker")
_locks_guard = threading.Lock()
_agent_locks: dict[int, threading.Lock] = {}
_logger = logging.getLogger(__name__)


def _report_background_error(future: Any) -> None:
    error = future.exception()
    if error is not None:
        _logger.error("Coworker background work failed", exc_info=(type(error), error, error.__traceback__))


def _lock_for(agent_id: int) -> threading.Lock:
    with _locks_guard:
        return _agent_locks.setdefault(agent_id, threading.Lock())


def submit_agent_work(agent_id: int, action: Callable[..., Any], *args: Any) -> None:
    """Serialize one coworker's runs while allowing different coworkers in parallel."""
    def run() -> None:
        with _lock_for(agent_id):
            action(*args)
    _executor.submit(run).add_done_callback(_report_background_error)


def submit_router_work(action: Callable[..., Any], *args: Any) -> None:
    _executor.submit(action, *args).add_done_callback(_report_background_error)


def _job_detail(row: Any) -> dict:
    return {
        "id": row["id"], "agent_id": row["agent_id"], "kind": row["kind"],
        "status": row["status"], "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"], "created_at": row["created_at"],
        "started_at": row["started_at"], "finished_at": row["finished_at"],
    }


def get_agent_job(agent_id: int, job_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM agent_jobs WHERE id = ? AND agent_id = ?", (job_id, agent_id),
        ).fetchone()
    return _job_detail(row) if row else None


def latest_agent_job(agent_id: int, kind: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """SELECT * FROM agent_jobs WHERE agent_id = ? AND kind = ?
               ORDER BY id DESC LIMIT 1""", (agent_id, kind),
        ).fetchone()
    return _job_detail(row) if row else None


def enqueue_agent_job(agent_id: int, kind: str, request: dict,
                      action: Callable[[], dict]) -> dict:
    if kind not in {"self_train", "trial"}:
        raise ValueError("Unsupported agent job")
    with get_connection() as connection:
        if kind == "self_train":
            current = connection.execute(
                """SELECT * FROM agent_jobs WHERE agent_id = ? AND kind = 'self_train'
                   AND status IN ('queued', 'running') ORDER BY id DESC LIMIT 1""",
                (agent_id,),
            ).fetchone()
            if current:
                return _job_detail(current)
        job_id = connection.execute(
            """INSERT INTO agent_jobs (agent_id, kind, request_json)
               VALUES (?, ?, ?)""", (agent_id, kind, json.dumps(request)),
        ).lastrowid
    def execute() -> None:
        with _lock_for(agent_id):
            with get_connection() as connection:
                connection.execute(
                    """UPDATE agent_jobs SET status = 'running', started_at = datetime('now')
                       WHERE id = ? AND status = 'queued'""", (job_id,),
                )
            try:
                result = action()
                with get_connection() as connection:
                    connection.execute(
                        """UPDATE agent_jobs SET status = 'completed', result_json = ?,
                           finished_at = datetime('now') WHERE id = ?""",
                        (json.dumps(result), job_id),
                    )
            except Exception as exc:
                detail = str(getattr(exc, "detail", exc)) or type(exc).__name__
                with get_connection() as connection:
                    connection.execute(
                        """UPDATE agent_jobs SET status = 'failed', error = ?,
                           finished_at = datetime('now') WHERE id = ?""",
                        (detail[:2000], job_id),
                    )
    _executor.submit(execute).add_done_callback(_report_background_error)
    return get_agent_job(agent_id, job_id)


def fail_interrupted_jobs() -> None:
    with get_connection() as connection:
        connection.execute(
            """UPDATE agent_jobs SET status = 'failed',
               error = 'The backend restarted before this job completed. Please start it again.',
               finished_at = datetime('now') WHERE status IN ('queued', 'running')""",
        )
