import { describe, expect, it } from "vitest";
import { parseSourceJob, validateSourceSubmission, type SourceJobStatus } from "./source-contracts";

const jobId = "00000000-0000-4000-8000-000000000001";
const jobFixture = { job_id: jobId, status: "queued", attempt_count: 0, error_code: null, result_ref: null, created_at: "2026-10-15T06:00:00Z", finished_at: null };
const body = { window_end: "2026-10-15T06:00:00+08:00", stream_kind: "live", max_pages: 5 };

describe("source jobs frozen boundary — isolated fixture", () => {
  it.each<SourceJobStatus>(["queued", "running", "retry_wait", "succeeded", "partial", "failed", "blocked", "cancelled", "waiting_approval"])("accepts SQL state %s and null unknowns", (status) => {
    const result = parseSourceJob({ ...jobFixture, status });
    expect(result.status).toBe(status);
    expect(result.finished_at).toBeNull();
  });
  it.each([
    { ...jobFixture, payload: "private" }, { ...jobFixture, status: "all_sources_complete" },
    { ...jobFixture, attempt_count: -1 }, { ...jobFixture, attempt_count: 1.5 },
    { ...jobFixture, created_at: "2026-10-15T06:00:00" }, { ...jobFixture, finished_at: "unknown" },
    { ...jobFixture, created_at: "2026-02-30T06:00:00Z" }, { ...jobFixture, created_at: "2026-10-15T24:00:00Z" },
    { ...jobFixture, error_code: "<script>fixture</script>" }, { ...jobFixture, error_code: "token=isolated-fixture" },
    { ...jobFixture, result_ref: "https://user:isolated-fixture@example.test" },
  ])("rejects unsafe extra or malformed fields without exposing them", (value) => expect(() => parseSourceJob(value)).toThrow(/数据格式/));
  it("keeps bounded internal PG references and fixed error codes", () => {
    expect(parseSourceJob({ ...jobFixture, status: "partial", attempt_count: 1, error_code: "source_page_limit_reached", result_ref: `pg:source:${jobId}` }).result_ref).toBe(`pg:source:${jobId}`);
  });
  it("accepts live five-page request without adding tenant or URL", () => {
    expect(() => validateSourceSubmission({ sourceKind: "nvd_ollama", body: { ...body, stream_kind: "live" }, idempotencyKey: "isolated-round-1" })).not.toThrow();
  });
  it.each([0, 21, 1.5])("rejects max_pages %s", (max_pages) => expect(() => validateSourceSubmission({ sourceKind: "vllm_vendor", body: { ...body, stream_kind: "backfill", max_pages }, idempotencyKey: "isolated-round-1" })).toThrow(/校验/));
});
