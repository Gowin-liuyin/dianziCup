import type { CurrentUser } from "../../api/client";
import { parseSnapshot } from "../assets/asset-contracts";
import { fixtureAssetId, fixtureSnapshotId, fixtureTenant, snapshotFixture } from "../assets/synthetic-fixtures";
import type { AssessmentResponse, AssessmentScope, ConditionEvaluation } from "./assessment-contracts";

/** Isolated synthetic unit/browser inputs; never imported by the product entry point. */
export const syntheticAssessmentId = "d0000000-0000-4000-8000-000000000001";
export const syntheticEventId = "e0000000-0000-4000-8000-000000000001";
export const syntheticEvidenceId = "f0000000-0000-4000-8000-000000000001";
export const syntheticScope: AssessmentScope = { tenantId: fixtureTenant, assetId: fixtureAssetId, snapshotId: fixtureSnapshotId, ruleId: "synthetic-rule", ruleVersion: 1 };
export const syntheticUser: CurrentUser = { user_id: "synthetic-user", tenant_id: fixtureTenant, role: "analyst", permissions: ["read:asset"], permission_version: 1, data_mode: "fixture" };
export function syntheticSnapshot(number = 2) { return parseSnapshot(snapshotFixture(number), fixtureTenant, fixtureAssetId); }
export function syntheticNode(): ConditionEvaluation {
  return { node_id: "version", value: "unknown", reason_code: "missing_version", evidence_ids: [syntheticEvidenceId], asset_field_refs: ["/components/0/version"], child_results: [], observed_conflict_ids: [], missing_requirements: ["component_version"], limitations: ["partial_inventory"] };
}
export function syntheticAssessment(status: AssessmentResponse["status"] = "insufficient_evidence"): AssessmentResponse {
  return { schema_version: "r11-assessment-http-1", assessment_id: syntheticAssessmentId, tenant_id: fixtureTenant, asset_id: fixtureAssetId, asset_snapshot_id: fixtureSnapshotId, event_id: syntheticEventId, rule_id: syntheticScope.ruleId, rule_version: 1, knowledge_epoch: null, scope_epoch_map: { public: null, "synthetic-product": 1 }, rule_result: { rule_id: syntheticScope.ruleId, rule_version: 1, rule_kind: "software_applicability", asset_snapshot_id: fixtureSnapshotId, condition_sha256: "a".repeat(64), evaluation_tree: syntheticNode(), status, limitations: ["software_applicability_does_not_confirm_exploitation_or_absolute_safety"] }, status, freshness: "current", missing_requirements: ["component_version"], conflicts: [], limitations: ["partial_inventory"], exposure_result: "not_evaluated", exploit_evidence_status: "not_verified", input_digest: "b".repeat(64), created_at: "2026-10-16T12:00:00Z", reused: false };
}
