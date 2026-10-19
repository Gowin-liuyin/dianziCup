# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: review.browser.spec.ts >> Fixture: current link reloads current when the first revision becomes historical during evidence pagination
- Location: ..\reports\runs\recovery_r06_document_workspace_review_1_20261015\review.browser.spec.ts:58:5

# Error details

```
Error: expect(received).toBeGreaterThan(expected)

Expected: > 2
Received:   2

Call Log:
- Timeout 5000ms exceeded while waiting on the predicate
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
        - strong [ref=e49]: 合成 / Fixture
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
            - generic [ref=e62]: 已取得本页
          - form "资料筛选" [ref=e64]:
            - generic [ref=e65]:
              - text: 检索关键词
              - textbox "检索关键词" [ref=e66]:
                - /placeholder: 已保存资料的标题关键词
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
                  - option "全部来源类别" [selected]
                  - option "结构化漏洞库"
                  - option "厂商公告"
                  - option "安全社区"
                  - option "代码仓库"
                  - option "技术博客"
                  - option "学术论文"
                  - option "技术标准"
                  - option "政策法规"
            - button "检索资料" [ref=e72] [cursor=pointer]
            - paragraph [ref=e73]: 仅检索已保存标题。资料覆盖与风险确认分别核查。
          - paragraph [ref=e74]: 本页 1 条 · 合成 / Fixture
          - list "已保存资料列表" [ref=e75]:
            - listitem [ref=e76]:
              - generic [ref=e77]:
                - generic [ref=e78]: 论文
                - generic [ref=e79]: 仅摘要
              - link "隔离测试：模型风险研究资料" [ref=e80] [cursor=pointer]:
                - /url: "#documents/00000000-0000-4000-8000-000000000101"
              - paragraph [ref=e81]: 隔离测试学术来源 · 修订 2
              - generic [ref=e82]:
                - generic [ref=e83]: 2026-10-14
                - generic [ref=e84]: 仅日期 · 时刻未知
          - generic [ref=e85]:
            - button "回到第一页" [disabled] [ref=e86]
            - button "下一页资料" [disabled] [ref=e87]
        - region [ref=e88]:
          - generic [ref=e89]:
            - heading "资料检视" [level=2] [ref=e90]
            - link "关闭详情" [ref=e91] [cursor=pointer]:
              - /url: "#documents"
          - generic [ref=e92]:
            - paragraph [ref=e93]: 合成 / Fixture · 论文 · 历史版本
            - heading "隔离测试：模型风险研究资料" [level=3] [ref=e94]
            - generic [ref=e95]:
              - generic [ref=e96]: 修订 2
              - generic [ref=e97]: 部分解析
              - generic [ref=e98]: 仅摘要
            - paragraph [ref=e99]:
              - text: 正在查看保存的历史修订，标题和证据属于此版本。
              - link "查看当前版本 →" [active] [ref=e100] [cursor=pointer]:
                - /url: "#documents/00000000-0000-4000-8000-000000000101"
            - generic [ref=e101]:
              - term [ref=e102]: 来源
              - definition [ref=e103]: 隔离测试学术来源
              - term [ref=e104]: 来源类别
              - definition [ref=e105]: 学术论文
              - term [ref=e106]: 文档标识
              - definition [ref=e107]:
                - code [ref=e108]: 00000000-0000-4000-8000-000000000101
              - term [ref=e109]: 原文修订
              - definition [ref=e110]:
                - code [ref=e111]: 00000000-0000-4000-8000-000000000102
              - term [ref=e112]: 发布日期精度
              - definition [ref=e113]:
                - generic [ref=e114]: 2026-10-14
                - generic [ref=e115]: 仅日期 · 时刻未知
              - term [ref=e116]: 源发布时间
              - definition [ref=e117]: 未知 / 未留存
              - term [ref=e118]: 源修订时间
              - definition [ref=e119]: 未知 / 未留存
              - term [ref=e120]: 首次观察
              - definition [ref=e121]:
                - time [ref=e122]: 2026-10-15T10:00:00+08:00
              - term [ref=e123]: 入库完成
              - definition [ref=e124]:
                - time [ref=e125]: 2026-10-15T10:00:01+08:00
              - term [ref=e126]: 许可
              - definition [ref=e127]: 未知 / 未留存
            - link "打开此版本来源地址 ↗" [ref=e128] [cursor=pointer]:
              - /url: https://example.test/isolated-paper
            - generic [ref=e129]:
              - heading "来源与覆盖说明" [level=4] [ref=e130]
              - paragraph [ref=e131]: 隔离测试：仅保存摘要，正文未抓取。
            - generic [ref=e132]:
              - heading "选择保存的版本" [level=4] [ref=e133]
              - generic [ref=e134]: 原文修订版本
              - combobox "原文修订版本" [ref=e135]:
                - option "修订 2 · 当前 · 隔离测试：模型风险研究资料" [selected]
              - paragraph [ref=e136]: 已取得 1 个版本 · 还有版本未加载
              - button "加载更多历史版本" [ref=e137] [cursor=pointer]
            - generic [ref=e138]:
              - heading "原文与证据片段" [level=4] [ref=e139]
              - generic [ref=e140]: 已取得 2 / 2 段
            - paragraph [ref=e141]: 引文存在不等于内容支持。资料中的主张尚不能作为本系统确认的风险结论。
            - paragraph [ref=e142]: 覆盖：仅摘要。未保存完整正文。
            - article [ref=e143]:
              - generic [ref=e144]:
                - heading "原文片段 1" [level=4] [ref=e145]
                - generic [ref=e146]: 定位已核验
              - blockquote [ref=e147]: 隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。
              - group [ref=e148]:
                - generic "展开定位与证据记录" [ref=e149] [cursor=pointer]
            - article [ref=e150]:
              - generic [ref=e151]:
                - heading "原文片段 2" [level=4] [ref=e152]
                - generic [ref=e153]: 定位已核验
              - blockquote [ref=e154]: 隔离测试：旧版本晚到原文
              - group [ref=e155]:
                - generic "展开定位与证据记录" [ref=e156] [cursor=pointer]
      - generic [ref=e157]:
        - generic [ref=e158]: 环境未由服务端标明
        - generic [ref=e159]: 版本未由服务端标明
```

# Test source

```ts
  1  | import { expect, test, type Page } from "../../../frontend/node_modules/@playwright/test/index.mjs";
  2  | import { documentFixture, detailFixture, documentId, evidenceFixture, historicalRevisionId, revisionId } from "../../../frontend/tests/document-fixture";
  3  | 
  4  | async function install(page: Page, options: { historyStatus?: number; delayedEvidence?: boolean; lateDetail?: boolean; currentChanged?: boolean } = {}) {
  5  |   const paths: string[] = [];
  6  |   let release = () => {};
  7  |   const barrier = new Promise<void>((resolve) => { release = resolve; });
  8  |   let userNumber = 1;
  9  |   let revisionBecameHistorical = false;
  10 |   await page.route("**/v1/**", async (route) => {
  11 |     const url = new URL(route.request().url()); const path = url.pathname; paths.push(path + url.search);
  12 |     let body: unknown; let status = 200;
  13 |     if (path === "/v1/auth/me") body = { user_id: `independent-fixture-user-${userNumber}`, tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: userNumber, data_mode: "fixture", csrf_token: "b".repeat(64) };
  14 |     else if (path === "/v1/auth/login") { userNumber += 1; body = { user_id: `independent-fixture-user-${userNumber}`, csrf_token: "b".repeat(64), expires_at: "2026-10-16T00:00:00Z" }; }
  15 |     else if (path === "/v1/auth/logout") body = { status: "logged_out" };
  16 |     else if (path === "/v1/health/live") body = { status: "live" };
  17 |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
  18 |     else if (path === "/v1/documents") body = { schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" };
  19 |     else if (path.endsWith("/revisions")) {
  20 |       if (url.searchParams.get("offset") === "1" && options.historyStatus) { status = options.historyStatus; body = { error: { code: "fixture_permission" } }; }
  21 |       else body = { schema_version: 2, items: [documentFixture], next_offset: 1, data_mode: "fixture" };
  22 |     } else if (path === `/v1/documents/${documentId}`) {
  23 |       const old = url.searchParams.get("revision_id") === historicalRevisionId;
  24 |       const more = url.searchParams.get("evidence_offset") === "1";
  25 |       if (more && options.currentChanged) revisionBecameHistorical = true;
  26 |       const firstUser = userNumber === 1;
  27 |       if ((more && options.delayedEvidence) || (!old && firstUser && options.lateDetail)) await barrier;
  28 |       body = { ...detailFixture, document: { ...documentFixture, ...(old ? { title: "隔离测试：新选历史版本", revision_id: historicalRevisionId, is_current: false, revision_number: 1 } : {}), ...(options.currentChanged && more ? { is_current: false } : {}), ...(options.currentChanged && revisionBecameHistorical && !more ? { title: "隔离测试：最新版本标题" } : {}) }, evidence: [{ ...evidenceFixture, ...(old ? { revision_id: historicalRevisionId, quote_text: "隔离测试：新历史原文" } : {}), ...(more ? { span_id: "00000000-0000-4000-8000-000000000199", quote_text: "隔离测试：旧版本晚到原文" } : {}), ...(options.lateDetail ? { quote_text: firstUser ? "隔离测试：旧会话晚到原文" : "隔离测试：新会话原文" } : {}) }], evidence_total: 2, next_evidence_offset: more ? null : 1 };
  29 |     } else throw new Error(`Unexpected fixture ${path}`);
  30 |     await route.fulfill({ status, json: body });
  31 |   });
  32 |   return { paths, release };
  33 | }
  34 | 
  35 | for (const status of [403, 404]) {
  36 |   test(`Fixture: history ${status} must remove previously loaded title and evidence`, async ({ page }, testInfo) => {
  37 |     await install(page, { historyStatus: status }); await page.goto(`/#documents/${documentId}`);
  38 |     await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  39 |     await page.getByRole("button", { name: "加载更多历史版本", exact: true }).click();
  40 |     await expect(page.getByRole("heading", { name: status === 403 ? "没有资料查看权限" : "资料或版本不可访问", exact: true })).toBeVisible();
  41 |     await page.screenshot({ path: testInfo.outputPath(`history-${status}-stale.png`), fullPage: true });
  42 |     await testInfo.attach("fixture-observation", { body: JSON.stringify(await page.evaluate(() => ({ title: document.querySelector(".document-title")?.textContent, evidence: document.querySelector(".document-evidence")?.textContent, error: document.querySelector(".resource-error")?.textContent }))), contentType: "application/json" });
  43 |     await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  44 |   });
  45 | }
  46 | 
  47 | test("Fixture: changing revision discards an old revision's late evidence response", async ({ page }) => {
  48 |   const fixture = await install(page, { delayedEvidence: true }); await page.goto(`/#documents/${documentId}`);
  49 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  50 |   await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click();
  51 |   await expect.poll(() => fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
  52 |   await page.evaluate((hash) => { window.location.hash = hash; }, `#documents/${documentId}/revision/${historicalRevisionId}`);
  53 |   await expect(page.getByText("隔离测试：新历史原文", { exact: true })).toBeVisible(); fixture.release();
  54 |   await expect(page.getByText("隔离测试：旧版本晚到原文", { exact: true })).toHaveCount(0);
  55 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  56 | });
  57 | 
  58 | test("Fixture: current link reloads current when the first revision becomes historical during evidence pagination", async ({ page }, testInfo) => {
  59 |   const fixture = await install(page, { currentChanged: true }); await page.goto(`/#documents/${documentId}`);
  60 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  61 |   await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click();
  62 |   await expect(page.getByRole("link", { name: "查看当前版本 →", exact: true })).toBeVisible();
  63 |   expect(fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
  64 |   const previousCurrentReads = fixture.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length;
  65 |   await page.getByRole("link", { name: "查看当前版本 →", exact: true }).click();
  66 |   await page.screenshot({ path: testInfo.outputPath("current-link-stale.png"), fullPage: true });
  67 |   await testInfo.attach("fixture-paths-after-click", { body: JSON.stringify(fixture.paths), contentType: "application/json" });
> 68 |   await expect.poll(() => fixture.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length).toBeGreaterThan(previousCurrentReads);
     |                                                                                                                                                     ^ Error: expect(received).toBeGreaterThan(expected)
  69 |   await expect(page.getByRole("heading", { name: "隔离测试：最新版本标题", exact: true })).toBeVisible();
  70 | });
  71 | 
  72 | test("Fixture: real browser cache does not restore a previous session's delayed detail", async ({ page }) => {
  73 |   const fixture = await install(page, { lateDetail: true }); await page.goto(`/#documents/${documentId}`);
  74 |   await expect(page.getByText("正在取得资料版本与原文…", { exact: true })).toBeVisible();
  75 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  76 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  77 |   await page.getByLabel("用户名", { exact: true }).fill("independent-fixture");
  78 |   await page.getByLabel("密码", { exact: true }).fill("explicit-fixture-only");
  79 |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  80 |   await expect(page.getByText("independent-fixture-user-2", { exact: true })).toBeVisible();
  81 |   await page.getByRole("link", { name: "资料库", exact: true }).click(); await page.getByRole("link", { name: documentFixture.title, exact: true }).click();
  82 |   await expect(page.getByText("隔离测试：新会话原文", { exact: true })).toBeVisible(); fixture.release();
  83 |   await expect(page.getByText("隔离测试：旧会话晚到原文", { exact: true })).toHaveCount(0);
  84 |   await page.reload(); await expect(page.getByText("隔离测试：新会话原文", { exact: true })).toBeVisible();
  85 |   expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  86 | });
  87 | 
```