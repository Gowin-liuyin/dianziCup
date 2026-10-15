import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, historicalEvidenceFixture } from "../src/features/events/event-detail.fixture";

async function installFixtureRoutes(page: Page, evidenceStatus = 200) {
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown;
    let status = 200;
    if (path === "/v1/auth/me") body = { user_id: "r17-detail-isolated-fixture-user", tenant_id: "r17-detail-isolated-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated R17 fixture", dependencies: {} };
    else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
    else if (path === `/v1/events/${fixtureEventId}`) body = eventDetailFixture;
    else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) {
      status = evidenceStatus;
      body = evidenceStatus === 200 ? historicalEvidenceFixture : { error: { code: "fixture_evidence_unavailable", retryable: true } };
    } else throw new Error(`Unexpected isolated R17 fixture route: ${path}`);
    await route.fulfill({ status, json: body });
  });
}

for (const width of [1366, 390]) {
  test(`R17 isolated fixture ${width}px dynamic dimension values and keyboard historical citation`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await installFixtureRoutes(page);
    await page.goto(`/#events/${fixtureEventId}`);
    await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
    const score = page.getByRole("article", { name: "CVSS 评分", exact: true });
    await expect(score.getByText("9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", { exact: true })).toBeVisible();
    await expect(page.locator(".dimension-row")).toHaveCount(9);
    await expect(page.getByRole("article", { name: "CWE 弱点", exact: true }).getByText("隔离来源 B：CWE-20", { exact: true })).toBeVisible();
    await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
    await score.getByText("展开原文摘录", { exact: true }).click();
    await expect(score.getByText("隔离 Fixture：评分来自已保存来源断言，不代表真实风险。", { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await page.locator(".dimension-value, .dimension-state-note, .event-context-metadata dd, .claim-row p, .revision-entry dd").evaluateAll((elements) => elements.every((element) => {
      const range = document.createRange(); range.selectNodeContents(element);
      return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
    }))).toBe(true);
    const factTargetMetrics = await page.locator(".dimension-fact-link").evaluateAll((elements) => elements.map((element) => ({ bounds: element.getBoundingClientRect().toJSON(), minHeight: getComputedStyle(element).minHeight })));
    expect(factTargetMetrics.length).toBeGreaterThan(0);
    for (const metrics of factTargetMetrics) {
      expect(metrics.bounds.height).toBeGreaterThanOrEqual(width === 390 ? 44 : 40);
      expect(metrics.minHeight).toBe(width === 390 ? "44px" : "40px");
    }
    await testInfo.attach(`fact-target-metrics-${width}`, { body: JSON.stringify({ width, factTargetMetrics }, null, 2), contentType: "application/json" });
    const factButton = score.getByRole("button", { name: "查看断言与依据", exact: true });
    await factButton.scrollIntoViewIfNeeded();
    await factButton.focus();
    await page.screenshot({ path: testInfo.outputPath(`fact-button-focus-fixture-${width}.png`), fullPage: false });
    await page.keyboard.press("Enter");
    await expect(page.locator("#claim-10000000-0000-4000-8000-000000000006")).toBeFocused();
    expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
    await page.getByRole("region", { name: "事件详情", exact: true }).evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }));
    await page.screenshot({ path: testInfo.outputPath(`detail-viewport-fixture-${width}.png`), fullPage: false });
    await page.screenshot({ path: testInfo.outputPath(`detail-fixture-${width}.png`), fullPage: true });
    const timelineButton = page.getByRole("button", { name: "原文修订时间线", exact: true });
    await timelineButton.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("region", { name: "原文修订时间线", exact: true })).toBeFocused();
    expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
    const oldRevision = page.getByRole("article", { name: `修订 1 ${fixtureOldRevisionId}`, exact: true });
    await expect(oldRevision.getByText("未知 / 未留存", { exact: true })).toHaveCount(4);
    const oldReference = oldRevision.getByRole("link", { name: "此修订的原文片段 [1]", exact: true });
    await oldReference.focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
    await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
    expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
    await expect(page.getByText("[12, 42)", { exact: true })).toBeVisible();
    await page.reload();
    await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
    await page.screenshot({ path: testInfo.outputPath(`historical-evidence-fixture-${width}.png`), fullPage: false });
    expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  });
}

test("R17 isolated fixture evidence dependency failure retains the other saved detail", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installFixtureRoutes(page, 503);
  await page.goto(`/#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
  const inspector = page.getByRole("complementary", { name: "证据检视", exact: true });
  await expect(inspector.getByRole("heading", { name: "依赖暂不可用", exact: true })).toBeVisible();
  await expect(page.getByRole("article", { name: "CVSS 评分", exact: true }).getByText("已取得", { exact: true })).toBeVisible();
  await expect(inspector.locator("blockquote")).toHaveCount(0);
  await expect(inspector.getByRole("button", { name: "重新查询", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await inspector.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("partial-evidence-failure-fixture-390.png"), fullPage: false });
});
