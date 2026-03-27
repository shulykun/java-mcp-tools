"""
Spring dependency graph tool:
  - find_spring_dependencies — карта Spring-инъекций (@Autowired, @RequiredArgsConstructor,
                                @Inject, constructor injection) через AST (tree-sitter)
  - analyze_spring_impact    — analyze_impact расширенный injection-рёбрами
"""
import re
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project
from java_mcp.tools.graph import _iter_java_files, _parse_file, _build_graph

_EXCLUDED_DIRS = {".git", ".idea", "target", "build", ".gradle", "__pycache__"}

# ── tree-sitter helpers ────────────────────────────────────────────────────

def _get_ts_parser():
    try:
        import tree_sitter_java as tsjava
        from tree_sitter import Language, Parser
        lang = Language(tsjava.language())
        return Parser(lang)
    except ImportError:
        return None


def _extract_injected_fields(content: str, parser) -> list[dict]:
    """
    Use tree-sitter AST to extract injected fields from a Java class.

    Detects:
      1. @Autowired fields
      2. @Inject fields
      3. private final fields (constructor injection via @RequiredArgsConstructor)

    Returns list of {field_name, type_name, injection_type}.
    """
    try:
        tree = parser.parse(content.encode("utf-8", errors="replace"))
    except Exception:
        return []

    results = []

    # Check class-level annotations for @RequiredArgsConstructor / @AllArgsConstructor
    class_has_lombok_constructor = _has_class_annotation(
        tree.root_node, {"RequiredArgsConstructor", "AllArgsConstructor"}
    )

    # Walk all field_declaration nodes
    _walk_fields(tree.root_node, class_has_lombok_constructor, results)

    return results


def _has_class_annotation(root_node, annotation_names: set) -> bool:
    """Check if any class in the file has any of the given annotations."""
    for node in root_node.children:
        if node.type == "class_declaration":
            modifiers = next((c for c in node.children if c.type == "modifiers"), None)
            if modifiers:
                for child in modifiers.children:
                    # tree-sitter uses marker_annotation for @Foo and annotation for @Foo(...)
                    if child.type in ("annotation", "marker_annotation"):
                        name_node = next(
                            (c for c in child.children if c.type == "identifier"),
                            None
                        )
                        if name_node and name_node.text.decode() in annotation_names:
                            return True
    return False


def _walk_fields(node, class_has_lombok: bool, results: list, depth: int = 0):
    """
    Find field_declaration nodes inside class_body and extract injection info.
    tree-sitter layout: root → class_declaration → class_body → field_declaration
    """
    if depth > 15:
        return

    if node.type == "field_declaration":
        modifiers_node = next((c for c in node.children if c.type == "modifiers"), None)
        type_node = next(
            (c for c in node.children if c.type in ("type_identifier", "generic_type")),
            None
        )
        declarator = next((c for c in node.children if c.type == "variable_declarator"), None)

        if not type_node or not declarator:
            return

        modifiers_text = modifiers_node.text.decode() if modifiers_node else ""
        type_name = _extract_simple_type(type_node)
        field_name_node = next((c for c in declarator.children if c.type == "identifier"), None)
        field_name = field_name_node.text.decode() if field_name_node else "?"

        # Determine injection type by checking annotation nodes in modifiers
        annotation_names_present = set()
        if modifiers_node:
            for child in modifiers_node.children:
                if child.type in ("annotation", "marker_annotation"):
                    name_node = next(
                        (c for c in child.children if c.type == "identifier"), None
                    )
                    if name_node:
                        annotation_names_present.add(name_node.text.decode())

        injection_type = None
        if "Autowired" in annotation_names_present:
            injection_type = "autowired"
        elif "Inject" in annotation_names_present:
            injection_type = "inject"
        elif "final" in modifiers_text and "private" in modifiers_text and class_has_lombok:
            injection_type = "lombok_constructor"

        if injection_type:
            results.append({
                "field_name": field_name,
                "type_name": type_name,
                "injection_type": injection_type,
                "modifiers": modifiers_text.replace("\n", " ").strip(),
            })
        return

    for child in node.children:
        _walk_fields(child, class_has_lombok, results, depth + 1)


def _extract_simple_type(type_node) -> str:
    """Extract simple class name from type node (handles generics like List<Bike>)."""
    if type_node.type == "type_identifier":
        return type_node.text.decode()
    if type_node.type == "generic_type":
        # Take the first identifier (e.g. "List" from "List<Bike>")
        first = next((c for c in type_node.children if c.type == "type_identifier"), None)
        return first.text.decode() if first else type_node.text.decode()
    return type_node.text.decode()


def _has_explicit_constructor_injection(field_node) -> bool:
    """Check for @Value or other Spring annotations that suggest constructor injection."""
    modifiers = next((c for c in field_node.children if c.type == "modifiers"), None)
    if not modifiers:
        return False
    text = modifiers.text.decode()
    return "@Value" in text or "@Qualifier" in text


# ── Regex fallback ─────────────────────────────────────────────────────────

def _extract_injected_fields_regex(content: str) -> list[dict]:
    """Fallback when tree-sitter is unavailable."""
    results = []

    # @Autowired or @Inject fields
    pattern_annotated = re.compile(
        r"@(?:Autowired|Inject)\s+(?:private|protected|public)?\s+"
        r"([\w<>]+)\s+(\w+)\s*;",
        re.MULTILINE,
    )
    for m in pattern_annotated.finditer(content):
        injection = "autowired" if "@Autowired" in content[max(0, m.start()-30):m.start()] else "inject"
        results.append({
            "field_name": m.group(2),
            "type_name": m.group(1).split("<")[0],
            "injection_type": injection,
            "modifiers": "",
        })

    # private final fields (Lombok)
    has_lombok = bool(re.search(r"@(?:RequiredArgsConstructor|AllArgsConstructor)", content))
    if has_lombok:
        pattern_final = re.compile(
            r"private\s+final\s+([\w<>]+)\s+(\w+)\s*;", re.MULTILINE
        )
        for m in pattern_final.finditer(content):
            type_name = m.group(1).split("<")[0]
            # Skip primitives and common non-injectable types
            if type_name[0].isupper():
                results.append({
                    "field_name": m.group(2),
                    "type_name": type_name,
                    "injection_type": "lombok_constructor",
                    "modifiers": "private final",
                })

    return results


# ── Public API ─────────────────────────────────────────────────────────────

def find_spring_dependencies(
    project_path: str,
    class_name: Optional[str] = None,
) -> dict:
    """
    Scan project for Spring injection relationships.

    If class_name is given: returns injections for that specific class.
    If class_name is None: returns the full Spring injection graph.

    Detects:
      - @Autowired fields
      - @Inject fields
      - private final fields with @RequiredArgsConstructor / @AllArgsConstructor (Lombok)

    Returns: {
        class_name?,
        injections: [{class, field_name, type_name, injection_type}],
        injected_by: [{class, field_name, injection_type}]  # who injects this class
    }
    """
    root = resolve_project(project_path)
    parser = _get_ts_parser()

    all_injections = {}  # class_name -> list of injected deps

    for f in _iter_java_files(root):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Get class name from file
        cm = re.search(
            r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+(\w+)",
            content
        )
        if not cm:
            continue
        cls = cm.group(1)

        # Extract injections
        if parser:
            fields = _extract_injected_fields(content, parser)
        else:
            fields = _extract_injected_fields_regex(content)

        if fields:
            all_injections[cls] = {
                "file": str(f.relative_to(root)),
                "fields": fields,
            }

    if class_name:
        # Return specific class info
        target = all_injections.get(class_name, {})

        # Also find who injects this class
        injected_by = []
        for cls, info in all_injections.items():
            if cls == class_name:
                continue
            for field in info["fields"]:
                if field["type_name"] == class_name:
                    injected_by.append({
                        "class": cls,
                        "file": info["file"],
                        "field_name": field["field_name"],
                        "injection_type": field["injection_type"],
                    })

        return {
            "class_name": class_name,
            "file": target.get("file"),
            "injections": target.get("fields", []),
            "injected_by": injected_by,
            "summary": _format_summary(class_name, target.get("fields", []), injected_by),
        }

    else:
        # Return full graph
        graph = []
        for cls, info in sorted(all_injections.items()):
            graph.append({
                "class": cls,
                "file": info["file"],
                "dependencies": [
                    {"type": f["type_name"], "field": f["field_name"], "via": f["injection_type"]}
                    for f in info["fields"]
                ],
            })
        return {
            "total_classes_with_injections": len(graph),
            "graph": graph,
        }


def _format_summary(class_name: str, injections: list, injected_by: list) -> list[str]:
    lines = []
    if injections:
        deps = ", ".join(f"{f['type_name']} ({f['injection_type']})" for f in injections[:5])
        if len(injections) > 5:
            deps += f", ...+{len(injections) - 5} more"
        lines.append(f"{class_name} depends on: {deps}")
    else:
        lines.append(f"{class_name} has no detected Spring injections")

    if injected_by:
        users = ", ".join(f"{i['class']} (via {i['field_name']})" for i in injected_by[:5])
        if len(injected_by) > 5:
            users += f", ...+{len(injected_by) - 5} more"
        lines.append(f"{class_name} is injected into: {users}")
    else:
        lines.append(f"{class_name} is not injected into any detected class")

    return lines


def analyze_spring_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Like analyze_impact but uses BOTH import-graph AND Spring injection graph.

    This catches classes that inject the target via @Autowired / @RequiredArgsConstructor
    without necessarily importing it explicitly (or where import-graph alone misses it).

    Returns same structure as analyze_impact + injection_edges count.
    """
    root = resolve_project(project_path)
    parser = _get_ts_parser()

    # Build import graph (existing)
    from java_mcp.tools.graph import _build_graph
    index, forward, reverse = _build_graph(root)

    # Find target FQN
    target_fqn = None
    target_simple = class_name
    for fqn, info in index.items():
        if info["class_name"] == class_name:
            target_fqn = fqn
            break

    if not target_fqn:
        matches = [fqn for fqn in reverse if fqn.endswith(f".{class_name}")]
        if matches:
            target_fqn = matches[0]

    # Build Spring injection edges and add them to reverse graph
    injection_edges_added = 0
    spring_reverse = defaultdict(set)  # type_name -> {class_names that inject it}

    for f in _iter_java_files(root):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        cm = re.search(
            r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?(?:class|interface|enum|record)\s+(\w+)",
            content
        )
        if not cm:
            continue
        cls = cm.group(1)

        if parser:
            fields = _extract_injected_fields(content, parser)
        else:
            fields = _extract_injected_fields_regex(content)

        for field in fields:
            dep_type = field["type_name"]
            # Find FQN of this dependency
            dep_fqn = next(
                (fqn for fqn, info in index.items() if info["class_name"] == dep_type),
                None
            )
            injector_fqn = next(
                (fqn for fqn, info in index.items() if info["class_name"] == cls),
                None
            )
            if dep_fqn and injector_fqn:
                spring_reverse[dep_fqn].add(injector_fqn)
                injection_edges_added += 1

    # Merge spring_reverse into regular reverse
    merged_reverse = defaultdict(set)
    for fqn in set(list(reverse.keys()) + list(spring_reverse.keys())):
        merged_reverse[fqn] = reverse.get(fqn, set()) | spring_reverse.get(fqn, set())

    if not target_fqn:
        return {
            "error": f"Class '{class_name}' not found in project index",
            "hint": "Check class name spelling",
        }

    # BFS on merged graph
    visited = {target_fqn}
    queue = deque([(target_fqn, 0)])
    impact_tree = defaultdict(list)
    total = 0

    while queue:
        current_fqn, depth = queue.popleft()
        if depth >= max_depth:
            continue

        dependents = merged_reverse.get(current_fqn, set())
        for dep_fqn in sorted(dependents):
            if dep_fqn in visited:
                continue
            visited.add(dep_fqn)
            dep_info = index.get(dep_fqn, {})

            # Mark as injection if edge exists in spring graph (even if also in import graph)
            via_injection = dep_fqn in spring_reverse.get(current_fqn, set())
            via_import = dep_fqn in reverse.get(current_fqn, set())
            if via_injection and via_import:
                edge_type = "injection+import"
            elif via_injection:
                edge_type = "injection"
            else:
                edge_type = "import"

            impact_tree[depth + 1].append({
                "fqn": dep_fqn,
                "file": dep_info.get("file", "?"),
                "class_name": dep_info.get("class_name", dep_fqn.split(".")[-1]),
                "edge_type": edge_type,
            })
            total += 1
            queue.append((dep_fqn, depth + 1))

    # Risk
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
        "injection_edges_added": injection_edges_added,
        "impact_tree": {
            f"depth_{d}": impact_tree[d]
            for d in sorted(impact_tree.keys())
        },
        "summary": _impact_summary(impact_tree),
    }


def _impact_summary(impact_tree: dict) -> list[str]:
    lines = []
    for depth in sorted(impact_tree.keys()):
        items = impact_tree[depth]
        label = "direct dependents" if depth == 1 else f"indirect (depth {depth})"
        parts = []
        for i in items[:5]:
            tag = " [injection]" if i.get("edge_type") == "injection" else ""
            parts.append(f"{i['class_name']}{tag}")
        if len(items) > 5:
            parts.append(f"...+{len(items) - 5} more")
        lines.append(f"Level {depth} ({label}): {', '.join(parts)}")
    return lines
