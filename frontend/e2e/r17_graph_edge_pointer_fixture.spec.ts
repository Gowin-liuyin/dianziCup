import { randomBytes } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";
import { graphFixture, graphFixtureEventId, fixtureGraphId } from "../src/features/graph/graph.fixture";
import { graphNodeKinds, type GraphSnapshot } from "../src/features/graph/graph-contracts";

async function isolateGraph(page: Page, snapshot: GraphSnapshot) {
  await page.route("**/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/v1/auth/me") await route.fulfill({ json: { user_id: "graph-pointer-fixture-user", tenant_id: "graph-pointer-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") } });
    else if (path === `/v1/events/${graphFixtureEventId}/graph`) await route.fulfill({ json: snapshot });
    else throw new Error(`Unexpected graph pointer fixture route: ${path}`);
  });
}

async function clickCurveByMouse(page: Page, edgeIndex: number, ratio = 0.5) {
  const coordinates = await page.locator(".graph-edge-line").nth(edgeIndex).evaluate((element, fraction) => {
    if (!(element instanceof SVGPathElement)) throw new Error("Expected real SVG curve");
    const matrix = element.getScreenCTM(); if (!matrix) throw new Error("Curve matrix unavailable");
    const point = element.getPointAtLength(element.getTotalLength() * fraction);
    const screen = new DOMPoint(point.x, point.y).matrixTransform(matrix);
    return { x: screen.x, y: screen.y };
  }, ratio);
  await page.mouse.click(coordinates.x, coordinates.y);
  return coordinates;
}

async function chooseExpectedEdge(page: Page, edgeId: string) {
  const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
  if (await chooser.isVisible()) {
    const option = chooser.locator("button").filter({ has: page.locator("code", { hasText: edgeId }) });
    await option.scrollIntoViewIfNeeded(); const bounds = await option.boundingBox(); if (!bounds) throw new Error("Choice bounds unavailable");
    await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  }
  await expect(page.locator(".graph-edge[aria-pressed=true]")).toHaveAttribute("data-edge-id", edgeId);
}

async function clickVisibleCurve(page: Page, edgeIndex: number) {
  await page.locator(".graph-canvas").scrollIntoViewIfNeeded();
  for (const fraction of [0.5, 0.35, 0.65, 0.2, 0.8, 0.1, 0.9]) {
    const coordinates = await page.locator(".graph-canvas").evaluate((element, input) => {
      const curve = element.querySelectorAll(".graph-edge-line")[input.index];
      if (!(curve instanceof SVGPathElement)) throw new Error("Curve missing");
      const graphPoint = curve.getPointAtLength(curve.getTotalLength() * input.fraction);
      let matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Curve matrix missing");
      let screen = new DOMPoint(graphPoint.x, graphPoint.y).matrixTransform(matrix);
      const canvasBounds = element.getBoundingClientRect();
      element.scrollLeft += screen.x - canvasBounds.left - canvasBounds.width / 2;
      element.scrollTop += screen.y - canvasBounds.top - canvasBounds.height / 2;
      matrix = curve.getScreenCTM(); if (!matrix) throw new Error("Scrolled curve matrix missing");
      screen = new DOMPoint(graphPoint.x, graphPoint.y).matrixTransform(matrix);
      const nodeCore = [...element.querySelectorAll(".graph-node")].some((node) => {
        const shape = node.querySelector("path, ellipse, rect:not(.graph-node-hit)");
        if (!shape) return false;
        const bounds = shape.getBoundingClientRect();
        return screen.x >= bounds.left && screen.x <= bounds.right && screen.y >= bounds.top && screen.y <= bounds.bottom;
      });
      return { x: screen.x, y: screen.y, fraction: input.fraction, nodeCore };
    }, { index: edgeIndex, fraction });
    if (coordinates.nodeCore) continue;
    await page.mouse.click(coordinates.x, coordinates.y); return coordinates;
  }
  throw new Error(`No curve point outside visible node body for edge ${edgeIndex}`);
}

function thirtyEdgeFixture() {
  const snapshot = graphFixture("r10-graph-1.1.0"); const initial = [...snapshot.edges];
  for (let index = 0; index < 24; index += 1) {
    const base = initial[index % initial.length]; if (!base) throw new Error("Base edge missing");
    let subject = base.subject_id; let object = base.object_id;
    if (index >= 12) {
      const node = snapshot.nodes.find((item) => item.id === (base.relation_type === "component_version_vulnerability" ? base.subject_id : base.object_id));
      if (!node) throw new Error("Base endpoint missing");
      const id = fixtureGraphId(200 + index); snapshot.nodes.push({ ...node, id, label: `合成多边端点 ${index} · ${node.kind}` });
      if (base.relation_type === "component_version_vulnerability") subject = id; else object = id;
    }
    snapshot.edges.push({ ...base, id: fixtureGraphId(100 + index), subject_id: subject, object_id: object, reason: `合成平行/逆向/不同端点关系 ${index}，仅测试指针选择。` });
  }
  return snapshot;
}

for (const shape of ["full-six", "without-inverse", "single-edge-positive"] as const) {
  test(`R17 fix1 actual mouse midpoint ${shape}`, async ({ page }, info) => {
    const snapshot = graphFixture("r10-graph-1.1.0");
    if (shape === "without-inverse") snapshot.edges = snapshot.edges.slice(0, 5);
    if (shape === "single-edge-positive") { snapshot.edges = snapshot.edges.filter((edge) => edge.relation_type === "affects_component_version"); snapshot.nodes = snapshot.nodes.filter((node) => node.id === graphFixtureEventId || node.id === fixtureGraphId(3)); }
    await isolateGraph(page, snapshot); await page.goto("/e2e/graph-fixture/index.html");
    await expect(page.locator(".graph-edge-line")).toHaveCount(snapshot.edges.length);
    const coordinates = await clickCurveByMouse(page, shape === "single-edge-positive" ? 0 : 1);
    const expected = snapshot.edges.find((edge) => edge.relation_type === "affects_component_version"); if (!expected) throw new Error("Expected edge missing");
    if (shape === "full-six") {
      await expect(page.getByRole("region", { name: "选择此处的关系", exact: true })).toBeVisible();
      await expect(page.getByRole("complementary", { name: "节点检视", exact: true })).toBeVisible();
      await page.screenshot({ path: info.outputPath("ambiguous-full-six-before-confirmation.png"), fullPage: false });
    }
    const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
    if (await chooser.isVisible()) {
      const optionHeights = await chooser.locator("button").evaluateAll((buttons) => buttons.map((button) => button.getBoundingClientRect().height));
      for (const height of optionHeights) expect(height).toBeGreaterThanOrEqual(40);
      const option = chooser.locator("button").filter({ has: page.locator("code", { hasText: expected.id }) });
      await option.scrollIntoViewIfNeeded(); const bounds = await option.boundingBox(); if (!bounds) throw new Error("Choice bounds unavailable");
      await page.mouse.click(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    }
    await info.attach("actual-pointer-coordinates", { body: JSON.stringify({ shape, coordinates }, null, 2), contentType: "application/json" });
    await expect(page.locator(".graph-inspector > .graph-code").first()).toHaveText("affects_component_version");
  });
}

for (const width of [1366, 390]) {
  test(`R17 fix1 six kinds actual mouse every edge at 80/100/180 zoom and pan ${width}`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 }); await page.emulateMedia({ reducedMotion: "reduce" });
    const snapshot = graphFixture("r10-graph-1.1.0"); await isolateGraph(page, snapshot); await page.goto("/e2e/graph-fixture/index.html");
    await expect(page.locator(".graph-edge-line")).toHaveCount(6); const clicks = [];
    for (const zoom of [80, 100, 180]) {
      await page.getByRole("button", { name: "重置视图", exact: true }).click();
      if (zoom === 80) await page.getByRole("button", { name: "缩小图", exact: true }).click();
      if (zoom === 180) for (let count = 0; count < 4; count += 1) await page.getByRole("button", { name: "放大图", exact: true }).click();
      await expect(page.getByLabel("图缩放比例")).toHaveText(`${zoom}%`);
      await page.getByRole("button", { name: "向右平移", exact: true }).click();
      for (const [index, edge] of snapshot.edges.entries()) { const coordinates = await clickVisibleCurve(page, index); await chooseExpectedEdge(page, edge.id); clicks.push({ index, edgeId: edge.id, zoom, coordinates }); }
      expect(await page.locator(".graph-edge-hit").first().evaluate((element) => ({ width: getComputedStyle(element).strokeWidth, vectorEffect: getComputedStyle(element).vectorEffect }))).toEqual({ width: "44px", vectorEffect: "non-scaling-stroke" });
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator(".graph-edge-line").first().evaluate((element) => getComputedStyle(element).transitionDuration)).toBe("0s");
    await info.attach("six-kinds-mouse-clicks", { body: JSON.stringify({ width, clicks }, null, 2), contentType: "application/json" });
    await page.screenshot({ path: info.outputPath(`all-six-selected-${width}.png`), fullPage: false });
  });
}

test("R17 fix1 thirty edges: parallel, reverse and different endpoints via actual mouse", async ({ page }, info) => {
  const snapshot = thirtyEdgeFixture(); await isolateGraph(page, snapshot); await page.goto("/e2e/graph-fixture/index.html"); await expect(page.locator(".graph-edge-line")).toHaveCount(30);
  const clicks = []; const start = performance.now();
  for (const [index, edge] of snapshot.edges.entries()) { const coordinates = await clickVisibleCurve(page, index); await chooseExpectedEdge(page, edge.id); clicks.push({ index, edgeId: edge.id, coordinates }); }
  await info.attach("thirty-edges-pointer", { body: JSON.stringify({ data_kind: "synthetic", clicks, loopMilliseconds: performance.now() - start }, null, 2), contentType: "application/json" });
});

test("R17 fix1 chooser focus, keyboard, cancel, zoom/filter clearing and node mouse remain distinct", async ({ page }, info) => {
  await isolateGraph(page, graphFixture("r10-graph-1.1.0")); await page.goto("/e2e/graph-fixture/index.html"); await expect(page.locator(".graph-edge-line")).toHaveCount(6);
  await clickVisibleCurve(page, 1); const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true }); await expect(chooser).toBeVisible();
  await expect(chooser.locator("button").first()).toBeFocused(); await page.keyboard.press("Escape"); await expect(chooser).toHaveCount(0); await expect(page.getByRole("region", { name: "证据关系图画布", exact: true })).toBeFocused();
  await clickVisibleCurve(page, 1); await expect(chooser).toBeVisible(); const option = chooser.getByRole("button", { name: /^选择关系 2：影响组件版本/ }); await option.focus(); await page.keyboard.press("Enter"); await expect(page.locator(".graph-edge[aria-pressed=true]")).toHaveAttribute("data-edge-id", fixtureGraphId(11));
  await clickVisibleCurve(page, 1); await page.getByRole("button", { name: "放大图", exact: true }).click(); await expect(chooser).toHaveCount(0);
  await clickVisibleCurve(page, 1); await expect(chooser).toBeVisible(); await page.getByRole("checkbox", { name: "论文", exact: true }).click(); await expect(chooser).toHaveCount(0);
  const node = page.getByRole("button", { name: "事件节点：合成 Fixture · AI 组件安全事件", exact: true }); await node.scrollIntoViewIfNeeded();
  const point = await node.evaluate((element) => { const shape = element.querySelector("path"); if (!shape) throw new Error("Node shape missing"); const box = shape.getBoundingClientRect(); return { x: box.x + box.width / 2, y: box.y + box.height / 2 }; });
  await page.mouse.click(point.x, point.y); await expect(page.getByRole("complementary", { name: "节点检视", exact: true })).toBeVisible();
  const edge = page.getByRole("button", { name: "图关系 1：归于同一事件", exact: true }); await edge.focus(); await page.keyboard.press("Space"); await expect(edge).toHaveAttribute("aria-pressed", "true");
  await info.attach("node-real-pointer", { body: JSON.stringify(point), contentType: "application/json" });
});

test("R17 fix1 200 nodes / 400 edges actual pointer and bounded chooser", async ({ page }, info) => {
  const snapshot = graphFixture("r10-graph-1.1.0"); const root = snapshot.nodes[0]; const firstEdge = snapshot.edges[0];
  if (!root || !firstEdge) throw new Error("Bounded graph base missing");
  snapshot.nodes = [root, ...Array.from({ length: 199 }, (_, index) => {
    const kind = graphNodeKinds[(index % 5) + 1]; if (!kind) throw new Error("Bounded graph kind missing");
    return { id: fixtureGraphId(index + 1000), kind, label: `最大合成指针图 ${index} · ${kind}`, scope: root.scope };
  })];
  snapshot.edges = Array.from({ length: 400 }, (_, index) => {
    const node = snapshot.nodes[(index % 199) + 1]; if (!node) throw new Error("Bounded graph endpoint missing");
    return { ...firstEdge, id: fixtureGraphId(index + 2000), object_id: node.id, reason: `最大合成指针图第${index}关系，仅fixture。` };
  });
  await isolateGraph(page, snapshot); await page.goto("/e2e/graph-fixture/index.html"); await expect(page.locator(".graph-edge-line")).toHaveCount(400);
  const expected = snapshot.edges[1]; if (!expected) throw new Error("Expected dense edge missing");
  const start = performance.now(); const coordinates = await clickVisibleCurve(page, 1); const choice = page.getByRole("region", { name: "选择此处的关系", exact: true });
  if (await choice.isVisible()) expect(await choice.locator("div").last().evaluate((element) => element.getBoundingClientRect().height)).toBeLessThanOrEqual(260);
  await chooseExpectedEdge(page, expected.id); const clickMilliseconds = performance.now() - start;
  await expect(page.locator(".graph-node")).toHaveCount(200); await expect(page.locator(".graph-edge")).toHaveCount(400);
  await info.attach("dense-real-pointer", { body: JSON.stringify({ data_kind: "synthetic", nodes: 200, edges: 400, coordinates, expectedEdgeId: expected.id, clickMilliseconds, scope: "one UI pointer/chooser operation, no live or P95 claim" }, null, 2), contentType: "application/json" });
});
