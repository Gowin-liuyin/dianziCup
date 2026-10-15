import { afterEach, describe, expect, it, vi } from "vitest";
import { getEventDetail, getEventList, getEvidence } from "./knowledge-client";

const eventId = "00000000-0000-4000-8000-000000000001";
const revisionId = "00000000-0000-4000-8000-000000000002";
const evidenceId = "00000000-0000-4000-8000-000000000003";
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } }); }

afterEach(() => vi.unstubAllGlobals());
describe("R04 read-only transport — isolated fixture", () => {
  it("encodes only frozen filters and keeps credential/cache behavior", async () => {
    const fixtureFetch = vi.fn().mockResolvedValue(response({ schema_version: 2, items: [], next_cursor: null, data_mode: "fixture" }));
    vi.stubGlobal("fetch", fixtureFetch);
    await getEventList({ q: "标题&cursor=forged", product: "isolated component", risk_type: "advisory", cursor: "opaque cursor", limit: 20 });
    const [path, options] = fixtureFetch.mock.calls[0] ?? [];
    expect(path).toBe("/v1/events?q=%E6%A0%87%E9%A2%98%26cursor%3Dforged&product=isolated+component&risk_type=advisory&cursor=opaque+cursor&limit=20");
    expect(options.credentials).toBe("include");
    expect(options.cache).toBe("no-store");
    expect(options.method).toBeUndefined();
  });
  it.each([401, 403, 404, 503])("keeps HTTP %s as an error instead of a successful empty result", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ error: { code: "fixture_failure", retryable: status === 503 } }, status)));
    await expect(getEventList()).rejects.toMatchObject({ status });
  });
  it("keeps unsupported product filtering explicit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ error: { code: "unsupported_filter", retryable: false } }, 422)));
    await expect(getEventList({ product: "isolated product" })).rejects.toMatchObject({ status: 422, code: "unsupported_filter" });
  });
  it("rejects invalid IDs and limits before network IO", async () => {
    const fixtureFetch = vi.fn();
    vi.stubGlobal("fetch", fixtureFetch);
    await expect(getEventDetail("../other-tenant")).rejects.toMatchObject({ status: 422 });
    await expect(getEventList({ limit: 101 })).rejects.toMatchObject({ status: 422 });
    expect(fixtureFetch).not.toHaveBeenCalled();
  });
  it("rejects a citation that resolves to a different revision", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ schema_version: 2, span_id: evidenceId, revision_id: eventId, block_id: null, start_offset: 0, end_offset: 1, quote_text: "x", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" })));
    await expect(getEvidence(evidenceId, revisionId)).rejects.toMatchObject({ code: "invalid_response" });
  });
  it("compares equivalent UUID spellings without selecting another record", async () => {
    const mixedId = "abcdef00-0000-4000-8000-000000000001";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ schema_version: 2, span_id: mixedId, revision_id: mixedId, block_id: null, start_offset: 0, end_offset: 1, quote_text: "x", quote_sha256: "a".repeat(64), locator_kind: "legacy_unverified", page_number: null, json_pointer: null, verified_at: null, source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" })));
    expect((await getEvidence(mixedId.toUpperCase(), mixedId.toUpperCase())).span_id).toBe(mixedId);
  });
});
