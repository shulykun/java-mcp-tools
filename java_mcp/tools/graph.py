"""
Dependency graph tools:
  - find_usages    — кто использует класс/метод (import-граф + text search)
  - analyze_impact — граф влияния: что сломается если изменить X (BFS по импортам)
"""
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project

_EXCLUDED_DIRS = {".git", ".idea", "target", "build", ".gradle", "__pycache__"}

# Regex для парсинга Java файла
_IMPORT_RE = re.compile(r"^import\s+([\w.]+);", re.MULTILINE)
_CLASS_RE = re.compile(
    r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+(\w+)"
)
_PACKAGE_RE = re.compile(r"^package\s+([\w.]+);", re.MULTILINE)


def _iter_java_files(root: Path):
    """Yield all .java files not in excluded dirs."""
    for f in root.rglob("*.java"):
        if any(p in _EXCLUDED_DIRS for p in f.relative_to(root).parts):
            continue
        yield f


def _parse_file(f: Path, root: Path) -> dict:
    """Extract package, class name, imports from a .java file."""
    try:
        content = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    package = ""
    pm = _PACKAGE_RE.search(content)
    if pm:
        package = pm.group(1)

    class_name = ""
    cm = _CLASS_RE.search(content)
    if cm:
        class_name = cm.group(1)

    imports = _IMPORT_RE.findall(content)

    fqn = f"{package}.{class_name}" if package and class_name else class_name

    return {
        "file": str(f.relative_to(root)),
        "package": package,
        "class_name": class_name,
        "fqn": fqn,
        "imports": imports,
        "content": content,
    }


def _build_graph(root: Path) -> tuple[dict, dict]:
    """
    Build forward and reverse import graphs.

    forward[fqn]  = list of fqns this class imports
    reverse[fqn]  = list of fqns that import this class
    Also returns index: fqn -> parsed file info
    """
    index = {}  # fqn -> file_info
    forward = defaultdict(set)  # fqn -> {imported fqns}
    reverse = defaultdict(set)  # fqn -> {fqns that import it}

    # Parse all files
    for f in _iter_java_files(root):
        info = _parse_file(f, root)
        if not info or not info.get("fqn"):
            continue
        fqn = info["fqn"]
        index[fqn] = info

    # Build edges using imports
    # An import "com.example.Foo" means this class depends on Foo
    for fqn, info in index.items():
        for imp in info["imports"]:
            if imp in index:
                forward[fqn].add(imp)
                reverse[imp].add(fqn)

    return index, dict(forward), dict(reverse)


def find_usages(
    project_path: str,
    class_name: str,
    method_name: Optional[str] = None,
    max_results: int = 50,
) -> dict:
    """
    Find all usages of a class (and optionally a method) in the project.

    Strategy:
      1. Build import graph — find all files that import this class
      2. Text search within those files for actual usage patterns
      3. If method_name provided — narrow to method call sites

    Returns: {
        class_fqn, usages: [{file, line, preview, usage_type}],
        total_files_with_import: N
    }
    """
    root = resolve_project(project_path)
    index, forward, reverse = _build_graph(root)

    # Find the target class FQN
    target_fqn = None
    for fqn, info in index.items():
        if info["class_name"] == class_name:
            target_fqn = fqn
            break

    # Files that import target (from graph)
    graph_users = reverse.get(target_fqn, set()) if target_fqn else set()

    # Also text-search for class name (catches same-package usage without import)
    text_users = set()
    pattern = re.compile(r"\b" + re.escape(class_name) + r"\b")
    method_pattern = re.compile(r"\." + re.escape(method_name) + r"\s*\(") if method_name else None

    usages = []

    for f in _iter_java_files(root):
        rel = str(f.relative_to(root))
        # Skip the class definition file itself
        if index.get(target_fqn, {}).get("file") == rel:
            continue

        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = content.splitlines()
        file_has_usage = False

        for line_no, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue

            # Determine usage type
            if f"import {target_fqn}" in line or (target_fqn and f"import {target_fqn}" in line):
                usage_type = "import"
            elif re.search(r"\b" + re.escape(class_name) + r"\s+\w+", line):
                usage_type = "declaration"
            elif re.search(r"\bnew\s+" + re.escape(class_name) + r"\b", line):
                usage_type = "instantiation"
            elif re.search(r"\b" + re.escape(class_name) + r"\.", line):
                usage_type = "static_call"
            elif re.search(r"implements\s+.*\b" + re.escape(class_name) + r"\b", line):
                usage_type = "implements"
            elif re.search(r"extends\s+\b" + re.escape(class_name) + r"\b", line):
                usage_type = "extends"
            else:
                usage_type = "reference"

            # Filter by method if specified
            if method_name and usage_type != "import":
                if not method_pattern.search(line):
                    # Check next line too (method call may span lines)
                    next_line = lines[line_no] if line_no < len(lines) else ""
                    if not method_pattern.search(next_line):
                        continue

            preview = line.strip()
            # Highlight the match
            preview = pattern.sub(lambda m: f"||{m.group()}||", preview, count=1)

            usages.append({
                "file": rel,
                "line": line_no,
                "preview": preview[:120],
                "usage_type": usage_type,
            })
            file_has_usage = True

            if len(usages) >= max_results:
                break

        if file_has_usage:
            text_users.add(rel)

        if len(usages) >= max_results:
            break

    return {
        "class_name": class_name,
        "class_fqn": target_fqn or f"(not found, searched by name: {class_name})",
        "method_filter": method_name,
        "total_usages": len(usages),
        "total_files": len(text_users),
        "usages": usages,
    }


def analyze_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Analyze what would be impacted if class_name changes.

    Uses BFS on the reverse import graph:
      - Level 1: classes that directly import/use class_name
      - Level 2: classes that use level-1 classes
      - ...up to max_depth

    Returns: {
        target, total_impacted, impact_tree: {depth: [classes]},
        risk_level: low/medium/high/critical
    }
    """
    root = resolve_project(project_path)
    index, forward, reverse = _build_graph(root)

    # Find target FQN
    target_fqn = None
    for fqn, info in index.items():
        if info["class_name"] == class_name:
            target_fqn = fqn
            break

    if not target_fqn:
        # Fallback: search by simple name match in reverse keys
        matches = [fqn for fqn in reverse if fqn.endswith(f".{class_name}")]
        if matches:
            target_fqn = matches[0]

    if not target_fqn:
        return {
            "error": f"Class '{class_name}' not found in project index",
            "hint": "Check class name spelling or use FQN",
        }

    # BFS
    visited = {target_fqn}
    queue = deque([(target_fqn, 0)])
    impact_tree = defaultdict(list)
    total = 0

    while queue:
        current_fqn, depth = queue.popleft()
        if depth >= max_depth:
            continue

        dependents = reverse.get(current_fqn, set())
        for dep_fqn in sorted(dependents):
            if dep_fqn in visited:
                continue
            visited.add(dep_fqn)
            dep_info = index.get(dep_fqn, {})
            impact_tree[depth + 1].append({
                "fqn": dep_fqn,
                "file": dep_info.get("file", "?"),
                "class_name": dep_info.get("class_name", dep_fqn.split(".")[-1]),
            })
            total += 1
            queue.append((dep_fqn, depth + 1))

    # Risk assessment
    if total == 0:
        risk = "none"
    elif total <= 3:
        risk = "low"
    elif total <= 10:
        risk = "medium"
    elif total <= 25:
        risk = "high"
    else:
        risk = "critical"

    target_info = index.get(target_fqn, {})

    return {
        "target_class": class_name,
        "target_fqn": target_fqn,
        "target_file": target_info.get("file", "?"),
        "total_impacted": total,
        "risk_level": risk,
        "max_depth_reached": max(impact_tree.keys()) if impact_tree else 0,
        "impact_tree": {
            f"depth_{d}": impact_tree[d]
            for d in sorted(impact_tree.keys())
        },
        "summary": _impact_summary(impact_tree, index),
    }


def _impact_summary(impact_tree: dict, index: dict) -> list[str]:
    """Human-readable summary of impact by layer."""
    lines = []
    for depth in sorted(impact_tree.keys()):
        items = impact_tree[depth]
        label = "direct users" if depth == 1 else f"indirect (depth {depth})"
        names = [i["class_name"] for i in items[:5]]
        if len(items) > 5:
            names.append(f"...+{len(items) - 5} more")
        lines.append(f"Level {depth} ({label}): {', '.join(names)}")
    return lines
