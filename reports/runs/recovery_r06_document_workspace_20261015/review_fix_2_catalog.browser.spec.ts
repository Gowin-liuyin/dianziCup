import { expect, test } from "../../../frontend/node_modules/@playwright/test/index.mjs";
import { documentFixture, detailFixture, documentId, evidenceFixture } from "../../../frontend/tests/document-fixture";
test("Isolated fixture: catalog READ_PUBLIC 403 blocks delayed detail and history", async ({ page }, testInfo) => {
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  const paths: string[] = [];
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url()); const path = url.pathname; paths.push(path + url.search);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") body = { user_id: "isolated-catalog-browser-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "e".repeat(64) };
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "fixture", dependencies: {} };
    else if (path === "/v1/documents") { status = 403; body = { error: { code: "forbidden" } }; }
    else if (path.endsWith("/revisions")) { await barrier; body = { schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }; }
    else if (path === `/v1/documents/${documentId}`) { await barrier; body = detailFixture; }
    else throw new Error(`Unexpected fixture ${path}`);
    await route.fulfill({ status, json: body });
  });
  await page.goto(`/#documents/${documentId}`);
  await expect(page.getByRole("heading", { name: "没有资料查看权限", exact: true })).toBeVisible();
  release();
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0)); await page.screenshot({ path: testInfo.outputPath("catalog-403-late-body.png"), fullPage: true });
  await testInfo.attach("fixture-response-order", { body: JSON.stringify({ paths, catalogStatus: 403, delayedResources: ["detail", "history"], mode: "isolated fixture only" }), contentType: "application/json" });
  await expect(page.getByText(evidenceFixture.quote_text, { exact: true })).toHaveCount(0);
});
