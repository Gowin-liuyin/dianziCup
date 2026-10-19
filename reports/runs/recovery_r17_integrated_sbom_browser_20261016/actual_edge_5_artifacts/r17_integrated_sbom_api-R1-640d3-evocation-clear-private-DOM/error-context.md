# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_integrated_sbom_api.spec.ts >> R17 actual API 05: real role and session revocation clear private DOM
- Location: e2e\r17_integrated_sbom_api.spec.ts:177:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: page.waitForResponse: Test timeout of 60000ms exceeded.
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
        - text: 会话与权限
      - generic [ref=e48]:
        - text: 数据模式
        - strong [ref=e49]: 登录后确认
    - main [ref=e50]:
      - generic [ref=e51]:
        - generic [ref=e52]:
          - paragraph [ref=e53]: ACCESS / SESSION
          - heading "访问控制" [level=1] [ref=e54]: 访问控制_
          - paragraph [ref=e55]: 核对当前团队身份、授权与会话状态。
        - button "刷新状态" [ref=e56] [cursor=pointer]:
          - generic [aria-hidden] [ref=e57]: ↻
          - text: 刷新状态
      - generic [ref=e58]:
        - region [ref=e59]:
          - generic [ref=e60]:
            - generic [ref=e61]:
              - paragraph [ref=e62]: ACCESS / 访问
              - heading "团队会话" [level=2] [ref=e63]
            - generic [ref=e64]: 尚未登录
          - generic [ref=e65]:
            - paragraph [ref=e66]: 使用管理员为你创建的团队账号。
            - generic [ref=e67]:
              - generic [ref=e68]: 用户名
              - textbox "用户名" [disabled] [ref=e69]
              - generic [ref=e70]: 密码
              - textbox "密码" [disabled] [ref=e71]
              - button "提交中…" [disabled] [ref=e72]:
                - text: 提交中…
                - generic [aria-hidden] [ref=e73]: →
        - generic [ref=e74]:
          - paragraph [ref=e75]: TRUST BOUNDARY / 授权边界
          - heading "按权限查看 按证据判断" [level=2] [ref=e76]: 按权限查看按证据判断
          - paragraph [ref=e77]: 登录后，身份与权限由服务端确认。会话失效或退出时，页面立即清除身份信息。
          - link "返回运行概览 →" [ref=e78] [cursor=pointer]:
            - /url: "#runtime"
```

# Test source

```ts
  81  | 
  82  | test("R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation", async ({ page }, info) => {
  83  |   await login(page, 0);
  84  |   await expect(page.getByRole("heading", { name: "尚无可见资产清单", exact: true })).toBeVisible();
  85  |   await record(page, info, "empty-catalog");
  86  |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  87  |   firstCreated = created;
  88  |   await expect(page.getByText("pkg:npm/%40synthetic/root@1.0.0", { exact: true })).toBeVisible();
  89  |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  90  |   await expect(page.locator(".sbom-source-heading").filter({ hasText: "synthetic-root" })).toBeVisible();
  91  |   const navigation = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" });
  92  |   await expect(navigation.getByRole("button")).toHaveCount(6);
  93  |   await navigation.getByRole("button", { name: "依赖与标准关系 1", exact: true }).focus();
  94  |   await page.keyboard.press("Enter");
  95  |   await expect(page.locator(`[id='sbom-${created.snapshotId}-relationships']`)).toBeFocused();
  96  |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" }).getByText("dependsOn", { exact: true })).toBeVisible();
  97  |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  98  |   await expect(page.locator(".sbom-panel").getByText(/redacted-field:/)).toHaveCount(2);
  99  |   await expect(page.locator(".sbom-panel").getByText(/redacted-field:/).first()).toBeVisible();
  100 |   const delay = spawn("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", "sidecar-delay", "{}"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  101 |   const ended = new Promise<number | null>((resolve) => delay.once("exit", resolve));
  102 |   await new Promise<void>((resolve, reject) => { delay.stdout.once("data", () => resolve()); delay.once("error", reject); });
  103 |   await page.reload();
  104 |   await expect(page.getByText("正在读取固定快照 SBOM 声明…", { exact: true })).toBeVisible();
  105 |   await record(page, info, "actual-loading");
  106 |   expect(await ended).toBe(0);
  107 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  108 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  109 |   await record(page, info, "cdx-declarations-desktop");
  110 | });
  111 | 
  112 | test("R17 actual API 02: SPDX relations and public link keep private URI hidden", async ({ page }, info) => {
  113 |   await login(page, 1);
  114 |   if (firstCreated === null) throw new Error("first synthetic tenant asset required for cross-tenant proof");
  115 |   const foreign = await page.request.get(`/v1/assets/${firstCreated.assetId}/snapshots/${firstCreated.snapshotId}/sbom`);
  116 |   expect(foreign.status()).toBe(404);
  117 |   expect(await foreign.text()).not.toContain(firstCreated.snapshotId);
  118 |   await importThroughUi(page, spdxInput(), "spdx_json");
  119 |   await expect(page.getByText("DESCRIBES", { exact: true })).toBeVisible();
  120 |   await expect(page.getByText("pkg:pypi/synthetic-spdx@2.0", { exact: true })).toBeVisible();
  121 |   await expect(page.getByRole("link", { name: "打开服务器提供的公开文档 ↗", exact: true })).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  122 |   await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  123 |   await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  124 |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  125 |   await record(page, info, "spdx-privacy");
  126 | });
  127 | 
  128 | test("R17 actual API 03: three immutable snapshots, unknowns and stale pointer revalidation", async ({ page }, info) => {
  129 |   await login(page, 2);
  130 |   const first = await importThroughUi(page, cyclonedxInput("1.0.0", false), "cyclonedx_json");
  131 |   const me = await page.request.get("/v1/auth/me");
  132 |   const identity: unknown = await me.json();
  133 |   if (typeof identity !== "object" || identity === null || !("csrf_token" in identity) || typeof identity.csrf_token !== "string") throw new Error("actual CSRF identity missing");
  134 |   const conflictingRaw = Buffer.from(cyclonedxInput("2.0.0", true).toString("utf8").replace("root@2.0.0", "root@1.0.0"));
  135 |   const rejected = await page.request.post(`/v1/asset-imports?${new URLSearchParams({ asset_id: first.assetId, manifest_format: "cyclonedx_json", display_name: "Synthetic browser · 授权测试清单", source_version: "synthetic-browser-r17", observed_at: "2026-10-16T08:00:00+08:00" })}`, { data: conflictingRaw, headers: { Origin: new URL(page.url()).origin, "Content-Type": "application/json", "X-CSRF-Token": identity.csrf_token, "Idempotency-Key": "synthetic-conflicting-version" } });
  136 |   expect(rejected.status()).toBe(422);
  137 |   const second = await importThroughUi(page, cyclonedxInput("2.0.0", true), "cyclonedx_json", true);
  138 |   const third = await importThroughUi(page, cyclonedxInput(null, false), "cyclonedx_json", true);
  139 |   expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  140 |   await expect(page.getByRole("heading", { name: "快照 #3", exact: true })).toBeVisible();
  141 |   await expect(page.getByText("版本未知", { exact: true }).first()).toBeVisible();
  142 |   await expect(page.getByText("未知 · 当前响应未提供", { exact: true })).toBeVisible();
  143 |   await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  144 |   await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  145 |   await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  146 |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  147 |   await record(page, info, "fixed-history");
  148 |   await page.getByRole("button", { name: "查看当前快照", exact: true }).click();
  149 |   await page.reload();
  150 |   await expect(page.getByText(third.rawSha, { exact: true })).toBeVisible();
  151 |   await page.getByRole("button", { name: /查看快照 #2 · 历史/ }).click();
  152 |   await expect(page.getByText(second.rawSha, { exact: true })).toBeVisible();
  153 |   await expect(page.getByText("dependsOn", { exact: true })).toBeVisible();
  154 |   await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪", exact: true })).toBeDisabled();
  155 |   await expect(page.getByRole("button", { name: "查询授权外部观察 · 未就绪", exact: true })).toBeDisabled();
  156 | });
  157 | 
  158 | test("R17 actual API 04: database sidecar outage is partial 503 and recovers on retry", async ({ page }, info) => {
  159 |   await login(page, 3);
  160 |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  161 |   control("sidecar-unavailable");
  162 |   try {
  163 |     const response = page.waitForResponse((value) => new URL(value.url()).pathname.endsWith("/sbom"));
  164 |     await page.reload();
  165 |     expect((await response).status()).toBe(503);
  166 |     await expect(page.getByRole("heading", { name: "快照 #1", exact: true })).toBeVisible();
  167 |     await expect(page.getByRole("table", { name: "资产组件声明" })).toBeVisible();
  168 |     await expect(page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true })).toBeVisible();
  169 |     await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
  170 |     await record(page, info, "actual-503-partial");
  171 |   } finally { control("sidecar-restore"); }
  172 |   await page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true }).click();
  173 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  174 |   await record(page, info, "actual-503-recovery");
  175 | });
  176 | 
  177 | test("R17 actual API 05: real role and session revocation clear private DOM", async ({ page }, info) => {
  178 |   await login(page, 4);
  179 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  180 |   control("revoke-read", { username: actor(4).username });
> 181 |   const denied = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
      |                       ^ Error: page.waitForResponse: Test timeout of 60000ms exceeded.
  182 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  183 |   expect((await denied).status()).toBe(403);
  184 |   await expect(page.getByText("当前会话没有此项资产权限，请联系租户管理员。", { exact: true })).toBeVisible();
  185 |   await expect(page.getByRole("heading", { name: "当前授权资产", exact: true })).toHaveCount(0);
  186 |   await expect(page.getByRole("heading", { name: "快照历史", exact: true })).toHaveCount(0);
  187 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  188 |   await record(page, info, "actual-403-revocation");
  189 |   await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  190 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  191 |   await login(page, 5);
  192 |   await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  193 |   control("revoke-session", { username: actor(5).username });
  194 |   const expired = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/assets");
  195 |   await page.getByRole("button", { name: "刷新资产与快照", exact: true }).click();
  196 |   expect((await expired).status()).toBe(401);
  197 |   await expect(page.getByText("会话已失效，私有资产已清除", { exact: true })).toBeVisible();
  198 |   await expect(page.getByLabel("选择本地清单", { exact: true })).toHaveCount(0);
  199 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  200 |   await record(page, info, "actual-401-revocation");
  201 | });
  202 | 
  203 | test("R17 actual API 06: 390px keyboard, declaration focus and reduced motion", async ({ page }, info) => {
  204 |   await login(page, 6);
  205 |   await importThroughUi(page, cyclonedxInput("1.0.0", true, 25), "cyclonedx_json");
  206 |   await page.setViewportSize({ width: 390, height: 844 });
  207 |   await page.emulateMedia({ reducedMotion: "reduce" });
  208 |   const target = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" }).getByRole("button", { name: "组件来源 25", exact: true });
  209 |   await target.focus();
  210 |   await page.keyboard.press("Enter");
  211 |   await expect(page.locator(".sbom-declaration-section").first()).toBeFocused();
  212 |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  213 |   expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
  214 |   const components = page.getByRole("table", { name: "资产组件声明" });
  215 |   await expect(components.locator("tbody tr")).toHaveCount(20);
  216 |   await page.getByRole("button", { name: "下一页组件", exact: true }).focus();
  217 |   await page.keyboard.press("Enter");
  218 |   await expect(components.locator("tbody tr")).toHaveCount(5);
  219 |   await record(page, info, "actual-mobile-390");
  220 |   await page.setViewportSize({ width: 1366, height: 900 });
  221 |   await page.emulateMedia({ reducedMotion: "no-preference" });
  222 |   const transform = await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).transform);
  223 |   await record(page, info, "ambient-frame-a");
  224 |   await expect.poll(() => page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).transform)).not.toBe(transform);
  225 |   await record(page, info, "ambient-frame-b");
  226 | });
  227 | 
```