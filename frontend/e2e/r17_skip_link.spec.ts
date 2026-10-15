import { expect, test } from "@playwright/test";

for (const [route, heading] of [["events", "情报工作区"], ["sources", "来源与采集"]]) {
  test(`R17-P2 skip link retains ${route} and focuses main via keyboard`, async ({ page }) => {
    await page.goto(`/#${route}`);
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "刷新状态", exact: true })).toBeEnabled();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "跳到主要内容", exact: true })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main-content")).toBeFocused();
    await expect(page).toHaveURL(new RegExp(`#${route}$`));
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "运行概览", exact: true })).toHaveCount(0);
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "刷新状态", exact: true })).toBeFocused();
  });
}
