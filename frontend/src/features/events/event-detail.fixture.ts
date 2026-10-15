import type { EventDetailResponse, EvidenceResponse } from "../../api/knowledge-contracts";

export const fixtureEventId = "10000000-0000-4000-8000-000000000001";
export const fixtureRevisionId = "10000000-0000-4000-8000-000000000002";
export const fixtureOldRevisionId = "10000000-0000-4000-8000-000000000003";
export const fixtureEvidenceId = "10000000-0000-4000-8000-000000000004";
export const fixtureOldEvidenceId = "10000000-0000-4000-8000-000000000005";
const fixtureScoreClaimId = "10000000-0000-4000-8000-000000000006";
const fixtureConflictClaimId = "10000000-0000-4000-8000-000000000007";
const fixtureOtherConflictClaimId = "10000000-0000-4000-8000-000000000008";
const fixtureHypothesisClaimId = "10000000-0000-4000-8000-000000000009";
const fixtureWithdrawnClaimId = "10000000-0000-4000-8000-000000000010";
const fixtureSupersededClaimId = "10000000-0000-4000-8000-000000000011";
const fixtureCitation = { evidence_id: fixtureEvidenceId, revision_id: fixtureRevisionId, quote: "隔离 Fixture：评分来自已保存来源断言，不代表真实风险。", locator: "Unicode [12, 42)", source_uri: "https://example.test/fixture-source" };

/** 合成数据只供隔离测试导入，产品组件没有 fixture 回退入口。 */
export const eventDetailFixture: EventDetailResponse = {
  schema_version: 2,
  event: { event_id: fixtureEventId, event_type: "advisory", title: "隔离 Fixture：九维状态与历史证据", external_ids: ["FIXTURE-ONLY"], primary_product_ids: [], first_seen_at: "2026-10-15T02:00:00Z", status: "active", source_count: 2, latest_revision_id: fixtureRevisionId, freshness: "stale" },
  dimensions: [
    { dimension: "cvss", status: "available", claim_ids: [fixtureScoreClaimId], citations: [fixtureCitation], freshness: "stale", observed_at: "2026-10-15T03:00:00Z", source_version: "fixture-source-revision-2", error_code: null },
    { dimension: "epss", status: "not_found", claim_ids: [], citations: [], freshness: "current", observed_at: "2026-10-15T03:00:00Z", source_version: null, error_code: null },
    { dimension: "kev", status: "not_applicable", claim_ids: [], citations: [], freshness: "current", observed_at: null, source_version: null, error_code: null },
    { dimension: "cwe", status: "conflict", claim_ids: [fixtureConflictClaimId, fixtureOtherConflictClaimId], citations: [fixtureCitation], freshness: "unknown", observed_at: null, source_version: null, error_code: null },
    { dimension: "atlas", status: "pending", claim_ids: [fixtureHypothesisClaimId], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: null },
    { dimension: "versions", status: "blocked", claim_ids: [fixtureWithdrawnClaimId], citations: [], freshness: "stale", observed_at: null, source_version: null, error_code: "fixture_scope_unavailable" },
    { dimension: "literature", status: "failed", claim_ids: [], citations: [], freshness: "unknown", observed_at: null, source_version: null, error_code: "fixture_upstream_failure" },
    { dimension: "poc", status: "available", claim_ids: [], citations: [fixtureCitation], freshness: "current", observed_at: null, source_version: null, error_code: null },
  ],
  claims: [
    { claim_id: fixtureScoreClaimId, predicate: "fixture_cvss_score", display_value: "9.3 · CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", origin: "structured_source", status: "supported", source_revision_id: fixtureRevisionId, evidence_ids: [fixtureEvidenceId] },
    { claim_id: fixtureConflictClaimId, predicate: "fixture_weakness", display_value: "隔离来源 A：CWE-502", origin: "source_explicit", status: "disputed", source_revision_id: fixtureRevisionId, evidence_ids: [fixtureEvidenceId] },
    { claim_id: fixtureOtherConflictClaimId, predicate: "fixture_weakness", display_value: "隔离来源 B：CWE-20", origin: "source_explicit", status: "disputed", source_revision_id: fixtureOldRevisionId, evidence_ids: [fixtureOldEvidenceId] },
    { claim_id: fixtureHypothesisClaimId, predicate: "fixture_atlas_hypothesis", display_value: "隔离模型假设：关联尚未核验。", origin: "model_hypothesis", status: "unverified", source_revision_id: fixtureRevisionId, evidence_ids: [] },
    { claim_id: fixtureWithdrawnClaimId, predicate: "fixture_versions", display_value: "隔离已撤回范围：>=1.0.0 <2.0.0\n完整条件：仅在启用插件时适用，不能删除此条件。", origin: "rule_derived", status: "withdrawn", source_revision_id: fixtureOldRevisionId, evidence_ids: [fixtureOldEvidenceId] },
    { claim_id: fixtureSupersededClaimId, predicate: "fixture_historical_statement", display_value: "隔离旧结论：此断言已被新版本替代。", origin: "human_confirmed", status: "superseded", source_revision_id: fixtureOldRevisionId, evidence_ids: [fixtureOldEvidenceId] },
  ],
  revisions: [
    { revision_id: fixtureRevisionId, document_id: fixtureEventId, revision_number: 2, source_id: fixtureEvidenceId, source_published_at: "2026-10-14T00:00:00Z", source_modified_at: "2026-10-15T00:00:00Z", first_observed_at: "2026-10-15T02:00:00Z", ingested_at: "2026-10-15T02:01:00Z", parse_status: "partial", document_kind: "advisory", canonical_uri: "https://example.test/fixture-source" },
    { revision_id: fixtureOldRevisionId, document_id: fixtureEventId, revision_number: 1, source_id: fixtureOldEvidenceId, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, parse_status: "legacy_unverified", document_kind: "advisory", canonical_uri: null },
  ],
  data_mode: "fixture",
};

export const historicalEvidenceFixture: EvidenceResponse = { schema_version: 2, span_id: fixtureOldEvidenceId, revision_id: fixtureOldRevisionId, block_id: null, start_offset: 12, end_offset: 42, quote_text: "隔离 Fixture：这是修订 1 的保存片段，不能由修订 2 覆盖。", quote_sha256: "a".repeat(64), locator_kind: "text", page_number: null, json_pointer: null, verified_at: "2026-10-15T02:02:00Z", source_uri: null, source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };
