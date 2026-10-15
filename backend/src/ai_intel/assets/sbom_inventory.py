"""库存格式dispatcher与冻结声明序列化；历史读取不使用新代码重解析旧SBOM。"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ai_intel.assets.manifest_parser import (
    ManifestParseResult,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.assets.sbom_parser import SBOM_ADAPTER_VERSION, SbomParseResult, parse_sbom
from ai_intel.domain.access import AccessScope


@dataclass(frozen=True)
class InventoryParseResult:
    manifest: ManifestParseResult
    sbom: SbomParseResult | None

    @property
    def semantic_sha256(self) -> str:
        if self.sbom is not None:
            return self.sbom.combined_semantic_sha256
        return self.manifest.snapshot.snapshot_sha256


def parse_inventory_input(
    raw_bytes: bytes,
    *,
    manifest_format: str,
    scope: AccessScope,
    authorized_asset_tenant_id: str,
    asset_id: str,
    snapshot_number: int,
    source_version: str,
    observed_at: datetime,
    recorded_at: datetime,
    csv_column_mapping: Mapping[str, str] | None = None,
) -> InventoryParseResult:
    """显式格式选择；SBOM拒绝CSV映射，未知格式仍由既有parser固定拒绝。"""
    if manifest_format in {"cyclonedx_json", "spdx_json"}:
        if csv_column_mapping is not None:
            raise ManifestValidationError("unexpected_csv_mapping")
        sbom = parse_sbom(
            raw_bytes,
            sbom_format=manifest_format,
            scope=scope,
            authorized_asset_tenant_id=authorized_asset_tenant_id,
            asset_id=asset_id,
            snapshot_number=snapshot_number,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=recorded_at,
        )
        return InventoryParseResult(sbom.manifest, sbom)
    return InventoryParseResult(
        parse_manifest(
            raw_bytes,
            manifest_format=manifest_format,
            scope=scope,
            authorized_asset_tenant_id=authorized_asset_tenant_id,
            asset_id=asset_id,
            snapshot_number=snapshot_number,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=recorded_at,
            csv_column_mapping=csv_column_mapping,
        ),
        None,
    )


def freeze_sbom_sidecar(result: SbomParseResult) -> AssetSnapshotSbomResponse:
    """身份只由认证候选取得，typed sidecar与版本/hash一次冻结。"""
    snapshot = result.manifest.snapshot
    return AssetSnapshotSbomResponse.model_validate(
        {
            "schema_version": "r11-sbom-sidecar-1",
            "snapshot_id": snapshot.snapshot_id,
            "asset_id": snapshot.asset_id,
            "tenant_id": snapshot.tenant_id,
            "adapter_version": SBOM_ADAPTER_VERSION,
            "source_format": snapshot.source_kind,
            "spec_version": result.spec_version,
            "projection_sha256": snapshot.snapshot_sha256,
            "sidecar_sha256": result.sidecar_sha256,
            "combined_semantic_sha256": result.combined_semantic_sha256,
            "raw_sha256": result.raw_sha256,
            "component_sources": result.component_sources,
            "dependency_edges": result.dependency_edges,
            "completeness_declarations": result.completeness_declarations,
            "external_documents": result.external_documents,
            "unmapped_field_locators": result.unmapped_field_locators,
        }
    )
