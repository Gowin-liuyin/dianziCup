import process from "node:process";
import { expect, test, type Page } from "@playwright/test";

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be injected for the isolated real API run`);
  return value;
}

async function loginWithRealApi(page: Page) {
  await page.goto("/");
  await page.getByLabel("用户名", { exact: true }).fill(requiredEnvironment("DIANZI_E2E_USERNAME"));
  await page.getByLabel("密码", { exact: true }).fill(requiredEnvironment("DIANZI_E2E_PASSWORD"));
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
}

test("T40-C01/C02/C05 real login, reload, cookie/CSRF and revocation", async ({ page }, testInfo) => {
  await page.goto("/");
  await expect(page.getByText("尚未登录", { exact: true })).toBeVisible();
  await expect(page.getByText("已授予权限", { exact: true })).toHaveCount(0);
  await loginWithRealApi(page);
  await expect(page.getByText("真实 / Live", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("table", { name: "实际依赖探测结果" })).toBeVisible();
  const cookies = await page.context().cookies();
  const sessionCookie = cookies.find((cookie) => cookie.name === "ai_intel_session");
  expect(sessionCookie?.httpOnly).toBe(true);
  expect(sessionCookie?.sameSite).toBe("Strict");
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
  await page.reload();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("authenticated-workbench.png"), fullPage: true });
  const logoutResponse = page.waitForResponse((response) => response.url().endsWith("/v1/auth/logout") && response.request().method() === "POST");
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  expect((await logoutResponse).status()).toBe(200);
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
  await expect(page.getByText("已授予权限", { exact: true })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("尚未登录", { exact: true })).toBeVisible();
});

test("T40-C06 real keyboard focus and 390px authenticated layout", async ({ page }, testInfo) => {
  await loginWithRealApi(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "跳到主要内容" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("authenticated-mobile-390.png"), fullPage: true });
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
});

test("T40-C03 real browser offline state and recovery", async ({ page, context }) => {
  await loginWithRealApi(page);
  await context.setOffline(true);
  await page.getByRole("button", { name: "刷新状态", exact: true }).click();
  await expect(page.getByText("健康探测未完成，请恢复连接后重新检查。", { exact: true })).toBeVisible();
  await expect(page.getByText("全部依赖就绪", { exact: true })).toHaveCount(0);
  await context.setOffline(false);
  await page.getByRole("button", { name: "重新检查运行状态", exact: true }).click();
  await expect(page.getByRole("table", { name: "实际依赖探测结果" })).toBeVisible();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeEnabled();
});
