"""
Build/run tool:
  - execute_run_configuration

Supports Maven and Gradle goals/tasks.
"""
import subprocess
from pathlib import Path
from typing import Optional

from java_mcp.project import resolve_project

# Built-in run configuration presets
_MAVEN_PRESETS = {
    "test": ["mvn", "test"],
    "build": ["mvn", "package", "-DskipTests"],
    "clean": ["mvn", "clean"],
    "install": ["mvn", "install"],
    "verify": ["mvn", "verify"],
}

_GRADLE_PRESETS = {
    "test": ["./gradlew", "test"],
    "build": ["./gradlew", "build", "-x", "test"],
    "clean": ["./gradlew", "clean"],
    "check": ["./gradlew", "check"],
}


def execute_run_configuration(
    project_path: str,
    configuration_name: str,
    timeout: int = 120_000,
    max_lines_count: int = 500,
    truncate_mode: str = "end",
) -> dict:
    """
    Execute a named run configuration.

    Supported formats:
      - Preset names: "test", "build", "clean", etc.
      - Raw Maven goal: "mvn test -pl metrics-module"
      - Raw Gradle task: "gradle bootRun"
      - Arbitrary shell command: "java -jar target/app.jar"

    Returns: {exit_code, output, success}
    """
    root = resolve_project(project_path)

    cmd = _resolve_command(root, configuration_name)

    timeout_sec = timeout / 1000  # convert ms → seconds

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(root),
            shell=isinstance(cmd, str),
        )
        output = _merge_output(result.stdout, result.stderr)
        output = _truncate(output, max_lines_count, truncate_mode)

        return {
            "exit_code": result.returncode,
            "output": output,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "output": f"Timed out after {timeout_sec:.0f}s",
            "success": False,
        }
    except FileNotFoundError as e:
        return {
            "exit_code": -1,
            "output": f"Command not found: {e}",
            "success": False,
        }


def _resolve_command(root: Path, name: str):
    """Map configuration name → command list."""
    name_lower = name.lower().strip()

    # Check Maven presets
    if name_lower in _MAVEN_PRESETS and (root / "pom.xml").exists():
        return _MAVEN_PRESETS[name_lower]

    # Check Gradle presets
    if name_lower in _GRADLE_PRESETS:
        gradle_wrapper = root / "gradlew"
        if gradle_wrapper.exists():
            return _GRADLE_PRESETS[name_lower]

    # Raw command string — pass to shell
    return name


def _merge_output(stdout: str, stderr: str) -> str:
    parts = []
    if stdout.strip():
        parts.append(stdout)
    if stderr.strip():
        parts.append(stderr)
    return "\n".join(parts)


def _truncate(text: str, max_lines: int, mode: str) -> str:
    lines = text.splitlines(keepends=True)
    if len(lines) <= max_lines:
        return text

    if mode == "start":
        return f"[truncated {len(lines) - max_lines} lines]\n" + "".join(lines[-max_lines:])
    elif mode == "middle":
        half = max_lines // 2
        omitted = len(lines) - max_lines
        return "".join(lines[:half]) + f"\n[... {omitted} lines omitted ...]\n" + "".join(lines[-half:])
    else:  # end
        return "".join(lines[:max_lines]) + f"\n[truncated {len(lines) - max_lines} lines]"
