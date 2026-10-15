"""私有资产事实同事务持久化；历史不可变，幂等重放不恢复旧current。"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.assets.inventory_contracts import (
    AssetImportResponse,
    AssetListResponse,
    AssetResponse,
    AssetSnapshotListResponse,
    AssetSnapshotResponse,
)
from ai_intel.assets.inventory_models import asset_import_receipts, asset_snapshots, assets
from ai_intel.assets.manifest_parser import ManifestValidationError, parse_manifest
from ai_intel.domain.access import (
    READ_ASSET,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.persistence import knowledge_scope_key, save_change_publication

MAX_INVENTORY_UPLOAD_BYTES = 1048576


class InvalidAssetCursor(ValueError):
    """游标不属于当前租户/资产/查询或位置无效。"""


class AssetNameConflictError(ValueError):
    """导入不得静默修改既有资产名称；元数据变更需要独立审计操作。"""


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _cursor(values: list[str | int]) -> str:
    return base64.urlsafe_b64encode(json.dumps(values).encode()).decode()


def _position(cursor: str, prefix: list[str], count: int) -> list[object]:
    if len(cursor) > 2048:
        raise InvalidAssetCursor("invalid asset cursor")
    try:
        values: object = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
    except (ValueError, UnicodeError):
        raise InvalidAssetCursor("invalid asset cursor") from None
    if not isinstance(values, list) or len(values) != len(prefix) + count:
        raise InvalidAssetCursor("invalid asset cursor")
    if values[: len(prefix)] != prefix:
        raise InvalidAssetCursor("invalid asset cursor")
    return values[len(prefix) :]


class InventoryService:
    """使用调用者Session与认证scope；不commit、不读文件或提供网络资产扫描。"""

    def __init__(self, session: Session, scope: AccessScope) -> None:
        self.session = session
        self.scope = scope

    def _tenant(self, permission: str) -> str:
        self.scope.requires(permission)
        tenant = self.scope.tenant_id
        if not tenant or len(tenant) > 200:
            raise PermissionDeniedError("tenant asset scope required")
        return tenant

    def _asset(self, asset_id: str, *, writing: bool = False) -> RowMapping:
        tenant = self._tenant(WRITE_ASSET if writing else READ_ASSET)
        query = select(assets).where(assets.c.asset_id == asset_id, assets.c.tenant_id == tenant)
        if writing:
            query = query.with_for_update()
        row = self.session.execute(query).mappings().first()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        return row

    def get_snapshot(self, asset_id: str, snapshot_id: str) -> AssetSnapshotResponse:
        tenant = self._tenant(READ_ASSET)
        row = self.session.execute(
            select(asset_snapshots.c.canonical_payload).where(
                asset_snapshots.c.asset_id == asset_id,
                asset_snapshots.c.tenant_id == tenant,
                asset_snapshots.c.snapshot_id == snapshot_id,
            )
        ).first()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        return AssetSnapshotResponse.model_validate(row[0])

    def read_asset(self, asset_id: str) -> AssetResponse:
        row = self._asset(asset_id)
        return AssetResponse.model_validate(
            {
                **row,
                "snapshot": self.get_snapshot(asset_id, str(row["current_snapshot_id"])),
            }
        )

    def import_manifest(
        self,
        raw_bytes: bytes,
        *,
        manifest_format: str,
        display_name: str,
        source_version: str,
        observed_at: datetime,
        idempotency_key: str,
        asset_id: str | None = None,
        csv_column_mapping: Mapping[str, str] | None = None,
        request_route: str = "asset-imports",
    ) -> AssetImportResponse:
        """锁顺序为tenant请求锁→asset锁/行→发布锁/epoch；同current复用且不发布事件。"""
        tenant = self._tenant(WRITE_ASSET)
        if type(raw_bytes) is not bytes or not 1 <= len(raw_bytes) <= MAX_INVENTORY_UPLOAD_BYTES:
            raise ManifestValidationError("inventory_upload_size_limit")
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 200:
            raise ManifestValidationError("invalid_display_name")
        if any(ord(char) < 32 for char in display_name):
            raise ManifestValidationError("invalid_display_name")
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ManifestValidationError("idempotency_key_required")
        if len(idempotency_key) > 200 or any(ord(char) < 32 for char in idempotency_key):
            raise ManifestValidationError("invalid_idempotency_key")
        if request_route not in {"asset-imports", "asset-snapshots"}:
            raise ManifestValidationError("invalid_request_route")
        if asset_id is not None:
            try:
                asset_id = str(UUID(asset_id))
            except (ValueError, TypeError, AttributeError):
                raise ManifestValidationError("invalid_asset_id") from None
        now = datetime.now(UTC)
        selected_id = asset_id or str(uuid4())
        parsed = parse_manifest(
            raw_bytes,
            manifest_format=manifest_format,
            scope=self.scope,
            authorized_asset_tenant_id=tenant,
            asset_id=selected_id,
            snapshot_number=1,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=now,
            csv_column_mapping=csv_column_mapping,
        )
        request_digest = _digest(
            [
                asset_id,
                display_name,
                parsed.source_sha256,
                manifest_format,
                source_version,
                parsed.snapshot.observed_at.isoformat(),
                None if csv_column_mapping is None else dict(csv_column_mapping),
                request_route,
            ]
        )
        scope = VisibilityScope(visibility="tenant", tenant_id=tenant)
        self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(
                        "asset-inventory-tenant:" + tenant,
                        0,
                    )
                )
            )
        )
        previous_request = (
            self.session.execute(
                select(asset_import_receipts).where(
                    asset_import_receipts.c.tenant_id == tenant,
                    asset_import_receipts.c.actor_user_id == self.scope.user_id,
                    asset_import_receipts.c.request_route == request_route,
                    asset_import_receipts.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .first()
        )
        if previous_request is not None:
            if previous_request["request_sha256"] != request_digest:
                raise IdempotencyConflictError(
                    "asset idempotency key reused with different request"
                )
            return AssetImportResponse(
                asset_id=str(previous_request["asset_id"]),
                reused=True,
                snapshot=self.get_snapshot(
                    str(previous_request["asset_id"]),
                    str(previous_request["snapshot_id"]),
                ),
            )
        self.session.execute(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(
                        "asset-inventory:" + tenant + ":" + selected_id,
                        0,
                    )
                )
            )
        )
        current_snapshot = None
        if asset_id is not None:
            asset = self._asset(selected_id, writing=True)
            if asset["display_name"] != display_name:
                raise AssetNameConflictError("asset display name conflict")
            current_snapshot = self.get_snapshot(selected_id, str(asset["current_snapshot_id"]))
        if current_snapshot and current_snapshot.snapshot_sha256 == parsed.snapshot.snapshot_sha256:
            snapshot = current_snapshot
            reused = True
        else:
            if asset_id is None:
                self.session.execute(
                    insert(assets).values(
                        asset_id=selected_id,
                        tenant_id=tenant,
                        display_name=display_name,
                        created_at=now,
                        updated_at=now,
                    )
                )
            number = 1 if current_snapshot is None else current_snapshot.snapshot_number + 1
            parsed = parse_manifest(
                raw_bytes,
                manifest_format=manifest_format,
                scope=self.scope,
                authorized_asset_tenant_id=tenant,
                asset_id=selected_id,
                snapshot_number=number,
                source_version=source_version,
                observed_at=observed_at,
                recorded_at=now,
                csv_column_mapping=csv_column_mapping,
            )
            snapshot = AssetSnapshotResponse.model_validate(parsed.snapshot)
            self.session.execute(
                insert(asset_snapshots).values(
                    snapshot_id=snapshot.snapshot_id,
                    asset_id=selected_id,
                    tenant_id=tenant,
                    snapshot_number=number,
                    previous_snapshot_id=None
                    if current_snapshot is None
                    else current_snapshot.snapshot_id,
                    manifest_sha256=snapshot.snapshot_sha256,
                    raw_input_sha256=parsed.source_sha256,
                    schema_version=snapshot.schema_version,
                    parser_version=parsed.parser_version,
                    source_kind=snapshot.source_kind,
                    source_version=source_version,
                    canonical_payload=snapshot.model_dump(mode="json"),
                    raw_input=raw_bytes,
                    observed_at=snapshot.observed_at,
                    recorded_at=now,
                    actor_user_id=self.scope.user_id,
                )
            )
            self.session.execute(
                update(assets)
                .where(
                    assets.c.asset_id == selected_id,
                    assets.c.tenant_id == tenant,
                )
                .values(
                    current_snapshot_id=snapshot.snapshot_id,
                    display_name=display_name,
                    updated_at=now,
                )
            )
            payload: dict[str, object] = {
                "asset_id": selected_id,
                "asset_snapshot_id": snapshot.snapshot_id,
                "previous_snapshot_id": None
                if current_snapshot is None
                else current_snapshot.snapshot_id,
                "manifest_sha256": snapshot.snapshot_sha256,
                "package_keys": sorted(
                    {c.ecosystem + ":" + c.package_name for c in snapshot.components}
                ),
                "change_reason": "asset_created"
                if current_snapshot is None
                else "asset_snapshot_changed",
            }
            self.session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(
                            "knowledge-publication:" + knowledge_scope_key(scope),
                            0,
                        )
                    )
                )
            )
            save_change_publication(
                self.session,
                scope,
                "asset-snapshot:" + snapshot.snapshot_id,
                payload,
                _digest(payload),
                (),
                (selected_id, snapshot.snapshot_id),
                now,
                "asset_snapshot_changed",
            )
            reused = False
        self.session.execute(
            insert(asset_import_receipts).values(
                tenant_id=tenant,
                actor_user_id=self.scope.user_id,
                request_route=request_route,
                idempotency_key=idempotency_key,
                request_sha256=request_digest,
                asset_id=selected_id,
                snapshot_id=snapshot.snapshot_id,
                created_at=now,
            )
        )
        return AssetImportResponse(asset_id=selected_id, snapshot=snapshot, reused=reused)

    def list_assets(
        self,
        *,
        limit: int = 20,
        cursor: str | None = None,
        product: str = "",
    ) -> AssetListResponse:
        tenant = self._tenant(READ_ASSET)
        if not 1 <= limit <= 100 or len(product) > 200:
            raise InvalidAssetCursor("invalid asset page")
        query = select(assets).where(assets.c.tenant_id == tenant)
        if product:
            query = query.where(
                assets.c.current_snapshot_id.in_(
                    select(asset_snapshots.c.snapshot_id).where(
                        asset_snapshots.c.tenant_id == tenant,
                        asset_snapshots.c.canonical_payload["components"].contains(
                            [{"package_name": product}]
                        ),
                    )
                )
            )
        prefix = ["assets-v1", tenant, product]
        if cursor:
            position = _position(cursor, prefix, 2)
            try:
                if not isinstance(position[0], str) or not isinstance(position[1], str):
                    raise ValueError("invalid position")
                created = datetime.fromisoformat(position[0])
                if created.utcoffset() is None:
                    raise ValueError("invalid position")
                identity = str(UUID(position[1]))
            except (ValueError, TypeError):
                raise InvalidAssetCursor("invalid asset cursor") from None
            query = query.where(
                or_(
                    assets.c.created_at > created,
                    and_(assets.c.created_at == created, assets.c.asset_id > identity),
                )
            )
        rows = (
            self.session.execute(
                query.order_by(assets.c.created_at, assets.c.asset_id).limit(limit + 1)
            )
            .mappings()
            .all()
        )
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            last = page[-1]
            next_cursor = _cursor([*prefix, last["created_at"].isoformat(), str(last["asset_id"])])
        return AssetListResponse(
            items=tuple(
                AssetResponse.model_validate(
                    {
                        **row,
                        "snapshot": self.get_snapshot(
                            str(row["asset_id"]), str(row["current_snapshot_id"])
                        ),
                    }
                )
                for row in page
            ),
            next_cursor=next_cursor,
        )

    def list_snapshots(
        self,
        asset_id: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> AssetSnapshotListResponse:
        tenant = self._tenant(READ_ASSET)
        self._asset(asset_id)
        if not 1 <= limit <= 100:
            raise InvalidAssetCursor("invalid snapshot page")
        query = select(asset_snapshots).where(
            asset_snapshots.c.asset_id == asset_id,
            asset_snapshots.c.tenant_id == tenant,
        )
        prefix = ["snapshots-v1", tenant, asset_id]
        if cursor:
            position = _position(cursor, prefix, 1)
            number = position[0]
            if type(number) is not int or number < 1:
                raise InvalidAssetCursor("invalid snapshot cursor")
            query = query.where(asset_snapshots.c.snapshot_number < number)
        rows = (
            self.session.execute(
                query.order_by(asset_snapshots.c.snapshot_number.desc()).limit(limit + 1)
            )
            .mappings()
            .all()
        )
        page = rows[:limit]
        next_cursor = (
            _cursor([*prefix, int(page[-1]["snapshot_number"])]) if len(rows) > limit else None
        )
        return AssetSnapshotListResponse(
            items=tuple(
                AssetSnapshotResponse.model_validate(row["canonical_payload"]) for row in page
            ),
            next_cursor=next_cursor,
        )
