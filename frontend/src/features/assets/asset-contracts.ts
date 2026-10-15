import { ApiProblem } from "../../api/client";

export type InventoryCompleteness = "complete_for_declared_scope" | "partial" | "unknown";
export type ManifestFormat = "json_manifest_v1" | "csv_components_v1";
export interface DeclaredField { name: string; value: string | boolean | null; source_field_locator: string }
export interface AssetComponent {
  component_id: string; ecosystem: string; package_name: string; display_name: string | null; purl: string | null;
  version: string | null; version_scheme: string; image_digest: string | null; dependency_path: string[] | null; source_field_locator: string;
}
export interface AssetSnapshot {
  schema_version: "r11-asset-candidate-1"; snapshot_id: string; asset_id: string; tenant_id: string; snapshot_number: number;
  observed_at: string; recorded_at: string; source_kind: string; inventory_completeness: InventoryCompleteness; declared_scope: string[];
  components: AssetComponent[]; configuration: DeclaredField[]; tool_permissions: string[] | null;
  input_channels: DeclaredField[] | null; network_exposure: DeclaredField[] | null; snapshot_sha256: string;
}
export interface Asset {
  asset_id: string; tenant_id: string; display_name: string; criticality: string; active: boolean;
  current_snapshot_id: string; created_at: string; updated_at: string; snapshot: AssetSnapshot;
}
export interface AssetPage { items: Asset[]; next_cursor: string | null }
export interface SnapshotPage { items: AssetSnapshot[]; next_cursor: string | null }
export interface AssetImportResult { asset_id: string; snapshot: AssetSnapshot; reused: boolean }

/** 已确认的租户或请求对象范围违例；不携带收到的私有标识，沿用既有公开错误码。 */
export class AssetResponseScopeMismatch extends ApiProblem {
  constructor() {
    super(502, "invalid_response", false);
    this.name = "AssetResponseScopeMismatch";
  }
}

function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
  if (Object.keys(value).length !== keys.length || Object.keys(value).some((key) => !keys.includes(key))) return invalid();
  return Object.fromEntries(Object.entries(value));
}
function text(value: unknown, maximum = 4096): string {
  if (typeof value !== "string" || !value || [...value].length > maximum || /[\u0000-\u001f]/.test(value)) return invalid();
  return value;
}
function nullableText(value: unknown): string | null { return value === null ? null : text(value); }
export function isAssetIdentifier(value: string): boolean { return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value); }
function identifier(value: unknown): string { const id = text(value, 36); return isAssetIdentifier(id) ? id.toLowerCase() : invalid(); }
function timestamp(value: unknown): string {
  const result = text(value, 64);
  return /T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(result) && Number.isFinite(Date.parse(result)) ? result : invalid();
}
function boolean(value: unknown): boolean { return typeof value === "boolean" ? value : invalid(); }
function list<T>(value: unknown, parse: (item: unknown) => T, maximum: number): T[] {
  return Array.isArray(value) && value.length <= maximum ? value.map((item: unknown) => parse(item)) : invalid();
}
function unique<T>(items: T[], identity: (item: T) => string): T[] { return new Set(items.map(identity)).size === items.length ? items : invalid(); }
function strings(value: unknown): string[] { return list(value, (item) => text(item), 64); }
function field(value: unknown): DeclaredField {
  const item = record(value, ["name", "value", "source_field_locator"]);
  const declaredValue = item.value === null || typeof item.value === "boolean" ? item.value : text(item.value);
  return { name: text(item.name), value: declaredValue, source_field_locator: text(item.source_field_locator) };
}
function fields(value: unknown): DeclaredField[] { return unique(list(value, field, 64), (item) => item.name); }
function component(value: unknown): AssetComponent {
  const item = record(value, ["component_id", "ecosystem", "package_name", "display_name", "purl", "version", "version_scheme", "image_digest", "dependency_path", "source_field_locator"]);
  return { component_id: identifier(item.component_id), ecosystem: text(item.ecosystem), package_name: text(item.package_name), display_name: nullableText(item.display_name), purl: nullableText(item.purl), version: nullableText(item.version), version_scheme: text(item.version_scheme), image_digest: nullableText(item.image_digest), dependency_path: item.dependency_path === null ? null : strings(item.dependency_path), source_field_locator: text(item.source_field_locator) };
}

/** 响应必须与当前认证租户及指定资产一致；配置 null 保持未知，原文和存储路径不进入 DTO。 */
export function parseSnapshot(value: unknown, tenant: string, assetId: string): AssetSnapshot {
  const item = record(value, ["schema_version", "snapshot_id", "asset_id", "tenant_id", "snapshot_number", "observed_at", "recorded_at", "source_kind", "inventory_completeness", "declared_scope", "components", "configuration", "tool_permissions", "input_channels", "network_exposure", "snapshot_sha256"]);
  if (item.tenant_id !== tenant || identifier(item.asset_id) !== assetId.toLowerCase()) throw new AssetResponseScopeMismatch();
  if (item.schema_version !== "r11-asset-candidate-1") return invalid();
  const completeness = item.inventory_completeness;
  if (completeness !== "complete_for_declared_scope" && completeness !== "partial" && completeness !== "unknown") return invalid();
  if (typeof item.snapshot_number !== "number" || !Number.isSafeInteger(item.snapshot_number) || item.snapshot_number < 1) return invalid();
  const hash = text(item.snapshot_sha256, 64);
  if (!/^[0-9a-f]{64}$/.test(hash)) return invalid();
  return { schema_version: item.schema_version, snapshot_id: identifier(item.snapshot_id), asset_id: identifier(item.asset_id), tenant_id: tenant, snapshot_number: item.snapshot_number, observed_at: timestamp(item.observed_at), recorded_at: timestamp(item.recorded_at), source_kind: text(item.source_kind), inventory_completeness: completeness, declared_scope: strings(item.declared_scope), components: unique(list(item.components, component, 10000), (entry) => entry.component_id), configuration: fields(item.configuration), tool_permissions: item.tool_permissions === null ? null : strings(item.tool_permissions), input_channels: item.input_channels === null ? null : fields(item.input_channels), network_exposure: item.network_exposure === null ? null : fields(item.network_exposure), snapshot_sha256: hash };
}
export function parseAsset(value: unknown, tenant: string): Asset {
  const item = record(value, ["asset_id", "tenant_id", "display_name", "criticality", "active", "current_snapshot_id", "created_at", "updated_at", "snapshot"]);
  if (item.tenant_id !== tenant) throw new AssetResponseScopeMismatch();
  const assetId = identifier(item.asset_id);
  const snapshot = parseSnapshot(item.snapshot, tenant, assetId);
  if (identifier(item.current_snapshot_id) !== snapshot.snapshot_id) return invalid();
  return { asset_id: assetId, tenant_id: tenant, display_name: text(item.display_name, 200), criticality: text(item.criticality), active: boolean(item.active), current_snapshot_id: snapshot.snapshot_id, created_at: timestamp(item.created_at), updated_at: timestamp(item.updated_at), snapshot };
}
function cursor(value: unknown): string | null { return value === null ? null : text(value, 8192); }
export function parseAssetList(value: unknown, tenant: string): AssetPage {
  const item = record(value, ["items", "next_cursor"]);
  return { items: unique(list(item.items, (entry) => parseAsset(entry, tenant), 100), (entry) => entry.asset_id), next_cursor: cursor(item.next_cursor) };
}
export function parseSnapshotList(value: unknown, tenant: string, assetId: string): SnapshotPage {
  const item = record(value, ["items", "next_cursor"]);
  return { items: unique(list(item.items, (entry) => parseSnapshot(entry, tenant, assetId), 100), (entry) => entry.snapshot_id), next_cursor: cursor(item.next_cursor) };
}
export function parseImportResult(value: unknown, tenant: string): AssetImportResult {
  const item = record(value, ["asset_id", "snapshot", "reused"]);
  const assetId = identifier(item.asset_id);
  return { asset_id: assetId, snapshot: parseSnapshot(item.snapshot, tenant, assetId), reused: boolean(item.reused) };
}
