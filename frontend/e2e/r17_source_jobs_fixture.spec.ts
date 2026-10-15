import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

const jobId = "00000000-0000-4000-8000-000000000001";
const csrf = randomBytes(32).toString("hex");
const jobFixture = { job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null };

/** 本文件所有管理和身份请求仅在浏览器内隔离拦截，不连接实际来源或产品账号。 */
async function installFixture(page: Page, options: { denied?: boolean; firstWriteUnknown?: boolean; expireLookup?: boolean; delayedCsrf?: boolean } = {}) {
  const writes: { body: string; key: string; csrfPresent: boolean; path: string }[] = [];
  let lookupCount = 0;
  let releaseCsrf = () => {};
  const csrfBarrier = new Promise<void>((resolve) => { releaseCsrf = resolve; });
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    let status = 200;
    let body: unknown;
    if (path === "/v1/auth/me") body = { user_id: "isolated-source-fixture-admin", tenant_id: null, role: options.denied ? "analyst" : "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
    else if (path === "/v1/auth/csrf") { if (options.delayedCsrf) await csrfBarrier; body = { csrf_token: csrf, header_name: "X-CSRF-Token" }; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
    else if (path === "/v1/sources/nvd_ollama/collect" || path === "/v1/sources/vllm_vendor/collect") {
      writes.push({ body: request.postData() ?? "", key: request.headers()["idempotency-key"] ?? "", csrfPresent: request.headers()["x-csrf-token"] === csrf, path });
      if (options.firstWriteUnknown && writes.length === 1) { await route.abort("failed"); return; }
      status = 202; body = jobFixture;
    } else if (path === `/v1/jobs/${jobId}`) {
      lookupCount += 1;
      if (options.expireLookup) { status = 401; body = { error: { code: "unauthenticated" } }; }
      else body = { ...jobFixture, status: lookupCount === 1 ? "partial" : lookupCount === 2 ? "blocked" : "succeeded", attempt_count: 1, error_code: lookupCount === 1 ? "source_page_limit_reached" : lookupCount === 2 ? "source_authentication_denied" : null, result_ref: `pg:source:${jobId}`, finished_at: "2026-10-15T06:00:01Z" };
    } else throw new Error(`Unexpected isolated source fixture path: ${path}`);
    await route.fulfill({ status, json: body });
  });
  return { writes, releaseCsrf, lookupCount: () => lookupCount };
}

for (const width of [1366, 390]) {
  test(`source jobs isolated Fixture ${width}px retry identity and actual per-page states`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    const fixture = await installFixture(page, { firstWriteUnknown: true });
    await page.goto("/#sources");
    await expect(page.getByText("合成 / Fixture · 模式来自当前会话", { exact: true })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "采集流", exact: true })).toHaveValue("live");
    await expect(page.getByLabel("本轮页上限", { exact: true })).toHaveValue("5");
    await page.getByRole("combobox", { name: "固定来源", exact: true }).selectOption("vllm_vendor");
    await page.getByRole("button", { name: "提交本轮采集", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText(/提交结果未确认/)).toBeVisible();
    await expect(page.getByLabel("观察窗口截止（含时区）", { exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "原样重试本轮", exact: true }).click();
    await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
    expect(fixture.writes).toHaveLength(2);
    expect(fixture.writes[0]).toEqual(fixture.writes[1]);
    expect(fixture.writes[0]?.csrfPresent).toBe(true);
    expect(fixture.writes[0]?.path).toBe("/v1/sources/vllm_vendor/collect");
    expect(Object.keys(JSON.parse(fixture.writes[0]?.body ?? "{}"))).toEqual(["window_end", "stream_kind", "max_pages"]);
    expect(fixture.lookupCount()).toBe(0);
    for (const label of ["部分完成", "任务已阻塞", "本页处理完成"]) {
      await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
      await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible();
    }
    await expect(page.getByText(/后续页仍可能排队或运行/)).toBeVisible();
    await expect(page.locator(".source-job-details time").first()).toHaveText("2026-10-15T14:00:00+08:00");
    await expect(page.locator(".source-job-details time").first()).toHaveAttribute("datetime", "2026-10-15T06:00:00Z");
    const frozenKey = fixture.writes[0]?.key;
    await page.getByRole("button", { name: "开始新一轮", exact: true }).click();
    await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
    await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
    expect(fixture.writes[2]?.key).not.toBe(frozenKey);
    expect(fixture.lookupCount()).toBe(3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await page.locator(".source-boundary, .source-metadata dd, .source-job-state p").evaluateAll((elements) => elements.every((element) => {
      const range = document.createRange(); range.selectNodeContents(element);
      return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
    }))).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`source-jobs-isolated-fixture-${width}.png`), fullPage: true });
    await testInfo.attach("fixture-request-observation", { body: JSON.stringify({ writes: fixture.writes.length, retryBodyAndKeyEqual: fixture.writes[0]?.body === fixture.writes[1]?.body && fixture.writes[0]?.key === fixture.writes[1]?.key, lookupCount: fixture.lookupCount(), mode: "isolated fixture only" }), contentType: "application/json" });
  });
}

test("source fixture role gate and CSRF late on navigation never trigger management POST", async ({ page }) => {
  let fixture = await installFixture(page, { denied: true });
  await page.goto("/#sources");
  await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  expect(fixture.writes).toHaveLength(0);
  expect(fixture.lookupCount()).toBe(0);
  await page.unrouteAll({ behavior: "wait" });
  fixture = await installFixture(page, { delayedCsrf: true });
  await page.reload();
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByText("正在提交固定来源任务，等待PG回执…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "运行状态", exact: true }).click();
  fixture.releaseCsrf();
  await expect(page.getByRole("heading", { name: "运行概览", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "来源监测", exact: true }).click();
  await expect(page.getByRole("button", { name: "提交本轮采集", exact: true })).toBeEnabled();
  expect(fixture.writes).toHaveLength(0);
});

test("source fixture job 401 expires frontend identity without restoring admin data", async ({ page }) => {
  const fixture = await installFixture(page, { expireLookup: true });
  await page.goto("/#sources");
  await page.getByLabel("任务标识", { exact: true }).fill(jobId);
  await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "提交本轮采集", exact: true })).toHaveCount(0);
  await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  expect(fixture.lookupCount()).toBe(1);
  expect(fixture.writes).toHaveLength(0);
});
