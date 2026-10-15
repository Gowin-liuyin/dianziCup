import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, afterEach, vi } from "vitest";
import { collectSourcePage } from "./source-client";
import { isSourceKind, sourceKinds, type SourceSubmission } from "./source-contracts";
import { sourceCatalog } from "../features/sources/source-catalog";

const expectedKeys = ["nvd_ollama", "vllm_vendor", "osv_ollama", "avid_community", "ollama_releases", "trailofbits_blog", "arxiv_security", "nist_ai_rmf", "cac_generative_ai"];
const jobId = "00000000-0000-4000-8000-000000000001";
const body = { window_end: "2026-10-15T06:00:00Z", stream_kind: "live", max_pages: 5 };
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
afterEach(() => vi.unstubAllGlobals());
describe("frozen nine-source catalog boundary — isolated transport fixtures", () => {
  it("matches nine backend keys and eight source categories", () => {
    const source = readFileSync(resolve(process.cwd(), "../backend/src/ai_intel/ingestion/source_catalog.py"), "utf8");
    const catalogText = source.slice(source.indexOf("CATALOG_SOURCES:"), source.indexOf("HEX_SHA ="));
    const backend = [...catalogText.matchAll(/"([a-z_]+)": _source\(\s*"[a-z_]+",\s*"[^"]+",\s*SourceCategory\.([A-Z_]+),\s*"https:[^"]+",\s*"([a-z_]+)"/g)].map((match) => ({ key: match[1], category: match[2]?.toLowerCase(), contentScope: match[3] }));
    expect(sourceKinds).toEqual(expectedKeys); expect(Object.keys(sourceCatalog)).toEqual(expectedKeys);
    expect(backend.map((entry) => entry.key)).toEqual(expectedKeys);
    for (const entry of backend) { expect(entry.key).toBeTruthy(); const key = sourceKinds.find((key) => key === entry.key); expect(key).toBeDefined(); if (key) { expect(sourceCatalog[key].category).toBe(entry.category); expect(sourceCatalog[key].contentScope).toBe(entry.contentScope); } }
    expect(new Set(Object.values(sourceCatalog).map((source) => source.category)).size).toBe(8);
  });
  it.each(expectedKeys)("writes only the approved key %s with unchanged request and CSRF", async (key) => {
    expect(isSourceKind(key)).toBe(true); if (!isSourceKind(key)) throw new Error("catalog test key absent");
    const calls: { path: string; options: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      calls.push({ path: String(input), options });
      return String(input) === "/v1/auth/csrf" ? json({ csrf_token: "isolated-csrf", header_name: "X-CSRF-Token" }) : json({ job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null }, 202);
    }));
    const submission: SourceSubmission = { sourceKind: key, body: { ...body, stream_kind: "live" }, idempotencyKey: "isolated-nine-source" };
    await collectSourcePage(submission, () => true);
    const write = calls[1]; expect(write?.path).toBe(`/v1/sources/${key}/collect`);
    expect(write?.options.body).toBe(JSON.stringify(body)); expect(write?.options.credentials).toBe("include");
    expect(new Headers(write?.options.headers).get("X-CSRF-Token")).toBe("isolated-csrf");
  });
  it.each(["../sources", "https://example.test", "nvd_ollama?tenant=other", "constructor", "__proto__", "unknown_source"])("rejects unregistered source input %s", (key) => expect(isSourceKind(key)).toBe(false));
});
