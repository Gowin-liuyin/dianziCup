# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: r17_graph_edge_pointer_fixture.spec.ts >> R17 fix1 actual mouse midpoint full-six
- Location: e2e\r17_graph_edge_pointer_fixture.spec.ts:28:3

# Error details

```
Error: expect(locator).toHaveText(expected) failed

Locator:  locator('.graph-inspector > .graph-code').first()
Expected: "affects_component_version"
Received: "component_version_vulnerability"
Timeout:  1500ms

Call log:
  - Expect "toHaveText" locator('.graph-inspector > .graph-code').first() with timeout 1500ms
  - waiting for locator('.graph-inspector > .graph-code').first()
    16 × locator resolved to <code class="graph-code">component_version_vulnerability</code>
       - unexpected value "component_version_vulnerability"

```

```yaml
- code: component_version_vulnerability
```

# Test source

```ts
  1  | import { randomBytes } from "node:crypto";
  2  | import { expect, test, type Page } from "@playwright/test";
  3  | import { graphFixture, graphFixtureEventId, fixtureGraphId } from "../src/features/graph/graph.fixture";
  4  | import type { GraphSnapshot } from "../src/features/graph/graph-contracts";
  5  | 
  6  | async function isolateGraph(page: Page, snapshot: GraphSnapshot) {
  7  |   await page.route("**/v1/**", async (route) => {
  8  |     const path = new URL(route.request().url()).pathname;
  9  |     if (path === "/v1/auth/me") await route.fulfill({ json: { user_id: "graph-pointer-fixture-user", tenant_id: "graph-pointer-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") } });
  10 |     else if (path === `/v1/events/${graphFixtureEventId}/graph`) await route.fulfill({ json: snapshot });
  11 |     else throw new Error(`Unexpected graph pointer fixture route: ${path}`);
  12 |   });
  13 | }
  14 | 
  15 | async function clickCurveByMouse(page: Page, edgeIndex: number, ratio = 0.5) {
  16 |   const coordinates = await page.locator(".graph-edge-line").nth(edgeIndex).evaluate((element, fraction) => {
  17 |     if (!(element instanceof SVGPathElement)) throw new Error("Expected real SVG curve");
  18 |     const matrix = element.getScreenCTM(); if (!matrix) throw new Error("Curve matrix unavailable");
  19 |     const point = element.getPointAtLength(element.getTotalLength() * fraction);
  20 |     const screen = new DOMPoint(point.x, point.y).matrixTransform(matrix);
  21 |     return { x: screen.x, y: screen.y };
  22 |   }, ratio);
  23 |   await page.mouse.click(coordinates.x, coordinates.y);
  24 |   return coordinates;
  25 | }
  26 | 
  27 | for (const shape of ["full-six", "without-inverse", "single-edge-positive"] as const) {
  28 |   test(`R17 fix1 actual mouse midpoint ${shape}`, async ({ page }, info) => {
  29 |     const snapshot = graphFixture("r10-graph-1.1.0");
  30 |     if (shape === "without-inverse") snapshot.edges = snapshot.edges.slice(0, 5);
  31 |     if (shape === "single-edge-positive") { snapshot.edges = snapshot.edges.filter((edge) => edge.relation_type === "affects_component_version"); snapshot.nodes = snapshot.nodes.filter((node) => node.id === graphFixtureEventId || node.id === fixtureGraphId(3)); }
  32 |     await isolateGraph(page, snapshot); await page.goto("/e2e/graph-fixture/index.html");
  33 |     await expect(page.locator(".graph-edge-line")).toHaveCount(snapshot.edges.length);
  34 |     const coordinates = await clickCurveByMouse(page, shape === "single-edge-positive" ? 0 : 1);
  35 |     const chooser = page.getByRole("region", { name: "选择此处的关系", exact: true });
  36 |     if (await chooser.isVisible()) await chooser.getByRole("button", { name: /^选择关系 2：影响组件版本/ }).click();
  37 |     await info.attach("actual-pointer-coordinates", { body: JSON.stringify({ shape, coordinates }, null, 2), contentType: "application/json" });
> 38 |     await expect(page.locator(".graph-inspector > .graph-code").first()).toHaveText("affects_component_version");
     |                                                                          ^ Error: expect(locator).toHaveText(expected) failed
  39 |   });
  40 | }
  41 | 
```