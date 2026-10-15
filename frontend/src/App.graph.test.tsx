import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { graphFixture, graphFixtureEventId } from "./features/graph/graph.fixture";
import { eventDetailFixture, fixtureEventId } from "./features/events/event-detail.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status }); }
function navigate(hash: string) { window.history.replaceState(null, "", `/${hash}`); fireEvent(window, new HashChangeEvent("hashchange")); }
function installFixture() {
  const api = { authStatus: 200, graphStatus: 200, graph: graphFixture("r10-graph-1.2.0") };
  const requests = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path === "/v1/auth/me") return response(api.authStatus === 200 ? { user_id: "graph-app-fixture-user", tenant_id: "graph-app-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") } : { error: { code: "session_expired", retryable: false } }, api.authStatus);
    if (path === "/v1/health/live") return response({ status: "live" });
    if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
    if (path === "/v1/events?limit=20") return response({ schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" });
    if (path === `/v1/events/${fixtureEventId}`) return response(eventDetailFixture);
    if (path === `/v1/events/${graphFixtureEventId}/graph?max_nodes=200&max_edges=400`) return response(api.graphStatus === 200 ? api.graph : { error: { code: "graph_fixture_problem", retryable: api.graphStatus >= 500 } }, api.graphStatus);
    throw new Error(`Unexpected isolated graph app path: ${path}`);
  });
  vi.stubGlobal("fetch", requests);
  return { api, requests };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

describe("default workbench graph integration with explicit isolated HTTP fixtures", () => {
  it("registers the current graph route and restores it after remount", async () => {
    const { requests } = installFixture(); navigate(`#graph/${graphFixtureEventId}`);
    const first = render(<App />);
    await screen.findByText("6 节点 / 6 支持关系");
    expect(screen.getByRole("link", { name: "知识图谱" }).getAttribute("aria-current")).toBe("page");
    expect(screen.queryByText("真实 / Live", { exact: true })).toBeNull();
    expect(screen.getByRole("link", { name: "返回事件" }).getAttribute("href")).toBe(`#events/${graphFixtureEventId}`);
    first.unmount(); render(<App />);
    await screen.findByText("6 节点 / 6 支持关系");
    expect(requests.mock.calls.filter(([path]) => String(path).includes("/graph?")).length).toBe(2);
  });
  it("offers a graph route only after the event detail is loaded", async () => {
    installFixture(); navigate(`#events/${fixtureEventId}`); render(<App />);
    expect(screen.queryByRole("link", { name: "查看证据关系图" })).toBeNull();
    const link = await screen.findByRole("link", { name: "查看证据关系图" });
    expect(link.getAttribute("href")).toBe(`#graph/${fixtureEventId}`);
  });
  it.each(["#graph", "#graph/https://external.invalid", `#graph/${graphFixtureEventId}?tenant=forged`, "#graph/../private"])("does not query a graph from an absent or invalid event: %s", async (hash) => {
    const { requests } = installFixture(); navigate(hash); render(<App />);
    await waitFor(() => expect(requests).toHaveBeenCalledTimes(3));
    expect(requests.mock.calls.some(([path]) => String(path).includes("/graph?"))).toBe(false);
    expect(screen.queryByRole("region", { name: "证据关系图画布" })).toBeNull();
    if (hash === "#graph") expect(screen.getByRole("link", { name: "进入情报列表" }).getAttribute("href")).toBe("#events");
    else expect(screen.getByRole("heading", { name: "工作区不存在" })).toBeTruthy();
  });
  it("keeps graph requests behind the restored session", async () => {
    const { api, requests } = installFixture(); api.authStatus = 401;
    navigate(`#graph/${graphFixtureEventId}`); render(<App />);
    await screen.findByRole("heading", { name: "登录后查看证据图" });
    expect(requests.mock.calls.every(([path]) => !String(path).includes("/graph?"))).toBe(true);
  });
  it.each([[403, "没有查看权限"], [409, "图快照已过期"], [503, "图服务暂不可用"]])("clears the old snapshot on a %s reload", async (status, heading) => {
    const { api } = installFixture(); navigate(`#graph/${graphFixtureEventId}`); render(<App />);
    await screen.findByText("6 节点 / 6 支持关系"); api.graphStatus = Number(status);
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(screen.queryByText("6 节点 / 6 支持关系")).toBeNull();
    await screen.findByRole("heading", { name: String(heading) });
    expect(screen.queryByRole("region", { name: "证据关系图画布" })).toBeNull();
  });
  it("expires the default auth context when a graph read returns 401", async () => {
    const { api } = installFixture(); navigate(`#graph/${graphFixtureEventId}`); render(<App />);
    await screen.findByText("6 节点 / 6 支持关系"); api.graphStatus = 401;
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    await screen.findByRole("heading", { name: "登录后查看证据图" });
    expect(screen.queryByText("6 节点 / 6 支持关系")).toBeNull();
    expect(screen.queryByText("数据模式未确认")).toBeNull();
  });
});
