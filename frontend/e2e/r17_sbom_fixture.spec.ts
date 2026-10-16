import { expect, test, type Page } from "@playwright/test";
import { randomBytes } from "node:crypto";
import { sbomAsset, sbomFixture, sbomSnapshot } from "../tests/r17_sbom_fixture";
import { fixtureAssetId, fixtureTenant } from "../src/features/assets/synthetic-fixtures";

async function installFixture(page: Page, format: "cyclonedx_json" | "spdx_json" = "cyclonedx_json") {
  const state = { status: 200, wrongScope: false, many: false, hidden: false, hold: false, release: () => {}, paths: [] as string[], uploads: [] as Buffer[], formats: [] as string[], authenticated: true };
  const csrf = randomBytes(32).toString("hex");
  await page.route("**/v1/**", async (route) => {
    const request = route.request(); const url = new URL(request.url()); const path = url.pathname; state.paths.push(path);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") { status = state.authenticated ? 200 : 401; body = state.authenticated ? { user_id: "synthetic-sbom-admin", tenant_id: fixtureTenant, role: "tenant_admin", permissions: ["read:asset", "write:asset"], permission_version: 1, data_mode: "fixture", csrf_token: csrf } : { error: { code: "session_expired", retryable: false } }; }
    else if (path === "/v1/auth/csrf") body = { csrf_token: csrf, header_name: "X-CSRF-Token" };
    else if (path === "/v1/auth/logout") { state.authenticated = false; body = { status: "logged_out" }; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "explicit synthetic fixture", dependencies: {} };
    else if (path === "/v1/assets") body = { items: [{ ...sbomAsset(), snapshot: sbomSnapshot(2, format) }], next_cursor: null };
    else if (path === `/v1/assets/${fixtureAssetId}`) body = { ...sbomAsset(), snapshot: sbomSnapshot(2, format) };
    else if (path === `/v1/assets/${fixtureAssetId}/snapshots`) body = { items: [sbomSnapshot(2, format), sbomSnapshot(1, format)], next_cursor: null };
    else if (path.endsWith("/sbom")) {
      const number = path.includes(sbomSnapshot(1).snapshot_id) ? 1 : 2; const sbom = sbomFixture(number, format);
      if (number === 2 && state.hold) await new Promise<void>((resolve) => { state.release = resolve; });
      if (state.wrongScope) sbom.tenant_id = "wrong-synthetic-tenant";
      if (state.many) sbom.dependency_edges = Array.from({ length: 10000 }, (_, index) => ({ source_ref: "synthetic-root", target_ref: `synthetic-child-${index}`, relationship: "dependsOn", source_field_locator: `/dependencies/0/dependsOn/${index}` }));
      if (state.hidden) {
        const checksum = { algorithm: "SHA256", checksum_value: "a".repeat(64), source_field_locator: "/externalDocumentRefs/0/checksum" };
        sbom.external_documents = [{ document_ref: "DocumentRef-Public", document_uri: "https://example.com/synthetic.spdx.json", checksum, source_field_locator: "/externalDocumentRefs/0" }, { document_ref: "DocumentRef-Hidden", document_uri: null, checksum: { ...checksum, source_field_locator: "/externalDocumentRefs/1/checksum" }, source_field_locator: "/externalDocumentRefs/1" }];
        sbom.redactions = [{ source_field_locator: "/externalDocumentRefs/1/spdxDocument", reason: "unsafe_uri_or_path", replacement_ref: null }];
      }
      status = state.status; body = status === 200 ? sbom : { error: { code: status === 401 ? "session_expired" : status === 403 ? "permission_denied" : "inventory_unavailable", retryable: status === 503 } };
    } else if (path.endsWith(sbomSnapshot(1).snapshot_id)) body = sbomSnapshot(1, format);
    else if (path === "/v1/asset-imports") {
      if (request.headers()["x-csrf-token"] !== csrf || request.headers()["origin"] !== new URL(page.url()).origin) throw new Error("synthetic upload session fence failed");
      state.uploads.push(request.postDataBuffer() ?? Buffer.alloc(0)); state.formats.push(url.searchParams.get("manifest_format") ?? "");
      status = 201; body = { asset_id: fixtureAssetId, snapshot: { ...sbomSnapshot(), source_kind: url.searchParams.get("manifest_format") }, reused: false };
    } else throw new Error(`unexpected synthetic route ${path}`);
    await route.fulfill({ status, json: body });
  });
  return state;
}
async function clickVisible(page: Page, locator: ReturnType<Page["locator"]>) {
  await locator.scrollIntoViewIfNeeded(); const box = await locator.boundingBox();
  if (box === null) throw new Error("synthetic target is not visible");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}
test("synthetic dist SBOM 01: four explicit formats and exact original uploads", async ({ page }) => {
  const api = await installFixture(page); await page.goto("/#assets");
  const formats = ["json_manifest_v1", "csv_components_v1", "cyclonedx_json", "spdx_json"];
  const contents = [' {"format_version":1,"components":[]}\r\n', "package_name,ecosystem,version\r\nsynthetic,PyPI,1.0\r\n", ' {"bomFormat":"CycloneDX","specVersion":"1.6","components":[],"private":"file:///synthetic"}\r\n', ' {"spdxVersion":"SPDX-2.3","packages":[]}\r\n'];
  for (const [index, format] of formats.entries()) {
    const raw = contents[index]; if (raw === undefined) throw new Error("synthetic file missing");
    if ((await page.locator(".asset-import-panel").getAttribute("open")) === null) await clickVisible(page, page.locator(".asset-import-panel summary"));
    await page.getByLabel("清单格式", { exact: true }).selectOption(format);
    await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: format === "csv_components_v1" ? "synthetic.csv" : "synthetic.json", mimeType: format === "csv_components_v1" ? "text/csv" : "application/json", buffer: Buffer.from(raw) });
    await page.getByLabel("资产名称", { exact: true }).fill("Synthetic fixture · 资产工作台");
    await page.getByLabel("输入来源版本", { exact: true }).fill(`synthetic-${index}`);
    await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-16T07:00:00+08:00");
    await expect(page.getByText(/本地预览只读取结构/)).toBeVisible();
    await expect(page.getByText("file:///synthetic", { exact: true })).toHaveCount(0);
    await clickVisible(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
    await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
    await expect.poll(() => api.uploads.length).toBe(index + 1); expect(api.uploads[index]).toEqual(Buffer.from(raw));
  }
  expect(api.formats).toEqual(formats);
});
test("synthetic dist SBOM 02: history keeps fixed content and 390px keyboard reading", async ({ page }, info) => {
  const api = await installFixture(page); await page.setViewportSize({ width: 390, height: 844 }); await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText(sbomFixture().combined_semantic_sha256, { exact: true })).toBeVisible();
  const historical = page.getByRole("button", { name: /查看快照 #1 · 历史/ }); await historical.focus(); await page.keyboard.press("Enter");
  await expect(page.getByText(sbomFixture(1).combined_semantic_sha256, { exact: true })).toBeVisible();
  await expect(page.getByText(sbomFixture().combined_semantic_sha256, { exact: true })).toHaveCount(0);
  await expect(page.getByText(/此声明不证明授权资产安装范围完整/)).toBeVisible();
  expect(api.paths).toContain(`/v1/assets/${fixtureAssetId}/snapshots/${sbomSnapshot(1).snapshot_id}/sbom`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await page.screenshot({ path: info.outputPath("synthetic-sbom-history-390.png"), fullPage: true });
});
test("synthetic dist SBOM 03: 503 is partial and successful retry cannot imply verified safety", async ({ page }, info) => {
  const api = await installFixture(page); api.status = 503;
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByRole("heading", { name: "快照 #2" })).toBeVisible();
  await expect(page.getByRole("button", { name: "重试固定 SBOM 声明" })).toBeVisible();
  api.status = 200; await clickVisible(page, page.getByRole("button", { name: "重试固定 SBOM 声明" }));
  await expect(page.getByText(sbomFixture().combined_semantic_sha256, { exact: true })).toBeVisible();
  await expect(page.getByText("安全", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("synthetic-sbom-desktop.png"), fullPage: true });
});
test("synthetic dist SBOM 04: scope contradiction removes private DOM", async ({ page }) => {
  const api = await installFixture(page); api.hold = true;
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByRole("heading", { name: "快照 #2" })).toBeVisible();
  api.wrongScope = true; api.hold = false; api.release();
  await expect(page.getByText(/已清除私有资产工作区/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前授权资产" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "快照历史" })).toHaveCount(0);
  await expect(page.getByLabel("选择本地清单")).toHaveCount(0);
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
});
test("synthetic dist SBOM 05: 10000 declarations remain 20 rows and keyboard pages work", async ({ page }) => {
  const api = await installFixture(page); api.many = true;
  await page.goto(`/#assets/${fixtureAssetId}`); const table = page.getByRole("table", { name: "SBOM 原始关系声明" });
  await expect(table.locator("tbody tr")).toHaveCount(20);
  const next = page.getByRole("button", { name: "下一页依赖与标准关系" }); await next.focus(); await page.keyboard.press("Enter");
  await expect(page.getByText("synthetic-child-20", { exact: true })).toBeVisible(); await expect(table.locator("tbody tr")).toHaveCount(20);
  await expect(page.getByText("页 2 / 500", { exact: true })).toBeVisible();
});
test("synthetic dist SBOM 06: SPDX standard relations and safe external link preserve hidden URI", async ({ page }, info) => {
  const api = await installFixture(page, "spdx_json"); api.hidden = true;
  await page.goto(`/#assets/${fixtureAssetId}`); await expect(page.getByText("DEPENDS_ON", { exact: true })).toBeVisible();
  const publicLink = page.getByRole("link", { name: "打开服务器提供的公开文档 ↗" });
  await expect(publicLink).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  await expect(publicLink).toHaveAttribute("rel", "noopener noreferrer"); await expect(publicLink).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  await expect(page.locator("a[href^='file:'],a[href^='postgresql:']")).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("synthetic-spdx-hidden-document.png"), fullPage: true });
});
