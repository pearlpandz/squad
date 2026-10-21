"""Relocate legacy application files and keep database source paths usable."""

import hashlib
import shutil
import tempfile
from contextlib import closing
from pathlib import Path

from app.core.runtime import model_cache_root, project_root, runtime_project_root
from app.db.session import get_connection
from app.services.knowledge_storage import _safe_segment


def _copy_verified(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(source, destination)
    with source.open("rb") as original, destination.open("rb") as copied:
        if hashlib.file_digest(original, "sha256").digest() != hashlib.file_digest(copied, "sha256").digest():
            raise RuntimeError(f"Runtime relocation would replace a different file: {destination}")


def relocate_runtime_files() -> None:
    root = project_root().resolve()
    legacy_roots = (root / "backend/knowledge_sources", root / "knowledge")
    mappings: dict[str, tuple[Path, Path]] = {}
    with closing(get_connection()) as connection:
        records = connection.execute(
            """SELECT s.relative_path, s.project_id, COALESCE(a.username, 'shared') AS username
               FROM knowledge_sources s LEFT JOIN agents a ON a.id = s.owner_agent_id
               UNION ALL
               SELECT s.relative_path, a.project_id, a.username
               FROM agent_sources s JOIN agents a ON a.id = s.agent_id"""
        ).fetchall()
        for record in records:
            old_path = record["relative_path"]
            source = (root / old_path).resolve()
            if old_path in mappings or not any(source.is_relative_to(base) for base in legacy_roots):
                continue
            destination = (runtime_project_root(record["project_id"]) / "knowledge"
                           / _safe_segment(record["username"], "shared") / source.name)
            if source.is_file():
                _copy_verified(source, destination)
            mappings[old_path] = (source, destination)
        with connection:
            for old_path, (_, destination) in mappings.items():
                new_path = destination.relative_to(root).as_posix()
                for table in ("agent_sources", "knowledge_sources"):
                    connection.execute(f"UPDATE {table} SET relative_path = ? WHERE relative_path = ?", (new_path, old_path))
        # Delete the old copies only after new files are verified and paths committed.
        for source, _ in mappings.values():
            source.unlink(missing_ok=True)

    system = runtime_project_root()
    # Preserve unreferenced legacy files as well, rather than dropping them.
    for legacy_root in legacy_roots:
        if not legacy_root.exists():
            continue
        for source in legacy_root.rglob("*"):
            if source.is_file() and not source.is_symlink() and source.resolve().is_relative_to(legacy_root):
                destination = system / "legacy" / source.relative_to(root)
                _copy_verified(source, destination)
                source.unlink()
    backups = root / ".runtime/backups"
    if backups.exists():
        for source in backups.iterdir():
            if source.is_file():
                destination = system / "backups" / source.name
                _copy_verified(source, destination)
                source.unlink()
    relocate_model_cache()


def relocate_model_cache() -> None:
    """Reuse installed models without changing the user's shared library cache."""
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
    except ImportError:
        return

    cache = model_cache_root()
    cache.mkdir(parents=True, exist_ok=True)
    for name in ("models--sentence-transformers--all-MiniLM-L6-v2",
                 "models--cross-encoder--ms-marco-MiniLM-L6-v2"):
        source = Path(HF_HUB_CACHE) / name
        destination = cache / name
        if destination.exists() or not source.is_dir():
            continue
        with tempfile.TemporaryDirectory(prefix="model-move-", dir=cache) as temporary:
            copied = Path(temporary) / name
            shutil.copytree(source, copied)
            copied.replace(destination)
