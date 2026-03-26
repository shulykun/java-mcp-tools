"""Tests for search tools."""
import pytest
from java_mcp.tools.search import search_in_files_by_text, search_in_files_by_regex


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/MetricReporter.java").write_text(
        'package com.example;\n'
        'public class MetricReporter {\n'
        '    public void report(String metricName, double value) {\n'
        '        System.out.println("Metric: " + metricName);\n'
        '    }\n'
        '}\n'
    )
    (tmp_path / "src/MetricFilter.java").write_text(
        'package com.example;\n'
        'public interface MetricFilter {\n'
        '    boolean shouldRecord(String metricName);\n'
        '}\n'
    )
    (tmp_path / "target").mkdir()
    (tmp_path / "target/MetricReporter.class").write_bytes(b"\xca\xfe\xba\xbe")  # binary
    return tmp_path


def test_search_by_text_basic(project):
    results = search_in_files_by_text(str(project), "metricName")
    assert len(results) >= 2
    assert all("file" in r and "line" in r and "preview" in r for r in results)


def test_search_by_text_highlight(project):
    results = search_in_files_by_text(str(project), "metricName")
    previews = [r["preview"] for r in results]
    assert any("||metricName||" in p for p in previews)


def test_search_by_text_case_insensitive(project):
    results = search_in_files_by_text(str(project), "METRICNAME", case_sensitive=False)
    assert len(results) >= 2


def test_search_by_text_file_mask(project):
    results = search_in_files_by_text(str(project), "metricName", file_mask="*.java")
    assert all(r["file"].endswith(".java") for r in results)


def test_search_excludes_binary(project):
    results = search_in_files_by_text(str(project), "cafe")
    assert not any(".class" in r["file"] for r in results)


def test_search_excludes_target(project):
    results = search_in_files_by_text(str(project), "MetricReporter")
    assert not any("target" in r["file"] for r in results)


def test_search_by_regex_basic(project):
    # Matches "public class MetricReporter" and "public interface MetricFilter" and "public void report"
    results = search_in_files_by_regex(str(project), r"public\s+\w+")
    assert len(results) >= 2


def test_search_by_regex_highlight(project):
    results = search_in_files_by_regex(str(project), r"MetricFilter")
    previews = [r["preview"] for r in results]
    assert any("||MetricFilter||" in p for p in previews)


def test_search_by_regex_invalid(project):
    results = search_in_files_by_regex(str(project), r"[invalid")
    assert len(results) == 1
    assert "error" in results[0]


def test_search_max_usage_count(project):
    results = search_in_files_by_text(str(project), "com", max_usage_count=1)
    assert len(results) == 1
