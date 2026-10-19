# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_integrated_sbom_api.spec.ts >> R17 actual API 02: SPDX relations and public link keep private URI hidden
- Location: e2e\r17_integrated_sbom_api.spec.ts:107:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: "223914328b60c60b2be1ccf65e372707c1ac1edcf04f434ba81315017d7d916d"
Received: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
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
        - generic [ref=e59]:
          - paragraph [ref=e60]:
            - generic [ref=e61]: PRIVATE INVENTORY / 授权清单
            - text: 仅显示当前认证租户的资产声明
          - generic [ref=e62]: 合成 Fixture · 非真实资产
          - button "刷新资产与快照" [disabled] [ref=e63]
        - status [ref=e64]:
          - strong [ref=e65]: 导入成功 · 服务端已保存快照
          - paragraph [ref=e66]:
            - text: "快照 #1 ·"
            - code [ref=e67]: 153a2679-a848-556a-9edf-bbb06e7fbb81
            - text: 。当前内容请以重新读取的资产详情为准。
        - group [ref=e68]:
          - generic "+ 导入授权清单 JSON / CSV / CycloneDX / SPDX · 最大 1 MiB" [ref=e69] [cursor=pointer]:
            - text: + 导入授权清单
            - generic [ref=e70]: JSON / CSV / CycloneDX / SPDX · 最大 1 MiB
          - option "JSON manifest v1" [selected]
          - option "CSV 组件清单"
          - option "CycloneDX JSON 1.5 / 1.6 / 1.7"
          - option "SPDX JSON 2.3"
        - generic [ref=e71]:
          - region [ref=e72]:
            - generic [ref=e73]:
              - generic [ref=e74]:
                - paragraph [ref=e75]: INVENTORY / 资产目录
                - heading "当前授权资产" [level=2] [ref=e76]
              - generic [ref=e77]: 等待读取
            - generic [ref=e78]:
              - generic [ref=e79]: 按组件包名精确筛选
              - generic [ref=e80]:
                - textbox "按组件包名精确筛选" [ref=e81]:
                  - /placeholder: package_name
                - button "筛选资产" [disabled] [ref=e82]
            - status [ref=e83]: 正在读取资产页…
            - list
          - region [ref=e84]:
            - generic [ref=e85]:
              - generic [ref=e86]:
                - paragraph [ref=e87]: ASSET / 私有资产检视
                - heading "资产详情" [level=2] [ref=e88]
              - link "返回资产列表" [ref=e89] [cursor=pointer]:
                - /url: "#assets"
            - status [ref=e90]: 正在读取当前资产快照…
      - generic [ref=e91]:
        - generic [ref=e92]: 环境 test
        - generic [ref=e93]: 版本 0.1.0
```

# Test source

```ts
  1   | import process from "node:process";
  2   | import { createHash } from "node:crypto";
  3   | import { execFileSync, spawn } from "node:child_process";
  4   | import { writeFileSync } from "node:fs";
  5   | import { expect, test, type Page, type TestInfo } from "@playwright/test";
  6   | import { cyclonedxInput, spdxInput } from "./helpers/r17-sbom-inputs";
  7   | 
  8   | const httpFlows = new WeakMap<Page, { path: string; method: string; status: number; observed_at: string }[]>();
  9   | test.beforeEach(async ({ page }) => {
  10  |   const responses: { path: string; method: string; status: number; observed_at: string }[] = [];
  11  |   httpFlows.set(page, responses);
  12  |   page.on("response", (response) => {
  13  |     const path = new URL(response.url()).pathname;
  14  |     if (path.startsWith("/v1/")) responses.push({ path, method: response.request().method(), status: response.status(), observed_at: new Date().toISOString() });
  15  |   });
  16  | });
  17  | 
  18  | function actor(index: number): { username: string; password: string } {
  19  |   const accounts: unknown = JSON.parse(process.env.R17_BROWSER_ACCOUNTS ?? "null");
  20  |   if (!Array.isArray(accounts)) throw new Error("isolated browser actors must be injected");
  21  |   const account: unknown = accounts[index];
  22  |   if (typeof account !== "object" || account === null || !("username" in account) || !("password" in account) || typeof account.username !== "string" || typeof account.password !== "string") throw new Error("isolated actor schema invalid");
  23  |   return { username: account.username, password: account.password };
  24  | }
  25  | 
  26  | function control(action: string, payload: Record<string, string> = {}): unknown {
  27  |   const output = execFileSync("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", action, JSON.stringify(payload)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 10_000 });
  28  |   return JSON.parse(output);
  29  | }
  30  | 
  31  | async function login(page: Page, index: number) {
  32  |   const account = actor(index);
  33  |   await page.goto("/#session");
  34  |   await page.getByLabel("用户名", { exact: true }).fill(account.username);
  35  |   await page.getByLabel("密码", { exact: true }).fill(account.password);
  36  |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  37  |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  38  |   await page.getByRole("link", { name: "资产自查", exact: true }).click();
  39  |   await expect(page.getByText("合成 Fixture · 非真实资产", { exact: true })).toBeVisible();
  40  |   const session = (await page.context().cookies()).find((cookie) => cookie.name === "ai_intel_session");
  41  |   expect(session?.httpOnly).toBe(true);
  42  |   expect(session?.sameSite).toBe("Strict");
  43  | }
  44  | 
  45  | async function record(page: Page, info: TestInfo, name: string) {
  46  |   const screenshot = info.outputPath(name + ".png");
  47  |   await page.screenshot({ path: screenshot, fullPage: true });
  48  |   writeFileSync(info.outputPath(name + ".json"), JSON.stringify({ name, observed_at: new Date().toISOString(), url: page.url(), viewport: page.viewportSize(), screenshot, data_mode: "fixture", actual_api: true }, null, 2));
  49  | }
  50  | 
  51  | async function importThroughUi(page: Page, raw: Buffer, format: "cyclonedx_json" | "spdx_json", append = false) {
  52  |   if ((await page.locator(".asset-import-panel").getAttribute("open")) === null) await page.locator(".asset-import-panel summary").click();
  53  |   await page.getByLabel("清单格式", { exact: true }).selectOption(format);
  54  |   await page.getByLabel("选择本地清单", { exact: true }).setInputFiles({ name: "synthetic-browser.json", mimeType: "application/json", buffer: raw });
  55  |   if (append) await page.getByLabel("追加到当前所选资产（名称保持一致）", { exact: true }).check();
  56  |   else await page.getByLabel("资产名称", { exact: true }).fill("Synthetic browser · 授权测试清单");
  57  |   await page.getByLabel("输入来源版本", { exact: true }).fill("synthetic-browser-r17");
  58  |   await page.getByLabel("实际观察时间（含时区）", { exact: true }).fill("2026-10-16T08:00:00+08:00");
  59  |   const responsePromise = page.waitForResponse((response) => new URL(response.url()).pathname === "/v1/asset-imports" && response.request().method() === "POST");
  60  |   await page.getByRole("button", { name: "提交授权清单", exact: true }).click();
  61  |   const response = await responsePromise;
  62  |   expect(response.status()).toBe(201);
> 63  |   expect(createHash("sha256").update(response.request().postDataBuffer() ?? Buffer.alloc(0)).digest("hex")).toBe(createHash("sha256").update(raw).digest("hex"));
      |                                                                                                             ^ Error: expect(received).toBe(expected) // Object.is equality
  64  |   const created: unknown = await response.json();
  65  |   if (typeof created !== "object" || created === null || !("asset_id" in created) || typeof created.asset_id !== "string" || !("snapshot" in created) || typeof created.snapshot !== "object" || created.snapshot === null || !("snapshot_id" in created.snapshot) || typeof created.snapshot.snapshot_id !== "string") throw new Error("actual import response invalid");
  66  |   await expect(page.getByRole("heading", { name: "Synthetic browser · 授权测试清单", exact: true })).toBeVisible();
  67  |   await expect(page.getByText("r11-sbom-adapter-1", { exact: true })).toBeVisible();
  68  |   const rawSha = createHash("sha256").update(raw).digest("hex");
  69  |   expect(control("verify-upload", { snapshot_id: created.snapshot.snapshot_id, raw_sha256: rawSha })).toMatchObject({ raw_sha256: rawSha, snapshot_id: created.snapshot.snapshot_id, migration: "0022_sbom_sidecars", public_schema: "public" });
  70  |   return { assetId: created.asset_id, snapshotId: created.snapshot.snapshot_id, rawSha };
  71  | }
  72  | 
  73  | test.afterEach(async ({ page }, info) => {
  74  |   const logout = page.getByRole("button", { name: "退出登录", exact: true });
  75  |   if (await logout.isVisible()) await logout.click();
  76  |   writeFileSync(info.outputPath("actual-http-flow.json"), JSON.stringify(httpFlows.get(page), null, 2));
  77  | });
  78  | 
  79  | test("R17 actual API 01: empty catalog, raw POST, typed sidecar and declaration navigation", async ({ page }, info) => {
  80  |   await login(page, 0);
  81  |   await expect(page.getByRole("heading", { name: "尚无可见资产清单", exact: true })).toBeVisible();
  82  |   await record(page, info, "empty-catalog");
  83  |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  84  |   await expect(page.getByText("pkg:npm/%40synthetic/root@1.0.0", { exact: true })).toBeVisible();
  85  |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  86  |   await expect(page.locator(".sbom-source-heading").filter({ hasText: "synthetic-root" })).toBeVisible();
  87  |   const navigation = page.getByRole("navigation", { name: "当前固定 SBOM 的声明导航" });
  88  |   await expect(navigation.getByRole("button")).toHaveCount(6);
  89  |   await navigation.getByRole("button", { name: "依赖与标准关系 1", exact: true }).focus();
  90  |   await page.keyboard.press("Enter");
  91  |   await expect(page.locator(`[id='sbom-${created.snapshotId}-relationships']`)).toBeFocused();
  92  |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" }).getByText("dependsOn", { exact: true })).toBeVisible();
  93  |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  94  |   await expect(page.locator(".sbom-panel").getByText(/redacted-field:/)).toBeVisible();
  95  |   const delay = spawn("D:/dianzi/backend/.venv/Scripts/python.exe", ["e2e/helpers/r17_sbom_control.py", "sidecar-delay", "{}"], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  96  |   const ended = new Promise<number | null>((resolve) => delay.once("exit", resolve));
  97  |   await new Promise<void>((resolve, reject) => { delay.stdout.once("data", () => resolve()); delay.once("error", reject); });
  98  |   await page.reload();
  99  |   await expect(page.getByText("正在读取固定快照 SBOM 声明…", { exact: true })).toBeVisible();
  100 |   await record(page, info, "actual-loading");
  101 |   expect(await ended).toBe(0);
  102 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  103 |   expect(await page.evaluate(() => localStorage.length + sessionStorage.length)).toBe(0);
  104 |   await record(page, info, "cdx-declarations-desktop");
  105 | });
  106 | 
  107 | test("R17 actual API 02: SPDX relations and public link keep private URI hidden", async ({ page }, info) => {
  108 |   await login(page, 1);
  109 |   await importThroughUi(page, spdxInput(), "spdx_json");
  110 |   await expect(page.getByText("DESCRIBES", { exact: true })).toBeVisible();
  111 |   await expect(page.getByText("pkg:pypi/synthetic-spdx@2.0", { exact: true })).toBeVisible();
  112 |   await expect(page.getByRole("link", { name: "打开服务器提供的公开文档 ↗", exact: true })).toHaveAttribute("href", "https://example.com/synthetic.spdx.json");
  113 |   await expect(page.getByText("原 URI 已隐藏 · 不恢复或点击不安全定位", { exact: true })).toBeVisible();
  114 |   await expect(page.locator("a[href^='file:']")).toHaveCount(0);
  115 |   await expect(page.getByText("file:///synthetic-private-location", { exact: true })).toHaveCount(0);
  116 |   await record(page, info, "spdx-privacy");
  117 | });
  118 | 
  119 | test("R17 actual API 03: three immutable snapshots, unknowns and stale pointer revalidation", async ({ page }, info) => {
  120 |   await login(page, 2);
  121 |   const first = await importThroughUi(page, cyclonedxInput("1.0.0", false), "cyclonedx_json");
  122 |   const second = await importThroughUi(page, cyclonedxInput("2.0.0", true), "cyclonedx_json", true);
  123 |   const third = await importThroughUi(page, cyclonedxInput(null, false), "cyclonedx_json", true);
  124 |   expect(new Set([first.snapshotId, second.snapshotId, third.snapshotId]).size).toBe(3);
  125 |   await expect(page.getByRole("heading", { name: "快照 #3", exact: true })).toBeVisible();
  126 |   await expect(page.getByText("版本未知", { exact: true }).first()).toBeVisible();
  127 |   await expect(page.getByText("未知 · 当前响应未提供", { exact: true })).toBeVisible();
  128 |   await page.getByRole("button", { name: /查看快照 #1 · 历史/ }).click();
  129 |   await expect(page.getByText(first.rawSha, { exact: true })).toBeVisible();
  130 |   await expect(page.getByText(/正在查看历史快照/)).toBeVisible();
  131 |   await expect(page.getByRole("table", { name: "SBOM 原始关系声明" })).toHaveCount(0);
  132 |   await record(page, info, "fixed-history");
  133 |   await page.getByRole("button", { name: "查看当前快照", exact: true }).click();
  134 |   await page.reload();
  135 |   await expect(page.getByText(third.rawSha, { exact: true })).toBeVisible();
  136 |   await page.getByRole("button", { name: /查看快照 #2 · 历史/ }).click();
  137 |   await expect(page.getByText(second.rawSha, { exact: true })).toBeVisible();
  138 |   await expect(page.getByText("dependsOn", { exact: true })).toBeVisible();
  139 |   await expect(page.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪", exact: true })).toBeDisabled();
  140 |   await expect(page.getByRole("button", { name: "查询授权外部观察 · 未就绪", exact: true })).toBeDisabled();
  141 | });
  142 | 
  143 | test("R17 actual API 04: database sidecar outage is partial 503 and recovers on retry", async ({ page }, info) => {
  144 |   await login(page, 3);
  145 |   const created = await importThroughUi(page, cyclonedxInput(), "cyclonedx_json");
  146 |   control("sidecar-unavailable");
  147 |   try {
  148 |     const response = page.waitForResponse((value) => new URL(value.url()).pathname.endsWith("/sbom"));
  149 |     await page.reload();
  150 |     expect((await response).status()).toBe(503);
  151 |     await expect(page.getByRole("heading", { name: "快照 #1", exact: true })).toBeVisible();
  152 |     await expect(page.getByRole("table", { name: "资产组件声明" })).toBeVisible();
  153 |     await expect(page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true })).toBeVisible();
  154 |     await expect(page.getByText(created.rawSha, { exact: true })).toHaveCount(0);
  155 |     await record(page, info, "actual-503-partial");
  156 |   } finally { control("sidecar-restore"); }
  157 |   await page.getByRole("button", { name: "重试固定 SBOM 声明", exact: true }).click();
  158 |   await expect(page.getByText(created.rawSha, { exact: true })).toBeVisible();
  159 |   await record(page, info, "actual-503-recovery");
  160 | });
  161 | 
  162 | test("R17 actual API 05: real role and session revocation clear private DOM", async ({ page }, info) => {
  163 |   await login(page, 4);
```