import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { graphFixture, graphFixtureEventId, fixtureGraphId } from "../src/features/graph/graph.fixture";
import { graphRelationKinds, type GraphSnapshot } from "../src/features/graph/graph-contracts";
import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, historicalEvidenceFixture } from "../src/features/events/event-detail.fixture";

function appGraphFixture(): GraphSnapshot {
  const snapshot = graphFixture("r10-graph-1.2.0");
  snapshot.event_id = fixtureEventId;
  snapshot.nodes = snapshot.nodes.map((node) => node.id === graphFixtureEventId ? { ...node, id: fixtureEventId, label: "合成 Fixture · App 事件" } : node);
  snapshot.edges = snapshot.edges.map((edge) => ({ ...edge, subject_id: edge.subject_id === graphFixtureEventId ? fixtureEventId : edge.subject_id, object_id: edge.object_id === graphFixtureEventId ? fixtureEventId : edge.object_id, evidence_span_ids: [fixtureOldEvidenceId], source_revision_ids: [fixtureOldRevisionId, fixtureGraphId(90)] }));
  return snapshot;
}

async function installFixture(page: Page) {
  const api = { graph: appGraphFixture(), graphStatus: 200, authStatus: 200, authenticated: true, tenant: "graph-app-fixture-a", dataMode: "fixture", hold: false, release: () => {}, requests: [] as string[] };
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    api.requests.push(`${route.request().method()} ${path}`);
    let body: unknown; let status = 200;
    if (path === "/v1/auth/me") {
      status = api.authenticated ? api.authStatus : 401;
      body = status === 200 ? { user_id: "graph-app-isolated-user", tenant_id: api.tenant, role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: api.dataMode, csrf_token: randomBytes(32).toString("hex") } : { error: { code: "session_expired", retryable: false } };
    } else if (path === "/v1/auth/logout") { api.authenticated = false; await route.fulfill({ status: 204 }); return; }
    else if (path === "/v1/health/live") body = { status: "live" };
    else if (path === "/v1/health/ready") body = { status: "ready", reason: "isolated frontend fixture only", dependencies: {} };
    else if (path === "/v1/events") body = { schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" };
    else if (path === `/v1/events/${fixtureEventId}`) body = eventDetailFixture;
    else if (path === `/v1/evidence/${fixtureOldEvidenceId}`) { expect(new URL(route.request().url()).search).toBe(""); body = historicalEvidenceFixture; }
    else if (path === `/v1/events/${fixtureEventId}/graph`) {
      expect(new URL(route.request().url()).search).toBe("?max_nodes=200&max_edges=400");
      status = api.graphStatus; body = status === 200 ? structuredClone(api.graph) : { error: { code: "isolated_graph_problem", retryable: status >= 500 || status === 409 } };
      if (api.hold) await new Promise<void>((resolve) => { api.release = resolve; });
    } else throw new Error(`Unexpected isolated graph app route: ${path}`);
    await route.fulfill({ status, json: body });
  });
  return api;
}

async function clickOverlappingCurve(page: Page) {
  await page.locator(".graph-canvas").scrollIntoViewIfNeeded();
  const point = await page.locator(".graph-canvas").evaluate((element) => {
    const curve = element.querySelectorAll(".graph-edge-line")[1];
    if (!(curve instanceof SVGPathElement)) throw new Error("Real graph curve missing");
    const local = curve.getPointAtLength(curve.getTotalLength() * 0.5);
    let matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Curve transform missing");
    let screen = new DOMPoint(local.x, local.y).matrixTransform(matrix);
    const bounds = element.getBoundingClientRect();
    element.scrollLeft += screen.x - bounds.left - bounds.width / 2;
    element.scrollTop += screen.y - bounds.top - bounds.height / 2;
    matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Scrolled transform missing");
    screen = new DOMPoint(local.x, local.y).matrixTransform(matrix);
    return { x: screen.x, y: screen.y };
  });
  await page.mouse.click(point.x, point.y);
  const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
  await expect(chooser).toBeVisible();
  const choice = chooser.locator("button").filter({ has: page.locator("code", { hasText: fixtureGraphId(11) }) });
  await choice.scrollIntoViewIfNeeded();
  const bounds = await choice.boundingBox(); if (!bounds) throw new Error("Native chooser bounds missing");
  await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await expect(page.locator(".graph-edge[aria-pressed=true]")).toHaveAttribute("data-edge-id", fixtureGraphId(11));
  return point;
}

for (const width of [1366, 390]) {
  test(`default App isolated fixture ${width}: event graph native chooser evidence refresh and hash back`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await page.emulateMedia({ reducedMotion: width === 390 ? "reduce" : "no-preference" });
    const api = await installFixture(page);
    await page.goto(`/#events/${fixtureEventId}`);
    await expect(page.getByRole("link", { name: "查看证据关系图", exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("link", { name: "查看证据关系图", exact: true }).click();
    await expect(page.getByText("6 节点 / 6 支持关系", { exact: true })).toBeVisible();
    expect(new URL(page.url()).hash).toBe(`#graph/${fixtureEventId}`);
    await page.reload();
    await expect(page.locator(".graph-edge-line")).toHaveCount(6);
    const nativePoint = await clickOverlappingCurve(page);
    await expect(page.getByRole("complementary", { name: "关系检视", exact: true }).getByText("r10-graph-1.2.0", { exact: true })).toBeVisible();
    expect(await page.locator(".ambient-topology").evaluate((element) => getComputedStyle(element).animationName)).toBe(width === 390 ? "none" : "topology-drift");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`default-graph-fixture-${width}.png`), fullPage: false });
    const evidenceLink = page.getByRole("complementary", { name: "关系检视", exact: true }).getByRole("link", { name: /原文片段 \[1\]/ });
    await expect(evidenceLink).toHaveAttribute("href", `#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
    await evidenceLink.click();
    await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
    await expect(page.getByRole("complementary", { name: "证据检视", exact: true }).getByText(fixtureOldRevisionId, { exact: true })).toBeVisible();
    expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}`);
    await page.reload(); await expect(page.locator("blockquote")).toHaveText(historicalEvidenceFixture.quote_text);
    await page.goBack();
    await expect(page.locator(".graph-edge-line")).toHaveCount(6);
    await page.getByRole("link", { name: "返回事件", exact: true }).click();
    await expect(page.getByRole("link", { name: "查看证据关系图", exact: true })).toBeVisible();
    expect(new URL(page.url()).hash).toBe(`#events/${fixtureEventId}`);
    expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
    await info.attach("native-point-and-request-paths", { body: JSON.stringify({ width, nativePoint, requests: api.requests }), contentType: "application/json" });
  });
}

test("default App isolated fixture: loading empty partial stale and retry", async ({ page }) => {
  const api = await installFixture(page); api.hold = true;
  api.graph.nodes = api.graph.nodes.slice(0, 1); api.graph.edges = [];
  api.graph.gaps = graphRelationKinds.map((relation_type) => ({ relation_type, status: "unknown", reason: "no_current_supported_relation" }));
  await page.goto(`/#graph/${fixtureEventId}`);
  await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  api.hold = false; api.release();
  await expect(page.getByRole("heading", { name: "目前只有事件上下文", exact: true })).toBeVisible();
  await expect(page.getByText("关系缺口 · 6 项未知", { exact: true })).toBeVisible();
  api.graph = appGraphFixture(); api.graph.truncated = true; api.graph.gaps = [{ relation_type: "related_paper", status: "unknown", reason: "truncated" }];
  await page.getByRole("button", { name: "重新读取", exact: true }).click();
  await expect(page.locator(".graph-warning")).toContainText("截断");
  await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  api.graphStatus = 409; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  await expect(page.getByRole("heading", { name: "图快照已过期", exact: true })).toBeVisible();
  await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  api.graphStatus = 200; await page.getByRole("button", { name: "重新取得图", exact: true }).click();
  await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  expect(await page.getByText("暂无风险", { exact: true }).count()).toBe(0);
});

test("default App isolated fixture: guest denied expired session logout clear", async ({ page }) => {
  const api = await installFixture(page); api.authenticated = false;
  await page.goto(`/#graph/${fixtureEventId}`);
  await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  api.authenticated = true; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  api.graphStatus = 403; await page.getByRole("button", { name: "重新读取", exact: true }).click();
  await expect(page.getByRole("heading", { name: "没有查看权限", exact: true })).toBeVisible();
  await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  api.graphStatus = 401; await page.reload();
  await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  api.graphStatus = 200; await page.reload(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  await expect(page.locator(".graph-edge-line")).toHaveCount(0);
});

test("default App isolated fixture: legacy entry invalid route and future version fail closed", async ({ page }) => {
  const api = await installFixture(page);
  await page.goto("/#graph"); await expect(page.getByRole("link", { name: "进入情报列表", exact: true })).toBeVisible();
  expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  await page.goto(`/#graph/${fixtureEventId}?tenant=forged`); await expect(page.getByRole("heading", { name: "工作区不存在", exact: true })).toBeVisible();
  expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  api.dataMode = "unknown"; await page.reload(); await page.goto(`/#graph/${fixtureEventId}`);
  await expect(page.getByRole("heading", { name: "登录后查看证据图", exact: true })).toBeVisible();
  expect(api.requests.some((path) => path.endsWith("/graph"))).toBe(false);
  api.dataMode = "fixture";
  await page.route(`**/v1/events/${fixtureEventId}/graph?*`, async (route) => { await route.fulfill({ json: { ...appGraphFixture(), rule_version: "r10-graph-9.0.0" } }); });
  await page.reload(); await expect(page.getByRole("heading", { name: "图协议不匹配", exact: true })).toBeVisible();
  await expect(page.locator(".graph-edge-line")).toHaveCount(0);
  expect(await page.getByText("真实 / Live", { exact: true }).count()).toBe(0);
});

test("default App isolated fixture: late old tenant response cannot restore graph after session changes", async ({ page }) => {
  const api = await installFixture(page); api.hold = true;
  api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · 私有 A 旧图", scope: { visibility: "tenant", tenant_id: api.tenant } };
  api.graph.edges = api.graph.edges.map((edge) => ({ ...edge, scope: { visibility: "tenant", tenant_id: api.tenant } }));
  await page.goto(`/#graph/${fixtureEventId}`);
  await expect(page.getByText("正在取得授权范围内的图快照…", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "会话与权限", exact: true }).click();
  api.tenant = "graph-app-fixture-b";
  await page.getByRole("button", { name: "重新验证会话", exact: true }).click();
  await expect(page.getByText("graph-app-fixture-b", { exact: true })).toBeVisible();
  api.hold = false; api.release(); api.graph = appGraphFixture(); api.graph.nodes[0] = { ...api.graph.nodes[0]!, label: "合成 Fixture · B 当前图" };
  await page.goBack(); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  await expect(page.getByRole("heading", { name: "合成 Fixture · B 当前图", exact: true })).toBeVisible();
  expect(await page.getByText("合成 Fixture · 私有 A 旧图", { exact: true }).count()).toBe(0);
});
