import { expect, test, type Locator, type Page } from "@playwright/test";
import { assetFixture, fixtureAssetId } from "../src/features/assets/synthetic-fixtures";
import { installAssetsFixture } from "./r17-assets.fixture";

async function mouseClick(page: Page, target: Locator) {
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  if (box === null) throw new Error("fixture interaction target is not visible");
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}
async function fillImport(page: Page, raw: string, format = "json_manifest_v1") {
  await mouseClick(page, page.locator(".asset-import-panel summary"));
  await page.getByLabel("清单格式", { exact: true }).selectOption(format);
  await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: format === "json_manifest_v1" ? "synthetic-fixture.json" : "synthetic-fixture.csv", mimeType: format === "json_manifest_v1" ? "application/json" : "text/csv", buffer: Buffer.from(raw) });
  await page.getByLabel("资产名称", { exact: true }).fill("Synthetic fixture · 资产工作台");
  await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-v1");
  await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-15T10:00:00Z");
  await expect(page.getByRole("button", { name: "提交授权清单", exact: true })).toBeEnabled();
}

test("synthetic Edge assets 01: loading and empty remain distinguishable", async ({ page }, info) => {
  const api = await installAssetsFixture(page); api.hold = true; api.empty = true;
  await page.goto("/#assets");
  await expect(page.getByText("正在读取资产页…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "刷新资产与快照" })).toBeDisabled();
  await page.screenshot({ path: info.outputPath("synthetic-loading.png") });
  api.hold = false; api.release();
  await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  await expect(page.getByText(/空查询不等于零影响或安全/)).toBeVisible();
  await mouseClick(page, page.locator(".asset-import-panel summary"));
  await expect(page.getByLabel("选择本地清单")).toBeVisible();
  await page.screenshot({ path: info.outputPath("synthetic-empty-import.png") });
});

test("synthetic Edge assets 02: 403 clears catalog and viewer gate makes no private request", async ({ page }, info) => {
  const api = await installAssetsFixture(page);
  await page.goto("/#assets"); await expect(page.getByRole("link", { name: new RegExp(assetFixture().display_name) })).toBeVisible();
  api.assetStatus = 403; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  await expect(page.getByText(/当前会话没有此项资产权限/)).toBeVisible();
  await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("synthetic-403.png") });
  api.permissions = ["read:public"]; api.paths.length = 0; await page.reload();
  await expect(page.getByText("当前会话无资产读取权限", { exact: true })).toBeVisible();
  expect(api.paths.some((path) => path.includes("/v1/assets"))).toBe(false);
});

test("synthetic Edge assets 03: JSON original bytes import 201 and server UUID deep-link refresh", async ({ page }, info) => {
  const api = await installAssetsFixture(page); api.empty = true;
  await page.goto("/#assets"); await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  const raw = ' {"format_version":1,"components":[],"inventory_completeness":"unknown"}\r\n';
  await fillImport(page, raw); api.empty = false;
  await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`#assets/${fixtureAssetId}$`));
  expect(api.uploads).toEqual([Buffer.from(raw)]);
  expect(api.writeKeys[0]).toMatch(/^[0-9a-f-]{36}$/);
  await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: info.outputPath("synthetic-import-success.png"), fullPage: true });
  await page.reload(); await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  await mouseClick(page, page.locator(".asset-import-panel summary"));
  await mouseClick(page, page.getByLabel("追加到当前所选资产（名称保持一致）", { exact: true }));
  await expect(page.getByLabel("资产名称", { exact: true })).toBeDisabled();
  await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: "synthetic-append.json", mimeType: "application/json", buffer: Buffer.from(raw) });
  await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-append-v2");
  await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-15T11:00:00Z");
  await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
  expect(api.appendAssetIds).toEqual([fixtureAssetId]);
  await mouseClick(page, page.getByRole("link", { name: "返回资产列表", exact: true }));
  await expect(page).toHaveURL(/#assets$/); await page.goBack();
  await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
});

test("synthetic Edge assets 04: history pages fixed snapshot partial failure and retry at 390px", async ({ page }, info) => {
  const api = await installAssetsFixture(page); api.historyStatus = 503;
  await page.setViewportSize({ width: 390, height: 844 }); await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/#assets/${fixtureAssetId}`);
  await expect(page.getByRole("heading", { name: "快照 #2", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "重试历史页", exact: true })).toBeVisible();
  api.historyStatus = 200; await mouseClick(page, page.getByRole("button", { name: "重试历史页", exact: true }));
  await mouseClick(page, page.getByRole("button", { name: "加载更多历史", exact: true }));
  await mouseClick(page, page.getByRole("button", { name: /查看快照 #1 · 历史/ }));
  await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  await expect(page.getByText("1.9.0", { exact: true })).toBeVisible();
  await expect(page.getByText("pkg:pypi/synthetic-demo-package@1.9.0", { exact: true })).toBeVisible();
  await expect(page.getByText("/components/0", { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("synthetic-history-390.png"), fullPage: false });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  const targets = await page.locator(".asset-workspace button:not(:disabled), .asset-workspace summary, .asset-workspace .asset-catalog-link").evaluateAll((elements) => elements.filter((element) => element.getClientRects().length > 0).map((element) => element.getBoundingClientRect().height));
  expect(targets.every((height) => height >= 44)).toBe(true);
  await mouseClick(page, page.getByRole("button", { name: "查看当前快照", exact: true }));
  await expect(page.getByText("版本未知", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪" })).toBeDisabled();
});

test("synthetic Edge assets 05: CSV errors and uncertain import reuse the same key and bytes", async ({ page }, info) => {
  const api = await installAssetsFixture(page); api.importStatus = 422;
  await page.goto("/#assets"); await expect(page.locator(".asset-import-panel summary")).toBeVisible();
  const raw = "package_name,ecosystem,version\r\nsynthetic-demo-package,PyPI,1.9.0\r\n";
  await fillImport(page, raw, "csv_components_v1");
  await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  await expect(page.getByText(/CSV 表头与映射列名不一致/)).toBeVisible();
  await page.screenshot({ path: info.outputPath("synthetic-csv-field-error.png") });
  await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-v2");
  api.importStatus = 503; await mouseClick(page, page.getByRole("button", { name: "提交授权清单", exact: true }));
  await expect(page.getByRole("button", { name: "重试相同导入", exact: true })).toBeVisible();
  api.importStatus = 201; await mouseClick(page, page.getByRole("button", { name: "重试相同导入", exact: true }));
  await expect(page.getByText("导入成功 · 服务端已保存快照", { exact: true })).toBeVisible();
  expect(api.writeKeys[1]).toBe(api.writeKeys[2]); expect(api.writeKeys[0]).not.toBe(api.writeKeys[1]);
  expect(api.uploads.every((bytes) => bytes.equals(Buffer.from(raw)))).toBe(true);
});

test("synthetic Edge assets 06: paging logout expired session and cross-tenant late response stay isolated", async ({ page }, info) => {
  const api = await installAssetsFixture(page); api.paged = true;
  await page.goto("/#assets");
  await mouseClick(page, page.getByRole("button", { name: "加载更多资产", exact: true }));
  await expect(page.getByRole("link", { name: /第二页资产/ })).toBeVisible();
  api.hold = true; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  await expect(page.getByText("正在读取资产页…", { exact: true })).toBeVisible();
  await mouseClick(page, page.getByRole("link", { name: "会话与权限", exact: true }));
  await mouseClick(page, page.getByRole("button", { name: "退出登录", exact: true }));
  api.hold = false; api.release();
  await mouseClick(page, page.getByRole("link", { name: "资产自查", exact: true }));
  await expect(page.getByText("登录后查看授权资产", { exact: true })).toBeVisible();
  await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("synthetic-logout-cleared.png") });
  api.authenticated = true; api.tenant = "synthetic-assets-other-tenant"; api.empty = true; await page.reload();
  await expect(page.getByText("尚无可见资产清单", { exact: true })).toBeVisible();
  await expect(page.getByText(assetFixture().display_name, { exact: true })).toHaveCount(0);
  api.assetStatus = 401; await mouseClick(page, page.getByRole("button", { name: "刷新资产与快照" }));
  await expect(page.getByText("会话已失效，私有资产已清除", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
});
