import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssessmentPanel, type AssessmentPanelProps } from "./AssessmentPanel";
import { syntheticAssessment, syntheticAssessmentId, syntheticEventId, syntheticEvidenceId, syntheticScope, syntheticSnapshot, syntheticUser } from "./assessment.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
function props(): AssessmentPanelProps { return { user: syntheticUser, snapshot: syntheticSnapshot(), currentSnapshotId: syntheticScope.snapshotId, authScope: "synthetic-session-1", isCurrent: () => true }; }
function enterRule(ruleId = syntheticScope.ruleId) { fireEvent.change(screen.getByRole("textbox", { name: "已知规则标识" }), { target: { value: ruleId } }); }
function submit() { fireEvent.click(screen.getByRole("button", { name: "评估固定快照" })); }
function setupFetch(body: unknown, status = 200) { const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path) => response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : body, path === "/v1/auth/csrf" ? 200 : status)); vi.stubGlobal("fetch", fetch); return fetch; }
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("R17 fixed assessment panel · synthetic HTTP fixture, no live", () => {
  it.each([["supported_applicability", "支持适用"], ["excluded_with_evidence", "证据排除"], ["insufficient_evidence", "证据不足"], ["conflicting_evidence", "证据冲突"]] satisfies Array<[ReturnType<typeof syntheticAssessment>["status"], string]>)("shows backend %s and keeps exposure, PoC and unknown independent", async (status, label) => {
    setupFetch(syntheticAssessment(status)); const onOpenEvent = vi.fn(); render(<AssessmentPanel {...props()} onOpenEvent={onOpenEvent} />); enterRule(); submit();
    expect(await screen.findByRole("heading", { name: label, level: 3 })).toBeTruthy();
    expect(screen.getByText("路径未评估")).toBeTruthy(); expect(screen.getByText(/PoC 未验证/)).toBeTruthy(); expect(screen.getByText("条件未知")).toBeTruthy(); expect(screen.getByText("/components/0/version")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: new RegExp(`核查证据 ${syntheticEvidenceId}`) })); expect(onOpenEvent).toHaveBeenCalledWith(syntheticEventId, syntheticEvidenceId);
    fireEvent.click(screen.getByRole("button", { name: "核查关联事件" })); expect(onOpenEvent).toHaveBeenCalledWith(syntheticEventId);
    expect(screen.getAllByText(/显式 Fixture/).length).toBeGreaterThan(0); expect(screen.queryByText("安全")).toBeNull();
  });
  it("reads a saved result with the same scope and preserves stale historical outcome", async () => {
    const snapshot = syntheticSnapshot(1);
    const body = { ...syntheticAssessment("excluded_with_evidence"), asset_snapshot_id: snapshot.snapshot_id, rule_result: { ...syntheticAssessment("excluded_with_evidence").rule_result, asset_snapshot_id: snapshot.snapshot_id }, freshness: "stale" };
    const fetch = setupFetch(body); render(<AssessmentPanel {...props()} snapshot={snapshot} />); enterRule(); fireEvent.change(screen.getByRole("textbox", { name: "重读保存的评估 UUID" }), { target: { value: syntheticAssessmentId } }); fireEvent.click(screen.getByRole("button", { name: "读取保存结果" }));
    await screen.findByRole("heading", { name: "证据排除", level: 3 }); expect(screen.getByText(/历史快照结果，保留原结论/)).toBeTruthy(); expect(screen.getByText("已过期 · 待重新验证")).toBeTruthy(); expect(fetch).toHaveBeenCalledTimes(1);
    expect(document.querySelector(".assessment-result .confirmed")).toBeNull();
  });
  it("shows unpublished rules and missing evidence without a pretend condition tree", async () => {
    setupFetch({ ...syntheticAssessment(), rule_result: null, missing_requirements: ["unsupported_rule"], limitations: ["pending_semantic_review"] }); render(<AssessmentPanel {...props()} />); enterRule(); submit();
    await screen.findByRole("heading", { name: "规则尚不能支持判定" }); expect(screen.getByText("没有可支持此次判断的已发布规则。")).toBeTruthy(); expect(screen.getByText("pending_semantic_review")).toBeTruthy(); expect(screen.queryByText("条件成立")).toBeNull();
  });
  it.each([401, 403, 404, 409, 422, 503])("renders %i distinctly and clears any previously loaded assessment", async (status) => {
    let failing = false;
    const fetch = vi.fn(async (path: string) => {
      if (path === "/v1/auth/csrf") return response({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" });
      if (failing) return response({ error: { code: status === 503 ? "assessment_unavailable" : "synthetic-boundary", retryable: status === 503 } }, status);
      return response(syntheticAssessment());
    }); vi.stubGlobal("fetch", fetch);
    render(<AssessmentPanel {...props()} />); enterRule(); submit(); await screen.findByRole("heading", { name: "证据不足", level: 3 }); failing = true; fireEvent.click(screen.getByRole("button", { name: "读取保存结果" }));
    expect(await screen.findByRole("alert")).toBeTruthy(); expect(screen.queryByRole("article", { name: "保存的固定快照评估" })).toBeNull();
    if (status === 401 || status === 403) expect(screen.queryByText(syntheticScope.snapshotId)).toBeNull();
    if (status === 503) expect(screen.getByText(/依赖未配置或暂不可用/)).toBeTruthy();
  });
  it("invalid input, no snapshot, wrong tenant and denied permissions perform no request", async () => {
    const fetch = setupFetch(syntheticAssessment()); const { rerender } = render(<AssessmentPanel {...props()} />); enterRule(); fireEvent.change(screen.getByRole("textbox", { name: "固定规则版本" }), { target: { value: "1e3" } }); submit(); await screen.findByRole("alert"); expect(fetch).not.toHaveBeenCalled();
    rerender(<AssessmentPanel {...props()} snapshot={null} />); expect(screen.getByRole("heading", { name: "请选择固定资产快照" })).toBeTruthy();
    rerender(<AssessmentPanel {...props()} user={{ ...syntheticUser, tenant_id: "another-tenant" }} />); expect(screen.getByRole("heading", { name: "快照与当前认证范围不一致" })).toBeTruthy(); expect(screen.queryByText(syntheticScope.snapshotId)).toBeNull();
    rerender(<AssessmentPanel {...props()} user={{ ...syntheticUser, permissions: [] }} />); expect(screen.getByRole("heading", { name: "当前会话无资产研判权限" })).toBeTruthy(); expect(fetch).not.toHaveBeenCalled();
  });
  it("stops waiting, aborts IO and ignores a late response after a new rule intent", async () => {
    let resolveFirst: ((value: Response) => void) | undefined;
    let firstSignal: AbortSignal | null | undefined;
    const fetch = vi.fn(async (path: string, options?: RequestInit) => {
      if (path === "/v1/auth/csrf") return response({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" });
      if (JSON.parse(String(options?.body)).rule_id === syntheticScope.ruleId) { firstSignal = options?.signal; return new Promise<Response>((resolve) => { resolveFirst = resolve; }); }
      return response({ ...syntheticAssessment("conflicting_evidence"), rule_id: "new-rule", rule_result: { ...syntheticAssessment("conflicting_evidence").rule_result, rule_id: "new-rule" } });
    }); vi.stubGlobal("fetch", fetch); render(<AssessmentPanel {...props()} />); enterRule(); submit(); await waitFor(() => expect(resolveFirst).toBeTypeOf("function"));
    fireEvent.click(screen.getByRole("button", { name: "停止等待" })); expect(screen.getByText(/停止等待不会撤销/)).toBeTruthy(); expect(firstSignal?.aborted).toBe(true);
    enterRule("new-rule"); submit(); await screen.findByRole("heading", { name: "证据冲突", level: 3 }); await act(async () => { resolveFirst?.(response(syntheticAssessment("supported_applicability"))); }); expect(screen.queryByRole("heading", { name: "支持适用", level: 3 })).toBeNull();
  });
  it("auth scope changes and unmount abort old IO without restoring private fields", async () => {
    let resolveReceipt: ((value: Response) => void) | undefined; let signal: AbortSignal | null | undefined;
    vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => path === "/v1/auth/csrf" ? response({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" }) : new Promise<Response>((resolve) => { resolveReceipt = resolve; signal = options?.signal; })));
    const { rerender, unmount } = render(<AssessmentPanel {...props()} />); enterRule(); submit(); await waitFor(() => expect(resolveReceipt).toBeTypeOf("function")); rerender(<AssessmentPanel {...props()} authScope="synthetic-session-2" />); expect(signal?.aborted).toBe(true);
    await act(async () => { resolveReceipt?.(response(syntheticAssessment())); }); expect(screen.queryByRole("article", { name: "保存的固定快照评估" })).toBeNull(); expect(screen.getByRole("textbox", { name: "已知规则标识" }).getAttribute("value")).toBe(""); unmount();
  });
});
