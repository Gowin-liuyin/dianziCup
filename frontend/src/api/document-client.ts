import { ApiProblem, fetchJson } from "./client";
import { documentKinds, sourceCategories, parseDocumentDetailResponse, parseDocumentListResponse, parseDocumentRevisionsResponse, type DocumentKind, type DocumentListResponse, type DocumentDetailResponse, type DocumentRevisionsResponse, type SourceCategory } from "./document-contracts";

export interface DocumentFilters { q?: string; document_kind?: DocumentKind; source_category?: SourceCategory; cursor?: string; limit?: number; }
function validateInteger(value: number, minimum: number, maximum: number): void {
  if (!Number.isSafeInteger(value) || value < minimum || value > maximum) throw new ApiProblem(422, "validation_error", false);
}
function documentPath(id: string): string {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) throw new ApiProblem(422, "validation_error", false);
  return `/v1/documents/${id}`;
}

export async function getDocumentList(filters: DocumentFilters = {}, signal?: AbortSignal): Promise<DocumentListResponse> {
  const query = new URLSearchParams();
  if (filters.q !== undefined) {
    if ([...filters.q].length > 500 || filters.q.includes("\0")) throw new ApiProblem(422, "validation_error", false);
    if (filters.q) query.set("q", filters.q);
  }
  if (filters.document_kind !== undefined) {
    if (!documentKinds.includes(filters.document_kind)) throw new ApiProblem(422, "validation_error", false);
    query.set("document_kind", filters.document_kind);
  }
  if (filters.source_category !== undefined) {
    if (!sourceCategories.includes(filters.source_category)) throw new ApiProblem(422, "validation_error", false);
    query.set("source_category", filters.source_category);
  }
  if (filters.cursor !== undefined) {
    if (!filters.cursor || [...filters.cursor].length > 2048) throw new ApiProblem(422, "validation_error", false);
    query.set("cursor", filters.cursor);
  }
  const limit = filters.limit ?? 20;
  validateInteger(limit, 1, 100);
  query.set("limit", String(limit));
  return parseDocumentListResponse(await fetchJson(`/v1/documents?${query}`, {}, signal));
}

/** 证据后续页必须由调用方固定revisionId；错误对象与跨版本响应不进入资料正文。 */
export async function getDocumentDetail(id: string, revisionId: string | null = null, evidenceOffset = 0, signal?: AbortSignal): Promise<DocumentDetailResponse> {
  const path = documentPath(id);
  validateInteger(evidenceOffset, 0, 2000);
  const query = new URLSearchParams();
  if (revisionId !== null) { documentPath(revisionId); query.set("revision_id", revisionId); }
  if (evidenceOffset > 0 && revisionId === null) throw new ApiProblem(422, "validation_error", false);
  query.set("evidence_offset", String(evidenceOffset));
  query.set("evidence_limit", "100");
  const result = parseDocumentDetailResponse(await fetchJson(`${path}?${query}`, {}, signal));
  if (result.document.document_id.toLowerCase() !== id.toLowerCase() || (revisionId !== null && result.document.revision_id.toLowerCase() !== revisionId.toLowerCase()) || (result.next_evidence_offset !== null && result.next_evidence_offset <= evidenceOffset)) throw new ApiProblem(502, "invalid_response", true);
  return result;
}
export async function getDocumentRevisions(id: string, offset = 0, signal?: AbortSignal): Promise<DocumentRevisionsResponse> {
  const path = documentPath(id);
  validateInteger(offset, 0, 100000);
  const result = parseDocumentRevisionsResponse(await fetchJson(`${path}/revisions?offset=${offset}&limit=20`, {}, signal));
  if (result.items.some((revision) => revision.document_id.toLowerCase() !== id.toLowerCase()) || (result.next_offset !== null && result.next_offset <= offset)) throw new ApiProblem(502, "invalid_response", true);
  return result;
}
