import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { detailFixture, documentFixture, documentId } from "../../../tests/document-fixture";

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function install(options: { status: number; allowedLists?: number }) {
  const requests: { path: string; signal: AbortSignal | null | undefined }[] = [];
  let lists = 0;
  let release = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input); requests.push({ path, signal: init?.signal });
    if (path === "/v1/auth/me") return json({ user_id: "isolated-scope-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "d".repeat(64) });
    if (path === "/v1/health/live") return json({ status: "live" });
    if (path === "/v1/health/ready") return json({ status: "ready", reason: "fixture", dependencies: {} });
    if (path.startsWith("/v1/documents?")) {
      lists += 1;
      if (lists > (options.allowedLists ?? 0)) return json({ error: { code: options.status === 403 ? "forbidden" : "fixture_failure" } }, options.status);
      return json({ schema_version: 2, items: [documentFixture], next_cursor: "isolated-scope-cursor", data_mode: "fixture" });
    }
    await barrier;
    if (path.includes("/revisions?")) return json({ schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" });
    if (path.startsWith(`/v1/documents/${documentId}?`)) return json(detailFixture);
    throw new Error(`Unexpected isolated scope request ${path}`);
  }));
  return { requests, release: async () => { release(); await barrier; await Promise.resolve(); } };
}
function navigateToDocument() { window.history.replaceState(null, "", `/#documents/${documentId}`); fireEvent(window, new HashChangeEvent("hashchange")); }
function expectHiddenDocument() {
  expect(document.querySelector(".document-detail-body")).toBeNull();
  expect(screen.queryByRole("heading", { name: documentFixture.title })).toBeNull();
  expect(screen.queryByRole("link", { name: "打开此版本来源地址 ↗" })).toBeNull();
  expect(screen.queryByLabelText("原文修订版本")).toBeNull();
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
describe("shared READ_PUBLIC document scope — isolated fixtures only", () => {
  it.each([403, 401])("fences deep-link detail/history when catalog first rejects HTTP %s", async (status) => {
    const fixture = install({ status }); navigateToDocument(); render(<App />);
    if (status === 403) await screen.findByRole("heading", { name: "没有资料查看权限" });
    else await screen.findByText("会话已失效，请重新登录。");
    const delayed = fixture.requests.filter((request) => request.path.startsWith(`/v1/documents/${documentId}`));
    expect(delayed).toHaveLength(2); expect(delayed.every((request) => request.signal?.aborted)).toBe(true);
    await act(fixture.release); expectHiddenDocument();
    expect(fixture.requests.filter((request) => request.path === "/v1/auth/me")).toHaveLength(1);
  });
  it.each(["search", "next_page", "first_page"] as const)("cancels the old inspection on %s before catalog denial", async (action) => {
    const fixture = install({ status: 403, allowedLists: action === "first_page" ? 2 : 1 }); navigateToDocument(); render(<App />);
    await screen.findByRole("link", { name: documentFixture.title });
    if (action === "first_page") {
      fireEvent.click(screen.getByRole("button", { name: "下一页资料" }));
      await screen.findByRole("link", { name: documentFixture.title }); navigateToDocument();
      await screen.findByRole("heading", { name: "资料检视" });
    }
    const delayed = fixture.requests.filter((request) => request.path.startsWith(`/v1/documents/${documentId}`));
    if (action === "search") fireEvent.click(screen.getByRole("button", { name: "检索资料" }));
    else fireEvent.click(screen.getByRole("button", { name: action === "first_page" ? "回到第一页" : "下一页资料" }));
    await screen.findByRole("heading", { name: "没有资料查看权限" });
    await waitFor(() => expect(delayed.every((request) => request.signal?.aborted)).toBe(true));
    await act(fixture.release); expectHiddenDocument();
  });
  it("keeps list 503 distinct from permission and permits valid detail responses", async () => {
    const fixture = install({ status: 503 }); navigateToDocument(); render(<App />);
    await screen.findByRole("heading", { name: "资料依赖暂不可用" }); await act(fixture.release);
    await screen.findByRole("heading", { name: documentFixture.title });
    expect(screen.queryByRole("heading", { name: "没有资料查看权限" })).toBeNull();
    expect(screen.queryByText(/本页 0 条/)).toBeNull();
  });
});
