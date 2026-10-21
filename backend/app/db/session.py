import sqlite3
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path
from contextlib import closing

from app.core.config import settings
from app.core.runtime import project_root, runtime_project_root


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def database_path() -> Path:
    configured_path = Path(settings.sqlite_database_path)
    resolved = configured_path if configured_path.is_absolute() else project_root() / configured_path
    # Older .env files must not keep the live database in the backend folder.
    if resolved.resolve() == (project_root() / "backend/data/multi-agent-team.db").resolve():
        return project_root() / ".runtime/multi-agent-team.db"
    return resolved


def relocate_legacy_database() -> None:
    destination = database_path()
    legacy = project_root() / "backend/data/multi-agent-team.db"
    if destination.resolve() != (project_root() / ".runtime/multi-agent-team.db").resolve():
        return
    if destination.exists() or not legacy.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    backups = runtime_project_root() / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="database-move-", suffix=".db", dir=backups)
    os.close(handle)
    temporary_path = Path(temporary)
    try:
        with closing(sqlite3.connect(legacy)) as source, closing(sqlite3.connect(temporary_path)) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Legacy database relocation failed integrity verification")
        os.replace(temporary_path, destination)
        legacy.replace(backups / "multi-agent-team.db.legacy")
    finally:
        temporary_path.unlink(missing_ok=True)


def get_connection() -> sqlite3.Connection:
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def iter_migration_files() -> Iterator[tuple[str, Path]]:
    migrations_root = backend_root() / "db" / "migrations"
    for version_dir in sorted(
        (path for path in migrations_root.iterdir() if path.is_dir()),
        key=lambda path: tuple(int(part) for part in path.name.split(".")),
    ):
        for migration_file in sorted(version_dir.glob("*.sql")):
            yield version_dir.name, migration_file


def migration_applied(connection: sqlite3.Connection, version: str) -> bool:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'schema_migrations'
        """
    ).fetchone()
    if table_exists is None:
        return False
    row = connection.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        (version,),
    ).fetchone()
    return row is not None


def initialize_database() -> None:
    relocate_legacy_database()
    with get_connection() as connection:
        for version, migration_file in iter_migration_files():
            if migration_applied(connection, version):
                continue
            connection.executescript(migration_file.read_text(encoding="utf-8"))
