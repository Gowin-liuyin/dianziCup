import { describe, expect, it } from "vitest";
import { investigationNeedsPolling, parseInvestigationOperations, parseInvestigationResponse, readInvestigationRoute, validateInvestigationSubmission } from "./investigation-contracts";
import { fixtureEventId, fixtureJob, fixtureJobId, fixtureOperation, fixtureOtherJobId, fixtureSubmission } from "./investigation.fixture";

describe("R17 investigation wire boundary · explicit isolated fixtures", () => {
  it("preserves partial, not_configured, unknown cost and complete service elapsed time", () => {
    const result = parseInvestigationResponse(fixtureJob("partial"), fixtureJobId);
    expect(result.elapsed_milliseconds).toBe(12345.678);
    expect(result.result?.receipts[0]?.status).toBe("not_configured");
    expect(parseInvestigationOperations({ items: [fixtureOperation()], next_cursor: null }).items[0]?.cost_status).toBe("unknown");
  });
  it.each(["queued", "running", "retry_wait"] as const)("polls %s until a server stop", (status) => expect(investigationNeedsPolling(fixtureJob(status))).toBe(true));
  it.each(["waiting_approval", "succeeded", "partial", "failed", "cancelled", "blocked"] as const)("does not poll %s", (status) => expect(investigationNeedsPolling(fixtureJob(status))).toBe(false));
  it("stops on stale result even when a job record still says running", () => {
    const job = fixtureJob("partial");
    if (job.result === null) throw new Error("fixture result missing");
    expect(investigationNeedsPolling({ ...job, status: "running", result: { ...job.result, status: "stale" } })).toBe(false);
  });
  it.each([
    { ...fixtureJob(), job_id: fixtureOtherJobId }, { ...fixtureJob(), status: "looks_successful" },
    { ...fixtureJob(), tenant_id: "untrusted" }, { ...fixtureJob(), elapsed_milliseconds: -1 },
    { ...fixtureJob(), created_at: "2026-02-30T10:00:00Z" },
  ])("rejects wrong identity, authority, unknown state and invalid timings", (value) => expect(() => parseInvestigationResponse(value, fixtureJobId)).toThrow());
  it("rejects fabricated claim supports, duplicate citations and another result identity", () => {
    const job = fixtureJob("succeeded"), result = job.result;
    if (result?.answer === null || result?.answer === undefined) throw new Error("fixture answer missing");
    const answer = result.answer;
    expect(() => parseInvestigationResponse({ ...job, result: { ...result, job_id: fixtureOtherJobId } })).toThrow();
    expect(() => parseInvestigationResponse({ ...job, result: { ...result, answer: { ...answer, claims: [{ text: "unverified", kind: "source_fact", support_ids: [fixtureOtherJobId] }] } } })).toThrow();
    expect(() => parseInvestigationResponse({ ...job, result: { ...result, answer: { ...answer, citations: [...answer.citations, ...answer.citations] } } })).toThrow();
  });
  it("rejects repeated, unordered or self-replaying operation pages", () => {
    for (const value of [{ items: [fixtureOperation(), fixtureOperation()], next_cursor: null }, { items: [fixtureOperation("002"), fixtureOperation("001")], next_cursor: null }, { items: [fixtureOperation()], next_cursor: "002" }]) expect(() => parseInvestigationOperations(value)).toThrow();
    expect(() => parseInvestigationOperations({ items: [fixtureOperation()], next_cursor: "001" }, "001")).toThrow();
  });
  it("accepts exact bounded input but rejects actor, budget, unpaired assets, duplicate or mismatched refs", () => {
    const submission = fixtureSubmission();
    expect(() => validateInvestigationSubmission(submission)).not.toThrow();
    for (const body of [{ ...submission.body, actor: "admin" }, { ...submission.body, budget: 1 }, { ...submission.body, asset_id: fixtureEventId }, { ...submission.body, question: " " }, { ...submission.body, question: "a".repeat(4097) }, { ...submission.body, evidence_refs: [{ event_id: fixtureOtherJobId, evidence_id: fixtureEventId, revision_id: fixtureJobId }] }, { ...submission.body, evidence_refs: Array.from({ length: 2 }, () => ({ event_id: fixtureEventId, evidence_id: fixtureJobId, revision_id: fixtureOtherJobId })) }]) expect(() => validateInvestigationSubmission({ ...submission, body })).toThrow();
    expect(() => validateInvestigationSubmission({ ...submission, idempotencyKey: "bad key" })).toThrow();
  });
  it("keeps only UUID deep links and no question body", () => {
    expect(readInvestigationRoute(`#investigations/${fixtureJobId}`)).toEqual({ jobId: fixtureJobId });
    expect(readInvestigationRoute(`#investigations/${fixtureJobId}?question=secret`)).toBeNull();
    expect(readInvestigationRoute("#investigations/../../private")).toBeNull();
  });
});
