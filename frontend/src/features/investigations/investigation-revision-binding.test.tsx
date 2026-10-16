import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { InvestigationWorkspace } from "./InvestigationWorkspace";
import { fixtureEvidence, fixtureEvidenceId, fixtureEventId, fixtureJob, fixtureJobId, fixtureOtherJobId, fixtureRevisionId, fixtureUser } from "./investigation.fixture";

const current = () => true;
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function transport() {
  return vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => {
    if (path === "/v1/auth/csrf") return response({ csrf_token: "fix1-explicit-fixture-csrf", header_name: "X-CSRF-Token" });
    if (path.includes("/tool-runs")) return response({ items: [], next_cursor: null });
    if (path.startsWith("/v1/evidence/")) return response(fixtureEvidence());
    return response(fixtureJob("partial", path.endsWith(fixtureOtherJobId) ? fixtureOtherJobId : fixtureJobId), options?.method === "POST" ? 202 : 200);
  });
}
function submitFrozenReference() {
  fireEvent.change(screen.getByRole("textbox", { name: "事件标识" }), { target: { value: fixtureEventId } });
  fireEvent.change(screen.getByRole("textbox", { name: "调查问题" }), { target: { value: "Fix1 explicit fixture: preserve the submitted revision" } });
  fireEvent.click(screen.getByRole("button", { name: "添加固定证据" }));
  fireEvent.change(screen.getByRole("textbox", { name: "证据 1 标识" }), { target: { value: fixtureEvidenceId } });
  fireEvent.change(screen.getByRole("textbox", { name: "证据 1 修订标识" }), { target: { value: fixtureRevisionId } });
  fireEvent.submit(screen.getByRole("form", { name: "调查输入" }));
}
async function flush() { await act(async () => { for (let index = 0; index < 20; index += 1) await Promise.resolve(); }); }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("R17 fix1 immutable evidence binding · explicit synthetic HTTP", () => {
  it("opens matching R1 from the confirmed submission even if draft event/revision fields are changed", async () => {
    const fetch = transport(), onOpenEvidence = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-frozen" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitFrozenReference();
    const openButton = await screen.findByRole("button", { name: "核查固定证据 [1] →" });
    fireEvent.change(screen.getByRole("textbox", { name: "事件标识" }), { target: { value: fixtureOtherJobId } });
    fireEvent.change(screen.getByRole("textbox", { name: "证据 1 修订标识" }), { target: { value: fixtureOtherJobId } });
    fireEvent.click(openButton); await flush();
    expect(onOpenEvidence).toHaveBeenCalledExactlyOnceWith(fixtureEventId, fixtureEvidenceId, fixtureRevisionId);
    expect(fetch.mock.calls.find(([path]) => path.startsWith("/v1/evidence/"))?.[0]).toBe(`/v1/evidence/${fixtureEvidenceId}`);
  });
  it("blocks both fixed and fallback navigation on R1→R2 and preserves invalid_response with a stale binding explanation", async () => {
    const base = transport(), onOpenEvidence = vi.fn(), onOpenEvent = vi.fn(), onFailure = vi.fn();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? response({ ...fixtureEvidence(), revision_id: fixtureOtherJobId }) : base(path, options)));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-mismatch" isCurrent={current} onOpenEvidence={onOpenEvidence} onOpenEvent={onOpenEvent} onFailure={onFailure} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await screen.findByRole("alert");
    expect(onOpenEvidence).not.toHaveBeenCalled(); expect(onOpenEvent).not.toHaveBeenCalled();
    expect(screen.getByText(/固定证据绑定已过期/)).toBeTruthy();
    expect(onFailure).toHaveBeenCalledWith(expect.objectContaining({ status: 502, code: "invalid_response" }));
  });
  it("also blocks R1→R2 when the caller only supplies the legacy event callback", async () => {
    const base = transport(), onOpenEvent = vi.fn();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? response({ ...fixtureEvidence(), revision_id: fixtureOtherJobId }) : base(path, options)));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-legacy" isCurrent={current} onOpenEvent={onOpenEvent} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await screen.findByRole("alert"); expect(onOpenEvent).not.toHaveBeenCalled();
  });
  it("never navigates a pending evidence read after selecting a different owner job", async () => {
    const base = transport(), onOpenEvidence = vi.fn(); let resolveEvidence: ((value: Response) => void) | undefined;
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? new Promise<Response>((resolve) => { resolveEvidence = resolve; }) : base(path, options)); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-switch-job" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await waitFor(() => expect(resolveEvidence).toBeTypeOf("function"));
    const signal = fetch.mock.calls.find(([path]) => path.startsWith("/v1/evidence/"))?.[1]?.signal;
    fireEvent.change(screen.getByRole("textbox", { name: "任务标识" }), { target: { value: fixtureOtherJobId } });
    fireEvent.submit(screen.getByRole("form", { name: "恢复调查任务" }));
    expect(signal?.aborted).toBe(true);
    await act(async () => resolveEvidence?.(response(fixtureEvidence())));
    expect(onOpenEvidence).not.toHaveBeenCalled();
    await screen.findByText(fixtureOtherJobId, { selector: ".investigation-job-line code" });
    expect(screen.queryByRole("button", { name: /核查固定证据/ })).toBeNull();
  });
  it("discards a matching R1 read when isCurrent becomes false before it completes", async () => {
    let sessionCurrent = true, resolveEvidence: ((value: Response) => void) | undefined;
    const base = transport(), onOpenEvidence = vi.fn();
    vi.stubGlobal("fetch", vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? new Promise<Response>((resolve) => { resolveEvidence = resolve; }) : base(path, options)));
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-expired" isCurrent={() => sessionCurrent} onOpenEvidence={onOpenEvidence} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await waitFor(() => expect(resolveEvidence).toBeTypeOf("function")); sessionCurrent = false;
    await act(async () => resolveEvidence?.(response(fixtureEvidence()))); expect(onOpenEvidence).not.toHaveBeenCalled();
  });
  it("aborts the old fixed binding when authScope changes and cannot create a new binding from initial props", async () => {
    let resolveEvidence: ((value: Response) => void) | undefined; const base = transport(), onOpenEvidence = vi.fn();
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? new Promise<Response>((resolve) => { resolveEvidence = resolve; }) : base(path, options)); vi.stubGlobal("fetch", fetch);
    const { rerender } = render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-old-scope" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await waitFor(() => expect(resolveEvidence).toBeTypeOf("function"));
    const signal = fetch.mock.calls.find(([path]) => path.startsWith("/v1/evidence/"))?.[1]?.signal;
    rerender(<InvestigationWorkspace user={fixtureUser} authScope="fix1-new-scope" isCurrent={current} initialJobId={fixtureJobId} initialEventId={fixtureEventId} onOpenEvidence={onOpenEvidence} />);
    expect(signal?.aborted).toBe(true); await act(async () => resolveEvidence?.(response(fixtureEvidence())));
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(screen.queryByRole("button", { name: /核查固定证据/ })).toBeNull(); expect(onOpenEvidence).not.toHaveBeenCalled();
  });
  it("recovery GET plus matching initialEventId does not imply a frozen event/evidence/revision binding", async () => {
    const fetch = transport(), onOpenEvidence = vi.fn(), onOpenEvent = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-restored" isCurrent={current} initialJobId={fixtureJobId} initialEventId={fixtureEventId} onOpenEvidence={onOpenEvidence} onOpenEvent={onOpenEvent} />);
    await screen.findByText("Explicit fixture: evidence is incomplete.");
    expect(screen.queryByRole("button", { name: /核查固定证据/ })).toBeNull();
    expect(fetch.mock.calls.some(([path]) => path.startsWith("/v1/evidence/"))).toBe(false);
    expect(onOpenEvidence).not.toHaveBeenCalled(); expect(onOpenEvent).not.toHaveBeenCalled();
  });
  it("starting a new investigation invalidates a pending fixed evidence callback", async () => {
    let resolveEvidence: ((value: Response) => void) | undefined; const base = transport(), onOpenEvidence = vi.fn();
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => path.startsWith("/v1/evidence/") ? new Promise<Response>((resolve) => { resolveEvidence = resolve; }) : base(path, options)); vi.stubGlobal("fetch", fetch);
    render(<InvestigationWorkspace user={fixtureUser} authScope="fix1-new-request" isCurrent={current} onOpenEvidence={onOpenEvidence} />);
    submitFrozenReference(); fireEvent.click(await screen.findByRole("button", { name: "核查固定证据 [1] →" }));
    await waitFor(() => expect(resolveEvidence).toBeTypeOf("function"));
    const signal = fetch.mock.calls.find(([path]) => path.startsWith("/v1/evidence/"))?.[1]?.signal;
    fireEvent.click(screen.getByRole("button", { name: "开始新调查" })); expect(signal?.aborted).toBe(true);
    await act(async () => resolveEvidence?.(response(fixtureEvidence()))); expect(onOpenEvidence).not.toHaveBeenCalled();
    expect(screen.getByText("尚未取得调查任务")).toBeTruthy();
  });
});
