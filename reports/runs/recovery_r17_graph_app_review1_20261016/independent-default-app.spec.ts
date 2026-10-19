import { randomBytes } from "node:crypto";
import { test, expect, type Page } from "../../../frontend/node_modules/@playwright/test/index.mjs";
import { graphFixture, graphFixtureEventId, fixtureGraphId } from "../../../frontend/src/features/graph/graph.fixture";
import { fixtureEventId, eventDetailFixture, historicalEvidenceFixture, fixtureOldEvidenceId, fixtureOldRevisionId } from "../../../frontend/src/features/events/event-detail.fixture";

async function installIndependentFixture(page: Page) {
  const snapshot = graphFixture("r10-graph-1.2.0");
  snapshot.event_id = fixtureEventId;
  snapshot.nodes = snapshot.nodes.map((node) => node.id === graphFixtureEventId ? { ...node, id: fixtureEventId, label: "独立审查合成 Fixture · 当前事件" } : node);
  snapshot.edges = snapshot.edges.map((edge) => ({ ...edge,
    subject_id: edge.subject_id === graphFixtureEventId ? fixtureEventId : edge.subject_id,
    object_id: edge.object_id === graphFixtureEventId ? fixtureEventId : edge.object_id,
    evidence_span_ids: [fixtureOldEvidenceId], source_revision_ids: [fixtureGraphId(90), fixtureOldRevisionId] }));
  const api = { status: 200, body: snapshot as unknown, requests: [] as { method: string; path: string; search: string }[] };
  await page.route("**/v1/**", async (route) => {
    const url = new URL(route.request().url());
    api.requests.push({ method: route.request().method(), path: url.pathname, search: url.search });
    let body: unknown;
    let status = 200;
    if (url.pathname === "/v1/auth/me") body = { user_id: "independent-graph-app-fixture-user", tenant_id: "independent-graph-app-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
    else if (url.pathname === "/v1/health/live") body = { status: "live" };
    else if (url.pathname === "/v1/health/ready") body = { status: "ready", reason: "independent isolated fixture only", dependencies: {} };
    else if (url.pathname === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
    else if (url.pathname === `/v1/events/${fixtureEventId}`) body = eventDetailFixture;
    else if (url.pathname === `/v1/events/${fixtureEventId}/graph`) { expect(url.search).toBe("?max_nodes=200&max_edges=400"); body = api.body; status = api.status; }
    else if (url.pathname === `/v1/evidence/${fixtureOldEvidenceId}`) { expect(url.search).toBe(""); body = historicalEvidenceFixture; }
    else throw new Error(`Unexpected independent fixture route: ${url.pathname}`);
    await route.fulfill({ status, json: status === 200 ? body : { error: { code: "not_found", retryable: false } } });
  });
  return { api, snapshot };
}

test("independent built default App fixture: native mouse choice original GET return and 404 clears", async ({ page }, info) => {
  const { api } = await installIndependentFixture(page);
  await page.goto(`/#events/${fixtureEventId}`);
  await page.getByRole("link", { name: "查看证据关系图", exact: true }).click();
  await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  await page.locator(".graph-canvas").scrollIntoViewIfNeeded();
  const pointer = await page.locator(".graph-canvas").evaluate((canvas) => {
    const curve = canvas.querySelectorAll(".graph-edge-line")[1];
    if (!(curve instanceof SVGPathElement)) throw new Error("Missing native SVG curve");
    const point = curve.getPointAtLength(curve.getTotalLength() / 2);
    const first = curve.getScreenCTM();
    if (!first) throw new Error("Missing SVG transform");
    const screen = new DOMPoint(point.x, point.y).matrixTransform(first);
    const bounds = canvas.getBoundingClientRect();
    canvas.scrollLeft += screen.x - bounds.left - bounds.width / 2;
    canvas.scrollTop += screen.y - bounds.top - bounds.height / 2;
    const scrolled = curve.getScreenCTM();
    if (!scrolled) throw new Error("Missing scrolled transform");
    const target = new DOMPoint(point.x, point.y).matrixTransform(scrolled);
    return { x: target.x, y: target.y };
  });
  await page.mouse.click(pointer.x, pointer.y);
  const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
  await expect(chooser).toBeVisible();
  const selected = chooser.locator("button").filter({ has: page.locator("code", { hasText: fixtureGraphId(11) }) });
  await selected.scrollIntoViewIfNeeded();
  const bounds = await selected.boundingBox();
  if (!bounds) throw new Error("Missing chooser mouse bounds");
  await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await expect(page.locator(".graph-edge[aria-pressed=true]")).toHaveAttribute("data-edge-id", fixtureGraphId(11));
  const inspector = page.getByRole("complementary", { name: "关系检视", exact: true });
  await expect(inspector.getByRole("link", { name: /原文片段/ })).toHaveAttribute("href", `#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
  await inspector.getByRole("link", { name: /原文片段/ }).click();
  await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  await page.reload();
  await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
  await page.goBack();
  await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  api.status = 404;
  await page.getByRole("button", { name: "重新读取", exact: true }).click();
  await expect(page.getByRole("heading", { name: "事件不可访问", exact: true })).toBeVisible();
  await expect(page.locator(".graph-scene,.graph-inspector,.graph-edge-choices,blockquote")).toHaveCount(0);
  expect(await page.getByText("暂无风险", { exact: true }).count()).toBe(0);
  expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
  await page.screenshot({ path: info.outputPath("independent-built-default-404.png"), fullPage: true });
  await info.attach("independent-native-and-404", { body: JSON.stringify({ pointer, expected_edge: fixtureGraphId(11), requests: api.requests }), contentType: "application/json" });
});

test("independent built default App fixture: exact historical union and unknown schema or edge rule rejection", async ({ page }, info) => {
  const { api, snapshot } = await installIndependentFixture(page);
  for (const rule_version of ["r10-graph-1.0.0", "r10-graph-1.1.0", "r10-graph-1.2.0"]) {
    api.body = { ...snapshot, rule_version, edges: snapshot.edges.map((edge) => ({ ...edge, rule_or_model_version: rule_version })) };
    await page.goto(`/#graph/${fixtureEventId}`);
    await page.reload();
    await expect(page.locator(".graph-edge-line")).toHaveCount(6);
    await expect(page.locator(".graph-snapshot-provenance")).toContainText(rule_version);
  }
  for (const body of [{ ...snapshot, schema_version: 2 }, { ...snapshot, rule_version: "r10-graph-1.3.0" }, { ...snapshot, edges: [{ ...snapshot.edges[0], rule_or_model_version: "r10-graph-1.3.0" }] }]) {
    api.body = body;
    await page.reload();
    await expect(page.getByRole("heading", { name: "图协议不匹配", exact: true })).toBeVisible();
    await expect(page.locator(".graph-scene,.graph-inspector")).toHaveCount(0);
  }
  await info.attach("independent-protocol-requests", { body: JSON.stringify(api.requests), contentType: "application/json" });
});
