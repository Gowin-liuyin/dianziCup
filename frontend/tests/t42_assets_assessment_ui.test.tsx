import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { assetFixture, fixtureAssetId, fixtureSnapshotId, fixtureTenant, snapshotFixture } from "../src/features/assets/synthetic-fixtures";

function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function mockAssets() {
  const api = { tenant: fixtureTenant, permissions: ["read:asset", "write:asset"], authenticated: true, status: 200, empty: false, historyStatus: 200, historyAdvanced: false, listDeferred: null as Promise<Response> | null, requests: [] as { path: string; options: RequestInit | undefined }[] };
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    api.requests.push({ path, options });
    const url = new URL(path, "http://127.0.0.1");
    if (url.pathname === "/v1/auth/me") return json(api.authenticated ? { user_id: "synthetic-fixture-admin", tenant_id: api.tenant, role: "tenant_admin", permissions: api.permissions, permission_version: 1, data_mode: "fixture", csrf_token: "synthetic-csrf" } : { error: { code: "session_expired", retryable: false } }, api.authenticated ? 200 : 401);
    if (url.pathname === "/v1/auth/logout") { api.authenticated = false; return json({ status: "logged_out" }); }
    if (url.pathname === "/v1/auth/csrf") return json({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" });
    if (url.pathname === "/v1/health/live") return json({ status: "live" });
    if (url.pathname === "/v1/health/ready") return json({ status: "ready", reason: "synthetic fixture", dependencies: {} });
    if (url.pathname.startsWith("/v1/assets") && api.status !== 200) return json({ error: { code: api.status === 403 ? "permission_denied" : "inventory_unavailable", retryable: api.status === 503 } }, api.status);
    if (url.pathname === "/v1/assets") return api.listDeferred ?? json({ items: api.empty ? [] : [assetFixture()], next_cursor: null });
    if (url.pathname === `/v1/assets/${fixtureAssetId}`) return json(assetFixture());
    if (url.pathname === `/v1/assets/${fixtureAssetId}/snapshots`) return api.historyStatus === 200 ? json({ items: api.historyAdvanced ? [{ ...snapshotFixture(), snapshot_number: 3, snapshot_id: "b0000000-0000-4000-8000-000000000003" }] : [snapshotFixture(), snapshotFixture(1)], next_cursor: null }) : json({ error: { code: "inventory_unavailable", retryable: true } }, api.historyStatus);
    if (url.pathname === `/v1/assets/${fixtureAssetId}/snapshots/b0000000-0000-4000-8000-000000000001`) return json(snapshotFixture(1));
    if (url.pathname === "/v1/asset-imports") return json({ asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: false }, 201);
    throw new Error(`unexpected synthetic API route: ${url.pathname}`);
  }));
  return api;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

describe("T42 asset inventory UI slice · explicit synthetic fixtures", () => {
  it("T42-C02: preserves missing version, source version and nullable configuration", async () => {
    mockAssets(); window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    const detail = await screen.findByRole("region", { name: assetFixture().display_name });
    expect(within(detail).getByText("版本未知")).toBeTruthy();
    expect(within(detail).getByText("未知 · 当前响应未提供")).toBeTruthy();
    expect(within(detail).getAllByText("未知 · 未声明").length).toBeGreaterThan(0);
    expect(within(detail).getAllByText("声明为 false").length).toBe(2);
    expect(within(detail).getByText("/configuration/trust_remote_code")).toBeTruthy();
    expect(within(detail).getByText(fixtureSnapshotId)).toBeTruthy();
  });
  it("empty and loading states make no zero-impact or safety claim", async () => {
    const api = mockAssets(); let release: (response: Response) => void = () => {};
    api.listDeferred = new Promise<Response>((resolve) => { release = resolve; });
    window.location.hash = "assets"; render(<App />);
    expect(await screen.findByText("正在读取资产页…")).toBeTruthy();
    await act(async () => release(json({ items: [], next_cursor: null })));
    expect(await screen.findByText("尚无可见资产清单")).toBeTruthy();
    expect(screen.getByText(/空查询不等于零影响或安全/)).toBeTruthy();
    expect(screen.queryByText("0 影响")).toBeNull();
  });
  it("read permission is explicit; role name never grants an import", async () => {
    const api = mockAssets(); api.permissions = ["read:asset"];
    window.location.hash = "assets"; render(<App />);
    expect(await screen.findByText("只读资产权限")).toBeTruthy();
    expect(screen.queryByText("导入授权清单")).toBeNull();
    cleanup(); api.permissions = ["read:public"]; api.requests.length = 0;
    render(<App />);
    expect(await screen.findByText("当前会话无资产读取权限")).toBeTruthy();
    expect(api.requests.some((request) => request.path.startsWith("/v1/assets"))).toBe(false);
  });
  it("server 403 clears previously loaded private catalog", async () => {
    const api = mockAssets(); window.location.hash = "assets"; render(<App />);
    await screen.findByRole("link", { name: new RegExp(assetFixture().display_name) });
    api.status = 403; fireEvent.click(screen.getByRole("button", { name: "刷新资产与快照" }));
    expect(await screen.findByText(/当前会话没有此项资产权限/)).toBeTruthy();
    expect(screen.queryByText(assetFixture().display_name)).toBeNull();
  });
  it("history failure keeps current detail readable and retry reaches the real history route", async () => {
    const api = mockAssets(); api.historyStatus = 503; window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    expect(await screen.findByText("重试历史页")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "快照 #2" })).toBeTruthy();
    api.historyStatus = 200; fireEvent.click(screen.getByRole("button", { name: "重试历史页" }));
    expect(await screen.findByRole("button", { name: /查看快照 #1 · 历史/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /查看快照 #1 · 历史/ }));
    expect(await screen.findByText(/正在查看历史快照/)).toBeTruthy();
    expect(screen.getByText("1.9.0", { exact: true })).toBeTruthy();
    expect(api.requests.some((request) => request.path.endsWith("/snapshots/b0000000-0000-4000-8000-000000000001"))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "查看当前快照" }));
    expect(screen.getByText("版本未知")).toBeTruthy();
  });
  it("T42-C03/C05/C06 partial boundary: observation, assessment and exports stay unavailable", async () => {
    mockAssets(); window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    const observation = await screen.findByRole("button", { name: "查询授权外部观察 · 未就绪" });
    expect(observation.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "提交研判 · 未就绪" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "导出证据包 / OpenVEX · 未就绪" }).hasAttribute("disabled")).toBe(true);
    expect(screen.queryByText("软件已修复", { exact: true })).toBeNull();
    expect(screen.queryByText("安全", { exact: true })).toBeNull();
  });
  it("a newer history version marks the separately read current pointer as awaiting validation", async () => {
    const api = mockAssets(); api.historyAdvanced = true; window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    expect(await screen.findByText(/历史页包含较新快照/)).toBeTruthy();
    expect(screen.getByText("REVALIDATE / 当前指针待复核")).toBeTruthy();
    expect(screen.queryByText("CURRENT SNAPSHOT / 当前快照")).toBeNull();
  });
  it("history 404 invalidates the asset resource instead of retaining formerly visible private fields", async () => {
    const api = mockAssets(); api.historyStatus = 404; window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    const detail = await screen.findByRole("region", { name: "资产详情" });
    await waitFor(() => expect(within(detail).getByText(/该资产或快照不可用/)).toBeTruthy());
    expect(within(detail).queryByText("/configuration/trust_remote_code")).toBeNull();
  });
  it("JSON import uses selected original File and navigates only to server asset UUID", async () => {
    const api = mockAssets(); window.location.hash = "assets"; render(<App />);
    await screen.findByText("导入授权清单");
    const raw = '{"format_version":1,"components":[],"inventory_completeness":"unknown"}\r\n';
    const file = new File([raw], "synthetic-fixture.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => raw });
    fireEvent.change(screen.getByLabelText("选择本地清单"), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText("资产名称"), { target: { value: "Synthetic fixture" } });
    fireEvent.change(screen.getByLabelText("输入来源版本"), { target: { value: "synthetic-v1" } });
    fireEvent.change(screen.getByLabelText("实际观察时间（含时区）"), { target: { value: "2026-10-15T10:00:00Z" } });
    await screen.findByText("0 个组件声明");
    fireEvent.submit(screen.getByRole("button", { name: "提交授权清单" }).closest("form")!);
    expect(await screen.findByText("导入成功 · 服务端已保存快照")).toBeTruthy();
    await waitFor(() => expect(window.location.hash).toBe(`#assets/${fixtureAssetId}`));
    const write = api.requests.find((request) => request.path.startsWith("/v1/asset-imports"));
    expect(write?.options?.body).toBe(file);
    expect(new Headers(write?.options?.headers).get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
  });
  it("logout plus a late response cannot restore asset state", async () => {
    const api = mockAssets(); window.location.hash = "assets"; render(<App />);
    await screen.findByRole("link", { name: new RegExp(assetFixture().display_name) });
    let release: (response: Response) => void = () => {};
    api.listDeferred = new Promise<Response>((resolve) => { release = resolve; });
    fireEvent.click(screen.getByRole("button", { name: "刷新资产与快照" }));
    fireEvent.click(screen.getByRole("link", { name: "会话与权限" }));
    fireEvent.click(await screen.findByRole("button", { name: "退出登录" }));
    await act(async () => release(json({ items: [assetFixture()], next_cursor: null })));
    fireEvent.click(screen.getByRole("link", { name: "资产自查" }));
    expect(await screen.findByText("登录后查看授权资产")).toBeTruthy();
    expect(screen.queryByText(assetFixture().display_name)).toBeNull();
  });
});
