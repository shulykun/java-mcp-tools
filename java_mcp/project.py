"""
Project context — resolves and validates project root path.
Every tool accepts `project_path` and calls resolve_project() first.
"""
from pathlib import Path


class ProjectNotFoundError(Exception):
    pass


def resolve_project(project_path: str) -> Path:
    """Resolve and validate project root. Raises ProjectNotFoundError if not found."""
    p = Path(project_path).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        raise ProjectNotFoundError(f"Project directory not found: {project_path}")
    return p


def resolve_file(project_path: str, relative_path: str) -> Path:
    """Resolve a project-relative file path. Raises FileNotFoundError if missing."""
    root = resolve_project(project_path)
    full = (root / relative_path).resolve()
    # Security: prevent path traversal outside project
    if not str(full).startswith(str(root)):
        raise ValueError(f"Path escapes project root: {relative_path}")
    return full
