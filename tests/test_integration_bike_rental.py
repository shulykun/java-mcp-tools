"""
Integration tests: all tools against real project — bike-rental-service.

Project: Spring Boot e-commerce bike rental
  - 1 Maven module, single-module layout
  - Layers: controller / service / repository / model / dto / exception
  - 43 .java files (main + test)
  - Key classes: RentalService, DiscountService, PricingService, Bike, Rental, Customer
"""
import pytest
from pathlib import Path

# ── helpers ────────────────────────────────────────────────────────────────

BIKE = str(Path(__file__).parent.parent.parent / "bike-rental-service")


def requires_project(func):
    """Skip test if bike-rental-service is not on disk."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not Path(BIKE).exists():
            pytest.skip("bike-rental-service not found")
        return func(*args, **kwargs)

    return wrapper


# ── project info ────────────────────────────────────────────────────────────

@requires_project
def test_project_modules_single():
    from java_mcp.tools.project_info import get_project_modules
    mods = get_project_modules(BIKE)
    assert len(mods) == 1
    assert mods[0]["name"] == "bike-rental-service"
    assert mods[0]["type"] == "JAVA"
    assert mods[0]["build_file"] == "pom.xml"


@requires_project
def test_project_dependencies_count():
    from java_mcp.tools.project_info import get_project_dependencies
    deps = get_project_dependencies(BIKE)
    assert len(deps) >= 8
    artifacts = [d["artifact"] for d in deps]
    assert "spring-boot-starter-web" in artifacts
    assert "spring-boot-starter-data-jpa" in artifacts
    assert "h2" in artifacts  # test DB
    assert "lombok" in artifacts


@requires_project
def test_project_dependencies_scopes():
    from java_mcp.tools.project_info import get_project_dependencies
    deps = get_project_dependencies(BIKE)
    scopes = {d["scope"] for d in deps}
    assert "compile" in scopes
    assert "test" in scopes


# ── filesystem ──────────────────────────────────────────────────────────────

@requires_project
def test_java_file_count():
    from java_mcp.tools.filesystem import find_files_by_glob
    files = find_files_by_glob(BIKE, "**/*.java", file_count_limit=500)
    assert len(files) == 43


@requires_project
def test_main_vs_test_split():
    from java_mcp.tools.filesystem import find_files_by_glob
    all_files = find_files_by_glob(BIKE, "**/*.java", file_count_limit=500)
    main = [f for f in all_files if "src/main" in f]
    test = [f for f in all_files if "src/test" in f]
    assert len(main) == 39
    assert len(test) == 4


@requires_project
def test_directory_tree_structure():
    from java_mcp.tools.filesystem import list_directory_tree
    tree = list_directory_tree(BIKE, "", max_depth=3)
    assert "src" in tree
    assert "main" in tree
    assert "test" in tree
    assert "pom.xml" in tree
    # target/ should be excluded
    assert "target" not in tree


@requires_project
def test_find_service_files():
    from java_mcp.tools.filesystem import find_files_by_name_keyword
    services = find_files_by_name_keyword(BIKE, "Service.java")
    names = [Path(f).name for f in services]
    assert "RentalService.java" in names
    assert "DiscountService.java" in names
    assert "PricingService.java" in names
    assert "BikeService.java" in names
    assert "CustomerService.java" in names


@requires_project
def test_read_rental_service():
    from java_mcp.tools.filesystem import get_file_text_by_path
    content = get_file_text_by_path(
        BIKE,
        "src/main/java/com/bikerental/service/RentalService.java",
    )
    assert "startRental" in content
    assert "returnBike" in content
    assert "@Transactional" in content
    assert "@Service" in content


@requires_project
def test_read_file_truncation():
    from java_mcp.tools.filesystem import get_file_text_by_path
    # RentalService is large — truncate to 10 lines
    content = get_file_text_by_path(
        BIKE,
        "src/main/java/com/bikerental/service/RentalService.java",
        max_lines=10,
        truncate_mode="end",
    )
    assert "truncated" in content
    lines = content.splitlines()
    # 10 content lines + 1 truncation notice
    assert len(lines) <= 12


@requires_project
def test_replace_and_restore(tmp_path):
    """Write a temp file, replace text, verify, restore."""
    from java_mcp.tools.filesystem import create_new_file, replace_text_in_file, get_file_text_by_path
    proj = str(tmp_path)
    create_new_file(proj, "Test.java", "public class TestClass { String name = \"bike\"; }")
    result = replace_text_in_file(proj, "Test.java", "bike", "scooter")
    assert result == "ok"
    content = get_file_text_by_path(proj, "Test.java")
    assert "scooter" in content
    assert "bike" not in content


# ── search ──────────────────────────────────────────────────────────────────

@requires_project
def test_search_annotations():
    from java_mcp.tools.search import search_in_files_by_text
    for ann, expected_min in [("@Service", 5), ("@RestController", 4), ("@Repository", 4), ("@Transactional", 20)]:
        r = search_in_files_by_text(BIKE, ann, file_mask="*.java", max_usage_count=100)
        assert len(r) >= expected_min, f"{ann} expected >= {expected_min}, got {len(r)}"


@requires_project
def test_search_no_system_out():
    from java_mcp.tools.search import search_in_files_by_text
    r = search_in_files_by_text(BIKE, "System.out", file_mask="*.java")
    assert len(r) == 0, "Clean code: no System.out in production code"


@requires_project
def test_search_no_todo():
    from java_mcp.tools.search import search_in_files_by_regex
    r = search_in_files_by_regex(BIKE, r"(TODO|FIXME|HACK)", file_mask="*.java")
    assert len(r) == 0, "No TODO/FIXME left in bike-rental code"


@requires_project
def test_search_highlight_format():
    from java_mcp.tools.search import search_in_files_by_text
    r = search_in_files_by_text(BIKE, "RentalService", file_mask="*.java", max_usage_count=5)
    assert all("||RentalService||" in u["preview"] for u in r)


@requires_project
def test_search_regex_transactional_methods():
    from java_mcp.tools.search import search_in_files_by_regex
    # Find methods annotated with @Transactional
    r = search_in_files_by_regex(BIKE, r"@Transactional", file_mask="*.java", max_usage_count=100)
    assert len(r) >= 20
    files = {u["file"] for u in r}
    # Only service layer should have @Transactional
    assert all("service" in f.lower() for f in files)


@requires_project
def test_search_exception_classes():
    from java_mcp.tools.filesystem import find_files_by_glob
    exceptions = find_files_by_glob(BIKE, "**/*Exception.java", file_count_limit=20)
    assert len(exceptions) == 3
    names = [Path(f).name for f in exceptions]
    assert "BikeNotAvailableException.java" in names
    assert "CustomerNotEligibleException.java" in names
    assert "ResourceNotFoundException.java" in names


@requires_project
def test_search_discount_logic():
    from java_mcp.tools.search import search_in_files_by_regex
    # Discount applied on every 5th rental — find the magic number
    r = search_in_files_by_regex(BIKE, r"\b5\b", file_mask="*.java", max_usage_count=50)
    files = [u["file"] for u in r]
    assert any("Discount" in f for f in files)


# ── graph: find_usages ──────────────────────────────────────────────────────

@requires_project
def test_find_usages_rental_class():
    from java_mcp.tools.graph import find_usages
    r = find_usages(BIKE, "Rental", max_results=100)
    assert r["class_fqn"] == "com.bikerental.model.Rental"
    assert r["total_files"] >= 4  # Repository, PricingService, RentalService, tests
    types = {u["usage_type"] for u in r["usages"]}
    assert "import" in types
    assert "declaration" in types


@requires_project
def test_find_usages_bike_class():
    from java_mcp.tools.graph import find_usages
    r = find_usages(BIKE, "Bike", max_results=100)
    assert "com.bikerental.model.Bike" in r["class_fqn"]
    assert r["total_files"] >= 3


@requires_project
def test_find_usages_discount_service_apply():
    from java_mcp.tools.graph import find_usages
    r = find_usages(BIKE, "DiscountService", method_name="applyDiscount", max_results=20)
    # applyDiscount is called in RentalService + DiscountServiceTest
    assert r["total_usages"] >= 2
    files = [u["file"] for u in r["usages"]]
    assert any("RentalService" in f for f in files)
    types = {u["usage_type"] for u in r["usages"]}
    assert "method_call" in types


@requires_project
def test_find_usages_rental_service_start():
    from java_mcp.tools.graph import find_usages
    r = find_usages(BIKE, "RentalService", method_name="startRental", max_results=20)
    # Called in controller + tests
    assert r["total_usages"] >= 3
    files = [u["file"] for u in r["usages"]]
    assert any("Controller" in f for f in files)
    assert any("Test" in f for f in files)


@requires_project
def test_find_usages_excludes_self():
    from java_mcp.tools.graph import find_usages
    r = find_usages(BIKE, "RentalService", max_results=50)
    files = [u["file"] for u in r["usages"]]
    assert not any(f.endswith("RentalService.java") for f in files)


# ── graph: analyze_impact ───────────────────────────────────────────────────

@requires_project
def test_impact_rental_model():
    from java_mcp.tools.graph import analyze_impact
    r = analyze_impact(BIKE, "Rental")
    assert r["target_fqn"] == "com.bikerental.model.Rental"
    assert r["total_impacted"] >= 5
    assert r["risk_level"] in ("medium", "high")
    assert isinstance(r["summary"], list)
    assert len(r["summary"]) > 0


@requires_project
def test_impact_bike_model():
    from java_mcp.tools.graph import analyze_impact
    r = analyze_impact(BIKE, "Bike")
    assert r["total_impacted"] >= 4
    assert r["risk_level"] in ("low", "medium", "high")


@requires_project
def test_impact_discount_service_is_leaf():
    from java_mcp.tools.graph import analyze_impact
    # DiscountService is used by RentalService only via injection, not import-based
    r = analyze_impact(BIKE, "DiscountService")
    # Graph-based impact may be 0 (injection without import graph edge)
    # or 1+ if import is present — either is acceptable
    assert r["risk_level"] in ("none", "low", "medium")


@requires_project
def test_impact_controller_is_leaf():
    from java_mcp.tools.graph import analyze_impact
    # Controllers are endpoints — nobody should import them
    r = analyze_impact(BIKE, "RentalController")
    assert r["total_impacted"] == 0
    assert r["risk_level"] == "none"


@requires_project
def test_impact_depth_1_vs_5():
    from java_mcp.tools.graph import analyze_impact
    r1 = analyze_impact(BIKE, "Rental", max_depth=1)
    r5 = analyze_impact(BIKE, "Rental", max_depth=5)
    # Deeper search finds more or equal classes
    assert r5["total_impacted"] >= r1["total_impacted"]


@requires_project
def test_impact_summary_format():
    from java_mcp.tools.graph import analyze_impact
    r = analyze_impact(BIKE, "Rental")
    for line in r["summary"]:
        assert line.startswith("Level ")
        assert "direct users" in line or "indirect" in line


@requires_project
def test_impact_not_found():
    from java_mcp.tools.graph import analyze_impact
    r = analyze_impact(BIKE, "GhostBike")
    assert "error" in r


# ── java analysis ────────────────────────────────────────────────────────────

@requires_project
def test_get_symbol_info_in_pricing_service():
    from java_mcp.tools.java_analysis import get_symbol_info
    from java_mcp.tools.filesystem import get_file_text_by_path
    # Find "calculatePrice" in PricingService
    content = get_file_text_by_path(BIKE, "src/main/java/com/bikerental/service/PricingService.java")
    lines = content.splitlines()
    target_line = next((i + 1 for i, l in enumerate(lines) if "calculateBaseAmount" in l), None)
    assert target_line is not None

    r = get_symbol_info(BIKE, "src/main/java/com/bikerental/service/PricingService.java",
                        line=target_line, column=10)
    assert "name" in r
    assert "file" in r


@requires_project
def test_get_file_problems_heuristics_in_blog():
    """BlogService has println — should trigger heuristic warning."""
    from java_mcp.tools.java_analysis import get_file_problems
    from java_mcp.tools.search import search_in_files_by_text
    # First check if any file has System.out
    r = search_in_files_by_text(BIKE, "System.out", file_mask="*.java")
    if not r:
        pytest.skip("No System.out found in project")
    # Check heuristic fires on that file
    file_path = r[0]["file"]
    problems = get_file_problems(BIKE, file_path)
    heuristic = [p for p in problems if p.get("source") == "heuristic"]
    assert len(heuristic) > 0
