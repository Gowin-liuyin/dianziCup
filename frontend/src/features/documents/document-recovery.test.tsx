import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { detailFixture, documentFixture, documentId, evidenceFixture, revisionId } from "../../../tests/document-fixture";

function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function fixture(options: { historyStatus?: number; lateEvidence?: boolean; changedCurrent?: boolean } = {}) {
  const paths: string[] = [];
  let currentChanged = false;
  let release: () => void = () => {};
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); paths.push(path);
    if (path === "/v1/auth/me") return json({ user_id: "isolated-recovery-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "a".repeat(64) });
    if (path === "/v1/health/live") return json({ status: "live" });
    if (path === "/v1/health/ready") return json({ status: "ready", reason: "fixture", dependencies: {} });
    if (path.startsWith("/v1/documents?")) return json({ schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" });
    if (path.includes("/revisions?")) return path.includes("offset=1") && options.historyStatus ? json({ error: { code: "fixture_rejected" } }, options.historyStatus) : json({ schema_version: 2, items: [documentFixture], next_offset: 1, data_mode: "fixture" });
    if (path.startsWith(`/v1/documents/${documentId}?`)) {
      const more = path.includes("evidence_offset=1");
      if (more) {
        if (options.lateEvidence) await barrier;
        if (options.changedCurrent) currentChanged = true;
        return json({ ...detailFixture, document: { ...documentFixture, is_current: !options.changedCurrent }, evidence: [{ ...evidenceFixture, span_id: "00000000-0000-4000-8000-000000000199", quote_text: "隔离测试：旧版后页原文" }], evidence_total: 2, next_evidence_offset: null });
      }
      if (currentChanged && !path.includes("revision_id=")) return json({ ...detailFixture, document: { ...documentFixture, revision_id: "00000000-0000-4000-8000-000000000198", title: "隔离测试：新当前标题", revision_number: 3 }, evidence: [{ ...evidenceFixture, revision_id: "00000000-0000-4000-8000-000000000198", quote_text: "隔离测试：新当前原文" }] });
      return json({ ...detailFixture, evidence_total: 2, next_evidence_offset: 1 });
    }
    throw new Error(`Unexpected isolated recovery request ${path}`);
  }));
  window.history.replaceState(null, "", `/#documents/${documentId}`);
  return { paths, release };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
describe("document recovery: isolated fixture permission and current-version regressions", () => {
  it.each([403, 404])("removes document, history and catalog after history HTTP %s despite late evidence", async (historyStatus) => {
    const request = fixture({ historyStatus, lateEvidence: true }); render(<App />); await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" }));
    await waitFor(() => expect(request.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "加载更多历史版本" }));
    await screen.findAllByRole("heading", { name: historyStatus === 403 ? "没有资料查看权限" : "资料或版本不可访问" });
    request.release();
    await waitFor(() => expect(document.querySelector(".document-detail-body")).toBeNull());
    expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull(); expect(screen.queryByText("隔离测试：旧版后页原文")).toBeNull();
    expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull(); expect(screen.queryByLabelText("原文修订版本")).toBeNull();
  });
  it("retains partial loaded content for transient history 503", async () => {
    fixture({ historyStatus: 503 }); render(<App />); await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(screen.getByRole("button", { name: "加载更多历史版本" }));
    await screen.findByText("后续历史版本读取失败，已取得的版本仍在此处；版本记录尚未完整。");
    expect(screen.getByText(evidenceFixture.quote_text)).toBeTruthy();
  });
  it("reloads current without revision when the current route became historical", async () => {
    const request = fixture({ changedCurrent: true }); render(<App />); await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" })); await screen.findByRole("link", { name: "查看当前版本 →" });
    const originalReads = request.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length;
    fireEvent.click(screen.getByRole("link", { name: "查看当前版本 →" }));
    await screen.findByRole("heading", { name: "隔离测试：新当前标题" });
    expect(request.paths.filter((path) => path.startsWith(`/v1/documents/${documentId}?`) && !path.includes("revision_id=")).length).toBeGreaterThan(originalReads);
    expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull(); expect(screen.queryByText("隔离测试：旧版后页原文")).toBeNull();
    expect(screen.getByText("已取得 1 / 1 段")).toBeTruthy();
  });
});
