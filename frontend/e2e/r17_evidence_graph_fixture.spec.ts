import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { graphFixture, graphFixtureEventId, graphFixtureEvidenceId, graphFixtureRevisionId, fixtureGraphId } from "../src/features/graph/graph.fixture";
import { graphNodeKinds, graphRelationKinds, type GraphSnapshot } from "../src/features/graph/graph-contracts";

const fixtureUrl = "/e2e/graph-fixture/index.html";
async function isolateApi(page: Page, snapshot = graphFixture("r10-graph-1.1.0")) {
  const state: { graphStatus: number; authStatus: number; requests: string[] } = { graphStatus: 200, authStatus: 200, requests: [] };
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname; state.requests.push(path);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") {
      status = state.authStatus; body = status === 200 ? { user_id: "isolated-graph-fixture-user", tenant_id: "isolated-graph-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") } : { error: { code: "session_expired", retryable: false } };
    } else if (path === `/v1/events/${graphFixtureEventId}/graph`) { status = state.graphStatus; body = status === 200 ? snapshot : { error: { code: "graph_problem", retryable: status >= 500 }, detail: "isolated-fixture-private-error-not-for-ui" }; }
    else if (path === "/v1/events") body = { schema_version: 2, items: [], next_cursor: null, data_mode: "fixture" };
    else if (path === `/v1/events/${graphFixtureEventId}`) body = { schema_version: 2, event: { event_id: graphFixtureEventId, event_type: "advisory", title: "合成证据图事件", external_ids: [], primary_product_ids: [], first_seen_at: "2026-10-16T01:00:00Z", status: "active", source_count: 1, latest_revision_id: graphFixtureRevisionId, freshness: "current" }, dimensions: [], revisions: [], claims: [], data_mode: "fixture" };
    else if (path === `/v1/evidence/${graphFixtureEvidenceId}`) body = { schema_version: 2, span_id: graphFixtureEvidenceId, revision_id: graphFixtureRevisionId, block_id: null, start_offset: 0, end_offset: 12, quote_text: "合成证据：保存修订的定位片段。", quote_sha256: "b".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };
    else throw new Error(`Unexpected isolated graph route: ${path}`);
    await route.fulfill({ status, json: body });
  });
  return state;
}

for (const width of [1366, 390]) {
  test(`R17 Edge fixture ${width}: graph keyboard, complete evidence route and reduced motion`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
    const fixture = await isolateApi(page); await page.goto(fixtureUrl); await expect(page.getByText("6 节点 / 6 支持关系")).toBeVisible();
    await expect(page.getByText("合成 / Fixture", { exact: true })).toBeVisible(); await expect(page.getByText("真实 / Live", { exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const controls = await page.locator(".graph-explorer button:visible, .graph-heading-actions a:visible").evaluateAll((elements) => elements.map((element) => ({ text: element.textContent, height: element.getBoundingClientRect().height })));
    for (const control of controls) expect(control.height).toBeGreaterThanOrEqual(width === 390 ? 44 : 40);
    expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
    expect(await page.locator(".graph-edge-line").first().evaluate((element) => getComputedStyle(element).transitionDuration)).toBe("0s");
    await page.screenshot({ path: info.outputPath(`graph-fixture-${width}.png`), fullPage: false });
    const relation = page.getByRole("button", { name: "图关系 2：影响组件版本", exact: true });
    await relation.focus(); await page.keyboard.press("Enter"); await expect(relation).toHaveAttribute("aria-pressed", "true");
    const inspector = page.getByRole("complementary", { name: "关系检视", exact: true });
    await expect(inspector.getByText("r10-graph-1.1.0", { exact: true })).toBeVisible();
    await inspector.getByText("支持断言 · 1", { exact: true }).click(); await expect(inspector.getByText(fixtureGraphId(32), { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "放大图", exact: true }).click(); await expect(page.getByLabel("图缩放比例")).toHaveText("120%");
    await page.getByRole("button", { name: "向右平移", exact: true }).click(); expect(await page.locator(".graph-canvas").evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    await page.getByRole("button", { name: "重置视图", exact: true }).click(); await expect(page.getByLabel("图缩放比例")).toHaveText("100%");
    expect(await page.locator(".graph-canvas").evaluate((element) => element.scrollLeft)).toBe(0);
    const evidence = inspector.getByRole("link", { name: /^原文片段 \[1\]/ }); await evidence.focus(); await page.keyboard.press("Enter");
    await expect(page.locator("blockquote")).toHaveText("合成证据：保存修订的定位片段。");
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByText(graphFixtureRevisionId, { exact: true })).toBeVisible();
    expect(fixture.requests).toContain(`/v1/evidence/${graphFixtureEvidenceId}`);
    await page.screenshot({ path: info.outputPath(`graph-evidence-fixture-${width}.png`), fullPage: false });
    await info.attach("control-metrics", { body: JSON.stringify({ width, controls, requests: fixture.requests }, null, 2), contentType: "application/json" });
  });
}
for (const [status, title] of [[401, "登录后查看证据图"], [403, "没有查看权限"], [404, "事件不可访问"], [409, "图快照已过期"], [503, "图服务暂不可用"]] as const) {
  test(`R17 Edge fixture HTTP ${status} cannot become an empty success`, async ({ page }, info) => {
    await page.setViewportSize({ width: 390, height: 844 }); const state = await isolateApi(page); state.graphStatus = status;
    await page.goto(fixtureUrl); await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(page.locator(".graph-scene")).toHaveCount(0); await expect(page.getByText("isolated-fixture-private-error-not-for-ui", { exact: true })).toHaveCount(0);
    if (status === 503 || status === 409) { state.graphStatus = 200; await page.getByRole("button", { name: "重新取得图", exact: true }).click(); await expect(page.getByText("6 节点 / 6 支持关系")).toBeVisible(); }
    await page.screenshot({ path: info.outputPath(`http-${status}-fixture-390.png`), fullPage: false });
  });
}
test("R17 Edge fixture root-only unknown, truncation and view filters", async ({ page }, info) => {
  const snapshot = graphFixture("r10-graph-1.1.0"); snapshot.nodes = snapshot.nodes.slice(0, 1); snapshot.edges = []; snapshot.truncated = true;
  snapshot.gaps = graphRelationKinds.map((relation_type) => ({ relation_type, status: "unknown", reason: "truncated" }));
  await isolateApi(page, snapshot); await page.goto(fixtureUrl); await expect(page.getByRole("heading", { name: "目前只有事件上下文" })).toBeVisible();
  await expect(page.getByText("关系缺口 · 6 项未知")).toBeVisible(); await expect(page.getByText("暂无风险")).toHaveCount(0);
  await page.screenshot({ path: info.outputPath("root-only-unknown-fixture.png"), fullPage: false });
});
test("R17 Edge fixture clears graph after new request and session revocation", async ({ page }) => {
  const state = await isolateApi(page); await page.goto(fixtureUrl); await expect(page.getByText("6 节点 / 6 支持关系")).toBeVisible();
  state.graphStatus = 403; await page.getByRole("button", { name: "重新读取", exact: true }).click(); await expect(page.getByRole("heading", { name: "没有查看权限" })).toBeVisible(); await expect(page.locator(".graph-scene")).toHaveCount(0);
  state.authStatus = 401; await page.getByRole("button", { name: "测试重新验证会话", exact: true }).click(); await expect(page.getByRole("heading", { name: "登录后查看证据图" })).toBeVisible(); await expect(page.locator(".graph-scene")).toHaveCount(0);
});
test("R17 Edge fixture 200 nodes / 400 edges remains operable; synthetic timing only", async ({ page }, info) => {
  const snapshot: GraphSnapshot = graphFixture("r10-graph-1.1.0"); const root = snapshot.nodes[0]; const firstEdge = snapshot.edges[0]; if (!root || !firstEdge) throw new Error("fixture root missing");
  snapshot.nodes = [root, ...Array.from({ length: 199 }, (_, index) => {
    const kind = graphNodeKinds[(index % 5) + 1]; if (!kind) throw new Error("fixture kind missing");
    return { id: fixtureGraphId(index + 100), kind, label: `合成大图 · ${kind} · ${index} · 完整标签核查`, scope: root.scope };
  })];
  snapshot.edges = Array.from({ length: 400 }, (_, index) => {
    const target = snapshot.nodes[(index % 199) + 1]; const relation = graphRelationKinds[index % 6]; if (!target || !relation) throw new Error("fixture target missing");
    return { ...firstEdge, id: fixtureGraphId(index + 1000), object_id: target.id, relation_type: relation };
  });
  await isolateApi(page, snapshot); const start = performance.now(); await page.goto(fixtureUrl); await expect(page.getByText("200 节点 / 400 支持关系")).toBeVisible(); const renderMilliseconds = performance.now() - start;
  await expect(page.locator(".graph-node")).toHaveCount(200); await expect(page.locator(".graph-edge")).toHaveCount(400);
  expect(await page.locator(".graph-node-relations").evaluate((element) => element.getBoundingClientRect().height)).toBeLessThanOrEqual(330);
  const interactionStart = performance.now(); await page.getByRole("button", { name: "放大图", exact: true }).click(); await expect(page.getByLabel("图缩放比例")).toHaveText("120%");
  await page.getByRole("checkbox", { name: "论文", exact: true }).click(); await expect(page.locator(".graph-node")).toHaveCount(160);
  const interactionMilliseconds = performance.now() - interactionStart;
  await info.attach("synthetic-bounded-timing", { body: JSON.stringify({ data_kind: "synthetic", nodes: 200, edges: 400, renderMilliseconds, interactionMilliseconds, scope: "one isolated Edge UI run, no backend/live throughput claim" }, null, 2), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("bounded-200-400-fixture.png"), fullPage: false });
});
