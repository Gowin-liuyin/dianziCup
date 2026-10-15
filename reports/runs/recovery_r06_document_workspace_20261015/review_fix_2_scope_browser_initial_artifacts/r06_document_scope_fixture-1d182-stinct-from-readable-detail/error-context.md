# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r06_document_scope_fixture.spec.ts >> isolated catalog 503 keeps query failure distinct from readable detail
- Location: e2e\r06_document_scope_fixture.spec.ts:51:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 2
Received: 4

Call Log:
- Timeout 10000ms exceeded while waiting on the predicate
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
            - generic [ref=e62]: 失败
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
          - generic [ref=e74]:
            - heading "资料依赖暂不可用" [level=3] [ref=e75]
            - alert [ref=e76]:
              - paragraph [ref=e77]: 本次读取失败，不能据此判断为空或无风险。恢复服务后请重新查询。
              - button "重新查询资料" [ref=e78] [cursor=pointer]
        - region [active] [ref=e79]:
          - generic [ref=e80]:
            - heading "资料检视" [level=2] [ref=e81]
            - link "关闭详情" [ref=e82] [cursor=pointer]:
              - /url: "#documents"
          - generic [ref=e83]:
            - paragraph [ref=e84]: 合成 / Fixture · 论文 · 当前版本
            - heading "隔离测试：模型风险研究资料" [level=3] [ref=e85]
            - generic [ref=e86]:
              - generic [ref=e87]: 修订 2
              - generic [ref=e88]: 部分解析
              - generic [ref=e89]: 仅摘要
            - generic [ref=e90]:
              - term [ref=e91]: 来源
              - definition [ref=e92]: 隔离测试学术来源
              - term [ref=e93]: 来源类别
              - definition [ref=e94]: 学术论文
              - term [ref=e95]: 文档标识
              - definition [ref=e96]:
                - code [ref=e97]: 00000000-0000-4000-8000-000000000101
              - term [ref=e98]: 原文修订
              - definition [ref=e99]:
                - code [ref=e100]: 00000000-0000-4000-8000-000000000102
              - term [ref=e101]: 发布日期精度
              - definition [ref=e102]:
                - generic [ref=e103]: 2026-10-14
                - generic [ref=e104]: 仅日期 · 时刻未知
              - term [ref=e105]: 源发布时间
              - definition [ref=e106]: 未知 / 未留存
              - term [ref=e107]: 源修订时间
              - definition [ref=e108]: 未知 / 未留存
              - term [ref=e109]: 首次观察
              - definition [ref=e110]:
                - time [ref=e111]: 2026-10-15T10:00:00+08:00
              - term [ref=e112]: 入库完成
              - definition [ref=e113]:
                - time [ref=e114]: 2026-10-15T10:00:01+08:00
              - term [ref=e115]: 许可
              - definition [ref=e116]: 未知 / 未留存
            - link "打开此版本来源地址 ↗" [ref=e117] [cursor=pointer]:
              - /url: https://example.test/isolated-paper
            - generic [ref=e118]:
              - heading "来源与覆盖说明" [level=4] [ref=e119]
              - paragraph [ref=e120]: 隔离测试：仅保存摘要，正文未抓取。
            - generic [ref=e121]:
              - heading "选择保存的版本" [level=4] [ref=e122]
              - generic [ref=e123]: 原文修订版本
              - combobox "原文修订版本" [ref=e124]:
                - option "修订 2 · 当前 · 隔离测试：模型风险研究资料" [selected]
              - paragraph [ref=e125]: 已取得 1 个版本 · 本次版本查询已结束
            - generic [ref=e126]:
              - heading "原文与证据片段" [level=4] [ref=e127]
              - generic [ref=e128]: 已取得 1 / 1 段
            - paragraph [ref=e129]: 引文存在不等于内容支持。资料中的主张尚不能作为本系统确认的风险结论。
            - paragraph [ref=e130]: 覆盖：仅摘要。未保存完整正文。
            - article [ref=e131]:
              - generic [ref=e132]:
                - heading "原文片段 1" [level=4] [ref=e133]
                - generic [ref=e134]: 定位已核验
              - blockquote [ref=e135]: 隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。
              - group [ref=e136]:
                - generic "展开定位与证据记录" [ref=e137] [cursor=pointer]
      - generic [ref=e138]:
        - generic [ref=e139]: 环境未由服务端标明
        - generic [ref=e140]: 版本未由服务端标明
```

# Test source

```ts
  1  | import { expect, test, type Page } from "@playwright/test";
  2  | import { detailFixture, documentFixture, documentId, evidenceFixture } from "../tests/document-fixture";
  3  | 
  4  | /** 仅浏览器内显式合成响应；等待已取消的延迟请求处理结束后检查不可见资料。 */
  5  | async function install(page: Page, status: number, allowedLists = 0) {
  6  |   let release = () => {};
  7  |   const barrier = new Promise<void>((resolve) => { release = resolve; });
  8  |   let lists = 0;
  9  |   let settled = 0;
  10 |   const cancelled = new Set<string>();
  11 |   page.on("requestfailed", (request) => { if (new URL(request.url()).pathname.startsWith(`/v1/documents/${documentId}`)) cancelled.add(request.url()); });
  12 |   await page.route("**/v1/**", async (route) => {
  13 |     const url = new URL(route.request().url()); const path = url.pathname;
  14 |     let body: unknown; let responseStatus = 200;
  15 |     if (path === "/v1/auth/me") body = { user_id: "isolated-scope-browser", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
  16 |     else if (path === "/v1/health/live") body = { status: "live" };
  17 |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
  18 |     else if (path === "/v1/documents") { lists += 1; if (lists > allowedLists) { responseStatus = status; body = { error: { code: status === 403 ? "forbidden" : "fixture_failure" } }; } else body = { schema_version: 2, items: [documentFixture], next_cursor: "isolated-scope-cursor", data_mode: "fixture" }; }
  19 |     else if (path.endsWith("/revisions")) { await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
  20 |     else if (path === `/v1/documents/${documentId}`) { await barrier; body = detailFixture; }
  21 |     else throw new Error(`Unexpected isolated scope browser request ${path}`);
  22 |     await route.fulfill({ status: responseStatus, json: body });
  23 |     if (path.startsWith(`/v1/documents/${documentId}`)) settled += 1;
  24 |   });
  25 |   return { release, cancelled, settled: () => settled };
  26 | }
  27 | async function expectPrivateContentAbsent(page: Page) {
  28 |   await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toHaveCount(0);
  29 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  30 |   await expect(page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true })).toHaveCount(0);
  31 |   await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveCount(0);
  32 | }
  33 | for (const status of [403, 401]) {
  34 |   test(`isolated catalog HTTP ${status} cancels deep-link inspection before late success`, async ({ page }, testInfo) => {
  35 |     const fixture = await install(page, status); await page.goto(`/#documents/${documentId}`);
  36 |     if (status === 403) await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  37 |     else await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  38 |     try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
  39 |     await expect.poll(fixture.settled).toBe(2); await expectPrivateContentAbsent(page);
  40 |     await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath(`catalog-${status}-scope-cleared.png`), fullPage: true });
  41 |   });
  42 | }
  43 | test("isolated next-page catalog denial cancels old inspection", async ({ page }) => {
  44 |   const fixture = await install(page, 403, 1); await page.goto(`/#documents/${documentId}`);
  45 |   await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
  46 |   await page.getByRole("button", { name: "下一页资料", exact: true }).click();
  47 |   await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  48 |   try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
  49 |   await expect.poll(fixture.settled).toBe(2); await expectPrivateContentAbsent(page);
  50 | });
  51 | test("isolated catalog 503 keeps query failure distinct from readable detail", async ({ page }) => {
  52 |   const fixture = await install(page, 503); await page.goto(`/#documents/${documentId}`);
  53 |   await expect(page.getByRole("heading", { name: "资料依赖暂不可用", exact: true })).toBeVisible(); fixture.release();
> 54 |   await expect.poll(fixture.settled).toBe(2);
     |                                      ^ Error: expect(received).toBe(expected) // Object.is equality
  55 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  56 |   await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0);
  57 | });
  58 | 
```