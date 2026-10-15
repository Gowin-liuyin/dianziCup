"""显式合成security fixtures：证明解析边界，不代表外部扫描或真实资产授权。"""

import builtins
import json
import os
import subprocess
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from ai_intel.assets.manifest_parser import (
    MAX_COMPONENTS,
    MAX_MANIFEST_BYTES,
    MAX_STRING_LENGTH,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.domain.access import AccessScope, Role

FIXTURE_CONTEXT = {
    "manifest_format": "json_manifest_v1",
    "scope": AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.ANALYST),
    "authorized_asset_tenant_id": "fixture-tenant",
    "asset_id": "29a06008-8abf-442f-8645-a4c0f8876469",
    "snapshot_number": 1,
    "source_version": "fixture-revision-1",
    "observed_at": datetime(2026, 10, 15, tzinfo=UTC),
    "recorded_at": datetime(2026, 10, 15, tzinfo=UTC),
}


@pytest.mark.parametrize("field", ["tenant_id", "user_id", "authorization", "skip_validation"])
def test_manifest_cannot_override_authentication(field: str) -> None:
    raw = json.dumps({"format_version": 1, "components": [], field: "attacker-tenant"}).encode()
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code == "unsupported_field"
    assert "attacker-tenant" not in str(error.value)


@pytest.mark.parametrize("secret_key", ["api_key", "password", "access_token", "private_key"])
def test_secret_fields_are_rejected_without_raw_values_in_errors(secret_key: str) -> None:
    raw = json.dumps(
        {
            "format_version": 1,
            "components": [],
            "configuration": {secret_key: "fixture-secret-canary"},
        }
    ).encode()
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code == "unsupported_field"
    assert "fixture-secret-canary" not in str(error.value)


@pytest.mark.parametrize(
    "component",
    [
        {"package_name": "langchain", "scripts": {"install": "fixture-shell-canary"}},
        {"package_name": "langchain", "command": "fixture-shell-canary"},
        {"package_name": "langchain", "symlink": "/fixture/private-file"},
        {"package_name": "../../private"},
        {"package_name": "C:/private"},
        {"package_name": "https://fixture.invalid/manifest"},
        {"package_name": "langchain", "dependency_path": ["../private"]},
        {"package_name": "__import__('os').system('fixture-shell-canary')"},
        {"package_name": "langchain", "purl": "https://fixture.invalid/package"},
        {"package_name": "langchain", "purl": "pkg:pypi/langchain?token=fixture-secret-canary"},
    ],
)
def test_execution_file_and_url_fields_cannot_become_candidates(
    component: dict[str, object],
) -> None:
    raw = json.dumps({"format_version": 1, "components": [component]}).encode()
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code in {"unsupported_field", "invalid_package_name", "unsupported_purl"}
    assert "fixture-shell-canary" not in str(error.value)
    assert "fixture-secret-canary" not in str(error.value)


def test_normal_manifest_parses_with_file_shell_and_url_readers_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden = Mock(side_effect=AssertionError("parser attempted IO"))
    raw = b'{"format_version":1,"components":[{"package_name":"langchain","version":"0.2.0"}]}'
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        patch.setattr(os, "system", forbidden)
        patch.setattr(subprocess, "run", forbidden)
        patch.setattr(urllib.request, "urlopen", forbidden)
        result = parse_manifest(raw, **FIXTURE_CONTEXT)
    assert result.snapshot.components[0].version == "0.2.0"
    forbidden.assert_not_called()
    assert raw.decode() not in repr(result)
    assert "source_bytes=" not in repr(result)


def test_t24_c06_private_path_and_symlink_objects_rejected_without_reading(tmp_path: Path) -> None:
    private_file = tmp_path / "fixture-private.json"
    private_file.write_text("fixture-private-file-canary", encoding="utf-8")
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(private_file, **FIXTURE_CONTEXT)
    assert error.value.code == "bytes_required"
    assert "fixture-private-file-canary" not in str(error.value)


def test_xxe_format_is_unsupported() -> None:
    raw = b'<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///fixture/private">]><x>&secret;</x>'
    context = {**FIXTURE_CONTEXT, "manifest_format": "xml"}
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **context)
    assert error.value.code == "unsupported_format"


@pytest.mark.parametrize(
    "raw", [b"", b"x" * (MAX_MANIFEST_BYTES + 1)], ids=["empty", "above-byte-limit"]
)
def test_manifest_byte_bounds(raw: bytes) -> None:
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code == "manifest_size_limit"


def test_manifest_exact_byte_upper_bound_is_accepted() -> None:
    prefix = b'{"format_version":1,"components":[]}'
    raw = prefix + b" " * (MAX_MANIFEST_BYTES - len(prefix))
    assert len(parse_manifest(raw, **FIXTURE_CONTEXT).source_bytes) == MAX_MANIFEST_BYTES


def test_string_limit_with_normal_pair() -> None:
    raw = json.dumps(
        {
            "format_version": 1,
            "components": [],
            "configuration": {"model_name": "x" * MAX_STRING_LENGTH},
        }
    ).encode()
    assert (
        len(parse_manifest(raw, **FIXTURE_CONTEXT).snapshot.configuration[0].value)
        == MAX_STRING_LENGTH
    )
    invalid = raw.replace(b"x" * MAX_STRING_LENGTH, b"x" * (MAX_STRING_LENGTH + 1))
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(invalid, **FIXTURE_CONTEXT)
    assert error.value.code == "invalid_string"


def test_deep_json_is_rejected_before_unknown_field_processing() -> None:
    raw = b'{"format_version":1,"components":[],"extra":' + b"[" * 17 + b"0" + b"]" * 17 + b"}"
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code == "json_depth_limit"


def test_json_component_count_boundary() -> None:
    components = [{"package_name": f"fixture-package-{index}"} for index in range(MAX_COMPONENTS)]
    raw = json.dumps({"format_version": 1, "components": components}).encode()
    assert len(parse_manifest(raw, **FIXTURE_CONTEXT).snapshot.components) == MAX_COMPONENTS
    components.append({"package_name": "fixture-over-limit"})
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(
            json.dumps({"format_version": 1, "components": components}).encode(), **FIXTURE_CONTEXT
        )
    assert error.value.code == "component_limit"


def test_t24_c05_csv_component_count_boundary() -> None:
    raw = b"Package\n" + b"".join(
        f"fixture-package-{index}\n".encode() for index in range(MAX_COMPONENTS)
    )
    context = {
        **FIXTURE_CONTEXT,
        "manifest_format": "csv_components_v1",
        "csv_column_mapping": {"package_name": "Package"},
    }
    assert len(parse_manifest(raw, **context).snapshot.components) == MAX_COMPONENTS
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw + b"fixture-over-limit\n", **context)
    assert error.value.code == "component_limit"
    assert error.value.locator == "csv:line:10002"


@pytest.mark.parametrize("value", [[], {}, 1, None])
def test_invalid_completeness_types_have_a_controlled_error(value: object) -> None:
    raw = json.dumps(
        {"format_version": 1, "components": [], "inventory_completeness": value}
    ).encode()
    with pytest.raises(ManifestValidationError) as error:
        parse_manifest(raw, **FIXTURE_CONTEXT)
    assert error.value.code == "invalid_inventory_completeness"
