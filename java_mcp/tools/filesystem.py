"""
File system tools:
  - create_new_file
  - get_file_text_by_path
  - replace_text_in_file
  - list_directory_tree
  - find_files_by_glob
  - find_files_by_name_keyword
"""
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project, resolve_file, ProjectNotFoundError

# Directories always excluded from traversal
_EXCLUDED_DIRS = {".git", ".idea", "target", "build", ".gradle", "__pycache__", "node_modules"}


def create_new_file(
    project_path: str,
    path_in_project: str,
    text: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Create a new file at path_in_project inside the project.
    Optionally write text into it.
    """
    root = resolve_project(project_path)
    full = (root / path_in_project).resolve()

    if not str(full).startswith(str(root)):
        return "error: path escapes project root"

    if full.exists() and not overwrite:
        return f"error: file already exists: {path_in_project}"

    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(text or "", encoding="utf-8")
    return f"ok: created {path_in_project}"


def get_file_text_by_path(
    project_path: str,
    path_in_project: str,
    max_lines: Optional[int] = None,
    truncate_mode: str = "end",
) -> str:
    """
    Read file content. Supports truncation: start / middle / end / none.
    """
    try:
        full = resolve_file(project_path, path_in_project)
    except (FileNotFoundError, ValueError) as e:
        return f"error: {e}"

    if not full.is_file():
        return f"error: not a file: {path_in_project}"

    lines = full.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    if max_lines is None or len(lines) <= max_lines:
        return "".join(lines)

    if truncate_mode == "start":
        kept = lines[-max_lines:]
        return f"[truncated {len(lines) - max_lines} lines from start]\n" + "".join(kept)
    elif truncate_mode == "middle":
        half = max_lines // 2
        kept = lines[:half] + [f"\n[... {len(lines) - max_lines} lines omitted ...]\n"] + lines[-half:]
        return "".join(kept)
    else:  # end (default)
        kept = lines[:max_lines]
        return "".join(kept) + f"\n[truncated {len(lines) - max_lines} lines from end]"


def replace_text_in_file(
    project_path: str,
    path_in_project: str,
    old_text: str,
    new_text: str,
    replace_all: bool = True,
    case_sensitive: bool = True,
) -> str:
    """
    Find-and-replace in a file. Returns status string.
    """
    try:
        full = resolve_file(project_path, path_in_project)
    except FileNotFoundError:
        return "file not found"

    if not full.is_file():
        return "file not found"

    content = full.read_text(encoding="utf-8", errors="replace")

    search = old_text if case_sensitive else old_text.lower()
    haystack = content if case_sensitive else content.lower()

    if search not in haystack:
        return "no occurrences found"

    if replace_all:
        if case_sensitive:
            new_content = content.replace(old_text, new_text)
        else:
            # Case-insensitive replace: rebuild manually
            result = []
            i = 0
            lower_content = content.lower()
            lower_search = old_text.lower()
            slen = len(old_text)
            while i < len(content):
                idx = lower_content.find(lower_search, i)
                if idx == -1:
                    result.append(content[i:])
                    break
                result.append(content[i:idx])
                result.append(new_text)
                i = idx + slen
            new_content = "".join(result)
    else:
        if case_sensitive:
            new_content = content.replace(old_text, new_text, 1)
        else:
            lower_content = content.lower()
            idx = lower_content.find(old_text.lower())
            new_content = content[:idx] + new_text + content[idx + len(old_text):]

    full.write_text(new_content, encoding="utf-8")
    return "ok"


def list_directory_tree(
    project_path: str,
    directory_path: str = "",
    max_depth: int = 5,
) -> str:
    """
    Return ASCII directory tree (like `tree` utility).
    """
    root = resolve_project(project_path)
    start = (root / directory_path).resolve() if directory_path else root

    if not start.exists():
        return f"error: directory not found: {directory_path}"

    lines = [start.name + "/"]
    _build_tree(start, "", max_depth, 0, lines)
    return "\n".join(lines)


def _build_tree(path: Path, prefix: str, max_depth: int, depth: int, lines: list) -> None:
    if depth >= max_depth:
        return

    try:
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
    except PermissionError:
        return

    entries = [e for e in entries if e.name not in _EXCLUDED_DIRS]
    count = len(entries)

    for i, entry in enumerate(entries):
        is_last = i == count - 1
        connector = "└── " if is_last else "├── "
        suffix = "/" if entry.is_dir() else ""
        lines.append(prefix + connector + entry.name + suffix)

        if entry.is_dir():
            extension = "    " if is_last else "│   "
            _build_tree(entry, prefix + extension, max_depth, depth + 1, lines)


def find_files_by_glob(
    project_path: str,
    glob_pattern: str,
    sub_directory: Optional[str] = None,
    add_excluded: bool = False,
    file_count_limit: int = 100,
) -> list[str]:
    """
    Find files matching a glob pattern (relative to project root).
    Returns list of project-relative paths.
    """
    root = resolve_project(project_path)
    search_from = (root / sub_directory).resolve() if sub_directory else root

    results = []
    for match in search_from.rglob("*"):
        if not match.is_file():
            continue
        # Apply glob pattern matching against the relative path
        try:
            rel = match.relative_to(root)
        except ValueError:
            continue
        if not rel.match(glob_pattern) and not match.match(glob_pattern):
            continue
        if not add_excluded:
            if any(part in _EXCLUDED_DIRS for part in match.relative_to(root).parts):
                continue
        results.append(str(match.relative_to(root)))
        if len(results) >= file_count_limit:
            break

    return results


def find_files_by_name_keyword(
    project_path: str,
    name_keyword: str,
    file_count_limit: int = 100,
) -> list[str]:
    """
    Find files whose name contains name_keyword (case-sensitive).
    Returns list of project-relative paths.
    """
    root = resolve_project(project_path)
    results = []

    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if any(part in _EXCLUDED_DIRS for part in f.parts):
            continue
        if name_keyword in f.name:
            results.append(str(f.relative_to(root)))
        if len(results) >= file_count_limit:
            break

    return results
