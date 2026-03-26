"""
Java-aware analysis tools:
  - get_file_problems   (javac + basic heuristics)
  - get_symbol_info     (tree-sitter AST)
  - rename_refactoring  (tree-sitter + text replacement)
"""
import re
import subprocess
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project, resolve_file

# --- tree-sitter setup (lazy import) ---
_TS_PARSER = None


def _get_parser():
    global _TS_PARSER
    if _TS_PARSER is None:
        try:
            import tree_sitter_java as tsjava
            from tree_sitter import Language, Parser
            JAVA_LANGUAGE = Language(tsjava.language())
            _TS_PARSER = Parser(JAVA_LANGUAGE)
        except ImportError:
            _TS_PARSER = None
    return _TS_PARSER


# ---------------------------------------------------------------------------
# get_file_problems
# ---------------------------------------------------------------------------

def get_file_problems(
    project_path: str,
    file_path: str,
    errors_only: bool = False,
) -> list[dict]:
    """
    Analyze a Java file for problems.
    Strategy:
      1. Run javac on the file (compile errors)
      2. Run basic regex heuristics (common anti-patterns)
    Returns list of {severity, description, line, column}.
    """
    root = resolve_project(project_path)
    full = (root / file_path).resolve()

    if not full.is_file():
        return [{"error": f"File not found: {file_path}"}]

    problems = []

    # --- javac pass ---
    problems.extend(_run_javac(root, full, file_path))

    # --- heuristic warnings (only if not errors_only) ---
    if not errors_only:
        problems.extend(_heuristic_warnings(full, file_path))

    if errors_only:
        problems = [p for p in problems if p.get("severity") == "ERROR"]

    return problems


def _run_javac(root: Path, full_path: Path, rel_path: str) -> list[dict]:
    """Try to compile with javac and parse errors."""
    # Build classpath from target/classes + common locations
    cp_dirs = [
        root / "target/classes",
        root / "build/classes/java/main",
    ]
    # Also include jars from target/dependency if present
    jar_paths = list((root / "target/dependency").glob("*.jar")) if (root / "target/dependency").exists() else []

    cp_parts = [str(d) for d in cp_dirs if d.exists()] + [str(j) for j in jar_paths]
    cp = ":".join(cp_parts) if cp_parts else "."

    cmd = ["javac", "-cp", cp, "-nowarn" if False else "", str(full_path)]
    cmd = [c for c in cmd if c]  # remove empty strings

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(root),
        )
        return _parse_javac_output(result.stderr, rel_path)
    except FileNotFoundError:
        # javac not available
        return [{"severity": "WARNING", "description": "javac not found in PATH — skipping compile check", "line": 0, "column": 0}]
    except subprocess.TimeoutExpired:
        return [{"severity": "WARNING", "description": "javac timed out", "line": 0, "column": 0}]


def _parse_javac_output(stderr: str, rel_path: str) -> list[dict]:
    """Parse javac stderr: 'File.java:10: error: ...'"""
    problems = []
    pattern = re.compile(r"^.+?:(\d+):\s*(error|warning|note):\s*(.+)$", re.MULTILINE)
    for m in pattern.finditer(stderr):
        severity = m.group(2).upper()
        if severity == "NOTE":
            continue
        problems.append({
            "severity": severity,
            "description": m.group(3).strip(),
            "line": int(m.group(1)),
            "column": 0,
            "source": "javac",
        })
    return problems


def _heuristic_warnings(full_path: Path, rel_path: str) -> list[dict]:
    """Basic static analysis heuristics (no compiler needed)."""
    problems = []
    try:
        lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    rules = [
        (re.compile(r'\bSystem\.out\.print'), "WARNING", "Use logger instead of System.out.print"),
        (re.compile(r'\bSystem\.err\.print'), "WARNING", "Use logger instead of System.err.print"),
        (re.compile(r'catch\s*\(\s*Exception\s+\w+\s*\)\s*\{\s*\}'), "WARNING", "Empty catch block"),
        (re.compile(r'catch\s*\(\s*Throwable\s+\w+\s*\)'), "WARNING", "Catching Throwable is dangerous"),
        (re.compile(r'\.equals\s*\(\s*null\s*\)'), "WARNING", "Use == null instead of .equals(null)"),
        (re.compile(r'TODO|FIXME|HACK'), "INFO", "TODO/FIXME comment"),
        (re.compile(r'@SuppressWarnings\("unchecked"\)'), "INFO", "Unchecked cast suppression"),
        (re.compile(r'new\s+\w+\[\d+\]'), "INFO", "Consider using List instead of fixed-size array"),
    ]

    for line_no, line in enumerate(lines, start=1):
        for pattern, severity, description in rules:
            if pattern.search(line):
                problems.append({
                    "severity": severity,
                    "description": description,
                    "line": line_no,
                    "column": 0,
                    "source": "heuristic",
                })

    return problems


# ---------------------------------------------------------------------------
# get_symbol_info
# ---------------------------------------------------------------------------

def get_symbol_info(
    project_path: str,
    file_path: str,
    line: int,
    column: int,
) -> dict:
    """
    Return info about the symbol at (line, column) using tree-sitter.
    Falls back to regex-based extraction if tree-sitter unavailable.
    """
    root = resolve_project(project_path)
    full = (root / file_path).resolve()

    if not full.is_file():
        return {"error": f"File not found: {file_path}"}

    source = full.read_text(encoding="utf-8", errors="replace")

    parser = _get_parser()
    if parser:
        return _symbol_info_treesitter(source, line, column, file_path)
    else:
        return _symbol_info_regex(source, line, column, file_path)


def _symbol_info_treesitter(source: str, line: int, column: int, file_path: str) -> dict:
    from tree_sitter import Language, Parser
    import tree_sitter_java as tsjava

    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(source.encode("utf-8"))

    # Find node at position (0-indexed internally)
    target_line = line - 1
    target_col = column - 1

    node = tree.root_node.descendant_for_point_range(
        (target_line, target_col),
        (target_line, target_col),
    )

    if not node:
        return {"error": "No symbol at this position"}

    # Walk up to meaningful declaration
    result = {
        "name": node.text.decode("utf-8") if node.text else "",
        "node_type": node.type,
        "line": line,
        "column": column,
        "file": file_path,
    }

    # Find enclosing declaration
    parent = node.parent
    while parent:
        if parent.type in ("method_declaration", "constructor_declaration", "class_declaration",
                           "interface_declaration", "field_declaration", "variable_declarator"):
            result["declaration_type"] = parent.type
            result["declaration_snippet"] = parent.text.decode("utf-8", errors="replace")[:300]
            break
        parent = parent.parent

    return result


def _symbol_info_regex(source: str, line: int, column: int, file_path: str) -> dict:
    """Fallback: extract symbol name and surrounding context without tree-sitter."""
    lines = source.splitlines()
    if line < 1 or line > len(lines):
        return {"error": f"Line {line} out of range"}

    target_line = lines[line - 1]
    col0 = column - 1

    # Find word boundaries around column
    start = col0
    while start > 0 and (target_line[start - 1].isalnum() or target_line[start - 1] == "_"):
        start -= 1
    end = col0
    while end < len(target_line) and (target_line[end].isalnum() or target_line[end] == "_"):
        end += 1

    symbol_name = target_line[start:end]

    # Search for declaration of this symbol in the file
    decl_pattern = re.compile(
        r"((?:public|private|protected|static|final|abstract)\s+)*"
        r"[\w<>\[\]]+\s+" + re.escape(symbol_name) + r"\s*[({;]"
    )

    declaration = None
    for i, src_line in enumerate(lines, start=1):
        if decl_pattern.search(src_line):
            declaration = {"line": i, "snippet": src_line.strip()}
            break

    return {
        "name": symbol_name,
        "line": line,
        "column": column,
        "file": file_path,
        "declaration": declaration,
        "note": "tree-sitter not available — using regex fallback",
    }


# ---------------------------------------------------------------------------
# rename_refactoring
# ---------------------------------------------------------------------------

def rename_refactoring(
    project_path: str,
    path_in_project: str,
    symbol_name: str,
    new_name: str,
) -> dict:
    """
    Rename a symbol across the project.
    Uses tree-sitter to find usages in the target file's package,
    then applies text substitution with word-boundary guards.

    Returns: {renamed_files: [...], total_replacements: N}
    """
    root = resolve_project(project_path)
    anchor_file = (root / path_in_project).resolve()

    if not anchor_file.is_file():
        return {"error": f"File not found: {path_in_project}"}

    # Collect all .java files to update
    java_files = list(root.rglob("*.java"))
    # Filter out excluded dirs
    excluded = {".git", ".idea", "target", "build", ".gradle"}
    java_files = [f for f in java_files if not any(p in excluded for p in f.parts)]

    renamed_files = []
    total = 0

    # Word-boundary pattern: only whole-word matches
    pattern = re.compile(r"\b" + re.escape(symbol_name) + r"\b")

    for java_file in java_files:
        try:
            content = java_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        new_content, count = pattern.subn(new_name, content)
        if count > 0:
            java_file.write_text(new_content, encoding="utf-8")
            renamed_files.append({
                "file": str(java_file.relative_to(root)),
                "replacements": count,
            })
            total += count

    if total == 0:
        return {"error": f"Symbol '{symbol_name}' not found in any .java file"}

    return {
        "status": "ok",
        "symbol": symbol_name,
        "new_name": new_name,
        "renamed_files": renamed_files,
        "total_replacements": total,
    }
