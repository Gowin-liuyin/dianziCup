import { describe, expect, it } from "vitest";
import { parseEventDetailResponse, parseEventListResponse, parseEvidenceResponse } from "./knowledge-contracts";

const eventId = "00000000-0000-4000-8000-000000000001";
const revisionId = "00000000-0000-4000-8000-000000000002";
const evidenceId = "00000000-0000-4000-8000-000000000003";
const eventFixture = { event_id: eventId, event_type: "advisory", title: "隔离测试：无CVE厂商公告", external_ids: ["FIXTURE-ONLY"], primary_product_ids: [], first_seen_at: "2026-10-15T02:00:00Z", status: "active", source_count: 2, latest_revision_id: revisionId, freshness: "unknown" };
const dimensionFixture = { dimension: "cvss", status: "pending", claim_ids: [], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: null };
const evidenceFixture = { schema_version: 2, span_id: evidenceId, revision_id: revisionId, block_id: null, start_offset: 12, end_offset: 17, quote_text: "原文🔎片段", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };

describe("frozen R04 schema 2 — isolated synthetic boundary", () => {
  it("keeps stable IDs, independent source count and unknown freshness", () => {
    const result = parseEventListResponse({ schema_version: 2, items: [eventFixture], next_cursor: "opaque-fixture-cursor", data_mode: "fixture" });
    expect(result.items[0]?.event_id).toBe(eventId);
    expect(result.items[0]?.external_ids).toEqual(["FIXTURE-ONLY"]);
    expect(result.items[0]?.source_count).toBe(2);
    expect(result.items[0]?.freshness).toBe("unknown");
    expect(result.data_mode).toBe("fixture");
  });
  it("accepts a real empty response separately from malformed payloads", () => {
    expect(parseEventListResponse({ schema_version: 2, items: [], next_cursor: null, data_mode: "fixture" }).items).toEqual([]);
  });
  it.each([
    { schema_version: "2", items: [], next_cursor: null, data_mode: "fixture" },
    { schema_version: 2, items: [], next_cursor: "", data_mode: "fixture" },
    { schema_version: 2, items: [], next_cursor: null, data_mode: "fixture", tenant_id: "not-allowed" },
    { schema_version: 2, items: [{ ...eventFixture, source_count: -1 }], next_cursor: null, data_mode: "fixture" },
    { schema_version: 2, items: [{ ...eventFixture, freshness: "safe" }], next_cursor: null, data_mode: "fixture" },
    { schema_version: 2, items: [{ ...eventFixture, first_seen_at: "2026-10-15T02:00:00" }], next_cursor: null, data_mode: "fixture" },
    { schema_version: 2, items: [{ ...eventFixture, storage_key: "not-public" }], next_cursor: null, data_mode: "fixture" },
  ])("rejects a non-conforming event response without default success", (value) => expect(() => parseEventListResponse(value)).toThrow(/数据格式/));
  it("keeps null historical time and URI without inventing current source metadata", () => {
    const result = parseEventDetailResponse({ schema_version: 2, event: eventFixture, dimensions: [dimensionFixture], revisions: [{ revision_id: revisionId, document_id: eventId, revision_number: 1, source_id: evidenceId, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "legacy_unverified", document_kind: "advisory", canonical_uri: null }], claims: [], data_mode: "fixture" });
    expect(result.revisions[0]?.source_published_at).toBeNull();
    expect(result.revisions[0]?.canonical_uri).toBeNull();
    expect(result.dimensions[0]?.status).toBe("pending");
  });
  it("requires a citation for an available enrichment", () => {
    expect(() => parseEventDetailResponse({ schema_version: 2, event: eventFixture, dimensions: [{ ...dimensionFixture, status: "available" }], revisions: [], claims: [], data_mode: "fixture" })).toThrow(/数据格式/);
  });
  it("preserves Unicode coordinates and an unverified legacy locator", () => {
    const result = parseEvidenceResponse(evidenceFixture);
    expect(result.start_offset).toBe(12);
    expect(result.end_offset).toBe(17);
    expect(result.locator_kind).toBe("legacy_unverified");
    expect(result.source_uri).toBeNull();
    expect(result.verified_at).toBeNull();
  });
  it.each([{ ...evidenceFixture, end_offset: 11 }, { ...evidenceFixture, source_uri: "javascript:alert(1)" }, { ...evidenceFixture, source_uri: "https://user:secret@example.test/" }, { ...evidenceFixture, quote_sha256: "invalid" }, { ...evidenceFixture, locator_kind: "first-match-guessed" }])("rejects unsafe or inconsistent evidence fields", (value) => expect(() => parseEvidenceResponse(value)).toThrow(/数据格式/));
  it("retains an empty JSON pointer for a valid root locator", () => {
    expect(parseEvidenceResponse({ ...evidenceFixture, locator_kind: "json_pointer", json_pointer: "" }).json_pointer).toBe("");
  });
});
