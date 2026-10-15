"""库存接线所需完整10000组件容量；合成输入不计产品live。"""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_intel.assets.manifest_parser import parse_manifest
from ai_intel.assets.sbom_parser import parse_sbom
from ai_intel.domain.access import AccessScope, Role

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("capacity-test", "capacity-tenant", Role.TENANT_ADMIN)


@pytest.mark.parametrize("profile", ["two_fields", "dense"])
def test_cdx_10000_keeps_every_version_and_identity(profile):
    components = [{"type": "library", "name": f"p{i}", "version": "1"} for i in range(10000)]
    if profile == "dense":
        for component in components:
            component["purl"] = "pkg:pypi/" + component["name"] + "@1"
    raw = json.dumps(
        {"bomFormat": "CycloneDX", "specVersion": "1.7", "version": 1, "components": components},
        separators=(",", ":"),
    ).encode()
    assert len(raw) < 1048576
    parsed = parse_sbom(
        raw,
        sbom_format="cyclonedx_json",
        scope=SCOPE,
        authorized_asset_tenant_id="capacity-tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-capacity",
        observed_at=NOW,
        recorded_at=NOW,
    )
    assert len(parsed.manifest.snapshot.components) == 10000
    assert parsed.manifest.snapshot.components[-1].package_name == "p9999"
    assert {component.version for component in parsed.manifest.snapshot.components} == {"1"}
    assert len(parsed.component_sources) == 10000
    assert parsed.manifest.snapshot.inventory_completeness == "unknown"


def test_original_reviewed_dense_10000_bytes_now_parse():
    raw = gzip.decompress(
        (
            ROOT / "reports/runs/recovery_r11_sbom_adapters_20261016/synthetic-dense-10000.json.gz"
        ).read_bytes()
    )
    parsed = parse_sbom(
        raw,
        sbom_format="cyclonedx_json",
        scope=SCOPE,
        authorized_asset_tenant_id="capacity-tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="reviewed-synthetic-capacity",
        observed_at=NOW,
        recorded_at=NOW,
    )
    assert len(parsed.manifest.snapshot.components) == 10000
    assert len(parsed.component_sources) == 10000


def test_spdx_10000_with_direct_versions_keeps_all_components():
    document = {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "capacity",
        "documentNamespace": "https://example.test/capacity",
        "dataLicense": "CC0-1.0",
        "creationInfo": {"created": "2026-10-16T00:00:00Z", "creators": ["Tool: capacity"]},
        "packages": [
            {
                "SPDXID": f"SPDXRef-{i}",
                "name": f"p{i}",
                "versionInfo": "1",
                "downloadLocation": "NOASSERTION",
            }
            for i in range(10000)
        ],
    }
    raw = json.dumps(document, separators=(",", ":")).encode()
    assert len(raw) < 1048576
    parsed = parse_sbom(
        raw,
        sbom_format="spdx_json",
        scope=SCOPE,
        authorized_asset_tenant_id="capacity-tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-spdx-capacity",
        observed_at=NOW,
        recorded_at=NOW,
    )
    assert len(parsed.manifest.snapshot.components) == 10000
    assert parsed.manifest.snapshot.components[-1].version == "1"
    assert parsed.component_sources[-1].source_ref == "SPDXRef-9999"


def test_local_manifest_budget_supports_all_valid_fields_at_10000_component_boundary():
    document = {
        "format_version": 1,
        "components": [
            {
                "ecosystem": "unknown",
                "package_name": f"p{i}",
                "display_name": "package",
                "purl": f"pkg:generic/p{i}",
                "version": "1",
                "version_scheme": "unknown",
                "image_digest": "sha256:" + "a" * 64,
                "dependency_path": [f"parent{j}" for j in range(64)],
            }
            for i in range(10000)
        ],
        "inventory_completeness": "complete_for_declared_scope",
        "declared_scope": [f"scope{i}" for i in range(64)],
        "tool_permissions": [f"tool{i}" for i in range(64)],
        "configuration": {
            "model_name": "declared",
            "provider_name": "declared",
            "trust_remote_code": None,
            "authentication_required": True,
        },
        "input_channels": {
            "public_api": None,
            "uploaded_documents": True,
            "retrieved_web_content": False,
        },
        "network_exposure": {"public_endpoint": None, "outbound_network_allowed": False},
    }
    raw = json.dumps(document, separators=(",", ":")).encode()
    assert len(raw) <= 10485760
    parsed = parse_manifest(
        raw,
        manifest_format="json_manifest_v1",
        scope=SCOPE,
        authorized_asset_tenant_id="capacity-tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-full-field-capacity",
        observed_at=NOW,
        recorded_at=NOW,
    )
    assert len(parsed.snapshot.components) == 10000
    assert len(parsed.snapshot.components[-1].dependency_path) == 64
    assert parsed.snapshot.network_exposure[0].value is False
