# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: integrated-live.spec.cjs >> real admin nine-source catalog queries actual default-beat PG jobs
- Location: ..\..\..\dianzi\reports\runs\recovery_r06_integrated_live_20261015\integrated-live.spec.cjs:21:1

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByLabel('固定来源', { exact: true }).locator('option')
Expected: 9
Received: 0
Timeout:  15000ms

Call log:
  - Expect "toHaveCount" getByLabel('固定来源', { exact: true }).locator('option') with timeout 15000ms
  - waiting for getByLabel('固定来源', { exact: true }).locator('option')
    33 × locator resolved to 0 elements
       - unexpected value "0"

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
        - paragraph [ref=e13]: 研究
        - link "情报列表" [ref=e14] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=e15]: ≡
          - text: 情报列表
        - link "来源监测" [ref=e16] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=e17]: ◉
          - text: 来源监测
        - link "资料库" [ref=e18] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=e19]: ▤
          - text: 资料库
        - link "知识图谱" [ref=e20] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e21]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e22] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e23]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e24] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e25]: ⬡
          - text: 资产自查
      - generic [ref=e26]:
        - paragraph [ref=e27]: 协作
        - link "任务轨迹" [ref=e28] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=e29]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=e30] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=e31]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=e32] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=e33]: ▤
          - text: 证据报告
      - generic [ref=e34]:
        - paragraph [ref=e35]: 系统
        - link "运行状态" [ref=e36] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e37]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e38] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e39]: ◎
          - text: 会话与权限
    - generic [ref=e40]:
      - paragraph [ref=e41]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=e42]: READ · VERIFY · CONNECT
  - generic [ref=e43]:
    - banner [ref=e44]:
      - generic [ref=e45]:
        - generic [aria-hidden] [ref=e46]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e47]: /
        - text: 来源监测
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 真实 / Live
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: COLLECTION / SOURCES
          - heading "来源与采集" [level=1] [ref=e54]: 来源与采集_
          - paragraph [ref=e55]: 区分来源覆盖、实际接通与采集时效。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - generic [ref=e58]:
        - generic [ref=e59]:
          - generic [ref=e60]: FIXED SOURCES / 有界调度
          - paragraph [ref=e61]: 九个固定来源归入八类。目录仅说明登记范围，未验证接通或启用；任务状态读取PG，不代表持续在线或全部采完。
          - generic [ref=e62]: 真实 / Live · 模式来自当前会话
        - generic [ref=e63]:
          - region [ref=e64]:
            - generic [ref=e65]:
              - generic [ref=e66]:
                - paragraph [ref=e67]: CATALOG / 登记范围
                - heading "固定来源目录" [level=2] [ref=e68]
              - generic [ref=e69]: 接通状态未验证
            - generic [ref=e70]:
              - generic [ref=e71]:
                - heading "结构化漏洞" [level=3] [ref=e72]
                - article [ref=e73]:
                  - generic [ref=e74]:
                    - strong [ref=e75]: NVD · Ollama
                    - generic [ref=e76]: 未验证
                  - paragraph [ref=e77]: 固定 Ollama 关键词的漏洞记录。
                  - generic [ref=e78]:
                    - code [ref=e79]: nvd_ollama
                    - button "选择 NVD · Ollama" [pressed] [ref=e80] [cursor=pointer]
                - article [ref=e81]:
                  - generic [ref=e82]:
                    - strong [ref=e83]: OSV · Ollama Go 包
                    - generic [ref=e84]: 未验证
                  - paragraph [ref=e85]: 固定 Go 包 github.com/ollama/ollama 的漏洞记录。
                  - generic [ref=e86]:
                    - code [ref=e87]: osv_ollama
                    - button "选择 OSV · Ollama Go 包" [ref=e88] [cursor=pointer]
              - generic [ref=e89]:
                - heading "厂商公告" [level=3] [ref=e90]
                - article [ref=e91]:
                  - generic [ref=e92]:
                    - strong [ref=e93]: vLLM · 厂商公告
                    - generic [ref=e94]: 未验证
                  - paragraph [ref=e95]: vLLM 官方仓库公开安全公告。
                  - generic [ref=e96]:
                    - code [ref=e97]: vllm_vendor
                    - button "选择 vLLM · 厂商公告" [ref=e98] [cursor=pointer]
              - generic [ref=e99]:
                - heading "安全社区" [level=3] [ref=e100]
                - article [ref=e101]:
                  - generic [ref=e102]:
                    - strong [ref=e103]: AVID · AI 社区报告
                    - generic [ref=e104]: 未验证
                  - paragraph [ref=e105]: AVID 固定公开仓库的 AI 风险报告。
                  - generic [ref=e106]:
                    - code [ref=e107]: avid_community
                    - button "选择 AVID · AI 社区报告" [ref=e108] [cursor=pointer]
              - generic [ref=e109]:
                - heading "代码仓库" [level=3] [ref=e110]
                - article [ref=e111]:
                  - generic [ref=e112]:
                    - strong [ref=e113]: Ollama · 发布记录
                    - generic [ref=e114]: 未验证
                  - paragraph [ref=e115]: Ollama 官方仓库的发布元数据。
                  - generic [ref=e116]:
                    - code [ref=e117]: ollama_releases
                    - button "选择 Ollama · 发布记录" [ref=e118] [cursor=pointer]
              - generic [ref=e119]:
                - heading "技术博客" [level=3] [ref=e120]
                - article [ref=e121]:
                  - generic [ref=e122]:
                    - strong [ref=e123]: Trail of Bits · 研究文章
                    - generic [ref=e124]: 未验证
                  - paragraph [ref=e125]: 固定研究博客的 RSS 发现与片段。
                  - generic [ref=e126]:
                    - code [ref=e127]: trailofbits_blog
                    - button "选择 Trail of Bits · 研究文章" [ref=e128] [cursor=pointer]
              - generic [ref=e129]:
                - heading "学术论文" [level=3] [ref=e130]
                - article [ref=e131]:
                  - generic [ref=e132]:
                    - strong [ref=e133]: arXiv · AI 安全论文
                    - generic [ref=e134]: 未验证
                  - paragraph [ref=e135]: 固定 AI 安全检索的论文元数据与摘要。
                  - generic [ref=e136]:
                    - code [ref=e137]: arxiv_security
                    - button "选择 arXiv · AI 安全论文" [ref=e138] [cursor=pointer]
              - generic [ref=e139]:
                - heading "技术标准" [level=3] [ref=e140]
                - article [ref=e141]:
                  - generic [ref=e142]:
                    - strong [ref=e143]: NIST · AI RMF 1.0
                    - generic [ref=e144]: 未验证
                  - paragraph [ref=e145]: NIST AI RMF 1.0 原文框架。
                  - generic [ref=e146]:
                    - code [ref=e147]: nist_ai_rmf
                    - button "选择 NIST · AI RMF 1.0" [ref=e148] [cursor=pointer]
              - generic [ref=e149]:
                - heading "政策法规" [level=3] [ref=e150]
                - article [ref=e151]:
                  - generic [ref=e152]:
                    - strong [ref=e153]: 网信办 · 生成式人工智能办法
                    - generic [ref=e154]: 未验证
                  - paragraph [ref=e155]: 生成式人工智能服务管理办法官方资料。
                  - generic [ref=e156]:
                    - code [ref=e157]: cac_generative_ai
                    - button "选择 网信办 · 生成式人工智能办法" [ref=e158] [cursor=pointer]
          - generic [ref=e159]:
            - region [ref=e160]:
              - generic [ref=e162]:
                - paragraph [ref=e163]: COLLECT / 单源提交
                - heading "提交采集轮次" [level=2] [ref=e164]
              - generic [ref=e165]:
                - strong [ref=e166]: NVD · Ollama
                - paragraph [ref=e167]: 关键词结果不代表全生态覆盖；每个任务处理一页。
              - form "固定来源采集" [ref=e168]:
                - generic [ref=e169]:
                  - text: 固定来源
                  - combobox "固定来源" [ref=e170]:
                    - option "NVD · Ollama" [selected]
                    - option "vLLM · 厂商公告"
                    - option "OSV · Ollama Go 包"
                    - option "AVID · AI 社区报告"
                    - option "Ollama · 发布记录"
                    - option "Trail of Bits · 研究文章"
                    - option "arXiv · AI 安全论文"
                    - option "NIST · AI RMF 1.0"
                    - option "网信办 · 生成式人工智能办法"
                - generic [ref=e171]:
                  - generic [ref=e172]:
                    - text: 采集流
                    - combobox "采集流" [ref=e173]:
                      - option "实时流 / live" [selected]
                      - option "回补流 / backfill"
                  - generic [ref=e174]:
                    - text: 本轮页上限
                    - spinbutton "本轮页上限" [ref=e175]: "5"
                - generic [ref=e176]:
                  - text: 观察窗口截止（含时区）
                  - textbox "观察窗口截止（含时区）" [ref=e177]: 2026-10-15T22:52:41+08:00
                - paragraph [ref=e178]: 窗口是本轮观察标识，不保证上游快照或完整时间过滤。202只表示PG受理，不表示来源采完。
                - button "提交本轮采集" [ref=e179] [cursor=pointer]
            - region [ref=e180]:
              - generic [ref=e181]:
                - generic [ref=e182]:
                  - paragraph [ref=e183]: JOB / PG单页任务
                  - heading "任务状态查询" [level=2] [ref=e184]
                - generic [ref=e185]: 手动刷新
              - form "查询单页任务" [ref=e186]:
                - generic [ref=e187]:
                  - text: 任务标识
                  - textbox "任务标识" [ref=e188]:
                    - /placeholder: 输入已保存的job UUID
                - button "查询 / 刷新任务" [disabled] [ref=e189]
                - paragraph [ref=e190]: 保存任务标识可在返回本页后重新查询。此处没有任务历史、全来源计数或自动轮询。
              - generic [ref=e191]:
                - heading "尚未查询任务" [level=3] [ref=e192]
                - paragraph [ref=e193]: 提交一轮取得任务标识，或输入已有标识查询。尚未查询不等于没有任务。
      - generic [ref=e194]:
        - generic [ref=e195]: 环境 test
        - generic [ref=e196]: 版本 0.1.0
```

# Test source

```ts
  1   | const { test, expect } = require("D:/wt/r06-integrated-live-1156/frontend/node_modules/@playwright/test");
  2   | const fs = require("node:fs");
  3   | const path = require("node:path");
  4   | const crypto = require("node:crypto");
  5   | 
  6   | /** Only actual API responses; the source and login secrets stay in process memory. */
  7   | const collected = JSON.parse(fs.readFileSync(path.join(__dirname, "collection_receipt.json"), "utf8"));
  8   | const roots = collected.jobs.filter((job) => (job.idempotency_key ?? "").startsWith("source-poll-v1:"));
  9   | const representatives = Object.entries(collected.representative_documents);
  10  | const saved = (collected.representative_documents.nist_ai_rmf ?? collected.representative_documents.cac_generative_ai ?? representatives[0]?.[1])?.document;
  11  | const sourceKinds = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];
  12  | 
  13  | async function login(page, role) {
  14  |   await page.goto("/#session");
  15  |   await page.getByLabel("用户名", { exact: true }).fill(process.env.DIANZI_E2E_USERNAME + "-r06-integrated-" + role);
  16  |   await page.getByLabel("密码", { exact: true }).fill(process.env.DIANZI_E2E_PASSWORD);
  17  |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  18  |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  19  | }
  20  | 
  21  | test("real admin nine-source catalog queries actual default-beat PG jobs", async ({ page }, testInfo) => {
  22  |   await page.setViewportSize({ width: 1366, height: 900 });
  23  |   await login(page, "admin");
  24  |   await page.goto("/#sources");
  25  |   const select = page.getByLabel("固定来源", { exact: true });
> 26  |   await expect(select.locator("option")).toHaveCount(9);
      |                                          ^ Error: expect(locator).toHaveCount(expected) failed
  27  |   expect(await select.locator("option").evaluateAll((options) => options.map((option) => option.value))).toEqual(sourceKinds);
  28  |   await expect(page.getByRole("heading", { name: "固定来源目录", exact: true })).toBeVisible();
  29  |   const observations = [];
  30  |   for (const key of sourceKinds) {
  31  |     const job = roots.find((candidate) => candidate.request.source_kind === key);
  32  |     expect(job).toBeTruthy();
  33  |     await select.selectOption(key);
  34  |     await page.getByLabel("任务标识", { exact: true }).fill(job.job_id);
  35  |     const received = page.waitForResponse((response) => response.url().endsWith("/v1/jobs/" + job.job_id));
  36  |     await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  37  |     const response = await received;
  38  |     expect(response.status()).toBe(200);
  39  |     const actual = await response.json();
  40  |     await expect(page.getByRole("article", { name: "当前单页任务", exact: true })).toBeVisible();
  41  |     await expect(page.getByRole("article", { name: "当前单页任务", exact: true }).getByText(job.job_id, { exact: true })).toBeVisible();
  42  |     observations.push({ source_kind: key, job_id: job.job_id, actual_status: actual.status, error_code: actual.error_code, http_status: response.status() });
  43  |   }
  44  |   await page.getByTestId("ambient-backdrop").evaluate((element) => element.scrollIntoView());
  45  |   await page.evaluate(() => window.scrollTo(0, 0));
  46  |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  47  |   await page.screenshot({ path: path.join(__dirname, "source-admin-visible-1366.png"), fullPage: false });
  48  |   await testInfo.attach("actual-nine-source-job-statuses", { body: JSON.stringify({ code_sha: collected.code_sha, observations, request_interception: false }), contentType: "application/json" });
  49  | });
  50  | 
  51  | test("real admin submits one bounded CAC backfill through existing REST CSRF and worker", async ({ page }, testInfo) => {
  52  |   await login(page, "admin");
  53  |   await page.goto("/#sources");
  54  |   await page.getByLabel("固定来源", { exact: true }).selectOption("cac_generative_ai");
  55  |   await page.getByLabel("采集流", { exact: true }).selectOption("backfill");
  56  |   await page.getByLabel("本轮页上限", { exact: true }).fill("1");
  57  |   await page.getByLabel("观察窗口截止（含时区）", { exact: true }).fill(new Date().toISOString());
  58  |   const received = page.waitForResponse((response) => response.url().endsWith("/v1/sources/cac_generative_ai/collect"));
  59  |   await page.getByRole("button", { name: "提交本轮采集", exact: true }).click();
  60  |   const response = await received;
  61  |   expect(response.status()).toBe(202);
  62  |   const accepted = await response.json();
  63  |   await expect(page.getByRole("heading", { name: "本轮已受理", exact: true })).toBeVisible();
  64  |   let actual = accepted;
  65  |   for (let attempts = 0; attempts < 20; attempts += 1) {
  66  |     if (["succeeded", "partial", "failed", "blocked", "cancelled"].includes(actual.status)) break;
  67  |     await page.waitForTimeout(3000);
  68  |     const lookup = page.waitForResponse((item) => item.url().endsWith("/v1/jobs/" + accepted.job_id));
  69  |     await page.getByRole("button", { name: "查询 / 刷新任务", exact: true }).click();
  70  |     const result = await lookup;
  71  |     expect(result.status()).toBe(200);
  72  |     actual = await result.json();
  73  |   }
  74  |   expect(["succeeded", "partial", "failed", "blocked", "cancelled"]).toContain(actual.status);
  75  |   fs.writeFileSync(path.join(__dirname, "browser_manual_collection.json"), JSON.stringify({ observed_at_utc: new Date().toISOString(), code_sha: collected.code_sha, source_kind: "cac_generative_ai", stream_kind: "backfill", max_pages: 1, actual_job: actual, csrf_from_real_pg_session: true, external_failure_not_rewritten_as_success: true }, null, 2));
  76  |   await testInfo.attach("actual-bounded-manual-source", { body: JSON.stringify({ job_id: accepted.job_id, status: actual.status, error_code: actual.error_code, manual_one_page_separate_from_beat_roots: true }), contentType: "application/json" });
  77  | });
  78  | 
  79  | for (const width of [1366, 390]) {
  80  |   test(`real viewer source denial and document evidence history refresh motion privacy ${width}px`, async ({ page }, testInfo) => {
  81  |     expect(saved).toBeTruthy();
  82  |     await page.setViewportSize({ width, height: 900 });
  83  |     await login(page, "viewer");
  84  |     let sourceRequests = 0;
  85  |     page.on("request", (request) => { if (/\/v1\/(sources|jobs)\//.test(request.url())) sourceRequests += 1; });
  86  |     await page.goto("/#sources");
  87  |     await expect(page.getByRole("heading", { name: "没有来源调度权限", exact: true })).toBeVisible();
  88  |     expect(sourceRequests).toBe(0);
  89  |     await page.goto("/#documents");
  90  |     const checkedCategories = [];
  91  |     for (const category of [...new Set(representatives.map(([, sample]) => sample.document.source_category))]) {
  92  |       await page.getByLabel("来源类别", { exact: true }).selectOption(category);
  93  |       const loaded = page.waitForResponse((response) => response.url().includes("/v1/documents?") && new URL(response.url()).searchParams.get("source_category") === category);
  94  |       await page.getByRole("button", { name: "检索资料", exact: true }).click();
  95  |       const response = await loaded;
  96  |       expect(response.status()).toBe(200);
  97  |       const body = await response.json();
  98  |       expect(body.items.length).toBeGreaterThan(0);
  99  |       expect(body.items.every((item) => item.source_category === category)).toBe(true);
  100 |       checkedCategories.push(category);
  101 |     }
  102 |     await page.goto("/#documents/" + saved.document_id);
  103 |     await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
  104 |     await page.getByLabel("检索关键词", { exact: true }).fill(saved.title);
  105 |     const loaded = page.waitForResponse((response) => response.url().includes("/v1/documents?") && new URL(response.url()).searchParams.get("q") === saved.title);
  106 |     await page.getByRole("button", { name: "检索资料", exact: true }).click();
  107 |     await loaded;
  108 |     await page.getByRole("list", { name: "已保存资料列表", exact: true }).getByRole("link", { name: saved.title, exact: true }).click();
  109 |     await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
  110 |     const quote = await page.locator(".document-evidence blockquote").first().textContent();
  111 |     expect(quote.length).toBeGreaterThan(0);
  112 |     const quoteHash = crypto.createHash("sha256").update(quote).digest("hex");
  113 |     await page.locator(".document-evidence summary").first().click();
  114 |     await expect(page.getByText(quoteHash, { exact: true })).toBeVisible();
  115 |     await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveValue(saved.revision_id);
  116 |     await expect(page.getByTestId("ambient-backdrop")).toHaveCSS("pointer-events", "none");
  117 |     await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "topology-drift");
  118 |     await page.emulateMedia({ reducedMotion: "reduce" });
  119 |     await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "none");
  120 |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  121 |     if (width === 390) await page.locator(".document-inspector").scrollIntoViewIfNeeded();
  122 |     else await page.evaluate(() => window.scrollTo(0, 0));
  123 |     await page.screenshot({ path: path.join(__dirname, `document-visible-${width}.png`), fullPage: false });
  124 |     await page.reload();
  125 |     await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
  126 |     await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveValue(saved.revision_id);
```