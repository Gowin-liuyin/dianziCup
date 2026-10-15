import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuthSession } from "../../app/auth-session";
import { sourceKinds } from "../../api/source-contracts";
import { sourceCatalog } from "./source-catalog";
import { SourceWorkspace } from "./source-workspace";

const jobId = "00000000-0000-4000-8000-000000000001";
const admin = { user_id: "catalog-fixture-admin", tenant_id: null, role: "system_admin", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "isolated-catalog-csrf" };
const job = { job_id: jobId, status: "succeeded", attempt_count: 1, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: "2026-10-15T06:00:01Z" };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function deferredResponse() { let release: (response: Response) => void = () => { throw new Error("isolated barrier not initialized"); }; const promise = new Promise<Response>((resolve) => { release = resolve; }); return { promise, release }; }
function FixtureSession() {
  const session = useAuthSession();
  return <><button onClick={() => void session.logout()}>隔离退出</button><button onClick={() => void session.refreshSession()}>隔离刷新会话</button><SourceWorkspace /></>;
}
function installFixture(options: { lookup?: () => Response | Promise<Response>; write?: () => Response | Promise<Response> } = {}) {
  const calls: { path: string; init: RequestInit }[] = [];
  let role = "system_admin";
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input); calls.push({ path, init });
    if (path === "/v1/auth/me") return response({ ...admin, role });
    if (path === "/v1/auth/csrf") return response({ csrf_token: admin.csrf_token, header_name: "X-CSRF-Token" });
    if (path === "/v1/auth/logout") return response({ logged_out: true });
    if (path.endsWith("/collect")) return options.write ? options.write() : response(job, 202);
    if (path === `/v1/jobs/${jobId}`) return options.lookup ? options.lookup() : response(job);
    throw new Error("Unexpected isolated catalog request");
  }));
  render(<AuthProvider><FixtureSession /></AuthProvider>);
  return { calls, revoke: () => { role = "analyst"; } };
}
async function ready() { await screen.findByRole("heading", { name: "固定来源目录" }); }
function query() { fireEvent.change(screen.getByLabelText("任务标识"), { target: { value: jobId } }); fireEvent.click(screen.getByRole("button", { name: "查询 / 刷新任务" })); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("source catalog UI — isolated fixture only", () => {
  it("starts with unknown catalog and no job snapshots or automatic management calls", async () => {
    const fixture = installFixture(); await ready();
    expect(screen.getAllByText("未验证", { exact: true })).toHaveLength(9);
    expect(document.querySelectorAll(".source-category-group")).toHaveLength(8);
    expect(screen.getByRole("heading", { name: "尚未查询任务" })).toBeTruthy();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
    expect(fixture.calls.filter((call) => call.path.startsWith("/v1/sources/") || call.path.startsWith("/v1/jobs/") || call.path === "/v1/auth/csrf")).toHaveLength(0);
  });
  it.each(sourceKinds)("selects %s without collection, then submits exactly the selected source", async (key) => {
    const fixture = installFixture(); await ready();
    fireEvent.click(screen.getByRole("button", { name: `选择 ${sourceCatalog[key].name}` }));
    expect(screen.getByLabelText("固定来源").getAttribute("id")).toBe("source-kind");
    expect(document.activeElement).toBe(screen.getByLabelText("固定来源"));
    expect(screen.getByDisplayValue(sourceCatalog[key].name)).toBeTruthy();
    expect(fixture.calls.filter((call) => call.path.endsWith("/collect"))).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    const writes = fixture.calls.filter((call) => call.path.endsWith("/collect"));
    expect(writes).toHaveLength(1); expect(writes[0]?.path).toBe(`/v1/sources/${key}/collect`);
    expect(JSON.parse(String(writes[0]?.init.body))).toMatchObject({ stream_kind: "live", max_pages: 5 });
    expect(screen.getByRole("button", { name: `选择 ${sourceCatalog[key].name}` }).hasAttribute("disabled")).toBe(true);
  });
  it("does not infer manual job source and clears its success and receive timestamp on source change", async () => {
    installFixture(); await ready(); query();
    await screen.findByRole("heading", { name: "本页处理完成" });
    expect(screen.getByText("未知 / 仅按任务标识查询")).toBeTruthy();
    expect(screen.getByText(/服务未提供时效标记/)).toBeTruthy();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(3);
    fireEvent.change(screen.getByLabelText("固定来源"), { target: { value: "cac_generative_ai" } });
    expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull();
    expect(screen.queryByText("本轮已受理")).toBeNull();
    expect(screen.getByLabelText("任务标识").getAttribute("value")).toBe("");
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
  });
  it("clears accepted job and timer before a new source round", async () => {
    installFixture(); await ready(); fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    fireEvent.click(screen.getByRole("button", { name: "开始新一轮" }));
    fireEvent.click(screen.getByRole("button", { name: "选择 NIST · AI RMF 1.0" }));
    expect(screen.queryByRole("heading", { name: "本轮已受理" })).toBeNull();
    expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
    expect(screen.getByLabelText("任务标识").getAttribute("value")).toBe("");
  });
  it.each([429, 503])("clears prior success during HTTP %s lookup and keeps unknown separate from zero", async (status) => {
    let fail = false;
    installFixture({ lookup: () => fail ? response({ error: { code: "isolated_failure" } }, status) : response(job) });
    await ready(); query(); await screen.findByRole("heading", { name: "本页处理完成" });
    fail = true; query(); await screen.findByRole("alert");
    expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
    expect(screen.queryByText("0个任务")).toBeNull();
    expect(screen.queryByRole("heading", { name: "尚未查询任务" })).toBeNull();
  });
  it("retains the same request identity after a 429 submission", async () => {
    let writes = 0;
    const fixture = installFixture({ write: () => ++writes === 1 ? response({ error: { code: "isolated_limit" } }, 429) : response(job, 202) });
    await ready(); fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByText(/请求过于频繁/);
    expect(screen.queryByRole("heading", { name: "本轮已受理" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "原样重试本轮" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    const posts = fixture.calls.filter((call) => call.path.endsWith("/collect"));
    expect(posts[1]?.init.body).toBe(posts[0]?.init.body);
    expect(new Headers(posts[1]?.init.headers).get("Idempotency-Key")).toBe(new Headers(posts[0]?.init.headers).get("Idempotency-Key"));
  });
  it("clears the entire management view when the server revokes access", async () => {
    let denied = false;
    installFixture({ lookup: () => denied ? response({ error: { code: "permission_denied" } }, 403) : response(job) });
    await ready(); fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByRole("heading", { name: "本轮已受理" });
    denied = true; query(); await screen.findByRole("heading", { name: "没有来源调度权限" });
    expect(screen.queryByRole("heading", { name: "固定来源目录" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "本轮已受理" })).toBeNull();
    expect(screen.queryByText(jobId)).toBeNull();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
  });
  it.each(["logout", "role-revocation"])("fences a late lookup after %s, then starts without old success or timestamps", async (action) => {
    const late = deferredResponse(); const fixture = installFixture({ lookup: () => late.promise });
    await ready(); fireEvent.click(screen.getByRole("button", { name: "提交本轮采集" }));
    await screen.findByRole("heading", { name: "本轮已受理" }); query();
    await screen.findByText("正在读取指定任务的PG状态…");
    if (action === "role-revocation") { fixture.revoke(); fireEvent.click(screen.getByRole("button", { name: "隔离刷新会话" })); }
    else fireEvent.click(screen.getByRole("button", { name: "隔离退出" }));
    await screen.findByRole("heading", { name: "没有来源调度权限" });
    await act(async () => { late.release(response(job)); await late.promise; });
    await waitFor(() => expect(screen.queryByRole("article", { name: "当前单页任务" })).toBeNull());
    expect(screen.queryByRole("heading", { name: "本轮已受理" })).toBeNull();
    expect(document.querySelectorAll(".source-job-details time")).toHaveLength(0);
    expect(fixture.calls.filter((call) => call.path.startsWith("/v1/jobs/"))).toHaveLength(1);
  });
});
