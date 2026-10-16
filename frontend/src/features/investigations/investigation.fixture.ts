import type { CurrentUser } from "../../api/client";
import type { EvidenceResponse } from "../../api/knowledge-contracts";
import type { InvestigationOperation, InvestigationResponse, InvestigationSubmission } from "./investigation-contracts";

export const fixtureJobId = "b1700000-0000-4000-8000-000000000001";
export const fixtureOtherJobId = "b1700000-0000-4000-8000-000000000002";
export const fixtureEventId = "b1700000-0000-4000-8000-000000000003";
export const fixtureEvidenceId = "b1700000-0000-4000-8000-000000000004";
export const fixtureRevisionId = "b1700000-0000-4000-8000-000000000005";
export const fixtureUser: CurrentUser = { user_id: "explicit-fixture-investigator", tenant_id: "explicit-fixture-tenant", role: "analyst", permissions: ["read:public", "read:asset", "write:asset"], permission_version: 1, data_mode: "fixture" };
export function fixtureSubmission(): InvestigationSubmission {
  return { body: { question: "Explicit fixture: what evidence remains missing?", event_id: fixtureEventId, evidence_refs: [], strategy: "B2b", asset_id: null, asset_snapshot_id: null, version_comparison: null }, idempotencyKey: "r17-explicit-fixture-key" };
}
export function fixtureJob(status: InvestigationResponse["status"] = "queued", jobId = fixtureJobId): InvestigationResponse {
  const terminal = ["succeeded", "partial", "failed", "cancelled", "blocked"].includes(status);
  return { job_id: jobId, status, created_at: "2026-10-16T10:00:00Z", updated_at: "2026-10-16T10:00:12Z", started_at: status === "queued" ? null : "2026-10-16T10:00:01Z", finished_at: terminal ? "2026-10-16T10:00:12Z" : null, error_code: null, result_ref: null, elapsed_milliseconds: 12345.678, result: terminal && status !== "cancelled" && status !== "blocked" ? { job_id: jobId, status: status === "succeeded" ? "succeeded" : status === "partial" ? "partial" : "failed", stop_reason: "evidence_gap", graph_version: "r14-langgraph-1", input_sha256: "a".repeat(64), data_mode: "fixture", receipts: [{ role: "collector", status: "not_configured", reason_code: "adapter_not_configured", evidence_ids: [], operation_keys: [], output: {} }], answer: { claims: [{ text: "Explicit fixture: evidence is incomplete.", kind: "source_fact", support_ids: [fixtureEvidenceId] }], citations: [{ evidence_id: fixtureEvidenceId, quote: "Explicit fixture evidence." }] }, evidence_ids: [fixtureEvidenceId], missing_requirements: ["current_support"] } : null };
}
export function fixtureOperation(operationKey = "001", status: InvestigationOperation["status"] = "failed"): InvestigationOperation {
  return { operation_key: operationKey, kind: "tool", role: "collector", status, request_sha256: "b".repeat(64), tool_name: "read_evidence", model_version: null, prompt_version: null, policy_version: "explicit-fixture-policy", cost_status: "unknown", input_bytes: 24, output_bytes: 48, model_calls: 0, tool_calls: 1, created_at: "2026-10-16T10:00:02Z", completed_at: status === "reserved" ? null : "2026-10-16T10:00:03Z" };
}
export function fixtureEvidence(): EvidenceResponse {
  return { schema_version: 2, span_id: fixtureEvidenceId, revision_id: fixtureRevisionId, block_id: null, start_offset: 0, end_offset: 26, quote_text: "Explicit fixture evidence.", quote_sha256: "e".repeat(64), locator_kind: "text", page_number: null, json_pointer: null, verified_at: "2026-10-16T10:00:00Z", source_uri: "https://example.org/explicit-fixture", source_published_at: null, source_modified_at: null, first_observed_at: null, ingested_at: null, data_mode: "fixture" };
}
