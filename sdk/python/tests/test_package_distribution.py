"""Check actual local distributions and fresh installed interpreters, without product access."""

from __future__ import annotations

import configparser
import hashlib
import json
import os
import subprocess
import tarfile
import time
import tomllib
import zipfile
from datetime import UTC, datetime
from email.parser import BytesParser
from pathlib import Path

import pytest
from packaging.requirements import Requirement

SDK = Path(__file__).resolve().parents[1]
PACKAGE_FILES = {
    "__init__.py",
    "cli.py",
    "client.py",
    "models.py",
    "mcp_adapter.py",
    "mcp_stdio.py",
    "output_budget.py",
    "py.typed",
}
DIST_INFO = "ai_intel_client-0.1.0.dist-info"
EGG_INFO = "ai_intel_client.egg-info"
METADATA_FILES = {
    "PKG-INFO",
    "SOURCES.txt",
    "dependency_links.txt",
    "entry_points.txt",
    "requires.txt",
    "top_level.txt",
}


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} must point to actual built/installed packaging evidence")
    return Path(value)


def _wheel() -> Path:
    return _required_path("SDK_PACKAGE_DIST_DIR") / "ai_intel_client-0.1.0-py3-none-any.whl"


def _sdist() -> Path:
    return _required_path("SDK_PACKAGE_DIST_DIR") / "ai_intel_client-0.1.0.tar.gz"


def _installed_command(
    label: str,
    name: str,
    arguments: list[str],
    *,
    expected_exit: int = 0,
) -> subprocess.CompletedProcess[bytes]:
    interpreter = _required_path(f"SDK_PACKAGE_{label.upper()}_PYTHON")
    working_directory = interpreter.parents[2]
    environment = os.environ.copy()
    for variable in tuple(environment):
        if variable.startswith(("DIANZI_", "SDK_PACKAGE_")) or variable == "PYTHONPATH":
            environment.pop(variable)
    output_directory = _required_path("SDK_TEST_EVIDENCE_DIR") / "package_installations"
    output_directory.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat()
    start_clock = time.monotonic()
    result = subprocess.run(
        arguments,
        cwd=working_directory,
        env=environment,
        capture_output=True,
        timeout=30,
        check=False,
    )
    prefix = output_directory / f"{label}_{name}"
    prefix.with_suffix(".stdout.log").write_bytes(result.stdout)
    prefix.with_suffix(".stderr.log").write_bytes(result.stderr)
    prefix.with_suffix(".command.json").write_text(
        json.dumps(
            {
                "arguments": arguments,
                "cwd": str(working_directory),
                "started_at": started,
                "ended_at": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - start_clock,
                "exit_code": result.returncode,
                "timeout_seconds": 30,
                "product_requests": 0,
                "environment_policy": (
                    "parent sanitized allowlist, minus DIANZI_/SDK_PACKAGE_/PYTHONPATH"
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert result.returncode == expected_exit, result.stderr.decode("utf-8", errors="replace")
    return result


def test_metadata_declaration_has_only_current_cli_and_optional_transport() -> None:
    metadata = tomllib.loads((SDK / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["name"] == "ai-intel-client"
    assert metadata["project"]["version"] == "0.1.0"
    assert metadata["project"]["requires-python"] == ">=3.12,<3.13"
    assert metadata["project"]["scripts"] == {"dianzi-intel": "ai_intel_client.cli:main"}
    assert metadata["project"]["dependencies"] == ["httpx>=0.28,<1", "pydantic>=2.10,<3"]
    assert metadata["project"]["optional-dependencies"] == {
        "mcp": ["mcp==2.3.0", "tiktoken==0.14.0"],
    }


def test_wheel_metadata_is_compatible_with_frozen_dependency_lock() -> None:
    with zipfile.ZipFile(_wheel()) as archive:
        metadata = BytesParser().parsebytes(archive.read(f"{DIST_INFO}/METADATA"))
    assert metadata["Name"] == "ai-intel-client"
    assert metadata["Version"] == "0.1.0"
    assert metadata["Requires-Python"] == "<3.13,>=3.12"
    assert metadata["License-Expression"] == "Apache-2.0"
    assert metadata.get_all("License-File") == ["LICENSE"]
    assert metadata.get_all("Provides-Extra") == ["mcp"]
    requirements = [Requirement(value) for value in metadata.get_all("Requires-Dist", [])]
    assert {item.name for item in requirements if item.marker is None} == {"httpx", "pydantic"}
    assert {item.name for item in requirements if item.marker is not None} == {"mcp", "tiktoken"}
    frozen_lock = tomllib.loads((SDK.parents[1] / "backend/uv.lock").read_text(encoding="utf-8"))
    versions = {item["name"]: item["version"] for item in frozen_lock["package"]}
    for requirement in requirements:
        assert versions[requirement.name] in requirement.specifier
        if requirement.marker is not None:
            assert not requirement.marker.evaluate({"extra": ""})
            assert requirement.marker.evaluate({"extra": "mcp"})


def test_wheel_entrypoint_targets_existing_callable() -> None:
    with zipfile.ZipFile(_wheel()) as archive:
        parser = configparser.ConfigParser()
        parser.read_string(archive.read(f"{DIST_INFO}/entry_points.txt").decode())
    assert parser.sections() == ["console_scripts"]
    assert dict(parser["console_scripts"]) == {"dianzi-intel": "ai_intel_client.cli:main"}
    from ai_intel_client.cli import main

    assert callable(main)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_archives_exactly_exclude_tests_secrets_holdout_and_caches(kind: str) -> None:
    sources = {f"ai_intel_client/{name}" for name in PACKAGE_FILES}
    if kind == "wheel":
        with zipfile.ZipFile(_wheel()) as archive:
            members = archive.namelist()
            actual = set(members)
            assert len(actual) == len(members)
            assert sum(item.file_size for item in archive.infolist()) < 256 * 1024
        expected = sources | {
            f"{DIST_INFO}/{name}"
            for name in (
                "METADATA",
                "WHEEL",
                "entry_points.txt",
                "top_level.txt",
                "RECORD",
                "licenses/LICENSE",
            )
        }
    else:
        with tarfile.open(_sdist()) as archive:
            members = archive.getmembers()
            assert all(item.isdir() or item.isfile() for item in members)
            actual = {
                item.name.removeprefix("ai_intel_client-0.1.0/")
                for item in members
                if item.isfile()
            }
            assert len(actual) == sum(item.isfile() for item in members)
            assert sum(item.size for item in members) < 256 * 1024
        expected = sources | {
            "LICENSE",
            "README.md",
            "pyproject.toml",
            "MANIFEST.in",
            "PKG-INFO",
            "setup.cfg",
        }
        expected |= {f"{EGG_INFO}/{name}" for name in METADATA_FILES}
    assert actual == expected
    assert all(not name.startswith("/") and ".." not in Path(name).parts for name in actual)
    forbidden = {"tests", "benchmarks", "holdout", ".env", ".venv", "__pycache__", "reports"}
    assert all(not forbidden.intersection(Path(name).parts) for name in actual)


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_distribution_sources_license_and_type_marker_are_byte_identical(kind: str) -> None:
    if kind == "wheel":
        with zipfile.ZipFile(_wheel()) as archive:
            for name in PACKAGE_FILES:
                assert (
                    archive.read(f"ai_intel_client/{name}")
                    == (SDK / "ai_intel_client" / name).read_bytes()
                )
            license_bytes = archive.read(f"{DIST_INFO}/licenses/LICENSE")
    else:
        with tarfile.open(_sdist()) as archive:
            for name in PACKAGE_FILES:
                member = archive.extractfile(f"ai_intel_client-0.1.0/ai_intel_client/{name}")
                assert member is not None
                assert member.read() == (SDK / "ai_intel_client" / name).read_bytes()
            license_member = archive.extractfile("ai_intel_client-0.1.0/LICENSE")
            assert license_member is not None
            license_bytes = license_member.read()
    assert license_bytes == (SDK / "LICENSE").read_bytes()
    assert b"Apache License" in license_bytes and b"Version 2.0, January 2004" in license_bytes
    assert (SDK / "ai_intel_client/py.typed").is_file()


def test_sdist_rebuilt_wheel_matches_direct_wheel() -> None:
    rebuilt = _required_path("SDK_PACKAGE_REBUILT_DIR") / _wheel().name
    assert (
        hashlib.sha256(rebuilt.read_bytes()).digest()
        == hashlib.sha256(_wheel().read_bytes()).digest()
    )


@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_build_rejects_unrelated_synthetic_files_from_distribution(kind: str) -> None:
    canary_directory = _required_path("SDK_PACKAGE_CANARY_DIST_DIR")
    sentinel = b"SYNTHETIC_PACKAGE_EXCLUDED_SENTINEL"
    if kind == "wheel":
        with (
            zipfile.ZipFile(canary_directory / _wheel().name) as archive,
            zipfile.ZipFile(_wheel()) as original,
        ):
            assert archive.namelist() == original.namelist()
            assert all(sentinel not in archive.read(name) for name in archive.namelist())
    else:
        with tarfile.open(canary_directory / _sdist().name) as archive:
            for item in archive.getmembers():
                assert item.isdir() or item.isfile()
                if item.isfile():
                    member = archive.extractfile(item)
                    assert member is not None
                    assert sentinel not in member.read()
                    assert not {"tests", "holdout", "benchmarks", "__pycache__"}.intersection(
                        Path(item.name).parts
                    )


@pytest.mark.parametrize("label", ["wheel", "sdist"])
def test_clean_install_imports_typed_exports_without_optional_transport(label: str) -> None:
    interpreter = _required_path(f"SDK_PACKAGE_{label.upper()}_PYTHON")
    script = """
import importlib.metadata as metadata
import importlib.util
import inspect
import json
import pathlib
import sys
import ai_intel_client
from ai_intel_client import AskRequest, AskResult, StackCheckRequest, StackCheckResult, DianziClient
from ai_intel_client.models import (
    Citation, Component, NormalizedIntel, Vulnerability, Advisory, Enrichment, Relation, QAAnswer,
)
expected = {
    'AskRequest', 'AskResult', 'DianziApiError', 'DianziClient', 'DianziTransportError',
    'StackCheckRequest', 'StackCheckResult',
}
assert set(ai_intel_client.__all__) == expected
assert metadata.version('ai-intel-client') == '0.1.0'
package = pathlib.Path(ai_intel_client.__file__).resolve()
assert package.is_relative_to(pathlib.Path(sys.prefix).resolve())
assert sys.prefix != sys.base_prefix
venv_config = (pathlib.Path(sys.prefix) / 'pyvenv.cfg').read_text()
assert 'include-system-site-packages = false' in venv_config
assert (package.parent / 'py.typed').is_file()
public_types = (
    Citation, Component, NormalizedIntel, Vulnerability, Advisory, Enrichment, Relation, QAAnswer,
)
assert all(inspect.isclass(value) for value in public_types)
assert inspect.iscoroutinefunction(DianziClient.ask_async)
assert inspect.iscoroutinefunction(DianziClient.check_stack_async)
assert inspect.iscoroutinefunction(DianziClient.aclose)
assert importlib.util.find_spec('mcp') is None
assert importlib.util.find_spec('tiktoken') is None
installed = {
    distribution.metadata['Name'].lower().replace('_', '-'): distribution.version
    for distribution in metadata.distributions()
}
expected_distributions = {
    'pip', 'ai-intel-client', 'annotated-types', 'anyio', 'certifi', 'h11', 'httpcore', 'httpx',
    'idna', 'pydantic', 'pydantic-core', 'typing-extensions', 'typing-inspection',
}
assert set(installed) == expected_distributions, installed
print(json.dumps({
    'version': metadata.version('ai-intel-client'), 'package': str(package), 'prefix': sys.prefix,
    'installed': installed, 'exports': sorted(expected),
}))
"""
    result = _installed_command(label, "typed_imports", [str(interpreter), "-I", "-c", script])
    observation = json.loads(result.stdout)
    assert observation["version"] == "0.1.0"


@pytest.mark.parametrize("label", ["wheel", "sdist"])
def test_installed_console_launcher_help_and_safe_configuration_failure(label: str) -> None:
    interpreter = _required_path(f"SDK_PACKAGE_{label.upper()}_PYTHON")
    executable = interpreter.parent / ("dianzi-intel.exe" if os.name == "nt" else "dianzi-intel")
    assert executable.is_file()
    help_result = _installed_command(label, "cli_help", [str(executable), "--help"])
    assert b"dianzi-intel" in help_result.stdout
    assert b"check" in help_result.stdout and b"ask" in help_result.stdout
    assert help_result.stderr == b""
    failure = _installed_command(
        label, "cli_not_configured", [str(executable), "check"], expected_exit=3
    )
    assert failure.stdout == b""
    assert b"could not be completed" in failure.stderr
    version_flag = _installed_command(
        label, "cli_version_boundary", [str(executable), "--version"], expected_exit=3
    )
    assert version_flag.stdout == b""
    assert b"could not be completed" in version_flag.stderr
