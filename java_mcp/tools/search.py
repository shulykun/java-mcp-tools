"""
Search tools:
  - search_in_files_by_text
  - search_in_files_by_regex
"""
import re
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project

_EXCLUDED_DIRS = {".git", ".idea", "target", "build", ".gradle", "__pycache__", "node_modules"}

_BINARY_EXTENSIONS = {
    ".class", ".jar", ".war", ".ear", ".zip", ".gz", ".tar",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".so", ".dll", ".dylib", ".exe",
}


def _is_binary(path: Path) -> bool:
    return path.suffix.lower() in _BINARY_EXTENSIONS


def _file_mask_matches(path: Path, file_mask: Optional[str]) -> bool:
    if not file_mask:
        return True
    return path.match(file_mask)


def _highlight(line: str, match: re.Match) -> str:
    """Wrap match in || ... || like IntelliJ does."""
    start, end = match.start(), match.end()
    return line[:start] + "||" + line[start:end] + "||" + line[end:]


def _iter_files(root: Path, directory: Optional[str], file_mask: Optional[str]):
    """Yield (file_path, relative_path) for searchable files."""
    search_from = (root / directory).resolve() if directory else root

    for f in search_from.rglob("*"):
        if not f.is_file():
            continue
        if _is_binary(f):
            continue
        if any(part in _EXCLUDED_DIRS for part in f.relative_to(root).parts):
            continue
        if not _file_mask_matches(f, file_mask):
            continue
        yield f, str(f.relative_to(root))


def search_in_files_by_text(
    project_path: str,
    search_text: str,
    directory_to_search: Optional[str] = None,
    file_mask: Optional[str] = None,
    case_sensitive: bool = True,
    max_usage_count: int = 100,
) -> list[dict]:
    """
    Search for a text substring in all project files.
    Returns list of {file, line, column, preview}.
    Matches highlighted with ||text||.
    """
    root = resolve_project(project_path)
    needle = search_text if case_sensitive else search_text.lower()
    results = []

    for f, rel_path in _iter_files(root, directory_to_search, file_mask):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            haystack = line if case_sensitive else line.lower()
            col = haystack.find(needle)
            if col != -1:
                # Build highlighted preview
                preview = line[:col] + "||" + line[col:col + len(search_text)] + "||" + line[col + len(search_text):]
                results.append({
                    "file": rel_path,
                    "line": line_no,
                    "column": col + 1,
                    "preview": preview.strip(),
                })
                if len(results) >= max_usage_count:
                    return results

    return results


def search_in_files_by_regex(
    project_path: str,
    regex_pattern: str,
    directory_to_search: Optional[str] = None,
    file_mask: Optional[str] = None,
    case_sensitive: bool = True,
    max_usage_count: int = 100,
) -> list[dict]:
    """
    Search for a regex pattern in all project files.
    Returns list of {file, line, column, preview}.
    Matches highlighted with ||text||.
    """
    root = resolve_project(project_path)
    flags = 0 if case_sensitive else re.IGNORECASE

    try:
        pattern = re.compile(regex_pattern, flags)
    except re.error as e:
        return [{"error": f"Invalid regex: {e}"}]

    results = []

    for f, rel_path in _iter_files(root, directory_to_search, file_mask):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        for line_no, line in enumerate(lines, start=1):
            for m in pattern.finditer(line):
                preview = _highlight(line, m).strip()
                results.append({
                    "file": rel_path,
                    "line": line_no,
                    "column": m.start() + 1,
                    "preview": preview,
                })
                if len(results) >= max_usage_count:
                    return results

    return results
