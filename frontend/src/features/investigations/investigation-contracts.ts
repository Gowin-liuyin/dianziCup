import { ApiProblem } from "../../api/client";
import type { AnswerClaim } from "../../api/question-contracts";
import { isAssetIdentifier } from "../assets/asset-contracts";

export type InvestigationStrategy = "B2" | "B2b" | "B3";
export interface InvestigationRequest {
  question: string; event_id: string; evidence_refs: EvidenceReference[]; strategy: InvestigationStrategy;
  asset_id: string | null; asset_snapshot_id: string | null; version_comparison: null;
}
export interface EvidenceReference { event_id: string; evidence_id: string; revision_id: string; }
export interface InvestigationSubmission { body: InvestigationRequest; idempotencyKey: string; }
export type InvestigationJobStatus = "queued" | "running" | "retry_wait" | "waiting_approval" | "succeeded" | "partial" | "failed" | "cancelled" | "blocked";
type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export interface RoleReceipt {
  role: "orchestrator" | "collector" | "triage" | "enricher" | "graph_writer" | "assessor" | "qa" | "critic" | "reporter";
  status: "succeeded" | "partial" | "failed" | "not_configured" | "skipped";
  reason_code: string; evidence_ids: string[]; operation_keys: string[]; output: { [key: string]: JsonValue };
}
export interface InvestigationResult {
  job_id: string; status: "running" | "waiting_approval" | "succeeded" | "partial" | "failed" | "stale";
  stop_reason: string; graph_version: "r14-langgraph-1"; input_sha256: string; data_mode: "fixture" | "live";
  receipts: RoleReceipt[]; answer: { claims: AnswerClaim[]; citations: { evidence_id: string; quote: string }[] } | null;
  evidence_ids: string[]; missing_requirements: string[];
}
export interface InvestigationResponse {
  job_id: string; status: InvestigationJobStatus; created_at: string; updated_at: string;
  started_at: string | null; finished_at: string | null; error_code: string | null; result_ref: string | null;
  elapsed_milliseconds: number; result: InvestigationResult | null;
}
export interface InvestigationOperation {
  operation_key: string; kind: "tool" | "model" | "node"; role: string;
  status: "reserved" | "succeeded" | "failed" | "partial"; request_sha256: string;
  tool_name: string | null; model_version: string | null; prompt_version: string | null; policy_version: string;
  cost_status: "unknown"; input_bytes: number; output_bytes: number; model_calls: number; tool_calls: number;
  created_at: string; completed_at: string | null;
}
export interface InvestigationOperationPage { items: InvestigationOperation[]; next_cursor: string | null; }

function invalid(): never { throw new ApiProblem(502, "invalid_response", false); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function record(value: unknown, keys?: readonly string[]): Record<string, unknown> {
  if (!isRecord(value)) return invalid();
  if (keys !== undefined && (Object.keys(value).length !== keys.length || !Object.keys(value).every((key) => keys.includes(key)))) return invalid();
  return value;
}
function text(value: unknown, maximum = 65536): string {
  if (typeof value !== "string" || value.includes("\0") || /[\uD800-\uDFFF]/u.test(value) || [...value].length > maximum) return invalid();
  return value;
}
function nonempty(value: unknown, maximum = 65536): string { const result = text(value, maximum); return result.trim() ? result : invalid(); }
function answerText(value: unknown): string { const result = nonempty(value, 2048); return /[\r\n\v\f\x85\u2028\u2029]/u.test(result) ? invalid() : result; }
function nullableText(value: unknown): string | null { return value === null ? null : text(value); }
function identifier(value: unknown): string { return typeof value === "string" && isAssetIdentifier(value) ? value.toLowerCase() : invalid(); }
function choice<T extends string>(value: unknown, choices: readonly T[]): T {
  const result = choices.find((candidate) => candidate === value); return result === undefined ? invalid() : result;
}
function list<T>(value: unknown, parse: (item: unknown) => T, maximum: number): T[] {
  return Array.isArray(value) && value.length <= maximum ? value.map((item) => parse(item)) : invalid();
}
function nonnegative(value: unknown, integer = false): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || (integer && !Number.isSafeInteger(value))) return invalid();
  return value;
}
function timestamp(value: unknown): string {
  const result = nonempty(value, 40);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(result) || !Number.isFinite(Date.parse(result))) return invalid();
  const year = Number(result.slice(0, 4)), month = Number(result.slice(5, 7)), day = Number(result.slice(8, 10));
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate() || Number(result.slice(11, 13)) > 23 || Number(result.slice(14, 16)) > 59 || Number(result.slice(17, 19)) > 59) return invalid();
  return result;
}
function nullableTimestamp(value: unknown): string | null { return value === null ? null : timestamp(value); }
function digest(value: unknown): string { const result = text(value, 64); return /^[a-f0-9]{64}$/.test(result) ? result : invalid(); }
function jsonValue(value: unknown, depth = 0): JsonValue {
  if (depth > 12) return invalid();
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : invalid();
  if (typeof value === "string") return text(value);
  if (Array.isArray(value)) return list(value, (item) => jsonValue(item, depth + 1), 1000);
  const fields = record(value), output: { [key: string]: JsonValue } = {};
  if (Object.keys(fields).length > 1000) return invalid();
  for (const [key, item] of Object.entries(fields)) {
    if (["__proto__", "constructor", "prototype"].includes(key)) return invalid();
    output[text(key, 200)] = jsonValue(item, depth + 1);
  }
  return output;
}
function parseReceipt(value: unknown): RoleReceipt {
  const fields = record(value, ["role", "status", "reason_code", "evidence_ids", "operation_keys", "output"]);
  const reason = nonempty(fields.reason_code, 100);
  if (!/^[a-z][a-z0-9_]{0,99}$/.test(reason)) return invalid();
  const output = jsonValue(record(fields.output));
  if (output === null || typeof output !== "object" || Array.isArray(output)) return invalid();
  return { role: choice(fields.role, ["orchestrator", "collector", "triage", "enricher", "graph_writer", "assessor", "qa", "critic", "reporter"]), status: choice(fields.status, ["succeeded", "partial", "failed", "not_configured", "skipped"]), reason_code: reason, evidence_ids: list(fields.evidence_ids, identifier, 8), operation_keys: list(fields.operation_keys, nonempty, 12), output };
}
function parseAnswer(value: unknown): NonNullable<InvestigationResult["answer"]> {
  const fields = record(value, ["claims", "citations"]);
  const citations = list(fields.citations, (item) => {
    const citation = record(item, ["evidence_id", "quote"]);
    return { evidence_id: identifier(citation.evidence_id), quote: answerText(citation.quote) };
  }, 20);
  const evidenceIds = new Set(citations.map((citation) => citation.evidence_id));
  if (evidenceIds.size !== citations.length) return invalid();
  const claims = list(fields.claims, (item): AnswerClaim => {
    const claim = record(item, ["text", "kind", "support_ids"]);
    const kind = choice(claim.kind, ["source_fact", "rule_result", "project_suggestion"]);
    const supportIds = list(claim.support_ids, identifier, 20);
    if (new Set(supportIds).size !== supportIds.length || supportIds.some((id) => !evidenceIds.has(id)) || (kind !== "project_suggestion" && supportIds.length === 0)) return invalid();
    return { text: answerText(claim.text), kind, support_ids: supportIds };
  }, 20);
  if (claims.length === 0) return invalid();
  return { claims, citations };
}
function parseResult(value: unknown, expectedJobId: string): InvestigationResult {
  const fields = record(value, ["job_id", "status", "stop_reason", "graph_version", "input_sha256", "data_mode", "receipts", "answer", "evidence_ids", "missing_requirements"]);
  const jobId = identifier(fields.job_id);
  if (jobId !== expectedJobId || fields.graph_version !== "r14-langgraph-1") return invalid();
  return { job_id: jobId, status: choice(fields.status, ["running", "waiting_approval", "succeeded", "partial", "failed", "stale"]), stop_reason: text(fields.stop_reason), graph_version: fields.graph_version, input_sha256: digest(fields.input_sha256), data_mode: choice(fields.data_mode, ["fixture", "live"]), receipts: list(fields.receipts, parseReceipt, 9), answer: fields.answer === null ? null : parseAnswer(fields.answer), evidence_ids: list(fields.evidence_ids, identifier, 8), missing_requirements: list(fields.missing_requirements, nonempty, 20) };
}

/** Exact wire DTOs are checked before they become visible; unknown data never becomes an empty success. */
export function parseInvestigationResponse(value: unknown, expectedJobId?: string): InvestigationResponse {
  const fields = record(value, ["job_id", "status", "created_at", "updated_at", "started_at", "finished_at", "error_code", "result_ref", "elapsed_milliseconds", "result"]);
  const jobId = identifier(fields.job_id);
  if (expectedJobId !== undefined && jobId !== expectedJobId.toLowerCase()) return invalid();
  const createdAt = timestamp(fields.created_at), updatedAt = timestamp(fields.updated_at), startedAt = nullableTimestamp(fields.started_at), finishedAt = nullableTimestamp(fields.finished_at);
  if (Date.parse(updatedAt) < Date.parse(createdAt) || (startedAt !== null && Date.parse(startedAt) < Date.parse(createdAt)) || (finishedAt !== null && Date.parse(finishedAt) < Date.parse(startedAt ?? createdAt))) return invalid();
  return { job_id: jobId, status: choice(fields.status, ["queued", "running", "retry_wait", "waiting_approval", "succeeded", "partial", "failed", "cancelled", "blocked"]), created_at: createdAt, updated_at: updatedAt, started_at: startedAt, finished_at: finishedAt, error_code: nullableText(fields.error_code), result_ref: nullableText(fields.result_ref), elapsed_milliseconds: nonnegative(fields.elapsed_milliseconds), result: fields.result === null ? null : parseResult(fields.result, jobId) };
}
export function parseInvestigationOperations(value: unknown, cursor: string | null = null, limit = 20): InvestigationOperationPage {
  const fields = record(value, ["items", "next_cursor"]);
  const items = list(fields.items, (item): InvestigationOperation => {
    const operation = record(item, ["operation_key", "kind", "role", "status", "request_sha256", "tool_name", "model_version", "prompt_version", "policy_version", "cost_status", "input_bytes", "output_bytes", "model_calls", "tool_calls", "created_at", "completed_at"]);
    const createdAt = timestamp(operation.created_at), completedAt = nullableTimestamp(operation.completed_at);
    if (completedAt !== null && Date.parse(completedAt) < Date.parse(createdAt)) return invalid();
    return { operation_key: nonempty(operation.operation_key, 200), kind: choice(operation.kind, ["tool", "model", "node"]), role: nonempty(operation.role, 100), status: choice(operation.status, ["reserved", "succeeded", "failed", "partial"]), request_sha256: digest(operation.request_sha256), tool_name: nullableText(operation.tool_name), model_version: nullableText(operation.model_version), prompt_version: nullableText(operation.prompt_version), policy_version: text(operation.policy_version), cost_status: choice(operation.cost_status, ["unknown"]), input_bytes: nonnegative(operation.input_bytes, true), output_bytes: nonnegative(operation.output_bytes, true), model_calls: nonnegative(operation.model_calls, true), tool_calls: nonnegative(operation.tool_calls, true), created_at: createdAt, completed_at: completedAt };
  }, limit);
  const nextCursor = fields.next_cursor === null ? null : nonempty(fields.next_cursor, 200);
  if (new Set(items.map((item) => item.operation_key)).size !== items.length || items.some((item, index) => (cursor !== null && item.operation_key <= cursor) || (index > 0 && item.operation_key <= (items[index - 1]?.operation_key ?? ""))) || (nextCursor !== null && (nextCursor === cursor || nextCursor !== items.at(-1)?.operation_key))) return invalid();
  return { items, next_cursor: nextCursor };
}

export function validateInvestigationId(value: string): string {
  if (!isAssetIdentifier(value)) throw new ApiProblem(422, "invalid_investigation", false);
  return value.toLowerCase();
}
/** Authority and budget are absent from the request; asset and immutable snapshot identifiers stay paired. */
export function validateInvestigationSubmission(submission: InvestigationSubmission): void {
  try {
    const body = record(submission.body, ["question", "event_id", "evidence_refs", "strategy", "asset_id", "asset_snapshot_id", "version_comparison"]);
    nonempty(body.question, 4096); identifier(body.event_id); choice(body.strategy, ["B2", "B2b", "B3"]);
    if (body.version_comparison !== null || (body.asset_id === null) !== (body.asset_snapshot_id === null)) return invalid();
    if (body.asset_id !== null) { identifier(body.asset_id); identifier(body.asset_snapshot_id); }
    const references = list(body.evidence_refs, (item) => {
      const reference = record(item, ["event_id", "evidence_id", "revision_id"]);
      const eventId = identifier(reference.event_id);
      if (eventId !== identifier(body.event_id)) return invalid();
      return { event_id: eventId, evidence_id: identifier(reference.evidence_id), revision_id: identifier(reference.revision_id) };
    }, 8);
    if (new Set(references.map((reference) => reference.evidence_id)).size !== references.length || !/^[A-Za-z0-9._:-]{1,200}$/.test(submission.idempotencyKey)) return invalid();
    if (new TextEncoder().encode(JSON.stringify(submission.body)).length > 65536) return invalid();
  } catch { throw new ApiProblem(422, "invalid_investigation", false); }
}
export function investigationNeedsPolling(job: InvestigationResponse): boolean {
  return ["queued", "running", "retry_wait"].includes(job.status) && (job.result === null || job.result.status === "running");
}

/** A route contains only a public opaque job identifier, never a question or evidence body. */
export function readInvestigationRoute(hash: string): { jobId: string } | null {
  const match = /^#investigations\/([0-9a-f-]{36})$/i.exec(hash);
  return match?.[1] !== undefined && isAssetIdentifier(match[1]) ? { jobId: match[1].toLowerCase() } : null;
}
