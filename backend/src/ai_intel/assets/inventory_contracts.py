"""03完整资产字段的独立DTO；public v2尚无AssetSnapshot定义，未修改公共schema。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from ai_intel.assets.manifest_parser import InventoryCompleteness

ManifestFormat = Literal["json_manifest_v1", "csv_components_v1"]


class InventoryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, hide_input_in_errors=True)


class DeclaredFieldResponse(InventoryContract):
    name: str
    value: str | bool | None
    source_field_locator: str


class ComponentResponse(InventoryContract):
    component_id: str
    ecosystem: str
    package_name: str
    display_name: str | None
    purl: str | None
    version: str | None
    version_scheme: str
    image_digest: str | None
    dependency_path: tuple[str, ...] | None
    source_field_locator: str


class AssetSnapshotResponse(InventoryContract):
    schema_version: Literal["r11-asset-candidate-1"]
    snapshot_id: str
    asset_id: str
    tenant_id: str
    snapshot_number: int
    observed_at: datetime
    recorded_at: datetime
    source_kind: str
    inventory_completeness: InventoryCompleteness
    declared_scope: tuple[str, ...]
    components: tuple[ComponentResponse, ...]
    configuration: tuple[DeclaredFieldResponse, ...]
    tool_permissions: tuple[str, ...] | None
    input_channels: tuple[DeclaredFieldResponse, ...] | None
    network_exposure: tuple[DeclaredFieldResponse, ...] | None
    snapshot_sha256: str


class AssetResponse(InventoryContract):
    asset_id: str
    tenant_id: str
    display_name: str
    criticality: str
    active: bool
    current_snapshot_id: str
    created_at: datetime
    updated_at: datetime
    snapshot: AssetSnapshotResponse


class AssetImportResponse(InventoryContract):
    asset_id: str
    snapshot: AssetSnapshotResponse
    reused: bool


class AssetListResponse(InventoryContract):
    items: tuple[AssetResponse, ...]
    next_cursor: str | None


class AssetSnapshotListResponse(InventoryContract):
    items: tuple[AssetSnapshotResponse, ...]
    next_cursor: str | None


class AssetSnapshotRequest(InventoryContract):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    asset_id: UUID | None = None
    display_name: str = Field(min_length=1, max_length=200)
    source_version: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    snapshot: dict[str, JsonValue]

    @field_validator("asset_id", mode="before")
    @classmethod
    def parse_asset_uuid(cls, value: object) -> UUID | None:
        if value is None or isinstance(value, UUID):
            return value
        if isinstance(value, str):
            return UUID(value)
        raise ValueError("invalid asset identity")

    @field_validator("observed_at", mode="before")
    @classmethod
    def parse_observed_timestamp(cls, value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        raise ValueError("invalid observed timestamp")
