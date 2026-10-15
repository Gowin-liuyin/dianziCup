"""展示URI边界不得修改原始SBOM、checksum或完整语义摘要。"""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from ai_intel.assets.sbom_inventory import (
    SbomProjectionValidationError,
    _safe_http_uri,
    freeze_sbom_sidecar,
    parse_inventory_input,
    safe_sbom_sidecar,
)
from ai_intel.domain.access import AccessScope, Role


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql://synthetic_user:synthetic_password@db.internal:5432/private",
        "file:///C:/private/synthetic-parent",
        "https://synthetic_user:synthetic_password@example.test/sbom",
    ],
    ids=["connection_uri", "file_uri", "userinfo_uri"],
)
def test_original_privacy_must_external_document_uri_is_not_returned(uri):
    raw = json.dumps(
        {
            "spdxVersion": "SPDX-2.3",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "synthetic",
            "documentNamespace": "https://example.test/sbom",
            "dataLicense": "CC0-1.0",
            "creationInfo": {"created": "2026-10-16T00:00:00Z", "creators": ["Tool: synthetic"]},
            "packages": [
                {
                    "SPDXID": "SPDXRef-A",
                    "name": "a",
                    "versionInfo": "1",
                    "downloadLocation": "NOASSERTION",
                }
            ],
            "externalDocumentRefs": [
                {
                    "externalDocumentId": "DocumentRef-external",
                    "spdxDocument": uri,
                    "checksum": {"algorithm": "SHA256", "checksumValue": "c" * 64},
                }
            ],
        },
        separators=(",", ":"),
    ).encode()
    now = datetime(2026, 10, 16, 0, tzinfo=UTC)
    result = parse_inventory_input(
        raw,
        manifest_format="spdx_json",
        scope=AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN),
        authorized_asset_tenant_id="tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-privacy",
        observed_at=now,
        recorded_at=now,
    )
    assert result.sbom is not None
    public = freeze_sbom_sidecar(result.sbom)
    assert uri not in public.model_dump_json()
    assert public.external_documents[0].document_ref == "DocumentRef-external"
    assert public.external_documents[0].checksum.checksum_value == "c" * 64
    assert result.manifest.source_bytes == raw
    assert public.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert public.combined_semantic_sha256 == result.sbom.combined_semantic_sha256
    assert public.schema_version == "r11-sbom-sidecar-2"
    assert public.external_documents[0].document_uri is None
    assert public.redactions[0].reason == "unsafe_uri_or_path"


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.test/external",
        "http://www.example.com/docs",
        "https://8.8.8.8/sbom",
        "https://[2606:4700:4700::1111]/bom",
    ],
)
def test_public_document_uri_is_not_fetched_or_removed(uri, monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("URI projection must remain offline")

    monkeypatch.setattr("socket.getaddrinfo", network_forbidden)
    assert _safe_http_uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "https://example.test/sbom?token=synthetic-password",
        "https://example.test/sbom#synthetic-password",
        "https://example.test/sbom?",
        "https://%73ynthetic-user@example.test/sbom",
        "https://example.test/%253A%252F%252Fprivate",
        "https://localhost/sbom",
        "https://localhost.localdomain/sbom",
        "https://db.internal/sbom",
        "https://db.local/sbom",
        "http://127.0.0.1/sbom",
        "http://127.1/sbom",
        "http://10.1.2.3/sbom",
        "https://[::1]/sbom",
        "https://[fd00::1]/sbom",
        "https://example.test\\@private/sbom",
        "javascript:synthetic",
        "ftp://example.test/sbom",
    ],
    ids=[
        "query",
        "fragment",
        "empty_query",
        "encoded_authority",
        "nested_path_encoding",
        "localhost",
        "localdomain",
        "internal",
        "local",
        "loopback",
        "short_loopback",
        "private_ipv4",
        "ipv6_loopback",
        "ipv6_private",
        "backslash",
        "javascript",
        "ftp",
    ],
)
def test_uri_projection_rejects_private_or_ambiguous_locations(uri):
    assert not _safe_http_uri(uri)


@pytest.mark.parametrize(
    "uri",
    [
        "https://localhost./sbom",
        "https://localhost.localdomain./sbom",
        "https://x.localdomain/sbom",
        "https://example..test/sbom",
    ],
)
def test_uri_authority_normalization_does_not_allow_local_or_malformed_hosts(uri):
    assert not _safe_http_uri(uri)


def test_cdx_dangerous_ref_has_consistent_noncolliding_alias_and_v2_is_idempotent():
    original = "https://synthetic_user:synthetic_password@example.test/sbom"
    forged_alias = "redacted-ref:" + hashlib.sha256(original.encode()).hexdigest()
    raw = json.dumps(
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "components": [
                {"type": "library", "name": "a", "bom-ref": original},
                {"type": "library", "name": "b", "bom-ref": forged_alias},
                {"type": "library", "name": "c", "bom-ref": "safe-ref"},
            ],
            "dependencies": [{"ref": original, "dependsOn": [forged_alias, "safe-ref"]}],
            "compositions": [
                {
                    "aggregate": "unknown",
                    "assemblies": [original, forged_alias],
                    "dependencies": [original],
                    "vulnerabilities": [original],
                }
            ],
        }
    ).encode()
    now = datetime(2026, 10, 16, 0, tzinfo=UTC)
    parsed = parse_inventory_input(
        raw,
        manifest_format="cyclonedx_json",
        scope=AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN),
        authorized_asset_tenant_id="tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic",
        observed_at=now,
        recorded_at=now,
    )
    public = freeze_sbom_sidecar(parsed.sbom)
    first, second, third = (item.source_ref for item in public.component_sources)
    assert first == forged_alias and second != forged_alias and third == "safe-ref"
    assert public.dependency_edges[0].source_ref == first
    assert public.dependency_edges[0].target_ref == second
    assert public.dependency_edges[1].target_ref == third
    assert public.completeness_declarations[0].assemblies == (first, second)
    assert public.completeness_declarations[0].dependencies == (first,)
    assert public.completeness_declarations[0].vulnerabilities == (first,)
    assert original not in public.model_dump_json()
    assert safe_sbom_sidecar(public) == public
    assert parsed.manifest.source_bytes == raw
    assert {item.source_field_locator for item in public.redactions} >= {
        "/components/0/bom-ref",
        "/dependencies/0/ref",
        "/dependencies/0/dependsOn/0",
    }


@pytest.mark.parametrize(
    "spoof", ["wrong_alias", "wrong_locator", "legacy_metadata", "null_uri_without_marker"]
)
def test_unbound_projection_prefix_is_not_trusted(spoof):
    private = "file:///C:/private/synthetic-parent"
    now = datetime(2026, 10, 16, 0, tzinfo=UTC)
    parsed = parse_inventory_input(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.7",
                "components": [{"type": "library", "name": "a", "bom-ref": private}],
            }
        ).encode(),
        manifest_format="cyclonedx_json",
        scope=AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN),
        authorized_asset_tenant_id="tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic",
        observed_at=now,
        recorded_at=now,
    )
    payload = freeze_sbom_sidecar(parsed.sbom).model_dump(mode="json")
    if spoof == "null_uri_without_marker":
        payload["redactions"] = []
        payload["component_sources"][0]["source_ref"] = "public-ref"
        payload["external_documents"] = [
            {
                "document_ref": "DocumentRef-external",
                "document_uri": None,
                "checksum": {
                    "algorithm": "SHA256",
                    "checksum_value": "c" * 64,
                    "source_field_locator": "/externalDocumentRefs/0/checksum",
                },
                "source_field_locator": "/externalDocumentRefs/0",
            }
        ]
    elif spoof == "wrong_alias":
        payload["redactions"][0]["replacement_ref"] = "redacted-ref:" + "a" * 64
    elif spoof == "wrong_locator":
        payload["redactions"][0]["source_field_locator"] = "/unrelated"
    else:
        payload["schema_version"] = "r11-sbom-sidecar-1"
    from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse

    corrupted = AssetSnapshotSbomResponse.model_validate(payload)
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(corrupted)
