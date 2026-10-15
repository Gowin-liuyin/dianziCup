# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_event_detail_fixture.spec.ts >> R17 isolated fixture 390px dynamic dimension values and keyboard historical citation
- Location: e2e\r17_event_detail_fixture.spec.ts:22:3

# Error details

```
Error: Unexpected isolated R17 fixture route: /v1/health/live
```

```
Error: expect(locator).toBeFocused() failed

Locator: getByRole('region', { name: '事件详情', exact: true })
Expected: focused
Error: element(s) not found

Call log:
  - Expect "toBeFocused" getByRole('region', { name: '事件详情', exact: true }) with timeout 10000ms
  - waiting for getByRole('region', { name: '事件详情', exact: true })
  - Test ended.

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
    - link "资料库":
      - /url: "#documents"
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
  - text: 工作台 情报列表 数据模式
  - strong: 登录后确认
- main:
  - paragraph: INTELLIGENCE / FEED
  - heading "情报工作区" [level=1]
  - paragraph: 从事件线索进入事实、版本与原文证据。
  - button "刷新状态" [disabled]
  - region "情报列表":
    - paragraph: EVENTS / 事件流
    - heading "情报列表" [level=2]
    - text: 待接通
    - form "情报筛选":
      - text: 检索关键词
      - textbox "检索关键词" [disabled]:
        - /placeholder: 事件标题、组件或公开标识
      - text: 产品
      - textbox "产品筛选" [disabled]:
        - /placeholder: 全部产品
      - text: 风险类型
      - textbox "风险类型筛选" [disabled]:
        - /placeholder: 全部类型
      - button "检索情报" [disabled]
      - paragraph: 检索服务接通后启用筛选。列表与证据来自同一授权范围。
    - table "情报事件列表":
      - rowgroup:
        - row "事件 / 公开标识 来源 富化状态 版本 / 时间":
          - columnheader "事件 / 公开标识"
          - columnheader "来源"
          - columnheader "富化状态"
          - columnheader "版本 / 时间"
      - rowgroup
    - heading "情报服务待接通" [level=3]
    - paragraph: 尚未取得事件查询结果。接通真实来源与事件服务后，可查看记录、修订与证据；当前不能判断为无情报。
    - link "查看来源工作区":
      - /url: "#sources"
    - link "登录并核对权限":
      - /url: "#session"
  - complementary "证据检视":
    - paragraph: EVIDENCE / 原文依据
    - heading "证据检视" [level=2]
    - paragraph: 选择事件 追溯每条结论
    - paragraph: 接通后选中可见事件，查看指定原文版本、准确片段和支持关系。
    - list:
      - listitem: ↳文档修订与来源
      - listitem: ↳片段位置与核验状态
      - listitem: ↳发布 / 发现 / 入库时间
      - listitem: ↳冲突与证据不足
    - paragraph: 引文存在 ≠ 内容支持
```

# Test source

```ts
  1  | import { randomBytes } from "node:crypto";
  2  | import { expect, test, type Page } from "@playwright/test";
  3  | import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, historicalEvidenceFixture } from "../src/features/events/event-detail.fixture";
  4  | 
  5  | async function installFixtureRoutes(page: Page, evidenceStatus = 200) {
  6  |   await page.route("**/v1/**", async (route) => {
  7  |     const path = new URL(route.request().url()).pathname;
  8  |     let body: unknown;
  9  |     let status = 200;
  10 |     if (path === "/v1/auth/me") body = { user_id: "r17-detail-isolated-fixture-user", tenant_id: "r17-detail-isolated-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
  11 |     else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
  12 |     else if (path === `/v1/events/${fixtureEventId}`) body = eventDetailFixture;
  13 |     else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) {
  14 |       status = evidenceStatus;
  15 |       body = evidenceStatus === 200 ? historicalEvidenceFixture : { error: { code: "fixture_evidence_unavailable", retryable: true } };
  16 |     } else throw new Error(`Unexpected isolated R17 fixture route: ${path}`);
  17 |     await route.fulfill({ status, json: body });
  18 |   });
  19 | }
  20 | 
  21 | for (const width of [1366, 390]) {
  22 |   test(`R17 isolated fixture ${width}px dynamic dimension values and keyboard historical citation`, async ({ page }, testInfo) => {
  23 |     await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  24 |     await page.emulateMedia({ reducedMotion: "reduce" });
  25 |     await installFixtureRoutes(page);
  26 |     await page.goto(`/#events/${fixtureEventId}`);
> 27 |     await expect(page.getByRole("region", { name: "事件详情", exact: true })).toBeFocused();
     |                                                                           ^ Error: expect(locator).toBeFocused() failed
  28 |     const score = page.getByRole("article", { name: "CVSS 评分", exact: true });
  29 |     await expect(score.getByText("9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", { exact: true })).toBeVisible();
  30 |     await expect(page.locator(".dimension-row")).toHaveCount(9);
  31 |     await expect(page.getByRole("article", { name: "CWE 弱点", exact: true }).getByText("隔离来源 B：CWE-20", { exact: true })).toBeVisible();
  32 |     await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
  33 |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  34 |     expect(await page.locator(".dimension-value, .dimension-state-note, .event-context-metadata dd, .claim-row p, .revision-entry dd").evaluateAll((elements) => elements.every((element) => {
  35 |       const range = document.createRange(); range.selectNodeContents(element);
  36 |       return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  37 |     }))).toBe(true);
  38 |     await page.screenshot({ path: testInfo.outputPath(`detail-fixture-${width}.png`), fullPage: true });
  39 |     const timelineButton = page.getByRole("button", { name: "原文修订时间线", exact: true });
  40 |     await timelineButton.focus(); await page.keyboard.press("Enter");
  41 |     await expect(page.getByRole("region", { name: "原文修订时间线", exact: true })).toBeFocused();
  42 |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
  43 |     const oldRevision = page.getByRole("article", { name: `修订 1 ${fixtureOldRevisionId}`, exact: true });
  44 |     await expect(oldRevision.getByText("未知 / 未留存", { exact: true })).toHaveCount(4);
  45 |     const oldReference = oldRevision.getByRole("link", { name: "此修订的原文片段 [1]", exact: true });
  46 |     await oldReference.focus(); await page.keyboard.press("Enter");
  47 |     await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
  48 |     await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  49 |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
  50 |     await expect(page.getByText("[12, 42)", { exact: true })).toBeVisible();
  51 |     await page.reload();
  52 |     await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  53 |     await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
  54 |     await page.screenshot({ path: testInfo.outputPath(`historical-evidence-fixture-${width}.png`), fullPage: false });
  55 |     expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  56 |   });
  57 | }
  58 | 
  59 | test("R17 isolated fixture evidence dependency failure retains the other saved detail", async ({ page }, testInfo) => {
  60 |   await page.setViewportSize({ width: 390, height: 844 });
  61 |   await installFixtureRoutes(page, 503);
  62 |   await page.goto(`/#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
  63 |   const inspector = page.getByRole("complementary", { name: "证据检视", exact: true });
  64 |   await expect(inspector.getByRole("heading", { name: "依赖暂不可用", exact: true })).toBeVisible();
  65 |   await expect(page.getByRole("article", { name: "CVSS 评分", exact: true }).getByText("已取得", { exact: true })).toBeVisible();
  66 |   await expect(inspector.locator("blockquote")).toHaveCount(0);
  67 |   await expect(inspector.getByRole("button", { name: "重新查询", exact: true })).toBeVisible();
  68 |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  69 |   await inspector.scrollIntoViewIfNeeded();
  70 |   await page.screenshot({ path: testInfo.outputPath("partial-evidence-failure-fixture-390.png"), fullPage: false });
  71 | });
  72 | 
```