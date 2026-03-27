"""Minimal Java parser using tree-sitter-java (same as rest of java-mcp-tools)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ParsedFile:
    path: Path
    tree: Any
    source: str
    source_bytes: bytes = field(default=b"")


class CodeParser:
    def __init__(self) -> None:
        import tree_sitter_java as tsjava
        from tree_sitter import Language, Parser
        self._parser = Parser(Language(tsjava.language()))

    def parse_file(self, path: Path) -> ParsedFile:
        source_bytes = path.read_bytes()
        source = source_bytes.decode("utf-8", errors="replace")
        tree = self._parser.parse(source_bytes)
        return ParsedFile(path=path, tree=tree, source=source, source_bytes=source_bytes)
