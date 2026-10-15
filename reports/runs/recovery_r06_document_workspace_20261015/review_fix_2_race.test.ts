import { createElement } from "../../../frontend/node_modules/react/index.js";
import { act, cleanup, fireEvent, render, screen, waitFor } from "../../../frontend/node_modules/@testing-library/react/dist/index.js";
import { afterEach, expect, it, vi } from "../../../frontend/node_modules/vitest/dist/index.js";
import { App } from "../../../frontend/src/App";
import { detailFixture, documentFixture, documentId, evidenceFixture, revisionId } from "../../../frontend/tests/document-fixture";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
function fixture(options: { deniedRead?: "history" | "detail"; deniedStatus?: number; transient?: boolean; reloadCurrent?: boolean } = {}) {
  const paths: string[] = [];
  const signals: { path: string; signal: AbortSignal }[] = [];
  let release = () => {};
  let changed = false;
  const barrier = new Promise<void>((resolve) => { release = resolve; });
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const path = String(input); paths.push(path);
    if (path === "/v1/auth/me") return json({ user_id: "independent-race-fixture", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "c".repeat(64) });
    if (path === "/v1/health/live") return json({ status: "live" });
    if (path === "/v1/health/ready") return json({ status: "ready", reason: "fixture", dependencies: {} });
    if (path.startsWith("/v1/documents")) {
      if (request?.signal) signals.push({ path, signal: request.signal });
      if (path.startsWith("/v1/documents?")) {
        if (options.deniedRead) await barrier;
        return json({ schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" });
      }
      if (path.includes("/revisions?")) {
        if (options.deniedRead === "history") return json({ error: { code: "isolated_race_denied" } }, options.deniedStatus);
        if (options.deniedRead === "detail") await barrier;
        if (options.transient && path.includes("offset=1")) return json({ error: { code: "service_unavailable" } }, 503);
        return json({ schema_version: 2, items: [documentFixture], next_offset: 1, data_mode: "fixture" });
      }
      if (options.deniedRead === "detail") return json({ error: { code: "isolated_race_denied" } }, options.deniedStatus);
      if (options.deniedRead === "history") await barrier;
      const more = path.includes("evidence_offset=1");
      if (options.transient && more) return json({ error: { code: "service_unavailable" } }, 503);
      if (options.reloadCurrent && more && path.includes(`revision_id=${revisionId}`)) { changed = true; return json({ ...detailFixture, document: { ...documentFixture, is_current: false }, evidence: [{ ...evidenceFixture, span_id: "00000000-0000-4000-8000-000000000199", quote_text: "隔离测试：旧版本分页原文" }], evidence_total: 2, next_evidence_offset: null }); }
      if (changed) {
        const nextRevision = "00000000-0000-4000-8000-000000000198";
        return json({ ...detailFixture, document: { ...documentFixture, revision_id: nextRevision, revision_number: 3, title: "隔离测试：重读当前第三版" }, evidence: [{ ...evidenceFixture, revision_id: nextRevision, span_id: more ? "00000000-0000-4000-8000-000000000197" : evidenceFixture.span_id, quote_text: more ? "隔离测试：第三版后页" : "隔离测试：第三版首页" }], evidence_total: 2, next_evidence_offset: more ? null : 1 });
      }
      return json({ ...detailFixture, evidence_total: 2, next_evidence_offset: 1 });
    }
    throw new Error(`Unexpected fixture request ${path}`);
  }));
  window.history.replaceState(null, "", `/#documents/${documentId}`);
  return { paths, signals, release: async () => { await act(async () => { release(); await barrier; await Promise.resolve(); }); } };
}

for (const deniedRead of ["history", "detail"] as const) for (const deniedStatus of [403, 404]) {
  it(`initial ${deniedRead} ${deniedStatus} fences delayed other-resource and catalog success`, async () => {
    const request = fixture({ deniedRead, deniedStatus }); render(createElement(App));
    await screen.findByRole("heading", { name: deniedStatus === 403 ? "没有资料查看权限" : "资料或版本不可访问" });
    const pendingSignals = request.signals.filter(({ path }) => path.startsWith("/v1/documents?") || (deniedRead === "history" ? path.startsWith(`/v1/documents/${documentId}?`) : path.includes("/revisions?")));
    expect(pendingSignals.length).toBe(2);
    expect(pendingSignals.every(({ signal }) => signal.aborted)).toBe(true);
    await request.release();
    expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull();
    expect(screen.queryByRole("heading", { name: documentFixture.title })).toBeNull();
    expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull();
    expect(screen.queryByLabelText("原文修订版本")).toBeNull();
    expect(screen.getByRole("heading", { name: "资料列表已清除" })).toBeTruthy();
    expect(screen.queryByText(/本页 \d+ 条/)).toBeNull();
  });
}
it("initial history 401 expires identity before delayed catalog and detail arrive", async () => {
  const request = fixture({ deniedRead: "history", deniedStatus: 401 }); render(createElement(App));
  await screen.findByText("会话已失效，请重新登录。"); await request.release();
  expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull(); expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull();
  expect(request.paths.filter((path) => path === "/v1/auth/me")).toHaveLength(1);
});
it("simultaneous history and evidence 503 preserve partial text with two incomplete notices", async () => {
  fixture({ transient: true }); render(createElement(App)); await screen.findByText(evidenceFixture.quote_text);
  fireEvent.click(screen.getByRole("button", { name: "加载更多历史版本" })); fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" }));
  await screen.findByText("后续历史版本读取失败，已取得的版本仍在此处；版本记录尚未完整。");
  await screen.findByText("后续原文读取失败，已取得的片段不代表全文；本次证据尚未完整。");
  expect(screen.getByText(evidenceFixture.quote_text)).toBeTruthy(); expect(screen.getByRole("link", { name: documentFixture.title })).toBeTruthy();
});
it("same-hash current reload resets pagination then fixes subsequent pages to revision three", async () => {
  const request = fixture({ reloadCurrent: true }); render(createElement(App)); await screen.findByText(evidenceFixture.quote_text);
  fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" }));
  fireEvent.click(await screen.findByRole("link", { name: "查看当前版本 →" }));
  await screen.findByText("隔离测试：第三版首页");
  expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull(); expect(screen.queryByText("隔离测试：旧版本分页原文")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" })); await screen.findByText("隔离测试：第三版后页");
  await waitFor(() => expect(request.paths.some((path) => path.includes("revision_id=00000000-0000-4000-8000-000000000198&evidence_offset=1"))).toBe(true));
  expect(screen.getByText("已取得 2 / 2 段")).toBeTruthy();
});
