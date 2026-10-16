import { randomBytes } from "node:crypto";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../app/auth-session";
import { RecommendationWorkspace } from "./recommendation-workspace";
import { syntheticIds, syntheticRecommendation, syntheticScope, syntheticSubscription } from "./synthetic-wire-fixtures";

const rejectedQuote = "Explicit synthetic quote; <script>not executable</script>.";
const otherSubscriptionId = "a0000000-0000-4000-8000-000000000002";
const otherQuote = "Explicit synthetic other recommendation quote.";
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
function deferred() {
  let resolve: (value: Response) => void = () => { throw new Error("fixture response not initialized"); };
  const promise = new Promise<Response>((complete) => { resolve = complete; });
  return { promise, resolve };
}
function installFixture(includeOtherSubscription = false) {
  const nonce = randomBytes(32).toString("hex");
  const original = syntheticRecommendation();
  const other = { ...syntheticRecommendation(), recommendation_id: "e0000000-0000-4000-8000-000000000002", content: { ...original.content, key: { ...original.content.key, event_id: "b0000000-0000-4000-8000-000000000002" }, reasons: original.content.reasons.map((reason) => ({ ...reason, citations: reason.citations.map((citation) => ({ ...citation, quote: otherQuote })) })) } };
  const page = { items: [original, other], next_cursor: null };
  const subscriptions = { items: includeOtherSubscription ? [syntheticSubscription(), { ...syntheticSubscription(), subscription_id: otherSubscriptionId, spec: { ...syntheticSubscription().spec, product_keys: ["synthetic-other-subscription"] } }] : [syntheticSubscription()], next_cursor: null };
  const state = { read: deferred(), previousList: deferred(), recommendationReads: 0, writes: [] as string[] };
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path === "/v1/auth/me") return json({ user_id: syntheticScope.userId, tenant_id: syntheticScope.tenantId, role: "viewer", permission_version: 1, permissions: ["read:public", "read:asset"], data_mode: "fixture", csrf_token: nonce });
    if (path === "/v1/auth/csrf") return json({ csrf_token: nonce, header_name: "X-CSRF-Token" });
    if (init?.method === "POST" && path === "/api/v1/recommendations/" + syntheticIds.recommendation + "/read?subscription_id=" + syntheticIds.subscription) { state.writes.push(path); return state.read.promise; }
    if (path.startsWith("/api/v1/subscriptions?")) return json(subscriptions);
    if (path === "/api/v1/subscriptions/" + syntheticIds.subscription) return json(syntheticSubscription());
    if (path.includes(otherSubscriptionId + "/recommendations?")) return json({ error: { code: "dependency_unavailable", retryable: true } }, 503);
    if (path.includes("/recommendations?")) {
      state.recommendationReads += 1;
      if (state.recommendationReads === 2) return state.previousList.promise;
      if (state.recommendationReads === 3) return json({ error: { code: "not_found", retryable: false } }, 404);
      return json(page);
    }
    throw new Error("Unexpected explicit synthetic request " + path);
  }));
  render(<AuthProvider><RecommendationWorkspace /></AuthProvider>);
  return state;
}
async function targetReadButton() {
  const quote = await screen.findByText(rejectedQuote);
  const item = quote.closest(".recommendation-list > li");
  if (!(item instanceof HTMLElement)) throw new Error("recommendation item missing");
  return within(item).getByRole("button", { name: "标记已读" });
}
async function rejectRead(state: ReturnType<typeof installFixture>) {
  await waitFor(() => expect(state.writes).toHaveLength(1));
  await act(async () => { state.read.resolve(json({ error: { code: "not_found", retryable: false } }, 404)); await state.read.promise; });
  await screen.findAllByText("记录不存在，或当前会话不能访问该记录。");
  await waitFor(() => expect(screen.getByRole("button", { name: "刷新本人记录" }).hasAttribute("disabled")).toBe(false));
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("R17 recommendation current-access rejection · synthetic HTTP only", () => {
  it("hides only the rejected recommendation while preserving another recommendation, subscription and unsaved draft", async () => {
    const state = installFixture();
    const read = await targetReadButton();
    fireEvent.click(screen.getByRole("button", { name: "编辑当前订阅" }));
    fireEvent.change(screen.getByLabelText("风险主题（每行一个）"), { target: { value: "synthetic-preserved-draft-after-read-404" } });
    fireEvent.click(read);
    await rejectRead(state);
    expect(screen.queryByText(rejectedQuote)).toBeNull();
    expect(screen.getByText(otherQuote)).toBeTruthy();
    expect(screen.getByText("订阅版本 1 · 已启用 · 优先级 P0 至 P3")).toBeTruthy();
    expect(screen.getByDisplayValue("synthetic-preserved-draft-after-read-404")).toBeTruthy();
    expect(screen.getByText("部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "标记已读" })).toHaveLength(1);
  });

  it("rejects an in-flight old page, keeps a fresh 404 hidden, and restores content only after an explicit fresh successful list read", async () => {
    const state = installFixture();
    const read = await targetReadButton();
    const refresh = screen.getByRole("button", { name: "刷新本人记录" });
    act(() => { fireEvent.click(refresh); fireEvent.click(read); });
    await waitFor(() => expect(state.recommendationReads).toBe(2));
    await rejectRead(state);
    await act(async () => { state.previousList.resolve(json({ items: [syntheticRecommendation()], next_cursor: null })); await state.previousList.promise; });
    expect(screen.queryByText(rejectedQuote)).toBeNull();
    expect(screen.queryByText("本页未返回推荐")).toBeNull();
    expect(screen.getByText("订阅版本 1 · 已启用 · 优先级 P0 至 P3")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await waitFor(() => expect(state.recommendationReads).toBe(3));
    await screen.findAllByText("记录不存在，或当前会话不能访问该记录。");
    expect(screen.queryByText(rejectedQuote)).toBeNull();
    await waitFor(() => expect(screen.getByRole("button", { name: "刷新本人记录" }).hasAttribute("disabled")).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "刷新本人记录" }));
    await waitFor(() => expect(state.recommendationReads).toBe(4));
    await screen.findByText(rejectedQuote);
    expect(screen.getByText(otherQuote)).toBeTruthy();
    expect(screen.queryByText("部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。")).toBeNull();
    expect(state.writes).toHaveLength(1);
  });
  it("does not carry another subscription access boundary into a selected subscription whose fresh list fails", async () => {
    const state = installFixture(true);
    fireEvent.click(await targetReadButton());
    await rejectRead(state);
    expect(screen.getByText("部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。")).toBeTruthy();
    const catalog = screen.getByRole("complementary", { name: "本人订阅" });
    fireEvent.click(within(catalog).getByRole("button", { name: new RegExp(otherSubscriptionId) }));
    await screen.findByRole("alert");
    expect(within(screen.getByRole("region", { name: "本人推荐" })).getByText(otherSubscriptionId, { selector: "code" })).toBeTruthy();
    expect(screen.queryByText("部分推荐当前不可读取，已隐藏其内容；这不表示没有风险。")).toBeNull();
    expect(screen.queryByText(rejectedQuote)).toBeNull();
    expect(state.writes).toHaveLength(1);
  });

});
