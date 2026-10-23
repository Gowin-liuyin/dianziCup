import { ApiProblem } from "./client";

export type DataMode = "live" | "fixture";
export type Freshness = "current" | "stale" | "unknown";
export type DimensionName = "cvss" | "epss" | "kev" | "cwe" | "atlas" | "versions" | "literature" | "poc" | "exposure";
export type DimensionStatus = "available" | "not_found" | "not_applicable" | "conflict" | "blocked" | "failed" | "pending";
export type ClaimOrigin = "source_explicit" | "structured_source" | "rule_derived" | "model_hypothesis" | "human_confirmed";
export type ClaimStatus = "supported" | "disputed" | "unverified" | "superseded" | "withdrawn";

export interface Citation {
  evidence_id: string; revision_id: string; quote: string; locator: string; source_uri: string;
}
export interface Enrichment {
  dimension: DimensionName; status: DimensionStatus; claim_ids: string[]; citations: Citation[]; freshness: Freshness;
  observed_at: string | null; source_version: string | null; error_code: string | null;
}
export interface EventSummary {
  event_id: string; event_type: string; title: string; external_ids: string[]; primary_product_ids: string[];
  first_seen_at: string; status: string; source_count: number; latest_revision_id: string | null; freshness: Freshness;
}
export interface EventListResponse {
  schema_version: 2; items: EventSummary[]; next_cursor: string | null; data_mode: DataMode;
}
export interface RevisionSummary {
  revision_id: string; document_id: string; revision_number: number; source_id: string;
  source_published_at: string | null; source_modified_at: string | null; first_observed_at: string | null; ingested_at: string | null;
  parse_status: "pending" | "parsed" | "partial" | "failed" | "legacy_unverified";
  document_kind: "advisory" | "article" | "paper" | "repository_record" | "standard" | "policy"; canonical_uri: string | null;
}
export interface ClaimSummary {
  claim_id: string; predicate: string; display_value: string; origin: ClaimOrigin; status: ClaimStatus;
  source_revision_id: string | null; evidence_ids: string[];
}
export interface EventDetailResponse {
  schema_version: 2; event: EventSummary; dimensions: Enrichment[]; revisions: RevisionSummary[]; claims: ClaimSummary[]; business_version: number; data_mode: DataMode;
}
export interface EvidenceResponse {
  schema_version: 2; span_id: string; revision_id: string; block_id: string | null; start_offset: number; end_offset: number;
  quote_text: string; quote_sha256: string; locator_kind: "text" | "pdf_page" | "json_pointer" | "legacy_unverified";
  page_number: number | null; json_pointer: string | null; verified_at: string | null; source_uri: string | null;
  source_published_at: string | null; source_modified_at: string | null; first_observed_at: string | null; ingested_at: string | null; data_mode: DataMode;
}

const freshnessValues: readonly Freshness[] = ["current", "stale", "unknown"];
const dataModes: readonly DataMode[] = ["live", "fixture"];
const dimensionNames: readonly DimensionName[] = ["cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"];
const dimensionStatuses: readonly DimensionStatus[] = ["available", "not_found", "not_applicable", "conflict", "blocked", "failed", "pending"];
const claimOrigins: readonly ClaimOrigin[] = ["source_explicit", "structured_source", "rule_derived", "model_hypothesis", "human_confirmed"];
const claimStatuses: readonly ClaimStatus[] = ["supported", "disputed", "unverified", "superseded", "withdrawn"];

function invalidContract(): never { throw new ApiProblem(502, "invalid_response", true); }

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function record(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (!isObject(value)) return invalidContract();
  const fields = Object.keys(value);
  if (fields.length !== keys.length || !fields.every((field) => keys.includes(field))) return invalidContract();
  return value;
}

function text(value: unknown, maximum = Number.POSITIVE_INFINITY): string {
  if (typeof value !== "string" || !value.trim() || [...value].length > maximum) return invalidContract();
  return value;
}

function stringValue(value: unknown, maximum = Number.POSITIVE_INFINITY): string {
  if (typeof value !== "string" || [...value].length > maximum) return invalidContract();
  return value;
}
function nullableText(value: unknown, maximum = Number.POSITIVE_INFINITY): string | null { return value === null ? null : stringValue(value, maximum); }
function identifier(value: unknown): string {
  const id = text(value);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return invalidContract();
  return id;
}
function nullableIdentifier(value: unknown): string | null { return value === null ? null : identifier(value); }
function integer(value: unknown, minimum: number): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum) return invalidContract();
  return value;
}
function timestamp(value: unknown): string {
  const date = text(value);
  if (!/(Z|[+-]\d{2}:\d{2})$/.test(date) || !Number.isFinite(Date.parse(date))) return invalidContract();
  return date;
}
function nullableTimestamp(value: unknown): string | null { return value === null ? null : timestamp(value); }
function httpUri(value: unknown): string {
  const uri = text(value);
  try {
    const url = new URL(uri);
    if ((url.protocol !== "http:" && url.protocol !== "https:") || url.username || url.password) return invalidContract();
    return uri;
  } catch { return invalidContract(); }
}
function nullableHttpUri(value: unknown): string | null { return value === null ? null : httpUri(value); }
function enumeration<T extends string>(value: unknown, choices: readonly T[]): T {
  const choice = choices.find((candidate) => candidate === value);
  return choice === undefined ? invalidContract() : choice;
}
function list<T>(value: unknown, parser: (item: unknown) => T, maximum = Number.POSITIVE_INFINITY): T[] {
  if (!Array.isArray(value) || value.length > maximum) return invalidContract();
  return value.map((item) => parser(item));
}
function schemaVersion(value: unknown): 2 { return value === 2 ? 2 : invalidContract(); }

function parseEventSummary(value: unknown): EventSummary {
  const fields = record(value, ["event_id", "event_type", "title", "external_ids", "primary_product_ids", "first_seen_at", "status", "source_count", "latest_revision_id", "freshness"]);
  return { event_id: identifier(fields.event_id), event_type: text(fields.event_type, 100), title: text(fields.title, 500), external_ids: list(fields.external_ids, stringValue, 100), primary_product_ids: list(fields.primary_product_ids, identifier, 100), first_seen_at: timestamp(fields.first_seen_at), status: text(fields.status, 100), source_count: integer(fields.source_count, 0), latest_revision_id: nullableIdentifier(fields.latest_revision_id), freshness: enumeration(fields.freshness, freshnessValues) };
}

function parseCitation(value: unknown): Citation {
  const fields = record(value, ["evidence_id", "revision_id", "quote", "locator", "source_uri"]);
  return { evidence_id: identifier(fields.evidence_id), revision_id: identifier(fields.revision_id), quote: text(fields.quote), locator: text(fields.locator), source_uri: httpUri(fields.source_uri) };
}

function parseEnrichment(value: unknown): Enrichment {
  const fields = record(value, ["dimension", "status", "claim_ids", "citations", "freshness", "observed_at", "source_version", "error_code"]);
  const status = enumeration(fields.status, dimensionStatuses);
  const citations = list(fields.citations, parseCitation, 100);
  if (status === "available" && citations.length === 0) return invalidContract();
  return { dimension: enumeration(fields.dimension, dimensionNames), status, claim_ids: list(fields.claim_ids, identifier, 100), citations, freshness: enumeration(fields.freshness, freshnessValues), observed_at: nullableTimestamp(fields.observed_at), source_version: nullableText(fields.source_version), error_code: nullableText(fields.error_code) };
}

function parseRevision(value: unknown): RevisionSummary {
  const fields = record(value, ["revision_id", "document_id", "revision_number", "source_id", "source_published_at", "source_modified_at", "first_observed_at", "ingested_at", "parse_status", "document_kind", "canonical_uri"]);
  return { revision_id: identifier(fields.revision_id), document_id: identifier(fields.document_id), revision_number: integer(fields.revision_number, 1), source_id: identifier(fields.source_id), source_published_at: nullableTimestamp(fields.source_published_at), source_modified_at: nullableTimestamp(fields.source_modified_at), first_observed_at: nullableTimestamp(fields.first_observed_at), ingested_at: nullableTimestamp(fields.ingested_at), parse_status: enumeration(fields.parse_status, ["pending", "parsed", "partial", "failed", "legacy_unverified"]), document_kind: enumeration(fields.document_kind, ["advisory", "article", "paper", "repository_record", "standard", "policy"]), canonical_uri: nullableHttpUri(fields.canonical_uri) };
}

function parseClaim(value: unknown): ClaimSummary {
  const fields = record(value, ["claim_id", "predicate", "display_value", "origin", "status", "source_revision_id", "evidence_ids"]);
  return { claim_id: identifier(fields.claim_id), predicate: text(fields.predicate, 200), display_value: text(fields.display_value, 4000), origin: enumeration(fields.origin, claimOrigins), status: enumeration(fields.status, claimStatuses), source_revision_id: nullableIdentifier(fields.source_revision_id), evidence_ids: list(fields.evidence_ids, identifier, 100) };
}

/** 仅接受主控冻结的schema 2；未知字段或非法状态作为合同错误，不降级成空数据。 */
export function parseEventListResponse(value: unknown): EventListResponse {
  const fields = record(value, ["schema_version", "items", "next_cursor", "data_mode"]);
  return { schema_version: schemaVersion(fields.schema_version), items: list(fields.items, parseEventSummary, 100), next_cursor: fields.next_cursor === null ? null : text(fields.next_cursor, 2048), data_mode: enumeration(fields.data_mode, dataModes) };
}

export function parseEventDetailResponse(value: unknown): EventDetailResponse {
  const fields = record(value, ["schema_version", "event", "dimensions", "revisions", "claims", "business_version", "data_mode"]);
  const businessVersion = integer(fields.business_version, 1);
  return { schema_version: schemaVersion(fields.schema_version), event: parseEventSummary(fields.event), dimensions: list(fields.dimensions, parseEnrichment, 9), revisions: list(fields.revisions, parseRevision), claims: list(fields.claims, parseClaim), business_version: businessVersion, data_mode: enumeration(fields.data_mode, dataModes) };
}

export function parseEvidenceResponse(value: unknown): EvidenceResponse {
  const fields = record(value, ["schema_version", "span_id", "revision_id", "block_id", "start_offset", "end_offset", "quote_text", "quote_sha256", "locator_kind", "page_number", "json_pointer", "verified_at", "source_uri", "source_published_at", "source_modified_at", "first_observed_at", "ingested_at", "data_mode"]);
  const start = integer(fields.start_offset, 0);
  const end = integer(fields.end_offset, 0);
  const hash = text(fields.quote_sha256);
  if (end < start || !/^[0-9a-f]{64}$/.test(hash)) return invalidContract();
  return { schema_version: schemaVersion(fields.schema_version), span_id: identifier(fields.span_id), revision_id: identifier(fields.revision_id), block_id: nullableIdentifier(fields.block_id), start_offset: start, end_offset: end, quote_text: text(fields.quote_text), quote_sha256: hash, locator_kind: enumeration(fields.locator_kind, ["text", "pdf_page", "json_pointer", "legacy_unverified"]), page_number: fields.page_number === null ? null : integer(fields.page_number, 1), json_pointer: nullableText(fields.json_pointer), verified_at: nullableTimestamp(fields.verified_at), source_uri: nullableHttpUri(fields.source_uri), source_published_at: nullableTimestamp(fields.source_published_at), source_modified_at: nullableTimestamp(fields.source_modified_at), first_observed_at: nullableTimestamp(fields.first_observed_at), ingested_at: nullableTimestamp(fields.ingested_at), data_mode: enumeration(fields.data_mode, dataModes) };
}
