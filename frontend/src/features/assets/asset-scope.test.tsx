import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { ApiProblem } from "../../api/client";
import { parseAsset, parseSnapshot } from "./asset-contracts";
import { assetFixture, fixtureAssetId, fixtureTenant, snapshotFixture } from "./synthetic-fixtures";

function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function deferredResponse() {
  let resolve: (value: Response) => void = () => { throw new Error("synthetic promise not initialized"); };
  const promise = new Promise<Response>((complete) => { resolve = complete; });
  return { promise, resolve };
}
interface ScopeFixture {
  listFault: "none" | "scope" | "503"; fixedFault: "none" | "scope"; current: ReturnType<typeof deferredResponse> | null;
  list: ReturnType<typeof deferredResponse> | null; csrf: ReturnType<typeof deferredResponse> | null; imported: ReturnType<typeof deferredResponse> | null;
  paths: string[];
}
function installScopeFixture(): ScopeFixture {
  const state: ScopeFixture = { listFault: "none", fixedFault: "none", current: null, list: null, csrf: null, imported: null, paths: [] };
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    const url = new URL(path, "http://127.0.0.1");
    state.paths.push(`${options?.method ?? "GET"} ${url.pathname}`);
    if (url.pathname === "/v1/auth/me") return json({ user_id: "synthetic-scope-admin", tenant_id: fixtureTenant, role: "tenant_admin", permissions: ["read:asset", "write:asset"], permission_version: 1, data_mode: "fixture", csrf_token: "synthetic-scope-memory" });
    if (url.pathname === "/v1/auth/csrf") return state.csrf?.promise ?? json({ csrf_token: "synthetic-scope-memory", header_name: "X-CSRF-Token" });
    if (url.pathname === "/v1/health/live") return json({ status: "live" });
    if (url.pathname === "/v1/health/ready") return json({ status: "ready", reason: "synthetic fixture", dependencies: {} });
    if (url.pathname === "/v1/assets") {
      if (url.searchParams.has("cursor")) {
        if (state.listFault === "503") return json({ error: { code: "inventory_unavailable", retryable: true } }, 503);
        const asset = assetFixture();
        if (state.listFault === "scope") return json({ items: [{ ...asset, tenant_id: "wrong-synthetic-tenant", snapshot: { ...asset.snapshot, tenant_id: "wrong-synthetic-tenant" } }], next_cursor: null });
      }
      return state.list?.promise ?? json({ items: [assetFixture()], next_cursor: "synthetic-scope-next" });
    }
    if (url.pathname === `/v1/assets/${fixtureAssetId}`) return state.current?.promise ?? json(assetFixture());
    if (url.pathname === `/v1/assets/${fixtureAssetId}/snapshots`) return json({ items: [snapshotFixture(), snapshotFixture(1)], next_cursor: null });
    if (url.pathname.endsWith("/snapshots/b0000000-0000-4000-8000-000000000001")) return json({ ...snapshotFixture(1), tenant_id: state.fixedFault === "scope" ? "wrong-synthetic-tenant" : fixtureTenant });
    if (url.pathname === "/v1/asset-imports") return state.imported?.promise ?? json({ asset_id: fixtureAssetId, snapshot: snapshotFixture(), reused: false }, 201);
    throw new Error(`unexpected synthetic scope route: ${url.pathname}`);
  }));
  return state;
}
function prepareSyntheticFile() {
  const raw = '{"format_version":1,"components":[],"inventory_completeness":"unknown"}\r\n';
  const file = new File([raw], "synthetic-private-scope.json", { type: "application/json" });
  Object.defineProperty(file, "text", { value: async () => raw });
  fireEvent.change(screen.getByLabelText("选择本地清单"), { target: { files: [file] } });
  fireEvent.change(screen.getByLabelText("资产名称"), { target: { value: "Synthetic scope input" } });
  fireEvent.change(screen.getByLabelText("输入来源版本"), { target: { value: "synthetic-scope-v1" } });
  fireEvent.change(screen.getByLabelText("实际观察时间（含时区）"), { target: { value: "2026-10-15T10:00:00Z" } });
}
function assertPrivateWorkspaceCleared() {
  expect(screen.queryAllByText(assetFixture().display_name, { exact: true })).toHaveLength(0);
  expect(screen.queryByRole("heading", { name: "当前授权资产" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "快照历史" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "快照 #2" })).toBeNull();
  expect(screen.queryByLabelText("选择本地清单")).toBeNull();
  expect(screen.queryByText("导入成功 · 服务端已保存快照")).toBeNull();
  expect(localStorage.length + sessionStorage.length).toBe(0);
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });

describe("M01 asset scope mismatch · explicit synthetic inputs", () => {
  it("scope contradictions have a distinct local type; ordinary schema failures keep their type", () => {
    for (const parse of [() => parseSnapshot({ ...snapshotFixture(), tenant_id: "wrong-synthetic-tenant" }, fixtureTenant, fixtureAssetId), () => parseSnapshot(snapshotFixture(), fixtureTenant, "a0000000-0000-4000-8000-000000000099"), () => parseAsset({ ...assetFixture(), tenant_id: "wrong-synthetic-tenant" }, fixtureTenant)]) {
      let problem: unknown;
      try { parse(); } catch (failure: unknown) { problem = failure; }
      expect(problem).toBeInstanceOf(ApiProblem);
      expect(problem).toMatchObject({ name: "AssetResponseScopeMismatch", status: 502, code: "invalid_response", retryable: false });
    }
    let ordinaryProblem: unknown;
    try { parseSnapshot({ ...snapshotFixture(), schema_version: "unsupported-synthetic-version" }, fixtureTenant, fixtureAssetId); } catch (failure: unknown) { ordinaryProblem = failure; }
    expect(ordinaryProblem).toMatchObject({ name: "ApiProblem", status: 502, code: "invalid_response", retryable: true });
  });
  it("A: wrong-tenant next catalog page removes all formerly visible private workspace", async () => {
    const state = installScopeFixture(); window.location.hash = "assets"; render(<App />);
    await screen.findByRole("link", { name: new RegExp(assetFixture().display_name) });
    state.listFault = "scope"; fireEvent.click(screen.getByRole("button", { name: "加载更多资产" }));
    await screen.findByRole("alert"); assertPrivateWorkspaceCleared();
  });
  it("B: wrong-tenant fixed history removes catalog, detail, saved receipt and selected File", async () => {
    const state = installScopeFixture(); window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    await screen.findByRole("heading", { name: "快照 #2" }); prepareSyntheticFile();
    await screen.findByText("0 个组件声明"); fireEvent.submit(screen.getByRole("button", { name: "提交授权清单" }).closest("form")!);
    await screen.findByText("导入成功 · 服务端已保存快照");
    await screen.findByRole("button", { name: /查看快照 #1 · 历史/ }); prepareSyntheticFile();
    state.fixedFault = "scope"; fireEvent.click(screen.getByRole("button", { name: /查看快照 #1 · 历史/ }));
    await screen.findByRole("alert"); assertPrivateWorkspaceCleared();
  });
  it("wrong-scope catalog blocks late current read from restoring private state", async () => {
    const state = installScopeFixture(); const current = deferredResponse(); state.current = current;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    await screen.findByRole("button", { name: "加载更多资产" }); state.listFault = "scope";
    fireEvent.click(screen.getByRole("button", { name: "加载更多资产" })); await screen.findByRole("alert");
    await act(async () => current.resolve(json(assetFixture()))); assertPrivateWorkspaceCleared();
  });
  it("wrong-scope fixed history blocks a late catalog response", async () => {
    const state = installScopeFixture(); const list = deferredResponse(); state.list = list;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    await screen.findByRole("button", { name: /查看快照 #1 · 历史/ }); state.fixedFault = "scope";
    fireEvent.click(screen.getByRole("button", { name: /查看快照 #1 · 历史/ })); await screen.findByRole("alert");
    await act(async () => list.resolve(json({ items: [assetFixture()], next_cursor: null }))); assertPrivateWorkspaceCleared();
  });
  it("a late CSRF response cannot start a POST after a scope contradiction", async () => {
    const state = installScopeFixture(); const csrf = deferredResponse(); state.csrf = csrf;
    window.location.hash = "assets"; render(<App />); await screen.findByRole("button", { name: "加载更多资产" });
    prepareSyntheticFile(); await screen.findByText("0 个组件声明"); fireEvent.submit(screen.getByRole("button", { name: "提交授权清单" }).closest("form")!);
    await waitFor(() => expect(state.paths).toContain("GET /v1/auth/csrf")); state.listFault = "scope";
    fireEvent.click(screen.getByRole("button", { name: "加载更多资产" })); await screen.findByRole("alert");
    await act(async () => csrf.resolve(json({ csrf_token: "synthetic-scope-memory", header_name: "X-CSRF-Token" })));
    expect(state.paths.filter((path) => path === "POST /v1/asset-imports")).toHaveLength(0); assertPrivateWorkspaceCleared();
  });
  it("an already submitted late import cannot restore a receipt or navigate after wrong scope", async () => {
    const state = installScopeFixture(); const imported = deferredResponse(); state.imported = imported;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />); await screen.findByRole("heading", { name: "快照 #2" });
    prepareSyntheticFile(); await screen.findByText("0 个组件声明"); fireEvent.submit(screen.getByRole("button", { name: "提交授权清单" }).closest("form")!);
    await waitFor(() => expect(state.paths).toContain("POST /v1/asset-imports")); state.fixedFault = "scope";
    fireEvent.click(screen.getByRole("button", { name: /查看快照 #1 · 历史/ })); await screen.findByRole("alert");
    const resultId = "a0000000-0000-4000-8000-000000000099";
    await act(async () => imported.resolve(json({ asset_id: resultId, snapshot: { ...snapshotFixture(), asset_id: resultId }, reused: false }, 201)));
    expect(window.location.hash).toBe(`#assets/${fixtureAssetId}`); assertPrivateWorkspaceCleared();
  });
  it("ordinary 503 keeps the authorized catalog readable and never expires the session", async () => {
    const state = installScopeFixture(); window.location.hash = "assets"; render(<App />);
    await screen.findByRole("button", { name: "加载更多资产" }); state.listFault = "503";
    fireEvent.click(screen.getByRole("button", { name: "加载更多资产" })); await screen.findByRole("alert");
    expect(screen.getByRole("link", { name: new RegExp(assetFixture().display_name) })).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试资产页" })).toBeTruthy();
    fireEvent.click(screen.getByRole("link", { name: "会话与权限" }));
    expect(await screen.findByRole("button", { name: "退出登录" })).toBeTruthy();
    expect(state.paths.filter((path) => path === "POST /v1/auth/logout")).toHaveLength(0);
  });
});
