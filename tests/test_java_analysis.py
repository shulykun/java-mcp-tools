"""Tests for Java analysis tools (heuristics, rename)."""
import pytest
from java_mcp.tools.java_analysis import get_file_problems, rename_refactoring, get_symbol_info

SAMPLE_JAVA = """\
package com.example;

import java.util.List;

public class MetricReporter {

    public void report(String metricName, double value) {
        System.out.println("Metric: " + metricName);  // line 8
        try {
            doSomething();
        } catch (Exception e) {}  // line 11: empty catch
    }

    private void doSomething() {
        // TODO: implement  // line 15
    }
}
"""


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src/main/java/com/example").mkdir(parents=True)
    (tmp_path / "src/main/java/com/example/MetricReporter.java").write_text(SAMPLE_JAVA)
    (tmp_path / "src/main/java/com/example/MetricFilter.java").write_text(
        'package com.example;\n'
        'public interface MetricFilter {\n'
        '    boolean shouldRecord(String metricName);\n'
        '}\n'
    )
    return tmp_path


# --- get_file_problems ---

def test_get_file_problems_finds_sysout(project):
    problems = get_file_problems(str(project), "src/main/java/com/example/MetricReporter.java")
    descriptions = [p["description"] for p in problems if p.get("source") == "heuristic"]
    assert any("System.out" in d for d in descriptions)


def test_get_file_problems_finds_empty_catch(project):
    problems = get_file_problems(str(project), "src/main/java/com/example/MetricReporter.java")
    descriptions = [p["description"] for p in problems if p.get("source") == "heuristic"]
    assert any("catch" in d.lower() for d in descriptions)


def test_get_file_problems_finds_todo(project):
    problems = get_file_problems(str(project), "src/main/java/com/example/MetricReporter.java")
    descriptions = [p["description"] for p in problems if p.get("source") == "heuristic"]
    assert any("TODO" in d for d in descriptions)


def test_get_file_problems_errors_only(project):
    # With errors_only=True, heuristic warnings should be filtered out
    problems = get_file_problems(
        str(project),
        "src/main/java/com/example/MetricReporter.java",
        errors_only=True,
    )
    for p in problems:
        assert p.get("severity") == "ERROR" or "error" in p


def test_get_file_problems_not_found(project):
    problems = get_file_problems(str(project), "nonexistent.java")
    assert any("error" in str(p) for p in problems)


# --- rename_refactoring ---

def test_rename_refactoring_basic(project):
    result = rename_refactoring(
        str(project),
        "src/main/java/com/example/MetricReporter.java",
        "MetricReporter",
        "MetricsReporter",
    )
    assert result["status"] == "ok"
    assert result["total_replacements"] > 0

    # Check content changed
    content = (project / "src/main/java/com/example/MetricReporter.java").read_text()
    assert "MetricsReporter" in content


def test_rename_refactoring_whole_word_only(project):
    # "metricName" should NOT be renamed when renaming "Metric"
    result = rename_refactoring(
        str(project),
        "src/main/java/com/example/MetricReporter.java",
        "Metric",
        "Measurement",
    )
    content = (project / "src/main/java/com/example/MetricReporter.java").read_text()
    # "metricName" contains "metric" (lowercase) — should NOT be affected by "Metric" rename
    assert "metricName" in content


def test_rename_refactoring_cross_file(project):
    # MetricFilter uses metricName too
    result = rename_refactoring(
        str(project),
        "src/main/java/com/example/MetricFilter.java",
        "metricName",
        "name",
    )
    assert result["status"] == "ok"
    files_changed = [r["file"] for r in result["renamed_files"]]
    # Both files should be updated
    assert any("MetricReporter" in f for f in files_changed)
    assert any("MetricFilter" in f for f in files_changed)


def test_rename_refactoring_not_found(project):
    result = rename_refactoring(
        str(project),
        "src/main/java/com/example/MetricReporter.java",
        "NonExistentSymbol",
        "NewName",
    )
    assert "error" in result


# --- get_symbol_info ---

def test_get_symbol_info_basic(project):
    # Line 7, column 17 is "metricName" parameter
    result = get_symbol_info(
        str(project),
        "src/main/java/com/example/MetricReporter.java",
        line=7,
        column=24,
    )
    assert "name" in result
    assert "file" in result


def test_get_symbol_info_not_found(project):
    result = get_symbol_info(str(project), "nonexistent.java", line=1, column=1)
    assert "error" in result
