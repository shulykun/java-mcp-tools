# java-mcp-tools

MCP server providing IntelliJ-compatible tools for Java projects — **no IDE required**.

Designed for AI coding assistants like Qwen Code CLI, Claude Code, and others that support MCP.

## Tools

| Tool | Description |
|------|-------------|
| `create_new_file` | Create a file with optional content |
| `get_file_text_by_path` | Read file content with truncation support |
| `replace_text_in_file` | Find-and-replace in a file |
| `list_directory_tree` | ASCII tree of a directory |
| `find_files_by_glob` | Find files by glob pattern (`src/**/*.java`) |
| `find_files_by_name_keyword` | Find files by name substring |
| `search_in_files_by_text` | Full-project text search |
| `search_in_files_by_regex` | Full-project regex search |
| `get_project_modules` | Discover Maven/Gradle modules |
| `get_project_dependencies` | Parse dependencies from pom.xml/build.gradle |
| `get_file_problems` | Static analysis via javac + heuristics |
| `get_symbol_info` | Symbol info at position (tree-sitter) |
| `rename_refactoring` | Rename symbol across all .java files |
| `execute_run_configuration` | Run Maven/Gradle build/test/clean |

## Installation

```bash
cd java-mcp-tools
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running

```bash
# Start MCP server (stdio — default for Qwen Code CLI)
python -m java_mcp.server
# or
java-mcp
```

## Qwen Code CLI configuration

Add to your MCP config:

```json
{
  "mcpServers": {
    "java-tools": {
      "command": "python",
      "args": ["-m", "java_mcp.server"],
      "cwd": "/path/to/java-mcp-tools"
    }
  }
}
```

## Running tests

```bash
pytest tests/ -v
```

## Architecture

```
java_mcp/
  server.py          ← FastMCP server, tool registration
  project.py         ← Project root resolution + security
  tools/
    filesystem.py    ← create_new_file, get_file_text, replace_text, tree, glob, keyword
    search.py        ← search_by_text, search_by_regex
    project_info.py  ← get_modules, get_dependencies (Maven + Gradle)
    java_analysis.py ← get_file_problems, get_symbol_info, rename_refactoring
    runner.py        ← execute_run_configuration
```

## Notes

- `rename_refactoring` uses whole-word matching (`\bSymbolName\b`) — context-aware via tree-sitter if available
- `get_file_problems` runs javac if available in PATH, plus regex-based heuristics (System.out, empty catch, TODO)
- `get_symbol_info` uses tree-sitter-java for AST analysis, falls back to regex
- All paths are relative to `project_path`; path traversal outside project root is blocked
