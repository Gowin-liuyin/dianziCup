import { afterEach, describe, expect, it, vi } from "vitest";
import { sbomFixture, sbomSnapshot } from "../../../tests/r17_sbom_fixture";
import { getAssetSnapshotSbom, importAsset, type AssetImportRequest } from "./asset-client";
import { AssetResponseScopeMismatch, type ManifestFormat } from "./asset-contracts";
import { fixtureAssetId, fixtureTenant, snapshotFixture } from "./synthetic-fixtures";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
afterEach(() => vi.unstubAllGlobals());
describe("R17 SBOM HTTP adapter · synthetic no backend", () => {
  it.each(["json_manifest_v1", "csv_components_v1", "cyclonedx_json", "spdx_json"] satisfies ManifestFormat[])("uploads original %s File bytes and exact manifest_format", async (format) => {
    const calls: { path: string; options: RequestInit | undefined }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => { calls.push({ path, options }); return response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : { asset_id: fixtureAssetId, snapshot: { ...snapshotFixture(), source_kind: format }, reused: false }, path === "/v1/auth/csrf" ? 200 : 201); }));
    const file = new File([" synthetic original bytes\r\n"], "synthetic-upload.json");
    await importAsset(fixtureTenant, { file, displayName: "synthetic", sourceVersion: "v1", observedAt: "2026-10-16T07:00:00+08:00", manifestFormat: format, idempotencyKey: "synthetic-key", ...(format === "csv_components_v1" ? { csvColumnMapping: { package_name: "Name" } } : {}) });
    const call = calls[1]; const path = new URL(call?.path ?? "", "http://synthetic.invalid");
    expect(path.pathname).toBe("/v1/asset-imports"); expect(path.searchParams.get("manifest_format")).toBe(format);
    expect(call?.options?.body).toBe(file); expect(call?.options?.credentials).toBe("include"); expect(call?.options?.cache).toBe("no-store");
    expect(new Headers(call?.options?.headers).get("Content-Type")).toBe(format === "csv_components_v1" ? "text/csv" : "application/json");
    expect(new Headers(call?.options?.headers).get("Idempotency-Key")).toBe("synthetic-key");
    expect(path.searchParams.has("tenant_id")).toBe(false);
  });
  it.each(["cyclonedx_json", "spdx_json"] as const)("rejects %s CSV mapping before CSRF or network IO", async (format) => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const request: AssetImportRequest = { file: new File(["synthetic"], "synthetic.json"), displayName: "synthetic", sourceVersion: "v1", observedAt: "2026-10-16T07:00:00Z", manifestFormat: format, idempotencyKey: "synthetic-key", csvColumnMapping: { package_name: "Name" } };
    await expect(importAsset(fixtureTenant, request)).rejects.toMatchObject({ status: 422 }); expect(fetch).not.toHaveBeenCalled();
  });
  it("requests exact fixed snapshot and refuses a different returned snapshot", async () => {
    const fetch = vi.fn(async () => response(sbomFixture(1)));
    vi.stubGlobal("fetch", fetch);
    await expect(getAssetSnapshotSbom(fixtureTenant, sbomSnapshot())).rejects.toBeInstanceOf(AssetResponseScopeMismatch);
    expect(fetch).toHaveBeenCalledWith(`/v1/assets/${fixtureAssetId}/snapshots/${sbomSnapshot().snapshot_id}/sbom`, expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });
  it.each([401, 403, 404, 503])("keeps HTTP %i separate from an empty successful sidecar", async (status) => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ error: { code: "synthetic-boundary", retryable: status === 503 } }, status)));
    await expect(getAssetSnapshotSbom(fixtureTenant, sbomSnapshot())).rejects.toMatchObject({ status });
  });
  it.each(["cyclonedx_json", "spdx_json"] as const)("rejects a different receipt source_kind after %s import", async (format) => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : { asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: false }, path === "/v1/auth/csrf" ? 200 : 201)));
    await expect(importAsset(fixtureTenant, { file: new File(["synthetic"], "synthetic.json"), displayName: "synthetic", sourceVersion: "v1", observedAt: "2026-10-16T07:00:00Z", manifestFormat: format, idempotencyKey: "synthetic-key" })).rejects.toBeInstanceOf(AssetResponseScopeMismatch);
  });
});
