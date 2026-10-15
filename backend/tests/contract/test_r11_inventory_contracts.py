"""完整03私有AssetSnapshot映射及公开Component五字段合同。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ai_intel.assets.inventory_contracts import AssetSnapshotRequest, AssetSnapshotResponse
from ai_intel.assets.manifest_parser import parse_manifest
from ai_intel.domain.access import AccessScope, Role


def test_complete_snapshot_maps_all_frozen_03_fields_and_nullable_values():
    result = parse_manifest(
        b'{"format_version":1,"components":[{"ecosystem":"pypi","package_name":"langchain","version":null}],"configuration":{"authentication_required":null}}',
        manifest_format="json_manifest_v1",
        scope=AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN),
        authorized_asset_tenant_id="tenant",
        asset_id=str(uuid4()),
        snapshot_number=1,
        source_version="synthetic-test",
        observed_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
    )
    response = AssetSnapshotResponse.model_validate(result.snapshot)
    assert set(response.model_dump()) == {
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
    component = response.components[0].model_dump()
    public_component = {
        key: component[key]
        for key in ("component_id", "ecosystem", "package_name", "version", "purl")
    }
    bundle = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_v2.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(bundle["$defs"]["Component"]).validate(public_component)
    assert public_component["version"] is None
    assert response.configuration[0].source_field_locator.startswith("/configuration/")
    assert response.tool_permissions is None


@pytest.mark.parametrize(
    "extra", [{"tenant_id": "spoof"}, {"role": "system_admin"}, {"server_path": "C:/private"}]
)
def test_request_disallows_identity_and_file_fields(extra):
    with pytest.raises(ValidationError):
        AssetSnapshotRequest.model_validate_json(
            json.dumps(
                {
                    "display_name": "fixture",
                    "source_version": "synthetic",
                    "observed_at": "2026-10-16T00:00:00+08:00",
                    "snapshot": {},
                    **extra,
                }
            )
        )


def test_public_v2_has_no_asset_snapshot_definition_so_full_adapter_is_not_claimed():
    bundle = json.loads(
        (Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_v2.json").read_text(
            encoding="utf-8"
        )
    )
    assert "AssetSnapshot" not in bundle["$defs"]
