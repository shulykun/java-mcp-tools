"""
Java MCP Tools Server
IntelliJ-compatible MCP tools for Java projects — no IDE required.

Usage:
  python -m java_mcp.server          # stdio (for Qwen Code CLI, Claude Code, etc.)
  java-mcp                           # via installed script
"""
import json
from typing import Optional

from fastmcp import FastMCP

from java_mcp.tools.filesystem import (
    create_new_file,
    get_file_text_by_path,
    replace_text_in_file,
    list_directory_tree,
    find_files_by_glob,
    find_files_by_name_keyword,
)
from java_mcp.tools.search import (
    search_in_files_by_text,
    search_in_files_by_regex,
)
from java_mcp.tools.project_info import (
    get_project_modules,
    get_project_dependencies,
)
from java_mcp.tools.java_analysis import get_symbol_info
from java_mcp.tools.runner import execute_run_configuration
from java_mcp.tools.graph import find_usages, analyze_impact
from java_mcp.tools.spring_graph import find_spring_dependencies, analyze_spring_impact
from java_mcp.tools.architecture import get_architecture, get_architecture_violations

mcp = FastMCP(
    "java-mcp-tools",
    instructions=(
        "MCP server providing IntelliJ-compatible tools for Java projects. "
        "Use project_path to specify the absolute path to your Java project root. "
        "All file paths are relative to project_path."
    ),
)


# ---------------------------------------------------------------------------
# File system tools
# ---------------------------------------------------------------------------

@mcp.tool()
def create_new_file(
    project_path: str,
    path_in_project: str,
    text: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """
    Create a new file at path_in_project inside the project.
    Optionally writes text into it. Creates parent directories automatically.
    """
    return create_new_file(project_path, path_in_project, text, overwrite)


@mcp.tool()
def get_file_text_by_path(
    project_path: str,
    path_in_project: str,
    max_lines: Optional[int] = None,
    truncate_mode: str = "end",
) -> str:
    """
    Read the content of a file by its project-relative path.
    truncate_mode: start | middle | end | none
    """
    return get_file_text_by_path(project_path, path_in_project, max_lines, truncate_mode)


@mcp.tool()
def replace_text_in_file(
    project_path: str,
    path_in_project: str,
    old_text: str,
    new_text: str,
    replace_all: bool = True,
    case_sensitive: bool = True,
) -> str:
    """
    Find-and-replace text in a file.
    Returns: ok | file not found | no occurrences found
    """
    return replace_text_in_file(project_path, path_in_project, old_text, new_text, replace_all, case_sensitive)


@mcp.tool()
def list_directory_tree(
    project_path: str,
    directory_path: str = "",
    max_depth: int = 5,
) -> str:
    """
    Return ASCII tree of a directory (like the `tree` command).
    directory_path is relative to project root; empty = project root.
    """
    return list_directory_tree(project_path, directory_path, max_depth)


@mcp.tool()
def find_files_by_glob(
    project_path: str,
    glob_pattern: str,
    sub_directory: Optional[str] = None,
    add_excluded: bool = False,
    file_count_limit: int = 100,
) -> list:
    """
    Find files matching a glob pattern (e.g. src/**/*.java).
    Returns list of project-relative paths.
    """
    return find_files_by_glob(project_path, glob_pattern, sub_directory, add_excluded, file_count_limit)


@mcp.tool()
def find_files_by_name_keyword(
    project_path: str,
    name_keyword: str,
    file_count_limit: int = 100,
) -> list:
    """
    Find files whose name contains name_keyword (case-sensitive substring).
    Returns list of project-relative paths.
    """
    return find_files_by_name_keyword(project_path, name_keyword, file_count_limit)


# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_in_files_by_text(
    project_path: str,
    search_text: str,
    directory_to_search: Optional[str] = None,
    file_mask: Optional[str] = None,
    case_sensitive: bool = True,
    max_usage_count: int = 100,
) -> list:
    """
    Search for a text substring in all project files.
    Matches highlighted with ||text||.
    Returns list of {file, line, column, preview}.
    """
    return search_in_files_by_text(
        project_path, search_text, directory_to_search, file_mask, case_sensitive, max_usage_count
    )


@mcp.tool()
def search_in_files_by_regex(
    project_path: str,
    regex_pattern: str,
    directory_to_search: Optional[str] = None,
    file_mask: Optional[str] = None,
    case_sensitive: bool = True,
    max_usage_count: int = 100,
) -> list:
    """
    Search for a regex pattern in all project files.
    Matches highlighted with ||text||.
    Returns list of {file, line, column, preview}.
    """
    return search_in_files_by_regex(
        project_path, regex_pattern, directory_to_search, file_mask, case_sensitive, max_usage_count
    )


# ---------------------------------------------------------------------------
# Project info tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_project_modules(project_path: str) -> list:
    """
    Discover all modules in a Maven or Gradle project.
    Returns list of {name, type, path, build_file}.
    """
    return get_project_modules(project_path)


@mcp.tool()
def get_project_dependencies(project_path: str) -> list:
    """
    Parse project dependencies from pom.xml or build.gradle.
    Returns list of {group, artifact, version, scope}.
    """
    return get_project_dependencies(project_path)


# ---------------------------------------------------------------------------
# Java analysis tools
# ---------------------------------------------------------------------------

@mcp.tool()
def get_symbol_info(
    project_path: str,
    file_path: str,
    line: int,
    column: int,
) -> dict:
    """
    Get information about the symbol at the given position (1-based line/column).
    Uses tree-sitter for accurate AST-based analysis; falls back to regex.
    Returns {name, node_type, declaration_type, declaration_snippet, ...}.
    """
    return get_symbol_info(project_path, file_path, line, column)


# ---------------------------------------------------------------------------
# Runner tool
# ---------------------------------------------------------------------------

@mcp.tool()
def execute_run_configuration(
    project_path: str,
    configuration_name: str,
    timeout: int = 120_000,
    max_lines_count: int = 500,
    truncate_mode: str = "end",
) -> dict:
    """
    Execute a build/run configuration.
    Supports presets (test, build, clean, install) and raw commands.
    Returns {exit_code, output, success}.
    """
    return execute_run_configuration(
        project_path, configuration_name, timeout, max_lines_count, truncate_mode
    )


# ---------------------------------------------------------------------------
# Dependency graph tools
# ---------------------------------------------------------------------------

@mcp.tool()
def find_usages(
    project_path: str,
    class_name: str,
    max_results: int = 50,
) -> dict:
    """
    Find all usages of a class across the project.
    Uses import graph + text search. Returns {class_fqn, usages: [{file, line, preview, usage_type}]}.
    usage_type: import | declaration | instantiation | static_call | implements | extends | reference
    Tip: to find specific method call sites, use search_in_files_by_regex with pattern \\.methodName\\(
    """
    return find_usages(project_path, class_name, None, max_results)


@mcp.tool()
def analyze_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Analyze the blast radius of changing a class: who directly and indirectly depends on it.
    Uses BFS on the reverse import graph up to max_depth levels.
    Returns {total_impacted, risk_level (none/low/medium/high/critical), impact_tree, summary}.
    Use this before making changes to understand the scope of impact.
    """
    return analyze_impact(project_path, class_name, max_depth)


# ---------------------------------------------------------------------------
# Spring injection graph tools
# ---------------------------------------------------------------------------

@mcp.tool()
def find_spring_dependencies(
    project_path: str,
    class_name: Optional[str] = None,
) -> dict:
    """
    Scan Spring injection relationships via AST (tree-sitter).
    Detects @Autowired, @Inject, and private final fields with @RequiredArgsConstructor (Lombok).

    If class_name given: returns {injections: [...], injected_by: [...], summary}
    If class_name is None: returns full project injection graph.

    injections = what this class depends on (its own injected fields)
    injected_by = which other classes inject this class
    injection_type: autowired | inject | lombok_constructor
    """
    return find_spring_dependencies(project_path, class_name)


@mcp.tool()
def analyze_spring_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Like analyze_impact but includes Spring injection edges (@Autowired, Lombok constructor).
    More accurate blast-radius than import-only graph.
    Shows edge_type: import | injection for each impacted class.
    Returns {total_impacted, risk_level, injection_edges_added, impact_tree, summary}.
    """
    return analyze_spring_impact(project_path, class_name, max_depth)


# ---------------------------------------------------------------------------
# Architecture analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def get_architecture(
    project_path: str,
    format: str = "layered",
) -> str:
    """
    Build full AST-based dependency graph of the project.
    Uses tree-sitter to extract classes, imports, type usage — much deeper than import-graph.

    format:
      layered  — layer table (Controller/Service/Repository/...) + key flows + violations (default)
      tree     — each class with its dependency list
      mermaid  — Mermaid diagram for visual rendering
      json     — structured {classes, edges, violations} for programmatic use

    Use 'layered' to understand architecture before implementing a feature.
    Use 'mermaid' to generate a diagram.
    Use 'json' for further processing.
    """
    return get_architecture(project_path, format)


@mcp.tool()
def get_architecture_violations(project_path: str) -> list:
    """
    Detect architectural layer violations using AST dependency graph.
    Checks rules like: DTO must not depend on Service, Repository must not call Service, etc.
    Returns list of {source, target, source_layer, target_layer, reason}.
    Run this before implementing a feature to understand existing architectural debt.
    """
    return get_architecture_violations(project_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
