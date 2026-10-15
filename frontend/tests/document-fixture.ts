import type { DocumentDetailResponse, DocumentSummary } from "../src/api/document-contracts";
import type { EvidenceResponse } from "../src/api/knowledge-contracts";

/** 仅供隔离测试，产品代码不导入此文件。 */
export const documentId = "00000000-0000-4000-8000-000000000101";
export const revisionId = "00000000-0000-4000-8000-000000000102";
export const historicalRevisionId = "00000000-0000-4000-8000-000000000103";
export const evidenceId = "00000000-0000-4000-8000-000000000104";
export const documentFixture: DocumentSummary = {
  document_id: documentId, source_id: "00000000-0000-4000-8000-000000000105", revision_id: revisionId,
  source_name: "隔离测试学术来源", source_category: "academic_paper", document_kind: "paper",
  title: "隔离测试：模型风险研究资料", canonical_uri: "https://example.test/isolated-paper", revision_number: 2, is_current: true,
  source_published_at: null, source_modified_at: null, first_observed_at: "2026-10-15T02:00:00Z", ingested_at: "2026-10-15T02:00:01Z",
  parse_status: "partial", content_coverage: "abstract", published_at_raw: "2026-10-14", published_precision: "calendar_date",
};
export const evidenceFixture: EvidenceResponse = {
  schema_version: 2, span_id: evidenceId, revision_id: revisionId, block_id: null, start_offset: 0, end_offset: 47,
  quote_text: "隔离测试原文：<img src=x onerror=alert(1)>研究假设不等于确认风险。", quote_sha256: "95e25d922d8ccd8ece09856a1d7506836c655b7567eb987528e6df126892d60f", locator_kind: "text",
  page_number: null, json_pointer: null, verified_at: "2026-10-15T02:00:01Z", source_uri: "https://example.test/isolated-paper",
  source_published_at: null, source_modified_at: null, first_observed_at: "2026-10-15T02:00:00Z", ingested_at: "2026-10-15T02:00:01Z", data_mode: "fixture",
};
export const detailFixture: DocumentDetailResponse = {
  schema_version: 2, document: documentFixture, evidence: [evidenceFixture], evidence_total: 1, next_evidence_offset: null,
  license_identifier: null, license_uri: null, source_notes: ["隔离测试：仅保存摘要，正文未抓取。"], data_mode: "fixture",
};
