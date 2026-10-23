import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { AuthProvider, useAuthSession } from "../../app/auth-session";
import { QuestionWorkspace } from "./question-workspace";
import { questionAnswerFixture, questionFixtureIds as ids } from "./question.fixture";

const csrf = randomBytes(32).toString("hex");
const fixtureUser = { user_id: "isolated-question-user", tenant_id: "isolated-question-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function deferredResponse() { let resolve: (value: Response) => void = () => { throw new Error("deferred fixture not initialized"); }; const promise = new Promise<Response>((release) => { resolve = release; }); return { promise, resolve }; }
function fixtureApi(options: { anonymous?: boolean; denied?: boolean; mode?: string; unknownPost?: boolean; code?: string; status?: number; wire?: unknown; csrfResponse?: Promise<Response>; answerResponse?: Promise<Response> } = {}) {
  const requests: { path: string; options: RequestInit }[] = [];
  let writes = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input); requests.push({ path, options: init });
    if (path === "/v1/auth/me") return options.anonymous ? response({ error: { code: "session_expired" } }, 401) : response({ ...fixtureUser, permissions: options.denied ? [] : fixtureUser.permissions, data_mode: options.mode ?? "fixture" });
    if (path === "/v1/auth/csrf") return options.csrfResponse ?? response({ csrf_token: csrf, header_name: "X-CSRF-Token" });
    if (path === "/v1/auth/logout") return response({ status: "logged_out" });
    if (path === "/v1/health/live") return response({ status: "live" });
    if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
    if (path === "/v1/questions" || path.startsWith("/v1/answers/")) {
      if (path === "/v1/questions") { writes += 1; if (options.unknownPost && writes === 1) throw new Error("private upstream fixture secret ignored"); }
      if (options.status) return response({ type: "about:blank", title: "private error", status: options.status, error: { code: options.code ?? "isolated_failure", retryable: true, message: "private stack ignored" } }, options.status);
      return options.answerResponse ?? response(options.wire === undefined ? questionAnswerFixture() : options.wire);
    }
    throw new Error(`Unexpected isolated route: ${path}`);
  }));
  window.history.replaceState(null, "", `/#questions/${ids.event}`);
  return requests;
}
async function formReady() { await screen.findByRole("button", { name: "提交问题" }); }
function fillQuestion(value = "请核对风险机制") { fireEvent.change(screen.getByLabelText("你的问题"), { target: { value } }); }
function submitForm() { fireEvent.submit(screen.getByRole("form", { name: "单事件问答" })); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

describe("question workspace — isolated fixture, not live", () => {
  it.each([{ anonymous: true, title: "登录后使用证据问答" }, { denied: true, title: "没有问答访问权限" }])("makes no question request without authorized session: $title", async ({ title, ...options }) => {
    const requests = fixtureApi(options); render(<App />); await screen.findByRole("heading", { name: title });
    expect(requests.some((request) => request.path === "/v1/questions" || request.path === "/v1/auth/csrf" || request.path.startsWith("/v1/answers"))).toBe(false);
  });
  it("renders the empty state and validates input without a CSRF request", async () => {
    const requests = fixtureApi(); render(<App />); await formReady();
    expect(screen.getByRole("heading", { name: "尚未提出问题" })).toBeTruthy();
    submitForm(); await screen.findByText(/请求未通过校验/);
    expect(requests.some((request) => request.path === "/v1/auth/csrf")).toBe(false);
  });
  it("submits single-event library exactly once on double submit, shows separated claims and fixed evidence", async () => {
    const delayed = deferredResponse(); const requests = fixtureApi({ csrfResponse: delayed.promise }); render(<App />); await formReady(); fillQuestion(); submitForm(); submitForm();
    await screen.findByText(/正在提交问题并等待完整回答/);
    expect(screen.getByRole("button", { name: "等待完整回答…" }).hasAttribute("disabled")).toBe(true);
    delayed.resolve(response({ csrf_token: csrf, header_name: "X-CSRF-Token" }));
    await screen.findByRole("article", { name: "完整证据回答" });
    const posts = requests.filter((request) => request.path === "/v1/questions"); expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0]?.options.body))).toEqual({ question: "请核对风险机制", mode: "library", event_ids: [ids.event] });
    expect(screen.getByText("1234 毫秒 · 完整回答耗时")).toBeTruthy();
    for (const label of ["来源事实", "规则结论", "项目建议"]) expect(screen.getByRole("region", { name: label })).toBeTruthy();
    expect(screen.getByRole("link", { name: "检视固定修订证据 [1] →" }).getAttribute("href")).toBe(`#events/${ids.event}/evidence/${ids.evidence}/revision/${ids.revision}`);
    expect(screen.getByRole("link", { name: "打开来源原文 [1] ↗" }).getAttribute("rel")).toBe("noopener noreferrer");
    fireEvent.click(screen.getAllByRole("link", { name: "依据 [1]" })[0] ?? screen.getByRole("link", { name: "打开来源原文 [1] ↗" }));
    expect(document.activeElement?.id).toBe(`citation-${ids.evidence}`);
  });
  it("retries unknown result with identical key/body, new question explicitly changes key", async () => {
    const requests = fixtureApi({ unknownPost: true }); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByText(/提交结果未确认/);
    expect(screen.getByLabelText("你的问题").hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "原样重试本轮" })); await screen.findByRole("article", { name: "完整证据回答" });
    let posts = requests.filter((request) => request.path === "/v1/questions"); expect(posts[1]?.options.body).toBe(posts[0]?.options.body);
    expect(new Headers(posts[1]?.options.headers).get("Idempotency-Key")).toBe(new Headers(posts[0]?.options.headers).get("Idempotency-Key"));
    expect(screen.queryByText(/private upstream/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "开始新问题" })); fillQuestion("新的隔离问题"); submitForm(); await screen.findByRole("article", { name: "完整证据回答" });
    posts = requests.filter((request) => request.path === "/v1/questions"); expect(posts).toHaveLength(3);
    expect(new Headers(posts[2]?.options.headers).get("Idempotency-Key")).not.toBe(new Headers(posts[0]?.options.headers).get("Idempotency-Key"));
  });
  it("blocks lookup and repeated submits while the paid write response is pending", async () => {
    const delayed = deferredResponse(); const requests = fixtureApi({ answerResponse: delayed.promise }); render(<App />); await formReady(); fillQuestion(); submitForm();
    await screen.findByText(/正在提交问题并等待完整回答/);
    fireEvent.change(screen.getByLabelText("回答标识"), { target: { value: ids.answer } }); fireEvent.submit(screen.getByRole("form", { name: "查询已保存回答" })); submitForm();
    delayed.resolve(response(questionAnswerFixture())); await screen.findByRole("article", { name: "完整证据回答" });
    expect(requests.filter((request) => request.path === "/v1/questions")).toHaveLength(1); expect(requests.some((request) => request.path.startsWith("/v1/answers/"))).toBe(false);
  });
  it.each([{ status: 403, code: "csrf_rejected", message: "会话写入校验未通过" }, { status: 403, code: "permission_denied", message: "没有问答或回答查看权限" }, { status: 404, code: "not_found", message: "回答不存在" }, { status: 409, code: "answer_in_progress", message: "仍在处理中" }, { status: 409, code: "answer_failed", message: "同一请求已失败" }, { status: 409, code: "idempotency_conflict", message: "请求键发生冲突" }, { status: 422, code: "question_scope_not_supported", message: "超出单事件问答的范围" }, { status: 429, code: "question_capacity_busy", message: "繁忙或已达到限额" }, { status: 503, code: "question_models_not_configured", message: "生成模型尚未配置" }, { status: 503, code: "answer_evidence_unavailable", message: "合法证据不足" }, { status: 503, code: "answer_evidence_changed", message: "依赖证据已变化" }, { status: 503, code: "question_model_unavailable", message: "模型或证据服务暂不可用" }])("keeps $status/$code explicit and never generates fake success", async ({ message, ...options }) => {
    const requests = fixtureApi(options); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByText(new RegExp(message));
    expect(screen.queryByRole("article", { name: "完整证据回答" })).toBeNull(); expect(screen.queryByText(/private stack/)).toBeNull();
    expect(requests.filter((request) => request.path === "/v1/questions")).toHaveLength(1);
  });
  it("clears the session after 401 and removes all frozen private fields", async () => {
    fixtureApi({ status: 401, code: "session_expired" }); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByRole("heading", { name: "登录后使用证据问答" });
    expect(screen.getByText("会话已失效，请重新登录。")).toBeTruthy();
    expect(screen.queryByLabelText("你的问题")).toBeNull(); expect(screen.queryByText(/question-ui-/)).toBeNull();
  });
  it.each(["submit", "lookup"] as const)("clears private question state and stops requests after business 403 during %s", async (action) => {
    const apiOptions: { status?: number; code?: string } = {};
    const requests = fixtureApi(apiOptions); render(<App />); await formReady();
    fillQuestion("权限撤回后的私有问题");
    if (action === "lookup") {
      submitForm(); await screen.findByRole("article", { name: "完整证据回答" });
    }
    apiOptions.status = 403; apiOptions.code = "permission_denied";
    if (action === "submit") submitForm();
    else fireEvent.submit(screen.getByRole("form", { name: "查询已保存回答" }));
    await screen.findByRole("heading", { name: "问答访问已暂停" });
    expect(screen.queryByLabelText("你的问题")).toBeNull();
    expect(screen.queryByLabelText("回答标识")).toBeNull();
    expect(screen.queryByText("权限撤回后的私有问题")).toBeNull();
    expect(screen.queryByText(/question-ui-/)).toBeNull();
    expect(screen.queryByRole("article", { name: "完整证据回答" })).toBeNull();
    expect(screen.queryByRole("button", { name: "原样重试本轮" })).toBeNull();
    expect(screen.getByRole("link", { name: "重新核对会话与权限" }).getAttribute("href")).toBe("#session");
    const privateRequests = requests.filter((request) => request.path === "/v1/questions" || request.path.startsWith("/v1/answers/"));
    expect(privateRequests).toHaveLength(action === "submit" ? 1 : 2);
  });
  it("retains the frozen request for CSRF 403 and retries with the same body and key", async () => {
    const apiOptions: { status?: number; code?: string } = { status: 403, code: "csrf_rejected" };
    const requests = fixtureApi(apiOptions); render(<App />); await formReady(); fillQuestion(); submitForm();
    await screen.findByText(/会话写入校验未通过/);
    expect(screen.queryByRole("heading", { name: "问答访问已暂停" })).toBeNull();
    expect(screen.getByLabelText("你的问题").hasAttribute("disabled")).toBe(true);
    apiOptions.status = undefined;
    fireEvent.click(screen.getByRole("button", { name: "原样重试本轮" }));
    await screen.findByRole("article", { name: "完整证据回答" });
    const posts = requests.filter((request) => request.path === "/v1/questions");
    expect(posts).toHaveLength(2);
    expect(posts[1]?.options.body).toBe(posts[0]?.options.body);
    expect(new Headers(posts[1]?.options.headers).get("Idempotency-Key")).toBe(new Headers(posts[0]?.options.headers).get("Idempotency-Key"));
  });
  it.each(["stale", "unknown"])("renders limited coverage and %s without asserting current success", async (freshness) => {
    fixtureApi({ wire: { ...questionAnswerFixture(), freshness } }); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByRole("article", { name: "完整证据回答" });
    expect(screen.getByText(/隔离测试没有资产快照/)).toBeTruthy(); expect(screen.getByText(freshness === "stale" ? /这是已过期回答/ : /服务未确认该回答的当前性/)).toBeTruthy();
  });
  it.each([null, { ...questionAnswerFixture(), claims: [{ text: "invented", kind: "source_fact", support_ids: [ids.other] }] }, { ...questionAnswerFixture(), citations: [{ ...questionAnswerFixture().citations[0], source_uri: "javascript:alert(1)" }] }])("rejects unsafe wire without answering %#", async (wire) => {
    fixtureApi({ wire }); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByText(/提交结果未确认/); expect(screen.queryByRole("article", { name: "完整证据回答" })).toBeNull();
  });
  it("does not label fixture answers as live even if the authenticated snapshot is live", async () => {
    fixtureApi({ mode: "live" }); render(<App />); await formReady(); fillQuestion(); submitForm(); await screen.findByText(/提交结果未确认/); expect(screen.queryByRole("article", { name: "完整证据回答" })).toBeNull();
  });
  it("queries saved answers with GET, no CSRF or model POST, and does not invent their event binding", async () => {
    const requests = fixtureApi(); render(<App />); await formReady(); fireEvent.change(screen.getByLabelText("回答标识"), { target: { value: ids.answer } }); fireEvent.submit(screen.getByRole("form", { name: "查询已保存回答" })); await screen.findByRole("article", { name: "完整证据回答" });
    expect(requests.filter((request) => request.path.startsWith("/v1/answers/"))).toHaveLength(1); expect(requests.some((request) => request.path === "/v1/auth/csrf" || request.path === "/v1/questions")).toBe(false);
    expect(screen.queryByRole("link", { name: /检视固定修订证据/ })).toBeNull();
  });
  it("fences late CSRF after leaving the page and after a session refresh", async () => {
    const delayed = deferredResponse(); const requests = fixtureApi({ csrfResponse: delayed.promise }); render(<App />); await formReady(); fillQuestion(); submitForm();
    window.history.replaceState(null, "", "/#session"); fireEvent(window, new HashChangeEvent("hashchange"));
    await screen.findByRole("button", { name: "重新验证会话" }); fireEvent.click(screen.getByRole("button", { name: "重新验证会话" }));
    delayed.resolve(response({ csrf_token: csrf, header_name: "X-CSRF-Token" })); await waitFor(() => expect(screen.getByRole("button", { name: "退出登录" })).toBeTruthy());
    expect(requests.some((request) => request.path === "/v1/questions")).toBe(false);
  });
  it("does not revive old answers after logout while wire response is pending", async () => {
    const delayed = deferredResponse(); fixtureApi({ answerResponse: delayed.promise });
    function SessionHarness() { const session = useAuthSession(); return <><button onClick={() => void session.logout()}>隔离退出</button><QuestionWorkspace eventId={ids.event} /></>; }
    render(<AuthProvider><SessionHarness /></AuthProvider>); await formReady(); fillQuestion(); submitForm(); await screen.findByText(/正在提交问题并等待完整回答/); fireEvent.click(screen.getByRole("button", { name: "隔离退出" })); delayed.resolve(response(questionAnswerFixture())); await screen.findByRole("heading", { name: "登录后使用证据问答" }); expect(screen.queryByText(/隔离测试回答/)).toBeNull();
  });
});
