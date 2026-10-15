import { randomBytes } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";
import { collectSourcePage, getSourceJob } from "./source-client";
import type { SourceSubmission } from "./source-contracts";

const jobId = "00000000-0000-4000-8000-000000000001";
const csrf = randomBytes(32).toString("hex");
const job = { job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null };
const submission: SourceSubmission = { sourceKind: "nvd_ollama", body: { window_end: "2026-10-15T06:00:00+08:00", stream_kind: "live", max_pages: 5 }, idempotencyKey: "isolated-source-round" };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
afterEach(() => vi.unstubAllGlobals());

describe("fixed source transport — isolated fixture", () => {
  it("uses the session CSRF header and exactly the frozen body and retry identity", async () => {
    const calls: { path: string; options: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options: RequestInit) => {
      calls.push({ path: String(input), options });
      return String(input) === "/v1/auth/csrf" ? response({ csrf_token: csrf, header_name: "X-CSRF-Token" }) : response(job, 202);
    }));
    await collectSourcePage(submission, () => true);
    await collectSourcePage(submission, () => true);
    const writes = calls.filter((call) => call.path.endsWith("/collect"));
    expect(writes).toHaveLength(2);
    expect(writes[0]?.path).toBe("/v1/sources/nvd_ollama/collect");
    expect(writes[0]?.options.body).toBe(JSON.stringify(submission.body));
    expect(writes[1]?.options.body).toBe(writes[0]?.options.body);
    for (const write of writes) {
      const headers = new Headers(write.options.headers);
      expect(headers.get("X-CSRF-Token")).toBe(csrf);
      expect(headers.get("Idempotency-Key")).toBe(submission.idempotencyKey);
      expect(headers.has("Origin")).toBe(false);
      expect(write.options.credentials).toBe("include");
      expect(write.options.cache).toBe("no-store");
    }
  });
  it.each(["generation", "abort"])("does not POST after %s changes during CSRF fetch", async (change) => {
    let current = true;
    const controller = new AbortController();
    const fixtureFetch = vi.fn(async () => {
      if (change === "generation") current = false; else controller.abort();
      return response({ csrf_token: csrf, header_name: "X-CSRF-Token" });
    });
    vi.stubGlobal("fetch", fixtureFetch);
    await expect(collectSourcePage(submission, () => current, controller.signal)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fixtureFetch).toHaveBeenCalledTimes(1);
  });
  it.each([401, 403, 409, 503])("preserves HTTP %s without a successful job", async (status) => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => String(input) === "/v1/auth/csrf" ? response({ csrf_token: csrf, header_name: "X-CSRF-Token" }) : response({ error: { code: "isolated_failure", retryable: status === 503 } }, status)));
    await expect(collectSourcePage(submission, () => true)).rejects.toMatchObject({ status });
  });
  it("does not write on CSRF expiry", async () => {
    const fixtureFetch = vi.fn().mockResolvedValue(response({ error: { code: "session_expired" } }, 401));
    vi.stubGlobal("fetch", fixtureFetch);
    await expect(collectSourcePage(submission, () => true)).rejects.toMatchObject({ status: 401 });
    expect(fixtureFetch).toHaveBeenCalledTimes(1);
  });
  it("captures validated body and key before a delayed CSRF response", async () => {
    const mutable: SourceSubmission = { ...submission, body: { ...submission.body } };
    let release: (value: Response) => void = () => { throw new Error("isolated CSRF not initialized"); };
    const delayed = new Promise<Response>((resolve) => { release = resolve; });
    const fixtureFetch = vi.fn(async (input: RequestInfo | URL) => String(input) === "/v1/auth/csrf" ? delayed : response(job, 202));
    vi.stubGlobal("fetch", fixtureFetch);
    const reading = collectSourcePage(mutable, () => true);
    mutable.body.max_pages = 20;
    mutable.idempotencyKey = "changed-outside-operation";
    release(response({ csrf_token: csrf, header_name: "X-CSRF-Token" }));
    await reading;
    expect(fixtureFetch.mock.calls[1]?.[0]).toBe("/v1/sources/nvd_ollama/collect");
    const [, write] = vi.mocked(fetch).mock.calls[1] ?? [];
    expect(write?.body).toBe(JSON.stringify(submission.body));
    expect(new Headers(write?.headers).get("Idempotency-Key")).toBe(submission.idempotencyKey);
  });
  it("rejects invalid input before network and mismatching job IDs after GET", async () => {
    const fixtureFetch = vi.fn().mockResolvedValue(response({ ...job, job_id: "00000000-0000-4000-8000-000000000002" }));
    vi.stubGlobal("fetch", fixtureFetch);
    await expect(getSourceJob("../not-a-job")).rejects.toMatchObject({ status: 422 });
    expect(fixtureFetch).not.toHaveBeenCalled();
    await expect(getSourceJob(jobId)).rejects.toMatchObject({ code: "invalid_response" });
  });
});
