import { ApiProblem } from "./client";

export type SourceKind = "nvd_ollama" | "vllm_vendor";
export type SourceJobStatus = "queued" | "running" | "retry_wait" | "succeeded" | "partial" | "failed" | "blocked" | "cancelled" | "waiting_approval";
export interface SourceCollectionRequest { window_end: string; stream_kind: "live" | "backfill"; max_pages: number; }
export interface SourceSubmission { sourceKind: SourceKind; body: SourceCollectionRequest; idempotencyKey: string; }
export interface SourceJob { job_id: string; status: SourceJobStatus; attempt_count: number; error_code: string | null; result_ref: string | null; created_at: string; finished_at: string | null; }

const jobStatuses: readonly SourceJobStatus[] = ["queued", "running", "retry_wait", "succeeded", "partial", "failed", "blocked", "cancelled", "waiting_approval"];
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function invalidResponse(): never { throw new ApiProblem(502, "invalid_response", true); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function timestamp(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) return false;
  const year = Number(value.slice(0, 4));
  const month = Number(value.slice(5, 7));
  const day = Number(value.slice(8, 10));
  return year > 0 && month >= 1 && month <= 12 && day >= 1 && day <= new Date(Date.UTC(year, month, 0)).getUTCDate() && Number(value.slice(11, 13)) < 24 && Number(value.slice(14, 16)) < 60 && Number(value.slice(17, 19)) < 60;
}

export function validateJobId(value: string): string {
  if (!uuidPattern.test(value)) throw new ApiProblem(422, "validation_error", false);
  return value.toLowerCase();
}

/** 写入固定字段并限制来源、窗口和页数；验证失败不会触发CSRF或网络请求。 */
export function validateSourceSubmission(value: SourceSubmission): void {
  if (value.sourceKind !== "nvd_ollama" && value.sourceKind !== "vllm_vendor") throw new ApiProblem(422, "validation_error", false);
  const body = value.body;
  if (Object.keys(body).length !== 3 || !Object.keys(body).every((key) => ["window_end", "stream_kind", "max_pages"].includes(key))) throw new ApiProblem(422, "validation_error", false);
  if (!timestamp(body.window_end) || body.window_end.length > 64 || Date.parse(body.window_end) > Date.now()) throw new ApiProblem(422, "validation_error", false);
  if ((body.stream_kind !== "live" && body.stream_kind !== "backfill") || !Number.isInteger(body.max_pages) || body.max_pages < 1 || body.max_pages > 20) throw new ApiProblem(422, "validation_error", false);
  if (!/^[\x21-\x7e]{1,200}$/.test(value.idempotencyKey)) throw new ApiProblem(422, "validation_error", false);
}

/** 只接收PG公开投影与SQL中的九种状态，错误文字和外部地址不进入任务视图。 */
export function parseSourceJob(value: unknown): SourceJob {
  if (!isRecord(value)) return invalidResponse();
  const keys = ["job_id", "status", "attempt_count", "error_code", "result_ref", "created_at", "finished_at"];
  if (Object.keys(value).length !== keys.length || !Object.keys(value).every((key) => keys.includes(key))) return invalidResponse();
  const status = jobStatuses.find((candidate) => candidate === value.status);
  if (typeof value.job_id !== "string" || !uuidPattern.test(value.job_id) || status === undefined) return invalidResponse();
  if (typeof value.attempt_count !== "number" || !Number.isSafeInteger(value.attempt_count) || value.attempt_count < 0) return invalidResponse();
  if (value.error_code !== null && (typeof value.error_code !== "string" || !/^[a-z][a-z0-9_]{0,99}$/.test(value.error_code))) return invalidResponse();
  if (value.result_ref !== null && (typeof value.result_ref !== "string" || !/^pg:[a-z][a-z0-9_]{0,49}:[a-zA-Z0-9_-]{1,200}$/.test(value.result_ref))) return invalidResponse();
  if (!timestamp(value.created_at) || !(value.finished_at === null || timestamp(value.finished_at))) return invalidResponse();
  return { job_id: value.job_id.toLowerCase(), status, attempt_count: value.attempt_count, error_code: value.error_code, result_ref: value.result_ref, created_at: value.created_at, finished_at: value.finished_at };
}
