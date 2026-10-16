"""私有sidecar字段固定，旧snapshot无extra；离线官方SPDX容量profile。"""

import gzip
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from pydantic import ValidationError
from referencing import Registry
from referencing.exceptions import NoSuchResource

from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.sbom_inventory import freeze_sbom_sidecar, parse_inventory_input
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.domain.access import AccessScope, Role

NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("contract-actor", "contract-tenant", Role.TENANT_ADMIN)
ROOT = Path(__file__).resolve().parents[3]


def parse(raw, manifest_format):
    return parse_inventory_input(
        raw,
        manifest_format=manifest_format,
        scope=SCOPE,
        authorized_asset_tenant_id="contract-tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-contract",
        observed_at=NOW,
        recorded_at=NOW,
    )


def test_sbom_sidecar_schema_is_separate_and_roundtrips_without_raw_or_opaque():
    raw = (
        b'{"bomFormat":"CycloneDX","specVersion":"1.7","components":'
        b'[{"type":"library","name":"p","version":"1","bom-ref":"p"}],'
        b'"annotation":"synthetic-private-marker"}'
    )
    parsed = parse(raw, "cyclonedx_json")
    sidecar = freeze_sbom_sidecar(parsed.sbom)
    snapshot = AssetSnapshotResponse.model_validate(parsed.manifest.snapshot)
    assert set(snapshot.model_dump()) == {
        "schema_version",
        "snapshot_id",
        "asset_id",
        "tenant_id",
        "snapshot_number",
        "observed_at",
        "recorded_at",
        "source_kind",
        "inventory_completeness",
        "declared_scope",
        "components",
        "configuration",
        "tool_permissions",
        "input_channels",
        "network_exposure",
        "snapshot_sha256",
    }
    assert sidecar == AssetSnapshotSbomResponse.model_validate_json(sidecar.model_dump_json())
    assert sidecar.unmapped_field_locators == ("/annotation",)
    assert "synthetic-private-marker" not in sidecar.model_dump_json()
    assert "source_bytes" not in AssetSnapshotSbomResponse.model_fields
    assert "raw_input" not in AssetSnapshotSbomResponse.model_fields
    with pytest.raises(ValidationError):
        AssetSnapshotResponse.model_validate(
            {**snapshot.model_dump(), "sidecar": sidecar.model_dump()}
        )


@pytest.mark.parametrize("extra", ["raw_input", "tenant_from_input", "opaque"])
def test_sidecar_contract_rejects_unapproved_extra_fields(extra):
    parsed = parse(
        b'{"bomFormat":"CycloneDX","specVersion":"1.7","components":[]}', "cyclonedx_json"
    )
    sidecar = freeze_sbom_sidecar(parsed.sbom)
    with pytest.raises(ValidationError):
        AssetSnapshotSbomResponse.model_validate({**sidecar.model_dump(), extra: "synthetic"})


def test_official_spdx_10000_name_version_profile_is_valid_and_not_truncated():
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
    path = ROOT / "reports/runs/recovery_r11_sbom_adapters_20261016/spdx-2.3.1.schema.json.gz"
    schema = json.loads(gzip.decompress(path.read_bytes()))

    def prohibit_reference(uri):
        raise NoSuchResource(ref=uri)

    Draft7Validator(
        schema, registry=Registry(retrieve=prohibit_reference), format_checker=FormatChecker()
    ).validate(document)
    raw = json.dumps(document, separators=(",", ":")).encode()
    assert len(raw) < 1048576
    result = parse(raw, "spdx_json")
    assert len(result.manifest.snapshot.components) == 10000
    assert result.manifest.snapshot.components[-1].package_name == "p9999"
    assert len(result.sbom.component_sources) == 10000
    assert result.sbom.component_sources[-1].source_field_locator == "/packages/9999"
