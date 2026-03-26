"""Tests for project info tools."""
import pytest
from java_mcp.tools.project_info import get_project_modules, get_project_dependencies

SAMPLE_POM = """\
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>my-app</artifactId>
  <version>1.0.0</version>
  <packaging>pom</packaging>
  <modules>
    <module>core</module>
    <module>api</module>
  </modules>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>3.2.0</version>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
"""

SAMPLE_BUILD_GRADLE = """\
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.2.0'
}
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web:3.2.0")
    implementation 'com.fasterxml.jackson.core:jackson-databind:2.16.0'
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.0")
    compileOnly("org.projectlombok:lombok:1.18.30")
}
"""

SAMPLE_SETTINGS_GRADLE = """\
rootProject.name = 'my-app'
include ':core'
include ':api'
include ':feature:login'
"""


@pytest.fixture
def maven_project(tmp_path):
    (tmp_path / "pom.xml").write_text(SAMPLE_POM)
    (tmp_path / "core/src/main/java").mkdir(parents=True)
    (tmp_path / "core/pom.xml").write_text("<project/>")
    (tmp_path / "api/src/main/java").mkdir(parents=True)
    (tmp_path / "api/pom.xml").write_text("<project/>")
    return tmp_path


@pytest.fixture
def gradle_project(tmp_path):
    (tmp_path / "settings.gradle").write_text(SAMPLE_SETTINGS_GRADLE)
    (tmp_path / "build.gradle").write_text(SAMPLE_BUILD_GRADLE)
    (tmp_path / "core/src/main/java").mkdir(parents=True)
    (tmp_path / "api/src/main/java").mkdir(parents=True)
    return tmp_path


# --- Maven tests ---

def test_maven_modules(maven_project):
    modules = get_project_modules(str(maven_project))
    names = [m["name"] for m in modules]
    assert "my-app" in names
    assert "core" in names
    assert "api" in names


def test_maven_module_types(maven_project):
    modules = get_project_modules(str(maven_project))
    by_name = {m["name"]: m for m in modules}
    assert by_name["core"]["type"] == "JAVA"
    assert by_name["api"]["type"] == "JAVA"


def test_maven_dependencies(maven_project):
    deps = get_project_dependencies(str(maven_project))
    artifacts = [d["artifact"] for d in deps]
    assert "spring-boot-starter-web" in artifacts
    assert "junit-jupiter" in artifacts


def test_maven_dependency_scope(maven_project):
    deps = get_project_dependencies(str(maven_project))
    junit = next(d for d in deps if d["artifact"] == "junit-jupiter")
    assert junit["scope"] == "test"


# --- Gradle tests ---

def test_gradle_modules(gradle_project):
    modules = get_project_modules(str(gradle_project))
    names = [m["name"] for m in modules]
    assert "core" in names
    assert "api" in names


def test_gradle_nested_module(gradle_project):
    (gradle_project / "feature/login/src/main/java").mkdir(parents=True)
    modules = get_project_modules(str(gradle_project))
    names = [m["name"] for m in modules]
    assert "feature:login" in names


def test_gradle_dependencies(gradle_project):
    deps = get_project_dependencies(str(gradle_project))
    artifacts = [d["artifact"] for d in deps]
    assert "spring-boot-starter-web" in artifacts
    assert "junit-jupiter" in artifacts
    assert "lombok" in artifacts


def test_gradle_dependency_scope(gradle_project):
    deps = get_project_dependencies(str(gradle_project))
    lombok = next(d for d in deps if d["artifact"] == "lombok")
    assert lombok["scope"] == "compileOnly"


# --- Fallback ---

def test_no_build_file(tmp_path):
    result = get_project_dependencies(str(tmp_path))
    assert any("error" in str(r) for r in result)
