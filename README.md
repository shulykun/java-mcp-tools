# java-mcp-tools — agent branch

MCP server for Java project analysis — **designed for coding agents** (Qwen Code CLI, Claude Code, Codex).

> **This is the `agent` branch** — 14 analysis-only tools.  
> Coding agents have native file read/write. This server provides what they don't have: search, navigation, dependency graph, architecture analysis.  
> For the full 18-tool server (including file tools): see `main` branch.

---

## Tools (14)

### Navigation
| Tool | Description |
|------|-------------|
| `list_directory_tree` | ASCII tree of a directory — use at session start |
| `find_files_by_glob` | Find files by glob pattern (`**/*Service.java`) |
| `find_files_by_name_keyword` | Find files by name substring |

### Search
| Tool | Description |
|------|-------------|
| `search_in_files_by_text` | Full-project text search with `\|\|highlight\|\|` |
| `search_in_files_by_regex` | Full-project regex search — use `\.methodName\(` for call sites |

### Project info
| Tool | Description |
|------|-------------|
| `get_project_modules` | Discover Maven/Gradle modules |
| `get_project_dependencies` | Parse dependencies from pom.xml/build.gradle |
| `execute_run_configuration` | Run Maven/Gradle: `test`, `build`, `clean` or raw command |

### Dependency graph
| Tool | Description |
|------|-------------|
| `find_usages` | All usages of a class (import graph + text search) |
| `analyze_impact` | Blast radius via import graph (BFS) |
| `find_spring_dependencies` | Spring injection map (@Autowired, @Inject, Lombok) via AST |
| `analyze_spring_impact` | Blast radius including injection edges — more accurate than import-only |

### Architecture
| Tool | Description |
|------|-------------|
| `get_architecture` | Full AST dependency graph: layer table, key flows, violations, Mermaid |
| `get_architecture_violations` | Detect layer rule breaches (DTO→Service, Config→Repository, etc.) |

---

## What's NOT here (and why)

| Tool | Why removed |
|------|-------------|
| `create_new_file` | Agents write files natively |
| `get_file_text_by_path` | Agents read files natively |
| `replace_text_in_file` | Agents edit files natively |
| `get_symbol_info` | Requires precise line/col — rarely practical |
| `get_file_problems` | javac without classpath = 100 false errors |
| `rename_refactoring` | Word-boundary replace unsafe for autonomous agents |

---

## Installation

```bash
git clone https://github.com/shulykun/java-mcp-tools
cd java-mcp-tools
git checkout agent
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running

```bash
python -m java_mcp.server_agent
# or
java-mcp-agent
```

## Qwen Code CLI setup

Copy `.qwen/config.json` to your project root, adjust `cwd`:

```json
{
  "systemPrompt": "qwen-system-prompt.md",
  "mcpServers": {
    "java-tools": {
      "command": "python",
      "args": ["-m", "java_mcp.server_agent"],
      "cwd": "/path/to/java-mcp-tools"
    }
  }
}
```

System prompt in `qwen-system-prompt.md` — tells the agent when to use MCP vs native tools.

## How to use

**Session start — always:**
```
list_directory_tree(project_path, max_depth=3)
get_project_modules(project_path)
get_architecture(project_path, format="layered")
```

**Before modifying a class:**
```
analyze_spring_impact(project_path, class_name)
```

**Finding code:**
```
find_files_by_name_keyword("BikeController")   → locate the file
search_in_files_by_text("@Transactional")      → find all usages
search_in_files_by_regex("\\.startRental\\(")  → find method call sites
```

**Read/write files — use your native tools.**

---

## Tested on

| Project | Files | Modules | Violations found |
|---------|-------|---------|------------------|
| [mall (macrozheng)](https://github.com/macrozheng/mall) | 526 | 8 | 0 |
| [bike-rental-service](https://github.com/shulykun/bike-rental-service) | 43 | 1 | 0 |

## Tests

```bash
pytest tests/ -v   # 129 tests, 1 skipped
```

## Code structure

```
java_mcp/
  server_agent.py        ← this branch: 14-tool agent server
  server.py              ← main branch: 18-tool full server
  project.py             ← path resolution + traversal guard
  tools/
    filesystem.py        ← tree, glob, keyword (navigation only)
    search.py            ← text + regex search
    project_info.py      ← modules + deps (Maven + Gradle)
    graph.py             ← find_usages, analyze_impact
    spring_graph.py      ← find_spring_dependencies, analyze_spring_impact
    architecture.py      ← get_architecture, get_architecture_violations
    dep_graph_renderer.py
    dependency_extractor.py
    dependency_graph.py
    project_scanner.py
    runner.py
```
