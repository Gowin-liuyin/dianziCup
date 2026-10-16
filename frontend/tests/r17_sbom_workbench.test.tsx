import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { SbomDetail } from "../src/features/assets/sbom-detail";
import { fixtureAssetId, fixtureTenant } from "../src/features/assets/synthetic-fixtures";
import { sbomAsset, sbomFixture, sbomSnapshot } from "./r17_sbom_fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function deferred() {
  let release: (response: Response) => void = () => { throw new Error("synthetic response uninitialized"); };
  const promise = new Promise<Response>((resolve) => { release = resolve; });
  return { promise, release };
}
function installFixture() {
  const state = { status: 200, sidecar: sbomFixture(), sidecarDeferred: null as Promise<Response> | null, currentDeferred: null as Promise<Response> | null, historyDeferred: null as Promise<Response> | null, paths: [] as string[], authenticated: true };
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    const url = new URL(path, "http://synthetic.invalid"); state.paths.push(url.pathname);
    if (url.pathname === "/v1/auth/me") return response({ user_id: "synthetic-sbom-admin", tenant_id: fixtureTenant, role: "tenant_admin", permissions: ["read:asset", "write:asset"], permission_version: 1, data_mode: "fixture", csrf_token: "synthetic-sbom-memory" });
    if (url.pathname === "/v1/health/live") return response({ status: "live" });
    if (url.pathname === "/v1/health/ready") return response({ status: "ready", reason: "synthetic fixture", dependencies: {} });
    if (url.pathname === "/v1/assets") return response({ items: [sbomAsset()], next_cursor: null });
    if (url.pathname === `/v1/assets/${fixtureAssetId}`) return state.currentDeferred ?? response(sbomAsset());
    if (url.pathname === `/v1/assets/${fixtureAssetId}/snapshots`) return state.historyDeferred ?? response({ items: [sbomSnapshot(), sbomSnapshot(1)], next_cursor: null });
    if (url.pathname.endsWith("/sbom")) {
      if (url.pathname.includes(sbomSnapshot(1).snapshot_id)) return response(sbomFixture(1));
      return state.sidecarDeferred ?? response(state.status === 200 ? state.sidecar : { error: { code: state.status === 401 ? "session_expired" : state.status === 403 ? "permission_denied" : "inventory_unavailable", retryable: state.status === 503 } }, state.status);
    }
    if (url.pathname.endsWith(sbomSnapshot(1).snapshot_id)) return response(sbomSnapshot(1));
    throw new Error(`unexpected synthetic SBOM route ${url.pathname}`);
  }));
  return state;
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.location.hash = ""; });
describe("R17 SBOM workbook behavior · explicitly synthetic", () => {
  it("uses the real fixed endpoint and keeps composition complete separate from inventory unknown", async () => {
    const state = installFixture(); window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    await screen.findByText(sbomFixture().combined_semantic_sha256);
    const sbom = screen.getByRole("region", { name: "固定快照 SBOM 声明" });
    expect(within(sbom).getByText("complete")).toBeTruthy();
    expect(within(sbom).getByText(/此声明不证明授权资产安装范围完整/)).toBeTruthy();
    expect(screen.getAllByText("完整性未知").length).toBeGreaterThan(0);
    expect(state.paths).toContain(`/v1/assets/${fixtureAssetId}/snapshots/${sbomSnapshot().snapshot_id}/sbom`);
  });
  it.each([401, 403])("HTTP %i clears formerly visible private asset and upload DOM", async (status) => {
    const state = installFixture(); const sidecar = deferred(); state.sidecarDeferred = sidecar.promise;
    const history = deferred(); state.historyDeferred = history.promise;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />); await screen.findByRole("heading", { name: "快照 #2" });
    await act(async () => sidecar.release(response({ error: { code: status === 401 ? "session_expired" : "permission_denied", retryable: false } }, status)));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "当前授权资产" })).toBeNull());
    await act(async () => history.release(response({ items: [sbomSnapshot()], next_cursor: null })));
    expect(screen.queryByLabelText("选择本地清单")).toBeNull(); expect(screen.queryByText(sbomAsset().display_name)).toBeNull();
  });
  it.each(["tenant_id", "asset_id", "snapshot_id", "unsafe_uri", "extra_raw"])("SBOM %s violation clears workspace and a late history response cannot restore it", async (fault) => {
    const state = installFixture(); const sidecar = deferred(); state.sidecarDeferred = sidecar.promise;
    const history = deferred(); state.historyDeferred = history.promise;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />); await screen.findByRole("heading", { name: "快照 #2" });
    const result = fault === "unsafe_uri" ? { ...sbomFixture(), external_documents: [{ document_ref: "DocumentRef-Synthetic", document_uri: "file:///private/synthetic", checksum: { algorithm: "SHA256", checksum_value: "a".repeat(64), source_field_locator: "/externalDocumentRefs/0/checksum" }, source_field_locator: "/externalDocumentRefs/0" }] } : { ...sbomFixture(), [fault === "extra_raw" ? "raw_input" : fault]: "synthetic-private-value" };
    await act(async () => sidecar.release(response(result)));
    await screen.findByRole("alert");
    await act(async () => history.release(response({ items: [sbomSnapshot(), sbomSnapshot(1)], next_cursor: null })));
    expect(screen.queryByRole("heading", { name: "当前授权资产" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "快照历史" })).toBeNull();
    expect(screen.queryByLabelText("选择本地清单")).toBeNull();
    expect(document.body.textContent).not.toContain("synthetic-private-value"); expect(document.body.textContent).not.toContain("file:///private/synthetic");
    expect(localStorage.length + sessionStorage.length).toBe(0);
  });
  it("historical selection binds the old sidecar; a late current reply is discarded", async () => {
    const state = installFixture(); const sidecar = deferred(); state.sidecarDeferred = sidecar.promise;
    window.location.hash = `assets/${fixtureAssetId}`; render(<App />); await screen.findByRole("button", { name: /查看快照 #1 · 历史/ });
    fireEvent.click(screen.getByRole("button", { name: /查看快照 #1 · 历史/ }));
    await screen.findByText(sbomFixture(1).combined_semantic_sha256);
    await act(async () => sidecar.release(response(sbomFixture())));
    expect(screen.queryByText(sbomFixture().combined_semantic_sha256)).toBeNull();
    expect(screen.getByText(sbomFixture(1).combined_semantic_sha256)).toBeTruthy();
    expect(screen.getByText(/正在查看历史快照/)).toBeTruthy();
  });
  it.each([404, 503])("sidecar HTTP %i keeps current authorized inventory and exposes the partial failure", async (status) => {
    const state = installFixture(); state.status = status; window.location.hash = `assets/${fixtureAssetId}`; render(<App />);
    await screen.findByRole("heading", { name: "快照 #2" });
    if (status === 503) { await screen.findByRole("button", { name: "重试固定 SBOM 声明" }); state.status = 200; fireEvent.click(screen.getByRole("button", { name: "重试固定 SBOM 声明" })); await screen.findByText(sbomFixture().combined_semantic_sha256); }
    else await screen.findByText(/该快照的 SBOM 声明不可用或无权读取/);
    expect(screen.getByRole("heading", { name: "当前授权资产" })).toBeTruthy(); expect(screen.queryByText("安全", { exact: true })).toBeNull();
  });
  it("renders only 20 of 10000 relation rows and page controls preserve the declaration count", async () => {
    const fixture = sbomFixture(); fixture.dependency_edges = Array.from({ length: 10000 }, (_, index) => ({ source_ref: "synthetic-root", target_ref: `synthetic-child-${index}`, relationship: "dependsOn", source_field_locator: `/dependencies/0/dependsOn/${index}` }));
    vi.stubGlobal("fetch", vi.fn(async () => response(fixture)));
    render(<SbomDetail tenant={fixtureTenant} snapshot={sbomSnapshot()} isCurrent={() => true} onFailure={vi.fn()} />);
    const table = await screen.findByRole("table", { name: "SBOM 原始关系声明" });
    expect(within(table).getAllByRole("row")).toHaveLength(21); expect(screen.queryByText("synthetic-child-20", { exact: true })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "下一页依赖与标准关系" }));
    expect(screen.getByText("synthetic-child-20", { exact: true })).toBeTruthy(); expect(within(table).getAllByRole("row")).toHaveLength(21);
  });
});
