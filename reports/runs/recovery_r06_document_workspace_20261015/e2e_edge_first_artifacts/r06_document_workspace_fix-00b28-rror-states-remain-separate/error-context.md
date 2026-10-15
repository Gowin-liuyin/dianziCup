# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r06_document_workspace_fixture.spec.ts >> document isolated loading empty metadata and HTTP error states remain separate
- Location: e2e\r06_document_workspace_fixture.spec.ts:70:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: '没有资料查看权限', exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: '没有资料查看权限', exact: true }) with timeout 10000ms
  - waiting for getByRole('heading', { name: '没有资料查看权限', exact: true })

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
    - text: 已取得本页
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
    - paragraph: 本页 1 条 · 合成 / Fixture
    - list "已保存资料列表":
      - listitem:
        - text: 论文 仅摘要
        - link "隔离测试：模型风险研究资料":
          - /url: "#documents/00000000-0000-4000-8000-000000000101"
        - paragraph: 隔离测试学术来源 · 修订 2
        - text: 2026-10-14 仅日期 · 时刻未知
    - button "回到第一页" [disabled]
    - button "下一页资料"
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
  1  | import { randomBytes } from "node:crypto";
  2  | import { expect, test, type Page } from "@playwright/test";
  3  | import { detailFixture, documentFixture, documentId, evidenceFixture, historicalRevisionId, revisionId } from "../tests/document-fixture";
  4  | 
  5  | /** 所有/v1请求仅在本浏览器测试内拦截。此夹具不进入产品代码且不计live。 */
  6  | async function installFixture(page: Page, options: { listStatus?: number; metadataOnly?: boolean; slow?: boolean; empty?: boolean } = {}) {
  7  |   const paths: string[] = [];
  8  |   const csrf = randomBytes(32).toString("hex");
  9  |   let release = () => {};
  10 |   const barrier = new Promise<void>((resolve) => { release = resolve; });
  11 |   await page.route("**/v1/**", async (route) => {
  12 |     const path = new URL(route.request().url()).pathname;
  13 |     const query = new URL(route.request().url()).search;
  14 |     paths.push(path + query);
  15 |     let status = 200;
  16 |     let body: unknown;
  17 |     if (path === "/v1/auth/me") body = { user_id: "isolated-document-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
  18 |     else if (path === "/v1/health/live") body = { status: "live" };
  19 |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
  20 |     else if (path === "/v1/documents") {
  21 |       if (options.slow) await barrier;
  22 |       if (options.listStatus) { status = options.listStatus; body = { error: { code: "fixture_failure" } }; }
  23 |       else body = { schema_version: 2, items: options.empty ? [] : [{ ...documentFixture, title: query.includes("cursor=") ? "隔离测试：后续政策资料" : documentFixture.title }], next_cursor: query.includes("cursor=") ? null : "opaque-fixture", data_mode: "fixture" };
  24 |     } else if (path === `/v1/documents/${documentId}/revisions`) body = { schema_version: 2, items: query.includes("offset=1") ? [{ ...documentFixture, title: "隔离测试：历史研究标题", revision_id: historicalRevisionId, revision_number: 1, is_current: false }] : [documentFixture], next_offset: query.includes("offset=1") ? null : 1, data_mode: "fixture" };
  25 |     else if (path === `/v1/documents/${documentId}`) {
  26 |       const historical = query.includes(historicalRevisionId);
  27 |       const extra = query.includes("evidence_offset=1");
  28 |       body = { ...detailFixture, document: { ...documentFixture, ...(historical ? { revision_id: historicalRevisionId, revision_number: 1, is_current: false, title: "隔离测试：历史研究标题" } : {}), ...(options.metadataOnly ? { content_coverage: "metadata" } : {}) }, evidence: options.metadataOnly ? [] : [{ ...evidenceFixture, ...(historical ? { revision_id: historicalRevisionId, quote_text: "隔离测试历史原文：<script>window.fixtureInjected=true</script>" } : {}), ...(extra ? { span_id: "00000000-0000-4000-8000-000000000106", quote_text: "隔离测试后续原文" } : {}) }], evidence_total: options.metadataOnly ? 0 : 2, next_evidence_offset: options.metadataOnly || extra ? null : 1 };
  29 |     } else throw new Error(`Unexpected isolated fixture path ${path}`);
  30 |     await route.fulfill({ status, json: body });
  31 |   });
  32 |   return { paths, release };
  33 | }
  34 | 
  35 | for (const width of [1366, 390]) {
  36 |   test(`document isolated Fixture ${width}px filter history evidence keyboard layout`, async ({ page }, testInfo) => {
  37 |     await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
  38 |     const fixture = await installFixture(page); await page.goto("/#documents");
  39 |     await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
  40 |     await expect(page.getByText("本页 1 条 · 合成 / Fixture", { exact: true })).toBeVisible();
  41 |     await expect(page.getByText("仅日期 · 时刻未知", { exact: true })).toBeVisible();
  42 |     await page.getByLabel("资料类型", { exact: true }).selectOption("paper"); await page.getByLabel("检索关键词", { exact: true }).fill("模型");
  43 |     await page.getByRole("button", { name: "检索资料", exact: true }).focus(); await page.keyboard.press("Enter");
  44 |     await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
  45 |     await page.getByRole("link", { name: documentFixture.title, exact: true }).focus(); await page.keyboard.press("Enter");
  46 |     await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toBeVisible();
  47 |     await expect(page.locator(".document-inspector")).toBeFocused();
  48 |     await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  49 |     await expect(page.locator(".document-evidence img, .document-evidence script")).toHaveCount(0);
  50 |     await page.locator(".document-evidence summary").first().focus(); await page.keyboard.press("Space");
  51 |     await expect(page.getByText("片段哈希", { exact: true })).toBeVisible();
  52 |     await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click(); await expect(page.getByText("隔离测试后续原文", { exact: true })).toBeVisible();
  53 |     expect(fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
  54 |     await page.getByRole("button", { name: "加载更多历史版本", exact: true }).click();
  55 |     await expect(page.getByRole("option", { name: "修订 1 · 历史 · 隔离测试：历史研究标题", exact: true })).toHaveCount(1);
  56 |     await page.getByLabel("原文修订版本", { exact: true }).selectOption(historicalRevisionId);
  57 |     await expect(page.getByRole("heading", { name: "隔离测试：历史研究标题", exact: true })).toBeVisible();
  58 |     await expect(page.getByRole("link", { name: "查看当前版本 →", exact: true })).toBeVisible();
  59 |     await expect(page.getByText("隔离测试后续原文", { exact: true })).toHaveCount(0);
  60 |     await expect(page.locator(".document-evidence script")).toHaveCount(0);
  61 |     const observation = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > window.innerWidth, backgrounds: [...document.querySelectorAll(".ambient-backdrop")].map((element) => getComputedStyle(element).pointerEvents), animations: [...document.querySelectorAll(".ambient-topology,.ambient-orbit,.ambient-light")].map((element) => getComputedStyle(element).animationName), injected: Object.hasOwn(window, "fixtureInjected"), textVisible: [...document.querySelectorAll(".document-title,.document-metadata dd,.document-boundary,.document-evidence blockquote")].every((element) => { const range = document.createRange(); range.selectNodeContents(element); return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth); }) }));
  62 |     expect(observation.overflow).toBe(false); expect(observation.textVisible).toBe(true); expect(observation.injected).toBe(false); expect(observation.backgrounds).toEqual(["none"]); expect(observation.animations.every((name) => name === "none")).toBe(true);
  63 |     await page.screenshot({ path: testInfo.outputPath(`document-isolated-fixture-${width}.png`), fullPage: true });
  64 |     await testInfo.attach("document-fixture-observation", { body: JSON.stringify({ ...observation, paths: fixture.paths, mode: "isolated fixture only" }), contentType: "application/json" });
  65 |     await page.getByRole("link", { name: "关闭详情", exact: true }).click();
  66 |     await page.getByRole("button", { name: "下一页资料", exact: true }).click(); await expect(page.getByRole("link", { name: "隔离测试：后续政策资料", exact: true })).toBeVisible();
  67 |     expect(fixture.paths.some((path) => path.includes("document_kind=paper&cursor=opaque-fixture"))).toBe(true);
  68 |   });
  69 | }
  70 | test("document isolated loading empty metadata and HTTP error states remain separate", async ({ page }) => {
  71 |   const fixture = await installFixture(page, { slow: true, empty: true }); await page.goto("/#documents"); await expect(page.getByText("正在查询授权范围内的资料…", { exact: true })).toBeVisible(); fixture.release();
  72 |   await expect(page.getByRole("heading", { name: "本次查询没有资料记录", exact: true })).toBeVisible();
  73 |   await page.unrouteAll({ behavior: "wait" }); await installFixture(page, { metadataOnly: true }); await page.reload(); await page.getByRole("link", { name: documentFixture.title, exact: true }).click();
  74 |   await expect(page.getByRole("heading", { name: "没有可定位的原文片段", exact: true })).toBeVisible();
  75 |   for (const [status, title] of [[403, "没有资料查看权限"], [503, "资料依赖暂不可用"], [404, "资料服务待接通"]] as const) {
  76 |     await page.unrouteAll({ behavior: "wait" }); await installFixture(page, { listStatus: status }); await page.goto("/#documents");
> 77 |     await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible(); await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0); await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toHaveCount(0);
     |                                                                           ^ Error: expect(locator).toBeVisible() failed
  78 |   }
  79 | });
  80 | 
```