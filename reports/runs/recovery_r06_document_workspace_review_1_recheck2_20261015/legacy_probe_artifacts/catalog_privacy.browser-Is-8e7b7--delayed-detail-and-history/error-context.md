# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: catalog_privacy.browser.spec.ts >> Isolated fixture: catalog READ_PUBLIC 403 blocks delayed detail and history
- Location: ..\reports\runs\recovery_r06_document_workspace_review_1_recheck2_20261015\catalog_privacy.browser.spec.ts:3:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。', { exact: true })
Expected: visible
Timeout: 3000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。', { exact: true }) with timeout 3000ms
  - waiting for getByText('隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。', { exact: true })

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
  - complementary:
    - paragraph: 原文核查
    - heading "读资料 留意证据范围" [level=2]
    - paragraph: 选择资料，核查保存的版本、发布时间精度与原文覆盖。
    - term: 论文
    - definition: 研究主张与确认事实分别核查。
    - term: 标准与政策
    - definition: 版本、建议、义务和适用范围以原文为准。
    - term: 原文证据
    - definition: 定位已核验仍需确认片段是否支持论断。
    - paragraph: 未知保持未知
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
  1  | import { expect, test } from "../../../frontend/node_modules/@playwright/test/index.mjs";
  2  | import { documentFixture, detailFixture, documentId, evidenceFixture } from "../../../frontend/tests/document-fixture";
  3  | test("Isolated fixture: catalog READ_PUBLIC 403 blocks delayed detail and history", async ({ page }, testInfo) => {
  4  |   let release = () => {};
  5  |   const barrier = new Promise<void>((resolve) => { release = resolve; });
  6  |   const paths: string[] = [];
  7  |   await page.route("**/v1/**", async (route) => {
  8  |     const url = new URL(route.request().url()); const path = url.pathname; paths.push(path + url.search);
  9  |     let body: unknown; let status = 200;
  10 |     if (path === "/v1/auth/me") body = { user_id: "isolated-catalog-browser-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
  11 |     else if (path === "/v1/health/live") body = { status: "live" };
  12 |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
  13 |     else if (path === "/v1/documents") { status = 403; body = { error: { code: "forbidden" } }; }
  14 |     else if (path.endsWith("/revisions")) { await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
  15 |     else if (path === `/v1/documents/${documentId}`) { await barrier; body = detailFixture; }
  16 |     else throw new Error(`Unexpected fixture ${path}`);
  17 |     await route.fulfill({ status, json: body });
  18 |   });
  19 |   await page.goto(`/#documents/${documentId}`);
  20 |   await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  21 |   release();
> 22 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
     |                                                                             ^ Error: expect(locator).toBeVisible() failed
  23 |   await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath("catalog-403-late-body.png"), fullPage: true });
  24 |   await testInfo.attach("fixture-response-order", { body: JSON.stringify({ paths, catalogStatus: 403, delayedResources: ["detail", "history"], mode: "isolated fixture only" }), contentType: "application/json" });
  25 |   await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  26 | });
  27 | 
```