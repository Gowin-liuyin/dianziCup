import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const eventId = "00000000-0000-4000-8000-000000000001";
const revisionId = "00000000-0000-4000-8000-000000000002";
const evidenceId = "00000000-0000-4000-8000-000000000003";
const claimId = "00000000-0000-4000-8000-000000000004";
const eventFixture = { event_id: eventId, event_type: "advisory", title: "隔离 Fixture：历史公告与证据核查", external_ids: ["FIXTURE-ONLY"], primary_product_ids: [], first_seen_at: "2026-10-15T02:00:00Z", status: "active", source_count: 2, latest_revision_id: revisionId, freshness: "stale" };
const detailFixture = { schema_version: 2, event: eventFixture, dimensions: [{ dimension: "versions", status: "available", claim_ids: [claimId], citations: [{ evidence_id: evidenceId, revision_id: revisionId, quote: "隔离原文：仅用于检验界面，不代表真实事件。", locator: "Unicode [12, 37)", source_uri: "https://example.test/fixture-revision" }], freshness: "stale", observed_at: null, source_version: null, error_code: null }, { dimension: "poc", status: "failed", claim_ids: [], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: "fixture_upstream_failure" }], revisions: [{ revision_id: revisionId, document_id: eventId, revision_number: 1, source_id: evidenceId, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "legacy_unverified", document_kind: "advisory", canonical_uri: null }], claims: [{ claim_id: claimId, predicate: "isolated_statement", display_value: "隔离模型假设：条件尚未证实；不能视为已确认影响。", origin: "model_hypothesis", status: "unverified", source_revision_id: revisionId, evidence_ids: [evidenceId] }], data_mode: "fixture" };
const evidenceFixture = { schema_version: 2, span_id: evidenceId, revision_id: revisionId, block_id: null, start_offset: 12, end_offset: 37, quote_text: "隔离原文：仅用于检验界面，不代表真实事件。", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };

/** 全部请求在本测试进程隔离拦截；产品无fixture开关，失败不会替换成样本。 */
async function installFixtureRoutes(page: Page, options: { status?: number; delayed?: boolean } = {}) {
  let releaseList = () => {};
  const listBarrier = new Promise<void>((resolve) => { releaseList = resolve; });
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    let status = 200;
    if (path === "/v1/auth/me") body = { user_id: "isolated-fixture-user", tenant_id: "isolated-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture only", dependencies: {} };
    else if (path === "/v1/events") {
      if (options.delayed) await listBarrier;
      status = options.status ?? 200;
      body = status === 200 ? { schema_version: 2, items: [eventFixture], next_cursor: null, data_mode: "fixture" } : { error: { code: status === 401 ? "unauthenticated" : "dependency_unavailable", retryable: status === 503 } };
    } else if (path === `/v1/events/${eventId}`) body = detailFixture;
    else if (path === `/v1/evidence/${evidenceId}`) body = evidenceFixture;
    else throw new Error(`Unexpected isolated R04 fixture route: ${path}`);
    await route.fulfill({ status, json: body });
  });
  return { releaseList };
}

for (const width of [1366, 390]) {
  test(`R04 isolated fixture ${width}px list, nine dimensions and historical evidence`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await installFixtureRoutes(page);
    await page.goto("/#events");
    const record = page.getByRole("link", { name: eventFixture.title, exact: true });
    await expect(record).toBeVisible();
    await expect(page.getByText("本页 1 条 · 合成 / Fixture", { exact: true })).toBeVisible();
    await record.focus();
    await page.keyboard.press("Enter");
    await expect(page.locator(".dimension-row")).toHaveCount(9);
    await expect(page.getByText("模型假设", { exact: true })).toBeVisible();
    await expect(page.getByText("未提供该维度", { exact: true })).toHaveCount(7);
    await page.getByRole("link", { name: "查看引用：Unicode [12, 37)", exact: true }).click();
    await expect(page.locator("blockquote")).toHaveText(evidenceFixture.quote_text);
    await expect(page.getByText("历史定位未核验", { exact: true })).toBeVisible();
    await expect(page.getByText("[12, 37)", { exact: true })).toBeVisible();
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
    const evidenceHeading = await page.getByRole("heading", { name: "证据检视", exact: true }).boundingBox();
    expect(evidenceHeading?.y).toBeGreaterThanOrEqual(0);
    expect(evidenceHeading?.y).toBeLessThan(width === 390 ? 844 : 900);
    await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    const readableText = page.locator(".evidence-body blockquote, .evidence-metadata dd, .claim-row p");
    expect(await readableText.evaluateAll((elements) => elements.every((element) => {
      const range = document.createRange();
      range.selectNodeContents(element);
      return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
    }))).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`r04-isolated-fixture-${width}.png`), fullPage: true });
  });
}

test("R04 isolated fixture delayed loading and 503 preserve an explicit failure", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const routes = await installFixtureRoutes(page, { status: 503, delayed: true });
  await page.goto("/#events");
  await expect(page.getByText("正在查询授权范围内的事件…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "检索情报", exact: true })).toBeDisabled();
  routes.releaseList();
  await expect(page.getByRole("heading", { name: "依赖暂不可用", exact: true })).toBeVisible();
  const explanation = page.getByText("当前查询失败，不能据此判断为空或无风险。已有记录需重新取得后展示。", { exact: true });
  expect(await explanation.evaluate((element) => {
    const range = document.createRange(); range.selectNodeContents(element);
    return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  })).toBe(true);
  await expect(page.getByText(/本页 0 条/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: eventFixture.title, exact: true })).toHaveCount(0);
  await expect(page.getByText("合成 / Fixture", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("r04-isolated-fixture-503-390.png"), fullPage: true });
});

test("R04 isolated fixture business 401 clears identity without auth restore loop", async ({ page }, testInfo) => {
  let snapshotRequests = 0;
  let businessRequests = 0;
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (path === "/v1/auth/me") snapshotRequests += 1;
    if (path === "/v1/events") businessRequests += 1;
  });
  const routes = await installFixtureRoutes(page, { status: 401, delayed: true });
  await page.goto("/#events");
  await expect(page.getByText("正在查询授权范围内的事件…", { exact: true })).toBeVisible();
  const initialSnapshotRequests = snapshotRequests;
  const initialBusinessRequests = businessRequests;
  expect(initialSnapshotRequests).toBe(2);
  expect(initialBusinessRequests).toBeGreaterThan(0);
  routes.releaseList();
  await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  await expect(page.getByText("isolated-fixture-user", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: eventFixture.title, exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "重新登录", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "重新登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "访问控制", exact: true })).toBeVisible();
  expect(snapshotRequests).toBe(initialSnapshotRequests);
  expect(businessRequests).toBe(initialBusinessRequests);
  await testInfo.attach("fixture-401-request-counts", { body: JSON.stringify({ initialSnapshotRequests, initialBusinessRequests, finalSnapshotRequests: snapshotRequests, finalBusinessRequests: businessRequests, developmentStrictMode: true }), contentType: "application/json" });
});
