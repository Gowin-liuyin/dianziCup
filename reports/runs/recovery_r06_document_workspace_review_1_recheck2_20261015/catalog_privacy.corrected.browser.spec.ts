import { expect, test, type Page } from "../../../frontend/node_modules/@playwright/test/index.mjs";
import { documentFixture, detailFixture, documentId, evidenceFixture } from "../../../frontend/tests/document-fixture";

async function install(page: Page, status: number, action?: "search" | "next_page" | "retry") {
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  let started = 0;
  let settled = 0;
  const cancelled: string[] = [];
  const paths: string[] = [];
  let retryDenied = false;
  page.on("requestfailed", (request) => { if (new URL(request.url()).pathname.startsWith(`/v1/documents/${documentId}`)) cancelled.push(request.url()); });
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname; paths.push(path + url.search);
    let body: unknown; let responseStatus = 200;
    let delayed = false;
    if (path === "/v1/auth/me") body = { user_id: "isolated-corrected-probe", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
    else if (path === "/v1/documents") {
      const denyingQuery = !action || action === "retry" || (action === "search" ? url.searchParams.has("q") : url.searchParams.has("cursor"));
      if (denyingQuery) { responseStatus = action === "retry" && !retryDenied ? 503 : status; body = { error: { code: responseStatus === 403 ? "forbidden" : "fixture_failure" } }; }
      else body = { schema_version: 2, items: [documentFixture], next_cursor: "isolated-corrected-cursor", data_mode: "fixture" };
    } else if (path.endsWith("/revisions")) { delayed = true; started += 1; await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
    else if (path === `/v1/documents/${documentId}`) { delayed = true; started += 1; await barrier; body = detailFixture; }
    else throw new Error(`Unexpected fixture ${path}`);
    try { await route.fulfill({ status: responseStatus, json: body }); }
    finally { if (delayed) settled += 1; }
  });
  return { paths, cancelled, release, denyRetry: () => { retryDenied = true; }, started: () => started, settled: () => settled };
}

async function expectAbsent(page: Page) {
  await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toHaveCount(0);
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveCount(0);
  await expect(page.locator(".document-detail-body,.document-evidence,.document-history")).toHaveCount(0);
}

for (const [status, action] of [[403, undefined], [401, undefined], [403, "search"], [403, "next_page"], [403, "retry"]] as const) {
  test(`Corrected isolated fixture: catalog ${status}/${action ?? "deep_link"} cancels and fences released late success`, async ({ page }, testInfo) => {
    const fixture = await install(page, status, action); await page.goto(`/#documents/${documentId}`);
    await expect.poll(fixture.started).toBeGreaterThanOrEqual(2);
    if (action) {
      if (action === "retry") { await expect(page.getByRole("heading", { name: "资料依赖暂不可用", exact: true })).toBeVisible(); fixture.denyRetry(); await page.getByRole("button", { name: "重新查询资料", exact: true }).click(); }
      else if (action === "search") { await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible(); await page.getByLabel("检索关键词", { exact: true }).fill("independent-query"); await page.getByRole("button", { name: "检索资料", exact: true }).click(); }
      else await page.getByRole("button", { name: "下一页资料", exact: true }).click();
    }
    if (status === 401) await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
    else await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
    try { await expect.soft.poll(() => fixture.cancelled.length).toBeGreaterThanOrEqual(fixture.started()); }
    finally { fixture.release(); }
    await expect.poll(fixture.settled).toBe(fixture.started());
    await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    await expectAbsent(page);
    await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath(`catalog-${status}-${action ?? "deep_link"}-corrected.png`), fullPage: true });
    await testInfo.attach("corrected-probe-observation", { body: JSON.stringify({ paths: fixture.paths, started: fixture.started(), settled: fixture.settled(), cancelled: fixture.cancelled.length, contentVisiblePrecondition: false, mode: "isolated fixture only" }), contentType: "application/json" });
  });
}

test("Corrected isolated fixture: catalog 503 permits valid detail and preserves partial meaning", async ({ page }, testInfo) => {
  const fixture = await install(page, 503); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByRole("heading", { name: "资料依赖暂不可用", exact: true })).toBeVisible();
  await expect.poll(fixture.started).toBeGreaterThanOrEqual(2); fixture.release(); await expect.poll(fixture.settled).toBe(fixture.started());
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toBeVisible();
  await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0);
  await expect(page.getByText("覆盖：仅摘要。未保存完整正文。", { exact: true })).toBeVisible();
  await testInfo.attach("503-probe-observation", { body: JSON.stringify({ started: fixture.started(), settled: fixture.settled(), mode: "isolated fixture only" }), contentType: "application/json" });
});
