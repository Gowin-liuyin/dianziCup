# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r01_auth.spec.ts >> T40-C03 real browser offline state and recovery
- Location: e2e\r01_auth.spec.ts:60:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('button', { name: '退出登录', exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('button', { name: '退出登录', exact: true }) with timeout 10000ms
  - waiting for getByRole('button', { name: '退出登录', exact: true })

```

```yaml
- link "跳到主要内容":
  - /url: "#main-content"
- complementary:
  - link "安全情报 AI INTELLIGENCE":
    - /url: "#main-content"
  - navigation "工作台导航":
    - link "运行状态":
      - /url: "#runtime"
    - link "会话与权限":
      - /url: "#session"
  - paragraph: 可追溯的事实 清晰的判断边界
  - text: AI 安全知识情报系统
- banner:
  - text: 工作台 / 运行概览 数据模式
  - strong: 登录后确认
- main:
  - paragraph: WORKSPACE / 系统
  - heading "运行概览" [level=1]
  - paragraph: 查看服务状态，管理你的团队会话。
  - button "刷新状态"
  - region "当前运行摘要":
    - text: API 进程
    - strong: 可响应
    - text: 存活不代表依赖已就绪 依赖就绪
    - strong: 全部依赖就绪
    - text: 基于服务端实际探测结果 数据模式
    - strong: 登录后确认
    - text: 模式与业务验证状态分别呈现
  - region "服务与依赖":
    - paragraph: RUNTIME / 运行
    - heading "服务与依赖" [level=2]
    - text: 就绪
    - table "实际依赖探测结果":
      - rowgroup:
        - row "依赖 状态 探测说明":
          - columnheader "依赖"
          - columnheader "状态"
          - columnheader "探测说明"
      - rowgroup:
        - row "数据库 database 就绪 服务端未提供附加说明":
          - rowheader "数据库 database"
          - cell "就绪"
          - cell "服务端未提供附加说明"
        - row "缓存服务 cache 就绪 服务端未提供附加说明":
          - rowheader "缓存服务 cache"
          - cell "就绪"
          - cell "服务端未提供附加说明"
        - row "搜索服务 search 就绪 服务端未提供附加说明":
          - rowheader "搜索服务 search"
          - cell "就绪"
          - cell "服务端未提供附加说明"
        - row "任务进程 worker 就绪 服务端未提供附加说明":
          - rowheader "任务进程 worker"
          - cell "就绪"
          - cell "服务端未提供附加说明"
        - row "调度进程 scheduler 就绪 服务端未提供附加说明":
          - rowheader "调度进程 scheduler"
          - cell "就绪"
          - cell "服务端未提供附加说明"
    - paragraph:
      - text: 本页检查于
      - time: 2026-10-15T00:59:27+08:00
  - region "团队会话":
    - paragraph: ACCESS / 访问
    - heading "团队会话" [level=2]
    - text: 尚未登录
    - paragraph: 使用管理员为你创建的团队账号。
    - text: 用户名
    - textbox "用户名"
    - text: 密码
    - textbox "密码"
    - button "登录工作台"
    - alert:
      - paragraph: 登录请求过于频繁，请稍后重试。
      - paragraph:
        - text: 追踪标识
        - code: 7880fa37-b047-4e6f-819c-d6a5ec7e95dc
      - button "重新检查会话"
```

# Test source

```ts
  1  | import process from "node:process";
  2  | import { expect, test, type Page } from "@playwright/test";
  3  | 
  4  | function requiredEnvironment(name: string): string {
  5  |   const value = process.env[name];
  6  |   if (!value) throw new Error(`${name} must be injected for the isolated real API run`);
  7  |   return value;
  8  | }
  9  | 
  10 | async function loginWithRealApi(page: Page) {
  11 |   await page.goto("/");
  12 |   await page.getByLabel("用户名", { exact: true }).fill(requiredEnvironment("DIANZI_E2E_USERNAME"));
  13 |   await page.getByLabel("密码", { exact: true }).fill(requiredEnvironment("DIANZI_E2E_PASSWORD"));
  14 |   await page.getByRole("button", { name: "登录工作台", exact: true }).click();
> 15 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
     |                                                                         ^ Error: expect(locator).toBeVisible() failed
  16 | }
  17 | 
  18 | test("T40-C01/C02/C05 real login, reload, cookie/CSRF and revocation", async ({ page }, testInfo) => {
  19 |   await page.goto("/");
  20 |   await expect(page.getByText("尚未登录", { exact: true })).toBeVisible();
  21 |   await expect(page.getByText("已授予权限", { exact: true })).toHaveCount(0);
  22 |   await loginWithRealApi(page);
  23 |   await expect(page.getByText("真实 / Live", { exact: true }).first()).toBeVisible();
  24 |   await expect(page.getByRole("table", { name: "实际依赖探测结果" })).toBeVisible();
  25 |   const cookies = await page.context().cookies();
  26 |   const sessionCookie = cookies.find((cookie) => cookie.name === "ai_intel_session");
  27 |   expect(sessionCookie?.httpOnly).toBe(true);
  28 |   expect(sessionCookie?.sameSite).toBe("Strict");
  29 |   expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  30 |   await page.reload();
  31 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  32 |   await page.screenshot({ path: testInfo.outputPath("authenticated-workbench.png"), fullPage: true });
  33 |   const logoutResponse = page.waitForResponse((response) => response.url().endsWith("/v1/auth/logout") && response.request().method() === "POST");
  34 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  35 |   expect((await logoutResponse).status()).toBe(200);
  36 |   await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
  37 |   await expect(page.getByText("已授予权限", { exact: true })).toHaveCount(0);
  38 |   await page.reload();
  39 |   await expect(page.getByText("尚未登录", { exact: true })).toBeVisible();
  40 | });
  41 | 
  42 | test("T40-C06 real keyboard focus and 390px authenticated layout", async ({ page }, testInfo) => {
  43 |   await page.goto("/");
  44 |   await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
  45 |   await page.keyboard.press("Tab");
  46 |   await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  47 |   await page.keyboard.press("Enter");
  48 |   await expect(page.locator("#main-content")).toBeFocused();
  49 |   await page.keyboard.press("Tab");
  50 |   await expect(page.getByRole("button", { name: "刷新状态", exact: true })).toBeFocused();
  51 |   await loginWithRealApi(page);
  52 |   await page.setViewportSize({ width: 390, height: 844 });
  53 |   expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  54 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  55 |   await page.screenshot({ path: testInfo.outputPath("authenticated-mobile-390.png"), fullPage: true });
  56 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  57 |   await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
  58 | });
  59 | 
  60 | test("T40-C03 real browser offline state and recovery", async ({ page, context }) => {
  61 |   await loginWithRealApi(page);
  62 |   await context.setOffline(true);
  63 |   await page.getByRole("button", { name: "刷新状态", exact: true }).click();
  64 |   await expect(page.getByText("健康探测未完成，请恢复连接后重新检查。", { exact: true })).toBeVisible();
  65 |   await expect(page.getByText("全部依赖就绪", { exact: true })).toHaveCount(0);
  66 |   await context.setOffline(false);
  67 |   await page.getByRole("button", { name: "重新检查运行状态", exact: true }).click();
  68 |   await expect(page.getByRole("table", { name: "实际依赖探测结果" })).toBeVisible();
  69 |   await page.getByRole("button", { name: "退出登录", exact: true }).click();
  70 |   await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
  71 | });
  72 | 
```