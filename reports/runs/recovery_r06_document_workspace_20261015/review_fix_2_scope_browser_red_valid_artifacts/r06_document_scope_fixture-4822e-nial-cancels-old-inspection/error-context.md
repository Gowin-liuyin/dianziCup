# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r06_document_scope_fixture.spec.ts >> isolated next-page catalog denial cancels old inspection
- Location: e2e\r06_document_scope_fixture.spec.ts:44:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('link', { name: '隔离测试：模型风险研究资料', exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('link', { name: '隔离测试：模型风险研究资料', exact: true }) with timeout 10000ms
  - waiting for getByRole('link', { name: '隔离测试：模型风险研究资料', exact: true })

```

```yaml
- link "跳到主要内容":
  - /url: "#main-content"
- complementary:
  - link "安全情报 DEFENSE INTELLIGENCE":
    - /url: "#runtime"
  - navigation "工作台导航":
    - paragraph: 研究
    - link "情报列表":
      - /url: "#events"
    - link "来源监测":
      - /url: "#sources"
    - link "资料库":
      - /url: "#documents"
    - link "知识图谱":
      - /url: "#graph"
    - link "引用问答":
      - /url: "#questions"
    - link "资产自查":
      - /url: "#assets"
    - paragraph: 协作
    - link "任务轨迹":
      - /url: "#tasks"
    - link "变化与推荐":
      - /url: "#changes"
    - link "证据报告":
      - /url: "#reports"
    - paragraph: 系统
    - link "运行状态":
      - /url: "#runtime"
    - link "会话与权限":
      - /url: "#session"
  - paragraph: 可追溯的事实 清晰的判断边界
  - text: AI 安全知识情报系统
  - code: READ · VERIFY · CONNECT
- banner:
  - text: 工作台 资料库 数据模式
  - strong: 合成 / Fixture
- main:
  - paragraph: RESEARCH / DOCUMENTS
  - heading "资料与原文" [level=1]
  - paragraph: 核查论文、标准、政策与研究资料的原文版本和覆盖范围。
  - button "刷新状态"
  - region "已保存资料":
    - heading "已保存资料" [level=2]
    - text: 无权限
    - form "资料筛选":
      - text: 检索关键词
      - textbox "检索关键词":
        - /placeholder: 已保存资料的标题关键词
      - text: 资料类型
      - combobox "资料类型":
        - option "全部资料" [selected]
        - option "安全公告"
        - option "研究文章"
        - option "论文"
        - option "仓库记录"
        - option "技术标准"
        - option "政策法规"
      - text: 来源类别
      - combobox "来源类别":
        - option "全部来源类别" [selected]
        - option "结构化漏洞库"
        - option "厂商公告"
        - option "安全社区"
        - option "代码仓库"
        - option "技术博客"
        - option "学术论文"
        - option "技术标准"
        - option "政策法规"
      - button "检索资料"
      - paragraph: 仅检索已保存标题。资料覆盖与风险确认分别核查。
    - heading "没有资料查看权限" [level=3]
    - alert:
      - paragraph: 当前授权不允许查看资料，请核对团队权限。未展示记录标题或数量。
  - region "资料检视":
    - heading "资料检视" [level=2]
    - link "关闭详情":
      - /url: "#documents"
    - status: 正在取得资料版本与原文…
  - text: 环境未由服务端标明 版本未由服务端标明
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
  10 |   let started = 0;
  11 |   const cancelled = new Set<string>();
  12 |   page.on("requestfailed", (request) => { if (new URL(request.url()).pathname.startsWith(`/v1/documents/${documentId}`)) cancelled.add(request.url()); });
  13 |   await page.route("**/v1/**", async (route) => {
  14 |     const url = new URL(route.request().url()); const path = url.pathname;
  15 |     let body: unknown; let responseStatus = 200;
  16 |     if (path === "/v1/auth/me") body = { user_id: "isolated-scope-browser", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
  17 |     else if (path === "/v1/health/live") body = { status: "live" };
  18 |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
  19 |     else if (path === "/v1/documents") { lists += 1; if (lists > allowedLists) { responseStatus = status; body = { error: { code: status === 403 ? "forbidden" : "fixture_failure" } }; } else body = { schema_version: 2, items: [documentFixture], next_cursor: "isolated-scope-cursor", data_mode: "fixture" }; }
  20 |     else if (path.endsWith("/revisions")) { started += 1; await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
  21 |     else if (path === `/v1/documents/${documentId}`) { started += 1; await barrier; body = detailFixture; }
  22 |     else throw new Error(`Unexpected isolated scope browser request ${path}`);
  23 |     await route.fulfill({ status: responseStatus, json: body });
  24 |     if (path.startsWith(`/v1/documents/${documentId}`)) settled += 1;
  25 |   });
  26 |   return { release, cancelled, settled: () => settled, started: () => started };
  27 | }
  28 | async function expectPrivateContentAbsent(page: Page) {
  29 |   await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toHaveCount(0);
  30 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  31 |   await expect(page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true })).toHaveCount(0);
  32 |   await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveCount(0);
  33 | }
  34 | for (const status of [403, 401]) {
  35 |   test(`isolated catalog HTTP ${status} cancels deep-link inspection before late success`, async ({ page }, testInfo) => {
  36 |     const fixture = await install(page, status); await page.goto(`/#documents/${documentId}`);
  37 |     if (status === 403) await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  38 |     else await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  39 |     try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
  40 |     expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started()); await expectPrivateContentAbsent(page);
  41 |     await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath(`catalog-${status}-scope-cleared.png`), fullPage: true });
  42 |   });
  43 | }
  44 | test("isolated next-page catalog denial cancels old inspection", async ({ page }) => {
  45 |   const fixture = await install(page, 403, 1); await page.goto(`/#documents/${documentId}`);
> 46 |   await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
     |                                                                                      ^ Error: expect(locator).toBeVisible() failed
  47 |   await page.getByRole("button", { name: "下一页资料", exact: true }).click();
  48 |   await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  49 |   try { await expect.poll(() => fixture.cancelled.size).toBeGreaterThanOrEqual(2); } finally { fixture.release(); }
  50 |   expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started()); await expectPrivateContentAbsent(page);
  51 | });
  52 | test("isolated catalog 503 keeps query failure distinct from readable detail", async ({ page }) => {
  53 |   const fixture = await install(page, 503); await page.goto(`/#documents/${documentId}`);
  54 |   await expect(page.getByRole("heading", { name: "资料依赖暂不可用", exact: true })).toBeVisible(); fixture.release();
  55 |   expect(fixture.started()).toBeGreaterThanOrEqual(2); await expect.poll(fixture.settled).toBe(fixture.started());
  56 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  57 |   await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0);
  58 | });
  59 | 
```