# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_integrated_sbom_api.spec.ts >> R17 actual API 05: real role and session revocation clear private DOM
- Location: e2e\r17_integrated_sbom_api.spec.ts:163:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Test timeout of 60000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: '退出登录', exact: true })

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
        - text: 资产自查
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 合成 / Fixture
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: ASSESSMENT / ASSETS
          - heading "版本与资产" [level=1] [ref=e54]: 版本与资产_
          - paragraph [ref=e55]: 在固定资产快照上核查版本、条件与影响。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - generic [ref=e58]:
        - alert [ref=e59]:
          - paragraph [ref=e60]: 当前会话没有此项资产权限，请联系租户管理员。
          - paragraph [ref=e61]:
            - text: 追踪标识
            - code [ref=e62]: c25d2c2c-ad6e-4d7a-8759-4f19c714728e
        - link "核对会话与权限" [ref=e63] [cursor=pointer]:
          - /url: "#session"
      - generic [ref=e64]:
        - generic [ref=e65]: 环境 test
        - generic [ref=e66]: 版本 0.1.0
```

# Test source

```ts
  75  |   const logout = page.getByRole("button", { name: "退出登录", exact: true });
  76  |   if (await logout.isVisible()) await logout.click();
  77  |   writeFileSync(info.outputPath("actual-http-flow.json"), JSON.stringify(httpFlows.get(page), null, 2));
  78  | });
  79  | 
  80  | test("R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation", async ({ page }, info) => {
  81  |   await login(page, 0);
  82  |   await expect(page.getByRole("heading", { name: "尚无可见资产清单", exact: true })).toBeVisible();
  83  |   await record(page, info, "empty-catalog");
  84  |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  85  |   await expect(page.getByText("pkg:npm/%40synthetic/root@1.0.0", { exact: true })).toBeVisible();
  86  |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  87  |   await expect(page.locator(".sbom-source-heading").filter({ hasText: "synthetic-root" })).toBeVisible();
  88  |   const navigation = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" });
  89  |   await expect(navigation.getByRole("button")).toHaveCount(6);
  90  |   await navigation.getByRole("button", { name: "依赖与标准关系 1", exact: true }).focus();
  91  |   await page.keyboard.press("Enter");
  92  |   await expect(page.locator(`[id='sbom-${created.snapshotId}-relationships']`)).toBeFocused();
  93  |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" }).getByText("dependsOn", { exact: true })).toBeVisible();
  94  |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  95  |   await expect(page.locator(".sbom-panel").getByText(/redacted-field:/)).toBeVisible();
  96  |   const delay = spawn("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", "sidecar-delay", "{}"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  97  |   const ended = new Promise<number | null>((resolve) => delay.once("exit", resolve));
  98  |   await new Promise<void>((resolve, reject) => { delay.stdout.once("data", () => resolve()); delay.once("error", reject); });
  99  |   await page.reload();
  100 |   await expect(page.getByText("正在读取固定快照 SBOM 声明…", { exact: true })).toBeVisible();
  101 |   await record(page, info, "actual-loading");
  102 |   expect(await ended).toBe(0);
  103 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  104 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  105 |   await record(page, info, "cdx-declarations-desktop");
  106 | });
  107 | 
  108 | test("R17 actual API 02: SPDX relations and public link keep private URI hidden", async ({ page }, info) => {
  109 |   await login(page, 1);
  110 |   await importThroughUi(page, spdxInput(), "spdx_json");
  111 |   await expect(page.getByText("DESCRIBES", { exact: true })).toBeVisible();
  112 |   await expect(page.getByText("pkg:pypi/synthetic-spdx@2.0", { exact: true })).toBeVisible();
  113 |   await expect(page.getByRole("link", { name: "打开服务器提供的公开文档 ↗", exact: true })).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  114 |   await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  115 |   await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  116 |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  117 |   await record(page, info, "spdx-privacy");
  118 | });
  119 | 
  120 | test("R17 actual API 03: three immutable snapshots, unknowns and stale pointer revalidation", async ({ page }, info) => {
  121 |   await login(page, 2);
  122 |   const first = await importThroughUi(page, cyclonedxInput("1.0.0", false), "cyclonedx_json");
  123 |   const second = await importThroughUi(page, cyclonedxInput("2.0.0", true), "cyclonedx_json", true);
  124 |   const third = await importThroughUi(page, cyclonedxInput(null, false), "cyclonedx_json", true);
  125 |   expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  126 |   await expect(page.getByRole("heading", { name: "快照 #3", exact: true })).toBeVisible();
  127 |   await expect(page.getByText("版本未知", { exact: true }).first()).toBeVisible();
  128 |   await expect(page.getByText("未知 · 当前响应未提供", { exact: true })).toBeVisible();
  129 |   await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  130 |   await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  131 |   await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  132 |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  133 |   await record(page, info, "fixed-history");
  134 |   await page.getByRole("button", { name: "查看当前快照", exact: true }).click();
  135 |   await page.reload();
  136 |   await expect(page.getByText(third.rawSha, { exact: true })).toBeVisible();
  137 |   await page.getByRole("button", { name: /查看快照 #2 · 历史/ }).click();
  138 |   await expect(page.getByText(second.rawSha, { exact: true })).toBeVisible();
  139 |   await expect(page.getByText("dependsOn", { exact: true })).toBeVisible();
  140 |   await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪", exact: true })).toBeDisabled();
  141 |   await expect(page.getByRole("button", { name: "查询授权外部观察 · 未就绪", exact: true })).toBeDisabled();
  142 | });
  143 | 
  144 | test("R17 actual API 04: database sidecar outage is partial 503 and recovers on retry", async ({ page }, info) => {
  145 |   await login(page, 3);
  146 |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  147 |   control("sidecar-unavailable");
  148 |   try {
  149 |     const response = page.waitForResponse((value) => new URL(value.url()).pathname.endsWith("/sbom"));
  150 |     await page.reload();
  151 |     expect((await response).status()).toBe(503);
  152 |     await expect(page.getByRole("heading", { name: "快照 #1", exact: true })).toBeVisible();
  153 |     await expect(page.getByRole("table", { name: "资产组件声明" })).toBeVisible();
  154 |     await expect(page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true })).toBeVisible();
  155 |     await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
  156 |     await record(page, info, "actual-503-partial");
  157 |   } finally { control("sidecar-restore"); }
  158 |   await page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true }).click();
  159 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  160 |   await record(page, info, "actual-503-recovery");
  161 | });
  162 | 
  163 | test("R17 actual API 05: real role and session revocation clear private DOM", async ({ page }, info) => {
  164 |   await login(page, 4);
  165 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  166 |   control("revoke-read", { username: actor(4).username });
  167 |   const denied = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  168 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  169 |   expect((await denied).status()).toBe(403);
  170 |   await expect(page.getByText("当前会话没有此项资产权限，请联系租户管理员。", { exact: true })).toBeVisible();
  171 |   await expect(page.getByRole("heading", { name: "当前授权资产", exact: true })).toHaveCount(0);
  172 |   await expect(page.getByRole("heading", { name: "快照历史", exact: true })).toHaveCount(0);
  173 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  174 |   await record(page, info, "actual-403-revocation");
> 175 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
      |                                                                 ^ Error: locator.click: Test timeout of 60000ms exceeded.
  176 |   await login(page, 5);
  177 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  178 |   control("revoke-session", { username: actor(5).username });
  179 |   const expired = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  180 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  181 |   expect((await expired).status()).toBe(401);
  182 |   await expect(page.getByText("会话已失效，私有资产已清除", { exact: true })).toBeVisible();
  183 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  184 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  185 |   await record(page, info, "actual-401-revocation");
  186 | });
  187 | 
  188 | test("R17 actual API 06: 390px keyboard, declaration focus and reduced motion", async ({ page }, info) => {
  189 |   await login(page, 6);
  190 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  191 |   await page.setViewportSize({ width: 390, height: 844 });
  192 |   await page.emulateMedia({ reducedMotion: "reduce" });
  193 |   const target = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" }).getByRole("button", { name: "组件来源 2", exact: true });
  194 |   await target.focus();
  195 |   await page.keyboard.press("Enter");
  196 |   await expect(page.locator(".sbom-declaration-section").first()).toBeFocused();
  197 |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  198 |   expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  199 |   await record(page, info, "actual-mobile-390");
  200 | });
  201 | 
```