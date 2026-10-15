# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_graph_app_fixture.spec.ts >> default App isolated fixture: legacy entry invalid route and future version fail closed
- Location: e2e\r17_graph_app_fixture.spec.ts:137:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: '登录后查看证据图', exact: true })
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: '登录后查看证据图', exact: true }) with timeout 5000ms
  - waiting for getByRole('heading', { name: '登录后查看证据图', exact: true })

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
  - text: 工作台 知识图谱 数据模式
  - strong: 合成 / Fixture
- main:
  - paragraph: KNOWLEDGE / RELATIONS
  - heading "关联研究" [level=1]
  - paragraph: 查看关系理由、证据与历史状态。
  - button "刷新状态"
  - region "证据关系图":
    - paragraph: EVIDENCE GRAPH / 关系与原文
    - heading "证据关系图" [level=2]
    - paragraph: 从事件到关联依据，核查每条关系的版本与证据。
    - text: 合成 / Fixture
    - link "返回事件":
      - /url: "#events/10000000-0000-4000-8000-000000000001"
    - text: 快照
    - strong: v3
    - text: 6 节点 / 6 支持关系 上限 200 / 400
    - button "重新读取"
    - group "节点类型 / 视图筛选":
      - text: 节点类型 / 视图筛选
      - checkbox "来源修订" [checked]
      - text: 来源修订
      - checkbox "事件" [checked] [disabled]
      - text: 事件
      - checkbox "组件版本" [checked]
      - text: 组件版本
      - checkbox "ATLAS" [checked]
      - text: ATLAS
      - checkbox "论文" [checked]
      - text: 论文
      - checkbox "修复" [checked]
      - text: 修复
    - group "图画布控制":
      - button "缩小图": −
      - status "图缩放比例": 100%
      - button "放大图": +
      - button "重置视图"
      - button "向左平移": ←
      - button "向右平移": →
      - button "向上平移": ↑
      - button "向下平移": ↓
    - paragraph: 图区域可滚动。Tab 选择节点或边，Enter / 空格检视；方向键滚动，缩放与重置在上方。
    - region "证据关系图画布":
      - group "事件与证据关系":
        - button "图关系 1：归于同一事件"
        - button "图关系 2：影响组件版本"
        - button "图关系 3：映射 ATLAS"
        - button "图关系 4：关联论文"
        - button "图关系 5：修复依据"
        - button "图关系 6：组件版本关联事件"
        - button "来源修订节点：合成厂商公告 · 历史修订": 来源修订 合成厂商公告 · 历史修订
        - button "事件节点：合成 Fixture · App 事件" [pressed]: 事件 合成 Fixture · App…
        - button "组件版本节点：Fixture · package 1.0 < 1.4（仅合成）": 组件版本 Fixture · packag…
        - button "ATLAS节点：Fixture · AML.T0000": ATLAS Fixture · AML.T0…
        - button "论文节点：Fixture · 条件与缓解机制研究": 论文 Fixture · 条件与缓解机…
        - button "修复节点：Fixture · 需要核查的修复版本 1.4": 修复 Fixture · 需要核查的修…
    - region "关系列表":
      - heading "关系列表" [level=3]
      - text: 当前视图 6 / 快照 6
      - button "01 归于同一事件 合成 Fixture · App 事件 → 合成厂商公告 · 历史修订 支持"
      - button "02 影响组件版本 合成 Fixture · App 事件 → Fixture · package 1.0 < 1.4（仅合成） 支持"
      - button "03 映射 ATLAS 合成 Fixture · App 事件 → Fixture · AML.T0000 支持"
      - button "04 关联论文 合成 Fixture · App 事件 → Fixture · 条件与缓解机制研究 支持"
      - button "05 修复依据 合成 Fixture · App 事件 → Fixture · 需要核查的修复版本 1.4 支持"
      - button "06 组件版本关联事件 Fixture · package 1.0 < 1.4（仅合成） → 合成 Fixture · App 事件 支持"
    - complementary "节点检视":
      - paragraph: INSPECT / 可追溯依据
      - heading "节点检视" [level=3]
      - text: 事件
      - heading "合成 Fixture · App 事件" [level=4]
      - code: 10000000-0000-4000-8000-000000000001
      - paragraph: 公开范围 · 节点本身不是资产影响结论。
      - heading "关联关系" [level=4]
      - button "归于同一事件"
      - button "影响组件版本"
      - button "映射 ATLAS"
      - button "关联论文"
      - button "修复依据"
      - button "组件版本关联事件"
      - paragraph: 引文存在不等于内容支持。候选与待审关系未包含在此 supported 快照中；接口未提供人工审核进度。
    - group: 快照版本与内容标识
  - text: 环境未由服务端标明 版本未由服务端标明
```

# Test source

```ts
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
  82  |     await page.getByRole("link", { name: new RegExp(`原文片段 \\[1\\]${fixtureOldEvidenceId}`) }).click();
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
> 144 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
      |                                                                              ^ Error: expect(locator).toBeVisible() failed
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