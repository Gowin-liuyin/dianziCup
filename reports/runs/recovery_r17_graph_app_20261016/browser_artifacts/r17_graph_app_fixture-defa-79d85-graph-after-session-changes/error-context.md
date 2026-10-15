# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_graph_app_fixture.spec.ts >> default App isolated fixture: late old tenant response cannot restore graph after session changes
- Location: e2e\r17_graph_app_fixture.spec.ts:153:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('合成 Fixture · B 当前图', { exact: true })
Expected: visible
Error: strict mode violation: getByText('合成 Fixture · B 当前图', { exact: true }) resolved to 2 elements:
    1) <title>合成 Fixture · B 当前图</title> aka getByRole('button', { name: '事件节点：合成 Fixture · B 当前图' })
    2) <h4 class="graph-full-label">合成 Fixture · B 当前图</h4> aka getByRole('heading', { name: '合成 Fixture · B 当前图' })

Call log:
  - Expect "toBeVisible" getByText('合成 Fixture · B 当前图', { exact: true }) with timeout 5000ms
  - waiting for getByText('合成 Fixture · B 当前图', { exact: true })

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
        - text: 知识图谱
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 合成 / Fixture
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: KNOWLEDGE / RELATIONS
          - heading "关联研究" [level=1] [ref=e54]: 关联研究_
          - paragraph [ref=e55]: 查看关系理由、证据与历史状态。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - region [ref=e58]:
        - generic [ref=e59]:
          - generic [ref=e60]:
            - paragraph [ref=e61]: EVIDENCE GRAPH / 关系与原文
            - heading "证据关系图" [level=2] [ref=e62]
            - paragraph [ref=e63]: 从事件到关联依据，核查每条关系的版本与证据。
          - generic [ref=e64]:
            - generic [ref=e65]: 合成 / Fixture
            - link "返回事件" [ref=e66] [cursor=pointer]:
              - /url: "#events/10000000-0000-4000-8000-000000000001"
        - generic [ref=e67]:
          - generic [ref=e68]:
            - text: 快照
            - strong [ref=e69]: v3
          - generic [ref=e70]: 6 节点 / 6 支持关系
          - generic [ref=e71]: 上限 200 / 400
          - button "重新读取" [ref=e72] [cursor=pointer]
        - generic [ref=e73]:
          - generic [ref=e74]:
            - group "节点类型 / 视图筛选" [ref=e75]:
              - generic [ref=e77] [cursor=pointer]:
                - checkbox "来源修订" [checked] [ref=e78]
                - text: 来源修订
              - generic [ref=e80] [cursor=pointer]:
                - checkbox "事件" [checked] [disabled] [ref=e81]
                - text: 事件
              - generic [ref=e83] [cursor=pointer]:
                - checkbox "组件版本" [checked] [ref=e84]
                - text: 组件版本
              - generic [ref=e86] [cursor=pointer]:
                - checkbox "ATLAS" [checked] [ref=e87]
                - text: ATLAS
              - generic [ref=e89] [cursor=pointer]:
                - checkbox "论文" [checked] [ref=e90]
                - text: 论文
              - generic [ref=e92] [cursor=pointer]:
                - checkbox "修复" [checked] [ref=e93]
                - text: 修复
            - group "图画布控制" [ref=e95]:
              - button "缩小图" [ref=e96] [cursor=pointer]: −
              - status "图缩放比例" [ref=e97]: 100%
              - button "放大图" [ref=e98] [cursor=pointer]: +
              - button "重置视图" [ref=e99] [cursor=pointer]
              - button "向左平移" [ref=e100] [cursor=pointer]: ←
              - button "向右平移" [ref=e101] [cursor=pointer]: →
              - button "向上平移" [ref=e102] [cursor=pointer]: ↑
              - button "向下平移" [ref=e103] [cursor=pointer]: ↓
            - paragraph [ref=e104]: 图区域可滚动。Tab 选择节点或边，Enter / 空格检视；方向键滚动，缩放与重置在上方。
            - region "证据关系图画布" [ref=e105]:
              - group "事件与证据关系" [ref=e106]:
                - generic [ref=e108]: 来源修订
                - generic [ref=e110]: 事件
                - generic [ref=e112]: 组件版本
                - generic [ref=e114]: ATLAS
                - generic [ref=e116]: 论文
                - generic [ref=e118]: 修复
                - button "图关系 1：归于同一事件" [ref=e119] [cursor=pointer]
                - button "图关系 2：影响组件版本" [ref=e121] [cursor=pointer]
                - button "图关系 3：映射 ATLAS" [ref=e123] [cursor=pointer]
                - button "图关系 4：关联论文" [ref=e125] [cursor=pointer]
                - button "图关系 5：修复依据" [ref=e127] [cursor=pointer]
                - button "图关系 6：组件版本关联事件" [ref=e129] [cursor=pointer]
                - button "来源修订节点：合成厂商公告 · 历史修订" [ref=e131] [cursor=pointer]:
                  - generic: 来源修订
                  - generic: 合成厂商公告 · 历史修订
                - button "事件节点：合成 Fixture · B 当前图" [pressed] [ref=e134] [cursor=pointer]:
                  - generic: 事件
                  - generic: 合成 Fixture · B 当…
                - button "组件版本节点：Fixture · package 1.0 < 1.4（仅合成）" [ref=e137] [cursor=pointer]:
                  - generic: 组件版本
                  - generic: Fixture · packag…
                - button "ATLAS节点：Fixture · AML.T0000" [ref=e140] [cursor=pointer]:
                  - generic: ATLAS
                  - generic: Fixture · AML.T0…
                - button "论文节点：Fixture · 条件与缓解机制研究" [ref=e143] [cursor=pointer]:
                  - generic: 论文
                  - generic: Fixture · 条件与缓解机…
                - button "修复节点：Fixture · 需要核查的修复版本 1.4" [ref=e146] [cursor=pointer]:
                  - generic: 修复
                  - generic: Fixture · 需要核查的修…
            - region [ref=e149]:
              - generic [ref=e150]:
                - heading "关系列表" [level=3] [ref=e151]
                - generic [ref=e152]: 当前视图 6 / 快照 6
              - generic [ref=e153]:
                - button "01 归于同一事件 合成 Fixture · B 当前图 → 合成厂商公告 · 历史修订 支持" [ref=e154] [cursor=pointer]:
                  - generic [ref=e155]: "01"
                  - generic [ref=e156]:
                    - text: 归于同一事件
                    - generic [ref=e157]: 合成 Fixture · B 当前图 → 合成厂商公告 · 历史修订
                  - generic [ref=e158]: 支持
                - button "02 影响组件版本 合成 Fixture · B 当前图 → Fixture · package 1.0 < 1.4（仅合成） 支持" [ref=e159] [cursor=pointer]:
                  - generic [ref=e160]: "02"
                  - generic [ref=e161]:
                    - text: 影响组件版本
                    - generic [ref=e162]: 合成 Fixture · B 当前图 → Fixture · package 1.0 < 1.4（仅合成）
                  - generic [ref=e163]: 支持
                - button "03 映射 ATLAS 合成 Fixture · B 当前图 → Fixture · AML.T0000 支持" [ref=e164] [cursor=pointer]:
                  - generic [ref=e165]: "03"
                  - generic [ref=e166]:
                    - text: 映射 ATLAS
                    - generic [ref=e167]: 合成 Fixture · B 当前图 → Fixture · AML.T0000
                  - generic [ref=e168]: 支持
                - button "04 关联论文 合成 Fixture · B 当前图 → Fixture · 条件与缓解机制研究 支持" [ref=e169] [cursor=pointer]:
                  - generic [ref=e170]: "04"
                  - generic [ref=e171]:
                    - text: 关联论文
                    - generic [ref=e172]: 合成 Fixture · B 当前图 → Fixture · 条件与缓解机制研究
                  - generic [ref=e173]: 支持
                - button "05 修复依据 合成 Fixture · B 当前图 → Fixture · 需要核查的修复版本 1.4 支持" [ref=e174] [cursor=pointer]:
                  - generic [ref=e175]: "05"
                  - generic [ref=e176]:
                    - text: 修复依据
                    - generic [ref=e177]: 合成 Fixture · B 当前图 → Fixture · 需要核查的修复版本 1.4
                  - generic [ref=e178]: 支持
                - button "06 组件版本关联事件 Fixture · package 1.0 < 1.4（仅合成） → 合成 Fixture · B 当前图 支持" [ref=e179] [cursor=pointer]:
                  - generic [ref=e180]: "06"
                  - generic [ref=e181]:
                    - text: 组件版本关联事件
                    - generic [ref=e182]: Fixture · package 1.0 < 1.4（仅合成） → 合成 Fixture · B 当前图
                  - generic [ref=e183]: 支持
          - complementary [ref=e184]:
            - generic [ref=e185]:
              - paragraph [ref=e186]: INSPECT / 可追溯依据
              - heading "节点检视" [level=3] [ref=e187]
            - generic [ref=e188]: 事件
            - heading "合成 Fixture · B 当前图" [level=4] [ref=e189]
            - code [ref=e190]: 10000000-0000-4000-8000-000000000001
            - paragraph [ref=e191]: 公开范围 · 节点本身不是资产影响结论。
            - heading "关联关系" [level=4] [ref=e192]
            - generic [ref=e193]:
              - button "归于同一事件" [ref=e194] [cursor=pointer]: 归于同一事件 ↗
              - button "影响组件版本" [ref=e195] [cursor=pointer]: 影响组件版本 ↗
              - button "映射 ATLAS" [ref=e196] [cursor=pointer]: 映射 ATLAS ↗
              - button "关联论文" [ref=e197] [cursor=pointer]: 关联论文 ↗
              - button "修复依据" [ref=e198] [cursor=pointer]: 修复依据 ↗
              - button "组件版本关联事件" [ref=e199] [cursor=pointer]: 组件版本关联事件 ↗
            - paragraph [ref=e200]: 引文存在不等于内容支持。候选与待审关系未包含在此 supported 快照中；接口未提供人工审核进度。
        - group [ref=e201]:
          - generic "快照版本与内容标识" [ref=e202] [cursor=pointer]
      - generic [ref=e203]:
        - generic [ref=e204]: 环境未由服务端标明
        - generic [ref=e205]: 版本未由服务端标明
```

# Test source

```ts
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
> 165 |   await expect(page.getByText("合成 Fixture · B 当前图", { exact: true })).toBeVisible();
      |                                                                       ^ Error: expect(locator).toBeVisible() failed
  166 |   expect(await page.getByText("合成 Fixture · 私有 A 旧图", { exact: true }).count()).toBe(0);
  167 | });
  168 | 
```