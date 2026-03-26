"""Tests for filesystem tools."""
import pytest
from pathlib import Path

from java_mcp.tools.filesystem import (
    create_new_file,
    get_file_text_by_path,
    replace_text_in_file,
    list_directory_tree,
    find_files_by_glob,
    find_files_by_name_keyword,
)


@pytest.fixture
def project(tmp_path):
    """Minimal Java project layout."""
    (tmp_path / "src/main/java/com/example").mkdir(parents=True)
    (tmp_path / "src/test/java/com/example").mkdir(parents=True)
    f = tmp_path / "src/main/java/com/example/MyService.java"
    f.write_text('package com.example;\npublic class MyService {\n}\n')
    f2 = tmp_path / "src/main/java/com/example/UserController.java"
    f2.write_text('package com.example;\npublic class UserController {\n    // TODO: implement\n}\n')
    return tmp_path


def test_create_new_file(project):
    result = create_new_file(str(project), "src/main/java/com/example/NewClass.java", "public class NewClass {}")
    assert result.startswith("ok")
    assert (project / "src/main/java/com/example/NewClass.java").read_text() == "public class NewClass {}"


def test_create_new_file_no_overwrite(project):
    create_new_file(str(project), "src/main/java/com/example/NewClass.java", "v1")
    result = create_new_file(str(project), "src/main/java/com/example/NewClass.java", "v2", overwrite=False)
    assert "error" in result
    assert (project / "src/main/java/com/example/NewClass.java").read_text() == "v1"


def test_create_new_file_overwrite(project):
    create_new_file(str(project), "src/main/java/com/example/NewClass.java", "v1")
    result = create_new_file(str(project), "src/main/java/com/example/NewClass.java", "v2", overwrite=True)
    assert result.startswith("ok")
    assert (project / "src/main/java/com/example/NewClass.java").read_text() == "v2"


def test_get_file_text(project):
    text = get_file_text_by_path(str(project), "src/main/java/com/example/MyService.java")
    assert "MyService" in text


def test_get_file_text_not_found(project):
    result = get_file_text_by_path(str(project), "nonexistent.java")
    assert "error" in result


def test_get_file_text_truncate_end(project):
    # Create file with many lines
    lines = "\n".join(f"line {i}" for i in range(100))
    (project / "big.txt").write_text(lines)
    result = get_file_text_by_path(str(project), "big.txt", max_lines=10, truncate_mode="end")
    assert "line 0" in result
    assert "truncated" in result


def test_get_file_text_truncate_start(project):
    lines = "\n".join(f"line {i}" for i in range(100))
    (project / "big.txt").write_text(lines)
    result = get_file_text_by_path(str(project), "big.txt", max_lines=10, truncate_mode="start")
    assert "line 99" in result
    assert "truncated" in result


def test_replace_text_in_file(project):
    result = replace_text_in_file(
        str(project),
        "src/main/java/com/example/MyService.java",
        "MyService",
        "MyUpdatedService",
    )
    assert result == "ok"
    content = (project / "src/main/java/com/example/MyService.java").read_text()
    assert "MyUpdatedService" in content
    assert "MyService" not in content


def test_replace_text_not_found(project):
    result = replace_text_in_file(
        str(project),
        "src/main/java/com/example/MyService.java",
        "NonExistent",
        "Whatever",
    )
    assert result == "no occurrences found"


def test_replace_text_case_insensitive(project):
    result = replace_text_in_file(
        str(project),
        "src/main/java/com/example/MyService.java",
        "myservice",
        "UpdatedService",
        case_sensitive=False,
    )
    assert result == "ok"


def test_list_directory_tree(project):
    tree = list_directory_tree(str(project), "", max_depth=3)
    assert "src" in tree
    assert "main" in tree


def test_find_files_by_glob(project):
    results = find_files_by_glob(str(project), "**/*.java")
    assert len(results) >= 2
    assert all(r.endswith(".java") for r in results)


def test_find_files_by_name_keyword(project):
    results = find_files_by_name_keyword(str(project), "Service")
    assert any("MyService" in r for r in results)
    assert not any("Controller" in r for r in results)


def test_path_traversal_blocked(project):
    result = get_file_text_by_path(str(project), "../../etc/passwd")
    assert "error" in result or "not found" in result
