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
from java_mcp.tools.java_analysis import (
    get_file_problems,
    get_symbol_info,
    rename_refactoring,
)
from java_mcp.tools.runner import execute_run_configuration
from java_mcp.tools.graph import find_usages, analyze_impact
from java_mcp.tools.spring_graph import find_spring_dependencies, analyze_spring_impact

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
def tool_create_new_file(
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
def tool_get_file_text_by_path(
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
def tool_replace_text_in_file(
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
def tool_list_directory_tree(
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
def tool_find_files_by_glob(
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
def tool_find_files_by_name_keyword(
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
def tool_search_in_files_by_text(
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
def tool_search_in_files_by_regex(
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
def tool_get_project_modules(project_path: str) -> list:
    """
    Discover all modules in a Maven or Gradle project.
    Returns list of {name, type, path, build_file}.
    """
    return get_project_modules(project_path)


@mcp.tool()
def tool_get_project_dependencies(project_path: str) -> list:
    """
    Parse project dependencies from pom.xml or build.gradle.
    Returns list of {group, artifact, version, scope}.
    """
    return get_project_dependencies(project_path)


# ---------------------------------------------------------------------------
# Java analysis tools
# ---------------------------------------------------------------------------

@mcp.tool()
def tool_get_file_problems(
    project_path: str,
    file_path: str,
    errors_only: bool = False,
) -> list:
    """
    Analyze a Java file for problems using javac + heuristic rules.
    Returns list of {severity, description, line, column, source}.
    """
    return get_file_problems(project_path, file_path, errors_only)


@mcp.tool()
def tool_get_symbol_info(
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


@mcp.tool()
def tool_rename_refactoring(
    project_path: str,
    path_in_project: str,
    symbol_name: str,
    new_name: str,
) -> dict:
    """
    Rename a symbol across all .java files in the project (whole-word match).
    Returns {status, renamed_files: [{file, replacements}], total_replacements}.
    """
    return rename_refactoring(project_path, path_in_project, symbol_name, new_name)


# ---------------------------------------------------------------------------
# Runner tool
# ---------------------------------------------------------------------------

@mcp.tool()
def tool_execute_run_configuration(
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
def tool_find_usages(
    project_path: str,
    class_name: str,
    method_name: Optional[str] = None,
    max_results: int = 50,
) -> dict:
    """
    Find all usages of a class (and optionally a specific method) across the project.
    Uses import graph + text search. Returns {class_fqn, usages: [{file, line, preview, usage_type}]}.
    usage_type: import | declaration | instantiation | static_call | implements | extends | reference
    """
    return find_usages(project_path, class_name, method_name, max_results)


@mcp.tool()
def tool_analyze_impact(
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
def tool_find_spring_dependencies(
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
def tool_analyze_spring_impact(
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
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
