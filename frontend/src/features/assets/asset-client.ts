import { ApiProblem, fetchJson, getCsrfToken } from "../../api/client";
import { AssetResponseScopeMismatch, isAssetIdentifier, parseAsset, parseAssetList, parseImportResult, parseSnapshot, parseSnapshotList, type Asset, type AssetImportResult, type AssetPage, type AssetSnapshot, type ManifestFormat, type SnapshotPage } from "./asset-contracts";
import { parseSnapshotSbom, type SnapshotSbom } from "./sbom-contracts";

export const MAX_ASSET_UPLOAD_BYTES = 1048576;
export const csvFields = ["package_name", "ecosystem", "display_name", "purl", "version", "version_scheme", "image_digest"] as const;
export interface AssetImportRequest { file: File; displayName: string; sourceVersion: string; observedAt: string; manifestFormat: ManifestFormat; assetId?: string; csvColumnMapping?: Record<string, string>; idempotencyKey: string }
function invalidInput(): never { throw new ApiProblem(422, "validation_error", false); }
function assetPath(assetId: string): string { return isAssetIdentifier(assetId) ? `/v1/assets/${encodeURIComponent(assetId)}` : invalidInput(); }
function pageQuery(cursor: string | null): URLSearchParams {
  const query = new URLSearchParams({ limit: "20" });
  if (cursor !== null) { if (!cursor || cursor.length > 8192) return invalidInput(); query.set("cursor", cursor); }
  return query;
}
export async function getAssetList(tenant: string, product = "", cursor: string | null = null, signal?: AbortSignal): Promise<AssetPage> {
  const query = pageQuery(cursor);
  if ([...product].length > 200 || /[\u0000-\u001f]/.test(product)) return invalidInput();
  if (product) query.set("product", product);
  const result = parseAssetList(await fetchJson(`/v1/assets?${query}`, {}, signal), tenant);
  if (cursor !== null && result.next_cursor === cursor) throw new ApiProblem(502, "invalid_response", true);
  return result;
}
export async function getAsset(tenant: string, assetId: string, signal?: AbortSignal): Promise<Asset> {
  const result = parseAsset(await fetchJson(assetPath(assetId), {}, signal), tenant);
  if (result.asset_id !== assetId.toLowerCase()) throw new AssetResponseScopeMismatch();
  return result;
}
export async function getAssetHistory(tenant: string, assetId: string, cursor: string | null = null, signal?: AbortSignal): Promise<SnapshotPage> {
  const result = parseSnapshotList(await fetchJson(`${assetPath(assetId)}/snapshots?${pageQuery(cursor)}`, {}, signal), tenant, assetId);
  if (cursor !== null && result.next_cursor === cursor) throw new ApiProblem(502, "invalid_response", true);
  return result;
}
export async function getAssetSnapshot(tenant: string, assetId: string, snapshotId: string, signal?: AbortSignal): Promise<AssetSnapshot> {
  if (!isAssetIdentifier(snapshotId)) return invalidInput();
  const result = parseSnapshot(await fetchJson(`${assetPath(assetId)}/snapshots/${encodeURIComponent(snapshotId)}`, {}, signal), tenant, assetId);
  if (result.snapshot_id !== snapshotId.toLowerCase()) throw new AssetResponseScopeMismatch();
  return result;
}
export async function getAssetSnapshotSbom(tenant: string, snapshot: AssetSnapshot, signal?: AbortSignal): Promise<SnapshotSbom> {
  if (!isAssetIdentifier(snapshot.snapshot_id)) return invalidInput();
  return parseSnapshotSbom(await fetchJson(`${assetPath(snapshot.asset_id)}/snapshots/${encodeURIComponent(snapshot.snapshot_id)}/sbom`, {}, signal), tenant, snapshot);
}
export function parseCsvMapping(value: string): Record<string, string> {
  let parsed: unknown;
  try { parsed = JSON.parse(value); } catch { return invalidInput(); }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return invalidInput();
  const mapping: Record<string, string> = {};
  for (const [key, column] of Object.entries(parsed)) {
    if (!csvFields.some((field) => field === key) || typeof column !== "string" || !column || column.length > 4096 || /[\u0000-\u001f]/.test(column)) return invalidInput();
    mapping[key] = column;
  }
  if (!mapping.package_name || new Set(Object.values(mapping)).size !== Object.keys(mapping).length) return invalidInput();
  return mapping;
}

/** 发送浏览器原 File 字节；同源浏览器提供 Origin，复用会话 CSRF 与既有 no-store fetch。 */
export async function importAsset(tenant: string, request: AssetImportRequest, signal?: AbortSignal, isCurrent: () => boolean = () => true): Promise<AssetImportResult> {
  if (!(request.file instanceof File) || request.file.size < 1 || request.file.size > MAX_ASSET_UPLOAD_BYTES) throw new ApiProblem(413, "inventory_upload_size_limit", false);
  if (!request.displayName.trim() || [...request.displayName].length > 200 || !request.sourceVersion.trim() || [...request.sourceVersion].length > 200 || /[\u0000-\u001f]/.test(request.displayName + request.sourceVersion)) return invalidInput();
  if (!/T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(request.observedAt) || !Number.isFinite(Date.parse(request.observedAt))) return invalidInput();
  if (!/^[A-Za-z0-9_-]{1,200}$/.test(request.idempotencyKey)) return invalidInput();
  const query = new URLSearchParams({ display_name: request.displayName, source_version: request.sourceVersion, observed_at: request.observedAt, manifest_format: request.manifestFormat });
  if (request.assetId !== undefined) { assetPath(request.assetId); query.set("asset_id", request.assetId); }
  if (request.manifestFormat === "csv_components_v1") query.set("csv_column_mapping", JSON.stringify(parseCsvMapping(JSON.stringify(request.csvColumnMapping))));
  else if (!["json_manifest_v1", "cyclonedx_json", "spdx_json"].includes(request.manifestFormat) || request.csvColumnMapping !== undefined) return invalidInput();
  const token = await getCsrfToken(signal);
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const result = parseImportResult(await fetchJson(`/v1/asset-imports?${query}`, { method: "POST", headers: { "Content-Type": request.manifestFormat === "csv_components_v1" ? "text/csv" : "application/json", "X-CSRF-Token": token, "Idempotency-Key": request.idempotencyKey }, body: request.file }, signal), tenant);
  if ((request.manifestFormat === "cyclonedx_json" || request.manifestFormat === "spdx_json") && result.snapshot.source_kind !== request.manifestFormat) throw new AssetResponseScopeMismatch();
  if (request.assetId !== undefined && result.asset_id !== request.assetId.toLowerCase()) throw new AssetResponseScopeMismatch();
  return result;
}
