"""资产专用规范/游标/输入边界纯测试，不替代PG验证。"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ai_intel.assets.inventory import InvalidAssetCursor, InventoryService, _cursor, _position
from ai_intel.assets.manifest_parser import ManifestValidationError
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role


@pytest.mark.parametrize(
    "value",
    ["garbage!", "", "e30=", "bnVsbA==", "x" * 2049],
    ids=["invalid_base64", "empty", "wrong_object", "null", "oversized"],
)
def test_invalid_cursor_rejects_without_coercion(value):
    with pytest.raises(InvalidAssetCursor):
        _position(value, ["assets-v1", "tenant-a", ""], 2)


def test_cursor_partition_and_roundtrip():
    encoded = _cursor(
        ["assets-v1", "tenant-a", "langchain", "2026-10-16T00:00:00+00:00", str(uuid4())]
    )
    assert (
        _position(encoded, ["assets-v1", "tenant-a", "langchain"], 2)[0]
        == "2026-10-16T00:00:00+00:00"
    )
    with pytest.raises(InvalidAssetCursor):
        _position(encoded, ["assets-v1", "tenant-b", "langchain"], 2)
    with pytest.raises(InvalidAssetCursor):
        _position(encoded, ["assets-v1", "tenant-a", "different"], 2)


@pytest.mark.parametrize("permission", [Role.ANALYST, Role.VIEWER])
def test_write_scope_denied_before_database(permission):
    access = AccessScope.for_authenticated_user("test", "tenant-a", permission)
    with Session() as session, pytest.raises(PermissionDeniedError):
        InventoryService(session, access).import_manifest(
            b"{}",
            manifest_format="json_manifest_v1",
            display_name="test",
            source_version="synthetic",
            observed_at=datetime.now(UTC),
            idempotency_key="test",
        )


@pytest.mark.parametrize(
    "options,code",
    [
        ({"idempotency_key": ""}, "idempotency_key_required"),
        ({"idempotency_key": "a" * 201}, "invalid_idempotency_key"),
        ({"idempotency_key": "x\ny"}, "invalid_idempotency_key"),
        ({"display_name": " "}, "invalid_display_name"),
        ({"display_name": "x\ny"}, "invalid_display_name"),
        ({"request_route": "arbitrary"}, "invalid_request_route"),
        ({"asset_id": "C:/private"}, "invalid_asset_id"),
    ],
)
def test_import_boundary_rejects_before_database(options, code):
    arguments = {
        "manifest_format": "json_manifest_v1",
        "display_name": "test",
        "source_version": "synthetic",
        "observed_at": datetime.now(UTC),
        "idempotency_key": "test",
        **options,
    }
    access = AccessScope.for_authenticated_user("test", "tenant-a", Role.TENANT_ADMIN)
    with Session() as session, pytest.raises(ManifestValidationError) as rejected:
        InventoryService(session, access).import_manifest(b"{}", **arguments)
    assert rejected.value.code == code
