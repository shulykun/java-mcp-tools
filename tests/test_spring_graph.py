"""Tests for Spring injection graph tools."""
import pytest
from pathlib import Path


@pytest.fixture
def project(tmp_path):
    """
    Dependency chain:
      DiscountService (no injections)
          ↑ @RequiredArgsConstructor
      RentalService (injects DiscountService, PricingService)
          ↑ @Autowired
      RentalController (injects RentalService)

    PricingService (no injections)
          ↑ private final in RentalService
    """
    base = tmp_path / "src/main/java/com/example"
    base.mkdir(parents=True)

    (base / "DiscountService.java").write_text(
        "package com.example;\n"
        "import org.springframework.stereotype.Service;\n"
        "@Service\n"
        "public class DiscountService {\n"
        "    public boolean isApplicable(Long id) { return false; }\n"
        "}\n"
    )
    (base / "PricingService.java").write_text(
        "package com.example;\n"
        "import org.springframework.stereotype.Service;\n"
        "@Service\n"
        "public class PricingService {\n"
        "    public double calculate() { return 0.0; }\n"
        "}\n"
    )
    (base / "RentalService.java").write_text(
        "package com.example;\n"
        "import com.example.DiscountService;\n"
        "import com.example.PricingService;\n"
        "import lombok.RequiredArgsConstructor;\n"
        "import org.springframework.stereotype.Service;\n"
        "@Service\n"
        "@RequiredArgsConstructor\n"
        "public class RentalService {\n"
        "    private final DiscountService discountService;\n"
        "    private final PricingService pricingService;\n"
        "    public void start() {\n"
        "        discountService.isApplicable(1L);\n"
        "        pricingService.calculate();\n"
        "    }\n"
        "}\n"
    )
    (base / "RentalController.java").write_text(
        "package com.example;\n"
        "import com.example.RentalService;\n"
        "import org.springframework.beans.factory.annotation.Autowired;\n"
        "import org.springframework.web.bind.annotation.RestController;\n"
        "@RestController\n"
        "public class RentalController {\n"
        "    @Autowired\n"
        "    private RentalService rentalService;\n"
        "    public void rent() { rentalService.start(); }\n"
        "}\n"
    )
    # Class with @Inject (javax)
    (base / "ReportService.java").write_text(
        "package com.example;\n"
        "import com.example.PricingService;\n"
        "import javax.inject.Inject;\n"
        "public class ReportService {\n"
        "    @Inject\n"
        "    private PricingService pricingService;\n"
        "}\n"
    )
    return tmp_path


# ── find_spring_dependencies: specific class ──────────────────────────────

def test_rental_service_injections(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "RentalService")
    assert r["class_name"] == "RentalService"
    types = [f["type_name"] for f in r["injections"]]
    assert "DiscountService" in types
    assert "PricingService" in types


def test_rental_service_injection_type_lombok(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "RentalService")
    for inj in r["injections"]:
        assert inj["injection_type"] == "lombok_constructor"


def test_rental_controller_autowired(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "RentalController")
    assert len(r["injections"]) == 1
    assert r["injections"][0]["type_name"] == "RentalService"
    assert r["injections"][0]["injection_type"] == "autowired"
    assert r["injections"][0]["field_name"] == "rentalService"


def test_inject_annotation(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "ReportService")
    assert len(r["injections"]) == 1
    assert r["injections"][0]["injection_type"] == "inject"


def test_discount_service_no_injections(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "DiscountService")
    assert r["injections"] == []


def test_injected_by_discount_service(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "DiscountService")
    injectors = [i["class"] for i in r["injected_by"]]
    assert "RentalService" in injectors


def test_injected_by_pricing_service(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "PricingService")
    injectors = [i["class"] for i in r["injected_by"]]
    assert "RentalService" in injectors
    assert "ReportService" in injectors


def test_summary_format(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "RentalService")
    assert isinstance(r["summary"], list)
    assert len(r["summary"]) == 2
    assert "depends on" in r["summary"][0]
    assert "injected into" in r["summary"][1]


def test_not_found_class(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project), "GhostService")
    assert r["injections"] == []
    assert r["injected_by"] == []


# ── find_spring_dependencies: full graph ──────────────────────────────────

def test_full_graph_returns_all(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project))
    # Classes with injections: RentalService, RentalController, ReportService
    assert r["total_classes_with_injections"] >= 3
    class_names = [e["class"] for e in r["graph"]]
    assert "RentalService" in class_names
    assert "RentalController" in class_names


def test_full_graph_no_injections_excluded(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project))
    class_names = [e["class"] for e in r["graph"]]
    # DiscountService has no injections — should NOT appear
    assert "DiscountService" not in class_names


def test_full_graph_edge_format(project):
    from java_mcp.tools.spring_graph import find_spring_dependencies
    r = find_spring_dependencies(str(project))
    rental = next(e for e in r["graph"] if e["class"] == "RentalService")
    assert "dependencies" in rental
    for dep in rental["dependencies"]:
        assert "type" in dep
        assert "field" in dep
        assert "via" in dep


# ── analyze_spring_impact ─────────────────────────────────────────────────

def test_spring_impact_discount_service(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "DiscountService")
    # DiscountService is injected into RentalService
    assert r["total_impacted"] >= 1
    classes = [
        item["class_name"]
        for items in r["impact_tree"].values()
        for item in items
    ]
    assert "RentalService" in classes


def test_spring_impact_shows_injection_edge(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "DiscountService")
    # The edge from DiscountService -> RentalService should be marked as injection
    depth1 = r["impact_tree"].get("depth_1", [])
    rental = next((i for i in depth1 if i["class_name"] == "RentalService"), None)
    assert rental is not None
    assert "injection" in rental["edge_type"]


def test_spring_impact_more_than_import_only(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    from java_mcp.tools.graph import analyze_impact
    # DiscountService is NOT imported by RentalService (only injected via @RequiredArgsConstructor)
    # So import-only impact should be 0, spring impact should be > 0
    import_r = analyze_impact(str(project), "DiscountService")
    spring_r = analyze_spring_impact(str(project), "DiscountService")
    assert spring_r["total_impacted"] >= import_r["total_impacted"]


def test_spring_impact_injection_edges_added(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "DiscountService")
    assert r["injection_edges_added"] > 0


def test_spring_impact_risk_level(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "DiscountService")
    assert r["risk_level"] in ("low", "medium", "high", "critical", "none")


def test_spring_impact_not_found(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "Ghost")
    assert "error" in r


def test_spring_impact_controller_still_leaf(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "RentalController")
    assert r["total_impacted"] == 0
    assert r["risk_level"] == "none"


def test_spring_impact_summary_labels_injection(project):
    from java_mcp.tools.spring_graph import analyze_spring_impact
    r = analyze_spring_impact(str(project), "DiscountService")
    # RentalService should appear in summary with injection label
    summary_text = " ".join(r["summary"])
    assert "RentalService" in summary_text
