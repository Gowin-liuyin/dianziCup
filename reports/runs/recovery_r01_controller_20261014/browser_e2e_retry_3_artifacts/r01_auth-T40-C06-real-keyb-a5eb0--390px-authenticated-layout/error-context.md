# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r01_auth.spec.ts >> T40-C06 real keyboard focus and 390px authenticated layout
- Location: e2e\r01_auth.spec.ts:42:1

# Error details

```
Error: expect(locator).toBeFocused() failed

Locator:  getByRole('button', { name: '刷新状态', exact: true })
Expected: focused
Received: inactive
Timeout:  10000ms

Call log:
  - Expect "toBeFocused" getByRole('button', { name: '刷新状态', exact: true }) with timeout 10000ms
  - waiting for getByRole('button', { name: '刷新状态', exact: true })
    - locator resolved to <button disabled class="button secondary refresh-button">…</button>
    22 × unexpected value "inactive"
       - locator resolved to <button class="button secondary refresh-button">…</button>
    - unexpected value "inactive"

```

```yaml
- button "刷新状态"
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
  15 |   await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
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
> 50 |   await expect(page.getByRole("button", { name: "刷新状态", exact: true })).toBeFocused();
     |                                                                         ^ Error: expect(locator).toBeFocused() failed
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