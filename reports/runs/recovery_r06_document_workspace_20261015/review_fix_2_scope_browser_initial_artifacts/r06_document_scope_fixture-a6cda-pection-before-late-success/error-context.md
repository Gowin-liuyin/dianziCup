# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r06_document_scope_fixture.spec.ts >> isolated catalog HTTP 401 cancels deep-link inspection before late success
- Location: e2e\r06_document_scope_fixture.spec.ts:34:3

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
        - strong [ref=e49]: 登录后确认
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
        - alert [ref=e59]:
          - paragraph [ref=e60]: 会话已失效，请重新登录。
        - generic [ref=e61]:
          - heading "登录后核查资料" [level=3] [ref=e62]
          - paragraph [ref=e63]: 资料与原文版本需要当前团队会话。尚未执行资料查询，不能判断资料数量。
        - link "登录并核对权限" [ref=e64] [cursor=pointer]:
          - /url: "#session"
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
> 39 |     await expect.poll(fixture.settled).toBe(2); await expectPrivateContentAbsent(page);
     |                                        ^ Error: expect(received).toBe(expected) // Object.is equality
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
  54 |   await expect.poll(fixture.settled).toBe(2);
  55 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  56 |   await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0);
  57 | });
  58 | 
```