"""Canonical paths for application files outside SQLite."""

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def runtime_root() -> Path:
    return project_root() / ".runtime"


def runtime_project_root(project_id: int | None = None) -> Path:
    if project_id is not None and project_id < 1:
        raise ValueError("Project ID must be positive")
    root = runtime_root() / "projects"
    path = root / (f"project-{project_id}" if project_id is not None else "_system")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Runtime files must stay inside runtime projects")
    return path


def is_managed_knowledge_file(path: Path) -> bool:
    root = (runtime_root() / "projects").resolve()
    candidate = path.resolve()
    if not candidate.is_relative_to(root):
        return False
    parts = candidate.relative_to(root).parts
    return len(parts) >= 3 and parts[0].startswith("project-") and parts[1] == "knowledge"


def model_cache_root() -> Path:
    return runtime_project_root() / "cache" / "models"
