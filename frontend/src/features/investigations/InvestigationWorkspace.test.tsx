import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fixtureAssetId, fixtureSnapshotId, fixtureTenant, snapshotFixture } from "../assets/synthetic-fixtures";
import { InvestigationWorkspace } from "./InvestigationWorkspace";
import { fixtureEvidence, fixtureEvidenceId, fixtureEventId, fixtureJob, fixtureJobId, fixtureOperation, fixtureOtherJobId, fixtureRevisionId, fixtureUser } from "./investigation.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
const current = () => true;
const csrf = { csrf_token: "explicit-fixture-csrf", header_name: "X-CSRF-Token" };
function transport(status: ReturnType<typeof fixtureJob>["status"] = "partial") {
  return vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
    if (path === "/v1/auth/csrf") return response(csrf);
    if (path.includes("/tool-runs")) return response({ items: [fixtureOperation()], next_cursor: null });
    return response(fixtureJob(status), options?.method === "POST" ? 202 : 200);
  });
}
function submitQuestion(text = "Explicit fixture question") {
  fireEvent.change(screen.getByRole("textbox", { name: "事件标识" }), { target: { value: fixtureEventId } });
  fireEvent.change(screen.getByRole("textbox", { name: "调查问题" }), { target: { value: text } });
  fireEvent.submit(screen.getByRole("form", { name: "调查输入" }));
}
async function flush() { await act(async () => { for (let index = 0; index < 16; index += 1) await Promise.resolve(); }); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });
describe("R17 investigation interaction · isolated fixture HTTP, never live evidence", () => {
  it("does not request anything without login, read:public or a current generation", () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const { rerender } = render(<InvestigationWorkspace user={null} authScope="fixture" isCurrent={current} initialJobId={fixtureJobId} />);
    expect(screen.getByText("登录后使用调查工作台")).toBeTruthy();
    rerender(<InvestigationWorkspace user={{ ...fixtureUser, permissions: ["read:tenant"] }} authScope="fixture" isCurrent={current} initialJobId={fixtureJobId} />);
    expect(screen.getByText("当前会话无调查读取权限")).toBeTruthy();
    rerender(<InvestigationWorkspace user={fixtureUser} authScope="fixture" isCurrent={() => false} initialJobId={fixtureJobId} />);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("submits real POST, keeps partial and unconfigured duties visible, shows full service elapsed and actual failure", async () => {
    const fetch = transport(); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-1" isCurrent={current} />);
    submitQuestion();
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(screen.getByText("12345.678 毫秒")).toBeTruthy();
    expect(screen.getByText("未配置")).toBeTruthy();
    expect(screen.queryByText("已完成", { exact: true })).toBeNull();
    expect(screen.getByText("current_support")).toBeTruthy();
    await screen.findByText("read_evidence");
    expect(screen.getByText("失败", { selector: ".status-failed" })).toBeTruthy();
    const writes = fetch.mock.calls.filter(([path, options]) => path === "/api/v1/investigations" && options?.method === "POST");
    expect(writes).toHaveLength(1);
    const body: unknown = JSON.parse(writes[0]?.[1]?.body?.toString() ?? "null");
    expect(body).toEqual({ question: "Explicit fixture question", event_id: fixtureEventId, evidence_refs: [], strategy: "B2b", asset_id: null, asset_snapshot_id: null, version_comparison: null });
  });
  it("blocks same-tick double submission while CSRF is pending", async () => {
    let resolveCsrf: ((value: Response) => void) | undefined;
    const fetch = transport(); fetch.mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveCsrf = resolve; })); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-double" isCurrent={current} />);
    submitQuestion(); fireEvent.submit(screen.getByRole("form", { name: "调查输入" }));
    expect(fetch).toHaveBeenCalledTimes(1);
    await act(async () => resolveCsrf?.(response(csrf)));
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(fetch.mock.calls.filter(([path]) => path === "/api/v1/investigations")).toHaveLength(1);
  });
  it("keeps request body and idempotency unchanged after unknown POST outcome and explicit retry", async () => {
    let writes = 0;
    const base = transport();
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
      if (path === "/api/v1/investigations" && ++writes === 1) return response({ error: { code: "investigation_unavailable", retryable: true } }, 503);
      return base(path, options);
    }); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-retry" isCurrent={current} />);
    submitQuestion(); await screen.findByRole("alert");
    expect(fetch.mock.calls.filter(([path]) => path === "/api/v1/investigations")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "原样重试本轮" }));
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    const requests = fetch.mock.calls.filter(([path]) => path === "/api/v1/investigations");
    expect(requests[0]?.[1]?.body).toBe(requests[1]?.[1]?.body);
    expect(new Headers(requests[0]?.[1]?.headers).get("Idempotency-Key")).toBe(new Headers(requests[1]?.[1]?.headers).get("Idempotency-Key"));
  });
  it("recovers an owner UUID without inventing its event binding or fixed citation revision", async () => {
    vi.stubGlobal("fetch", transport()); const onOpenEvent = vi.fn();
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-restore" isCurrent={current} initialJobId={fixtureJobId} initialEventId={fixtureEventId} onOpenEvent={onOpenEvent} />);
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(screen.queryByRole("button", { name: /核查固定证据/ })).toBeNull();
    expect(screen.getByText(/本页不使用当前表单事件拼接链接/)).toBeTruthy();
    expect(onOpenEvent).not.toHaveBeenCalled();
  });
  it("paginates actual operations and keeps a failed next page distinct from an empty success", async () => {
    let pageAttempts = 0;
    const base = transport();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
      if (path.includes("cursor=001")) {
        pageAttempts += 1;
        return pageAttempts === 1 ? response({ error: { code: "investigation_unavailable", retryable: true } }, 503) : response({ items: [fixtureOperation("002", "succeeded")], next_cursor: null });
      }
      if (path.includes("/tool-runs")) return response({ items: [fixtureOperation("001")], next_cursor: "001" });
      return base(path, options);
    }));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-page" isCurrent={current} initialJobId={fixtureJobId} />);
    fireEvent.click(await screen.findByRole("button", { name: "加载更多操作" }));
    await screen.findByRole("alert");
    expect(screen.getByText("001")).toBeTruthy();
    expect(screen.queryByText("本页操作记录为空")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "重试" })); await screen.findByText("002");
    expect(screen.getByText("001")).toBeTruthy(); expect(screen.getByText("002")).toBeTruthy();
  });
  it("cancels only with actual write:asset and waits for the server confirmation", async () => {
    let resolveCancel: ((value: Response) => void) | undefined;
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path) => {
      if (path === "/v1/auth/csrf") return response(csrf);
      if (path.endsWith("/cancel")) return new Promise<Response>((resolve) => { resolveCancel = resolve; });
      if (path.includes("/tool-runs")) return response({ items: [], next_cursor: null });
      return response(fixtureJob(resolveCancel === undefined ? "waiting_approval" : "cancelled"));
    }); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-cancel" isCurrent={current} initialJobId={fixtureJobId} />);
    fireEvent.click(await screen.findByRole("button", { name: "请求取消任务" })); await flush();
    expect(screen.queryByText("已取消", { exact: true })).toBeNull();
    await act(async () => resolveCancel?.(response(fixtureJob("cancelled"))));
    await screen.findByText("已取消", { exact: true });
    expect(fetch.mock.calls.some(([path, options]) => path.endsWith("/cancel") && options?.method === "POST")).toBe(true);
  });
  it("disables cancellation and asset fields from actual permission DTO, not role names", async () => {
    const fetch = transport("waiting_approval"); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={{ ...fixtureUser, role: "system_admin", tenant_id: null, permissions: ["read:public"] }} authScope="fixture-limited" isCurrent={current} initialJobId={fixtureJobId} />);
    const cancelButton = await screen.findByRole("button", { name: "请求取消任务" });
    expect(cancelButton.hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("textbox", { name: "资产标识" }).closest("fieldset")?.hasAttribute("disabled")).toBe(true);
    fireEvent.click(cancelButton);
    expect(fetch.mock.calls.some(([path]) => path.endsWith("/cancel"))).toBe(false);
  });
  it("reuses evidence API and opens its actual fixed revision instead of trusting model or form metadata", async () => {
    const evidence = fixtureEvidence();
    const base = transport(), onOpenEvidence = vi.fn();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? response(evidence) : base(path, options)));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-evidence" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitQuestion(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await flush(); expect(onOpenEvidence).toHaveBeenCalledWith(fixtureEventId, fixtureEvidenceId, fixtureRevisionId);
  });
  it.each(["javascript:alert(1)", "https://user:password@example.org/", "https://example.org\\private"])("rejects unsafe evidence URI %s before navigation", async (sourceUri) => {
    const base = transport(), onOpenEvidence = vi.fn();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? response({ ...fixtureEvidence(), source_uri: sourceUri }) : base(path, options)));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-uri" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitQuestion(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await screen.findByRole("alert"); expect(onOpenEvidence).not.toHaveBeenCalled();
    expect(screen.queryByRole("link", { name: sourceUri })).toBeNull();
  });
  it("checks optional asset/snapshot with the existing authorized DTO client before submitting", async () => {
    const base = transport(), fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/assets/") ? response(snapshotFixture()) : base(path, options));
    vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={{ ...fixtureUser, tenant_id: fixtureTenant }} authScope="fixture-asset" isCurrent={current} />);
    fireEvent.change(screen.getByRole("textbox", { name: "资产标识" }), { target: { value: fixtureAssetId } });
    fireEvent.change(screen.getByRole("textbox", { name: "资产快照标识" }), { target: { value: fixtureSnapshotId } });
    submitQuestion(); await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(fetch.mock.calls[0]?.[0]).toBe(`/v1/assets/${fixtureAssetId}/snapshots/${fixtureSnapshotId}`);
    const body: unknown = JSON.parse(fetch.mock.calls.find(([path]) => path === "/api/v1/investigations")?.[1]?.body?.toString() ?? "null");
    expect(body).toMatchObject({ asset_id: fixtureAssetId, asset_snapshot_id: fixtureSnapshotId });
  });
  it("clears private data on a revoked read and does not display stale answer after 401", async () => {
    let reads = 0;
    const fetch = transport();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
      if (path === `/api/v1/investigations/${fixtureJobId}` && ++reads > 1) return response({ error: { code: "session_expired", retryable: false } }, 401);
      return fetch(path, options);
    })); const onFailure = vi.fn();
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-expire" isCurrent={current} initialJobId={fixtureJobId} onFailure={onFailure} />);
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    fireEvent.click(screen.getByRole("button", { name: "手动刷新任务" }));
    await screen.findByText(/会话已失效，调查内容已清除/);
    expect(screen.queryByText("Explicit fixture: evidence is incomplete.")).toBeNull();
    expect(screen.queryByRole("form", { name: "调查输入" })).toBeNull();
    expect(onFailure).toHaveBeenCalledWith(expect.objectContaining({ status: 401 }));
  });
  it("ignores old generation response and aborts in-flight IO across session change", async () => {
    let resolveOld: ((value: Response) => void) | undefined;
    const base = transport(), fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
      if (path === `/api/v1/investigations/${fixtureOtherJobId}`) {
        const job = fixtureJob("partial", fixtureOtherJobId);
        if (job.result?.answer === null || job.result?.answer === undefined) throw new Error("fixture answer missing");
        job.result.answer.claims[0] = { text: "Explicit fixture new owner response", kind: "source_fact", support_ids: [fixtureEvidenceId] };
        return response(job);
      }
      return base(path, options);
    }); fetch.mockImplementationOnce(() => new Promise<Response>((resolve) => { resolveOld = resolve; })); vi.stubGlobal("fetch", fetch);
    const { rerender } = render(<InvestigationWorkspace user={fixtureUser} authScope="old" isCurrent={current} initialJobId={fixtureJobId} />);
    const oldSignal = fetch.mock.calls[0]?.[1]?.signal;
    rerender(<InvestigationWorkspace user={{ ...fixtureUser, user_id: "new-fixture-owner" }} authScope="new" isCurrent={current} initialJobId={fixtureOtherJobId} />);
    expect(oldSignal?.aborted).toBe(true);
    await screen.findByText("Explicit fixture new owner response");
    await act(async () => resolveOld?.(response(fixtureJob("succeeded"))));
    expect(screen.getByText("Explicit fixture new owner response")).toBeTruthy();
    expect(screen.queryByText("Explicit fixture: evidence is incomplete.")).toBeNull();
  });
  it("polls serially with a 30-read cap and stops on unmount", async () => {
    vi.useFakeTimers(); const fetch = transport("running"); vi.stubGlobal("fetch", fetch);
    const { unmount } = render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-poll" isCurrent={current} initialJobId={fixtureJobId} />);
    await flush();
    for (let index = 0; index < 29; index += 1) await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
    expect(fetch.mock.calls.filter(([path]) => path === `/api/v1/investigations/${fixtureJobId}`)).toHaveLength(30);
    expect(screen.getByText(/已达到本页自动查询上限/)).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(12000); });
    expect(fetch.mock.calls.filter(([path]) => path === `/api/v1/investigations/${fixtureJobId}`)).toHaveLength(30);
    unmount(); expect(vi.getTimerCount()).toBe(0);
  });
  it("stops polling when server returns partial and renders hostile strings as text", async () => {
    vi.useFakeTimers(); let reads = 0;
    const fetch = transport("running");
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
      if (path === `/api/v1/investigations/${fixtureJobId}` && ++reads > 1) {
        const job = fixtureJob("partial");
        if (job.result?.answer === null || job.result?.answer === undefined) throw new Error("fixture answer missing");
        job.result.answer.claims[0] = { text: "<img src=x onerror=alert(1)>", kind: "source_fact", support_ids: [fixtureEvidenceId] };
        return response(job);
      }
      return fetch(path, options);
    }));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fixture-stop" isCurrent={current} initialJobId={fixtureJobId} />);
    await flush(); await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeTruthy(); expect(document.querySelector("img")).toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(12000); }); expect(reads).toBe(2);
  });
});
