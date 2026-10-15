import { describe, expect, it } from "vitest";
import { documentFixture, detailFixture, evidenceFixture } from "../../tests/document-fixture";
import { parseDocumentDetailResponse, parseDocumentListResponse, parseDocumentRevisionsResponse } from "./document-contracts";

const listFixture = { schema_version: 2, items: [documentFixture], next_cursor: null, data_mode: "fixture" };
describe("R06 strict document projection — isolated fixtures", () => {
  it("preserves partial abstract, calendar precision and explicit unknown license", () => {
    expect(parseDocumentListResponse(listFixture).items[0]).toEqual(documentFixture);
    expect(parseDocumentDetailResponse(detailFixture)).toEqual(detailFixture);
    expect(parseDocumentRevisionsResponse({ schema_version: 2, items: [documentFixture], next_offset: null, data_mode: "fixture" }).items).toHaveLength(1);
  });
  it.each([
    { ...documentFixture, tenant_id: "forged" }, { ...documentFixture, document_kind: "asset_inventory" },
    { ...documentFixture, source_category: "fake" }, { ...documentFixture, is_current: "true" },
    { ...documentFixture, canonical_uri: "javascript:alert(1)" }, { ...documentFixture, canonical_uri: "https://user:secret@example.test" },
    { ...documentFixture, canonical_uri: "http://example.test" }, { ...documentFixture, published_precision: "instant" },
    { ...documentFixture, ingested_at: "2026-02-30T02:00:00Z" }, { ...documentFixture, title: " " },
    { ...documentFixture, published_at_raw: null }, { ...documentFixture, source_published_at: "2026-10-15T02:00:00Z" },
    { ...documentFixture, canonical_uri: "https://example.test/?x-api-key=secret" }, { ...documentFixture, canonical_uri: "https://example.test/#fragment" },
  ])("rejects an invalid document boundary %j", (document) => {
    expect(() => parseDocumentListResponse({ ...listFixture, items: [document] })).toThrow();
  });
  it.each([
    { ...listFixture, next_cursor: "" }, { ...listFixture, schema_version: "2" }, { ...listFixture, data_mode: "online" },
  ])("rejects invalid envelope %j", (value) => expect(() => parseDocumentListResponse(value)).toThrow());
  it("rejects evidence with another revision or data mode", () => {
    expect(() => parseDocumentDetailResponse({ ...detailFixture, evidence: [{ ...evidenceFixture, revision_id: documentFixture.document_id }] })).toThrow();
    expect(() => parseDocumentDetailResponse({ ...detailFixture, evidence: [{ ...evidenceFixture, data_mode: "live" }] })).toThrow();
  });
  it("rejects untrusted license URLs, impossible totals and unbounded source notes", () => {
    for (const value of [{ ...detailFixture, license_uri: "javascript:alert(1)" }, { ...detailFixture, evidence_total: 0 }, { ...detailFixture, source_notes: Array(21).fill("x") }]) expect(() => parseDocumentDetailResponse(value)).toThrow();
  });
});
