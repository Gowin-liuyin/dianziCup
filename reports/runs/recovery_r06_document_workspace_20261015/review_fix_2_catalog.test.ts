import { createElement } from "../../../frontend/node_modules/react/index.js";
import { act, cleanup, render, screen } from "../../../frontend/node_modules/@testing-library/react/dist/index.js";
import { afterEach, expect, it, vi } from "../../../frontend/node_modules/vitest/dist/index.js";
import { App } from "../../../frontend/src/App";
import { detailFixture, documentFixture, documentId } from "../../../frontend/tests/document-fixture";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
it("catalog READ_PUBLIC 403 fences concurrent detail and history responses", async () => {
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/v1/auth/me") return json({ user_id: "isolated-catalog-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "d".repeat(64) });
    if (path === "/v1/health/live") return json({ status: "live" });
    if (path === "/v1/health/ready") return json({ status: "ready", reason: "fixture", dependencies: {} });
    if (path.startsWith("/v1/documents?")) return json({ error: { code: "forbidden" } }, 403);
    await barrier;
    if (path.includes("/revisions?")) return json({ schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" });
    if (path.startsWith(`/v1/documents/${documentId}?`)) return json(detailFixture);
    throw new Error(`Unexpected fixture ${path}`);
  }));
  window.history.replaceState(null, "", `/#documents/${documentId}`); render(createElement(App));
  await screen.findByRole("heading", { name: "没有资料查看权限" });
  await act(async () => { release(); await barrier; await Promise.resolve(); });
  expect(screen.queryByRole("heading", { name: documentFixture.title })).toBeNull();
  expect(document.querySelector(".document-evidence")).toBeNull();
});
