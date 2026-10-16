import { randomBytes } from "node:crypto";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../app/auth-session";
import { RecommendationWorkspace, ReportWorkspace } from "./recommendation-workspace";
import { syntheticIds, syntheticRecommendation, syntheticReport, syntheticScope, syntheticSubscription } from "./synthetic-wire-fixtures";

const unavailableAsset = "90000000-0000-4000-8000-000000000099";
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
function installFixture(mode: "recommendations" | "reports" = "recommendations") {
  const nonce = randomBytes(32).toString("hex");
  let completeCatalog: (value: Response) => void = () => { throw new Error("fixture response not initialized"); };
  const catalogResponse = new Promise<Response>((resolve) => { completeCatalog = resolve; });
  const state = { writes: [] as { method: string; path: string; body: unknown }[], subscriptionStatus: 200, subscriptionReads: 0, catalogReads: 0, completeCatalog, catalogResponse };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === "/v1/auth/me") return json({ user_id: syntheticScope.userId, tenant_id: syntheticScope.tenantId, role: "viewer", permission_version: 1, permissions: ["read:public", "read:asset"], data_mode: "fixture", csrf_token: nonce });
    if (path === "/v1/auth/csrf") return json({ csrf_token: nonce, header_name: "X-CSRF-Token" });
    if (init?.method === "PATCH" || init?.method === "POST") {
      const body: unknown = JSON.parse(String(init.body));
      state.writes.push({ method: init.method, path, body });
      return json({ error: { code: "not_found", retryable: false } }, 404);
    }
    if (path.startsWith("/api/v1/subscriptions?")) { state.catalogReads += 1; return state.catalogReads === 1 ? json({ items: [syntheticSubscription()], next_cursor: null }) : catalogResponse; }
    if (path === "/api/v1/subscriptions/" + syntheticIds.subscription) {
      state.subscriptionReads += 1;
      return state.subscriptionStatus === 404 ? json({ error: { code: "not_found", retryable: false } }, 404) : json(syntheticSubscription());
    }
    if (path.includes("/recommendations?")) return json({ items: [syntheticRecommendation()], next_cursor: null });
    if (path.includes("/reports?")) return json({ items: [syntheticReport()], next_cursor: null });
    if (path.startsWith("/api/v1/reports/" + syntheticIds.report + "?")) return json(syntheticReport());
    throw new Error("Unexpected explicit synthetic request " + path);
  }));
  render(<AuthProvider>{mode === "reports" ? <ReportWorkspace /> : <RecommendationWorkspace />}</AuthProvider>);
  return state;
}
async function expectWriteFailure() {
  await screen.findAllByText("记录不存在，或当前会话不能访问该记录。");
  await waitFor(() => expect(screen.getByRole("button", { name: "刷新本人记录" }).hasAttribute("disabled")).toBe(false));
  expect(screen.queryByText(/服务端已保存订阅版本|服务端已创建订阅|服务端已启用订阅|服务端已退订|服务端已完成本次推荐生成|服务端已保存报告|服务端已确认推荐已读/)).toBeNull();
}
function expectOriginalSelection() { expect(screen.getByText("订阅版本 1 · 已启用 · 优先级 P0 至 P3")).toBeTruthy(); }

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("R17 write 404 object semantics · explicit synthetic HTTP only", () => {
  it("preserves both unsaved fields and CAS version after an asset-validation save 404, including a successful direct subscription refresh", async () => {
    const state = installFixture();
    fireEvent.click(await screen.findByRole("button", { name: "编辑当前订阅" }));
    fireEvent.change(screen.getByLabelText("授权资产 UUID（每行一个）"), { target: { value: unavailableAsset } });
    fireEvent.change(screen.getByLabelText("风险主题（每行一个）"), { target: { value: "synthetic-unsaved-topic" } });
    fireEvent.click(screen.getByRole("button", { name: "保存订阅修改" }));
    await expectWriteFailure();
    expectOriginalSelection();
    expect(screen.getByDisplayValue(unavailableAsset)).toBeTruthy();
    expect(screen.getByDisplayValue("synthetic-unsaved-topic")).toBeTruthy();
    expect(state.writes).toHaveLength(1);
    expect(state.writes[0]?.body).toMatchObject({ expected_version: 1, spec: { asset_ids: [unavailableAsset], risk_topics: ["synthetic-unsaved-topic"], enabled: true } });
    expect(state.subscriptionReads).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await waitFor(() => expect(state.subscriptionReads).toBe(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "保存订阅修改" }).hasAttribute("disabled")).toBe(false));
    expectOriginalSelection();
    expect(screen.getByDisplayValue(unavailableAsset)).toBeTruthy();
    expect(screen.getByDisplayValue("synthetic-unsaved-topic")).toBeTruthy();
    expect(state.writes).toHaveLength(1);
  });

  it("keeps a failed create draft and the prior subscription results", async () => {
    const state = installFixture();
    await screen.findByRole("button", { name: "标记已读" });
    fireEvent.click(screen.getByRole("button", { name: "新建订阅" }));
    fireEvent.change(screen.getByLabelText("产品关注（每行一个）"), { target: { value: "synthetic-create-product" } });
    fireEvent.change(screen.getByLabelText("授权资产 UUID（每行一个）"), { target: { value: unavailableAsset } });
    fireEvent.click(screen.getByRole("button", { name: "创建本人订阅" }));
    await expectWriteFailure();
    expectOriginalSelection();
    expect(screen.getByDisplayValue("synthetic-create-product")).toBeTruthy();
    expect(screen.getByDisplayValue(unavailableAsset)).toBeTruthy();
    expect(screen.getByRole("button", { name: "标记已读" })).toBeTruthy();
    expect(state.writes[0]).toMatchObject({ method: "POST", path: "/api/v1/subscriptions" });
    expect(state.subscriptionReads).toBe(0);
  });

  it.each(["toggle", "generate", "read"] as const)("keeps the subscription and existing recommendation after a %s write 404", async (operation) => {
    const state = installFixture();
    await screen.findByRole("button", { name: "标记已读" });
    const action = operation === "toggle" ? "退订并保留历史" : operation === "generate" ? "生成当前推荐" : "标记已读";
    fireEvent.click(screen.getByRole("button", { name: action }));
    await expectWriteFailure();
    expectOriginalSelection();
    if (operation === "read") {
      expect(screen.queryByRole("button", { name: "标记已读" })).toBeNull();
      expect(screen.getByText("部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。")).toBeTruthy();
    } else expect(screen.getByRole("button", { name: "标记已读" }).hasAttribute("disabled")).toBe(false);
    expect(state.writes).toHaveLength(1);
    expect(state.subscriptionReads).toBe(0);
  });

  it("preserves the selected report and generation input after report creation 404", async () => {
    const state = installFixture("reports");
    fireEvent.click(await screen.findByRole("button", { name: new RegExp(syntheticIds.report) }));
    await screen.findByRole("heading", { name: "报告内容与当前状态" });
    fireEvent.change(screen.getByLabelText("既有生成批次 UUID"), { target: { value: syntheticIds.generation } });
    fireEvent.click(screen.getByRole("button", { name: "保存日周报告" }));
    await expectWriteFailure();
    expectOriginalSelection();
    expect(screen.getByDisplayValue(syntheticIds.generation)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "报告内容与当前状态" })).toBeTruthy();
    expect(state.writes).toHaveLength(1);
    expect(state.subscriptionReads).toBe(0);
  });

  it("still withdraws only after a direct subscription GET 404 and rejects its preceding catalog response", async () => {
    const state = installFixture();
    fireEvent.click(await screen.findByRole("button", { name: "编辑当前订阅" }));
    fireEvent.change(screen.getByLabelText("风险主题（每行一个）"), { target: { value: "synthetic-draft-before-read-revocation" } });
    state.subscriptionStatus = 404;
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await screen.findByText("记录不存在，或当前会话不能访问该记录。");
    await act(async () => { state.completeCatalog(json({ items: [syntheticSubscription()], next_cursor: null })); await state.catalogResponse; });
    expect(state.subscriptionReads).toBe(1);
    expect(state.writes).toHaveLength(0);
    expect(screen.queryByRole("button", { name: "生成当前推荐" })).toBeNull();
    expect(screen.queryByDisplayValue("synthetic-draft-before-read-revocation")).toBeNull();
    expect(screen.getByRole("heading", { name: "选择或创建本人订阅" })).toBeTruthy();
  });
});
