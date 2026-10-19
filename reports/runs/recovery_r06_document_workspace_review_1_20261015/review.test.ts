import { createElement } from "../../../frontend/node_modules/react/index.js";
import { cleanup, fireEvent, render, screen, waitFor } from "../../../frontend/node_modules/@testing-library/react/dist/index.js";
import { afterEach, describe, expect, it, vi } from "../../../frontend/node_modules/vitest/dist/index.js";
import { App } from "../../../frontend/src/App";
import { parseDocumentListResponse, parseDocumentDetailResponse } from "../../../frontend/src/api/document-contracts";
import { getDocumentDetail } from "../../../frontend/src/api/document-client";
import { documentFixture, detailFixture, evidenceFixture, documentId, revisionId, historicalRevisionId } from "../../../frontend/tests/document-fixture";

const list = (item: unknown) => ({ schema_version: 2, items: [item], next_cursor: null, data_mode: "fixture" });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

describe("Independent strict DTO boundary negatives: fixture only", () => {
  it.each(["token", "access_token", "key", "api_key", "api-key", "apikey", "secret", "password", "sig", "signature", "x-quaketoken", "x-api-key", "authorization", "cookie", "%74oken", "ToKeN"])("rejects sensitive query %s", (key) => {
    expect(() => parseDocumentListResponse(list({ ...documentFixture, canonical_uri: `https://example.test/?${key}=fixture-value` }))).toThrow();
    expect(() => parseDocumentDetailResponse({ ...detailFixture, license_uri: `https://example.test/?${key}=fixture-value` })).toThrow();
  });
  it.each(["https://user:pass@example.test/", "https://example.test/#fragment", "http://example.test/", "javascript:alert(1)"])("rejects unsafe URI %s", (uri) => expect(() => parseDocumentListResponse(list({ ...documentFixture, canonical_uri: uri }))).toThrow());
  it("accepts 2083 URI characters and rejects 2084 for both URI fields", () => {
    const base = "https://example.test/";
    const allowed = base + "a".repeat(2083 - base.length);
    const denied = allowed + "b";
    expect(parseDocumentListResponse(list({ ...documentFixture, canonical_uri: allowed })).items[0]?.canonical_uri).toBe(allowed);
    expect(() => parseDocumentListResponse(list({ ...documentFixture, canonical_uri: denied }))).toThrow();
    expect(parseDocumentDetailResponse({ ...detailFixture, license_uri: allowed }).license_uri).toBe(allowed);
    expect(() => parseDocumentDetailResponse({ ...detailFixture, license_uri: denied })).toThrow();
  });
  it.each(["2026-02-29T00:00:00Z", "2026-01-01T24:00:00Z", "2026-01-01T00:60:00Z", "2026-01-01T00:00:60Z", "2026-10-15T02:00:00", "2026-10-15"])("rejects impossible or ambiguous timestamp %s", (ingested_at) => expect(() => parseDocumentListResponse(list({ ...documentFixture, ingested_at }))).toThrow());
  it("retains exact timestamp offset and calendar precision", () => {
    const exact = { ...documentFixture, source_published_at: "2024-02-29T12:30:45.123456+08:00", published_precision: "instant" };
    expect(parseDocumentListResponse(list(exact)).items[0]?.source_published_at).toBe(exact.source_published_at);
    expect(parseDocumentListResponse(list(documentFixture)).items[0]?.source_published_at).toBeNull();
    expect(() => parseDocumentListResponse(list({ ...documentFixture, published_at_raw: null }))).toThrow();
    expect(() => parseDocumentListResponse(list({ ...documentFixture, source_published_at: exact.source_published_at }))).toThrow();
  });
  it("enforces Unicode character text limits and source-note bounds", () => {
    expect(parseDocumentListResponse(list({ ...documentFixture, title: "𠀀".repeat(500) })).items[0]?.title.length).toBe(1000);
    expect(() => parseDocumentListResponse(list({ ...documentFixture, title: "𠀀".repeat(501) }))).toThrow();
    for (const patch of [{ source_name: "x".repeat(301) }, { published_at_raw: "x".repeat(257) }, { document_kind: "asset_inventory" }, { is_current: "true" }, { revision_number: 1.5 }, { undocumented: true }]) expect(() => parseDocumentListResponse(list({ ...documentFixture, ...patch }))).toThrow();
    expect(() => parseDocumentDetailResponse({ ...detailFixture, license_identifier: "x".repeat(257) })).toThrow();
    expect(() => parseDocumentDetailResponse({ ...detailFixture, source_notes: ["x".repeat(1001)] })).toThrow();
  });
  it("rejects missing fields, schema/data mode errors and evidence binding errors", () => {
    const { title: ignoredTitle, ...missing } = documentFixture;
    expect(ignoredTitle).toBeTruthy();
    for (const value of [list(missing), { ...list(documentFixture), schema_version: 1 }, { ...list(documentFixture), data_mode: "demo" }]) expect(() => parseDocumentListResponse(value)).toThrow();
    for (const evidence of [{ ...evidenceFixture, revision_id: historicalRevisionId }, { ...evidenceFixture, data_mode: "live" }, { ...evidenceFixture, schema_version: 1 }]) expect(() => parseDocumentDetailResponse({ ...detailFixture, evidence: [evidence] })).toThrow();
  });
  it("rejects late evidence responses from a new current revision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ ...detailFixture, document: { ...documentFixture, revision_id: historicalRevisionId }, evidence: [{ ...evidenceFixture, revision_id: historicalRevisionId }] })));
    await expect(getDocumentDetail(documentId, revisionId, 1)).rejects.toMatchObject({ code: "invalid_response" });
  });
});

function fixture(options: { historyStatus?: number; evidenceStatus?: number } = {}) {
  const paths: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input); paths.push(path);
    if (path === "/v1/auth/me") return json({ user_id: "independent-fixture-user", tenant_id: null, role: "viewer", permissions: ["read:public"], permission_version: 1, data_mode: "fixture", csrf_token: "a".repeat(64) });
    if (path === "/v1/health/live") return json({ status: "live" });
    if (path === "/v1/health/ready") return json({ status: "ready", dependencies: {}, reason: "fixture" });
    if (path.startsWith("/v1/documents?")) return json(list(documentFixture));
    if (path.includes("/revisions?")) {
      if (path.includes("offset=1") && options.historyStatus) return json({ error: { code: "fixture_rejected" } }, options.historyStatus);
      return json({ schema_version: 2, items: [documentFixture], next_offset: 1, data_mode: "fixture" });
    }
    if (path.startsWith(`/v1/documents/${documentId}?`)) {
      if (path.includes("evidence_offset=1") && options.evidenceStatus) return json({ error: { code: "fixture_rejected" } }, options.evidenceStatus);
      return json({ ...detailFixture, evidence_total: 2, next_evidence_offset: 1 });
    }
    throw new Error(`Unexpected fixture route: ${path}`);
  }));
  window.history.replaceState(null, "", `/#documents/${documentId}`);
  return paths;
}

describe("Independent permission after loaded data: fixture only", () => {
  it.each([403, 404])("clears already loaded document body when history page becomes HTTP %s", async (historyStatus) => {
    fixture({ historyStatus }); render(createElement(App));
    await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(await screen.findByRole("button", { name: "加载更多历史版本" }));
    await screen.findByRole("heading", { name: historyStatus === 403 ? "没有资料查看权限" : "资料或版本不可访问" });
    expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull();
    expect(screen.queryByRole("heading", { name: documentFixture.title })).toBeNull();
  });
  it.each([403, 404])("clears detail for evidence HTTP %s", async (evidenceStatus) => {
    fixture({ evidenceStatus }); render(createElement(App)); await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(screen.getByRole("button", { name: "加载更多原文片段" }));
    await screen.findByRole("heading", { name: evidenceStatus === 403 ? "没有资料查看权限" : "资料或版本不可访问" });
    expect(screen.queryByText(evidenceFixture.quote_text)).toBeNull();
    expect(screen.queryByRole("heading", { name: documentFixture.title })).toBeNull();
  });
  it("retains loaded evidence after transient 503 while explaining incomplete history", async () => {
    fixture({ historyStatus: 503 }); render(createElement(App)); await screen.findByText(evidenceFixture.quote_text);
    fireEvent.click(await screen.findByRole("button", { name: "加载更多历史版本" }));
    await screen.findByText("后续历史版本读取失败，已取得的版本仍在此处；版本记录尚未完整。");
    expect(screen.getByText(evidenceFixture.quote_text)).toBeTruthy();
  });
});
