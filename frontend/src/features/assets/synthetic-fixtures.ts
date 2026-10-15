export const fixtureAssetId = "a0000000-0000-4000-8000-000000000001";
export const fixtureSnapshotId = "b0000000-0000-4000-8000-000000000002";
export const fixtureTenant = "synthetic-assets-tenant";
export function snapshotFixture(number = 2) {
  return {
    schema_version: "r11-asset-candidate-1", snapshot_id: number === 2 ? fixtureSnapshotId : "b0000000-0000-4000-8000-000000000001",
    asset_id: fixtureAssetId, tenant_id: fixtureTenant, snapshot_number: number,
    observed_at: "2026-10-15T10:00:00+00:00", recorded_at: "2026-10-15T10:01:00+00:00", source_kind: "json_manifest_v1",
    inventory_completeness: "partial", declared_scope: ["Synthetic fixture runtime"],
    components: [{ component_id: "c0000000-0000-4000-8000-000000000001", ecosystem: "PyPI", package_name: "synthetic-demo-package", display_name: "Synthetic fixture component", purl: "pkg:pypi/synthetic-demo-package@1.9.0", version: number === 2 ? null : "1.9.0", version_scheme: "pep440", image_digest: null, dependency_path: ["synthetic-root"], source_field_locator: "/components/0" }],
    configuration: [{ name: "trust_remote_code", value: null, source_field_locator: "/configuration/trust_remote_code" }, { name: "authentication_required", value: false, source_field_locator: "/configuration/authentication_required" }],
    tool_permissions: null, input_channels: null, network_exposure: [{ name: "public_endpoint", value: false, source_field_locator: "/network_exposure/public_endpoint" }], snapshot_sha256: "a".repeat(64),
  };
}
export function assetFixture() {
  return { asset_id: fixtureAssetId, tenant_id: fixtureTenant, display_name: "Synthetic fixture · 资产工作台", criticality: "unknown", active: true, current_snapshot_id: fixtureSnapshotId, created_at: "2026-10-15T10:00:00Z", updated_at: "2026-10-15T10:01:00Z", snapshot: snapshotFixture() };
}

