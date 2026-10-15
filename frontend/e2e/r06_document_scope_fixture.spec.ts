import { expect, test, type Page } from "@playwright/test";
import { detailFixture, documentFixture, documentId, evidenceFixture } from "../tests/document-fixture";

/** 仅浏览器内显式合成响应；等待已取消的延迟请求处理结束后检查不可见资料。 */
async function install(page: Page, status: number, allowFirstPage = false) {
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  let settled = 0;
  let started = 0;
  const cancelled = new Set<string>();
  page.on("requestfailed", (request) => { if (new URL(request.url()).pathname.startsWith(`/v1/documents/${documentId}`)) cancelled.add(request.url()); });
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname;
    let body: unknown; let responseStatus = 200;
    if (path === "/v1/auth/me") body = { user_id: "isolated-scope-browser", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
    else if (path === "/v1/documents") { if (!allowFirstPage || url.searchParams.has("cursor")) { responseStatus = status; body = { error: { code: status === 403 ? "forbidden" : "fixture_failure" } }; } else body = { schema_version: 2, items: [documentFixture], next_cursor: "isolated-scope-cursor", data_mode: "fixture" }; }
    else if (path.endsWith("/revisions")) { started += 1; await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
    else if (path === `/v1/documents/${documentId}`) { started += 1; await barrier; body = detailFixture; }
    else throw new Error(`Unexpected isolated scope browser request ${path}`);
    await route.fulfill({ status: responseStatus, json: body });
    if (path.startsWith(`/v1/documents/${documentId}`)) settled += 1;
  });
  return { release, cancelled, settled: () => settled, started: () => started };
}
async function expectPrivateContentAbsent(page: Page) {
  await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toHaveCount(0);
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveCount(0);
}
for (const status of [403, 401]) {
  test(`isolated catalog HTTP ${status} cancels deep-link inspection before late success`, async ({ page }, testInfo) => {
    const fixture = await install(page, status); await page.goto(`/#documents/${documentId}`);
    if (status === 403) await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
    else await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
    try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
    expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started()); await expectPrivateContentAbsent(page);
    await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath(`catalog-${status}-scope-cleared.png`), fullPage: true });
  });
}
test("isolated next-page catalog denial cancels old inspection", async ({ page }) => {
  const fixture = await install(page, 403, true); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "下一页资料", exact: true }).click();
  await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
  expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started()); await expectPrivateContentAbsent(page);
});
test("isolated catalog 503 keeps query failure distinct from readable detail", async ({ page }) => {
  const fixture = await install(page, 503); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByRole("heading", { name: "资料依赖暂不可用", exact: true })).toBeVisible(); fixture.release();
  expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started());
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0);
});
