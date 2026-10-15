import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiProblem } from "../../api/client";
import { getAsset, getAssetHistory, getAssetList, importAsset, parseCsvMapping } from "./asset-client";
import { assetFixture, fixtureAssetId, fixtureTenant, snapshotFixture } from "./synthetic-fixtures";

afterEach(() => vi.unstubAllGlobals());
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
describe("R17 authenticated asset client · synthetic", () => {
  it("uses current/history endpoints with encoded product/cursor and credentials no-store", async () => {
    const fetch = vi.fn(async (path: string) => response(path.includes("/snapshots") ? { items: [snapshotFixture()], next_cursor: null } : path.startsWith("/v1/assets?") ? { items: [assetFixture()], next_cursor: null } : assetFixture()));
    vi.stubGlobal("fetch", fetch);
    await getAssetList(fixtureTenant, "@synthetic/a+b", "server+/cursor");
    await getAsset(fixtureTenant, fixtureAssetId);
    await getAssetHistory(fixtureTenant, fixtureAssetId);
    const firstPath = fetch.mock.calls[0]?.[0];
    expect(firstPath).toContain("product=%40synthetic%2Fa%2Bb");
    expect(firstPath).toContain("cursor=server%2B%2Fcursor");
    expect(fetch).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });
  it("uploads exactly the original File with CSRF and stable Idempotency-Key", async () => {
    const file = new File([" {\"format_version\":1}\r\n"], "synthetic.json");
    const calls: { path: string; options: RequestInit | undefined }[] = [];
    const fetch = vi.fn(async (path: string, options?: RequestInit) => { calls.push({ path, options }); return response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-memory-csrf", header_name: "X-CSRF-Token" } : { asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: false }, path === "/v1/auth/csrf" ? 200 : 201); });
    vi.stubGlobal("fetch", fetch);
    await importAsset(fixtureTenant, { file, displayName: "Synthetic fixture", sourceVersion: "synthetic-v1", observedAt: "2026-10-15T10:00:00Z", manifestFormat: "json_manifest_v1", idempotencyKey: "synthetic-replay-key" });
    expect(fetch).toHaveBeenLastCalledWith(expect.stringContaining("/v1/asset-imports?"), expect.objectContaining({ body: file, credentials: "include" }));
    const call = calls[1];
    const options = call?.options;
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("synthetic-memory-csrf");
    expect(new Headers(options?.headers).get("Idempotency-Key")).toBe("synthetic-replay-key");
    expect(call?.path).not.toMatch(/tenant|role|server_path/);
  });
  it("rejects oversize, invalid timestamps/identities and stale session before write", async () => {
    const fetch = vi.fn(async () => response({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" }));
    vi.stubGlobal("fetch", fetch);
    const request = { file: new File(["synthetic"], "synthetic.json"), displayName: "Synthetic fixture", sourceVersion: "v1", observedAt: "2026-10-15T10:00:00Z", manifestFormat: "json_manifest_v1" as const, idempotencyKey: "synthetic-key" };
    await expect(importAsset(fixtureTenant, { ...request, file: new File([new Uint8Array(1048577)], "synthetic-big.json") })).rejects.toMatchObject({ status: 413 });
    await expect(importAsset(fixtureTenant, { ...request, observedAt: "2026-10-15T10:00:00" })).rejects.toMatchObject({ status: 422 });
    await expect(getAsset(fixtureTenant, "../../private")).rejects.toMatchObject({ status: 422 });
    expect(fetch).not.toHaveBeenCalled();
    await expect(importAsset(fixtureTenant, request, undefined, () => false)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("retains 403, 409, 422, 503 and malformed-response distinctions", async () => {
    for (const status of [403, 409, 422, 503]) {
      vi.stubGlobal("fetch", vi.fn(async () => response({ error: { code: "synthetic-boundary", retryable: status === 503 } }, status)));
      await expect(getAssetList(fixtureTenant)).rejects.toMatchObject({ status });
    }
    vi.stubGlobal("fetch", vi.fn(async () => response({ items: [], next_cursor: "same-cursor" })));
    await expect(getAssetList(fixtureTenant, "", "same-cursor")).rejects.toMatchObject({ status: 502 });
  });
  it("an append receipt must refer to the requested existing asset", async () => {
    vi.stubGlobal("fetch", vi.fn(async (path: string) => response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : { asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: false }, path === "/v1/auth/csrf" ? 200 : 201)));
    await expect(importAsset(fixtureTenant, { file: new File(["synthetic"], "synthetic.json"), displayName: "Synthetic fixture", sourceVersion: "v1", observedAt: "2026-10-15T10:00:00Z", manifestFormat: "json_manifest_v1", assetId: "a0000000-0000-4000-8000-000000000099", idempotencyKey: "synthetic-append-key" })).rejects.toMatchObject({ code: "invalid_response" });
  });
  it("validates explicit CSV mapping without reading server files", () => {
    expect(parseCsvMapping('{"package_name":"Name","version":"Version"}')).toEqual({ package_name: "Name", version: "Version" });
    for (const value of ['{}', '{"tenant_id":"Tenant","package_name":"Name"}', '{"package_name":"Name","version":"Name"}', '{"package_name":42}', 'broken']) expect(() => parseCsvMapping(value)).toThrow(ApiProblem);
  });
});
