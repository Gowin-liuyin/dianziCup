const { test, expect } = require("D:/wt/r06-integrated-live-1156/frontend/node_modules/@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

/** Only actual API responses; the source and login secrets stay in process memory. */
const collected = JSON.parse(fs.readFileSync(path.join(__dirname, "collection_receipt.json"), "utf8"));
const roots = collected.jobs.filter((job) => (job.idempotency_key ?? "").startsWith("source-poll-v1:"));
const representatives = Object.entries(collected.representative_documents);
const saved = (collected.representative_documents.nist_ai_rmf ?? collected.representative_documents.cac_generative_ai ?? representatives[0]?.[1])?.document;
const sourceKinds = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];

async function login(page, role) {
  await page.goto("/#session");
  await page.getByLabel("用户名", { exact: true }).fill(process.env.DIANZI_E2E_USERNAME + "-r06-integrated-" + role);
  await page.getByLabel("密码", { exact: true }).fill(process.env.DIANZI_E2E_PASSWORD);
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
}

test("real admin nine-source catalog queries actual default-beat PG jobs", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await login(page, "admin");
  await page.goto("/#sources");
  const select = page.getByLabel("固定来源", { exact: true });
  await expect(select.locator("option")).toHaveCount(9);
  expect(await select.locator("option").evaluateAll((options) => options.map((option) => option.value))).toEqual(sourceKinds);
  await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toBeVisible();
  const observations = [];
  for (const key of sourceKinds) {
    const job = roots.find((candidate) => candidate.request.source_kind === key);
    expect(job).toBeTruthy();
    await select.selectOption(key);
    await page.getByLabel("任务标识", { exact: true }).fill(job.job_id);
    const received = page.waitForResponse((response) => response.url().endsWith("/v1/jobs/" + job.job_id));
    await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
    const response = await received;
    expect(response.status()).toBe(200);
    const actual = await response.json();
    await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toBeVisible();
    await expect(page.getByRole("article", { name: "当前单页任务", exact: true }).getByText(job.job_id, { exact: true })).toBeVisible();
    observations.push({ source_kind: key, job_id: job.job_id, actual_status: actual.status, error_code: actual.error_code, http_status: response.status() });
  }
  await page.getByTestId("ambient-backdrop").evaluate((element) => element.scrollIntoView());
  await page.evaluate(() => window.scrollTo(0, 0));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: path.join(__dirname, "source-admin-visible-1366.png"), fullPage: false });
  await testInfo.attach("actual-nine-source-job-statuses", { body: JSON.stringify({ code_sha: collected.code_sha, observations, request_interception: false }), contentType: "application/json" });
});

test("real admin submits one bounded CAC backfill through existing REST CSRF and worker", async ({ page }, testInfo) => {
  await login(page, "admin");
  await page.goto("/#sources");
  await page.getByLabel("固定来源", { exact: true }).selectOption("cac_generative_ai");
  await page.getByLabel("采集流", { exact: true }).selectOption("backfill");
  await page.getByLabel("本轮页上限", { exact: true }).fill("1");
  await page.getByLabel("观察窗口截止（含时区）", { exact: true }).fill(new Date().toISOString());
  const received = page.waitForResponse((response) => response.url().endsWith("/v1/sources/cac_generative_ai/collect"));
  await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  const response = await received;
  expect(response.status()).toBe(202);
  const accepted = await response.json();
  await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  let actual = accepted;
  for (let attempts = 0; attempts < 20; attempts += 1) {
    if (["succeeded", "partial", "failed", "blocked", "cancelled"].includes(actual.status)) break;
    await page.waitForTimeout(3000);
    const lookup = page.waitForResponse((item) => item.url().endsWith("/v1/jobs/" + accepted.job_id));
    await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
    const result = await lookup;
    expect(result.status()).toBe(200);
    actual = await result.json();
  }
  expect(["succeeded", "partial", "failed", "blocked", "cancelled"]).toContain(actual.status);
  fs.writeFileSync(path.join(__dirname, "browser_manual_collection.json"), JSON.stringify({ observed_at_utc: new Date().toISOString(), code_sha: collected.code_sha, source_kind: "cac_generative_ai", stream_kind: "backfill", max_pages: 1, actual_job: actual, csrf_from_real_pg_session: true, external_failure_not_rewritten_as_success: true }, null, 2));
  await testInfo.attach("actual-bounded-manual-source", { body: JSON.stringify({ job_id: accepted.job_id, status: actual.status, error_code: actual.error_code, manual_one_page_separate_from_beat_roots: true }), contentType: "application/json" });
});

for (const width of [1366, 390]) {
  test(`real viewer source denial and document evidence history refresh motion privacy ${width}px`, async ({ page }, testInfo) => {
    expect(saved).toBeTruthy();
    await page.setViewportSize({ width, height: 900 });
    await login(page, "viewer");
    let sourceRequests = 0;
    page.on("request", (request) => { if (/\/v1\/(sources|jobs)\//.test(request.url())) sourceRequests += 1; });
    await page.goto("/#sources");
    await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
    expect(sourceRequests).toBe(0);
    await page.goto("/#documents");
    const checkedCategories = [];
    for (const category of [...new Set(representatives.map(([, sample]) => sample.document.source_category))]) {
      await page.getByLabel("来源类别", { exact: true }).selectOption(category);
      const loaded = page.waitForResponse((response) => response.url().includes("/v1/documents?") && new URL(response.url()).searchParams.get("source_category") === category);
      await page.getByRole("button", { name: "检索资料", exact: true }).click();
      const response = await loaded;
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(body.items.length).toBeGreaterThan(0);
      expect(body.items.every((item) => item.source_category === category)).toBe(true);
      checkedCategories.push(category);
    }
    await page.goto("/#documents/" + saved.document_id);
    await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
    await page.getByLabel("检索关键词", { exact: true }).fill(saved.title);
    const loaded = page.waitForResponse((response) => response.url().includes("/v1/documents?") && new URL(response.url()).searchParams.get("q") === saved.title);
    await page.getByRole("button", { name: "检索资料", exact: true }).click();
    await loaded;
    await page.getByRole("list", { name: "已保存资料列表", exact: true }).getByRole("link", { name: saved.title, exact: true }).click();
    await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
    const quote = await page.locator(".document-evidence blockquote").first().textContent();
    expect(quote.length).toBeGreaterThan(0);
    const quoteHash = crypto.createHash("sha256").update(quote).digest("hex");
    await page.locator(".document-evidence summary").first().click();
    await expect(page.getByText(quoteHash, { exact: true })).toBeVisible();
    await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveValue(saved.revision_id);
    await expect(page.getByTestId("ambient-backdrop")).toHaveCSS("pointer-events", "none");
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "topology-drift");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "none");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    if (width === 390) await page.locator(".document-inspector").scrollIntoViewIfNeeded();
    else await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(__dirname, `document-visible-${width}.png`), fullPage: false });
    await page.reload();
    await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
    await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveValue(saved.revision_id);
    await page.getByLabel("原文修订版本", { exact: true }).selectOption(saved.revision_id);
    await expect(page.locator(".document-evidence blockquote").first()).toHaveText(quote);
    await page.getByLabel("检索关键词", { exact: true }).fill("__r06_confirmed_empty_" + crypto.randomUUID());
    await page.getByRole("button", { name: "检索资料", exact: true }).click();
    await expect(page.getByRole("heading", { name: "本次查询没有资料记录", exact: true })).toBeVisible();
    await page.goto("/#session");
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
    await page.goto("/#documents/" + saved.document_id);
    await expect(page.getByRole("heading", { name: "登录后核查资料", exact: true })).toBeVisible();
    await expect(page.locator(".document-evidence blockquote")).toHaveCount(0);
    await testInfo.attach("real-document-observation", { body: JSON.stringify({ code_sha: collected.code_sha, width, checked_categories: checkedCategories, document_id: saved.document_id, revision_id: saved.revision_id, quote_hash: quoteHash, source_requests_from_viewer_sources_page: sourceRequests, request_interception: false, model_calls: 0 }), contentType: "application/json" });
  });
}

test("saved actual publisher source URL opens original policy or release page", async ({ page }, testInfo) => {
  const original = (collected.representative_documents.cac_generative_ai ?? collected.representative_documents.ollama_releases ?? representatives[0]?.[1])?.document;
  expect(original).toBeTruthy();
  await login(page, "viewer");
  await page.goto(`/#documents/${original.document_id}/revision/${original.revision_id}`);
  const link = page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true });
  await expect(link).toHaveAttribute("href", original.canonical_uri);
  const opened = page.waitForEvent("popup");
  await link.click();
  const popup = await opened;
  await popup.waitForLoadState("domcontentloaded", { timeout: 20000 });
  expect(popup.url()).toBe(original.canonical_uri);
  const title = await popup.title();
  expect(title).not.toMatch(/ERR_|not found|404/i);
  await testInfo.attach("original-publisher-opened", { body: JSON.stringify({ source_uri: original.canonical_uri, actual_url: popup.url(), actual_title: title, code_sha: collected.code_sha }), contentType: "application/json" });
  await popup.close();
});
