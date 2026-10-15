import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { AuthProvider, useAuthSession } from "../../app/auth-session";
import { SourceWorkspace } from "./source-workspace";

const jobId = "00000000-0000-4000-8000-000000000001";
const csrf = randomBytes(32).toString("hex");
const fixtureUser = { user_id: "isolated-source-admin", tenant_id: null, role: "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: csrf };
const fixtureJob = { job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function deferredResponse() { let resolve: (value: Response) => void = () => { throw new Error("isolated deferred response not initialized"); }; const promise = new Promise<Response>((release) => { resolve = release; }); return { promise, resolve }; }
function navigate(hash: string) { window.history.replaceState(null, "", `/${hash}`); fireEvent(window, new HashChangeEvent("hashchange")); }

function fixtureApi(options: { role?: string; tenantId?: string; anonymous?: boolean; status?: string; failureStatus?: number; postUnknown?: boolean; csrfStatus?: number; unsafeError?: boolean; delayedCsrf?: Promise<Response> } = {}) {
  const requests: { path: string; options: RequestInit }[] = [];
  let writeCount = 0;
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input);
    requests.push({ path, options: init });
    if (path === "/v1/auth/me") return options.anonymous ? response({ error: { code: "unauthenticated" } }, 401) : response({ ...fixtureUser, role: options.role ?? fixtureUser.role, tenant_id: options.tenantId ?? null });
    if (path === "/v1/auth/csrf") return options.delayedCsrf ?? (options.csrfStatus ? response({ error: { code: "session_expired" } }, options.csrfStatus) : response({ csrf_token: csrf, header_name: "X-CSRF-Token" }));
    if (path === "/v1/health/live") return response({ status: "live" });
    if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
    if (path.endsWith("/collect")) {
      writeCount += 1;
      if (options.postUnknown && writeCount === 1) throw new Error("isolated private upstream text must never appear");
      return response(fixtureJob, 202);
    }
    if (path === `/v1/jobs/${jobId}`) return options.failureStatus ? response({ error: { code: "isolated_failure", message: "private fixture response ignored" } }, options.failureStatus) : response({ ...fixtureJob, status: options.status ?? "queued", error_code: options.unsafeError ? "<img src=x onerror=alert('fixture')>" : null });
    throw new Error(`Unexpected isolated source route: ${path}`);
  }));
  window.history.replaceState(null, "", "/#sources");
  return requests;
}

async function findAdmin() { await screen.findByRole("button", { name: "提交本轮采集" }); }
async function queryJob() { fireEvent.change(screen.getByLabelText("任务标识"), { target: { value: jobId } }); fireEvent.click(screen.getByRole("button", { name: "查询 / 刷新任务" })); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

describe("source workspace — isolated fixture only", () => {
  it.each([{ anonymous: true }, { role: "analyst" }, { role: "system_admin", tenantId: "isolated-tenant" }])("denies management requests without a global admin snapshot: %j", async (options) => {
    const requests = fixtureApi(options);
    render(<App />);
    await screen.findByRole("heading", { name: "没有来源调度权限" });
    expect(screen.queryByRole("button", { name: "提交本轮采集" })).toBeNull();
    expect(requests.some((request) => request.path.startsWith("/v1/sources/") || request.path.startsWith("/v1/jobs/") || request.path === "/v1/auth/csrf")).toBe(false);
  });
  it("defaults to live five pages and submits exactly one fixed source on double submit", async () => {
    const csrfResponse = deferredResponse();
    const requests = fixtureApi({ delayedCsrf: csrfResponse.promise });
    render(<App />);
    await findAdmin();
    expect(screen.getByLabelText("采集流").getAttribute("id")).toBe("source-stream");
    expect(screen.getByDisplayValue("5")).toBeTruthy();
    expect(requests.filter((request) => request.path.startsWith("/v1/sources/"))).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("固定来源"), { target: { value: "vllm_vendor" } });
    fireEvent.submit(screen.getByRole("form", { name: "固定来源采集" }));
    fireEvent.submit(screen.getByRole("form", { name: "固定来源采集" }));
    csrfResponse.resolve(response({ csrf_token: csrf, header_name: "X-CSRF-Token" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    const writes = requests.filter((request) => request.path.startsWith("/v1/sources/"));
    expect(writes).toHaveLength(1);
    expect(writes[0]?.path).toBe("/v1/sources/vllm_vendor/collect");
    expect(JSON.parse(String(writes[0]?.options.body))).toMatchObject({ stream_kind: "live", max_pages: 5 });
    expect(Object.keys(JSON.parse(String(writes[0]?.options.body)))).toEqual(["window_end", "stream_kind", "max_pages"]);
    expect(screen.getByText("2026-10-15T14:00:00+08:00")).toBeTruthy();
    expect(screen.getByText("未知 / 未留存")).toBeTruthy();
  });
  it("retries unknown submission with identical body/key and only an explicit new round changes key", async () => {
    const requests = fixtureApi({ postUnknown: true });
    render(<App />);
    await findAdmin();
    fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByText(/提交结果未确认/);
    expect(screen.queryByText(/private upstream/)).toBeNull();
    expect(screen.getByLabelText("观察窗口截止（含时区）").hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "原样重试本轮" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    let writes = requests.filter((request) => request.path.endsWith("/collect"));
    expect(writes[1]?.options.body).toBe(writes[0]?.options.body);
    expect(new Headers(writes[1]?.options.headers).get("Idempotency-Key")).toBe(new Headers(writes[0]?.options.headers).get("Idempotency-Key"));
    fireEvent.click(screen.getByRole("button", { name: "开始新一轮" }));
    fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    writes = requests.filter((request) => request.path.endsWith("/collect"));
    expect(writes).toHaveLength(3);
    expect(new Headers(writes[2]?.options.headers).get("Idempotency-Key")).not.toBe(new Headers(writes[0]?.options.headers).get("Idempotency-Key"));
  });
  it.each([["queued", "已排队"], ["running", "本页处理中"], ["retry_wait", "等待重试"], ["succeeded", "本页处理完成"], ["partial", "部分完成"], ["failed", "本页失败"], ["blocked", "任务已阻塞"], ["cancelled", "任务已取消"], ["waiting_approval", "待人工确认"]])("displays actual %s separately and performs only a manual GET", async (status, label) => {
    const requests = fixtureApi({ status });
    render(<App />);
    await findAdmin();
    await queryJob();
    await screen.findByRole("heading", { name: label });
    expect(requests.filter((request) => request.path.startsWith("/v1/jobs/"))).toHaveLength(1);
    if (status === "succeeded") expect(screen.getByText(/后续页仍可能排队或运行/)).toBeTruthy();
    expect(screen.queryByText("整个来源已完成")).toBeNull();
  });
  it.each([404, 503])("keeps job HTTP %s separate from no task or completion", async (failureStatus) => {
    fixtureApi({ failureStatus });
    render(<App />);
    await findAdmin();
    await queryJob();
    await screen.findByRole("alert");
    expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull();
    expect(screen.queryByText(/private fixture response/)).toBeNull();
    expect(screen.queryByText("0个任务")).toBeNull();
  });
  it("rejects unsafe task error text without executing or echoing it", async () => {
    fixtureApi({ unsafeError: true });
    render(<App />);
    await findAdmin(); await queryJob();
    await screen.findByText("服务返回的数据格式不符合接口约定，请重新检查。");
    expect(document.querySelector("img")).toBeNull();
    expect(screen.queryByText(/onerror/)).toBeNull();
  });
  it("explains an invalid job UUID and permits correcting it without a management request", async () => {
    const requests = fixtureApi();
    render(<App />); await findAdmin();
    fireEvent.change(screen.getByLabelText("任务标识"), { target: { value: "not-a-job" } });
    fireEvent.click(screen.getByRole("button", { name: "查询 / 刷新任务" }));
    await screen.findByText("任务标识未通过校验，请输入完整UUID后重新查询。");
    expect(requests.some((request) => request.path.startsWith("/v1/jobs/"))).toBe(false);
    expect(screen.getByLabelText("任务标识").hasAttribute("disabled")).toBe(false);
  });
  it("clears identity on expired CSRF and never posts or loops auth/me", async () => {
    const requests = fixtureApi({ csrfStatus: 401 });
    render(<App />);
    await findAdmin();
    fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByText("会话已失效，请重新登录。");
    expect(screen.queryByRole("button", { name: "提交本轮采集" })).toBeNull();
    expect(requests.filter((request) => request.path.endsWith("/collect"))).toHaveLength(0);
    expect(requests.filter((request) => request.path === "/v1/auth/me")).toHaveLength(1);
  });
  it("does not write when delayed CSRF resolves after leaving the page", async () => {
    const csrfResponse = deferredResponse();
    const requests = fixtureApi({ delayedCsrf: csrfResponse.promise });
    render(<App />); await findAdmin();
    fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    navigate("#runtime");
    csrfResponse.resolve(response({ csrf_token: csrf, header_name: "X-CSRF-Token" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "运行概览" })).toBeTruthy());
    expect(requests.filter((request) => request.path.endsWith("/collect"))).toHaveLength(0);
  });
  it.each([200, 401])("discards a previous session's delayed job HTTP %s", async (lateStatus) => {
    const oldRead = deferredResponse();
    let identity = "first";
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/v1/auth/me") return response({ ...fixtureUser, user_id: identity });
      if (path === "/v1/auth/login") { identity = "second"; return response({ user_id: identity, csrf_token: csrf, expires_at: "2099-01-01T00:00:00Z" }); }
      if (path === `/v1/jobs/${jobId}`) return oldRead.promise;
      throw new Error("Unexpected isolated generation request");
    }));
    function SessionProbe() { const session = useAuthSession(); return <><button onClick={() => void session.login("isolated", "fixture-only")}>切换隔离身份</button><span>{session.state.kind === "authenticated" ? session.state.user.user_id : session.state.kind}</span><SourceWorkspace /></>; }
    render(<AuthProvider><SessionProbe /></AuthProvider>);
    await findAdmin(); await queryJob();
    await screen.findByText("正在读取指定任务的PG状态…");
    fireEvent.click(screen.getByRole("button", { name: "切换隔离身份" }));
    await screen.findByText("second");
    oldRead.resolve(lateStatus === 200 ? response(fixtureJob) : response({ error: { code: "unauthenticated" } }, 401));
    await waitFor(() => expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull());
    expect(screen.getByText("second")).toBeTruthy();
    expect(screen.queryByText("会话已失效，请重新登录。")).toBeNull();
  });
});
