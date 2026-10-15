import { ApiProblem, fetchJson, getCsrfToken } from "./client";
import { parseSourceJob, validateJobId, validateSourceSubmission, type SourceJob, type SourceSubmission } from "./source-contracts";

/** CSRF读取后再次检查会话与取消状态，避免旧会话的迟到令牌触发写请求。 */
export async function collectSourcePage(submission: SourceSubmission, isCurrent: () => boolean, signal?: AbortSignal): Promise<SourceJob> {
  validateSourceSubmission(submission);
  const path = `/v1/sources/${submission.sourceKind}/collect`;
  const body = JSON.stringify(submission.body);
  const idempotencyKey = submission.idempotencyKey;
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const token = await getCsrfToken(signal);
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const value = await fetchJson(path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token, "Idempotency-Key": idempotencyKey }, body }, signal);
  return parseSourceJob(value);
}

export async function getSourceJob(jobId: string, signal?: AbortSignal): Promise<SourceJob> {
  const id = validateJobId(jobId);
  const value = parseSourceJob(await fetchJson(`/v1/jobs/${id}`, {}, signal));
  if (value.job_id !== id) throw new ApiProblem(502, "invalid_response", true);
  return value;
}
