import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";
import { detailFixture, documentFixture, documentId, evidenceFixture, historicalRevisionId, revisionId } from "../../../tests/document-fixture";

function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
function navigate(hash: string) { window.history.replaceState(null, "", `/${hash}`); fireEvent(window, new HashChangeEvent("hashchange")); }
function fixtureApi(options: { listStatus?: number; detailStatus?: number; anonymous?: boolean; noPermission?: boolean; empty?: boolean; metadataOnly?: boolean; paginate?: boolean; delayed?: boolean } = {}) {
  const paths: string[] = [];
  let release: (value: Response) => void = () => {};
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); paths.push(path);
    if (path === "/v1/auth/me") return options.anonymous ? response({ error: { code: "unauthenticated" } }, 401) : response({ user_id: "isolated-document-fixture", tenant_id: null, role: "viewer", permissions: options.noPermission ? [] : ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") });
    if (path === "/v1/health/live") return response({ status: "live" });
    if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
    if (path.startsWith("/v1/documents?")) {
      if (options.listStatus) return response({ error: { code: "fixture_failure" } }, options.listStatus);
      if (options.delayed) return new Promise<Response>((resolve) => { release = resolve; });
      return response({ schema_version: 2, items: options.empty ? [] : [{ ...documentFixture, title: path.includes("cursor=") ? "隔离测试：下一页政策" : documentFixture.title }], next_cursor: options.paginate && !path.includes("cursor=") ? "opaque-fixture" : null, data_mode: "fixture" });
    }
    if (path.includes("/revisions?")) return response({ schema_version: 2, items: path.includes("offset=1") ? [{ ...documentFixture, revision_id: historicalRevisionId, revision_number: 1, is_current: false, title: "隔离测试：历史研究标题" }] : [documentFixture], next_offset: options.paginate && !path.includes("offset=1") ? 1 : null, data_mode: "fixture" });
    if (path.startsWith(`/v1/documents/${documentId}?`)) {
      if (options.detailStatus) return response({ error: { code: "fixture_failure" } }, options.detailStatus);
      const historical = path.includes(historicalRevisionId);
      const extra = path.includes("evidence_offset=1");
      return response({ ...detailFixture, document: { ...documentFixture, ...(historical ? { revision_id: historicalRevisionId, revision_number: 1, is_current: false, title: "隔离测试：历史研究标题" } : {}), ...(options.metadataOnly ? { content_coverage: "metadata" } : {}) },
        evidence: options.metadataOnly ? [] : [{ ...evidenceFixture, ...(historical ? { revision_id: historicalRevisionId, quote_text: "隔离测试历史原文" } : {}), ...(extra ? { span_id: "00000000-0000-4000-8000-000000000106", quote_text: "隔离测试后续原文" } : {}) }], evidence_total: options.metadataOnly ? 0 : options.paginate ? 2 : 1, next_evidence_offset: options.paginate && !extra ? 1 : null });
    }
    throw new Error(`Unexpected isolated fixture request ${path}`);
  }));
  window.history.replaceState(null, "", "/#documents");
  return { paths, release: (value: Response) => release(value) };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
describe("R06 document workspace — isolated fixtures only", () => {
  it("distinguishes actual page count, abstract, partial and calendar date", async () => {
    fixtureApi(); render(<App />);
    await screen.findByRole("link", { name: documentFixture.title });
    expect(screen.getByText("本页 1 条 · 合成 / Fixture")).toBeTruthy();
    expect(screen.getByText("仅日期 · 时刻未知")).toBeTruthy();
    expect(screen.getByText("仅摘要")).toBeTruthy();
    navigate(`#documents/${documentId}`);
    await screen.findByRole("heading", { name: documentFixture.title });
    expect(screen.getByText("部分解析")).toBeTruthy();
    expect(screen.getByText("覆盖：仅摘要。未保存完整正文。")).toBeTruthy();
    expect(screen.getByText(evidenceFixture.quote_text)).toBeTruthy();
    expect(document.querySelector(".document-evidence img")).toBeNull();
    expect(screen.getByRole("link", { name: "打开此版本来源地址 ↗" }).getAttribute("rel")).toBe("noopener noreferrer");
  });
  it("binds the opaque cursor to filters and resets selection for a new query", async () => {
    const fixture = fixtureApi({ paginate: true }); render(<App />); await screen.findByRole("link", { name: documentFixture.title });
    fireEvent.change(screen.getByLabelText("资料类型"), { target: { value: "paper" } }); fireEvent.change(screen.getByLabelText("检索关键词"), { target: { value: "模型" } }); fireEvent.click(screen.getByRole("button", { name: "检索资料" }));
    await waitFor(() => expect(fixture.paths.some((path) => path.includes("q=%E6%A8%A1%E5%9E%8B&document_kind=paper"))).toBe(true));
    await screen.findByRole("link", { name: documentFixture.title }); fireEvent.click(screen.getByRole("button", { name: "下一页资料" }));
    await screen.findByRole("link", { name: "隔离测试：下一页政策" });
    expect(fixture.paths.some((path) => path.includes("document_kind=paper&cursor=opaque-fixture"))).toBe(true);
    expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull();
  });
  it("loads evidence against the saved revision and loads full historical choices", async () => {
    const fixture = fixtureApi({ paginate: true }); render(<App />); await screen.findByRole("link", { name: documentFixture.title }); navigate(`#documents/${documentId}`);
    await screen.findByRole("heading", { name: documentFixture.title });
    fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" })); await screen.findByText("隔离测试后续原文");
    expect(fixture.paths.some((path) => path.includes(`revision_id=${revisionId}&evidence_offset=1`))).toBe(true);
    expect(screen.getByText("已取得 2 / 2 段")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "加载更多历史版本" })); await screen.findByRole("option", { name: "修订 1 · 历史 · 隔离测试：历史研究标题" });
    navigate(`#documents/${documentId}/revision/${historicalRevisionId}`);
    await screen.findByRole("heading", { name: "隔离测试：历史研究标题" });
    expect(screen.queryByText("隔离测试后续原文")).toBeNull();
    expect(screen.getByText("隔离测试历史原文")).toBeTruthy();
    expect(screen.getByRole("link", { name: "查看当前版本 →" })).toBeTruthy();
  });
  it("does not equate metadata with available body", async () => {
    fixtureApi({ metadataOnly: true }); render(<App />); await screen.findByRole("link", { name: documentFixture.title }); navigate(`#documents/${documentId}`);
    await screen.findByRole("heading", { name: "没有可定位的原文片段" }); expect(screen.getByText("已取得 0 / 0 段")).toBeTruthy();
  });
  it("keeps successful empty results distinct from errors", async () => { fixtureApi({ empty: true }); render(<App />); await screen.findByRole("heading", { name: "本次查询没有资料记录" }); expect(screen.getByText("本页 0 条 · 合成 / Fixture")).toBeTruthy(); });
  it.each([[403, "没有资料查看权限"], [404, "资料服务待接通"], [503, "资料依赖暂不可用"]])("separates list HTTP %s", async (status, title) => {
    fixtureApi({ listStatus: Number(status) }); render(<App />); await screen.findByRole("heading", { name: String(title) }); expect(screen.queryByText(/本页 0 条/)).toBeNull(); expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull();
  });
  it("performs no anonymous business request", async () => { const fixture = fixtureApi({ anonymous: true }); render(<App />); await screen.findByRole("heading", { name: "登录后核查资料" }); expect(fixture.paths.some((path) => path.startsWith("/v1/documents"))).toBe(false); });
  it("expires identity for detail 401 without an auth restore loop", async () => {
    const fixture = fixtureApi({ detailStatus: 401 }); render(<App />); await screen.findByRole("link", { name: documentFixture.title }); navigate(`#documents/${documentId}`);
    await screen.findByText("会话已失效，请重新登录。"); expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull(); expect(fixture.paths.filter((path) => path === "/v1/auth/me")).toHaveLength(1);
  });
  it("ignores a late list response after logout", async () => {
    const fixture = fixtureApi({ delayed: true }); render(<App />); await screen.findByText("正在查询授权范围内的资料…"); navigate("#session");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ status: "logged_out" })));
    fireEvent.click(screen.getByRole("button", { name: "退出登录" })); await screen.findByRole("button", { name: "登录工作台" });
    fixture.release(response({ schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" })); navigate("#documents");
    await screen.findByRole("heading", { name: "登录后核查资料" }); expect(screen.queryByRole("link", { name: documentFixture.title })).toBeNull();
  });
});
