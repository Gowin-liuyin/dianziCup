# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_graph_app_fixture.spec.ts >> default App isolated fixture: legacy entry invalid route and future version fail closed
- Location: e2e\r17_graph_app_fixture.spec.ts:139:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: false
Received: true
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
        - paragraph [ref=f1e13]: 研究
        - link "情报列表" [ref=f1e14] [cursor=pointer]:
          - /url: "#events"
          - generic [aria-hidden] [ref=f1e15]: ≡
          - text: 情报列表
        - link "来源监测" [ref=f1e16] [cursor=pointer]:
          - /url: "#sources"
          - generic [aria-hidden] [ref=f1e17]: ◉
          - text: 来源监测
        - link "资料库" [ref=f1e18] [cursor=pointer]:
          - /url: "#documents"
          - generic [aria-hidden] [ref=f1e19]: ▤
          - text: 资料库
        - link "知识图谱" [ref=f1e20] [cursor=pointer]:
          - /url: "#graph"
          - generic [aria-hidden] [ref=f1e21]: ◇
          - text: 知识图谱
        - link "引用问答" [ref=f1e22] [cursor=pointer]:
          - /url: "#questions"
          - generic [aria-hidden] [ref=f1e23]: ">_"
          - text: 引用问答
        - link "资产自查" [ref=f1e24] [cursor=pointer]:
          - /url: "#assets"
          - generic [aria-hidden] [ref=f1e25]: ⬡
          - text: 资产自查
      - generic [ref=f1e26]:
        - paragraph [ref=f1e27]: 协作
        - link "任务轨迹" [ref=f1e28] [cursor=pointer]:
          - /url: "#tasks"
          - generic [aria-hidden] [ref=f1e29]: ⌘
          - text: 任务轨迹
        - link "变化与推荐" [ref=f1e30] [cursor=pointer]:
          - /url: "#changes"
          - generic [aria-hidden] [ref=f1e31]: ↗
          - text: 变化与推荐
        - link "证据报告" [ref=f1e32] [cursor=pointer]:
          - /url: "#reports"
          - generic [aria-hidden] [ref=f1e33]: ▤
          - text: 证据报告
      - generic [ref=f1e34]:
        - paragraph [ref=f1e35]: 系统
        - link "运行状态" [ref=f1e36] [cursor=pointer]:
          - /url: "#runtime"
          - generic [aria-hidden] [ref=f1e37]: ◫
          - text: 运行状态
        - link "会话与权限" [ref=f1e38] [cursor=pointer]:
          - /url: "#session"
          - generic [aria-hidden] [ref=f1e39]: ◎
          - text: 会话与权限
    - generic [ref=f1e40]:
      - paragraph [ref=f1e41]: 可追溯的事实清晰的判断边界
      - text: AI 安全知识情报系统
      - code [ref=f1e42]: READ · VERIFY · CONNECT
  - generic [ref=f1e43]:
    - banner [ref=f1e44]:
      - generic [ref=f1e45]:
        - generic [aria-hidden] [ref=f1e46]: ">"
        - text: 工作台
        - generic [aria-hidden] [ref=f1e47]: /
        - text: 知识图谱
      - generic [ref=f1e48]:
        - text: 数据模式
        - strong [ref=f1e49]: 登录后确认
    - main [ref=f1e50]:
      - generic [ref=f1e51]:
        - generic [ref=f1e52]:
          - paragraph [ref=f1e53]: KNOWLEDGE / RELATIONS
          - heading "关联研究" [level=1] [ref=f1e54]: 关联研究_
          - paragraph [ref=f1e55]: 查看关系理由、证据与历史状态。
        - button "刷新状态" [ref=f1e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=f1e57]: ↻
          - text: 刷新状态
      - generic [ref=f1e59]:
        - heading "登录后查看证据图" [level=3] [ref=f1e60]
        - paragraph [ref=f1e61]: 当前没有可用认证上下文。请先恢复团队会话。
```

# Test source

```ts
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
  82  |     const evidenceLink = page.getByRole("complementary", { name: "关系检视", exact: true }).getByRole("link", { name: /原文片段 \[1\]/ });
  83  |     await expect(evidenceLink).toHaveAttribute("href", `#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
  84  |     await evidenceLink.click();
  85  |     await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  86  |     await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByText(fixtureOldRevisionId, { exact: true })).toBeVisible();
  87  |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
  88  |     await page.reload(); await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  89  |     await page.goBack();
  90  |     await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  91  |     await page.getByRole("link", { name: "返回事件", exact: true }).click();
  92  |     await expect(page.getByRole("link", { name: "查看证据关系图", exact: true })).toBeVisible();
  93  |     expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
  94  |     expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
  95  |     await info.attach("native-point-and-request-paths", { body: JSON.stringify({ width, nativePoint, requests: api.requests }), contentType: "application/json" });
  96  |   });
  97  | }
  98  | 
  99  | test("default App isolated fixture: loading empty partial stale and retry", async ({ page }) => {
  100 |   const api = await installFixture(page); api.hold = true;
  101 |   api.graph.nodes = api.graph.nodes.slice(0, 1); api.graph.edges = [];
  102 |   api.graph.gaps = graphRelationKinds.map((relation_type) => ({ relation_type, status: "unknown", reason: "no_current_supported_relation" }));
  103 |   await page.goto(`/#graph/${fixtureEventId}`);
  104 |   await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  105 |   api.hold = false; api.release();
  106 |   await expect(page.getByRole("heading", { name: "目前只有事件上下文", exact: true })).toBeVisible();
  107 |   await expect(page.getByText("关系缺口 · 6 项未知", { exact: true })).toBeVisible();
  108 |   api.graph = appGraphFixture(); api.graph.truncated = true; api.graph.gaps = [{ relation_type: "related_paper", status: "unknown", reason: "truncated" }];
  109 |   await page.getByRole("button", { name: "重新读取", exact: true }).click();
  110 |   await expect(page.locator(".graph-warning")).toContainText("截断");
  111 |   await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  112 |   api.graphStatus = 409; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  113 |   await expect(page.getByRole("heading", { name: "图快照已过期", exact: true })).toBeVisible();
  114 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  115 |   api.graphStatus = 200; await page.getByRole("button", { name: "重新取得图", exact: true }).click();
  116 |   await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  117 |   expect(await page.getByText("暂无风险", { exact: true }).count()).toBe(0);
  118 | });
  119 | 
  120 | test("default App isolated fixture: guest denied expired session logout clear", async ({ page }) => {
  121 |   const api = await installFixture(page); api.authenticated = false;
  122 |   await page.goto(`/#graph/${fixtureEventId}`);
  123 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  124 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  125 |   api.authenticated = true; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  126 |   api.graphStatus = 403; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  127 |   await expect(page.getByRole("heading", { name: "没有查看权限", exact: true })).toBeVisible();
  128 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  129 |   api.graphStatus = 401; await page.reload();
  130 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  131 |   api.graphStatus = 200; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  132 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  133 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  134 |   await page.goBack();
  135 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  136 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  137 | });
  138 | 
  139 | test("default App isolated fixture: legacy entry invalid route and future version fail closed", async ({ page }) => {
  140 |   const api = await installFixture(page);
  141 |   await page.goto("/#graph"); await expect(page.getByRole("link", { name: "进入情报列表", exact: true })).toBeVisible();
  142 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  143 |   await page.goto(`/#graph/${fixtureEventId}?tenant=forged`); await expect(page.getByRole("heading", { name: "工作区不存在", exact: true })).toBeVisible();
  144 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  145 |   api.dataMode = "unknown"; await page.goto(`/#graph/${fixtureEventId}`); await page.reload();
  146 |   await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
> 147 |   expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
      |                                                                ^ Error: expect(received).toBe(expected) // Object.is equality
  148 |   api.dataMode = "fixture";
  149 |   await page.route(`**/v1/events/${fixtureEventId}/graph?*`, async (route) => { await route.fulfill({ json: { ...appGraphFixture(), rule_version: "r10-graph-9.0.0" } }); });
  150 |   await page.reload(); await expect(page.getByRole("heading", { name: "图协议不匹配", exact: true })).toBeVisible();
  151 |   await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  152 |   expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
  153 | });
  154 | 
  155 | test("default App isolated fixture: late old tenant response cannot restore graph after session changes", async ({ page }) => {
  156 |   const api = await installFixture(page); api.hold = true;
  157 |   api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · 私有 A 旧图", scope: { visibility: "tenant", tenant_id: api.tenant } };
  158 |   api.graph.edges = api.graph.edges.map((edge) => ({ ...edge, scope: { visibility: "tenant", tenant_id: api.tenant } }));
  159 |   await page.goto(`/#graph/${fixtureEventId}`);
  160 |   await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  161 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  162 |   api.tenant = "graph-app-fixture-b";
  163 |   await page.getByRole("button", { name: "重新验证会话", exact: true }).click();
  164 |   await expect(page.getByText("graph-app-fixture-b", { exact: true })).toBeVisible();
  165 |   api.hold = false; api.release(); api.graph = appGraphFixture(); api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · B 当前图" };
  166 |   await page.goBack(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  167 |   await expect(page.getByRole("heading", { name: "合成 Fixture · B 当前图", exact: true })).toBeVisible();
  168 |   expect(await page.getByText("合成 Fixture · 私有 A 旧图", { exact: true }).count()).toBe(0);
  169 | });
  170 | 
```