import { ApiProblem } from "./client";
import { parseEvidenceResponse, type DataMode, type EvidenceResponse, type RevisionSummary } from "./knowledge-contracts";

export const documentKinds = ["advisory", "article", "paper", "repository_record", "standard", "policy"] as const;
export const sourceCategories = ["structured_vulnerability", "vendor_advisory", "security_community", "code_repository", "technical_blog", "academic_paper", "technical_standard", "policy_regulation"] as const;
export type DocumentKind = typeof documentKinds[number];
export type SourceCategory = typeof sourceCategories[number];
export type ContentCoverage = "full_text" | "abstract" | "feed_excerpt" | "metadata" | "unknown";
export interface DocumentSummary {
  document_id: string; source_id: string; revision_id: string; source_name: string; source_category: SourceCategory;
  document_kind: DocumentKind; title: string; canonical_uri: string | null; revision_number: number; is_current: boolean;
  source_published_at: string | null; source_modified_at: string | null; first_observed_at: string | null; ingested_at: string | null;
  parse_status: RevisionSummary["parse_status"]; content_coverage: ContentCoverage; published_at_raw: string | null;
  published_precision: "instant" | "calendar_date" | "unknown";
}
export interface DocumentListResponse { schema_version: 2; items: DocumentSummary[]; next_cursor: string | null; data_mode: DataMode; }
export interface DocumentDetailResponse {
  schema_version: 2; document: DocumentSummary; evidence: EvidenceResponse[]; evidence_total: number; next_evidence_offset: number | null;
  license_identifier: string | null; license_uri: string | null; source_notes: string[]; data_mode: DataMode;
}
export interface DocumentRevisionsResponse { schema_version: 2; items: DocumentSummary[]; next_offset: number | null; data_mode: DataMode; }

function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!isRecord(value)) return invalid();
  const fields = Object.keys(value);
  if (fields.length !== keys.length || !fields.every((key) => keys.includes(key))) return invalid();
  return value;
}
function text(value: unknown, maximum: number): string {
  if (typeof value !== "string" || !value.trim() || [...value].length > maximum) return invalid();
  return value;
}
function nullableText(value: unknown, maximum: number): string | null { return value === null ? null : text(value, maximum); }
function identifier(value: unknown): string {
  const id = text(value, 36);
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id) ? id : invalid();
}
function integer(value: unknown, minimum: number, maximum = Number.MAX_SAFE_INTEGER): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum ? value : invalid();
}
function enumeration<T extends string>(value: unknown, choices: readonly T[]): T {
  return choices.find((candidate) => candidate === value) ?? invalid();
}
function list<T>(value: unknown, parser: (item: unknown) => T, maximum: number): T[] {
  return Array.isArray(value) && value.length <= maximum ? value.map(parser) : invalid();
}
function nullableTimestamp(value: unknown): string | null {
  if (value === null) return null;
  const timestamp = text(value, 64);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp) || !Number.isFinite(Date.parse(timestamp))) return invalid();
  const year = Number(timestamp.slice(0, 4));
  const month = Number(timestamp.slice(5, 7));
  const day = Number(timestamp.slice(8, 10));
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate() || Number(timestamp.slice(11, 13)) > 23 || Number(timestamp.slice(14, 16)) > 59 || Number(timestamp.slice(17, 19)) > 59) return invalid();
  return timestamp;
}
function nullableHttpsUri(value: unknown): string | null {
  if (value === null) return null;
  const uri = text(value, 2083);
  try {
    const url = new URL(uri);
    const sensitiveKeys = ["token", "access_token", "key", "api_key", "api-key", "apikey", "secret", "password", "sig", "signature", "x-quaketoken", "x-api-key", "authorization", "cookie"];
    if (url.protocol !== "https:" || url.username || url.password || url.hash || [...url.searchParams.keys()].some((key) => sensitiveKeys.includes(key.toLowerCase()))) return invalid();
    return uri;
  } catch { return invalid(); }
}
function parseSummary(value: unknown): DocumentSummary {
  const fields = record(value, ["document_id", "source_id", "revision_id", "source_name", "source_category", "document_kind", "title", "canonical_uri", "revision_number", "is_current", "source_published_at", "source_modified_at", "first_observed_at", "ingested_at", "parse_status", "content_coverage", "published_at_raw", "published_precision"]);
  if (typeof fields.is_current !== "boolean") return invalid();
  const published = nullableTimestamp(fields.source_published_at);
  const precision = enumeration(fields.published_precision, ["instant", "calendar_date", "unknown"]);
  const publishedRaw = nullableText(fields.published_at_raw, 256);
  if (precision === "instant" && published === null) return invalid();
  if (precision === "calendar_date" && (published !== null || publishedRaw === null)) return invalid();
  return {
    document_id: identifier(fields.document_id), source_id: identifier(fields.source_id), revision_id: identifier(fields.revision_id),
    source_name: text(fields.source_name, 300), source_category: enumeration(fields.source_category, sourceCategories), document_kind: enumeration(fields.document_kind, documentKinds),
    title: text(fields.title, 500), canonical_uri: nullableHttpsUri(fields.canonical_uri), revision_number: integer(fields.revision_number, 1), is_current: fields.is_current,
    source_published_at: published, source_modified_at: nullableTimestamp(fields.source_modified_at), first_observed_at: nullableTimestamp(fields.first_observed_at), ingested_at: nullableTimestamp(fields.ingested_at),
    parse_status: enumeration(fields.parse_status, ["pending", "parsed", "partial", "failed", "legacy_unverified"]), content_coverage: enumeration(fields.content_coverage, ["full_text", "abstract", "feed_excerpt", "metadata", "unknown"]),
    published_at_raw: publishedRaw, published_precision: precision,
  };
}
function envelope(value: unknown, keys: readonly string[]): { fields: Record<string, unknown>; mode: DataMode } {
  const fields = record(value, keys);
  if (fields.schema_version !== 2) return invalid();
  return { fields, mode: enumeration(fields.data_mode, ["live", "fixture"]) };
}

/** 严格接受主控冻结的资料投影；字段缺失、未知枚举和不安全地址均保留为合同错误。 */
export function parseDocumentListResponse(value: unknown): DocumentListResponse {
  const { fields, mode } = envelope(value, ["schema_version", "items", "next_cursor", "data_mode"]);
  return { schema_version: 2, items: list(fields.items, parseSummary, 100), next_cursor: nullableText(fields.next_cursor, 2048), data_mode: mode };
}
export function parseDocumentDetailResponse(value: unknown): DocumentDetailResponse {
  const { fields, mode } = envelope(value, ["schema_version", "document", "evidence", "evidence_total", "next_evidence_offset", "license_identifier", "license_uri", "source_notes", "data_mode"]);
  const document = parseSummary(fields.document);
  const evidence = list(fields.evidence, parseEvidenceResponse, 100);
  const total = integer(fields.evidence_total, 0);
  if (total < evidence.length || evidence.some((span) => span.revision_id.toLowerCase() !== document.revision_id.toLowerCase() || span.data_mode !== mode)) return invalid();
  return { schema_version: 2, document, evidence, evidence_total: total, next_evidence_offset: fields.next_evidence_offset === null ? null : integer(fields.next_evidence_offset, 1, 2000), license_identifier: nullableText(fields.license_identifier, 256), license_uri: nullableHttpsUri(fields.license_uri), source_notes: list(fields.source_notes, (note) => text(note, 1000), 20), data_mode: mode };
}
export function parseDocumentRevisionsResponse(value: unknown): DocumentRevisionsResponse {
  const { fields, mode } = envelope(value, ["schema_version", "items", "next_offset", "data_mode"]);
  return { schema_version: 2, items: list(fields.items, parseSummary, 100), next_offset: fields.next_offset === null ? null : integer(fields.next_offset, 1, 100000), data_mode: mode };
}
