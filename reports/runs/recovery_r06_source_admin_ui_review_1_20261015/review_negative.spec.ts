import { expect, test, type Page } from "../../../frontend/node_modules/@playwright/test/index.js";

const jobId = "cb000001-1000-4000-8000-000000000001";
const csrf = "review-isolated-csrf";
const sourceKeys = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];
const job = { job_id: jobId, status: "succeeded", attempt_count: 1, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: "2026-10-15T06:00:01Z" };

function barrier() {
  let release = () => {};
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}

/** 只允许独立Vite同源资产；业务/身份/任务在浏览器内拦截，无外部来源或数据库。 */
async function fixture(page: Page, options: { hold?: "csrf" | "post" | "lookup"; writeStatus?: number; longJob?: boolean } = {}) {
  const held = barrier();
  const settled = barrier();
  const calls: string[] = [];
  const writes: { path: string; body: string; key: string; csrf: string; origin: string; cookiePresent: boolean }[] = [];
  let signedIn = true;
  let role = "system_admin";
  let permissionVersion = 1;
  let writeStatus = options.writeStatus ?? 202;
  let lookupStatus = 200;
  let token = csrf;
  const baseUrl = test.info().project.use.baseURL;
  if (typeof baseUrl !== "string") throw new Error("Independent review requires a loopback base URL");
  await page.context().addCookies([{ name: "ai_intel_session", value: "isolated-review-cookie", url: baseUrl, httpOnly: true, sameSite: "Lax" }]);
  await page.route("**/*", async (route) => {
    if (new URL(route.request().url()).hostname !== "127.0.0.1") { await route.abort("blockedbyclient"); return; }
    await route.continue();
  });
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    calls.push(path);
    let status = 200;
    let body: unknown;
    if (path === "/v1/auth/me") {
      status = signedIn ? 200 : 401;
      body = signedIn ? { user_id: "independent-review-fixture-admin", role, tenant_id: null, permissions: ["read:public"], permission_version: permissionVersion, data_mode: "fixture", csrf_token: token } : { error: { code: "unauthenticated" } };
    } else if (path === "/v1/auth/csrf") {
      if (options.hold === "csrf") await held.promise;
      body = { csrf_token: token, header_name: "X-CSRF-Token" };
    } else if (path === "/v1/auth/logout") { signedIn = false; body = { status: "logged_out" }; }
    else if (path === "/v1/auth/login") { signedIn = true; body = { user_id: "independent-review-fixture-admin", csrf_token: token, expires_at: "2099-01-01T00:00:00Z" }; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "independent isolated fixture", dependencies: {} };
    else if (sourceKeys.some((key) => path === `/v1/sources/${key}/collect`)) {
      const headers = await request.allHeaders();
      writes.push({ path, body: request.postData() ?? "", key: headers["idempotency-key"] ?? "", csrf: headers["x-csrf-token"] ?? "", origin: headers.origin ?? "", cookiePresent: (headers.cookie ?? "").includes("ai_intel_session=isolated-review-cookie") });
      if (options.hold === "post") await held.promise;
      status = writeStatus;
      body = status === 202 ? job : { error: { code: status === 403 ? "csrf_rejected" : "rate_limited", message: "raw-server-detail-do-not-display" } };
    } else if (path === `/v1/jobs/${jobId}`) {
      if (options.hold === "lookup") await held.promise;
      status = lookupStatus;
      body = status === 200 ? (options.longJob ? { ...job, status: "partial", attempt_count: Number.MAX_SAFE_INTEGER, error_code: `source_${"x".repeat(92)}`, result_ref: `pg:source:${"r".repeat(200)}` } : job) : { error: { code: status === 403 ? "permission_denied" : "review_failure", message: "raw-server-detail-do-not-display" } };
    } else throw new Error(`Unexpected independent fixture request: ${path}`);
    try { await route.fulfill({ status, json: body }); }
    finally { if (options.hold && ((options.hold === "csrf" && path.endsWith("/csrf")) || (options.hold === "post" && path.endsWith("/collect")) || (options.hold === "lookup" && path.startsWith("/v1/jobs/")))) settled.release(); }
  });
  return { calls, writes, release: held.release, settled: settled.promise, lookupStatus: (value: number) => { lookupStatus = value; }, writeStatus: (value: number) => { writeStatus = value; }, revoke: () => { role = "analyst"; permissionVersion += 1; }, renew: () => { permissionVersion += 1; }, nextCsrf: () => { token = `${csrf}-new`; } };
}

async function ready(page: Page, source = "cac_generative_ai") {
  await page.goto("/#sources");
  await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "固定来源", exact: true }).selectOption(source);
}

async function lookup(page: Page) {
  await page.getByLabel("任务标识", { exact: true }).fill(jobId);
  await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
}

async function noOldSuccess(page: Page) {
  await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  await expect(page.locator(".source-job-details time")).toHaveCount(0);
}

test("review negative: new-source CSRF hold freezes switch and duplicate submit, new round removes prior source", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const f = await fixture(page, { hold: "csrf" });
  await ready(page);
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByText("正在提交固定来源任务，等待PG回执…", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "选择 OSV · Ollama Go 包", exact: true })).toBeDisabled();
  await expect(page.locator('form[aria-label="固定来源采集"] button[type="submit"]')).toBeDisabled();
  await expect(page.getByRole("button", { name: "开始新一轮", exact: true })).toBeDisabled();
  expect(f.writes).toHaveLength(0);
  f.release(); await f.settled;
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  expect(f.writes).toHaveLength(1);
  expect(f.writes[0]?.path).toBe("/v1/sources/cac_generative_ai/collect");
  expect(Object.keys(JSON.parse(f.writes[0]?.body ?? "{}"))).toEqual(["window_end", "stream_kind", "max_pages"]);
  expect(f.writes[0]?.cookiePresent).toBe(true);
  expect(f.writes[0]?.csrf).toBe(csrf);
  expect(f.writes[0]?.origin).toBe(testInfo.project.use.baseURL);
  await page.getByRole("button", { name: "开始新一轮", exact: true }).click();
  await page.getByRole("button", { name: "选择 OSV · Ollama Go 包", exact: true }).focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toBeFocused();
  await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toHaveValue("osv_ollama");
  await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
  await noOldSuccess(page);
  await page.screenshot({ path: testInfo.outputPath("review-frozen-new-round-390.png"), fullPage: true });
});

for (const status of [401, 403]) {
  test(`review negative: new source accepted then HTTP ${status} clears old job and received time`, async ({ page }) => {
    const f = await fixture(page);
    await ready(page, "arxiv_security");
    await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
    await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
    f.lookupStatus(status); await lookup(page);
    await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
    await noOldSuccess(page);
    await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toHaveCount(0);
    expect(f.writes).toHaveLength(1);
  });
}

test("review negative: late new-source POST after logout and login cannot restore old accepted job", async ({ page }) => {
  const f = await fixture(page, { hold: "post" }); await ready(page, "ollama_releases");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect.poll(() => f.writes.length).toBe(1);
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台" })).toBeEnabled();
  await page.getByLabel("用户名", { exact: true }).fill("isolated-review-user");
  await page.getByLabel("密码", { exact: true }).fill("isolated-review-fixture-only");
  await page.getByRole("button", { name: "登录工作台" }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "来源监测", exact: true }).click();
  await expect(page.getByRole("heading", { name: "尚未查询任务", exact: true })).toBeVisible();
  f.release(); await f.settled;
  await noOldSuccess(page);
  await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
});

test("review negative: role revocation while new-source CSRF is late prevents POST entirely", async ({ page }) => {
  const f = await fixture(page, { hold: "csrf" }); await ready(page, "nist_ai_rmf");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect.poll(() => f.calls.filter((path) => path === "/v1/auth/csrf").length).toBe(1);
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  f.revoke(); await page.getByRole("button", { name: "重新验证会话", exact: true }).click();
  await expect(page.getByText("分析员", { exact: true })).toBeVisible();
  f.release(); await f.settled;
  await page.getByRole("link", { name: "来源监测", exact: true }).click();
  await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  expect(f.writes).toHaveLength(0);
  await noOldSuccess(page);
});

test("review negative: a new admin permission version fences old pending lookup", async ({ page }) => {
  const f = await fixture(page, { hold: "lookup" }); await ready(page, "avid_community");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  await lookup(page); await expect(page.getByText("正在读取指定任务的PG状态…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  f.renew(); await page.getByRole("button", { name: "重新验证会话", exact: true }).click();
  await expect(page.getByText("权限版本 2", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "来源监测", exact: true }).click();
  f.release(); await f.settled;
  await noOldSuccess(page);
  await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
});

for (const status of [404, 422, 429, 503]) {
  test(`review negative: failed manual HTTP ${status} snapshot is unknown and does not expose raw detail`, async ({ page }) => {
    const f = await fixture(page); await ready(page, "trailofbits_blog");
    await lookup(page); await expect(page.getByRole("heading", { name: "本页处理完成", exact: true })).toBeVisible();
    f.lookupStatus(status); await lookup(page);
    await expect(page.getByRole("alert")).toBeVisible();
    await noOldSuccess(page);
    await expect(page.getByText("raw-server-detail-do-not-display", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "尚未查询任务", exact: true })).toHaveCount(0);
    await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue(jobId);
    f.lookupStatus(200); await lookup(page);
    await expect(page.getByText("未知 / 仅按任务标识查询", { exact: true })).toBeVisible();
    await page.getByRole("combobox", { name: "固定来源", exact: true }).selectOption("osv_ollama");
    await noOldSuccess(page);
    await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
  });
}

test("review negative: new-source CSRF rejection retry uses original body and key with refreshed token", async ({ page }) => {
  const f = await fixture(page, { writeStatus: 403 }); await ready(page, "nist_ai_rmf");
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  await expect(page.getByText(/会话写入校验未通过/)).toBeVisible();
  await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toBeDisabled();
  f.nextCsrf(); f.writeStatus(202);
  await page.getByRole("button", { name: "原样重试本轮", exact: true }).click();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  expect(f.writes).toHaveLength(2);
  expect(f.writes[1]?.body).toBe(f.writes[0]?.body);
  expect(f.writes[1]?.key).toBe(f.writes[0]?.key);
  expect(f.writes[1]?.path).toBe(f.writes[0]?.path);
  expect(f.writes[1]?.csrf).toBe(`${csrf}-new`);
});

test("review negative: allowed longest job metadata wraps at 390 and background never blocks keyboard or pointer", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
  const f = await fixture(page, { longJob: true }); await ready(page, "cac_generative_ai"); await lookup(page);
  await expect(page.getByRole("heading", { name: "部分完成", exact: true })).toBeVisible();
  await expect(page.getByText(/来源仍可能有后续页/)).toBeVisible();
  expect(await page.locator(".ambient-backdrop").evaluate((element) => getComputedStyle(element).pointerEvents)).toBe("none");
  expect(await page.getByTestId("ambient-motion").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await page.locator(".source-metadata dd").evaluateAll((elements) => elements.every((element) => {
    const range = document.createRange(); range.selectNodeContents(element);
    return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  }))).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: testInfo.outputPath("review-long-metadata-partial-390.png"), fullPage: true });
  expect(f.writes).toHaveLength(0);
});
