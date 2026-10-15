# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_source_jobs_fixture.spec.ts >> source jobs isolated Fixture 390px retry identity and actual per-page states
- Location: e2e\r17_source_jobs_fixture.spec.ts:38:3

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByLabel('采集流', { exact: true })
Expected: "live"
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" getByLabel('采集流', { exact: true }) with timeout 10000ms
  - waiting for getByLabel('采集流', { exact: true })

```

```yaml
- link "跳到主要内容":
  - /url: "#main-content"
- complementary:
  - link "安全情报 DEFENSE INTELLIGENCE":
    - /url: "#runtime"
  - navigation "工作台导航":
    - link "情报列表":
      - /url: "#events"
    - link "来源监测":
      - /url: "#sources"
    - link "知识图谱":
      - /url: "#graph"
    - link "引用问答":
      - /url: "#questions"
    - link "资产自查":
      - /url: "#assets"
    - link "任务轨迹":
      - /url: "#tasks"
    - link "变化与推荐":
      - /url: "#changes"
    - link "证据报告":
      - /url: "#reports"
    - link "运行状态":
      - /url: "#runtime"
    - link "会话与权限":
      - /url: "#session"
- banner:
  - text: 工作台 来源监测 数据模式
  - strong: 合成 / Fixture
- main:
  - paragraph: COLLECTION / SOURCES
  - heading "来源与采集" [level=1]
  - paragraph: 区分来源覆盖、实际接通与采集时效。
  - button "刷新状态"
  - text: FIXED SOURCES / 有界调度
  - paragraph: 仅管理两个固定公开来源。任务状态读取PG，不代表整个来源覆盖、持续在线或监控总量。
  - text: 合成 / Fixture · 模式来自当前会话
  - region "提交采集轮次":
    - paragraph: COLLECT / 固定来源
    - heading "提交采集轮次" [level=2]
    - strong: NVD · Ollama
    - paragraph: 固定Ollama关键词；每个任务处理一页。
    - code: nvd_ollama
    - strong: vLLM · 厂商公告
    - paragraph: 固定官方仓库公开公告；服务端处理分页游标。
    - code: vllm_vendor
    - form "固定来源采集":
      - text: 固定来源
      - combobox "固定来源":
        - option "NVD · Ollama" [selected]
        - option "vLLM · 厂商公告"
      - text: 采集流
      - combobox "采集流":
        - option "实时流 / live" [selected]
        - option "回补流 / backfill"
      - text: 本轮页上限
      - spinbutton "本轮页上限": "5"
      - text: 观察窗口截止（含时区）
      - textbox "观察窗口截止（含时区）": 2026-10-15T15:12:02+08:00
      - paragraph: 窗口是本轮观察标识，不保证上游快照或完整时间过滤。202只表示PG受理，不表示来源采完。
      - button "提交本轮采集"
  - region "任务状态查询":
    - paragraph: JOB / PG单页任务
    - heading "任务状态查询" [level=2]
    - text: 手动刷新
    - form "查询单页任务":
      - text: 任务标识
      - textbox "任务标识":
        - /placeholder: 输入已保存的job UUID
      - button "查询 / 刷新任务" [disabled]
      - paragraph: 保存任务标识可在返回本页后重新查询。此处没有任务历史、全来源计数或自动轮询。
    - heading "尚未查询任务" [level=3]
    - paragraph: 提交一轮取得任务标识，或输入已有标识查询。尚未查询不等于没有任务。
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
  1   | import { randomBytes } from "node:crypto";
  2   | import { expect, test, type Page } from "@playwright/test";
  3   | 
  4   | const jobId = "00000000-0000-4000-8000-000000000001";
  5   | const csrf = randomBytes(32).toString("hex");
  6   | const jobFixture = { job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null };
  7   | 
  8   | /** 本文件所有管理和身份请求仅在浏览器内隔离拦截，不连接实际来源或产品账号。 */
  9   | async function installFixture(page: Page, options: { denied?: boolean; firstWriteUnknown?: boolean; expireLookup?: boolean; delayedCsrf?: boolean } = {}) {
  10  |   const writes: { body: string; key: string; csrfPresent: boolean; path: string }[] = [];
  11  |   let lookupCount = 0;
  12  |   let releaseCsrf = () => {};
  13  |   const csrfBarrier = new Promise<void>((resolve) => { releaseCsrf = resolve; });
  14  |   await page.route("**/v1/**", async (route) => {
  15  |     const request = route.request();
  16  |     const path = new URL(request.url()).pathname;
  17  |     let status = 200;
  18  |     let body: unknown;
  19  |     if (path === "/v1/auth/me") body = { user_id: "isolated-source-fixture-admin", tenant_id: null, role: options.denied ? "analyst" : "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
  20  |     else if (path === "/v1/auth/csrf") { if (options.delayedCsrf) await csrfBarrier; body = { csrf_token: csrf, header_name: "X-CSRF-Token" }; }
  21  |     else if (path === "/v1/health/live") body = { status: "live" };
  22  |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
  23  |     else if (path === "/v1/sources/nvd_ollama/collect" || path === "/v1/sources/vllm_vendor/collect") {
  24  |       writes.push({ body: request.postData() ?? "", key: request.headers()["idempotency-key"] ?? "", csrfPresent: request.headers()["x-csrf-token"] === csrf, path });
  25  |       if (options.firstWriteUnknown && writes.length === 1) { await route.abort("failed"); return; }
  26  |       status = 202; body = jobFixture;
  27  |     } else if (path === `/v1/jobs/${jobId}`) {
  28  |       lookupCount += 1;
  29  |       if (options.expireLookup) { status = 401; body = { error: { code: "unauthenticated" } }; }
  30  |       else body = { ...jobFixture, status: lookupCount === 1 ? "partial" : lookupCount === 2 ? "blocked" : "succeeded", attempt_count: 1, error_code: lookupCount === 1 ? "source_page_limit_reached" : lookupCount === 2 ? "source_authentication_denied" : null, result_ref: `pg:source:${jobId}`, finished_at: "2026-10-15T06:00:01Z" };
  31  |     } else throw new Error(`Unexpected isolated source fixture path: ${path}`);
  32  |     await route.fulfill({ status, json: body });
  33  |   });
  34  |   return { writes, releaseCsrf, lookupCount: () => lookupCount };
  35  | }
  36  | 
  37  | for (const width of [1366, 390]) {
  38  |   test(`source jobs isolated Fixture ${width}px retry identity and actual per-page states`, async ({ page }, testInfo) => {
  39  |     await page.setViewportSize({ width, height: 900 });
  40  |     await page.emulateMedia({ reducedMotion: "reduce" });
  41  |     const fixture = await installFixture(page, { firstWriteUnknown: true });
  42  |     await page.goto("/#sources");
  43  |     await expect(page.getByText("合成 / Fixture · 模式来自当前会话", { exact: true })).toBeVisible();
> 44  |     await expect(page.getByLabel("采集流", { exact: true })).toHaveValue("live");
      |                                                           ^ Error: expect(locator).toHaveValue(expected) failed
  45  |     await expect(page.getByLabel("本轮页上限", { exact: true })).toHaveValue("5");
  46  |     await page.getByLabel("固定来源", { exact: true }).selectOption("vllm_vendor");
  47  |     await page.getByRole("button", { name: "提交本轮采集", exact: true }).focus();
  48  |     await page.keyboard.press("Enter");
  49  |     await expect(page.getByText(/提交结果未确认/)).toBeVisible();
  50  |     await expect(page.getByLabel("观察窗口截止（含时区）", { exact: true })).toBeDisabled();
  51  |     await page.getByRole("button", { name: "原样重试本轮", exact: true }).click();
  52  |     await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  53  |     expect(fixture.writes).toHaveLength(2);
  54  |     expect(fixture.writes[0]).toEqual(fixture.writes[1]);
  55  |     expect(fixture.writes[0]?.csrfPresent).toBe(true);
  56  |     expect(fixture.writes[0]?.path).toBe("/v1/sources/vllm_vendor/collect");
  57  |     expect(Object.keys(JSON.parse(fixture.writes[0]?.body ?? "{}"))).toEqual(["window_end", "stream_kind", "max_pages"]);
  58  |     expect(fixture.lookupCount()).toBe(0);
  59  |     for (const label of ["部分完成", "任务已阻塞", "本页处理完成"]) {
  60  |       await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  61  |       await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible();
  62  |     }
  63  |     await expect(page.getByText(/后续页仍可能排队或运行/)).toBeVisible();
  64  |     await expect(page.locator(".source-job-details time").first()).toHaveText("2026-10-15T14:00:00+08:00");
  65  |     await expect(page.locator(".source-job-details time").first()).toHaveAttribute("datetime", "2026-10-15T06:00:00Z");
  66  |     const frozenKey = fixture.writes[0]?.key;
  67  |     await page.getByRole("button", { name: "开始新一轮", exact: true }).click();
  68  |     await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  69  |     await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  70  |     expect(fixture.writes[2]?.key).not.toBe(frozenKey);
  71  |     expect(fixture.lookupCount()).toBe(3);
  72  |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  73  |     expect(await page.locator(".source-boundary, .source-metadata dd, .source-job-state p").evaluateAll((elements) => elements.every((element) => {
  74  |       const range = document.createRange(); range.selectNodeContents(element);
  75  |       return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  76  |     }))).toBe(true);
  77  |     await page.evaluate(() => window.scrollTo(0, 0));
  78  |     await page.screenshot({ path: testInfo.outputPath(`source-jobs-isolated-fixture-${width}.png`), fullPage: true });
  79  |     await testInfo.attach("fixture-request-observation", { body: JSON.stringify({ writes: fixture.writes.length, retryBodyAndKeyEqual: fixture.writes[0]?.body === fixture.writes[1]?.body && fixture.writes[0]?.key === fixture.writes[1]?.key, lookupCount: fixture.lookupCount(), mode: "isolated fixture only" }), contentType: "application/json" });
  80  |   });
  81  | }
  82  | 
  83  | test("source fixture role gate and CSRF late on navigation never trigger management POST", async ({ page }) => {
  84  |   let fixture = await installFixture(page, { denied: true });
  85  |   await page.goto("/#sources");
  86  |   await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  87  |   expect(fixture.writes).toHaveLength(0);
  88  |   expect(fixture.lookupCount()).toBe(0);
  89  |   await page.unrouteAll({ behavior: "wait" });
  90  |   fixture = await installFixture(page, { delayedCsrf: true });
  91  |   await page.reload();
  92  |   await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  93  |   await expect(page.getByText("正在提交固定来源任务，等待PG回执…", { exact: true })).toBeVisible();
  94  |   await page.getByRole("link", { name: "运行状态", exact: true }).click();
  95  |   fixture.releaseCsrf();
  96  |   await expect(page.getByRole("heading", { name: "运行概览", exact: true })).toBeVisible();
  97  |   await page.getByRole("link", { name: "来源监测", exact: true }).click();
  98  |   await expect(page.getByRole("button", { name: "提交本轮采集", exact: true })).toBeEnabled();
  99  |   expect(fixture.writes).toHaveLength(0);
  100 | });
  101 | 
  102 | test("source fixture job 401 expires frontend identity without restoring admin data", async ({ page }) => {
  103 |   const fixture = await installFixture(page, { expireLookup: true });
  104 |   await page.goto("/#sources");
  105 |   await page.getByLabel("任务标识", { exact: true }).fill(jobId);
  106 |   await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  107 |   await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  108 |   await expect(page.getByRole("button", { name: "提交本轮采集", exact: true })).toHaveCount(0);
  109 |   await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  110 |   expect(fixture.lookupCount()).toBe(1);
  111 |   expect(fixture.writes).toHaveLength(0);
  112 | });
  113 | 
```