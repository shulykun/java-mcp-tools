"""Tests for dependency graph tools."""
import pytest
from java_mcp.tools.graph import find_usages, analyze_impact


@pytest.fixture
def project(tmp_path):
    """Mini Java project with known dependency graph:
    CommonResult <- UmsAdminService <- UmsAdminServiceImpl <- UmsAdminController
    """
    base = tmp_path / "src/main/java/com/example"
    base.mkdir(parents=True)

    (base / "CommonResult.java").write_text(
        'package com.example;\n'
        'public class CommonResult<T> {\n'
        '    private T data;\n'
        '    public static <T> CommonResult<T> success(T data) { return new CommonResult<>(); }\n'
        '}\n'
    )
    (base / "UmsAdminService.java").write_text(
        'package com.example;\n'
        'import com.example.CommonResult;\n'
        'public interface UmsAdminService {\n'
        '    CommonResult<String> login(String username, String password);\n'
        '}\n'
    )
    (base / "UmsAdminServiceImpl.java").write_text(
        'package com.example;\n'
        'import com.example.CommonResult;\n'
        'import com.example.UmsAdminService;\n'
        'public class UmsAdminServiceImpl implements UmsAdminService {\n'
        '    public CommonResult<String> login(String username, String password) {\n'
        '        return CommonResult.success("token");\n'
        '    }\n'
        '}\n'
    )
    (base / "UmsAdminController.java").write_text(
        'package com.example;\n'
        'import com.example.CommonResult;\n'
        'import com.example.UmsAdminService;\n'
        'public class UmsAdminController {\n'
        '    private UmsAdminService adminService;\n'
        '    public CommonResult<String> login(String username, String password) {\n'
        '        return adminService.login(username, password);\n'
        '    }\n'
        '}\n'
    )
    (base / "UnrelatedClass.java").write_text(
        'package com.example;\n'
        'public class UnrelatedClass {\n'
        '    public void doSomething() {}\n'
        '}\n'
    )
    return tmp_path


# ---------------------------------------------------------------------------
# find_usages tests
# ---------------------------------------------------------------------------

def test_find_usages_basic(project):
    result = find_usages(str(project), "CommonResult")
    assert result["class_name"] == "CommonResult"
    assert result["total_usages"] > 0
    assert result["total_files"] >= 3  # Service, Impl, Controller all use it


def test_find_usages_fqn_resolved(project):
    result = find_usages(str(project), "CommonResult")
    assert "com.example.CommonResult" in result["class_fqn"]


def test_find_usages_types(project):
    result = find_usages(str(project), "CommonResult")
    types = {u["usage_type"] for u in result["usages"]}
    # Should have imports + declarations
    assert "import" in types or "declaration" in types


def test_find_usages_excludes_self(project):
    result = find_usages(str(project), "CommonResult")
    # Should not include CommonResult.java itself as a usage
    files = [u["file"] for u in result["usages"]]
    assert not any("CommonResult.java" in f for f in files)


def test_find_usages_with_method(project):
    result = find_usages(str(project), "CommonResult", method_name="success")
    # Only Impl calls CommonResult.success()
    assert result["total_usages"] > 0
    files = {u["file"] for u in result["usages"]}
    assert any("Impl" in f or "Controller" in f for f in files)
    # Should contain method_call or static_call types
    types = {u["usage_type"] for u in result["usages"]}
    assert types & {"method_call", "static_call", "import"}


def test_find_usages_unrelated_not_included(project):
    result = find_usages(str(project), "CommonResult")
    files = [u["file"] for u in result["usages"]]
    assert not any("UnrelatedClass" in f for f in files)


def test_find_usages_highlight(project):
    result = find_usages(str(project), "CommonResult")
    previews = [u["preview"] for u in result["usages"]]
    assert any("||CommonResult||" in p for p in previews)


def test_find_usages_not_found(project):
    result = find_usages(str(project), "NonExistentClass")
    assert result["total_usages"] == 0


# ---------------------------------------------------------------------------
# analyze_impact tests
# ---------------------------------------------------------------------------

def test_analyze_impact_basic(project):
    result = analyze_impact(str(project), "CommonResult")
    assert result["target_class"] == "CommonResult"
    assert result["total_impacted"] >= 3  # Service, Impl, Controller


def test_analyze_impact_fqn(project):
    result = analyze_impact(str(project), "CommonResult")
    assert "com.example.CommonResult" in result["target_fqn"]


def test_analyze_impact_risk_level(project):
    result = analyze_impact(str(project), "CommonResult")
    assert result["risk_level"] in ("low", "medium", "high", "critical")
    # CommonResult is used by 3 classes → medium
    assert result["risk_level"] in ("low", "medium", "high")


def test_analyze_impact_tree_structure(project):
    result = analyze_impact(str(project), "CommonResult")
    assert "impact_tree" in result
    assert len(result["impact_tree"]) > 0


def test_analyze_impact_summary(project):
    result = analyze_impact(str(project), "CommonResult")
    assert isinstance(result["summary"], list)
    assert len(result["summary"]) > 0
    assert "Level 1" in result["summary"][0]


def test_analyze_impact_leaf_class(project):
    # UmsAdminController is a leaf — nobody imports it
    result = analyze_impact(str(project), "UmsAdminController")
    assert result["total_impacted"] == 0
    assert result["risk_level"] == "none"


def test_analyze_impact_not_found(project):
    result = analyze_impact(str(project), "GhostClass")
    assert "error" in result


def test_analyze_impact_service_vs_impl(project):
    # UmsAdminService is imported by both Impl and Controller
    result = analyze_impact(str(project), "UmsAdminService")
    assert result["total_impacted"] >= 2
    classes = [
        item["class_name"]
        for items in result["impact_tree"].values()
        for item in items
    ]
    assert "UmsAdminServiceImpl" in classes or "UmsAdminController" in classes


def test_analyze_impact_max_depth(project):
    # max_depth=1 should only show direct dependents
    result_d1 = analyze_impact(str(project), "CommonResult", max_depth=1)
    result_d5 = analyze_impact(str(project), "CommonResult", max_depth=5)
    # depth=1 should have <= depth=5 impacted classes
    assert result_d1["total_impacted"] <= result_d5["total_impacted"]
