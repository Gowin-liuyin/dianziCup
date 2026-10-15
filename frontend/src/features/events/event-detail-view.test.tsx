import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import type { EventDetailResponse } from "../../api/knowledge-contracts";
import { EventDetailView } from "./event-detail-view";
import { eventDetailFixture, fixtureEventId, fixtureOldEvidenceId, fixtureOldRevisionId, fixtureRevisionId, historicalEvidenceFixture } from "./event-detail.fixture";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

function renderDetail(detail: EventDetailResponse = eventDetailFixture) {
  return render(<EventDetailView detail={detail} selectedEvidenceId={null} selectedRevisionId={null} />);
}

describe("R17 detail presentation, explicitly isolated fixtures", () => {
  it("shows backend claim values under their dimension and all nine independent states", () => {
    renderDetail();
    const score = within(screen.getByRole("article", { name: "CVSS 评分" }));
    expect(score.getByText("9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")).toBeTruthy();
    expect(score.getByText("有证据支持")).toBeTruthy();
    expect(score.getByText("fixture-source-revision-2")).toBeTruthy();
    expect(document.querySelectorAll(".dimension-row")).toHaveLength(9);
    for (const status of ["已取得", "未发现", "不适用", "有冲突", "受阻", "失败", "待处理"]) expect(screen.getAllByText(status).length).toBeGreaterThan(0);
    expect(within(screen.getByRole("article", { name: "暴露统计" })).getByText("未提供该维度")).toBeTruthy();
    expect(screen.queryByText(/9\/9|全部完成|暂无风险|运行成功/)).toBeNull();
  });
  it("retains both conflicting values, withdrawn conditions, hypotheses and stale status", () => {
    renderDetail();
    const conflicts = within(screen.getByRole("article", { name: "CWE 弱点" }));
    expect(conflicts.getByText("隔离来源 A：CWE-502")).toBeTruthy();
    expect(conflicts.getByText("隔离来源 B：CWE-20")).toBeTruthy();
    expect(conflicts.getAllByText("有争议")).toHaveLength(2);
    expect(within(screen.getByRole("article", { name: "影响版本" })).getByText(/完整条件：仅在启用插件时适用/)).toBeTruthy();
    expect(screen.getAllByText("已撤回")).toHaveLength(2);
    expect(screen.getByText("已被新版本替代")).toBeTruthy();
    expect(screen.getByText("人工复核：当前只读接口未提供任务状态或确认入口。")).toBeTruthy();
    expect(screen.getByText(/事件已标为过期/)).toBeTruthy();
  });
  it("distinguishes available citations without values from missing linked claims", () => {
    const scoreDimension = eventDetailFixture.dimensions.find((dimension) => dimension.dimension === "cvss");
    if (scoreDimension === undefined) throw new Error("Isolated fixture must provide a score dimension");
    const detail: EventDetailResponse = { ...eventDetailFixture, dimensions: [{ ...scoreDimension, claim_ids: ["10000000-0000-4000-8000-000000000099"] }] };
    renderDetail(detail);
    const score = within(screen.getByRole("article", { name: "CVSS 评分" }));
    expect(score.getByText("未提供可展示的关联事实值")).toBeTruthy();
    expect(score.getByText("有 1 条关联断言未在本次响应中提供，无法展示其值。")).toBeTruthy();
    expect(score.queryByText(/9.3/)).toBeNull();
    expect(score.getByRole("link", { name: "查看引用：Unicode [12, 42)" })).toBeTruthy();
  });
  it("preserves history times, document/source identity and pinned evidence links", () => {
    renderDetail();
    const oldRevision = within(screen.getByRole("article", { name: `修订 1 ${fixtureOldRevisionId}` }));
    expect(oldRevision.getAllByText("未知 / 未留存")).toHaveLength(4);
    expect(oldRevision.getByText("历史解析未核验")).toBeTruthy();
    expect(oldRevision.getByRole("link", { name: "此修订的原文片段 [1]" }).getAttribute("href")).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
    expect(oldRevision.queryByText("事件指向的最新修订")).toBeNull();
    const latest = within(screen.getByRole("article", { name: `修订 2 ${fixtureRevisionId}` }));
    expect(latest.getByText("部分解析")).toBeTruthy();
    expect(latest.getByText("2026-10-14T08:00:00+08:00").getAttribute("datetime")).toBe("2026-10-14T00:00:00Z");
    expect(latest.getByText(/外部地址可能已修订/)).toBeTruthy();
  });
  it("moves reading focus without changing the event deep link and exposes complete quote text", () => {
    window.history.replaceState(null, "", `/#events/${fixtureEventId}`);
    renderDetail();
    fireEvent.click(screen.getByRole("button", { name: "原文修订时间线" }));
    expect(document.activeElement).toBe(screen.getByRole("region", { name: "原文修订时间线" }));
    expect(window.location.hash).toBe(`#events/${fixtureEventId}`);
    fireEvent.click(within(screen.getByRole("article", { name: "CVSS 评分" })).getByRole("button", { name: "查看断言与依据" }));
    expect(document.activeElement?.textContent).toContain("fixture_cvss_score");
    const disclosure = within(screen.getByRole("article", { name: "CVSS 评分" })).getByText("展开原文摘录");
    expect(disclosure.closest("details")?.textContent).toContain("评分来自已保存来源断言");
  });
  it("does not retain an earlier response value when a changed projection is rendered", () => {
    const view = renderDetail();
    view.rerender(<EventDetailView detail={{ ...eventDetailFixture, dimensions: [], claims: [], revisions: [], event: { ...eventDetailFixture.event, freshness: "unknown" } }} selectedEvidenceId={null} selectedRevisionId={null} />);
    expect(screen.queryByText(/9.3/)).toBeNull();
    expect(screen.getAllByText("未提供该维度")).toHaveLength(9);
    expect(screen.getByRole("heading", { name: "尚未取得事实记录" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "尚未取得修订记录" })).toBeTruthy();
    expect(screen.getByText(/事件时效未知/)).toBeTruthy();
  });
});

function fixtureApi(options: { detailStatus?: number; detailRead?: Promise<Response>; evidenceStatus?: number; mismatchedRevision?: boolean } = {}) {
  const requests: string[] = [];
  const fixtureUser = { user_id: "r17-detail-fixture-user", tenant_id: "r17-detail-fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
  const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); requests.push(path);
    if (path === "/v1/auth/me") return response(fixtureUser);
    if (path.startsWith("/v1/events?")) return response({ schema_version: 2, items: [eventDetailFixture.event], next_cursor: null, data_mode: "fixture" });
    if (path === `/v1/events/${fixtureEventId}`) return options.detailRead ?? (options.detailStatus ? response({ error: { code: "fixture_detail_failure", retryable: true } }, options.detailStatus) : response(eventDetailFixture));
    if (path === `/v1/evidence/${fixtureOldEvidenceId}`) return options.evidenceStatus ? response({ error: { code: "fixture_evidence_failure", retryable: true } }, options.evidenceStatus) : response({ ...historicalEvidenceFixture, revision_id: options.mismatchedRevision ? fixtureRevisionId : fixtureOldRevisionId });
    throw new Error(`Unexpected isolated R17 route: ${path}`);
  }));
  window.history.replaceState(null, "", `/#events/${fixtureEventId}`);
  return requests;
}

describe("R17 real client to UI path, isolated fixture responses", () => {
  it("shows layout loading without fabricated values before the response arrives", async () => {
    let resolveDetail: (value: Response) => void = () => { throw new Error("fixture detail resolver not initialized"); };
    const detailRead = new Promise<Response>((resolve) => { resolveDetail = resolve; });
    fixtureApi({ detailRead }); render(<App />);
    await screen.findByText("正在取得事件事实与历史版本…");
    expect(document.querySelector(".event-detail-loading")?.getAttribute("aria-busy")).toBe("true");
    expect(document.querySelector(".dimension-value")).toBeNull();
    resolveDetail(new Response(JSON.stringify(eventDetailFixture), { status: 200 }));
    await screen.findByRole("article", { name: "CVSS 评分" });
  });
  it.each([[403, "没有查看权限"], [503, "依赖暂不可用"]])("keeps HTTP %s detail failures distinct from emptiness", async (status, title) => {
    fixtureApi({ detailStatus: Number(status) }); render(<App />);
    await screen.findByRole("heading", { name: String(title) });
    expect(document.querySelector(".event-detail-body")).toBeNull();
    expect(screen.queryByText(/9.3/)).toBeNull();
    expect(screen.queryByRole("heading", { name: "尚未取得事实记录" })).toBeNull();
  });
  it("opens a historical revision from its saved timeline with exact coordinates and focus", async () => {
    const requests = fixtureApi(); render(<App />);
    const oldRevision = within(await screen.findByRole("article", { name: `修订 1 ${fixtureOldRevisionId}` }));
    fireEvent.click(oldRevision.getByRole("link", { name: "此修订的原文片段 [1]" }));
    await screen.findByText(historicalEvidenceFixture.quote_text, { selector: "blockquote" });
    expect(window.location.hash).toBe(`#events/${fixtureEventId}/evidence/${fixtureOldEvidenceId}/revision/${fixtureOldRevisionId}`);
    expect(screen.getByText("[12, 42)")).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("complementary", { name: "证据检视" })));
    expect(requests.filter((path) => path === `/v1/events/${fixtureEventId}`)).toHaveLength(1);
  });
  it.each([{ evidenceStatus: 403 }, { evidenceStatus: 503 }, { mismatchedRevision: true }])("leaves detail usable while failing the selected evidence %j", async (options) => {
    fixtureApi(options); render(<App />);
    const oldRevision = within(await screen.findByRole("article", { name: `修订 1 ${fixtureOldRevisionId}` }));
    fireEvent.click(oldRevision.getByRole("link", { name: "此修订的原文片段 [1]" }));
    await waitFor(() => expect(within(screen.getByRole("complementary", { name: "证据检视" })).getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("article", { name: "CVSS 评分" })).toBeTruthy();
    expect(screen.queryByText(historicalEvidenceFixture.quote_text, { selector: "blockquote" })).toBeNull();
  });
});
