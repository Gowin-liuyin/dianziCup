const { chromium } = require("D:/wt/r06-document-live-0a45185/frontend/node_modules/@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

/** Visible-viewport visual QA after real login; no credential screenshots or request interception. */
async function main() {
  const started = new Date().toISOString();
  const saved = JSON.parse(fs.readFileSync(path.join(__dirname, "collection_receipt.json"), "utf8")).first_document;
  const browser = await chromium.launch({ channel: "msedge", headless: true });
  const observations = [];
  try {
    for (const width of [1366, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      await page.goto("http://127.0.0.1:25174/#session");
      await page.getByLabel("用户名", { exact: true }).fill(process.env.DIANZI_E2E_USERNAME + "-r06-doc-viewer");
      await page.getByLabel("密码", { exact: true }).fill(process.env.DIANZI_E2E_PASSWORD);
      await page.getByRole("button", { name: "登录工作台", exact: true }).click();
      await page.getByRole("button", { name: "退出登录", exact: true }).waitFor({ state: "visible" });
      await page.goto("http://127.0.0.1:25174/#documents/" + saved.document_id);
      await page.getByRole("heading", { name: saved.title, exact: true }).waitFor({ state: "visible" });
      if (width === 390) {
        await page.getByLabel("检索关键词", { exact: true }).fill(saved.title);
        await page.getByRole("button", { name: "检索资料", exact: true }).click();
        await page.getByText("本页 1 条 · 真实 / Live", { exact: true }).waitFor({ state: "visible" });
        await page.getByRole("list", { name: "已保存资料列表", exact: true }).getByRole("link", { name: saved.title, exact: true }).click();
        await page.getByRole("heading", { name: saved.title, exact: true }).waitFor({ state: "visible" });
        await page.locator(".document-inspector").scrollIntoViewIfNeeded();
      } else {
        await page.evaluate(() => window.scrollTo(0, 0));
      }
      await page.screenshot({ path: path.join(__dirname, `document-visible-${width}.png`), fullPage: false });
      observations.push({ width, overflow: await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), screenshot: `document-visible-${width}.png`, data_mode: "live", viewport_only: true });
      await context.close();
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(__dirname, "visible_capture_receipt.json"), JSON.stringify({ started_at_utc: started, ended_at_utc: new Date().toISOString(), code_sha: "0a45185ae3ffb73a6d186b98421e26a52f78bfc6", observations, scope: "visual QA only, not another test denominator" }, null, 2));
  console.log("visible desktop/mobile real-data captures saved");
}

main().catch((error) => { console.error(JSON.stringify({ error_type: error.name, details: "withheld" })); process.exitCode = 1; });
