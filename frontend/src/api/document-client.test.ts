import { afterEach, describe, expect, it, vi } from "vitest";
import { detailFixture, documentFixture, documentId, revisionId } from "../../tests/document-fixture";
import { getDocumentDetail, getDocumentList, getDocumentRevisions } from "./document-client";
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
afterEach(() => vi.unstubAllGlobals());
describe("R06 read-only document transport — isolated fixtures", () => {
  it("encodes frozen filters while retaining the shared cookie/cache policy", async () => {
    const fetchFixture = vi.fn().mockResolvedValue(response({ schema_version: 2, items: [], next_cursor: null, data_mode: "fixture" }));
    vi.stubGlobal("fetch", fetchFixture);
    await getDocumentList({ q: "模型&tenant=forged", document_kind: "paper", source_category: "academic_paper", cursor: "opaque next", limit: 20 });
    const [path, options] = fetchFixture.mock.calls[0] ?? [];
    expect(path).toBe("/v1/documents?q=%E6%A8%A1%E5%9E%8B%26tenant%3Dforged&document_kind=paper&source_category=academic_paper&cursor=opaque+next&limit=20");
    expect(options.credentials).toBe("include"); expect(options.cache).toBe("no-store"); expect(options.method).toBeUndefined();
  });
  it.each([401, 403, 404, 503])("retains HTTP %s as an error", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ error: { code: "fixture_failure" } }, status)));
    await expect(getDocumentList()).rejects.toMatchObject({ status });
  });
  it("rejects input boundaries before any IO", async () => {
    const fetchFixture = vi.fn(); vi.stubGlobal("fetch", fetchFixture);
    for (const filters of [{ q: "x\0y" }, { q: "x".repeat(501) }, { limit: 101 }, { cursor: "" }]) await expect(getDocumentList(filters)).rejects.toMatchObject({ status: 422 });
    await expect(getDocumentDetail("../private")).rejects.toMatchObject({ status: 422 });
    await expect(getDocumentDetail(documentId, null, 100)).rejects.toMatchObject({ status: 422 });
    await expect(getDocumentRevisions(documentId, -1)).rejects.toMatchObject({ status: 422 });
    expect(fetchFixture).not.toHaveBeenCalled();
  });
  it("rejects mismatched document, revision and non-advancing evidence pages", async () => {
    for (const value of [{ ...detailFixture, document: { ...documentFixture, document_id: revisionId } }, { ...detailFixture, next_evidence_offset: 100 }]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(value)));
      await expect(getDocumentDetail(documentId, revisionId, 100)).rejects.toMatchObject({ code: "invalid_response" });
    }
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ...detailFixture, document: { ...documentFixture, revision_id: documentId }, evidence: [] })));
    await expect(getDocumentDetail(documentId, revisionId)).rejects.toMatchObject({ code: "invalid_response" });
  });
  it("rejects histories for another document or a repeated offset", async () => {
    for (const value of [{ schema_version: 2, items: [{ ...documentFixture, document_id: revisionId }], next_offset: null, data_mode: "fixture" }, { schema_version: 2, items: [], next_offset: 20, data_mode: "fixture" }]) {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(value)));
      await expect(getDocumentRevisions(documentId, 20)).rejects.toMatchObject({ code: "invalid_response" });
    }
  });
});
