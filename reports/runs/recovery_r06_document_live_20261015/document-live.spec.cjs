const { expect, test } = require("D:/wt/r06-document-live-0a45185/frontend/node_modules/@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

const collected = JSON.parse(fs.readFileSync(path.join(__dirname, "collection_receipt.json"), "utf8"));
const saved = collected.first_document;

async function login(page) {
  await page.goto("/#session");
  await page.getByLabel("用户名", { exact: true }).fill(process.env.DIANZI_E2E_USERNAME + "-r06-doc-viewer");
  await page.getByLabel("密码", { exact: true }).fill(process.env.DIANZI_E2E_PASSWORD);
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByRole("button", { name: "退出登录", exact: true })).toBeVisible();
}

for (const width of [1366, 390]) {
  test(`actual source PG document history evidence and privacy ${width}px`, async ({ page }, testInfo) => {
    const responses = [];
    page.on("response", (response) => {
      const uri = new URL(response.url());
      if (uri.pathname.startsWith("/v1/")) responses.push({ path: uri.pathname + uri.search, status: response.status() });
    });
    await page.setViewportSize({ width, height: 900 });
    await login(page);
    await page.goto("/#documents");
    await expect(page.getByText("本页 20 条 · 真实 / Live", { exact: true })).toBeVisible();
    const list = page.getByRole("list", { name: "已保存资料列表", exact: true });
    const firstPage = await list.getByRole("link").evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    await page.getByRole("button", { name: "下一页资料", exact: true }).click();
    await expect(page.getByText("本页 10 条 · 真实 / Live", { exact: true })).toBeVisible();
    const secondPage = await list.getByRole("link").evaluateAll((links) => links.map((link) => link.getAttribute("href")));
    expect(new Set([...firstPage, ...secondPage]).size).toBe(30);
    await expect(page.getByRole("button", { name: "下一页资料", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: "回到第一页", exact: true }).click();
    await expect(list.getByRole("link", { name: saved.title, exact: true })).toBeVisible();
    await list.getByRole("link", { name: saved.title, exact: true }).click();
    await expect(page.getByRole("heading", { name: saved.title, exact: true })).toBeVisible();
    await expect(page.locator(".document-evidence blockquote").first()).toHaveText(collected.first_detail.evidence[0].quote_text);
    await expect(page.getByLabel("原文修订版本", { exact: true })).toHaveValue(saved.revision_id);
    await page.locator(".document-evidence summary").first().click();
    await expect(page.getByText(collected.first_detail.evidence[0].quote_sha256, { exact: true })).toBeVisible();
    const source = page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true });
    await expect(source).toHaveAttribute("href", saved.canonical_uri);
    await expect(page.getByText("正文覆盖范围未知，不能认定已保存全文。", { exact: true })).toBeVisible();
    await expect(page.getByTestId("ambient-backdrop")).toHaveCSS("pointer-events", "none");
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "topology-drift");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.getByTestId("ambient-motion")).toHaveCSS("animation-name", "none");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath(`document-real-${width}.png`), fullPage: true });
    await page.reload();
    await expect(page.locator(".document-evidence blockquote").first()).toHaveText(collected.first_detail.evidence[0].quote_text);
    await page.getByLabel("原文修订版本", { exact: true }).selectOption(saved.revision_id);
    await expect(page.locator(".document-evidence blockquote").first()).toHaveText(collected.first_detail.evidence[0].quote_text);
    await page.getByLabel("资料类型", { exact: true }).selectOption("paper");
    await page.getByRole("button", { name: "检索资料", exact: true }).click();
    await expect(page.getByRole("heading", { name: "本次查询没有资料记录", exact: true })).toBeVisible();
    await page.goto("/#session");
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
    await page.goto(`/#documents/${saved.document_id}`);
    await expect(page.getByRole("heading", { name: "登录后核查资料", exact: true })).toBeVisible();
    await expect(page.locator(".document-evidence blockquote")).toHaveCount(0);
    await testInfo.attach("real-document-observation", { body: JSON.stringify({ code_sha: collected.code_sha, data_mode: "live", width, real_document_count: 30, unique_page_records: 30, fixed_revision_id: saved.revision_id, responses, source_uri: saved.canonical_uri, request_interception: false, model_calls: 0 }), contentType: "application/json" });
  });
}

test("actual saved source link opens original public publisher page", async ({ page }, testInfo) => {
  await login(page);
  await page.goto(`/#documents/${saved.document_id}/revision/${saved.revision_id}`);
  const source = page.getByRole("link", { name: "打开此版本来源地址 ↗", exact: true });
  const opened = page.waitForEvent("popup");
  await source.click();
  const popup = await opened;
  await popup.waitForLoadState("domcontentloaded", { timeout: 20000 });
  expect(popup.url()).toBe(saved.canonical_uri);
  expect(await popup.title()).not.toMatch(/ERR_|not found|404/i);
  await testInfo.attach("original-source-opened", { body: JSON.stringify({ url: popup.url(), title: await popup.title(), original_saved_uri: saved.canonical_uri }), contentType: "application/json" });
  await popup.close();
});
