# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_graph_app_fixture.spec.ts >> default App isolated fixture 390: event graph native chooser evidence refresh and hash back
- Location: e2e\r17_graph_app_fixture.spec.ts:67:3

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for getByRole('link', { name: /原文片段 \[1\]10000000-0000-4000-8000-000000000005/ })

```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - link "跳到主要内容" [ref=f1e4] [cursor=pointer]:
    - /url: "#main-content"
  - complementary [ref=f1e5]:
    - link "安全情报 DEFENSE INTELLIGENCE" [ref=f1e6] [cursor=pointer]:
      - /url: "#runtime"
      - generic [aria-hidden] [ref=f1e7]: DI
      - generic [ref=f1e9]:
        - text: 安全情报
        - generic [ref=f1e10]: DEFENSE INTELLIGENCE
    - navigation "工作台导航" [ref=f1e11]:
      - generic [ref=f1e12]:
        - link "情报列表" [ref=f1e13] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=f1e14]: ≡
          - text: 情报列表
        - link "来源监测" [ref=f1e15] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=f1e16]: ◉
          - text: 来源监测
        - link "资料库" [ref=f1e17] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=f1e18]: ▤
          - text: 资料库
        - link "知识图谱" [ref=f1e19] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=f1e20]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=f1e21] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=f1e22]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=f1e23] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=f1e24]: ⬡
          - text: 资产自查
      - generic [ref=f1e25]:
        - link "任务轨迹" [ref=f1e26] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=f1e27]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=f1e28] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=f1e29]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=f1e30] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=f1e31]: ▤
          - text: 证据报告
      - generic [ref=f1e32]:
        - link "运行状态" [ref=f1e33] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=f1e34]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=f1e35] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=f1e36]: ◎
          - text: 会话与权限
  - generic [ref=f1e37]:
    - banner [ref=f1e38]:
      - generic [ref=f1e39]:
        - generic [aria-hidden] [ref=f1e40]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=f1e41]: /
        - text: 知识图谱
      - generic [ref=f1e42]:
        - text: 数据模式
        - strong [ref=f1e43]: 合成 / Fixture
    - main [ref=f1e44]:
      - generic [ref=f1e45]:
        - generic [ref=f1e46]:
          - paragraph [ref=f1e47]: KNOWLEDGE / RELATIONS
          - heading "关联研究" [level=1] [ref=f1e48]: 关联研究_
          - paragraph [ref=f1e49]: 查看关系理由、证据与历史状态。
        - button "刷新状态" [ref=f1e50] [cursor=pointer]:
          - generic [aria-hidden] [ref=f1e51]: ↻
          - text: 刷新状态
      - region [ref=f1e52]:
        - generic [ref=f1e53]:
          - generic [ref=f1e54]:
            - paragraph [ref=f1e55]: EVIDENCE GRAPH / 关系与原文
            - heading "证据关系图" [level=2] [ref=f1e56]
            - paragraph [ref=f1e57]: 从事件到关联依据，核查每条关系的版本与证据。
          - generic [ref=f1e58]:
            - generic [ref=f1e59]: 合成 / Fixture
            - link "返回事件" [ref=f1e60] [cursor=pointer]:
              - /url: "#events/10000000-0000-4000-8000-000000000001"
        - generic [ref=f1e61]:
          - generic [ref=f1e62]:
            - text: 快照
            - strong [ref=f1e63]: v3
          - generic [ref=f1e64]: 6 节点 / 6 支持关系
          - generic [ref=f1e65]: 上限 200 / 400
          - button "重新读取" [ref=f1e66] [cursor=pointer]
        - generic [ref=f1e67]:
          - generic [ref=f1e68]:
            - group "节点类型 / 视图筛选" [ref=f1e69]:
              - generic [ref=f1e71] [cursor=pointer]:
                - checkbox "来源修订" [checked] [ref=f1e72]
                - text: 来源修订
              - generic [ref=f1e74] [cursor=pointer]:
                - checkbox "事件" [checked] [disabled] [ref=f1e75]
                - text: 事件
              - generic [ref=f1e77] [cursor=pointer]:
                - checkbox "组件版本" [checked] [ref=f1e78]
                - text: 组件版本
              - generic [ref=f1e80] [cursor=pointer]:
                - checkbox "ATLAS" [checked] [ref=f1e81]
                - text: ATLAS
              - generic [ref=f1e83] [cursor=pointer]:
                - checkbox "论文" [checked] [ref=f1e84]
                - text: 论文
              - generic [ref=f1e86] [cursor=pointer]:
                - checkbox "修复" [checked] [ref=f1e87]
                - text: 修复
            - group "图画布控制" [ref=f1e89]:
              - button "缩小图" [ref=f1e90] [cursor=pointer]: −
              - status "图缩放比例" [ref=f1e91]: 100%
              - button "放大图" [ref=f1e92] [cursor=pointer]: +
              - button "重置视图" [ref=f1e93] [cursor=pointer]
              - button "向左平移" [ref=f1e94] [cursor=pointer]: ←
              - button "向右平移" [ref=f1e95] [cursor=pointer]: →
              - button "向上平移" [ref=f1e96] [cursor=pointer]: ↑
              - button "向下平移" [ref=f1e97] [cursor=pointer]: ↓
            - paragraph [ref=f1e98]: 图区域可滚动。Tab 选择节点或边，Enter / 空格检视；方向键滚动，缩放与重置在上方。
            - region "证据关系图画布" [ref=f1e99]:
              - group "事件与证据关系" [ref=f1e100]:
                - generic [ref=f1e102]: 来源修订
                - generic [ref=f1e104]: 事件
                - generic [ref=f1e106]: 组件版本
                - generic [ref=f1e108]: ATLAS
                - generic [ref=f1e110]: 论文
                - generic [ref=f1e112]: 修复
                - button "图关系 1：归于同一事件" [ref=f1e113] [cursor=pointer]
                - button "图关系 2：影响组件版本" [pressed] [ref=f1e115] [cursor=pointer]
                - button "图关系 3：映射 ATLAS" [ref=f1e117] [cursor=pointer]
                - button "图关系 4：关联论文" [ref=f1e119] [cursor=pointer]
                - button "图关系 5：修复依据" [ref=f1e121] [cursor=pointer]
                - button "图关系 6：组件版本关联事件" [ref=f1e123] [cursor=pointer]
                - button "来源修订节点：合成厂商公告 · 历史修订" [ref=f1e125] [cursor=pointer]:
                  - generic: 来源修订
                  - generic: 合成厂商公告 · 历史修订
                - button "事件节点：合成 Fixture · App 事件" [ref=f1e128] [cursor=pointer]:
                  - generic: 事件
                  - generic: 合成 Fixture · App…
                - button "组件版本节点：Fixture · package 1.0 < 1.4（仅合成）" [ref=f1e131] [cursor=pointer]:
                  - generic: 组件版本
                  - generic: Fixture · packag…
                - button "ATLAS节点：Fixture · AML.T0000" [ref=f1e134] [cursor=pointer]:
                  - generic: ATLAS
                  - generic: Fixture · AML.T0…
                - button "论文节点：Fixture · 条件与缓解机制研究" [ref=f1e137] [cursor=pointer]:
                  - generic: 论文
                  - generic: Fixture · 条件与缓解机…
                - button "修复节点：Fixture · 需要核查的修复版本 1.4" [ref=f1e140] [cursor=pointer]:
                  - generic: 修复
                  - generic: Fixture · 需要核查的修…
            - region [ref=f1e143]:
              - generic [ref=f1e144]:
                - heading "关系列表" [level=3] [ref=f1e145]
                - generic [ref=f1e146]: 当前视图 6 / 快照 6
              - generic [ref=f1e147]:
                - button "01 归于同一事件 合成 Fixture · App 事件 → 合成厂商公告 · 历史修订 支持" [ref=f1e148] [cursor=pointer]:
                  - generic [ref=f1e149]: "01"
                  - generic [ref=f1e150]:
                    - text: 归于同一事件
                    - generic [ref=f1e151]: 合成 Fixture · App 事件 → 合成厂商公告 · 历史修订
                  - generic [ref=f1e152]: 支持
                - button "02 影响组件版本 合成 Fixture · App 事件 → Fixture · package 1.0 < 1.4（仅合成） 支持" [pressed] [ref=f1e153] [cursor=pointer]:
                  - generic [ref=f1e154]: "02"
                  - generic [ref=f1e155]:
                    - text: 影响组件版本
                    - generic [ref=f1e156]: 合成 Fixture · App 事件 → Fixture · package 1.0 < 1.4（仅合成）
                  - generic [ref=f1e157]: 支持
                - button "03 映射 ATLAS 合成 Fixture · App 事件 → Fixture · AML.T0000 支持" [ref=f1e158] [cursor=pointer]:
                  - generic [ref=f1e159]: "03"
                  - generic [ref=f1e160]:
                    - text: 映射 ATLAS
                    - generic [ref=f1e161]: 合成 Fixture · App 事件 → Fixture · AML.T0000
                  - generic [ref=f1e162]: 支持
                - button "04 关联论文 合成 Fixture · App 事件 → Fixture · 条件与缓解机制研究 支持" [ref=f1e163] [cursor=pointer]:
                  - generic [ref=f1e164]: "04"
                  - generic [ref=f1e165]:
                    - text: 关联论文
                    - generic [ref=f1e166]: 合成 Fixture · App 事件 → Fixture · 条件与缓解机制研究
                  - generic [ref=f1e167]: 支持
                - button "05 修复依据 合成 Fixture · App 事件 → Fixture · 需要核查的修复版本 1.4 支持" [ref=f1e168] [cursor=pointer]:
                  - generic [ref=f1e169]: "05"
                  - generic [ref=f1e170]:
                    - text: 修复依据
                    - generic [ref=f1e171]: 合成 Fixture · App 事件 → Fixture · 需要核查的修复版本 1.4
                  - generic [ref=f1e172]: 支持
                - button "06 组件版本关联事件 Fixture · package 1.0 < 1.4（仅合成） → 合成 Fixture · App 事件 支持" [ref=f1e173] [cursor=pointer]:
                  - generic [ref=f1e174]: "06"
                  - generic [ref=f1e175]:
                    - text: 组件版本关联事件
                    - generic [ref=f1e176]: Fixture · package 1.0 < 1.4（仅合成） → 合成 Fixture · App 事件
                  - generic [ref=f1e177]: 支持
          - complementary [ref=f1e178]:
            - generic [ref=f1e179]:
              - paragraph [ref=f1e180]: INSPECT / 可追溯依据
              - heading "关系检视" [level=3] [ref=f1e181]
            - generic [ref=f1e182]: 有证据支持 · 当前快照
            - heading "影响组件版本" [level=4] [ref=f1e183]
            - code [ref=f1e184]: affects_component_version
            - generic [ref=f1e185]:
              - button "合成 Fixture · App 事件" [ref=f1e186] [cursor=pointer]
              - generic [aria-hidden] [ref=f1e187]: ↓
              - button "Fixture · package 1.0 < 1.4（仅合成）" [ref=f1e188] [cursor=pointer]
            - paragraph [ref=f1e189]: 合成 Fixture：来自当前支持断言；不代表真实情报或受影响资产。
            - generic [ref=f1e190]:
              - term [ref=f1e191]: 规则 / 模型版本
              - definition [ref=f1e192]: r10-graph-1.2.0
              - term [ref=f1e193]: 可见范围
              - definition [ref=f1e194]: 公开
              - term [ref=f1e195]: 业务版本
              - definition [ref=f1e196]: "3"
            - generic [ref=f1e197]:
              - heading "原文证据 · 1" [level=4] [ref=f1e198]
              - paragraph [ref=f1e199]: 打开保存片段后核查其原文修订与位置。
              - link [ref=f1e200] [cursor=pointer]:
                - /url: "#events/10000000-0000-4000-8000-000000000001/evidence/10000000-0000-4000-8000-000000000005"
                - text: 原文片段 [1]
                - code [ref=f1e201]: 10000000-0000-4000-8000-000000000005
            - group [ref=f1e202]:
              - generic "支持断言 · 1" [ref=f1e203] [cursor=pointer]
            - group [ref=f1e204]:
              - generic "来源修订 · 2" [ref=f1e205] [cursor=pointer]
            - group [ref=f1e206]:
              - generic "关系标识" [ref=f1e207] [cursor=pointer]
            - paragraph [ref=f1e208]: 引文存在不等于内容支持。候选与待审关系未包含在此 supported 快照中；接口未提供人工审核进度。
        - group [ref=f1e209]:
          - generic "快照版本与内容标识" [ref=f1e210] [cursor=pointer]
      - generic [ref=f1e211]:
        - generic [ref=f1e212]: 环境未由服务端标明
        - generic [ref=f1e213]: 版本未由服务端标明
```

# Test source

```ts
  1   | import { randomBytes } from "node:crypto";
  2   | import { expect, test, type Page } from "@playwright/test";
  3   | import { graphFixture, graphFixtureEventId, fixtureGraphId } from "../src/features/graph/graph.fixture";
  4   | import { graphRelationKinds, type GraphSnapshot } from "../src/features/graph/graph-contracts";
  5   | import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, historicalEvidenceFixture } from "../src/features/events/event-detail.fixture";
  6   | 
  7   | function appGraphFixture(): GraphSnapshot {
  8   |   const snapshot = graphFixture("r10-graph-1.2.0");
  9   |   snapshot.event_id = fixtureEventId;
  10  |   snapshot.nodes = snapshot.nodes.map((node) => node.id === graphFixtureEventId ? { ...node, id: fixtureEventId, label: "合成 Fixture · App 事件" } : node);
  11  |   snapshot.edges = snapshot.edges.map((edge) => ({ ...edge, subject_id: edge.subject_id === graphFixtureEventId ? fixtureEventId : edge.subject_id, object_id: edge.object_id === graphFixtureEventId ? fixtureEventId : edge.object_id, evidence_span_ids: [fixtureOldEvidenceId], source_revision_ids: [fixtureOldRevisionId, fixtureGraphId(90)] }));
  12  |   return snapshot;
  13  | }
  14  | 
  15  | async function installFixture(page: Page) {
  16  |   const api = { graph: appGraphFixture(), graphStatus: 200, authStatus: 200, authenticated: true, tenant: "graph-app-fixture-a", dataMode: "fixture", hold: false, release: () => {}, requests: [] as string[] };
  17  |   await page.route("**/v1/**", async (route) => {
  18  |     const path = new URL(route.request().url()).pathname;
  19  |     api.requests.push(`${route.request().method()} ${path}`);
  20  |     let body: unknown; let status = 200;
  21  |     if (path === "/v1/auth/me") {
  22  |       status = api.authenticated ? api.authStatus : 401;
  23  |       body = status === 200 ? { user_id: "graph-app-isolated-user", tenant_id: api.tenant, role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: api.dataMode, csrf_token: randomBytes(32).toString("hex") } : { error: { code: "session_expired", retryable: false } };
  24  |     } else if (path === "/v1/auth/logout") { api.authenticated = false; await route.fulfill({ status: 204 }); return; }
  25  |     else if (path === "/v1/health/live") body = { status: "live" };
  26  |     else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated frontend fixture only", dependencies: {} };
  27  |     else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
  28  |     else if (path === `/v1/events/${fixtureEventId}`) body = eventDetailFixture;
  29  |     else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) { expect(new URL(route.request().url()).search).toBe(""); body = historicalEvidenceFixture; }
  30  |     else if (path === `/v1/events/${fixtureEventId}/graph`) {
  31  |       expect(new URL(route.request().url()).search).toBe("?max_nodes=200&max_edges=400");
  32  |       status = api.graphStatus; body = status === 200 ? structuredClone(api.graph) : { error: { code: "isolated_graph_problem", retryable: status >= 500 || status === 409 } };
  33  |       if (api.hold) await new Promise<void>((resolve) => { api.release = resolve; });
  34  |     } else throw new Error(`Unexpected isolated graph app route: ${path}`);
  35  |     await route.fulfill({ status, json: body });
  36  |   });
  37  |   return api;
  38  | }
  39  | 
  40  | async function clickOverlappingCurve(page: Page) {
  41  |   await page.locator(".graph-canvas").scrollIntoViewIfNeeded();
  42  |   const point = await page.locator(".graph-canvas").evaluate((element) => {
  43  |     const curve = element.querySelectorAll(".graph-edge-line")[1];
  44  |     if (!(curve instanceof SVGPathElement)) throw new Error("Real graph curve missing");
  45  |     const local = curve.getPointAtLength(curve.getTotalLength() * 0.5);
  46  |     let matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Curve transform missing");
  47  |     let screen = new DOMPoint(local.x, local.y).matrixTransform(matrix);
  48  |     const bounds = element.getBoundingClientRect();
  49  |     element.scrollLeft += screen.x - bounds.left - bounds.width / 2;
  50  |     element.scrollTop += screen.y - bounds.top - bounds.height / 2;
  51  |     matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Scrolled transform missing");
  52  |     screen = new DOMPoint(local.x, local.y).matrixTransform(matrix);
  53  |     return { x: screen.x, y: screen.y };
  54  |   });
  55  |   await page.mouse.click(point.x, point.y);
  56  |   const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
  57  |   await expect(chooser).toBeVisible();
  58  |   const choice = chooser.locator("button").filter({ has: page.locator("code", { hasText: fixtureGraphId(11) }) });
  59  |   await choice.scrollIntoViewIfNeeded();
  60  |   const bounds = await choice.boundingBox(); if (!bounds) throw new Error("Native chooser bounds missing");
  61  |   await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  62  |   await expect(page.locator(".graph-edge[aria-pressed=true]")).toHaveAttribute("data-edge-id", fixtureGraphId(11));
  63  |   return point;
  64  | }
  65  | 
  66  | for (const width of [1366, 390]) {
  67  |   test(`default App isolated fixture ${width}: event graph native chooser evidence refresh and hash back`, async ({ page }, info) => {
  68  |     await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
  69  |     await page.emulateMedia({ reducedMotion: width === 390 ? "reduce" : "no-preference" });
  70  |     const api = await installFixture(page);
  71  |     await page.goto(`/#events/${fixtureEventId}`);
  72  |     await page.getByRole("link", { name: "查看证据关系图", exact: true }).click();
  73  |     await expect(page.getByText("6 节点 / 6 支持关系", { exact: true })).toBeVisible();
  74  |     expect(new URL(page.url()).hash).toBe(`#graph/${fixtureEventId}`);
  75  |     await page.reload();
  76  |     await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  77  |     const nativePoint = await clickOverlappingCurve(page);
  78  |     await expect(page.getByRole("complementary", { name: "关系检视", exact: true }).getByText("r10-graph-1.2.0", { exact: true })).toBeVisible();
  79  |     expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe(width === 390 ? "none" : "topology-drift");
  80  |     expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  81  |     await page.screenshot({ path: info.outputPath(`default-graph-fixture-${width}.png`), fullPage: false });
> 82  |     await page.getByRole("link", { name: new RegExp(`原文片段 \\[1\\]${fixtureOldEvidenceId}`) }).click();
      |                                                                                               ^ Error: locator.click: Test timeout of 30000ms exceeded.
  83  |     await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  84  |     await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByText(fixtureOldRevisionId, { exact: true })).toBeVisible();
  85  |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
  86  |     await page.reload(); await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  87  |     await page.goBack();
  88  |     await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  89  |     await page.getByRole("link", { name: "返回事件", exact: true }).click();
  90  |     await expect(page.getByRole("link", { name: "查看证据关系图", exact: true })).toBeVisible();
  91  |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
  92  |     expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
  93  |     await info.attach("native-point-and-request-paths", { body: JSON.stringify({ width, nativePoint, requests: api.requests }), contentType: "application/json" });
  94  |   });
  95  | }
  96  | 
  97  | test("default App isolated fixture: loading empty partial stale and retry", async ({ page }) => {
  98  |   const api = await installFixture(page); api.hold = true;
  99  |   api.graph.nodes = api.graph.nodes.slice(0, 1); api.graph.edges = [];
  100 |   api.graph.gaps = graphRelationKinds.map((relation_type) => ({ relation_type, status: "unknown", reason: "no_current_supported_relation" }));
  101 |   await page.goto(`/#graph/${fixtureEventId}`);
  102 |   await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  103 |   api.hold = false; api.release();
  104 |   await expect(page.getByRole("heading", { name: "目前只有事件上下文", exact: true })).toBeVisible();
  105 |   await expect(page.getByText("关系缺口 · 6 项未知", { exact: true })).toBeVisible();
  106 |   api.graph = appGraphFixture(); api.graph.truncated = true; api.graph.gaps = [{ relation_type: "related_paper", status: "unknown", reason: "truncated" }];
  107 |   await page.getByRole("button", { name: "重新读取", exact: true }).click();
  108 |   await expect(page.locator(".graph-warning")).toContainText("截断");
  109 |   await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  110 |   api.graphStatus = 409; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  111 |   await expect(page.getByRole("heading", { name: "图快照已过期", exact: true })).toBeVisible();
  112 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  113 |   api.graphStatus = 200; await page.getByRole("button", { name: "重新取得图", exact: true }).click();
  114 |   await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  115 |   expect(await page.getByText("暂无风险", { exact: true }).count()).toBe(0);
  116 | });
  117 | 
  118 | test("default App isolated fixture: guest denied expired session logout clear", async ({ page }) => {
  119 |   const api = await installFixture(page); api.authenticated = false;
  120 |   await page.goto(`/#graph/${fixtureEventId}`);
  121 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  122 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  123 |   api.authenticated = true; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  124 |   api.graphStatus = 403; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  125 |   await expect(page.getByRole("heading", { name: "没有查看权限", exact: true })).toBeVisible();
  126 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  127 |   api.graphStatus = 401; await page.reload();
  128 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  129 |   api.graphStatus = 200; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  130 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  131 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  132 |   await page.goBack();
  133 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  134 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  135 | });
  136 | 
  137 | test("default App isolated fixture: legacy entry invalid route and future version fail closed", async ({ page }) => {
  138 |   const api = await installFixture(page);
  139 |   await page.goto("/#graph"); await expect(page.getByRole("link", { name: "进入情报列表", exact: true })).toBeVisible();
  140 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  141 |   await page.goto(`/#graph/${fixtureEventId}?tenant=forged`); await expect(page.getByRole("heading", { name: "工作区不存在", exact: true })).toBeVisible();
  142 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  143 |   api.dataMode = "unknown"; await page.goto(`/#graph/${fixtureEventId}`);
  144 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  145 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  146 |   api.dataMode = "fixture";
  147 |   await page.route(`**/v1/events/${fixtureEventId}/graph?*`, async (route) => { await route.fulfill({ json: { ...appGraphFixture(), rule_version: "r10-graph-9.0.0" } }); });
  148 |   await page.reload(); await expect(page.getByRole("heading", { name: "图协议不匹配", exact: true })).toBeVisible();
  149 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  150 |   expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
  151 | });
  152 | 
  153 | test("default App isolated fixture: late old tenant response cannot restore graph after session changes", async ({ page }) => {
  154 |   const api = await installFixture(page); api.hold = true;
  155 |   api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · 私有 A 旧图", scope: { visibility: "tenant", tenant_id: api.tenant } };
  156 |   api.graph.edges = api.graph.edges.map((edge) => ({ ...edge, scope: { visibility: "tenant", tenant_id: api.tenant } }));
  157 |   await page.goto(`/#graph/${fixtureEventId}`);
  158 |   await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  159 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  160 |   api.tenant = "graph-app-fixture-b";
  161 |   await page.getByRole("button", { name: "重新验证会话", exact: true }).click();
  162 |   await expect(page.getByText("graph-app-fixture-b", { exact: true })).toBeVisible();
  163 |   api.hold = false; api.release(); api.graph = appGraphFixture(); api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · B 当前图" };
  164 |   await page.goBack(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  165 |   await expect(page.getByText("合成 Fixture · B 当前图", { exact: true })).toBeVisible();
  166 |   expect(await page.getByText("合成 Fixture · 私有 A 旧图", { exact: true }).count()).toBe(0);
  167 | });
  168 | 
```