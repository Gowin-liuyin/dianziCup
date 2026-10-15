import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { questionAnswerFixture, questionFixtureIds as ids } from "../src/features/questions/question.fixture";

/** 此文件只运行显式隔离fixture，所有/v1请求被路由隔离，不作为live问答证明。 */
async function setupFixture(page: Page, options: { unknownFirst?: boolean; status?: number; code?: string; freshness?: string; anonymous?: boolean; longText?: boolean } = {}) {
  const csrf = randomBytes(32).toString("hex");
  const posts: { body: string | null; key: string | undefined }[] = [];
  await page.route("**/v1/**", async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname;
    const send = async (body: unknown, status = 200) => route.fulfill({ status, contentType: status >= 400 ? "application/problem+json" : "application/json", body: JSON.stringify(body) });
    if (path === "/v1/auth/me") return options.anonymous ? send({ error: { code: "session_expired" } }, 401) : send({ user_id: "isolated-browser-question-user", tenant_id: "isolated-browser-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf });
    if (path === "/v1/auth/csrf") return send({ csrf_token: csrf, header_name: "X-CSRF-Token" });
    if (path === "/v1/health/live") return send({ status: "live" });
    if (path === "/v1/health/ready") return send({ status: "ready", reason: "isolated browser fixture", dependencies: {} });
    if (path === "/v1/questions") {
      expect(request.method()).toBe("POST"); expect(request.headers()["x-csrf-token"]).toBe(csrf);
      posts.push({ body: request.postData(), key: request.headers()["idempotency-key"] });
      if (options.unknownFirst && posts.length === 1) return route.abort("failed");
      if (options.status) return send({ type: "about:blank", title: "isolated failure", status: options.status, error: { code: options.code, retryable: true, message: "private upstream must not display" } }, options.status);
      const answer = questionAnswerFixture();
      if (options.longText) { answer.answer_text = "长文本边界".repeat(800); answer.citations[0] = { evidence_id: ids.evidence, revision_id: ids.revision, quote: "<img src=x onerror=alert('isolated')>" + "长原文".repeat(800), locator: "very-long-locator-".repeat(30), source_uri: "https://example.test/advisory" }; }
      return send({ ...answer, freshness: options.freshness ?? "current" });
    }
    if (path === `/v1/answers/${ids.answer}`) return send({ ...questionAnswerFixture(), freshness: "stale" });
    if (path === "/v1/events") return send({ schema_version: 2, items: [], next_cursor: null, data_mode: "fixture" });
    if (path === `/v1/events/${ids.event}`) return send({ schema_version: 2, event: { event_id: ids.event, event_type: "advisory", title: "隔离浏览器事件", external_ids: [], primary_product_ids: [], first_seen_at: "2026-10-15T07:00:00Z", status: "active", source_count: 1, latest_revision_id: ids.revision, freshness: "current" }, dimensions: [], revisions: [], claims: [], data_mode: "fixture" });
    if (path === `/v1/evidence/${ids.evidence}`) return send({ schema_version: 2, span_id: ids.evidence, revision_id: ids.revision, block_id: null, start_offset: 0, end_offset: 18, quote_text: "隔离原文：仅在指定条件下适用。", quote_sha256: "a".repeat(64), locator_kind: "text", page_number: null, json_pointer: null, verified_at: "2026-10-15T07:00:00Z", source_uri: "https://example.test/advisory", source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" });
    throw new Error(`Unexpected route in isolated question browser fixture: ${path}`);
  });
  await page.goto(`/#questions/${ids.event}`);
  return posts;
}
async function ask(page: Page) { await page.getByLabel("你的问题", { exact: true }).fill("请核对风险机制与限制"); await page.getByRole("button", { name: "提交问题", exact: true }).click(); }

test("R05 fixture C01/C03/C05 desktop answer, keyboard citation and fixed revision evidence", async ({ page }, testInfo) => {
  const posts = await setupFixture(page); await expect(page.getByRole("heading", { name: "尚未提出问题" })).toBeVisible(); await ask(page);
  await expect(page.getByRole("article", { name: "完整证据回答" })).toBeVisible(); expect(posts).toHaveLength(1);
  expect(JSON.parse(posts[0]?.body ?? "null")).toEqual({ question: "请核对风险机制与限制", mode: "library", event_ids: [ids.event] });
  await expect(page.getByText("1234 毫秒 · 完整回答耗时", { exact: true })).toBeVisible(); await expect(page.getByRole("article", { name: "完整证据回答" }).getByText("合成 / Fixture · 隔离数据", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "依据 [1]", exact: true }).first().focus(); await page.keyboard.press("Enter"); await expect(page.locator(`#citation-${ids.evidence}`)).toBeFocused();
  await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath("fixture-question-desktop-1280.png"), fullPage: true });
  await page.getByRole("link", { name: "检视固定修订证据 [1] →", exact: true }).click(); await expect(page.getByRole("heading", { name: "证据检视", exact: true })).toBeVisible(); await expect(page.getByText("隔离原文：仅在指定条件下适用。", { exact: true })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "证据检视" })).toBeFocused(); await expect(page.getByRole("complementary", { name: "证据检视" }).getByText(ids.revision, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "基于此事件提问 →", exact: true }).click(); await expect(page.getByLabel("事件标识", { exact: true })).toHaveValue(ids.event);
});

test("R05 fixture C04/C06 390px, reduced motion, unknown retry, saved answer freshness", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 }); await page.emulateMedia({ reducedMotion: "reduce" }); const posts = await setupFixture(page, { unknownFirst: true }); await ask(page); await expect(page.getByRole("alert")).toContainText("提交结果未确认");
  await page.getByRole("button", { name: "原样重试本轮", exact: true }).focus(); await page.keyboard.press("Enter"); await expect(page.getByRole("article", { name: "完整证据回答" })).toBeVisible(); expect(posts).toHaveLength(2); expect(posts[1]).toEqual(posts[0]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.getByTestId("ambient-motion").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath("fixture-question-mobile-390-reduced.png"), fullPage: true });
  await page.getByRole("button", { name: "查询 / 刷新回答", exact: true }).click(); await expect(page.getByText(/这是已过期回答/)).toBeVisible();
  await page.reload(); await expect(page.getByRole("heading", { name: "尚未提出问题" })).toBeVisible(); await page.getByLabel("回答标识", { exact: true }).fill(ids.answer); await page.getByRole("button", { name: "查询 / 刷新回答", exact: true }).click(); await expect(page.getByText(/这是已过期回答/)).toBeVisible();
  await expect(page.getByRole("link", { name: /检视固定修订证据/ })).toHaveCount(0); expect(posts).toHaveLength(2);
});

for (const scenario of [{ status: 403, code: "permission_denied", text: "没有问答或回答查看权限" }, { status: 409, code: "answer_in_progress", text: "仍在处理中" }, { status: 429, code: "question_capacity_busy", text: "繁忙或已达到限额" }, { status: 503, code: "question_models_not_configured", text: "生成模型尚未配置" }, { status: 503, code: "answer_evidence_unavailable", text: "合法证据不足" }]) {
  test(`R05 fixture C02 ${scenario.status}/${scenario.code} visible without fake answer`, async ({ page }) => { const posts = await setupFixture(page, scenario); await ask(page); await expect(page.getByRole("alert")).toContainText(scenario.text); await expect(page.getByRole("article", { name: "完整证据回答" })).toHaveCount(0); expect(posts).toHaveLength(1); await expect(page.getByText(/private upstream/)).toHaveCount(0); });
}
test("R05 fixture C06 anonymous is explicit and performs no question request", async ({ page }) => { const posts = await setupFixture(page, { anonymous: true }); await expect(page.getByRole("heading", { name: "登录后使用证据问答", exact: true })).toBeVisible(); expect(posts).toHaveLength(0); });
test("R05 fixture C05 long text and HTML remain readable text at 390px", async ({ page }) => { await page.setViewportSize({ width: 390, height: 844 }); await setupFixture(page, { longText: true }); await ask(page); await expect(page.getByRole("article", { name: "完整证据回答" })).toBeVisible(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true); await expect(page.locator("img")).toHaveCount(0); await expect(page.getByRole("blockquote")).toContainText("<img src=x onerror=alert('isolated')>"); });
