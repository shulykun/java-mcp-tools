"""
Java MCP Tools — Agent Edition
For coding agents (Qwen Code CLI, Claude Code, Codex) that have native file tools.

Excludes: create_new_file, get_file_text_by_path, replace_text_in_file, get_symbol_info
Includes: search, navigation, project info, dependency graph, architecture

Usage:
  python -m java_mcp.server_agent
"""
from typing import Optional

from fastmcp import FastMCP

from java_mcp.tools.filesystem import (
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
from java_mcp.tools.runner import execute_run_configuration
from java_mcp.tools.graph import find_usages, analyze_impact
from java_mcp.tools.spring_graph import find_spring_dependencies, analyze_spring_impact
from java_mcp.tools.architecture import get_architecture, get_architecture_violations

mcp = FastMCP(
    "java-mcp-agent",
    instructions=(
        "Java project analysis tools for coding agents. "
        "Use your native tools for reading/writing files. "
        "Use these MCP tools for search, navigation, dependency analysis, and architecture. "
        "Always start with list_directory_tree + get_project_modules. "
        "Always run analyze_spring_impact before modifying any class."
    ),
)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

@mcp.tool()
def list_directory_tree(
    project_path: str,
    directory_path: str = "",
    max_depth: int = 5,
) -> str:
    """
    Return ASCII tree of a directory (like the `tree` command).
    Use at session start to understand project layout.
    directory_path is relative to project root; empty = project root.
    """
    return list_directory_tree(project_path, directory_path, max_depth)


@mcp.tool()
def find_files_by_glob(
    project_path: str,
    glob_pattern: str,
    sub_directory: Optional[str] = None,
    file_count_limit: int = 100,
) -> list:
    """
    Find files matching a glob pattern (e.g. src/**/*.java, **/*Service.java).
    Returns list of project-relative paths.
    Use to locate files before reading them with your native tool.
    """
    return find_files_by_glob(project_path, glob_pattern, sub_directory, False, file_count_limit)


@mcp.tool()
def find_files_by_name_keyword(
    project_path: str,
    name_keyword: str,
    file_count_limit: int = 100,
) -> list:
    """
    Find files whose name contains a keyword (case-sensitive).
    Returns list of project-relative paths.
    Example: find_files_by_name_keyword("BikeController") → ["src/.../BikeController.java"]
    """
    return find_files_by_name_keyword(project_path, name_keyword, file_count_limit)


# ---------------------------------------------------------------------------
# Search
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
    Search for a text substring across all project files.
    Faster than reading files one by one. Matches highlighted with ||text||.
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
    Search for a regex pattern across all project files.
    Use for method call sites: regex_pattern="\\.methodName\\("
    Matches highlighted with ||text||. Returns list of {file, line, column, preview}.
    """
    return search_in_files_by_regex(
        project_path, regex_pattern, directory_to_search, file_mask, case_sensitive, max_usage_count
    )


# ---------------------------------------------------------------------------
# Project info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_project_modules(project_path: str) -> list:
    """
    Discover all modules in a Maven or Gradle project.
    Returns list of {name, type, path, build_file}.
    Use at session start.
    """
    return get_project_modules(project_path)


@mcp.tool()
def get_project_dependencies(project_path: str) -> list:
    """
    Parse project dependencies from pom.xml or build.gradle.
    Returns list of {group, artifact, version, scope}.
    """
    return get_project_dependencies(project_path)


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
    Presets: test, build, clean, install, verify.
    Also accepts raw Maven/Gradle commands: "mvn test -pl module-name"
    Returns {exit_code, output, success}.
    """
    return execute_run_configuration(
        project_path, configuration_name, timeout, max_lines_count, truncate_mode
    )


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------

@mcp.tool()
def find_usages(
    project_path: str,
    class_name: str,
    max_results: int = 50,
) -> dict:
    """
    Find all usages of a class across the project (import graph + text search).
    Returns {class_fqn, usages: [{file, line, preview, usage_type}]}.
    usage_type: import | declaration | instantiation | static_call | implements | extends
    Tip: for method call sites use search_in_files_by_regex with "\\.methodName\\("
    """
    return find_usages(project_path, class_name, None, max_results)


@mcp.tool()
def analyze_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Blast radius of changing a class via import graph (BFS).
    Returns {total_impacted, risk_level: none/low/medium/high/critical, impact_tree, summary}.
    Use analyze_spring_impact for more accurate results in Spring projects.
    """
    return analyze_impact(project_path, class_name, max_depth)


@mcp.tool()
def find_spring_dependencies(
    project_path: str,
    class_name: Optional[str] = None,
) -> dict:
    """
    Detect Spring injection relationships via AST (@Autowired, @Inject, Lombok @RequiredArgsConstructor).
    class_name=None returns the full project injection graph.
    Returns {injections: [...], injected_by: [...], summary}.
    Use before implementing a feature to understand injection patterns in the layer.
    """
    return find_spring_dependencies(project_path, class_name)


@mcp.tool()
def analyze_spring_impact(
    project_path: str,
    class_name: str,
    max_depth: int = 5,
) -> dict:
    """
    Blast radius of changing a class — includes BOTH import edges AND Spring injection edges.
    More accurate than analyze_impact for Spring projects.
    Shows edge_type: import | injection | injection+import.
    ALWAYS run this before modifying any class.
    Returns {total_impacted, risk_level, injection_edges_added, impact_tree, summary}.
    """
    return analyze_spring_impact(project_path, class_name, max_depth)


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

@mcp.tool()
def get_architecture(
    project_path: str,
    format: str = "layered",
) -> str:
    """
    Full AST-based dependency graph of the project.
    format:
      layered  — layer table (Controller/Service/Repository/...) + key flows + violations (default)
      mermaid  — Mermaid diagram
      tree     — per-class dependency list
      json     — structured {classes, edges, violations}
    Use at session start with format="layered" to understand the full architecture.
    """
    return get_architecture(project_path, format)


@mcp.tool()
def get_architecture_violations(project_path: str) -> list:
    """
    Detect architectural layer violations (DTO→Service, Config→Repository, etc.).
    Returns list of {source, target, source_layer, target_layer, reason}.
    Run before implementing a feature to know the existing architectural debt.
    """
    return get_architecture_violations(project_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
