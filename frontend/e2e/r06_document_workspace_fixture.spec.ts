import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { detailFixture, documentFixture, documentId, evidenceFixture, historicalRevisionId, revisionId } from "../tests/document-fixture";

/** 所有/v1请求仅在本浏览器测试内拦截。此夹具不进入产品代码且不计live。 */
async function installFixture(page: Page, options: { listStatus?: number; metadataOnly?: boolean; slow?: boolean; empty?: boolean; expireDetail?: boolean } = {}) {
  const paths: string[] = [];
  const csrf = randomBytes(32).toString("hex");
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const query = new URL(route.request().url()).search;
    paths.push(path + query);
    let status = 200;
    let body: unknown;
    if (path === "/v1/auth/me") body = { user_id: "isolated-document-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
    else if (path === "/v1/auth/logout") body = { status: "logged_out" };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated fixture", dependencies: {} };
    else if (path === "/v1/documents") {
      if (options.slow) await barrier;
      if (options.listStatus) { status = options.listStatus; body = { error: { code: "fixture_failure" } }; }
      else body = { schema_version: 2, items: options.empty ? [] : [{ ...documentFixture, title: query.includes("cursor=") ? "隔离测试：后续政策资料" : documentFixture.title }], next_cursor: query.includes("cursor=") ? null : "opaque-fixture", data_mode: "fixture" };
    } else if (path === `/v1/documents/${documentId}/revisions`) body = { schema_version: 2, items: query.includes("offset=1") ? [{ ...documentFixture, title: "隔离测试：历史研究标题", revision_id: historicalRevisionId, revision_number: 1, is_current: false }] : [documentFixture], next_offset: query.includes("offset=1") ? null : 1, data_mode: "fixture" };
    else if (path === `/v1/documents/${documentId}`) {
      const historical = query.includes(historicalRevisionId);
      const extra = query.includes("evidence_offset=1");
      body = { ...detailFixture, document: { ...documentFixture, ...(historical ? { revision_id: historicalRevisionId, revision_number: 1, is_current: false, title: "隔离测试：历史研究标题" } : {}), ...(options.metadataOnly ? { content_coverage: "metadata" } : {}) }, evidence: options.metadataOnly ? [] : [{ ...evidenceFixture, ...(historical ? { revision_id: historicalRevisionId, quote_text: "隔离测试历史原文：<script>window.fixtureInjected=true</script>" } : {}), ...(extra ? { span_id: "00000000-0000-4000-8000-000000000106", quote_text: "隔离测试后续原文" } : {}) }], evidence_total: options.metadataOnly ? 0 : 2, next_evidence_offset: options.metadataOnly || extra ? null : 1 };
      if (options.expireDetail) { status = 401; body = { error: { code: "unauthenticated" } }; }
    } else throw new Error(`Unexpected isolated fixture path ${path}`);
    await route.fulfill({ status, json: body });
  });
  return { paths, release };
}

for (const width of [1366, 390]) {
  test(`document isolated Fixture ${width}px filter history evidence keyboard layout`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
    const fixture = await installFixture(page); await page.goto("/#documents");
    await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
    await expect(page.getByText("本页 1 条 · 合成 / Fixture", { exact: true })).toBeVisible();
    await expect(page.getByText("仅日期 · 时刻未知", { exact: true })).toBeVisible();
    await page.getByLabel("资料类型", { exact: true }).selectOption("paper"); await page.getByLabel("检索关键词", { exact: true }).fill("模型");
    await page.getByRole("button", { name: "检索资料", exact: true }).focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
    await page.getByRole("link", { name: documentFixture.title, exact: true }).focus(); await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: documentFixture.title, exact: true })).toBeVisible();
    await expect(page.locator(".document-inspector")).toBeFocused();
    await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
    await expect(page.locator(".document-evidence img, .document-evidence script")).toHaveCount(0);
    await page.locator(".document-evidence summary").first().focus(); await page.keyboard.press("Space");
    await expect(page.getByText("片段哈希", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "加载更多原文片段", exact: true }).click(); await expect(page.getByText("隔离测试后续原文", { exact: true })).toBeVisible();
    expect(fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
    await page.getByRole("button", { name: "加载更多历史版本", exact: true }).click();
    await expect(page.getByRole("option", { name: "修订 1 · 历史 · 隔离测试：历史研究标题", exact: true })).toHaveCount(1);
    await page.getByLabel("原文修订版本", { exact: true }).selectOption(historicalRevisionId);
    await expect(page.getByRole("heading", { name: "隔离测试：历史研究标题", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "查看当前版本 →", exact: true })).toBeVisible();
    await expect(page.getByText("隔离测试后续原文", { exact: true })).toHaveCount(0);
    await expect(page.locator(".document-evidence script")).toHaveCount(0);
    const observation = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > window.innerWidth, backgrounds: [...document.querySelectorAll(".ambient-backdrop")].map((element) => getComputedStyle(element).pointerEvents), animations: [...document.querySelectorAll(".ambient-topology,.ambient-orbit,.ambient-light")].map((element) => getComputedStyle(element).animationName), injected: Object.hasOwn(window, "fixtureInjected"), textVisible: [...document.querySelectorAll(".document-title,.document-metadata dd,.document-boundary,.document-evidence blockquote")].every((element) => { const range = document.createRange(); range.selectNodeContents(element); return [...range.getClientRects()].every((bounds) => bounds.left >= 0 && bounds.right <= window.innerWidth); }) }));
    expect(observation.overflow).toBe(false); expect(observation.textVisible).toBe(true); expect(observation.injected).toBe(false); expect(observation.backgrounds).toEqual(["none"]); expect(observation.animations.every((name) => name === "none")).toBe(true);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: testInfo.outputPath(`document-isolated-fixture-${width}.png`), fullPage: true });
    await testInfo.attach("document-fixture-observation", { body: JSON.stringify({ ...observation, paths: fixture.paths, mode: "isolated fixture only" }), contentType: "application/json" });
    await page.getByRole("link", { name: "关闭详情", exact: true }).click();
    await page.getByRole("button", { name: "下一页资料", exact: true }).click(); await expect(page.getByRole("link", { name: "隔离测试：后续政策资料", exact: true })).toBeVisible();
    expect(fixture.paths.some((path) => path.includes("document_kind=paper&cursor=opaque-fixture"))).toBe(true);
  });
}
test("document isolated loading empty metadata and HTTP error states remain separate", async ({ page }) => {
  const fixture = await installFixture(page, { slow: true, empty: true }); await page.goto("/#documents"); await expect(page.getByText("正在查询授权范围内的资料…", { exact: true })).toBeVisible(); fixture.release();
  await expect(page.getByRole("heading", { name: "本次查询没有资料记录", exact: true })).toBeVisible();
  await page.unrouteAll({ behavior: "wait" }); await installFixture(page, { metadataOnly: true }); await page.reload(); await page.getByRole("link", { name: documentFixture.title, exact: true }).click();
  await expect(page.getByRole("heading", { name: "没有可定位的原文片段", exact: true })).toBeVisible();
  for (const [status, title] of [[403, "没有资料查看权限"], [503, "资料依赖暂不可用"], [404, "资料服务待接通"]] as const) {
    await page.unrouteAll({ behavior: "wait" }); await installFixture(page, { listStatus: status }); await page.goto("/#documents"); await page.reload();
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible(); await expect(page.getByText("本页 0 条 · 合成 / Fixture", { exact: true })).toHaveCount(0); await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toHaveCount(0);
  }
});

test("document isolated 401 and late logout response never restore private UI", async ({ page }) => {
  let fixture = await installFixture(page, { expireDetail: true }); await page.goto("/#documents");
  await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toBeVisible();
  const initialMe = fixture.paths.filter((path) => path === "/v1/auth/me").length;
  await page.getByRole("link", { name: documentFixture.title, exact: true }).click();
  await expect(page.getByText("会话已失效，请重新登录。", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toHaveCount(0);
  expect(fixture.paths.filter((path) => path === "/v1/auth/me")).toHaveLength(initialMe);
  await page.unrouteAll({ behavior: "wait" }); fixture = await installFixture(page, { slow: true }); await page.reload();
  await expect(page.getByText("正在查询授权范围内的资料…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await expect(page.getByRole("button", { name: "登录工作台", exact: true })).toBeVisible();
  fixture.release(); await page.getByRole("link", { name: "资料库", exact: true }).click();
  await expect(page.getByRole("heading", { name: "登录后核查资料", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: documentFixture.title, exact: true })).toHaveCount(0);
});
