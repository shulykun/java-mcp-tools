"""Tests for AST-based architecture analysis."""
import pytest
from pathlib import Path


@pytest.fixture
def clean_project(tmp_path):
    """Well-architected project: Controller -> Service -> Repository -> Model."""
    base = tmp_path / "src/main/java/com/example"
    base.mkdir(parents=True)

    (base / "Bike.java").write_text(
        "package com.example;\n"
        "public class Bike { private String model; private BikeStatus status; }\n"
    )
    (base / "BikeStatus.java").write_text(
        "package com.example;\npublic enum BikeStatus { AVAILABLE, RENTED; }\n"
    )
    (base / "BikeDto.java").write_text(
        "package com.example;\npublic class BikeDto { private String model; private BikeStatus status; }\n"
    )
    (base / "BikeRepository.java").write_text(
        "package com.example;\nimport java.util.List;\n"
        "public interface BikeRepository { List<Bike> findAll(); }\n"
    )
    (base / "BikeService.java").write_text(
        "package com.example;\nimport java.util.List;\n"
        "public class BikeService {\n"
        "    private final BikeRepository bikeRepository;\n"
        "    public List<Bike> findAll() { return bikeRepository.findAll(); }\n"
        "}\n"
    )
    (base / "BikeController.java").write_text(
        "package com.example;\nimport java.util.List;\n"
        "public class BikeController {\n"
        "    private final BikeService bikeService;\n"
        "    public List<BikeDto> getAll() { return null; }\n"
        "}\n"
    )
    return tmp_path


@pytest.fixture
def violated_project(tmp_path):
    """Project with architectural violations: DTO calls Repository, Config calls Service."""
    base = tmp_path / "src/main/java/com/example"
    base.mkdir(parents=True)

    (base / "Rental.java").write_text(
        "package com.example;\npublic class Rental { private String id; }\n"
    )
    (base / "RentalRepository.java").write_text(
        "package com.example;\npublic interface RentalRepository { Rental findById(Long id); }\n"
    )
    (base / "RentalService.java").write_text(
        "package com.example;\npublic class RentalService {\n"
        "    private RentalRepository rentalRepository;\n"
        "}\n"
    )
    # VIOLATION: DTO depending on Repository
    (base / "RentalDto.java").write_text(
        "package com.example;\npublic class RentalDto {\n"
        "    private RentalRepository repo;  // violation\n"
        "}\n"
    )
    # VIOLATION: Config calling Service
    (base / "AppConfig.java").write_text(
        "package com.example;\npublic class AppConfig {\n"
        "    private RentalService rentalService;  // violation\n"
        "}\n"
    )
    return tmp_path


# ── get_architecture: layered format ─────────────────────────────────────────

def test_architecture_layered_contains_layers(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="layered")
    assert "Controller" in result
    assert "Service" in result
    assert "Repository" in result


def test_architecture_layered_contains_classes(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="layered")
    assert "BikeController" in result
    assert "BikeService" in result
    assert "BikeRepository" in result


def test_architecture_layered_key_flows(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="layered")
    assert "Ключевые потоки" in result
    assert "BikeController" in result
    assert "BikeService" in result


def test_architecture_layered_enum_detected(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="layered")
    assert "Enum" in result
    assert "BikeStatus" in result


def test_architecture_no_violations_clean_project(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="layered")
    assert "Нарушения" not in result


# ── get_architecture: other formats ──────────────────────────────────────────

def test_architecture_mermaid_format(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="mermaid")
    assert "```mermaid" in result
    assert "graph TD" in result
    assert "subgraph" in result


def test_architecture_json_format(clean_project):
    import json
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="json")
    data = json.loads(result)
    assert "classes" in data
    assert "edges" in data
    assert "violations" in data
    assert "stats" in data
    assert data["stats"]["classes"] > 0


def test_architecture_json_classes_have_layers(clean_project):
    import json
    from java_mcp.tools.architecture import get_architecture
    data = json.loads(get_architecture(str(clean_project), format="json"))
    layers = {c["layer"] for c in data["classes"]}
    assert "Controller" in layers
    assert "Service" in layers
    assert "Repository" in layers


def test_architecture_tree_format(clean_project):
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(str(clean_project), format="tree")
    assert "Граф зависимостей" in result
    assert "BikeService" in result
    assert "Зависит от" in result


# ── get_architecture_violations ───────────────────────────────────────────────

def test_no_violations_clean_project(clean_project):
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(str(clean_project))
    assert violations == []


def test_violations_detected(violated_project):
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(str(violated_project))
    assert len(violations) >= 1


def test_violations_structure(violated_project):
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(str(violated_project))
    for v in violations:
        assert "source" in v
        assert "target" in v
        assert "source_layer" in v
        assert "target_layer" in v
        assert "reason" in v


def test_dto_repository_violation(violated_project):
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(str(violated_project))
    dto_repo = [v for v in violations if v["source_layer"] == "DTO" and v["target_layer"] == "Repository"]
    assert len(dto_repo) >= 1
    assert dto_repo[0]["source"] == "RentalDto"
    assert "DTO" in dto_repo[0]["reason"] or "репозитор" in dto_repo[0]["reason"]


def test_config_service_violation(violated_project):
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(str(violated_project))
    cfg_svc = [v for v in violations if v["source_layer"] == "Config" and v["target_layer"] == "Service"]
    assert len(cfg_svc) >= 1


# ── Integration: bike-rental-service ─────────────────────────────────────────

BIKE = str(Path(__file__).parent.parent.parent / "bike-rental-service")


def test_bike_architecture_layered():
    if not Path(BIKE).exists():
        pytest.skip("bike-rental-service not found")
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(BIKE, format="layered")
    assert "Controller" in result
    assert "Service" in result
    assert "Repository" in result
    assert "RentalService" in result
    assert "BikeController" in result


def test_bike_no_violations():
    if not Path(BIKE).exists():
        pytest.skip("bike-rental-service not found")
    from java_mcp.tools.architecture import get_architecture_violations
    violations = get_architecture_violations(BIKE)
    assert violations == [], f"Unexpected violations: {violations}"


def test_bike_json_has_edges():
    if not Path(BIKE).exists():
        pytest.skip("bike-rental-service not found")
    import json
    from java_mcp.tools.architecture import get_architecture
    data = json.loads(get_architecture(BIKE, format="json"))
    assert data["stats"]["edges"] > 10
    assert data["stats"]["classes"] >= 20


def test_bike_mermaid_has_subgraphs():
    if not Path(BIKE).exists():
        pytest.skip("bike-rental-service not found")
    from java_mcp.tools.architecture import get_architecture
    result = get_architecture(BIKE, format="mermaid")
    assert result.count("subgraph") >= 3  # Controller, Service, Repository at minimum
