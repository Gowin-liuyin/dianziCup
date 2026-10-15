"""Synthetic, isolated independent review inputs; no secrets, network or real assets."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime, timedelta, timezone, tzinfo

import pytest

from ai_intel.assets.manifest_parser import ManifestValidationError, parse_manifest
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role

CONTEXT = {
    "manifest_format": "json_manifest_v1",
    "scope": AccessScope.for_authenticated_user("review-user", "review-tenant", Role.ANALYST),
    "authorized_asset_tenant_id": "review-tenant",
    "asset_id": "b3c1d42e-cf57-4d16-b8c6-6c62158d7e0e",
    "snapshot_number": 3,
    "source_version": "review-only-source-3",
    "observed_at": datetime(2026, 10, 15, 21, tzinfo=timezone(timedelta(hours=8))),
    "recorded_at": datetime(2026, 10, 15, 22, tzinfo=timezone(timedelta(hours=8))),
}


def parse(raw, **changes):
    return parse_manifest(raw, **{**CONTEXT, **changes})


def manifest(components=None, **changes):
    return json.dumps({"format_version": 1, "components": components or [], **changes}).encode()


def test_complete_legal_manifest_preserves_untrusted_source_and_fields():
    raw = manifest(
        [{"package_name": "@scope/llm-tool", "ecosystem": "npm", "display_name": "Review UI",
          "purl": "pkg:npm/%40scope/llm-tool@1.9.0", "version": "1.9.0", "version_scheme": "semver",
          "image_digest": "sha256:" + "0" * 64, "dependency_path": ["app", "@scope/llm-tool"]}],
        inventory_completeness="complete_for_declared_scope", declared_scope=["review-runtime"],
        configuration={"model_name": "review/model", "provider_name": "review-provider", "trust_remote_code": False, "authentication_required": None},
        tool_permissions=["read:inventory"], input_channels={"public_api": False, "retrieved_web_content": None},
        network_exposure={"outbound_network_allowed": False, "public_endpoint": None},
    )
    result = parse(raw)
    assert result.snapshot.tenant_id == "review-tenant"
    assert result.snapshot.components[0].ecosystem == "npm"
    assert result.snapshot.components[0].version_scheme == "semver"
    assert result.snapshot.components[0].package_name == "@scope/llm-tool"
    assert result.snapshot.components[0].display_name == "Review UI"
    assert result.snapshot.observed_at == datetime(2026, 10, 15, 13, tzinfo=UTC)
    assert result.snapshot.recorded_at == datetime(2026, 10, 15, 14, tzinfo=UTC)
    assert result.snapshot.inventory_completeness == "complete_for_declared_scope"
    assert result.source_bytes == raw
    assert asdict(result)["source_bytes"] == raw
    assert "source_bytes" not in asdict(result.snapshot)


def test_quoted_csv_json_pair_reaches_same_business_identity():
    json_result = parse(manifest([{"package_name": "langchain", "ecosystem": "PyPI", "version": "1.10.0", "display_name": "Friendly, AI"}]))
    csv_result = parse(b'Name,Kind,Ver,Label\r\n"langchain","PyPI","1.10.0","Friendly, AI"\r\n', manifest_format="csv_components_v1", csv_column_mapping={"package_name": "Name", "ecosystem": "Kind", "version": "Ver", "display_name": "Label"})
    assert json_result.snapshot.snapshot_sha256 == csv_result.snapshot.snapshot_sha256
    assert json_result.snapshot.snapshot_id == csv_result.snapshot.snapshot_id
    assert json_result.source_sha256 != csv_result.source_sha256


@pytest.mark.parametrize("field", ["tenant_id", "user_id", "permissions", "command", "url", "file_path", "scripts", "api_key"], ids=lambda field: field)
def test_unapproved_top_fields_do_not_enter_candidate(field):
    with pytest.raises(ManifestValidationError) as caught:
        parse(manifest(**{field: "review-canary"}))
    assert caught.value.code == "unsupported_field"
    assert "review-canary" not in str(caught.value)


@pytest.mark.parametrize("field", ["api_key", "password", "private_key", "access_token"])
def test_nested_secret_field_cannot_be_retained(field):
    with pytest.raises(ManifestValidationError) as caught:
        parse(manifest(configuration={field: "review-canary"}))
    assert caught.value.code == "unsupported_field"
    assert "review-canary" not in str(caught.value)


@pytest.mark.parametrize("value", ["/private", "../private", "C:/private", "https://review.invalid", "__import__('os')"])
def test_package_path_and_command_boundary(value):
    with pytest.raises(ManifestValidationError) as caught:
        parse(manifest([{"package_name": value}]))
    assert caught.value.code == "invalid_package_name"


def test_cross_tenant_rejected_before_error_body():
    with pytest.raises(CrossTenantAccessError):
        parse(b"not-json", authorized_asset_tenant_id="other-review-tenant")


@pytest.mark.parametrize("role", [Role.VIEWER, Role.ANALYST])
def test_no_tenant_scope_denied_for_roles(role):
    with pytest.raises(PermissionDeniedError):
        parse(manifest(), scope=AccessScope.for_authenticated_user("review-user", None, role))


def test_unknown_permission_set_differs_from_explicit_empty():
    unknown = parse(manifest())
    empty = parse(manifest(tool_permissions=[]))
    assert unknown.snapshot.tool_permissions is None
    assert empty.snapshot.tool_permissions == ()
    assert unknown.snapshot.snapshot_sha256 != empty.snapshot.snapshot_sha256


def test_configuration_missing_and_null_remain_distinct_from_false():
    missing = parse(manifest()).snapshot.configuration
    null = parse(manifest(configuration={"trust_remote_code": None})).snapshot.configuration
    explicit_false = parse(manifest(configuration={"trust_remote_code": False})).snapshot.configuration
    assert missing == ()
    assert null[0].value is None
    assert explicit_false[0].value is False


def test_component_and_declared_scope_reorder_does_not_change_hash():
    first = parse(manifest([{"package_name": "langchain"}, {"package_name": "vllm"}], declared_scope=["runtime", "build"]))
    second = parse(manifest([{"package_name": "vllm"}, {"package_name": "langchain"}], declared_scope=["build", "runtime"]))
    assert first.snapshot.snapshot_sha256 == second.snapshot.snapshot_sha256
    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id
    assert first.source_sha256 != second.source_sha256


def test_duplicate_identity_is_rejected_but_conflicting_version_is_retained():
    with pytest.raises(ManifestValidationError) as caught:
        parse(manifest([{"package_name": "vllm", "version": "0.1.0"}] * 2))
    assert caught.value.code == "duplicate_component"
    conflict = parse(manifest([{"package_name": "vllm", "version": "0.1.0"}, {"package_name": "vllm", "version": "0.2.0"}]))
    assert len(conflict.snapshot.components) == 2
    assert conflict.issues[0].locators == ("/components/0", "/components/1")


def test_purl_is_label_and_never_fills_explicit_identity():
    result = parse(manifest([{"package_name": "langchain", "purl": "pkg:npm/unrelated@9.9.9"}]))
    component = result.snapshot.components[0]
    assert component.ecosystem == "unknown"
    assert component.version is None
    assert component.package_name == "langchain"
    assert component.purl == "pkg:npm/unrelated@9.9.9"


@pytest.mark.parametrize("raw", [b'{"format_version":1,"components":[],"format_version":1}', b'{"format_version":1,"components":[],"configuration":{"model_name":NaN}}', b'{"format_version":1,"components":[],"x":' + b'[' * 33 + b'0' + b']' * 33 + b'}'], ids=["duplicate", "nan", "deep"])
def test_duplicate_nan_and_deep_input_are_rejected(raw):
    with pytest.raises(ManifestValidationError):
        parse(raw)


@pytest.mark.parametrize("raw", [b'Name,Ver\n"langchain,1\n', b"Name,Ver\nlangchain,1,extra\n", b"Name,Name\nlangchain,1\n"], ids=["unclosed-quote", "extra-cell", "duplicate-header"])
def test_existing_csv_invalid_cases_are_rejected(raw):
    with pytest.raises(ManifestValidationError) as caught:
        parse(raw, manifest_format="csv_components_v1", csv_column_mapping={"package_name": "Name", "version": "Ver"})
    assert caught.value.code in {"invalid_csv", "invalid_csv_columns"}
    assert caught.value.locator.startswith("csv:line:")


def test_exact_raw_replay_is_deterministic_in_parallel():
    raw = manifest([{"package_name": "langchain", "version": "1.10.0"}])
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(parse, [raw] * 24))
    assert all(result == results[0] for result in results)


def test_permission_reorder_keeps_same_semantic_hash():
    first = parse(manifest(tool_permissions=["read:inventory", "read:evidence"]))
    second = parse(manifest(tool_permissions=["read:evidence", "read:inventory"]))
    assert set(first.snapshot.tool_permissions) == set(second.snapshot.tool_permissions)
    assert first.snapshot.snapshot_sha256 == second.snapshot.snapshot_sha256
    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id


def test_unquoted_csv_quote_is_rejected_as_malformed_record():
    with pytest.raises(ManifestValidationError) as caught:
        parse(b'Name,Ver\nlangchain,1"2\n', manifest_format="csv_components_v1", csv_column_mapping={"package_name": "Name", "version": "Ver"})
    assert caught.value.code == "invalid_csv"
    assert caught.value.locator == "csv:line:2"


def test_timezone_conversion_overflow_has_controlled_validation_error():
    with pytest.raises(ManifestValidationError):
        parse(manifest(), observed_at=datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14))))


class MissingOffsetZone(tzinfo):
    def utcoffset(self, value):
        return None

    def dst(self, value):
        return None


def test_tzinfo_without_offset_does_not_count_as_aware_input():
    timestamp = datetime(2026, 10, 15, 12, tzinfo=MissingOffsetZone())
    assert timestamp.utcoffset() is None
    with pytest.raises(ManifestValidationError) as caught:
        parse(manifest(), observed_at=timestamp)
    assert caught.value.code == "timezone_required"
