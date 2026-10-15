import { randomBytes } from "node:crypto";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../../App";

const eventId = "00000000-0000-4000-8000-000000000001";
const revisionId = "00000000-0000-4000-8000-000000000002";
const evidenceId = "00000000-0000-4000-8000-000000000003";
const secondEventId = "00000000-0000-4000-8000-000000000004";
const fixtureUser = { user_id: "fixture-r04-user", tenant_id: "fixture-r04-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: randomBytes(32).toString("hex") };
const eventFixture = { event_id: eventId, event_type: "advisory", title: "隔离测试：无CVE厂商公告", external_ids: [], primary_product_ids: [], first_seen_at: "2026-10-15T02:00:00Z", status: "active", source_count: 2, latest_revision_id: revisionId, freshness: "stale" };
const citationFixture = { evidence_id: evidenceId, revision_id: revisionId, quote: "历史原文片段", locator: "Unicode [10, 16)", source_uri: "https://example.test/isolated-revision" };
const detailFixture = { schema_version: 2, event: eventFixture, dimensions: [{ dimension: "versions", status: "available", claim_ids: [], citations: [citationFixture], freshness: "stale", observed_at: null, source_version: "isolated revision", error_code: null }, { dimension: "poc", status: "failed", claim_ids: [], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: "fixture_upstream_failure" }], revisions: [{ revision_id: revisionId, document_id: eventId, revision_number: 1, source_id: evidenceId, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "legacy_unverified", document_kind: "advisory", canonical_uri: null }], claims: [{ claim_id: secondEventId, predicate: "isolated_predicate", display_value: "<img src=x onerror=alert('fixture')>", origin: "model_hypothesis", status: "unverified", source_revision_id: revisionId, evidence_ids: [evidenceId] }], data_mode: "fixture" };
const evidenceFixture = { schema_version: 2, span_id: evidenceId, revision_id: revisionId, block_id: null, start_offset: 10, end_offset: 16, quote_text: "历史原文片段", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };

function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }
function navigate(hash: string) { window.history.replaceState(null, "", `/${hash}`); fireEvent(window, new HashChangeEvent("hashchange")); }

function fixtureApi(options: { listStatus?: number; rawError?: boolean; empty?: boolean; unsupported?: boolean; pagination?: boolean; mismatchedRevision?: boolean } = {}) {
  const requests: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    requests.push(path);
    if (path === "/v1/auth/me") return response(fixtureUser);
    if (path === "/v1/health/live") return response({ status: "live" });
    if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
    if (path.startsWith("/v1/events?")) {
      if (options.listStatus) return options.rawError ? new Response("isolated non-JSON upstream failure", { status: options.listStatus }) : response({ error: { code: "fixture_failure", retryable: false } }, options.listStatus);
      if (options.unsupported && path.includes("product=")) return response({ error: { code: "unsupported_filter", retryable: false } }, 422);
      const secondPage = path.includes("cursor=opaque-fixture");
      return response({ schema_version: 2, items: options.empty ? [] : secondPage ? [{ ...eventFixture, event_id: secondEventId, title: "隔离测试：下一页事件" }] : [eventFixture], next_cursor: options.pagination && !secondPage ? "opaque-fixture" : null, data_mode: "fixture" });
    }
    if (path === `/v1/events/${eventId}`) return response(detailFixture);
    if (path === `/v1/evidence/${evidenceId}`) return response({ ...evidenceFixture, revision_id: options.mismatchedRevision ? secondEventId : revisionId });
    throw new Error(`Unexpected isolated fixture route: ${path}`);
  }));
  window.history.replaceState(null, "", "/#events");
  return requests;
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });
describe("R04 event/detail/evidence — isolated fixture mode only", () => {
  it("shows one saved event with two visible sources without inventing CVE or totals", async () => {
    fixtureApi();
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    expect(screen.getByText("本页 1 条 · 合成 / Fixture")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("未提供公开标识")).toBeTruthy();
    expect(screen.getByText("已过期")).toBeTruthy();
    expect(screen.queryByText("暂无风险")).toBeNull();
  });
  it("uses the opaque cursor without appending stale records as a new total", async () => {
    const requests = fixtureApi({ pagination: true });
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    await screen.findByRole("link", { name: "隔离测试：下一页事件" });
    expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull();
    expect(requests.some((path) => path === "/v1/events?cursor=opaque-fixture&limit=20")).toBe(true);
  });
  it("shows an actual empty response as query-scoped emptiness", async () => {
    fixtureApi({ empty: true });
    render(<App />);
    await screen.findByRole("heading", { name: "本次查询没有事件记录" });
    expect(screen.getByText("本页 0 条 · 合成 / Fixture")).toBeTruthy();
    expect(screen.queryByText("情报服务待接通")).toBeNull();
  });
  it.each([[404, "情报服务待接通"], [403, "没有查看权限"], [503, "依赖暂不可用"]])("separates HTTP %s from an empty result", async (status, title) => {
    fixtureApi({ listStatus: Number(status) });
    render(<App />);
    await screen.findByRole("heading", { name: String(title) });
    expect(screen.queryByText(/本页 0 条/)).toBeNull();
    expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull();
  });
  it("expires frontend identity on a business 401 without a restore loop", async () => {
    const requests = fixtureApi({ listStatus: 401 });
    render(<App />);
    await screen.findByText("会话已失效，请重新登录。");
    expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull();
    expect(screen.queryByText(/本页 0 条/)).toBeNull();
    expect(requests.filter((path) => path === "/v1/auth/me")).toHaveLength(1);
    expect(requests.filter((path) => path.startsWith("/v1/events?"))).toHaveLength(1);
    expect(screen.getByRole("button", { name: "重新登录" })).toBeTruthy();
  });
  it("does not treat an unsupported product filter as no matches", async () => {
    fixtureApi({ unsupported: true });
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    fireEvent.change(screen.getByLabelText("产品筛选"), { target: { value: "isolated product" } });
    fireEvent.click(screen.getByRole("button", { name: "检索情报" }));
    await screen.findByRole("heading", { name: "筛选能力尚未接通" });
    expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull();
    expect(screen.queryByText(/本页 0 条/)).toBeNull();
  });
  it("displays failed/missing dimensions, legacy time and a hypothesis as text", async () => {
    fixtureApi();
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    navigate(`#events/${eventId}`);
    await screen.findByText("模型假设");
    expect(screen.getByText("未核验")).toBeTruthy();
    expect(screen.getByText("fixture_upstream_failure")).toBeTruthy();
    expect(screen.getAllByText("未提供该维度")).toHaveLength(7);
    expect(screen.getAllByText("未知 / 未留存")).toHaveLength(4);
    expect(screen.getByText("<img src=x onerror=alert('fixture')>")).toBeTruthy();
    expect(document.querySelector("img")).toBeNull();
  });
  it("opens the cited historical version and preserves Unicode coordinates on a deep link", async () => {
    fixtureApi();
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    navigate(`#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`);
    await screen.findByText("历史原文片段");
    expect(screen.getByText("[10, 16)")).toBeTruthy();
    expect(screen.getByText("历史定位未核验")).toBeTruthy();
    expect(screen.getAllByText(revisionId).length).toBeGreaterThan(0);
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("complementary", { name: "证据检视" })));
  });
  it("does not display a citation when the response revision differs", async () => {
    fixtureApi({ mismatchedRevision: true });
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    navigate(`#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`);
    await screen.findByText("服务返回的数据格式不符合接口约定，请重新检查。");
    await waitFor(() => expect(document.querySelector("blockquote")).toBeNull());
  });
  it.each([200, 401])("discards a former identity's delayed HTTP %s after login changes", async (lateStatus) => {
    let resolveOldRead: (value: Response) => void = () => { throw new Error("isolated old read was not initialized"); };
    const oldRead = new Promise<Response>((resolve) => { resolveOldRead = resolve; });
    let cookieUser: "a" | "b" | null = "a";
    let listRequests = 0;
    const newNonce = randomBytes(32).toString("hex");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = String(input);
      if (path === "/v1/auth/me") return cookieUser === null ? response({ error: { code: "unauthenticated", retryable: false } }, 401) : response({ ...fixtureUser, user_id: `fixture-user-${cookieUser}`, tenant_id: `fixture-tenant-${cookieUser}`, csrf_token: cookieUser === "a" ? fixtureUser.csrf_token : newNonce });
      if (path === "/v1/auth/login") { cookieUser = "b"; return response({ user_id: "fixture-user-b", csrf_token: newNonce, expires_at: "2099-01-01T00:00:00Z" }); }
      if (path === "/v1/auth/logout") { cookieUser = null; return response({ status: "logged_out" }); }
      if (path === "/v1/health/live") return response({ status: "live" });
      if (path === "/v1/health/ready") return response({ status: "ready", reason: "isolated fixture", dependencies: {} });
      if (path.startsWith("/v1/events?")) {
        listRequests += 1;
        if (listRequests === 1) return oldRead;
        return response({ schema_version: 2, items: [{ ...eventFixture, title: "隔离测试：新身份事件" }], next_cursor: null, data_mode: "fixture" });
      }
      throw new Error("unexpected isolated cache fence request");
    }));
    window.history.replaceState(null, "", "/#events");
    render(<App />);
    await screen.findByText("正在查询授权范围内的事件…");
    navigate("#session");
    fireEvent.click(screen.getByRole("button", { name: "退出登录" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "登录工作台" }).hasAttribute("disabled")).toBe(false));
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "fixture-user-b" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "fixture-password" } });
    fireEvent.click(screen.getByRole("button", { name: "登录工作台" }));
    await screen.findByText("fixture-user-b");
    navigate("#events");
    await screen.findByRole("link", { name: "隔离测试：新身份事件" });
    resolveOldRead(lateStatus === 200 ? response({ schema_version: 2, items: [eventFixture], next_cursor: null, data_mode: "fixture" }) : response({ error: { code: "unauthenticated", retryable: false } }, 401));
    await waitFor(() => expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull());
    expect(screen.getByRole("link", { name: "隔离测试：新身份事件" })).toBeTruthy();
    expect(screen.queryByText("会话已失效，请重新登录。")).toBeNull();
    expect(listRequests).toBe(2);
  });
});


describe("R04 review regressions — explicit isolated fixtures", () => {
  it("rejects a wrong revision after clicking a claim reference", async () => {
    fixtureApi({ mismatchedRevision: true });
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    navigate(`#events/${eventId}`);
    const citation = await screen.findByRole("link", { name: "原文片段 [1]" });
    fireEvent.click(citation);
    await screen.findByText("服务返回的数据格式不符合接口约定，请重新检查。");
    expect(screen.queryByText("历史原文片段", { selector: "blockquote" })).toBeNull();
  });

  it.each([403, 503])("clears selected detail and evidence before a new filter returns %s", async (status) => {
    const options: { listStatus?: number } = {};
    fixtureApi(options);
    render(<App />);
    await screen.findByRole("link", { name: eventFixture.title });
    navigate(`#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`);
    await screen.findByText("历史原文片段", { selector: "blockquote" });
    await screen.findByText("模型假设");
    options.listStatus = status;
    fireEvent.change(screen.getByLabelText("检索关键词"), { target: { value: "changed scope" } });
    fireEvent.click(screen.getByRole("button", { name: "检索情报" }));
    await screen.findByText(status === 403 ? "没有查看权限" : "依赖暂不可用");
    expect(screen.queryByText("模型假设")).toBeNull();
    expect(screen.queryByText("历史原文片段", { selector: "blockquote" })).toBeNull();
    expect(window.location.hash).toBe("#events");
  });
});


it("expires the identity after an upstream empty/HTML 401 without restoring the session", async () => {
  const requests = fixtureApi({ listStatus: 401, rawError: true });
  render(<App />);
  await screen.findByText("会话已失效，请重新登录。");
  expect(screen.queryByRole("link", { name: eventFixture.title })).toBeNull();
  expect(requests.filter((path) => path === "/v1/auth/me")).toHaveLength(1);
});
