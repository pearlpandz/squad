import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.db.session import get_connection, project_root
from app.core.runtime import runtime_project_root
from app.services.agent_training import MAX_SOURCE_BYTES


SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = SAFE_NAME_PATTERN.sub("-", value.strip().lower()).strip(".-")
    return cleaned or fallback


async def save_agent_knowledge_files(username: str, files: list[UploadFile],
                                     project_id: int | None = None) -> list[str]:
    relative_paths: list[str] = []
    saved_paths: list[Path] = []
    agent_segment = _safe_segment(username.lstrip("@"), "agent")
    if project_id is None:
        with get_connection() as connection:
            pool = connection.execute("SELECT id FROM projects WHERE code = '_agent-pool'").fetchone()
            if pool is None:
                raise ValueError("Agent pool project is unavailable")
            project_id = pool["id"]
    target_dir = runtime_project_root(project_id) / "knowledge" / agent_segment
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        for upload in files:
            original_name = Path(upload.filename or "").name
            if not original_name:
                continue
            safe_name = _safe_segment(original_name, "knowledge-source")
            target_path = target_dir / f"{uuid4().hex}-{safe_name}"
            saved_paths.append(target_path)
            written = 0
            try:
                with target_path.open("wb") as file_buffer:
                    while chunk := await upload.read(1024 * 1024):
                        written += len(chunk)
                        if written > MAX_SOURCE_BYTES:
                            raise ValueError(f"File exceeds 50 MB: {original_name}")
                        file_buffer.write(chunk)
                relative_paths.append(target_path.relative_to(project_root()).as_posix())
            finally:
                await upload.close()
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    return relative_paths
