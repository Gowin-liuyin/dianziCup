import { expect, test } from "../../../frontend/node_modules/@playwright/test/index.mjs";

test("Isolated HTTP fixture: Edge native cache does not restore previous session documents", async ({ page }, testInfo) => {
  const observedHeaders: string[] = [];
  page.on("response", (response) => { if (new URL(response.url()).pathname === "/v1/documents") observedHeaders.push(response.headers()["cache-control"] ?? ""); });
  await page.goto("/#documents");
  await expect(page.getByRole("link", { name: "隔离测试：会话1授权资料", exact: true })).toBeVisible();
  const initial = await page.evaluate(async () => (await fetch("/v1/fixture-probe", { cache: "no-store" })).json());
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await page.getByLabel("用户名", { exact: true }).fill("native-cache-fixture");
  await page.getByLabel("密码", { exact: true }).fill("explicit-fixture-only");
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByText("native-cache-fixture-user-2", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "资料库", exact: true }).click();
  await expect(page.getByRole("link", { name: "隔离测试：会话2授权资料", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "隔离测试：会话1授权资料", exact: true })).toHaveCount(0);
  const final = await page.evaluate(async () => (await fetch("/v1/fixture-probe", { cache: "no-store" })).json());
  expect(final.documentReads).toBeGreaterThan(initial.documentReads);
  expect(observedHeaders.length).toBeGreaterThan(1); expect(observedHeaders.every((value) => value === "private, max-age=600")).toBe(true);
  await testInfo.attach("native-cache-fixture-observation", { body: JSON.stringify({ initial, final, observedHeaders, pageRouting: false, dataMode: "isolated fixture only" }), contentType: "application/json" });
});
