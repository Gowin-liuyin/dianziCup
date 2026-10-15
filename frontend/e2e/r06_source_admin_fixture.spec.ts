import { expect, test, type Page } from "@playwright/test";

const keys = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];
const jobId = "00000000-0000-4000-8000-000000000001";
const fixtureJob = { job_id: jobId, status: "succeeded", attempt_count: 1, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: "2026-10-15T06:00:01Z" };

/** 全部/v1请求隔离拦截；本测试不连接实际来源、PG或产品账号。 */
async function installFixture(page: Page, options: { rateLimitLast?: boolean; delayedLookup?: boolean } = {}) {
  const writes: { path: string; body: string; key: string }[] = [];
  const calls: string[] = [];
  let signedIn = true;
  let lookupStatus = 200;
  let limited = false;
  let releaseLookup = () => {};
  let settleLookup = () => {};
  const barrier = new Promise<void>((resolve) => { releaseLookup = resolve; });
  const settled = new Promise<void>((resolve) => { settleLookup = resolve; });
  await page.route("**/v1/**", async (route) => {
    const request = route.request(); const path = new URL(request.url()).pathname; calls.push(path);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") {
      status = signedIn ? 200 : 401;
      body = signedIn ? { user_id: "isolated-source-catalog-admin", tenant_id: null, role: "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "isolated-source-catalog-csrf" } : { error: { code: "unauthenticated" } };
    } else if (path === "/v1/auth/csrf") body = { csrf_token: "isolated-source-catalog-csrf", header_name: "X-CSRF-Token" };
    else if (path === "/v1/auth/logout") { signedIn = false; status = 204; }
    else if (path === "/v1/auth/login") { signedIn = true; body = { user_id: "isolated-source-catalog-admin", csrf_token: "isolated-source-catalog-csrf", expires_at: "2099-01-01T00:00:00Z" }; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
    else if (keys.some((key) => path === `/v1/sources/${key}/collect`)) {
      writes.push({ path, body: request.postData() ?? "", key: request.headers()["idempotency-key"] ?? "" });
      expect(request.method()).toBe("POST"); expect(request.headers()["x-csrf-token"]).toBe("isolated-source-catalog-csrf");
      if (options.rateLimitLast && path === "/v1/sources/cac_generative_ai/collect" && !limited) { limited = true; status = 429; body = { error: { code: "rate_limited" } }; }
      else { status = 202; body = fixtureJob; }
    } else if (path === `/v1/jobs/${jobId}`) {
      if (options.delayedLookup) await barrier;
      status = lookupStatus;
      body = status === 200 ? { ...fixtureJob, status: "partial", error_code: "source_page_limit_reached" } : { error: { code: "isolated_failure" } };
    } else throw new Error(`Unexpected isolated catalog route: ${path}`);
    try { await route.fulfill(status === 204 ? { status } : { status, json: body }); }
    finally { if (path === `/v1/jobs/${jobId}` && options.delayedLookup) settleLookup(); }
  });
  return { calls, writes, lookupStatus: (status: number) => { lookupStatus = status; }, releaseLookup, settled };
}

for (const width of [1366, 390]) {
  test(`nine-source catalog isolated Fixture ${width}px keyboard requests, unknown freshness and cleared snapshots`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
    const fixture = await installFixture(page, { rateLimitLast: true }); await page.goto("/#sources");
    await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toBeVisible();
    expect(await page.locator(".source-category-group").count()).toBe(8);
    expect(await page.getByText("未验证", { exact: true }).count()).toBe(9);
    expect(fixture.calls.some((path) => path.startsWith("/v1/sources/") || path.startsWith("/v1/jobs/") || path === "/v1/auth/csrf")).toBe(false);
    expect(await page.locator(".ambient-backdrop").evaluate((element) => getComputedStyle(element).pointerEvents)).toBe("none");
    expect(await page.getByTestId("ambient-motion").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
    await page.screenshot({ path: testInfo.outputPath(`catalog-fixture-initial-${width}.png`), fullPage: true });
    for (const key of keys) {
      const row = page.locator(".source-catalog-row").filter({ has: page.locator("code", { hasText: key }) });
      await row.getByRole("button").focus(); await page.keyboard.press("Enter");
      await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toBeFocused();
      expect(await page.getByRole("combobox", { name: "固定来源", exact: true }).evaluate((element) => getComputedStyle(element).outlineWidth)).toBe("2px");
      await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toHaveValue(key);
      expect(fixture.writes.filter((write) => write.path === `/v1/sources/${key}/collect`)).toHaveLength(0);
      await page.getByRole("button", { name: "提交本轮采集", exact: true }).focus(); await page.keyboard.press("Enter");
      if (key === "cac_generative_ai") {
        await expect(page.getByText(/请求过于频繁/)).toBeVisible();
        await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
        await page.getByRole("button", { name: "原样重试本轮", exact: true }).click();
        await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
        expect(fixture.writes.at(-2)).toEqual(fixture.writes.at(-1));
      }
      await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
      const write = fixture.writes.at(-1); expect(write?.path).toBe(`/v1/sources/${key}/collect`);
      expect(Object.keys(JSON.parse(write?.body ?? "{}"))).toEqual(["window_end", "stream_kind", "max_pages"]);
      await expect(row.getByRole("button")).toBeDisabled();
      await page.getByRole("button", { name: "开始新一轮", exact: true }).click();
      await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
      await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
    }
    expect(fixture.writes).toHaveLength(10);
    expect(fixture.calls.filter((path) => path.startsWith("/v1/jobs/"))).toHaveLength(0);
    await page.getByLabel("任务标识", { exact: true }).fill(jobId);
    await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
    await expect(page.getByRole("heading", { name: "部分完成", exact: true })).toBeVisible();
    await expect(page.getByText("未知 / 仅按任务标识查询", { exact: true })).toBeVisible();
    await expect(page.getByText(/服务未提供时效标记/)).toBeVisible();
    fixture.lookupStatus(503); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
    await expect(page.getByText(/本次未取得PG任务状态/)).toBeVisible();
    await expect(page.locator(".source-job-details time")).toHaveCount(0);
    fixture.lookupStatus(200); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
    await expect(page.getByRole("heading", { name: "部分完成", exact: true })).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`catalog-fixture-partial-${width}.png`), fullPage: true });
    await page.getByRole("combobox", { name: "固定来源", exact: true }).selectOption("nist_ai_rmf");
    await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
    expect(await page.locator(".source-job-details time").count()).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect(await page.locator(".source-catalog p, .source-catalog code, .source-selection-note p, .source-metadata dd").evaluateAll((elements) => elements.every((element) => {
      const range = document.createRange(); range.selectNodeContents(element);
      return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
    }))).toBe(true);
    await testInfo.attach("fixture-observation", { body: JSON.stringify({ mode: "isolated fixture only", sourceKeys: keys, writes: fixture.writes.length, manualLookups: 3, reducedMotion: true }), contentType: "application/json" });
  });
}

test("source catalog fixture permission revoked after acceptance clears every management resource", async ({ page }) => {
  const fixture = await installFixture(page); await page.goto("/#sources");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  fixture.lookupStatus(403); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  await expect(page.getByText(jobId, { exact: true })).toHaveCount(0);
  expect(await page.locator(".source-job-details time").count()).toBe(0);
});

test("source catalog fixture late lookup after logout cannot restore success or time in a new session", async ({ page }) => {
  const fixture = await installFixture(page, { delayedLookup: true }); await page.goto("/#sources");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  await expect(page.getByText("正在读取指定任务的PG状态…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台" })).toBeEnabled();
  fixture.releaseLookup(); await fixture.settled;
  await page.getByLabel("用户名", { exact: true }).fill("isolated-fixture-only");
  await page.getByLabel("密码", { exact: true }).fill("isolated-fixture-only");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "来源监测", exact: true }).click();
  await expect(page.getByRole("heading", { name: "尚未查询任务", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  expect(await page.locator(".source-job-details time").count()).toBe(0);
});
