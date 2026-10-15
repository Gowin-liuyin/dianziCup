import { randomBytes } from "node:crypto";
import type { Page } from "@playwright/test";
import { assetFixture, fixtureAssetId, fixtureTenant, snapshotFixture } from "../src/features/assets/synthetic-fixtures";

export async function installAssetsFixture(page: Page) {
  const api = {
    authenticated: true, tenant: fixtureTenant, permissions: ["read:asset", "write:asset"], assetStatus: 200, historyStatus: 200,
    empty: false, hold: false, release: () => {}, paged: false, importStatus: 201,
    paths: [] as string[], writeKeys: [] as string[], uploads: [] as Buffer[], appendAssetIds: [] as string[],
  };
  const csrf = randomBytes(32).toString("hex");
  await page.route("**/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname;
    api.paths.push(`${request.method()} ${path}`);
    let status = 200; let body: unknown;
    const asset = { ...assetFixture(), tenant_id: api.tenant, snapshot: { ...snapshotFixture(), tenant_id: api.tenant } };
    if (path === "/v1/auth/me") {
      status = api.authenticated ? 200 : 401;
      body = api.authenticated ? { user_id: "synthetic-assets-admin", tenant_id: api.tenant, role: "tenant_admin", permissions: api.permissions, permission_version: 1, data_mode: "fixture", csrf_token: csrf } : { error: { code: "session_expired", retryable: false } };
    } else if (path === "/v1/auth/csrf") body = { csrf_token: csrf, header_name: "X-CSRF-Token" };
    else if (path === "/v1/auth/logout") { api.authenticated = false; body = { status: "logged_out" }; }
    else if (path === "/v1/auth/login") { api.authenticated = true; body = { user_id: "synthetic-assets-admin", csrf_token: csrf, expires_at: "2026-10-16T23:00:00Z" }; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "synthetic-fixture-only", dependencies: {} };
    else if (path.startsWith("/v1/assets") && api.assetStatus !== 200) { status = api.assetStatus; body = { error: { code: status === 401 ? "session_expired" : status === 403 ? "permission_denied" : "inventory_unavailable", retryable: status === 503 } }; }
    else if (path === "/v1/assets") {
      if (api.hold) await new Promise<void>((resolve) => { api.release = resolve; });
      if (api.empty) body = { items: [], next_cursor: null };
      else if (url.searchParams.get("cursor") === "synthetic-next") {
        const secondId = "a0000000-0000-4000-8000-000000000003"; const secondSnapshot = "b0000000-0000-4000-8000-000000000003";
        body = { items: [{ ...asset, asset_id: secondId, display_name: "Synthetic fixture · 第二页资产", current_snapshot_id: secondSnapshot, snapshot: { ...asset.snapshot, asset_id: secondId, snapshot_id: secondSnapshot } }], next_cursor: null };
      } else body = { items: [asset], next_cursor: api.paged ? "synthetic-next" : null };
    } else if (path === `/v1/assets/${fixtureAssetId}`) body = asset;
    else if (path === `/v1/assets/${fixtureAssetId}/snapshots`) {
      status = api.historyStatus;
      body = status !== 200 ? { error: { code: "inventory_unavailable", retryable: true } } : { items: url.searchParams.has("cursor") ? [{ ...snapshotFixture(1), tenant_id: api.tenant }] : [asset.snapshot], next_cursor: url.searchParams.has("cursor") ? null : "synthetic-history-next" };
    } else if (path === `/v1/assets/${fixtureAssetId}/snapshots/b0000000-0000-4000-8000-000000000001`) body = { ...snapshotFixture(1), tenant_id: api.tenant };
    else if (path === "/v1/asset-imports") {
      const appendAssetId = url.searchParams.get("asset_id");
      if (appendAssetId !== null) { if (appendAssetId !== fixtureAssetId || url.searchParams.get("display_name") !== asset.display_name) throw new Error("synthetic append identity mismatch"); api.appendAssetIds.push(appendAssetId); }
      api.writeKeys.push(request.headers()["idempotency-key"] ?? "");
      api.uploads.push(request.postDataBuffer() ?? Buffer.alloc(0));
      if (request.headers()["x-csrf-token"] !== csrf || request.headers()["origin"] !== new URL(page.url()).origin || url.searchParams.has("tenant_id") || url.searchParams.has("role") || url.searchParams.has("server_path")) throw new Error("synthetic upload boundary mismatch");
      status = api.importStatus;
      body = status === 201 ? { asset_id: fixtureAssetId, snapshot: asset.snapshot, reused: false } : { error: { code: status === 503 ? "inventory_unavailable" : "invalid_csv_columns", retryable: status === 503 } };
    } else throw new Error(`unexpected synthetic fixture route ${request.method()} ${path}`);
    await route.fulfill({ status, json: body });
  });
  return api;
}
