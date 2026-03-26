"""
Project structure tools:
  - get_project_modules
  - get_project_dependencies
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project


def get_project_modules(project_path: str) -> list[dict]:
    """
    Discover modules in a Maven/Gradle project.
    Returns list of {name, type, path, build_file}.

    Detection logic:
      1. Find root pom.xml / settings.gradle / settings.gradle.kts
      2. Parse <modules> in Maven or include() in Gradle
      3. For each module dir — detect type (JAVA / ANDROID / UNKNOWN)
    """
    root = resolve_project(project_path)
    modules = []

    # --- Maven ---
    root_pom = root / "pom.xml"
    if root_pom.exists():
        modules.extend(_parse_maven_modules(root, root_pom))
        return modules

    # --- Gradle ---
    for settings_file in ["settings.gradle", "settings.gradle.kts"]:
        settings = root / settings_file
        if settings.exists():
            modules.extend(_parse_gradle_modules(root, settings))
            return modules

    # --- Fallback: single module ---
    module_type = _detect_module_type(root)
    modules.append({
        "name": root.name,
        "type": module_type,
        "path": ".",
        "build_file": _find_build_file(root),
    })
    return modules


def _parse_maven_modules(root: Path, pom_path: Path) -> list[dict]:
    modules = []
    try:
        tree = ET.parse(pom_path)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        xml_root = tree.getroot()

        # Root module itself
        artifact_id = xml_root.findtext("m:artifactId", default=root.name, namespaces=ns)
        modules.append({
            "name": artifact_id,
            "type": _detect_module_type(root),
            "path": ".",
            "build_file": "pom.xml",
        })

        # Sub-modules
        for module_el in xml_root.findall(".//m:modules/m:module", ns):
            module_name = module_el.text.strip()
            module_dir = root / module_name
            modules.append({
                "name": module_name,
                "type": _detect_module_type(module_dir),
                "path": module_name,
                "build_file": f"{module_name}/pom.xml" if (module_dir / "pom.xml").exists() else None,
            })
    except ET.ParseError as e:
        modules.append({"error": f"Failed to parse pom.xml: {e}"})
    return modules


def _parse_gradle_modules(root: Path, settings: Path) -> list[dict]:
    import re
    modules = []
    content = settings.read_text(encoding="utf-8", errors="replace")

    # Root module
    modules.append({
        "name": root.name,
        "type": _detect_module_type(root),
        "path": ".",
        "build_file": _find_build_file(root),
    })

    # include(":module1", ":module2") or include ':module1'
    for m in re.finditer(r"""include\s*[\("']([^"')]+)""", content):
        raw = m.group(1).strip("'\"")
        # Gradle uses : as separator, e.g. ":core" or ":feature:login"
        module_path = raw.lstrip(":").replace(":", "/")
        module_dir = root / module_path
        modules.append({
            "name": raw.lstrip(":"),
            "type": _detect_module_type(module_dir),
            "path": module_path,
            "build_file": _find_build_file(module_dir),
        })

    return modules


def _detect_module_type(module_dir: Path) -> str:
    if not module_dir.exists():
        return "UNKNOWN"
    # Android: has AndroidManifest.xml
    if (module_dir / "src/main/AndroidManifest.xml").exists():
        return "ANDROID"
    # Java: has src/main/java
    if (module_dir / "src/main/java").exists():
        return "JAVA"
    # Kotlin: has src/main/kotlin
    if (module_dir / "src/main/kotlin").exists():
        return "KOTLIN"
    return "UNKNOWN"


def _find_build_file(module_dir: Path) -> Optional[str]:
    for name in ["pom.xml", "build.gradle", "build.gradle.kts"]:
        if (module_dir / name).exists():
            return name
    return None


def get_project_dependencies(project_path: str) -> list[dict]:
    """
    Parse project dependencies from pom.xml or build.gradle.
    Returns list of {group, artifact, version, scope}.
    """
    root = resolve_project(project_path)

    # Maven
    root_pom = root / "pom.xml"
    if root_pom.exists():
        return _parse_maven_deps(root_pom)

    # Gradle
    for build_file in ["build.gradle", "build.gradle.kts"]:
        build = root / build_file
        if build.exists():
            return _parse_gradle_deps(build)

    return [{"error": "No build file found (pom.xml / build.gradle)"}]


def _parse_maven_deps(pom_path: Path) -> list[dict]:
    deps = []
    try:
        tree = ET.parse(pom_path)
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        for dep in tree.getroot().findall(".//m:dependency", ns):
            deps.append({
                "group": dep.findtext("m:groupId", default="", namespaces=ns),
                "artifact": dep.findtext("m:artifactId", default="", namespaces=ns),
                "version": dep.findtext("m:version", default="managed", namespaces=ns),
                "scope": dep.findtext("m:scope", default="compile", namespaces=ns),
            })
    except ET.ParseError as e:
        deps.append({"error": f"Failed to parse pom.xml: {e}"})
    return deps


def _parse_gradle_deps(build_path: Path) -> list[dict]:
    import re
    deps = []
    content = build_path.read_text(encoding="utf-8", errors="replace")

    # Match: implementation("group:artifact:version") or implementation 'group:artifact:version'
    pattern = re.compile(
        r"""(implementation|api|compileOnly|runtimeOnly|testImplementation|annotationProcessor)\s*[\(]?\s*["']([^"']+)["']""",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        scope = m.group(1)
        coords = m.group(2).strip("'\"")
        parts = coords.split(":")
        if len(parts) == 3:
            deps.append({
                "group": parts[0],
                "artifact": parts[1],
                "version": parts[2],
                "scope": scope,
            })
        elif len(parts) == 2:
            deps.append({
                "group": parts[0],
                "artifact": parts[1],
                "version": "managed",
                "scope": scope,
            })

    return deps
