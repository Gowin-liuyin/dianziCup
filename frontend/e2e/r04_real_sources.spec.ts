import process from "node:process";
import { expect, test } from "@playwright/test";

function credential(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error("isolated real browser identity is not configured");
  return value;
}

for (const width of [1366, 390]) {
  test(`R04 real collected source list to evidence and reload ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.goto("/#session");
    await page.getByLabel("用户名", { exact: true }).fill(credential("DIANZI_E2E_USERNAME"));
    await page.getByLabel("密码", { exact: true }).fill(credential("DIANZI_E2E_PASSWORD"));
    await page.getByRole("button", { name: "登录工作台", exact: true }).click();
    await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
    await page.goto("/#events");
    const table = page.getByRole("table", { name: "情报事件列表", exact: true });
    const record = table.getByRole("link").first();
    await expect(record).toBeVisible();
    await expect(page.getByText(/本页 [1-9][0-9]* 条 · 真实 \/ Live/)).toBeVisible();
    const href = await record.getAttribute("href");
    expect(href).toMatch(/^#events\/[a-f0-9-]{36}$/);
    await record.click();
    await expect(page.getByRole("heading", { name: "事件详情", exact: true })).toBeVisible();
    await expect(page.locator(".dimension-row")).toHaveCount(9);
    await page.getByRole("link", { name: "原文片段 [1]", exact: true }).first().click();
    await expect(page.locator(".evidence-body blockquote")).not.toBeEmpty();
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true })).toBeFocused();
    await expect(page.getByRole("link", { name: "打开来源地址 ↗", exact: true })).toHaveAttribute("href", /^https:\/\/(nvd\.nist\.gov|github\.com)\//);
    await page.reload();
    await expect(page.locator(".evidence-body blockquote")).not.toBeEmpty();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const backdrop = page.getByTestId("ambient-backdrop");
    await expect(backdrop).toHaveCSS("pointer-events", "none");
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "topology-drift");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "none");
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`real-collected-workbench-${width}.png`), fullPage: true });
    await page.goto("/#session");
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
  });
}
