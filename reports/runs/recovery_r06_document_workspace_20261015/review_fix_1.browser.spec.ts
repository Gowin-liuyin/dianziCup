import { expect, test, type Page } from "../../../frontend/node_modules/@playwright/test/index.mjs";
import { documentFixture, detailFixture, documentId, evidenceFixture, historicalRevisionId, revisionId } from "../../../frontend/tests/document-fixture";

async function install(page: Page, options: { historyStatus?: number; delayedEvidence?: boolean; lateDetail?: boolean; currentChanged?: boolean } = {}) {
  const paths: string[] = [];
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  let userNumber = 1;
  let revisionBecameHistorical = false;
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname; paths.push(path + url.search);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") body = { user_id: `independent-fixture-user-${userNumber}`, tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: userNumber, data_mode: "fixture", csrf_token: "b".repeat(64) };
    else if (path === "/v1/auth/login") { userNumber += 1; body = { user_id: `independent-fixture-user-${userNumber}`, csrf_token: "b".repeat(64), expires_at: "2026-10-16T00:00:00Z" }; }
    else if (path === "/v1/auth/logout") body = { status: "logged_out" };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
    else if (path === "/v1/documents") body = { schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" };
    else if (path.endsWith("/revisions")) {
      if (url.searchParams.get("offset") === "1" && options.historyStatus) { status = options.historyStatus; body = { error: { code: "fixture_permission" } }; }
      else body = { schema_version: 2, items: [documentFixture], next_offset: 1, data_mode: "fixture" };
    } else if (path === `/v1/documents/${documentId}`) {
      const old = url.searchParams.get("revision_id") === historicalRevisionId;
      const more = url.searchParams.get("evidence_offset") === "1";
      if (more && options.currentChanged) revisionBecameHistorical = true;
      const firstUser = userNumber === 1;
      if ((more && options.delayedEvidence) || (!old && firstUser && options.lateDetail)) await barrier;
      const newCurrent = options.currentChanged && revisionBecameHistorical && !more;
      body = { ...detailFixture, document: { ...documentFixture, ...(old ? { title: "隔离测试：新选历史版本", revision_id: historicalRevisionId, is_current: false, revision_number: 1 } : {}), ...(options.currentChanged && more ? { is_current: false } : {}), ...(newCurrent ? { title: "隔离测试：最新版本标题", revision_id: "00000000-0000-4000-8000-000000000198", revision_number: 3 } : {}) }, evidence: [{ ...evidenceFixture, ...(old ? { revision_id: historicalRevisionId, quote_text: "隔离测试：新历史原文" } : {}), ...(more ? { span_id: "00000000-0000-4000-8000-000000000199", quote_text: "隔离测试：旧版本晚到原文" } : {}), ...(newCurrent ? { revision_id: "00000000-0000-4000-8000-000000000198", quote_text: "隔离测试：最新版本原文" } : {}), ...(options.lateDetail ? { quote_text: firstUser ? "隔离测试：旧会话晚到原文" : "隔离测试：新会话原文" } : {}) }], evidence_total: 2, next_evidence_offset: more ? null : 1 };
    } else throw new Error(`Unexpected fixture ${path}`);
    await route.fulfill({ status, json: body });
  });
  return { paths, release };
}

for (const status of [403, 404]) {
  test(`Fixture: history ${status} must remove previously loaded title and evidence`, async ({ page }, testInfo) => {
    await install(page, { historyStatus: status }); await page.goto(`/#documents/${documentId}`);
    await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "加载更多历史版本", exact: true }).click();
    await expect(page.getByRole("heading", { name: status === 403 ? "没有资料查看权限" : "资料或版本不可访问", exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`history-${status}-stale.png`), fullPage: true });
    await testInfo.attach("fixture-observation", { body: JSON.stringify(await page.evaluate(() => ({ title: document.querySelector(".document-title")?.textContent, evidence: document.querySelector(".document-evidence")?.textContent, error: document.querySelector(".resource-error")?.textContent }))), contentType: "application/json" });
    await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
  });
}

test("Fixture: changing revision discards an old revision's late evidence response", async ({ page }) => {
  const fixture = await install(page, { delayedEvidence: true }); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click();
  await expect.poll(() => fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
  await page.evaluate((hash) => { window.location.hash = hash; }, `#documents/${documentId}/revision/${historicalRevisionId}`);
  await expect(page.getByText("隔离测试：新历史原文", { exact: true })).toBeVisible(); fixture.release();
  await expect(page.getByText("隔离测试：旧版本晚到原文", { exact: true })).toHaveCount(0);
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
});

test("Fixture: current link reloads current when the first revision becomes historical during evidence pagination", async ({ page }, testInfo) => {
  const fixture = await install(page, { currentChanged: true }); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click();
  await expect(page.getByRole("link", { name: "查看当前版本 →", exact: true })).toBeVisible();
  expect(fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
  const previousCurrentReads = fixture.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length;
  await page.getByRole("link", { name: "查看当前版本 →", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("current-link-stale.png"), fullPage: true });
  await testInfo.attach("fixture-paths-after-click", { body: JSON.stringify(fixture.paths), contentType: "application/json" });
  await expect.poll(() => fixture.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length).toBeGreaterThan(previousCurrentReads);
  await expect(page.getByRole("heading", { name: "隔离测试：最新版本标题", exact: true })).toBeVisible();
});

test("Fixture: real browser cache does not restore a previous session's delayed detail", async ({ page }) => {
  const fixture = await install(page, { lateDetail: true }); await page.goto(`/#documents/${documentId}`);
  await expect(page.getByText("正在取得资料版本与原文…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await page.getByLabel("用户名", { exact: true }).fill("independent-fixture");
  await page.getByLabel("密码", { exact: true }).fill("explicit-fixture-only");
  await page.getByRole("button", { name: "登录工作台", exact: true }).click();
  await expect(page.getByText("independent-fixture-user-2", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "资料库", exact: true }).click(); await page.getByRole("link", { name: documentFixture.title, exact: true }).click();
  await expect(page.getByText("隔离测试：新会话原文", { exact: true })).toBeVisible(); fixture.release();
  await expect(page.getByText("隔离测试：旧会话晚到原文", { exact: true })).toHaveCount(0);
  await page.reload(); await expect(page.getByText("隔离测试：新会话原文", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length }))).toEqual({ local: 0, session: 0 });
});

test("Fixture: 390px long title license notes and raw dates remain plain text without overflow", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 900 }); await page.emulateMedia({ reducedMotion: "no-preference" });
  await install(page);
  const title = "<img src=x onerror=window.independentInjected=true>" + "L".repeat(400);
  const note = "<script>window.independentInjected=true</script>" + "Q".repeat(900);
  const license = "<svg onload=window.independentInjected=true>" + "P".repeat(200);
  await page.route(`**/v1/documents/${documentId}?**`, async (route) => {
    await route.fulfill({ json: { ...detailFixture, document: { ...documentFixture, title, source_name: "S".repeat(300), published_at_raw: "<script>window.independentInjected=true</script>", published_precision: "unknown" }, source_notes: [note], license_identifier: license } });
  });
  await page.goto(`/#documents/${documentId}`);
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
  await expect(page.getByText(note, { exact: true })).toBeVisible();
  await expect(page.getByText(license, { exact: true })).toBeVisible();
  const active = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth > innerWidth,
    injected: Object.hasOwn(window, "independentInjected"),
    htmlNodes: document.querySelectorAll(".document-detail-body script,.document-detail-body img,.document-detail-body svg").length,
    animations: [...document.querySelectorAll(".ambient-topology,.ambient-orbit,.ambient-light")].map((element) => getComputedStyle(element).animationName),
    backdropPointer: getComputedStyle(document.querySelector(".ambient-backdrop")!).pointerEvents,
    textFits: [...document.querySelectorAll(".document-title,.document-source-notes p,.document-metadata dd,.document-evidence blockquote")].every((element) => { const range = document.createRange(); range.selectNodeContents(element); return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= innerWidth); }),
  }));
  expect(active.overflow).toBe(false); expect(active.injected).toBe(false); expect(active.htmlNodes).toBe(0); expect(active.textFits).toBe(true); expect(active.backdropPointer).toBe("none"); expect(active.animations.some((name) => name !== "none")).toBe(true);
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await page.locator(".ambient-topology,.ambient-orbit,.ambient-light").evaluateAll((elements) => elements.every((element) => getComputedStyle(element).animationName === "none"))).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath("long-injection-390.png"), fullPage: true });
  await testInfo.attach("fixture-longtext-observation", { body: JSON.stringify(active), contentType: "application/json" });
});
