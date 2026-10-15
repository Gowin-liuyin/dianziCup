"""私有SBOM历史声明DTO；不回原文、opaque值或自行核验完整性的结论。"""

from typing import Literal

from pydantic import Field

from ai_intel.assets.inventory_contracts import InventoryContract


class SbomFieldSourceResponse(InventoryContract):
    field_name: str
    source_field_locator: str


class SbomChecksumResponse(InventoryContract):
    algorithm: str
    checksum_value: str
    source_field_locator: str


class SbomComponentSourceResponse(InventoryContract):
    component_id: str
    source_ref: str | None
    component_type: str | None
    source_field_locator: str
    field_sources: tuple[SbomFieldSourceResponse, ...]
    checksums: tuple[SbomChecksumResponse, ...]


class SbomDependencyEdgeResponse(InventoryContract):
    source_ref: str
    target_ref: str
    relationship: str
    source_field_locator: str


class SbomCompletenessDeclarationResponse(InventoryContract):
    aggregate: str
    assemblies: tuple[str, ...]
    dependencies: tuple[str, ...]
    vulnerabilities: tuple[str, ...]
    source_field_locator: str


class SbomExternalDocumentResponse(InventoryContract):
    document_ref: str
    document_uri: str | None
    checksum: SbomChecksumResponse
    source_field_locator: str


class SbomRedactionResponse(InventoryContract):
    source_field_locator: str
    reason: Literal["unsafe_uri_or_path"]
    replacement_ref: str | None = Field(default=None, pattern="^redacted-ref:[0-9a-f]{64}$")


class AssetSnapshotSbomResponse(InventoryContract):
    schema_version: Literal["r11-sbom-sidecar-1", "r11-sbom-sidecar-2"]
    snapshot_id: str
    asset_id: str
    tenant_id: str
    adapter_version: Literal["r11-sbom-adapter-1"]
    source_format: Literal["cyclonedx_json", "spdx_json"]
    spec_version: Literal["1.5", "1.6", "1.7", "SPDX-2.3"]
    projection_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    sidecar_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    combined_semantic_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern="^[0-9a-f]{64}$")
    component_sources: tuple[SbomComponentSourceResponse, ...]
    dependency_edges: tuple[SbomDependencyEdgeResponse, ...]
    completeness_declarations: tuple[SbomCompletenessDeclarationResponse, ...]
    external_documents: tuple[SbomExternalDocumentResponse, ...]
    unmapped_field_locators: tuple[str, ...]
    redactions: tuple[SbomRedactionResponse, ...] = ()
