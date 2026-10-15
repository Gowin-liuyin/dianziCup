"""资产服务输入权限边界，不执行文件/网络/任意SQL或回显上传正文。"""

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_routes import build_inventory_router
from ai_intel.assets.manifest_parser import ManifestValidationError
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role


def test_tenantless_admin_does_not_gain_private_asset_scope():
    access = AccessScope.for_authenticated_user("actor", None, Role.SYSTEM_ADMIN)
    with Session() as session:
        inventory = InventoryService(session, access)
        with pytest.raises(PermissionDeniedError):
            inventory.list_assets()
        with pytest.raises(PermissionDeniedError):
            inventory.import_manifest(
                b"{}",
                manifest_format="json_manifest_v1",
                display_name="test",
                source_version="test",
                observed_at=datetime.now(UTC),
                idempotency_key="test",
            )


@pytest.mark.parametrize(
    "raw",
    ["C:/private", bytearray(b"{}"), b"", b"x" * 1048577],
    ids=["private_path", "bytearray", "empty", "one_mib_plus_one"],
)
def test_raw_type_and_size_fail_without_database_io(raw):
    access = AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN)
    with Session() as session, pytest.raises(ManifestValidationError) as rejected:
        InventoryService(session, access).import_manifest(
            raw,
            manifest_format="json_manifest_v1",
            display_name="test",
            source_version="test",
            observed_at=datetime.now(UTC),
            idempotency_key="test",
        )
    assert rejected.value.code == "inventory_upload_size_limit"
    assert "private" not in str(rejected.value)


def test_unconfigured_router_does_not_fallback_to_fixture_or_parse_private_input():
    app = FastAPI()
    app.include_router(build_inventory_router(lambda: None, None))
    with TestClient(app) as client:
        unauthenticated = client.post("/asset-snapshots", content=b"secret-marker")
        assert unauthenticated.status_code == 401
        unavailable = client.post(
            "/asset-snapshots",
            content=b"secret-marker",
            cookies={"ai_intel_session": "synthetic-invalid-token"},
        )
        assert unavailable.status_code == 503
        assert "secret-marker" not in unavailable.text
