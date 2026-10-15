"""显式合成unit fixtures：纯候选解析不代表真实资产、导入或研判成功。"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from ai_intel.assets.manifest_parser import (
    ManifestParseResult,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role

ASSET_ID = "29a06008-8abf-442f-8645-a4c0f8876469"
OBSERVED_AT = datetime(2026, 10, 15, 12, tzinfo=UTC)
FIXTURE_SCOPE = AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.ANALYST)


def parse_fixture(raw: bytes, **overrides: object) -> ManifestParseResult:
    arguments = {
        "manifest_format": "json_manifest_v1",
        "scope": FIXTURE_SCOPE,
        "authorized_asset_tenant_id": "fixture-tenant",
        "asset_id": ASSET_ID,
        "snapshot_number": 1,
        "source_version": "fixture-manifest-revision-1",
        "observed_at": OBSERVED_AT,
        "recorded_at": OBSERVED_AT,
    }
    arguments.update(overrides)
    return parse_manifest(raw, **arguments)


def manifest_fixture(components: list[dict[str, object]], **fields: object) -> bytes:
    return json.dumps({"format_version": 1, "components": components, **fields}).encode()


def test_t24_c01_json_csv_equivalent_candidates_retain_separate_provenance() -> None:
    json_bytes = manifest_fixture(
        [{"ecosystem": "PyPI", "package_name": "langchain", "version": "0.2.0"}]
    )
    csv_bytes = b"Package,Ecosystem,Version\r\nlangchain,PyPI,0.2.0\r\n"
    json_result = parse_fixture(json_bytes)
    csv_result = parse_fixture(
        csv_bytes,
        manifest_format="csv_components_v1",
        csv_column_mapping={
            "package_name": "Package",
            "ecosystem": "Ecosystem",
            "version": "Version",
        },
    )
    assert json_result.snapshot.snapshot_sha256 == csv_result.snapshot.snapshot_sha256
    assert json_result.snapshot.snapshot_id == csv_result.snapshot.snapshot_id
    assert json_result.source_sha256 != csv_result.source_sha256
    assert json_result.source_bytes == json_bytes
    assert json_result.source_version == "fixture-manifest-revision-1"
    assert json_result.snapshot.components[0].source_field_locator == "/components/0"
    assert csv_result.snapshot.components[0].source_field_locator == "csv:line:2"


def test_t24_c02_deterministic_replay_without_storage_or_reminders() -> None:
    raw = manifest_fixture([{"package_name": "langchain"}])
    assert parse_fixture(raw) == parse_fixture(raw)


def test_concurrent_candidate_parsing_has_no_shared_mutable_state() -> None:
    raw = manifest_fixture([{"package_name": "langchain", "version": "0.2.0"}])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = tuple(executor.map(parse_fixture, [raw] * 16))
    assert all(result == results[0] for result in results)


def test_t24_c03_version_change_creates_new_candidate_keeps_old_value() -> None:
    old = parse_fixture(manifest_fixture([{"package_name": "langchain", "version": "0.2.0"}]))
    new = parse_fixture(
        manifest_fixture([{"package_name": "langchain", "version": "0.2.1"}]), snapshot_number=2
    )
    assert old.snapshot.components[0].version == "0.2.0"
    assert new.snapshot.components[0].version == "0.2.1"
    assert old.snapshot.snapshot_id != new.snapshot.snapshot_id
    assert old.snapshot.snapshot_sha256 != new.snapshot.snapshot_sha256


@pytest.mark.parametrize("completeness", ["partial", "unknown"])
def test_t24_c04_partial_inventory_does_not_create_absence_or_default_configuration(
    completeness: str,
) -> None:
    result = parse_fixture(manifest_fixture([], inventory_completeness=completeness))
    assert result.snapshot.inventory_completeness == completeness
    assert result.snapshot.components == ()
    assert result.snapshot.configuration == ()
    assert result.snapshot.tool_permissions is None
    assert result.snapshot.input_channels is None
    assert result.snapshot.network_exposure is None


def test_unknown_component_fields_and_display_identity_are_separate() -> None:
    result = parse_fixture(
        manifest_fixture([{"package_name": "langchain", "display_name": "Friendly AI service"}])
    )
    component = result.snapshot.components[0]
    assert component.package_name == "langchain"
    assert component.display_name == "Friendly AI service"
    assert component.ecosystem == "unknown"
    assert component.version is None
    assert component.version_scheme == "unknown"
    assert component.purl is None


def test_purl_never_fills_unknown_identity_or_missing_version() -> None:
    result = parse_fixture(
        manifest_fixture([{"package_name": "langchain", "purl": "pkg:pypi/langchain@0.2.0"}])
    )
    component = result.snapshot.components[0]
    assert component.ecosystem == "unknown"
    assert component.version is None
    assert component.purl == "pkg:pypi/langchain@0.2.0"


def test_configuration_values_and_explicit_empty_permissions_are_preserved() -> None:
    result = parse_fixture(
        manifest_fixture(
            [{"package_name": "vllm"}],
            configuration={"model_name": "fixture/model", "trust_remote_code": False},
            tool_permissions=[],
            input_channels={"uploaded_documents": True},
            network_exposure={"public_endpoint": None},
        )
    )
    assert [(field.name, field.value) for field in result.snapshot.configuration] == [
        ("model_name", "fixture/model"),
        ("trust_remote_code", False),
    ]
    assert result.snapshot.tool_permissions == ()
    assert result.snapshot.input_channels[0].value is True
    assert result.snapshot.network_exposure[0].value is None


def test_conflicting_versions_preserved_with_both_field_locations() -> None:
    result = parse_fixture(
        manifest_fixture(
            [
                {"ecosystem": "PyPI", "package_name": "langchain", "version": "0.2.0"},
                {"ecosystem": "PyPI", "package_name": "langchain", "version": "0.2.1"},
            ]
        )
    )
    assert [component.version for component in result.snapshot.components] == ["0.2.0", "0.2.1"]
    assert [(issue.code, issue.locators) for issue in result.issues] == [
        ("conflicting_component_versions", ("/components/0", "/components/1"))
    ]


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b'{"format_version":1,"components":[],"components":[]}', "invalid_json"),
        (b'{"format_version":1,"components":[],"extra":NaN}', "invalid_json"),
        (b"\xff", "invalid_encoding"),
        (b"[]", "invalid_json"),
        (manifest_fixture([{"package_name": "langchain", "version": 12}]), "invalid_field_type"),
        (manifest_fixture([{}]), "missing_package_name"),
        (
            manifest_fixture([], inventory_completeness="complete_for_declared_scope"),
            "missing_declared_scope",
        ),
        (
            manifest_fixture(
                [{"package_name": "langchain", "ecosystem": "PyPI", "version_scheme": "semver"}]
            ),
            "conflicting_version_scheme",
        ),
        (manifest_fixture([], configuration={"trust_remote_code": "false"}), "invalid_field_type"),
        (manifest_fixture([], tool_permissions=["read", "read"]), "duplicate_value"),
    ],
)
def test_invalid_inputs_return_fixed_reason_without_partial_success(raw: bytes, code: str) -> None:
    with pytest.raises(ManifestValidationError) as error:
        parse_fixture(raw)
    assert error.value.code == code


@pytest.mark.parametrize(
    "raw",
    [
        b"Package,Version\nlangchain,1,extra\n",
        b"Package,Version\nlangchain\n",
        b'Package,Version\n"langchain,1\n',
        b"Package,Package\nlangchain,1\n",
    ],
)
def test_t24_c05_csv_invalid_rows_fail_with_line_locator(raw: bytes) -> None:
    with pytest.raises(ManifestValidationError) as error:
        parse_fixture(
            raw,
            manifest_format="csv_components_v1",
            csv_column_mapping={"package_name": "Package", "version": "Version"},
        )
    assert error.value.code in {"invalid_csv", "invalid_csv_columns"}
    assert error.value.locator.startswith("csv:line:")


def test_csv_blank_values_remain_unknown() -> None:
    result = parse_fixture(
        b"Package,Ecosystem,Version\nlangchain,,\n",
        manifest_format="csv_components_v1",
        csv_column_mapping={
            "package_name": "Package",
            "ecosystem": "Ecosystem",
            "version": "Version",
        },
    )
    assert result.snapshot.components[0].ecosystem == "unknown"
    assert result.snapshot.components[0].version is None


def test_t24_c06_cross_tenant_rejected_before_invalid_body_parse() -> None:
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        parse_fixture(b"invalid", authorized_asset_tenant_id="other-tenant")


def test_viewer_without_asset_permission_is_denied() -> None:
    viewer = AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        parse_fixture(b"invalid", scope=viewer)


def test_context_without_tenant_is_denied() -> None:
    unscoped = AccessScope.for_authenticated_user("fixture-user", None, Role.ANALYST)
    with pytest.raises(PermissionDeniedError):
        parse_fixture(b"invalid", scope=unscoped)


@pytest.mark.parametrize(
    "manifest_format", ["cyclonedx_json", "spdx_json", "xml", "requirements_txt"]
)
def test_unsupported_formats_fail_explicitly(manifest_format: str) -> None:
    with pytest.raises(ManifestValidationError) as error:
        parse_fixture(b"invalid", manifest_format=manifest_format)
    assert error.value.code == "unsupported_format"
