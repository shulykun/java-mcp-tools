# java-mcp-tools

MCP server with IntelliJ-compatible tools for Java projects — **no IDE required**.

Designed for AI coding assistants (Qwen Code CLI, Claude Code, etc.) that support MCP.

> **v0.2** — stable subset. Unreliable tools removed.  
> **v0.1-experimental** — full set including `get_file_problems`, `rename_refactoring`, `find_usages(method_name)`.

---

## Tools (v0.2 stable)

### File system
| Tool | Description |
|------|-------------|
| `create_new_file` | Create a file with optional content |
| `get_file_text_by_path` | Read file content (with truncation support) |
| `replace_text_in_file` | Find-and-replace in a file |
| `list_directory_tree` | ASCII tree of a directory |
| `find_files_by_glob` | Find files by glob pattern (`src/**/*.java`) |
| `find_files_by_name_keyword` | Find files by name substring |

### Search
| Tool | Description |
|------|-------------|
| `search_in_files_by_text` | Full-project text search with `\|\|highlight\|\|` |
| `search_in_files_by_regex` | Full-project regex search |

### Project info
| Tool | Description |
|------|-------------|
| `get_project_modules` | Discover Maven/Gradle modules |
| `get_project_dependencies` | Parse dependencies from pom.xml/build.gradle |

### Dependency graph
| Tool | Description |
|------|-------------|
| `find_usages` | Find all usages of a class (import graph + text search) |
| `analyze_impact` | Blast radius via import graph (BFS) |
| `find_spring_dependencies` | Spring injection map (@Autowired, @Inject, Lombok) via AST |
| `analyze_spring_impact` | Blast radius including injection edges — more accurate than import-only |

### Architecture
| Tool | Description |
|------|-------------|
| `get_architecture` | Full AST-based dependency graph: layer table, key flows, violations, Mermaid |
| `get_architecture_violations` | Detect layer rule breaches (DTO→Service, Config→Repository, etc.) |

### Analysis & execution
| Tool | Description |
|------|-------------|
| `get_symbol_info` | Symbol info at position (tree-sitter AST) |
| `execute_run_configuration` | Run Maven/Gradle build/test/clean |

---

## What was removed in v0.2 (and why)

| Tool | Reason |
|------|--------|
| `get_file_problems` | javac without classpath = 100 false errors on any real project |
| `rename_refactoring` | Word-boundary replace — unsafe for autonomous agents (renames `Bike` in `BikeService` too) |
| `find_usages(method_name)` | Method filter logic was fragile; use `search_in_files_by_regex("\\.methodName\\(")` instead |

---

## Installation

```bash
cd java-mcp-tools
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running

```bash
python -m java_mcp.server
# or
java-mcp
```

## Qwen Code CLI setup

Copy `.qwen/config.json` to your project root and adjust `cwd` path.  
System prompt is in `qwen-system-prompt.md`.

```json
{
  "systemPrompt": "qwen-system-prompt.md",
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
pytest tests/ -v        # 129 tests
# Integration tests require mall + bike-rental-service in ../
```

## Architecture

```
java_mcp/
  server.py           ← FastMCP server, tool registration
  project.py          ← Project root resolution + path traversal guard
  tools/
    filesystem.py     ← create, read, replace, tree, glob, keyword
    search.py         ← text + regex search with ||highlight||
    project_info.py   ← modules + deps (Maven + Gradle)
    java_analysis.py  ← get_symbol_info (tree-sitter + regex fallback)
    graph.py          ← find_usages, analyze_impact (import graph BFS)
    spring_graph.py   ← find_spring_dependencies, analyze_spring_impact (AST injection graph)
    architecture.py   ← get_architecture, get_architecture_violations
    dep_graph_renderer.py  ← layered/mermaid/tree/json renderers (ported from vibe-code-rag)
    dependency_extractor.py ← tree-sitter: imports, types, method calls
    dependency_graph.py    ← Edge graph (incoming/outgoing)
    project_scanner.py     ← Maven/Gradle module discovery
    runner.py         ← execute_run_configuration
```

## Tested on real projects

| Project | Files | Modules | Notes |
|---------|-------|---------|-------|
| [mall (macrozheng)](https://github.com/macrozheng/mall) | 526 | 8 | Spring Boot e-commerce |
| [bike-rental-service](https://github.com/shulykun/bike-rental-service) | 43 | 1 | Spring Boot + Lombok |
