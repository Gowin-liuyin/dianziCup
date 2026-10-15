# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r06_source_admin_fixture.spec.ts >> nine-source catalog isolated Fixture 390px keyboard requests, unknown freshness and cleared snapshots
- Location: e2e\r06_source_admin_fixture.spec.ts:46:3

# Error details

```
Error: expect(received).toEqual(expected) // deep equality

- Expected  - 3
+ Received  + 3

  Object {
-   "body": "{\"window_end\":\"2026-10-15T21:11:11+08:00\",\"stream_kind\":\"live\",\"max_pages\":5}",
-   "key": "source-ui-dc849a79-a2e2-4868-9b2f-73b38521a357",
-   "path": "/v1/sources/cac_generative_ai/collect",
+   "body": "{\"window_end\":\"2026-10-15T21:11:10+08:00\",\"stream_kind\":\"live\",\"max_pages\":5}",
+   "key": "source-ui-7ee1e078-dd2f-4d3a-a4c9-7a9058207339",
+   "path": "/v1/sources/nist_ai_rmf/collect",
  }
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - link "跳到主要内容" [ref=e4] [cursor=pointer]:
    - /url: "#main-content"
  - complementary [ref=e5]:
    - link "安全情报 DEFENSE INTELLIGENCE" [ref=e6] [cursor=pointer]:
      - /url: "#runtime"
      - generic [aria-hidden] [ref=e7]: DI
      - generic [ref=e9]:
        - text: 安全情报
        - generic [ref=e10]: DEFENSE INTELLIGENCE
    - navigation "工作台导航" [ref=e11]:
      - generic [ref=e12]:
        - link "情报列表" [ref=e13] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=e14]: ≡
          - text: 情报列表
        - link "来源监测" [ref=e15] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=e16]: ◉
          - text: 来源监测
        - link "资料库" [ref=e17] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=e18]: ▤
          - text: 资料库
        - link "知识图谱" [ref=e19] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e20]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e21] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e22]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e23] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e24]: ⬡
          - text: 资产自查
      - generic [ref=e25]:
        - link "任务轨迹" [ref=e26] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=e27]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=e28] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=e29]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=e30] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=e31]: ▤
          - text: 证据报告
      - generic [ref=e32]:
        - link "运行状态" [ref=e33] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e34]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e35] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e36]: ◎
          - text: 会话与权限
  - generic [ref=e37]:
    - banner [ref=e38]:
      - generic [ref=e39]:
        - generic [aria-hidden] [ref=e40]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e41]: /
        - text: 来源监测
      - generic [ref=e42]:
        - text: 数据模式
        - strong [ref=e43]: 合成 / Fixture
    - main [ref=e44]:
      - generic [ref=e45]:
        - generic [ref=e46]:
          - paragraph [ref=e47]: COLLECTION / SOURCES
          - heading "来源与采集" [level=1] [ref=e48]: 来源与采集_
          - paragraph [ref=e49]: 区分来源覆盖、实际接通与采集时效。
        - button "刷新状态" [ref=e50] [cursor=pointer]:
          - generic [aria-hidden] [ref=e51]: ↻
          - text: 刷新状态
      - generic [ref=e52]:
        - generic [ref=e53]:
          - generic [ref=e54]: FIXED SOURCES / 有界调度
          - paragraph [ref=e55]: 九个固定来源归入八类。目录仅说明登记范围，未验证接通或启用；任务状态读取PG，不代表持续在线或全部采完。
          - generic [ref=e56]: 合成 / Fixture · 模式来自当前会话
        - generic [ref=e57]:
          - region [ref=e58]:
            - generic [ref=e59]:
              - generic [ref=e60]:
                - paragraph [ref=e61]: CATALOG / 登记范围
                - heading "固定来源目录" [level=2] [ref=e62]
              - generic [ref=e63]: 接通状态未验证
            - generic [ref=e64]:
              - generic [ref=e65]:
                - heading "结构化漏洞" [level=3] [ref=e66]
                - article [ref=e67]:
                  - generic [ref=e68]:
                    - strong [ref=e69]: NVD · Ollama
                    - generic [ref=e70]: 未验证
                  - paragraph [ref=e71]: 固定 Ollama 关键词的漏洞记录。
                  - generic [ref=e72]:
                    - code [ref=e73]: nvd_ollama
                    - button "选择 NVD · Ollama" [disabled] [ref=e74]
                - article [ref=e75]:
                  - generic [ref=e76]:
                    - strong [ref=e77]: OSV · Ollama Go 包
                    - generic [ref=e78]: 未验证
                  - paragraph [ref=e79]: 固定 Go 包 github.com/ollama/ollama 的漏洞记录。
                  - generic [ref=e80]:
                    - code [ref=e81]: osv_ollama
                    - button "选择 OSV · Ollama Go 包" [disabled] [ref=e82]
              - generic [ref=e83]:
                - heading "厂商公告" [level=3] [ref=e84]
                - article [ref=e85]:
                  - generic [ref=e86]:
                    - strong [ref=e87]: vLLM · 厂商公告
                    - generic [ref=e88]: 未验证
                  - paragraph [ref=e89]: vLLM 官方仓库公开安全公告。
                  - generic [ref=e90]:
                    - code [ref=e91]: vllm_vendor
                    - button "选择 vLLM · 厂商公告" [disabled] [ref=e92]
              - generic [ref=e93]:
                - heading "安全社区" [level=3] [ref=e94]
                - article [ref=e95]:
                  - generic [ref=e96]:
                    - strong [ref=e97]: AVID · AI 社区报告
                    - generic [ref=e98]: 未验证
                  - paragraph [ref=e99]: AVID 固定公开仓库的 AI 风险报告。
                  - generic [ref=e100]:
                    - code [ref=e101]: avid_community
                    - button "选择 AVID · AI 社区报告" [disabled] [ref=e102]
              - generic [ref=e103]:
                - heading "代码仓库" [level=3] [ref=e104]
                - article [ref=e105]:
                  - generic [ref=e106]:
                    - strong [ref=e107]: Ollama · 发布记录
                    - generic [ref=e108]: 未验证
                  - paragraph [ref=e109]: Ollama 官方仓库的发布元数据。
                  - generic [ref=e110]:
                    - code [ref=e111]: ollama_releases
                    - button "选择 Ollama · 发布记录" [disabled] [ref=e112]
              - generic [ref=e113]:
                - heading "技术博客" [level=3] [ref=e114]
                - article [ref=e115]:
                  - generic [ref=e116]:
                    - strong [ref=e117]: Trail of Bits · 研究文章
                    - generic [ref=e118]: 未验证
                  - paragraph [ref=e119]: 固定研究博客的 RSS 发现与片段。
                  - generic [ref=e120]:
                    - code [ref=e121]: trailofbits_blog
                    - button "选择 Trail of Bits · 研究文章" [disabled] [ref=e122]
              - generic [ref=e123]:
                - heading "学术论文" [level=3] [ref=e124]
                - article [ref=e125]:
                  - generic [ref=e126]:
                    - strong [ref=e127]: arXiv · AI 安全论文
                    - generic [ref=e128]: 未验证
                  - paragraph [ref=e129]: 固定 AI 安全检索的论文元数据与摘要。
                  - generic [ref=e130]:
                    - code [ref=e131]: arxiv_security
                    - button "选择 arXiv · AI 安全论文" [disabled] [ref=e132]
              - generic [ref=e133]:
                - heading "技术标准" [level=3] [ref=e134]
                - article [ref=e135]:
                  - generic [ref=e136]:
                    - strong [ref=e137]: NIST · AI RMF 1.0
                    - generic [ref=e138]: 未验证
                  - paragraph [ref=e139]: NIST AI RMF 1.0 原文框架。
                  - generic [ref=e140]:
                    - code [ref=e141]: nist_ai_rmf
                    - button "选择 NIST · AI RMF 1.0" [disabled] [ref=e142]
              - generic [ref=e143]:
                - heading "政策法规" [level=3] [ref=e144]
                - article [ref=e145]:
                  - generic [ref=e146]:
                    - strong [ref=e147]: 网信办 · 生成式人工智能办法
                    - generic [ref=e148]: 未验证
                  - paragraph [ref=e149]: 生成式人工智能服务管理办法官方资料。
                  - generic [ref=e150]:
                    - code [ref=e151]: cac_generative_ai
                    - button "选择 网信办 · 生成式人工智能办法" [disabled] [pressed] [ref=e152]
          - generic [ref=e153]:
            - region [ref=e154]:
              - generic [ref=e156]:
                - paragraph [ref=e157]: COLLECT / 单源提交
                - heading "提交采集轮次" [level=2] [ref=e158]
              - generic [ref=e159]:
                - strong [ref=e160]: 网信办 · 生成式人工智能办法
                - paragraph [ref=e161]: 适用范围与义务以原文为准，尚未作适用判断。
              - form "固定来源采集" [ref=e162]:
                - generic [ref=e163]:
                  - text: 固定来源
                  - combobox "固定来源" [disabled] [ref=e164]:
                    - option "NVD · Ollama"
                    - option "vLLM · 厂商公告"
                    - option "OSV · Ollama Go 包"
                    - option "AVID · AI 社区报告"
                    - option "Ollama · 发布记录"
                    - option "Trail of Bits · 研究文章"
                    - option "arXiv · AI 安全论文"
                    - option "NIST · AI RMF 1.0"
                    - option "网信办 · 生成式人工智能办法" [selected]
                - generic [ref=e165]:
                  - generic [ref=e166]:
                    - text: 采集流
                    - combobox "采集流" [disabled] [ref=e167]:
                      - option "实时流 / live" [selected]
                      - option "回补流 / backfill"
                  - generic [ref=e168]:
                    - text: 本轮页上限
                    - spinbutton "本轮页上限" [disabled] [ref=e169]: "5"
                - generic [ref=e170]:
                  - text: 观察窗口截止（含时区）
                  - textbox "观察窗口截止（含时区）" [disabled] [ref=e171]: 2026-10-15T21:11:11+08:00
                - paragraph [ref=e172]: 窗口是本轮观察标识，不保证上游快照或完整时间过滤。202只表示PG受理，不表示来源采完。
                - button "正在提交…" [disabled] [ref=e173]
              - generic [ref=e174]:
                - heading "本轮请求已冻结" [level=3] [ref=e175]
                - generic [ref=e176]:
                  - term [ref=e177]: 来源与流
                  - definition [ref=e178]: 网信办 · 生成式人工智能办法 / live
                  - term [ref=e179]: 固定窗口
                  - definition [ref=e180]:
                    - time [ref=e181]: 2026-10-15T21:11:11+08:00
                  - term [ref=e182]: 页上限
                  - definition [ref=e183]: "5"
                  - term [ref=e184]: 幂等请求键
                  - definition [ref=e185]:
                    - code [ref=e186]: source-ui-dc849a79-a2e2-4868-9b2f-73b38521a357
                - paragraph [ref=e187]: 重试保留相同来源、请求体、窗口和请求键。开始新一轮后，首次提交会生成新键；上一轮结果未知时请先原样重试。
                - generic [ref=e188]:
                  - button "原样重试本轮" [disabled] [ref=e189]
                  - button "开始新一轮" [disabled] [ref=e190]
            - region [ref=e191]:
              - generic [ref=e192]:
                - generic [ref=e193]:
                  - paragraph [ref=e194]: JOB / PG单页任务
                  - heading "任务状态查询" [level=2] [ref=e195]
                - generic [ref=e196]: 手动刷新
              - form "查询单页任务" [ref=e197]:
                - generic [ref=e198]:
                  - text: 任务标识
                  - textbox "任务标识" [disabled] [ref=e199]:
                    - /placeholder: 输入已保存的job UUID
                - button "查询 / 刷新任务" [disabled] [ref=e200]
                - paragraph [ref=e201]: 保存任务标识可在返回本页后重新查询。此处没有任务历史、全来源计数或自动轮询。
              - status [ref=e202]: 正在提交固定来源任务，等待PG回执…
      - generic [ref=e203]:
        - generic [ref=e204]: 环境未由服务端标明
        - generic [ref=e205]: 版本未由服务端标明
```

# Test source

```ts
  1   | import { expect, test, type Page } from "@playwright/test";
  2   | 
  3   | const keys = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];
  4   | const jobId = "00000000-0000-4000-8000-000000000001";
  5   | const fixtureJob = { job_id: jobId, status: "succeeded", attempt_count: 1, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: "2026-10-15T06:00:01Z" };
  6   | 
  7   | /** 全部/v1请求隔离拦截；本测试不连接实际来源、PG或产品账号。 */
  8   | async function installFixture(page: Page, options: { rateLimitLast?: boolean; delayedLookup?: boolean } = {}) {
  9   |   const writes: { path: string; body: string; key: string }[] = [];
  10  |   const calls: string[] = [];
  11  |   let signedIn = true;
  12  |   let lookupStatus = 200;
  13  |   let limited = false;
  14  |   let releaseLookup = () => {};
  15  |   let settleLookup = () => {};
  16  |   const barrier = new Promise<void>((resolve) => { releaseLookup = resolve; });
  17  |   const settled = new Promise<void>((resolve) => { settleLookup = resolve; });
  18  |   await page.route("**/v1/**", async (route) => {
  19  |     const request = route.request(); const path = new URL(request.url()).pathname; calls.push(path);
  20  |     let body: unknown; let status = 200;
  21  |     if (path === "/v1/auth/me") {
  22  |       status = signedIn ? 200 : 401;
  23  |       body = signedIn ? { user_id: "isolated-source-catalog-admin", tenant_id: null, role: "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "isolated-source-catalog-csrf" } : { error: { code: "unauthenticated" } };
  24  |     } else if (path === "/v1/auth/csrf") body = { csrf_token: "isolated-source-catalog-csrf", header_name: "X-CSRF-Token" };
  25  |     else if (path === "/v1/auth/logout") { signedIn = false; status = 204; }
  26  |     else if (path === "/v1/auth/login") { signedIn = true; body = { user_id: "isolated-source-catalog-admin", csrf_token: "isolated-source-catalog-csrf", expires_at: "2099-01-01T00:00:00Z" }; }
  27  |     else if (path === "/v1/health/live") body = { status: "live" };
  28  |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
  29  |     else if (keys.some((key) => path === `/v1/sources/${key}/collect`)) {
  30  |       writes.push({ path, body: request.postData() ?? "", key: request.headers()["idempotency-key"] ?? "" });
  31  |       expect(request.method()).toBe("POST"); expect(request.headers()["x-csrf-token"]).toBe("isolated-source-catalog-csrf");
  32  |       if (options.rateLimitLast && path === "/v1/sources/cac_generative_ai/collect" && !limited) { limited = true; status = 429; body = { error: { code: "rate_limited" } }; }
  33  |       else { status = 202; body = fixtureJob; }
  34  |     } else if (path === `/v1/jobs/${jobId}`) {
  35  |       if (options.delayedLookup) await barrier;
  36  |       status = lookupStatus;
  37  |       body = status === 200 ? { ...fixtureJob, status: "partial", error_code: "source_page_limit_reached" } : { error: { code: "isolated_failure" } };
  38  |     } else throw new Error(`Unexpected isolated catalog route: ${path}`);
  39  |     try { await route.fulfill(status === 204 ? { status } : { status, json: body }); }
  40  |     finally { if (path === `/v1/jobs/${jobId}` && options.delayedLookup) settleLookup(); }
  41  |   });
  42  |   return { calls, writes, lookupStatus: (status: number) => { lookupStatus = status; }, releaseLookup, settled };
  43  | }
  44  | 
  45  | for (const width of [1366, 390]) {
  46  |   test(`nine-source catalog isolated Fixture ${width}px keyboard requests, unknown freshness and cleared snapshots`, async ({ page }, testInfo) => {
  47  |     await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
  48  |     const fixture = await installFixture(page, { rateLimitLast: true }); await page.goto("/#sources");
  49  |     await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toBeVisible();
  50  |     expect(await page.locator(".source-category-group").count()).toBe(8);
  51  |     expect(await page.getByText("未验证", { exact: true }).count()).toBe(9);
  52  |     expect(fixture.calls.some((path) => path.startsWith("/v1/sources/") || path.startsWith("/v1/jobs/") || path === "/v1/auth/csrf")).toBe(false);
  53  |     expect(await page.locator(".ambient-backdrop").evaluate((element) => getComputedStyle(element).pointerEvents)).toBe("none");
  54  |     await page.screenshot({ path: testInfo.outputPath(`catalog-fixture-initial-${width}.png`), fullPage: true });
  55  |     for (const key of keys) {
  56  |       const row = page.locator(".source-catalog-row").filter({ has: page.locator("code", { hasText: key }) });
  57  |       await row.getByRole("button").focus(); await page.keyboard.press("Enter");
  58  |       await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toBeFocused();
  59  |       await expect(page.getByRole("combobox", { name: "固定来源", exact: true })).toHaveValue(key);
  60  |       expect(fixture.writes.filter((write) => write.path === `/v1/sources/${key}/collect`)).toHaveLength(0);
  61  |       await page.getByRole("button", { name: "提交本轮采集", exact: true }).focus(); await page.keyboard.press("Enter");
  62  |       if (key === "cac_generative_ai") {
  63  |         await expect(page.getByText(/请求过于频繁/)).toBeVisible();
  64  |         await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  65  |         await page.getByRole("button", { name: "原样重试本轮", exact: true }).click();
> 66  |         expect(fixture.writes.at(-2)).toEqual(fixture.writes.at(-1));
      |                                       ^ Error: expect(received).toEqual(expected) // deep equality
  67  |       }
  68  |       await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  69  |       const write = fixture.writes.at(-1); expect(write?.path).toBe(`/v1/sources/${key}/collect`);
  70  |       expect(Object.keys(JSON.parse(write?.body ?? "{}"))).toEqual(["window_end", "stream_kind", "max_pages"]);
  71  |       await expect(row.getByRole("button")).toBeDisabled();
  72  |       await page.getByRole("button", { name: "开始新一轮", exact: true }).click();
  73  |       await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  74  |       await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  75  |       await expect(page.getByLabel("任务标识", { exact: true })).toHaveValue("");
  76  |     }
  77  |     expect(fixture.writes).toHaveLength(10);
  78  |     expect(fixture.calls.filter((path) => path.startsWith("/v1/jobs/"))).toHaveLength(0);
  79  |     await page.getByLabel("任务标识", { exact: true }).fill(jobId);
  80  |     await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  81  |     await expect(page.getByRole("heading", { name: "部分完成", exact: true })).toBeVisible();
  82  |     await expect(page.getByText("未知 / 仅按任务标识查询", { exact: true })).toBeVisible();
  83  |     await expect(page.getByText(/服务未提供时效标记/)).toBeVisible();
  84  |     fixture.lookupStatus(503); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  85  |     await expect(page.getByText(/本次未取得PG任务状态/)).toBeVisible();
  86  |     await expect(page.locator(".source-job-details time")).toHaveCount(0);
  87  |     fixture.lookupStatus(200); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  88  |     await expect(page.getByRole("heading", { name: "部分完成", exact: true })).toBeVisible();
  89  |     await page.screenshot({ path: testInfo.outputPath(`catalog-fixture-partial-${width}.png`), fullPage: true });
  90  |     await page.getByRole("combobox", { name: "固定来源", exact: true }).selectOption("nist_ai_rmf");
  91  |     await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  92  |     expect(await page.locator(".source-job-details time").count()).toBe(0);
  93  |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  94  |     expect(await page.locator(".source-catalog p, .source-catalog code, .source-selection-note p, .source-metadata dd").evaluateAll((elements) => elements.every((element) => {
  95  |       const range = document.createRange(); range.selectNodeContents(element);
  96  |       return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  97  |     }))).toBe(true);
  98  |     await testInfo.attach("fixture-observation", { body: JSON.stringify({ mode: "isolated fixture only", sourceKeys: keys, writes: fixture.writes.length, manualLookups: 3, reducedMotion: true }), contentType: "application/json" });
  99  |   });
  100 | }
  101 | 
  102 | test("source catalog fixture permission revoked after acceptance clears every management resource", async ({ page }) => {
  103 |   const fixture = await installFixture(page); await page.goto("/#sources");
  104 |   await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  105 |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  106 |   fixture.lookupStatus(403); await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  107 |   await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  108 |   await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toHaveCount(0);
  109 |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  110 |   await expect(page.getByText(jobId, { exact: true })).toHaveCount(0);
  111 |   expect(await page.locator(".source-job-details time").count()).toBe(0);
  112 | });
  113 | 
  114 | test("source catalog fixture late lookup after logout cannot restore success or time in a new session", async ({ page }) => {
  115 |   const fixture = await installFixture(page, { delayedLookup: true }); await page.goto("/#sources");
  116 |   await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  117 |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  118 |   await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  119 |   await expect(page.getByText("正在读取指定任务的PG状态…", { exact: true })).toBeVisible();
  120 |   await page.getByRole("link", { name: "团队登录", exact: true }).click();
  121 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  122 |   await expect(page.getByRole("button", { name: "登录工作台" })).toBeEnabled();
  123 |   fixture.releaseLookup(); await fixture.settled;
  124 |   await page.getByLabel("用户名", { exact: true }).fill("isolated-fixture-only");
  125 |   await page.getByLabel("密码", { exact: true }).fill("isolated-fixture-only");
  126 |   await page.getByRole("button", { name: "登录工作台" }).click();
  127 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  128 |   await page.getByRole("link", { name: "来源监测", exact: true }).click();
  129 |   await expect(page.getByRole("heading", { name: "尚未查询任务", exact: true })).toBeVisible();
  130 |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toHaveCount(0);
  131 |   await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toHaveCount(0);
  132 |   expect(await page.locator(".source-job-details time").count()).toBe(0);
  133 | });
  134 | 
```