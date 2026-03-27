"""
Architecture analysis tool:
  - get_architecture — полный AST-граф зависимостей проекта
    Возвращает: слои, потоки, нарушения, Mermaid-диаграмму
"""
from pathlib import Path
from java_mcp.project import resolve_project
from java_mcp.tools.dep_graph_renderer import (
    build_project_deps,
    render_layered_view,
    render_full_tree,
    render_mermaid,
    render_edges_json,
    _detect_violations,
)


def get_architecture(
    project_path: str,
    format: str = "layered",
) -> str:
    """
    Build full AST-based dependency graph and render it.

    format options:
      layered  — layer table + key flows + violations (default, best for AI)
      tree     — each class with its dependencies listed
      mermaid  — Mermaid graph diagram
      json     — structured data: classes, edges, violations
    """
    root = resolve_project(project_path)
    deps = build_project_deps(root)

    if format == "mermaid":
        return render_mermaid(deps)
    elif format == "tree":
        return render_full_tree(deps)
    elif format == "json":
        return render_edges_json(deps)
    else:
        return render_layered_view(deps)


def get_architecture_violations(project_path: str) -> list[dict]:
    """
    Detect architectural layer violations:
    e.g. DTO depending on Service, Repository calling Service, etc.
    Returns list of {source, target, source_layer, target_layer, reason}.
    """
    root = resolve_project(project_path)
    deps = build_project_deps(root)
    return _detect_violations(deps)
