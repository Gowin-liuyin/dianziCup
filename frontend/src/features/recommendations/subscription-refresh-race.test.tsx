import { randomBytes } from "node:crypto";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../app/auth-session";
import { RecommendationWorkspace } from "./recommendation-workspace";
import { syntheticIds, syntheticRecommendation, syntheticScope, syntheticSubscription } from "./synthetic-wire-fixtures";

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
function deferred() {
  let resolve: (value: Response) => void = () => { throw new Error("synthetic response not initialized"); };
  const promise = new Promise<Response>((complete) => { resolve = complete; });
  return { promise, resolve };
}
function installRace() {
  const nonce = randomBytes(32).toString("hex");
  const state = { catalog: deferred(), single: deferred(), patch: deferred(), followingCatalog: deferred(), catalogCount: 0, writes: [] as string[] };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (init?.method && init.method !== "GET") state.writes.push(`${init.method} ${path}`);
    if (path === "/v1/auth/me") return json({ user_id: syntheticScope.userId, tenant_id: syntheticScope.tenantId, role: "viewer", permission_version: 1, permissions: ["read:public", "read:asset"], data_mode: "fixture", csrf_token: nonce });
    if (path === "/v1/auth/csrf") return json({ csrf_token: nonce, header_name: "X-CSRF-Token" });
    if (path.startsWith("/api/v1/subscriptions?")) {
      state.catalogCount += 1;
      if (state.catalogCount === 1) return json({ items: [syntheticSubscription()], next_cursor: null });
      return state.catalogCount === 2 ? state.catalog.promise : state.followingCatalog.promise;
    }
    if (path === `/api/v1/subscriptions/${syntheticIds.subscription}`) return init?.method === "PATCH" ? state.patch.promise : state.single.promise;
    if (path.includes("/recommendations?")) return json({ items: [syntheticRecommendation()], next_cursor: null });
    throw new Error(`Unexpected explicit synthetic request ${path}`);
  }));
  render(<AuthProvider><RecommendationWorkspace /></AuthProvider>);
  return state;
}
async function settle(response: ReturnType<typeof deferred>, body: unknown, status = 200) {
  await act(async () => { response.resolve(json(body, status)); await response.promise; });
}
async function expectRefreshReady() {
  await waitFor(() => expect(screen.getByRole("button", { name: "刷新本人记录" }).hasAttribute("disabled")).toBe(false));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("R17 subscription response ordering · explicit synthetic HTTP only", () => {
  it("keeps the catalog version and CAS draft when an older single read arrives later", async () => {
    const state = installRace();
    fireEvent.click(await screen.findByRole("button", { name: "编辑当前订阅" }));
    fireEvent.change(screen.getByLabelText("风险主题（每行一个）"), { target: { value: "synthetic-retained-race-draft" } });
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await settle(state.catalog, { items: [syntheticSubscription(2, false)], next_cursor: null });
    await screen.findByText("订阅版本 2 · 已退订，历史保留 · 优先级 P0 至 P3");
    await settle(state.single, syntheticSubscription());
    await expectRefreshReady();
    expect(screen.getByText("订阅版本 2 · 已退订，历史保留 · 优先级 P0 至 P3")).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成当前推荐" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "保留输入，采用版本 2" })).toBeTruthy();
    expect(screen.getByDisplayValue("synthetic-retained-race-draft")).toBeTruthy();
    expect(state.writes).toHaveLength(0);
  });

  it("keeps a newer single read in the directory and when the directory row is selected again", async () => {
    const state = installRace();
    await screen.findByRole("button", { name: "生成当前推荐" });
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await settle(state.single, syntheticSubscription(2, false));
    await expectRefreshReady();
    await settle(state.catalog, { items: [syntheticSubscription()], next_cursor: null });
    const catalog = screen.getByRole("complementary", { name: "本人订阅" });
    fireEvent.click(within(catalog).getByRole("button", { name: new RegExp(syntheticIds.subscription) }));
    expect(screen.getByText("订阅版本 2 · 已退订，历史保留 · 优先级 P0 至 P3")).toBeTruthy();
    expect(within(catalog).getByText("版本 2 · 已退订 · P0 至 P3")).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成当前推荐" }).hasAttribute("disabled")).toBe(true);
    expect(state.writes).toHaveLength(0);
  });

  it("does not revive an inaccessible subscription from the preceding catalog request", async () => {
    const state = installRace();
    await screen.findByRole("button", { name: "生成当前推荐" });
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await settle(state.single, { error: { code: "not_found", retryable: false } }, 404);
    await expectRefreshReady();
    await settle(state.catalog, { items: [syntheticSubscription()], next_cursor: null });
    expect(screen.queryByRole("button", { name: "生成当前推荐" })).toBeNull();
    expect(screen.getByRole("heading", { name: "选择或创建本人订阅" })).toBeTruthy();
    expect(screen.getByText("记录不存在，或当前会话不能访问该记录。")).toBeTruthy();
    expect(state.writes).toHaveLength(0);
  });

  it.each(["toggle", "edit"] as const)("keeps the current version when a prior %s receipt arrives after a newer catalog record", async (operation) => {
    const state = installRace();
    await screen.findByRole("button", { name: "生成当前推荐" });
    if (operation === "edit") fireEvent.click(screen.getByRole("button", { name: "编辑当前订阅" }));
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await settle(state.single, syntheticSubscription());
    await expectRefreshReady();
    fireEvent.click(screen.getByRole("button", { name: operation === "toggle" ? "退订并保留历史" : "保存订阅修改" }));
    await waitFor(() => expect(state.writes).toHaveLength(1));
    await settle(state.catalog, { items: [syntheticSubscription(3, false)], next_cursor: null });
    await screen.findByText("订阅版本 3 · 已退订，历史保留 · 优先级 P0 至 P3");
    await settle(state.patch, syntheticSubscription(2, false));
    await expectRefreshReady();
    expect(screen.getByText("订阅版本 3 · 已退订，历史保留 · 优先级 P0 至 P3")).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成当前推荐" }).hasAttribute("disabled")).toBe(true);
    await settle(state.followingCatalog, { items: [syntheticSubscription(3, false)], next_cursor: null });
  });
});
