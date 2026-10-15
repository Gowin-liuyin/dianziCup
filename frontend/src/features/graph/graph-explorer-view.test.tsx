import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuthSession } from "../../app/auth-session";
import { GraphExplorerView } from "./graph-explorer-view";
import { graphFixture, graphFixtureEventId, graphFixtureEvidenceId, fixtureGraphId } from "./graph.fixture";
import { graphRelationKinds, type GraphSnapshot } from "./graph-contracts";
import { layoutGraph } from "./graph-layout";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status }); }
function fixtureAuth() { return { user_id: "isolated-graph-fixture-user", tenant_id: "fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") }; }
function Harness({ eventId = graphFixtureEventId, mode }: { eventId?: string; mode?: "fixture" }) {
  const { refreshSession } = useAuthSession();
  return <><button onClick={() => void refreshSession()}>测试重新验证会话</button><GraphExplorerView eventId={eventId} dataMode={mode} /></>;
}
function installApi(snapshot: GraphSnapshot = graphFixture()) {
  const mutable = { graphStatus: 200, authStatus: 200 };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    if (String(input) === "/v1/auth/me") return response(mutable.authStatus === 200 ? fixtureAuth() : { error: { code: "session_expired", retryable: false } }, mutable.authStatus);
    return response(mutable.graphStatus === 200 ? snapshot : { error: { code: "graph_problem", retryable: mutable.graphStatus >= 500 } }, mutable.graphStatus);
  }));
  return mutable;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("R17 independent graph view — explicit synthetic only", () => {
  it("renders six types, chooses a relationship with keyboard and links every evidence", async () => {
    installApi(); render(<AuthProvider><Harness mode="fixture" /></AuthProvider>);
    await screen.findByText("6 节点 / 6 支持关系");
    expect(screen.getByText("合成 / Fixture")).toBeTruthy();
    const edge = screen.getByRole("button", { name: "图关系 2：影响组件版本" });
    fireEvent.keyDown(edge, { key: "Enter" });
    const inspector = screen.getByRole("complementary", { name: "关系检视" });
    expect(within(inspector).getByText("合成 Fixture：来自当前支持断言；不代表真实情报或受影响资产。")).toBeTruthy();
    expect(within(inspector).getByRole("link").getAttribute("href")).toBe(`#events/${graphFixtureEventId}/evidence/${graphFixtureEvidenceId}`);
    expect(within(inspector).getByText("支持断言 · 1")).toBeTruthy();
    expect(within(inspector).getByText("来源修订 · 1")).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("button", { name: "论文节点：Fixture · 条件与缓解机制研究" }), { key: " " });
    expect(screen.getByRole("complementary", { name: "节点检视" })).toBeTruthy();
  });
  it("uses unknown data mode until the caller confirms it", async () => {
    installApi(); render(<AuthProvider><Harness /></AuthProvider>);
    await screen.findByText("数据模式未确认"); expect(screen.queryByText("真实 / Live")).toBeNull();
  });
  it("root-only and partial/truncated gaps remain unknown", async () => {
    const snapshot = graphFixture(); snapshot.nodes = snapshot.nodes.slice(0, 1); snapshot.edges = []; snapshot.truncated = true;
    snapshot.gaps = graphRelationKinds.map((relation_type) => ({ relation_type, status: "unknown", reason: "truncated" }));
    installApi(snapshot); render(<AuthProvider><Harness mode="fixture" /></AuthProvider>);
    await screen.findByRole("heading", { name: "目前只有事件上下文" });
    expect(screen.getByText("关系缺口 · 6 项未知")).toBeTruthy(); expect(screen.queryByText("暂无风险")).toBeNull();
  });
  it("clears displayed contents immediately on refresh and does not retain revoked private text", async () => {
    const api = installApi(); render(<AuthProvider><Harness /></AuthProvider>);
    await screen.findByText("6 节点 / 6 支持关系"); api.graphStatus = 403;
    fireEvent.click(screen.getByRole("button", { name: "重新读取" }));
    expect(screen.queryByText("6 节点 / 6 支持关系")).toBeNull();
    await screen.findByRole("heading", { name: "没有查看权限" });
    expect(screen.queryByRole("region", { name: "证据关系图画布" })).toBeNull();
  });
  it.each([[404, "事件不可访问"], [409, "图快照已过期"], [503, "图服务暂不可用"]])("keeps %s distinguishable and supports a new request", async (status, title) => {
    const api = installApi(); api.graphStatus = Number(status); render(<AuthProvider><Harness /></AuthProvider>);
    await screen.findByRole("heading", { name: String(title) }); api.graphStatus = 200;
    fireEvent.click(screen.getByRole("button", { name: "重新取得图" })); await screen.findByText("6 节点 / 6 支持关系");
  });
  it("business 401 expires the auth context without restoring the old graph", async () => {
    const api = installApi(); api.graphStatus = 401; render(<AuthProvider><Harness /></AuthProvider>);
    await screen.findByRole("heading", { name: "登录后查看证据图" }); expect(screen.queryByRole("region", { name: "证据关系图画布" })).toBeNull();
    expect(screen.getByText("会话已失效。旧图已清除，请重新登录。")).toBeTruthy();
  });
  it("renders malicious material as plain text without executing markup", async () => {
    const snapshot = graphFixture(); const root = snapshot.nodes[0]; const edge = snapshot.edges[0];
    if (!root || !edge) throw new Error("test setup missing root/edge");
    root.label = "<svg onload=alert('synthetic')>"; edge.reason = "<img src=x onerror=alert('synthetic')>";
    installApi(snapshot); const view = render(<AuthProvider><Harness /></AuthProvider>);
    await screen.findByText("6 节点 / 6 支持关系"); fireEvent.click(screen.getByRole("button", { name: "图关系 1：归于同一事件" }));
    expect(screen.getByText(edge.reason)).toBeTruthy(); expect(view.container.querySelector("img")).toBeNull(); expect(view.container.querySelector("svg[onload]")).toBeNull();
  });
  it("removes selected relations when view filters hide their endpoint without changing the snapshot count", async () => {
    installApi(); render(<AuthProvider><Harness /></AuthProvider>); await screen.findByText("6 节点 / 6 支持关系");
    fireEvent.click(screen.getByRole("checkbox", { name: "论文" }));
    expect(screen.getByText("当前视图 5 / 快照 6")).toBeTruthy(); expect(screen.queryByRole("button", { name: "论文节点：Fixture · 条件与缓解机制研究" })).toBeNull();
  });
  it("suppresses a late old-event response after event selection changes", async () => {
    let resolveOld: ((value: Response) => void) | undefined;
    const old = new Promise<Response>((resolve) => { resolveOld = resolve; });
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input) === "/v1/auth/me" ? response(fixtureAuth()) : String(input).includes(graphFixtureEventId) ? old : response({ error: { code: "not_found", retryable: false } }, 404)));
    const view = render(<AuthProvider><Harness /></AuthProvider>); await screen.findByText("正在取得授权范围内的图快照…");
    view.rerender(<AuthProvider><Harness eventId={fixtureGraphId(999)} /></AuthProvider>); await screen.findByRole("heading", { name: "事件不可访问" });
    resolveOld?.(response(graphFixture())); await waitFor(() => expect(screen.queryByText("6 节点 / 6 支持关系")).toBeNull());
  });
  it("clears contents while checking the session and keeps them absent after revocation", async () => {
    const api = installApi(); render(<AuthProvider><Harness /></AuthProvider>); await screen.findByText("6 节点 / 6 支持关系"); api.authStatus = 401;
    fireEvent.click(screen.getByRole("button", { name: "测试重新验证会话" }));
    expect(screen.queryByText("6 节点 / 6 支持关系")).toBeNull(); await screen.findByRole("heading", { name: "登录后查看证据图" });
  });
  it("uses deterministic positions instead of random movement", () => {
    const first = layoutGraph(graphFixture()); const next = layoutGraph({ ...graphFixture(), nodes: graphFixture().nodes.reverse() });
    expect(first).toEqual(next); expect(first.nodes.find((item) => item.node.id === graphFixtureEventId)).toMatchObject({ x: 295, y: 145 });
  });
});
