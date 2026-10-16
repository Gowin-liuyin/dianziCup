import { ApiProblem, fetchJson, getCsrfToken } from "../../api/client";
import { parseInvestigationOperations, parseInvestigationResponse, validateInvestigationId, validateInvestigationSubmission, type InvestigationOperationPage, type InvestigationResponse, type InvestigationSubmission } from "./investigation-contracts";

function jobPath(jobId: string): string { return `/api/v1/investigations/${validateInvestigationId(jobId)}`; }
function assertCurrent(signal: AbortSignal | undefined, isCurrent: () => boolean): void {
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
}
/** The browser supplies the same-origin Origin; CSRF and idempotency stay on the existing authenticated transport. */
export async function createInvestigation(submission: InvestigationSubmission, signal?: AbortSignal, isCurrent: () => boolean = () => true): Promise<InvestigationResponse> {
  validateInvestigationSubmission(submission);
  assertCurrent(signal, isCurrent);
  const token = await getCsrfToken(signal);
  assertCurrent(signal, isCurrent);
  return parseInvestigationResponse(await fetchJson("/api/v1/investigations", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token, "Idempotency-Key": submission.idempotencyKey }, body: JSON.stringify(submission.body) }, signal, [], 30_000, [202]));
}
export async function getInvestigation(jobId: string, signal?: AbortSignal): Promise<InvestigationResponse> {
  return parseInvestigationResponse(await fetchJson(jobPath(jobId), {}, signal, [], 10_000, [200]), jobId);
}
export async function getInvestigationOperations(jobId: string, cursor: string | null = null, signal?: AbortSignal): Promise<InvestigationOperationPage> {
  const path = jobPath(jobId), query = new URLSearchParams({ limit: "20" });
  if (cursor !== null) {
    if (!cursor || [...cursor].length > 200 || cursor.includes("\0")) throw new ApiProblem(422, "invalid_investigation", false);
    query.set("cursor", cursor);
  }
  return parseInvestigationOperations(await fetchJson(`${path}/tool-runs?${query}`, {}, signal, [], 10_000, [200]), cursor);
}
export async function cancelInvestigation(jobId: string, signal?: AbortSignal, isCurrent: () => boolean = () => true): Promise<InvestigationResponse> {
  const path = jobPath(jobId);
  assertCurrent(signal, isCurrent);
  const token = await getCsrfToken(signal);
  assertCurrent(signal, isCurrent);
  return parseInvestigationResponse(await fetchJson(`${path}/cancel`, { method: "POST", headers: { "X-CSRF-Token": token } }, signal, [], 10_000, [200]), jobId);
}
