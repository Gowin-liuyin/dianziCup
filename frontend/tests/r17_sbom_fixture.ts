import type { AssetSnapshot } from "../src/features/assets/asset-contracts";
import { parseSnapshot } from "../src/features/assets/asset-contracts";
import type { SnapshotSbom } from "../src/features/assets/sbom-contracts";
import { assetFixture, fixtureAssetId, fixtureTenant, snapshotFixture } from "../src/features/assets/synthetic-fixtures";

/** Synthetic declarations only; the digest literals are fixture identities, not measured evidence. */
export function sbomSnapshot(number = 2, format: "cyclonedx_json" | "spdx_json" = "cyclonedx_json"): AssetSnapshot {
  return parseSnapshot({ ...snapshotFixture(number), source_kind: format, inventory_completeness: "unknown", declared_scope: [] }, fixtureTenant, fixtureAssetId);
}
export function sbomAsset() { return { ...assetFixture(), snapshot: sbomSnapshot() }; }
export function sbomFixture(number = 2, format: "cyclonedx_json" | "spdx_json" = "cyclonedx_json"): SnapshotSbom {
  const snapshot = sbomSnapshot(number, format);
  const component = snapshot.components[0];
  if (component === undefined) throw new Error("synthetic component missing");
  return { schema_version: "r11-sbom-sidecar-2", snapshot_id: snapshot.snapshot_id, asset_id: snapshot.asset_id, tenant_id: snapshot.tenant_id,
    adapter_version: "r11-sbom-adapter-1", source_format: format, spec_version: format === "cyclonedx_json" ? "1.6" : "SPDX-2.3",
    projection_sha256: snapshot.snapshot_sha256, sidecar_sha256: "b".repeat(64), combined_semantic_sha256: (number === 2 ? "c" : "d").repeat(64), raw_sha256: "e".repeat(64),
    component_sources: [{ component_id: component.component_id, source_ref: "synthetic-root", component_type: "library", source_field_locator: "/components/0", field_sources: [{ field_name: "package_name", source_field_locator: "/components/0/name" }], checksums: [{ algorithm: "SHA-256", checksum_value: "f".repeat(64), source_field_locator: "/components/0/hashes/0" }] }],
    dependency_edges: [{ source_ref: "synthetic-root", target_ref: "synthetic-child", relationship: format === "cyclonedx_json" ? "dependsOn" : "DEPENDS_ON", source_field_locator: format === "cyclonedx_json" ? "/dependencies/0/dependsOn/0" : "/relationships/0" }],
    completeness_declarations: [{ aggregate: "complete", assemblies: ["synthetic-root"], dependencies: [], vulnerabilities: [], source_field_locator: "/compositions/0" }],
    external_documents: [], unmapped_field_locators: ["/metadata/annotations"], redactions: [] };
}
