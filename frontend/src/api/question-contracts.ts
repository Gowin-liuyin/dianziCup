import { ApiProblem } from "./client";
import type { Citation, DataMode, Freshness } from "./knowledge-contracts";

export type AnswerClaimKind = "source_fact" | "rule_result" | "project_suggestion";
export interface AnswerClaim { text: string; kind: AnswerClaimKind; support_ids: string[]; }
export interface QuestionAnswer {
  kind: "completed"; answer_id: string; answer_text: string; claims: AnswerClaim[]; citations: Citation[];
  limitations: string[]; freshness: Freshness; data_mode: DataMode; started_at: string; completed_at: string; latency_milliseconds: number;
}
export interface QuestionSubmission { body: { question: string; mode: "library"; event_ids: [string] }; idempotencyKey: string; }
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function record(value: unknown, keys: string[]): Record<string, unknown> {
  if (!isRecord(value)) return invalid();
  const fields = Object.keys(value);
  if (fields.length !== keys.length || !fields.every((key) => keys.includes(key))) return invalid();
  return value;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.includes("\0") || /[\uD800-\uDFFF]/u.test(value)) return invalid();
  return value;
}
function identifier(value: unknown): string {
  if (typeof value !== "string" || !uuidPattern.test(value)) return invalid();
  return value.toLowerCase();
}
function list<T>(value: unknown, parse: (item: unknown) => T): T[] {
  if (!Array.isArray(value) || value.length > 100) return invalid();
  return value.map(parse);
}
function choice<T extends string>(value: unknown, choices: readonly T[]): T {
  const result = choices.find((item) => item === value);
  return result === undefined ? invalid() : result;
}
function timestamp(value: unknown): string {
  const date = text(value);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(date) || !Number.isFinite(Date.parse(date))) return invalid();
  const year = Number(date.slice(0, 4));
  const month = Number(date.slice(5, 7));
  const day = Number(date.slice(8, 10));
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate() || Number(date.slice(11, 13)) > 23 || Number(date.slice(14, 16)) > 59 || Number(date.slice(17, 19)) > 59) return invalid();
  return date;
}
function parseCitation(value: unknown): Citation {
  const fields = record(value, ["evidence_id", "revision_id", "quote", "locator", "source_uri"]);
  const sourceUri = text(fields.source_uri);
  try {
    const url = new URL(sourceUri);
    if ((url.protocol !== "https:" && url.protocol !== "http:") || url.username || url.password || /[\s\\]/u.test(sourceUri)) return invalid();
  } catch { return invalid(); }
  return { evidence_id: identifier(fields.evidence_id), revision_id: identifier(fields.revision_id), quote: text(fields.quote), locator: text(fields.locator), source_uri: sourceUri };
}
function parseClaim(value: unknown): AnswerClaim {
  const fields = record(value, ["text", "kind", "support_ids"]);
  const kind = choice(fields.kind, ["source_fact", "rule_result", "project_suggestion"] as const);
  const supportIds = list(fields.support_ids, identifier);
  if (kind !== "project_suggestion" && supportIds.length === 0) return invalid();
  return { text: text(fields.text), kind, support_ids: supportIds };
}

/** 拒绝额外字段、伪造支持、重复引用和不完整回答；不将wire数据强转为可信事实。 */
export function parseQuestionAnswer(value: unknown): QuestionAnswer {
  const fields = record(value, ["kind", "answer_id", "answer_text", "claims", "citations", "limitations", "freshness", "data_mode", "started_at", "completed_at", "latency_milliseconds"]);
  if (fields.kind !== "completed") return invalid();
  const claims = list(fields.claims, parseClaim);
  const citations = list(fields.citations, parseCitation);
  const citationIds = new Set(citations.map((citation) => citation.evidence_id));
  if (citationIds.size !== citations.length || claims.some((claim) => claim.support_ids.some((id) => !citationIds.has(id)))) return invalid();
  const startedAt = timestamp(fields.started_at);
  const completedAt = timestamp(fields.completed_at);
  if (Date.parse(completedAt) < Date.parse(startedAt) || typeof fields.latency_milliseconds !== "number" || !Number.isSafeInteger(fields.latency_milliseconds) || fields.latency_milliseconds < 0) return invalid();
  return { kind: "completed", answer_id: identifier(fields.answer_id), answer_text: text(fields.answer_text), claims, citations, limitations: list(fields.limitations, text), freshness: choice(fields.freshness, ["current", "stale", "unknown"] as const), data_mode: choice(fields.data_mode, ["live", "fixture"] as const), started_at: startedAt, completed_at: completedAt, latency_milliseconds: fields.latency_milliseconds };
}

export function validateQuestionId(value: string): string {
  if (!uuidPattern.test(value)) throw new ApiProblem(422, "validation_error", false);
  return value.toLowerCase();
}

/** R05范围只接library单事件，不默默提交未接通的会话、资产或时间选项。 */
export function validateQuestionSubmission(value: QuestionSubmission): void {
  const body = value.body;
  if (Object.keys(body).length !== 3 || !Object.keys(body).every((key) => ["question", "mode", "event_ids"].includes(key)) || body.mode !== "library" || !Array.isArray(body.event_ids) || body.event_ids.length !== 1) throw new ApiProblem(422, "validation_error", false);
  validateQuestionId(body.event_ids[0]);
  if (typeof body.question !== "string" || !body.question.trim() || [...body.question].length > 4096 || body.question.includes("\0") || /[\uD800-\uDFFF]/u.test(body.question) || !/^[\x21-\x7e]{1,200}$/.test(value.idempotencyKey)) throw new ApiProblem(422, "validation_error", false);
}

/** 仅解析标识深链接，不在URL或浏览器存储保留问题与回答正文。 */
export function readQuestionRoute(hash: string): { eventId: string } | null {
  const uuid = "([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})";
  const match = new RegExp(`^#questions/${uuid}$`, "i").exec(hash);
  return match?.[1] === undefined ? null : { eventId: match[1].toLowerCase() };
}
