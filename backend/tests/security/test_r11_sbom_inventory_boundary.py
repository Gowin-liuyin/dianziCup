"""容量调整保持局部严格JSON与共享模型门，权限先于数据库/解析。"""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.manifest_parser import ManifestValidationError, parse_manifest
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.models.json_output import strict_json_object

NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "suffix",
    [
        b'"version":NaN',
        b'"version":Infinity',
        b'"version":1e999',
        b'"version":"\\u0000"',
        b'"version":"\\ud800"',
        b'"version":"1","version":"2"',
    ],
    ids=["nan", "infinity", "overflow", "nul", "surrogate", "duplicate"],
)
def test_local_inventory_json_still_rejects_invalid_values(suffix):
    raw = b'{"format_version":1,"components":[{"package_name":"p",' + suffix + b"}]}"
    scope = AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN)
    with pytest.raises(ManifestValidationError):
        parse_manifest(
            raw,
            manifest_format="json_manifest_v1",
            scope=scope,
            authorized_asset_tenant_id="tenant",
            asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
            snapshot_number=1,
            source_version="synthetic",
            observed_at=NOW,
            recorded_at=NOW,
        )


def test_local_inventory_json_keeps_depth_limit_and_component_limit():
    scope = AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN)
    arguments = {
        "manifest_format": "json_manifest_v1",
        "scope": scope,
        "authorized_asset_tenant_id": "tenant",
        "asset_id": "b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        "snapshot_number": 1,
        "source_version": "synthetic",
        "observed_at": NOW,
        "recorded_at": NOW,
    }
    nested = (
        b'{"format_version":1,"components":[],"configuration":'
        + b"[" * 17
        + b"0"
        + b"]" * 17
        + b"}"
    )
    with pytest.raises(ManifestValidationError, match="json_depth_limit"):
        parse_manifest(nested, **arguments)
    raw = json.dumps(
        {"format_version": 1, "components": [{"package_name": f"p{i}"} for i in range(10001)]}
    ).encode()
    with pytest.raises(ManifestValidationError, match="component_limit"):
        parse_manifest(raw, **arguments)


def test_shared_model_json_budget_is_not_increased():
    with pytest.raises(ValueError, match="budget outside limit"):
        strict_json_object(b"{}", maximum_nodes=50001)


@pytest.mark.parametrize("role", [Role.ANALYST, Role.VIEWER])
@pytest.mark.parametrize("format_name", ["cyclonedx_json", "spdx_json"])
def test_sbom_write_permission_is_checked_before_any_parse_or_database(role, format_name):
    scope = AccessScope.for_authenticated_user("actor", "tenant", role)
    with Session() as session, pytest.raises(PermissionDeniedError):
        InventoryService(session, scope).import_manifest(
            b"private-marker",
            manifest_format=format_name,
            display_name="synthetic",
            source_version="synthetic",
            observed_at=NOW,
            idempotency_key="key",
        )
