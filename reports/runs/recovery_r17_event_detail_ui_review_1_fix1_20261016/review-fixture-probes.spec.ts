import { randomBytes } from "node:crypto";
import { writeFile } from "node:fs/promises";
import { expect, test, type Page } from "../../../frontend/node_modules/@playwright/test";
import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, fixtureRevisionId, historicalEvidenceFixture } from "../../../frontend/src/features/events/event-detail.fixture";

async function fixtureRoutes(page: Page, options: { empty?: boolean; holdDetail?: Promise<void>; evidenceMismatch?: boolean } = {}) {
  const requests: string[] = [];
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    requests.push(`${route.request().method()} ${path}`);
    let body: unknown;
    if (path === "/v1/auth/me") body = { user_id: "independent-r17-fixture-user", tenant_id: "independent-r17-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "independent isolated fixture", dependencies: {} };
    else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
    else if (path === `/v1/events/${fixtureEventId}`) {
      await options.holdDetail;
      body = options.empty ? { ...eventDetailFixture, dimensions: [], claims: [], revisions: [], event: { ...eventDetailFixture.event, freshness: "unknown" } } : eventDetailFixture;
    } else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) body = options.evidenceMismatch ? { ...historicalEvidenceFixture, revision_id: fixtureRevisionId } : historicalEvidenceFixture;
    else throw new Error(`Unexpected independent fixture request ${path}`);
    await route.fulfill({ status: 200, json: body });
  });
  return requests;
}

test("independent loading then empty schema2 detail remains unknown", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let release: () => void = () => { throw new Error("detail gate not set"); };
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const requests = await fixtureRoutes(page, { empty: true, holdDetail: gate });
  await page.goto(`/#events/${fixtureEventId}`);
  await expect(page.locator(".event-detail-loading")).toHaveAttribute("aria-busy", "true");
  await expect(page.locator(".dimension-value")).toHaveCount(0);
  await expect(page.getByRole("region", { name: "事件详情", exact: true })).not.toBeFocused();
  await page.getByRole("region", { name: "事件详情", exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath("loading-fixture-390.png") });
  release();
  await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
  await expect(page.getByText("未提供该维度", { exact: true })).toHaveCount(9);
  await expect(page.getByRole("heading", { name: "尚未取得事实记录", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "尚未取得修订记录", exact: true })).toBeVisible();
  await expect(page.getByText("事件时效未知；请结合来源版本与观测时间核查。", { exact: true })).toBeVisible();
  await expect(page.locator(".dimension-value")).toHaveCount(0);
  await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("empty-fixture-390.png"), fullPage: true });
  await writeFile(info.outputPath("get-caller-requests.json"), JSON.stringify(requests, null, 2));
});

for (const width of [1366, 390]) {
  test(`independent readable saved assertions and revisions ${width}px`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await fixtureRoutes(page);
    await page.goto(`/#events/${fixtureEventId}`);
    await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
    await page.getByRole("article", { name: "CWE 弱点", exact: true }).evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }));
    await page.screenshot({ path: info.outputPath(`conflict-hypothesis-fixture-${width}.png`) });
    const claims = page.getByRole("region", { name: "事实与来源断言", exact: true });
    await page.getByRole("button", { name: "事实与来源断言", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(claims).toBeFocused();
    await page.screenshot({ path: info.outputPath(`saved-assertions-fixture-${width}.png`) });
    await page.locator("#claim-10000000-0000-4000-8000-000000000009").evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }));
    await expect(page.getByText("完整条件：仅在启用插件时适用，不能删除此条件。", { exact: false }).first()).toBeVisible();
    await page.screenshot({ path: info.outputPath(`hypothesis-withdrawn-fixture-${width}.png`) });
    await page.getByRole("button", { name: "原文修订时间线", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("region", { name: "原文修订时间线", exact: true })).toBeFocused();
    await page.screenshot({ path: info.outputPath(`saved-revisions-fixture-${width}.png`) });
  });
}

test("independent revision mismatch keeps evidence error and no quote", async ({ page }, info) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  const requests = await fixtureRoutes(page, { evidenceMismatch: true });
  await page.goto(`/#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
  await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByRole("alert")).toBeVisible();
  await expect(page.locator("blockquote")).toHaveCount(0);
  await expect(page.getByRole("article", { name: "CVSS 评分", exact: true })).toBeVisible();
  await writeFile(info.outputPath("revision-mismatch-get-caller.json"), JSON.stringify(requests, null, 2));
});

test("independent narrow screen status and new fact navigation target", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const requests = await fixtureRoutes(page);
  await page.goto(`/#events/${fixtureEventId}`);
  await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
  for (const state of ["已取得", "未发现", "不适用", "有冲突", "受阻", "失败", "待处理"]) expect(await page.getByText(state, { exact: true }).count()).toBeGreaterThan(0);
  const hypothesis = page.getByRole("article", { name: "ATLAS 映射", exact: true });
  await expect(hypothesis.getByText("依据：模型假设", { exact: true })).toBeVisible();
  await expect(hypothesis.getByText("未核验", { exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "CWE 弱点", exact: true }).getByText("隔离来源 B：CWE-20", { exact: true })).toBeVisible();
  await expect(page.getByText("事件已标为过期；以下保留已保存的信息，不能当作当前结论。", { exact: true })).toBeVisible();
  const factButton = page.getByRole("article", { name: "CVSS 评分", exact: true }).getByRole("button", { name: "查看断言与依据", exact: true });
  await factButton.scrollIntoViewIfNeeded();
  await factButton.focus();
  const metrics = await factButton.evaluate((element) => ({ text: element.textContent, bounds: element.getBoundingClientRect().toJSON(), fontSize: getComputedStyle(element).fontSize, lineHeight: getComputedStyle(element).lineHeight, minHeight: getComputedStyle(element).minHeight, outline: getComputedStyle(element).outline, viewport: { width: window.innerWidth, height: window.innerHeight } }));
  await writeFile(info.outputPath("new-fact-target-metrics.json"), JSON.stringify({ metrics, requests }, null, 2));
  await page.screenshot({ path: info.outputPath("fact-button-focus-fixture-390.png") });
  await page.keyboard.press("Enter");
  await expect(page.locator("#claim-10000000-0000-4000-8000-000000000006")).toBeFocused();
  expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
  expect(metrics.bounds.height, "project design requires action touch targets at least 40px").toBeGreaterThanOrEqual(40);
});
