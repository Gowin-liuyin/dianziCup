"""恶意清单拒绝及无文件/网络执行；不连接第三方资产。"""

import json
import socket

import pytest
from tests.unit.test_r11_sbom_parser import ASSET_ID, NOW, SCOPE, cdx_document, parse, spdx_document

from ai_intel.assets.sbom_parser import SbomValidationError, parse_sbom
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"<bom>&xxe;</bom>",
        b'{"bomFormat":"CycloneDX","bomFormat":"CycloneDX"}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b'{"x":"\\ud800"}',
        b'{"x":"\\u0000"}',
        b"\xff",
    ],
    ids=[
        "empty_object",
        "xml_entities",
        "duplicate_keys",
        "nan",
        "infinity",
        "overflow_float",
        "surrogate",
        "nul",
        "encoding",
    ],
)
def test_malformed_source_never_returns_empty_default_success(raw):
    with pytest.raises(SbomValidationError):
        parse(raw)


@pytest.mark.parametrize(
    "version", [[], {}, True, 1.7], ids=["list", "object", "boolean", "number"]
)
def test_invalid_version_types_are_typed_not_unhandled_errors(version):
    with pytest.raises(SbomValidationError) as rejected:
        parse(cdx_document(version))
    assert rejected.value.code == "unsupported_sbom_version"


@pytest.mark.parametrize(
    "field,value",
    [
        ("$ref", "https://untrusted.invalid/secret-marker"),
        ("tenant_id", "forged-tenant"),
        ("server_path", "C:/private/secret-marker"),
        ("password", "secret-marker"),
    ],
)
def test_identity_paths_and_schema_references_cannot_execute_or_echo_input(field, value):
    document = cdx_document(**{field: value})
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert value not in str(rejected.value)


def test_private_download_uri_and_namespaces_are_inert_data(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    document = spdx_document()
    document["documentNamespace"] = "https://127.0.0.1/private/secret-marker"
    document["packages"][0]["downloadLocation"] = "file:///C:/private/secret-marker"
    result = parse(document, "spdx_json")
    assert len(result.manifest.snapshot.components) == 1
    assert b"secret-marker" in result.manifest.source_bytes


@pytest.mark.parametrize(
    "scope",
    [
        AccessScope.for_authenticated_user("viewer", "synthetic-tenant", Role.VIEWER),
        AccessScope.for_authenticated_user("global", None, Role.SYSTEM_ADMIN),
    ],
)
def test_scope_is_enforced_before_parsing(scope):
    with pytest.raises(PermissionDeniedError):
        parse_sbom(
            b"malformed",
            sbom_format="cyclonedx_json",
            scope=scope,
            authorized_asset_tenant_id="synthetic-tenant",
            asset_id=ASSET_ID,
            snapshot_number=1,
            source_version="synthetic",
            observed_at=NOW,
            recorded_at=NOW,
        )


def test_cross_tenant_scope_is_not_trusted_from_document():
    with pytest.raises(CrossTenantAccessError):
        parse_sbom(
            json.dumps(cdx_document()).encode(),
            sbom_format="cyclonedx_json",
            scope=SCOPE,
            authorized_asset_tenant_id="other-tenant",
            asset_id=ASSET_ID,
            snapshot_number=1,
            source_version="synthetic",
            observed_at=NOW,
            recorded_at=NOW,
        )


@pytest.mark.parametrize(
    "raw",
    ["C:/private/file.json", bytearray(b"{}"), b"x" * 1048577],
    ids=["server_path", "mutable_bytes", "too_large"],
)
def test_bytes_only_and_exact_upload_limit(raw):
    with pytest.raises(SbomValidationError) as rejected:
        parse_sbom(
            raw,
            sbom_format="cyclonedx_json",
            scope=SCOPE,
            authorized_asset_tenant_id=SCOPE.tenant_id,
            asset_id=ASSET_ID,
            snapshot_number=1,
            source_version="synthetic",
            observed_at=NOW,
            recorded_at=NOW,
        )
    assert rejected.value.code == "sbom_size_or_type_limit"


def test_exact_one_mib_input_is_accepted_and_not_truncated():
    raw = json.dumps(cdx_document()).encode()
    raw += b" " * (1048576 - len(raw))
    assert parse(raw).manifest.source_bytes == raw


def test_depth_limit_is_independent_of_component_count():
    document = cdx_document()
    value = "leaf"
    for _ in range(17):
        value = [value]
    document["annotations"] = value
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.code == "json_depth_limit"


@pytest.mark.parametrize("sentinel", ["NONE", "NOASSERTION"])
def test_spdx_unknown_sentinels_cannot_resolve_cdx_dependencies(sentinel):
    document = cdx_document(dependencies=[{"ref": "component-a", "dependsOn": [sentinel]}])
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.code == "unresolved_reference"


@pytest.mark.parametrize("field", ["source", "documentDescribes"])
def test_unknown_spdx_sentinel_does_not_forge_local_reference(field):
    document = spdx_document()
    if field == "source":
        document["relationships"] = [
            {
                "spdxElementId": "NOASSERTION",
                "relatedSpdxElement": "SPDXRef-A",
                "relationshipType": "DEPENDS_ON",
            }
        ]
    else:
        document["documentDescribes"] = ["NONE"]
    with pytest.raises(SbomValidationError) as rejected:
        parse(document, "spdx_json")
    assert rejected.value.code == "unresolved_reference"


@pytest.mark.parametrize(
    "failure", ["length", "algorithm", "conflict", "duplicate_ref", "unresolved"]
)
def test_checksum_and_reference_inconsistencies_are_typed_with_source_location(failure):
    document = spdx_document()
    expected = "/packages/0/checksums/0"
    if failure == "duplicate_ref":
        document["packages"].append(dict(document["packages"][0]))
        expected = "/packages/1/SPDXID"
    elif failure == "unresolved":
        document["relationships"] = [
            {
                "spdxElementId": "SPDXRef-A",
                "relatedSpdxElement": "SPDXRef-Missing",
                "relationshipType": "DEPENDS_ON",
            }
        ]
        expected = "/relationships/0/relatedSpdxElement"
    else:
        checksum = {"algorithm": "SHA256", "checksumValue": "a" * 64}
        if failure == "length":
            checksum["checksumValue"] = "a" * 63
        elif failure == "algorithm":
            checksum["algorithm"] = "made-up"
        document["packages"][0]["checksums"] = [checksum]
        if failure == "conflict":
            document["packages"][0]["checksums"].append(
                {"algorithm": "SHA256", "checksumValue": "b" * 64}
            )
            expected = "/packages/0/checksums/1"
    with pytest.raises(SbomValidationError) as rejected:
        parse(document, "spdx_json")
    assert rejected.value.locator == expected


def test_raw_node_budget_rejects_dense_opaque_data_without_truncation():
    document = cdx_document()
    document["opaque"] = [0] * 200000
    raw = json.dumps(document).encode()
    assert len(raw) < 1048576
    with pytest.raises(SbomValidationError) as rejected:
        parse(raw)
    assert rejected.value.code == "json_node_limit"
