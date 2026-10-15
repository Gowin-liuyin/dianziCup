"""显式格式、来源字节、冻结typed声明及旧投影兼容。"""

import json
from datetime import UTC, datetime

import pytest

from ai_intel.assets.manifest_parser import ManifestValidationError
from ai_intel.assets.sbom_inventory import freeze_sbom_sidecar, parse_inventory_input
from ai_intel.domain.access import AccessScope, Role

NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("dispatch-actor", "dispatch-tenant", Role.TENANT_ADMIN)
OPTIONS = {
    "scope": SCOPE,
    "authorized_asset_tenant_id": "dispatch-tenant",
    "asset_id": "b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
    "snapshot_number": 1,
    "source_version": "synthetic-dispatch",
    "observed_at": NOW,
    "recorded_at": NOW,
}


def test_dispatch_legacy_json_and_csv_keep_projection_and_no_sbom():
    first = parse_inventory_input(
        b'{"format_version":1,"components":[{"package_name":"p","version":"1"}]}',
        manifest_format="json_manifest_v1",
        **OPTIONS,
    )
    second = parse_inventory_input(
        b"Name,Version\np,1\n",
        manifest_format="csv_components_v1",
        csv_column_mapping={"package_name": "Name", "version": "Version"},
        **OPTIONS,
    )
    assert first.sbom is second.sbom is None
    assert first.semantic_sha256 == first.manifest.snapshot.snapshot_sha256
    assert first.semantic_sha256 == second.semantic_sha256


@pytest.mark.parametrize("version", ["1.5", "1.6", "1.7"])
def test_sbom_dispatch_freezes_safe_typed_sidecar_from_server_identity(version):
    raw = json.dumps(
        {
            "bomFormat": "CycloneDX",
            "specVersion": version,
            "version": 1,
            "components": [
                {
                    "type": "library",
                    "name": "p",
                    "version": "1",
                    "bom-ref": "ref-p",
                    "hashes": [{"alg": "SHA-256", "content": "a" * 64}],
                }
            ],
            "compositions": [{"aggregate": "complete", "assemblies": ["ref-p"]}],
            "opaque": "private-marker",
        }
    ).encode()
    result = parse_inventory_input(raw, manifest_format="cyclonedx_json", **OPTIONS)
    assert result.sbom is not None
    sidecar = freeze_sbom_sidecar(result.sbom)
    assert sidecar.tenant_id == "dispatch-tenant"
    assert sidecar.spec_version == version
    assert sidecar.component_sources[0].checksums[0].checksum_value == "a" * 64
    assert sidecar.completeness_declarations[0].aggregate == "complete"
    assert result.manifest.source_bytes == raw
    assert result.manifest.snapshot.components[0].image_digest is None
    assert result.manifest.snapshot.components[0].dependency_path is None
    assert result.manifest.snapshot.inventory_completeness == "unknown"
    assert sidecar.combined_semantic_sha256 == result.semantic_sha256
    assert "private-marker" not in sidecar.model_dump_json()
    assert sidecar.unmapped_field_locators == ("/opaque",)


@pytest.mark.parametrize("format_name", ["cyclonedx_json", "spdx_json"])
def test_sbom_dispatch_rejects_csv_mapping_before_parsing(format_name):
    with pytest.raises(ManifestValidationError, match="unexpected_csv_mapping"):
        parse_inventory_input(
            b"{}",
            manifest_format=format_name,
            csv_column_mapping={"package_name": "Name"},
            **OPTIONS,
        )


def test_unknown_format_is_not_inferred_from_document():
    with pytest.raises(ManifestValidationError, match="unsupported_format"):
        parse_inventory_input(b"{}", manifest_format="auto", **OPTIONS)
