# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: integrated-live.spec.cjs >> real viewer source denial and document evidence history refresh motion privacy 1366px
- Location: ..\..\..\dianzi\reports\runs\recovery_r06_integrated_live_20261015\integrated-live.spec.cjs:80:3

# Error details

```
Test timeout of 100000ms exceeded.
```

```
Error: locator.click: Test timeout of 100000ms exceeded.
Call log:
  - waiting for getByRole('list', { name: '已保存资料列表', exact: true }).getByRole('link', { name: 'Artificial Intelligence Risk Management Framework (AI RMF 1.0)', exact: true })

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
        - text: 资料库
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 真实 / Live
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: RESEARCH / DOCUMENTS
          - heading "资料与原文" [level=1] [ref=e54]: 资料与原文_
          - paragraph [ref=e55]: 核查论文、标准、政策与研究资料的原文版本和覆盖范围。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - generic [ref=e58]:
        - region [ref=e59]:
          - generic [ref=e60]:
            - heading "已保存资料" [level=2] [ref=e61]
            - generic [ref=e62]: 本次查询为空
          - form "资料筛选" [ref=e64]:
            - generic [ref=e65]:
              - text: 检索关键词
              - textbox "检索关键词" [ref=e66]:
                - /placeholder: 已保存资料的标题关键词
                - text: Artificial Intelligence Risk Management Framework (AI RMF 1.0)
            - generic [ref=e67]:
              - generic [ref=e68]:
                - text: 资料类型
                - combobox "资料类型" [ref=e69]:
                  - option "全部资料" [selected]
                  - option "安全公告"
                  - option "研究文章"
                  - option "论文"
                  - option "仓库记录"
                  - option "技术标准"
                  - option "政策法规"
              - generic [ref=e70]:
                - text: 来源类别
                - combobox "来源类别" [ref=e71]:
                  - option "全部来源类别"
                  - option "结构化漏洞库"
                  - option "厂商公告"
                  - option "安全社区"
                  - option "代码仓库"
                  - option "技术博客"
                  - option "学术论文"
                  - option "技术标准"
                  - option "政策法规" [selected]
            - button "检索资料" [ref=e72] [cursor=pointer]
            - paragraph [ref=e73]: 仅检索已保存标题。资料覆盖与风险确认分别核查。
          - paragraph [ref=e74]: 本页 0 条 · 真实 / Live
          - generic [ref=e75]:
            - heading "本次查询没有资料记录" [level=3] [ref=e76]
            - paragraph [ref=e77]: 本次授权范围与筛选没有返回资料，不能推论相关研究或风险不存在。
          - list "已保存资料列表"
          - generic [ref=e78]:
            - button "回到第一页" [disabled] [ref=e79]
            - button "下一页资料" [disabled] [ref=e80]
        - complementary [ref=e81]:
          - paragraph [ref=e82]: 原文核查
          - heading "读资料 留意证据范围" [level=2] [ref=e83]: 读资料留意证据范围
          - paragraph [ref=e84]: 选择资料，核查保存的版本、发布时间精度与原文覆盖。
          - generic [ref=e85]:
            - term [ref=e86]: 论文
            - definition [ref=e87]: 研究主张与确认事实分别核查。
            - term [ref=e88]: 标准与政策
            - definition [ref=e89]: 版本、建议、义务和适用范围以原文为准。
            - term [ref=e90]: 原文证据
            - definition [ref=e91]: 定位已核验仍需确认片段是否支持论断。
          - paragraph [ref=e92]: 未知保持未知
      - generic [ref=e93]:
        - generic [ref=e94]: 环境 test
        - generic [ref=e95]: 版本 0.1.0
```

# Test source

```ts
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
  26  |   await expect(select.locator("option")).toHaveCount(9);
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
> 108 |     await page.getByRole("list", { name: "已保存资料列表", exact: true }).getByRole("link", { name: saved.title, exact: true }).click();
      |                                                                                                                          ^ Error: locator.click: Test timeout of 100000ms exceeded.
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
  127 |     await page.getByLabel("原文修订版本", { exact: true }).selectOption(saved.revision_id);
  128 |     await expect(page.locator(".document-evidence blockquote").first()).toHaveText(quote);
  129 |     await page.getByLabel("检索关键词", { exact: true }).fill("__r06_confirmed_empty_" + crypto.randomUUID());
  130 |     await page.getByRole("button", { name: "检索资料", exact: true }).click();
  131 |     await expect(page.getByRole("heading", { name: "本次查询没有资料记录", exact: true })).toBeVisible();
  132 |     await page.goto("/#session");
  133 |     await page.getByRole("button", { name: "退出登录", exact: true }).click();
  134 |     await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
  135 |     await page.goto("/#documents/" + saved.document_id);
  136 |     await expect(page.getByRole("heading", { name: "登录后核查资料", exact: true })).toBeVisible();
  137 |     await expect(page.locator(".document-evidence blockquote")).toHaveCount(0);
  138 |     await testInfo.attach("real-document-observation", { body: JSON.stringify({ code_sha: collected.code_sha, width, checked_categories: checkedCategories, document_id: saved.document_id, revision_id: saved.revision_id, quote_hash: quoteHash, source_requests_from_viewer_sources_page: sourceRequests, request_interception: false, model_calls: 0 }), contentType: "application/json" });
  139 |   });
  140 | }
  141 | 
  142 | test("saved actual publisher source URL opens original policy or release page", async ({ page }, testInfo) => {
  143 |   const original = (collected.representative_documents.cac_generative_ai ?? collected.representative_documents.ollama_releases ?? representatives[0]?.[1])?.document;
  144 |   expect(original).toBeTruthy();
  145 |   await login(page, "viewer");
  146 |   await page.goto(`/#documents/${original.document_id}/revision/${original.revision_id}`);
  147 |   const link = page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true });
  148 |   await expect(link).toHaveAttribute("href", original.canonical_uri);
  149 |   const opened = page.waitForEvent("popup");
  150 |   await link.click();
  151 |   const popup = await opened;
  152 |   await popup.waitForLoadState("domcontentloaded", { timeout: 20000 });
  153 |   expect(popup.url()).toBe(original.canonical_uri);
  154 |   const title = await popup.title();
  155 |   expect(title).not.toMatch(/ERR_|not found|404/i);
  156 |   await testInfo.attach("original-publisher-opened", { body: JSON.stringify({ source_uri: original.canonical_uri, actual_url: popup.url(), actual_title: title, code_sha: collected.code_sha }), contentType: "application/json" });
  157 |   await popup.close();
  158 | });
  159 | 
```