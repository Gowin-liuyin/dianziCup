# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r04_fixture_contract.spec.ts >> R04 isolated fixture business 401 clears identity without auth restore loop
- Location: e2e\r04_fixture_contract.spec.ts:84:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 1
Received: 2
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
        - link "知识图谱" [ref=e18] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=e19]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=e20] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=e21]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=e22] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=e23]: ⬡
          - text: 资产自查
      - generic [ref=e24]:
        - paragraph [ref=e25]: 协作
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
        - paragraph [ref=e33]: 系统
        - link "运行状态" [ref=e34] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=e35]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=e36] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=e37]: ◎
          - text: 会话与权限
    - generic [ref=e38]:
      - paragraph [ref=e39]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=e40]: READ · VERIFY · CONNECT
  - generic [ref=e41]:
    - banner [ref=e42]:
      - generic [ref=e43]:
        - generic [aria-hidden] [ref=e44]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=e45]: /
        - text: 会话与权限
      - generic [ref=e46]:
        - text: 数据模式
        - strong [ref=e47]: 登录后确认
    - main [ref=e48]:
      - generic [ref=e49]:
        - generic [ref=e50]:
          - paragraph [ref=e51]: ACCESS / SESSION
          - heading "访问控制" [level=1] [ref=e52]: 访问控制_
          - paragraph [ref=e53]: 核对当前团队身份、授权与会话状态。
        - button "刷新状态" [ref=e54] [cursor=pointer]:
          - generic [aria-hidden] [ref=e55]: ↻
          - text: 刷新状态
      - generic [ref=e56]:
        - region [ref=e57]:
          - generic [ref=e58]:
            - generic [ref=e59]:
              - paragraph [ref=e60]: ACCESS / 访问
              - heading "团队会话" [level=2] [ref=e61]
            - generic [ref=e62]: 尚未登录
          - generic [ref=e63]:
            - paragraph [ref=e64]: 使用管理员为你创建的团队账号。
            - generic [ref=e65]:
              - generic [ref=e66]: 用户名
              - textbox "用户名" [ref=e67]
              - generic [ref=e68]: 密码
              - textbox "密码" [ref=e69]
              - button "登录工作台" [ref=e70] [cursor=pointer]:
                - text: 登录工作台
                - generic [aria-hidden] [ref=e71]: →
          - alert [ref=e72]:
            - paragraph [ref=e73]: 会话已失效，请重新登录。
            - button "重新检查会话" [ref=e74] [cursor=pointer]
        - generic [ref=e75]:
          - paragraph [ref=e76]: TRUST BOUNDARY / 授权边界
          - heading "按权限查看 按证据判断" [level=2] [ref=e77]: 按权限查看按证据判断
          - paragraph [ref=e78]: 登录后，身份与权限由服务端确认。会话失效或退出时，页面立即清除身份信息。
          - link "返回运行概览 →" [ref=e79] [cursor=pointer]:
            - /url: "#runtime"
```

# Test source

```ts
  1   | import { randomBytes } from "node:crypto";
  2   | import { expect, test, type Page } from "@playwright/test";
  3   | 
  4   | const eventId = "00000000-0000-4000-8000-000000000001";
  5   | const revisionId = "00000000-0000-4000-8000-000000000002";
  6   | const evidenceId = "00000000-0000-4000-8000-000000000003";
  7   | const claimId = "00000000-0000-4000-8000-000000000004";
  8   | const eventFixture = { event_id: eventId, event_type: "advisory", title: "隔离 Fixture：历史公告与证据核查", external_ids: ["FIXTURE-ONLY"], primary_product_ids: [], first_seen_at: "2026-10-15T02:00:00Z", status: "active", source_count: 2, latest_revision_id: revisionId, freshness: "stale" };
  9   | const detailFixture = { schema_version: 2, event: eventFixture, dimensions: [{ dimension: "versions", status: "available", claim_ids: [claimId], citations: [{ evidence_id: evidenceId, revision_id: revisionId, quote: "隔离原文：仅用于检验界面，不代表真实事件。", locator: "Unicode [12, 37)", source_uri: "https://example.test/fixture-revision" }], freshness: "stale", observed_at: null, source_version: null, error_code: null }, { dimension: "poc", status: "failed", claim_ids: [], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: "fixture_upstream_failure" }], revisions: [{ revision_id: revisionId, document_id: eventId, revision_number: 1, source_id: evidenceId, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "legacy_unverified", document_kind: "advisory", canonical_uri: null }], claims: [{ claim_id: claimId, predicate: "isolated_statement", display_value: "隔离模型假设：条件尚未证实；不能视为已确认影响。", origin: "model_hypothesis", status: "unverified", source_revision_id: revisionId, evidence_ids: [evidenceId] }], data_mode: "fixture" };
  10  | const evidenceFixture = { schema_version: 2, span_id: evidenceId, revision_id: revisionId, block_id: null, start_offset: 12, end_offset: 37, quote_text: "隔离原文：仅用于检验界面，不代表真实事件。", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };
  11  | 
  12  | /** 全部请求在本测试进程隔离拦截；产品无fixture开关，失败不会替换成样本。 */
  13  | async function installFixtureRoutes(page: Page, options: { status?: number; delayed?: boolean } = {}) {
  14  |   let releaseList = () => {};
  15  |   const listBarrier = new Promise<void>((resolve) => { releaseList = resolve; });
  16  |   await page.route("**/v1/**", async (route) => {
  17  |     const path = new URL(route.request().url()).pathname;
  18  |     let body: unknown;
  19  |     let status = 200;
  20  |     if (path === "/v1/auth/me") body = { user_id: "isolated-fixture-user", tenant_id: "isolated-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
  21  |     else if (path === "/v1/health/live") body = { status: "live" };
  22  |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture only", dependencies: {} };
  23  |     else if (path === "/v1/events") {
  24  |       if (options.delayed) await listBarrier;
  25  |       status = options.status ?? 200;
  26  |       body = status === 200 ? { schema_version: 2, items: [eventFixture], next_cursor: null, data_mode: "fixture" } : { error: { code: status === 401 ? "unauthenticated" : "dependency_unavailable", retryable: status === 503 } };
  27  |     } else if (path === `/v1/events/${eventId}`) body = detailFixture;
  28  |     else if (path === `/v1/evidence/${evidenceId}`) body = evidenceFixture;
  29  |     else throw new Error(`Unexpected isolated R04 fixture route: ${path}`);
  30  |     await route.fulfill({ status, json: body });
  31  |   });
  32  |   return { releaseList };
  33  | }
  34  | 
  35  | for (const width of [1366, 390]) {
  36  |   test(`R04 isolated fixture ${width}px list, nine dimensions and historical evidence`, async ({ page }, testInfo) => {
  37  |     await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  38  |     await page.emulateMedia({ reducedMotion: "reduce" });
  39  |     await installFixtureRoutes(page);
  40  |     await page.goto("/#events");
  41  |     const record = page.getByRole("link", { name: eventFixture.title, exact: true });
  42  |     await expect(record).toBeVisible();
  43  |     await expect(page.getByText("本页 1 条 · 合成 / Fixture", { exact: true })).toBeVisible();
  44  |     await record.focus();
  45  |     await page.keyboard.press("Enter");
  46  |     await expect(page.locator(".dimension-row")).toHaveCount(9);
  47  |     await expect(page.getByText("模型假设", { exact: true })).toBeVisible();
  48  |     await expect(page.getByText("未提供该维度", { exact: true })).toHaveCount(7);
  49  |     await page.getByRole("link", { name: "查看引用：Unicode [12, 37)", exact: true }).click();
  50  |     await expect(page.locator("blockquote")).toHaveText(evidenceFixture.quote_text);
  51  |     await expect(page.getByText("历史定位未核验", { exact: true })).toBeVisible();
  52  |     await expect(page.getByText("[12, 37)", { exact: true })).toBeVisible();
  53  |     await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
  54  |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  55  |     const readableText = page.locator(".evidence-body blockquote, .evidence-metadata dd, .claim-row p");
  56  |     expect(await readableText.evaluateAll((elements) => elements.every((element) => {
  57  |       const range = document.createRange();
  58  |       range.selectNodeContents(element);
  59  |       return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  60  |     }))).toBe(true);
  61  |     await page.screenshot({ path: testInfo.outputPath(`r04-isolated-fixture-${width}.png`), fullPage: true });
  62  |   });
  63  | }
  64  | 
  65  | test("R04 isolated fixture delayed loading and 503 preserve an explicit failure", async ({ page }, testInfo) => {
  66  |   await page.setViewportSize({ width: 390, height: 844 });
  67  |   const routes = await installFixtureRoutes(page, { status: 503, delayed: true });
  68  |   await page.goto("/#events");
  69  |   await expect(page.getByText("正在查询授权范围内的事件…", { exact: true })).toBeVisible();
  70  |   await expect(page.getByRole("button", { name: "检索情报", exact: true })).toBeDisabled();
  71  |   routes.releaseList();
  72  |   await expect(page.getByRole("heading", { name: "依赖暂不可用", exact: true })).toBeVisible();
  73  |   const explanation = page.getByText("当前查询失败，不能据此判断为空或无风险。已有记录需重新取得后展示。", { exact: true });
  74  |   expect(await explanation.evaluate((element) => {
  75  |     const range = document.createRange(); range.selectNodeContents(element);
  76  |     return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth);
  77  |   })).toBe(true);
  78  |   await expect(page.getByText(/本页 0 条/)).toHaveCount(0);
  79  |   await expect(page.getByRole("link", { name: eventFixture.title, exact: true })).toHaveCount(0);
  80  |   await expect(page.getByText("合成 / Fixture", { exact: true })).toBeVisible();
  81  |   await page.screenshot({ path: testInfo.outputPath("r04-isolated-fixture-503-390.png"), fullPage: true });
  82  | });
  83  | 
  84  | test("R04 isolated fixture business 401 clears identity without auth restore loop", async ({ page }) => {
  85  |   let snapshotRequests = 0;
  86  |   let businessRequests = 0;
  87  |   page.on("request", (request) => {
  88  |     const path = new URL(request.url()).pathname;
  89  |     if (path === "/v1/auth/me") snapshotRequests += 1;
  90  |     if (path === "/v1/events") businessRequests += 1;
  91  |   });
  92  |   await installFixtureRoutes(page, { status: 401 });
  93  |   await page.goto("/#events");
  94  |   await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  95  |   await expect(page.getByText("isolated-fixture-user", { exact: true })).toHaveCount(0);
  96  |   await expect(page.getByRole("link", { name: eventFixture.title, exact: true })).toHaveCount(0);
  97  |   await expect(page.getByRole("button", { name: "重新登录", exact: true })).toBeVisible();
  98  |   await page.getByRole("button", { name: "重新登录", exact: true }).click();
  99  |   await expect(page.getByRole("heading", { name: "访问控制", exact: true })).toBeVisible();
> 100 |   expect(snapshotRequests).toBe(1);
      |                            ^ Error: expect(received).toBe(expected) // Object.is equality
  101 |   expect(businessRequests).toBe(1);
  102 | });
  103 | 
```