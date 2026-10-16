import { ApiProblem } from "../../api/client";
import type { Freshness } from "../../api/knowledge-contracts";
import { isAssetIdentifier } from "../assets/asset-contracts";
import { isAssessmentStatus, type AssessmentStatus } from "../recommendations/recommendation-wire-types";

export type ConditionValue = "true" | "false" | "unknown" | "conflict";
export type RuleKind = "software_applicability" | "observed_path" | "research_prerequisites";
export interface ConditionEvaluation {
  node_id: string; value: ConditionValue; reason_code: string; evidence_ids: string[]; asset_field_refs: string[];
  child_results: ConditionEvaluation[]; observed_conflict_ids: string[]; missing_requirements: string[]; limitations: string[];
}
export interface RuleEvaluation {
  rule_id: string; rule_version: number; rule_kind: RuleKind; asset_snapshot_id: string; condition_sha256: string;
  evaluation_tree: ConditionEvaluation; status: AssessmentStatus; limitations: string[];
}
export interface AssessmentRequest { asset_id: string; asset_snapshot_id: string; rule_id: string; rule_version: number }
export interface AssessmentScope { tenantId: string; assetId: string; snapshotId: string; ruleId: string; ruleVersion: number }
export interface AssessmentResponse {
  schema_version: "r11-assessment-http-1"; assessment_id: string; tenant_id: string; asset_id: string; asset_snapshot_id: string;
  event_id: string; rule_id: string; rule_version: number; knowledge_epoch: number | null; scope_epoch_map: Record<string, number | null>;
  rule_result: RuleEvaluation | null; status: AssessmentStatus; freshness: Freshness; missing_requirements: string[]; conflicts: string[];
  limitations: string[]; exposure_result: "not_evaluated" | "observed_path_only"; exploit_evidence_status: "not_verified";
  input_digest: string; created_at: string; reused: boolean;
}
export class AssessmentResponseScopeMismatch extends ApiProblem {
  constructor() { super(502, "invalid_response", false); this.name = "AssessmentResponseScopeMismatch"; }
}
function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function record(value: unknown, keys?: readonly string[]): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
  if (keys !== undefined && (Object.keys(value).length !== keys.length || Object.keys(value).some((key) => !keys.includes(key)))) return invalid();
  return Object.fromEntries(Object.entries(value));
}
function text(value: unknown, maximum = 8192): string {
  if (typeof value !== "string" || value.length === 0 || [...value].length > maximum) return invalid();
  return value;
}
function identifier(value: unknown): string { const id = text(value, 36); return isAssetIdentifier(id) ? id.toLowerCase() : invalid(); }
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= minimum && value <= maximum ? value : invalid();
}
function digest(value: unknown): string { const result = text(value, 64); return /^[a-f0-9]{64}$/.test(result) ? result : invalid(); }
function strings(value: unknown, maximum = 10064): string[] {
  return Array.isArray(value) && value.length <= maximum ? value.map((entry: unknown) => text(entry)) : invalid();
}
function status(value: unknown): AssessmentStatus { return isAssessmentStatus(value) ? value : invalid(); }
function conditionTree(value: unknown, seen: Set<string>, depth = 1): ConditionEvaluation {
  if (depth > 8 || seen.size >= 64) return invalid();
  const item = record(value, ["node_id", "value", "reason_code", "evidence_ids", "asset_field_refs", "child_results", "observed_conflict_ids", "missing_requirements", "limitations"]);
  const nodeId = text(item.node_id, 200);
  if (!/^[a-zA-Z0-9_.:-]+$/.test(nodeId) || seen.has(nodeId)) return invalid();
  seen.add(nodeId);
  if (item.value !== "true" && item.value !== "false" && item.value !== "unknown" && item.value !== "conflict") return invalid();
  if (!Array.isArray(item.child_results) || item.child_results.length > 63) return invalid();
  return { node_id: nodeId, value: item.value, reason_code: text(item.reason_code), evidence_ids: strings(item.evidence_ids), asset_field_refs: strings(item.asset_field_refs), child_results: item.child_results.map((child: unknown) => conditionTree(child, seen, depth + 1)), observed_conflict_ids: strings(item.observed_conflict_ids), missing_requirements: strings(item.missing_requirements), limitations: strings(item.limitations) };
}
function ruleResult(value: unknown, scope: AssessmentScope): RuleEvaluation | null {
  if (value === null) return null;
  const item = record(value, ["rule_id", "rule_version", "rule_kind", "asset_snapshot_id", "condition_sha256", "evaluation_tree", "status", "limitations"]);
  if (item.rule_id !== scope.ruleId || item.rule_version !== scope.ruleVersion || identifier(item.asset_snapshot_id) !== scope.snapshotId.toLowerCase()) throw new AssessmentResponseScopeMismatch();
  if (item.rule_kind !== "software_applicability" && item.rule_kind !== "observed_path" && item.rule_kind !== "research_prerequisites") return invalid();
  return { rule_id: text(item.rule_id, 200), rule_version: integer(item.rule_version, 1, 2147483647), rule_kind: item.rule_kind, asset_snapshot_id: identifier(item.asset_snapshot_id), condition_sha256: digest(item.condition_sha256), evaluation_tree: conditionTree(item.evaluation_tree, new Set()), status: status(item.status), limitations: strings(item.limitations) };
}

/** Input identity fields are never widened into tenant, actor, permissions, or a prepared receipt. */
export function validateAssessmentRequest(value: unknown): AssessmentRequest {
  try {
    const item = record(value, ["asset_id", "asset_snapshot_id", "rule_id", "rule_version"]);
    return { asset_id: identifier(item.asset_id), asset_snapshot_id: identifier(item.asset_snapshot_id), rule_id: text(item.rule_id, 200), rule_version: integer(item.rule_version, 1, 2147483647) };
  } catch { throw new ApiProblem(422, "validation_error", false); }
}

/** The HTTP projection is bound to the current authenticated tenant and the requested fixed inputs. */
export function parseAssessmentResponse(value: unknown, scope: AssessmentScope, expectedAssessmentId?: string): AssessmentResponse {
  const item = record(value, ["schema_version", "assessment_id", "tenant_id", "asset_id", "asset_snapshot_id", "event_id", "rule_id", "rule_version", "knowledge_epoch", "scope_epoch_map", "rule_result", "status", "freshness", "missing_requirements", "conflicts", "limitations", "exposure_result", "exploit_evidence_status", "input_digest", "created_at", "reused"]);
  const assessmentId = identifier(item.assessment_id);
  if (item.tenant_id !== scope.tenantId || identifier(item.asset_id) !== scope.assetId.toLowerCase() || identifier(item.asset_snapshot_id) !== scope.snapshotId.toLowerCase() || item.rule_id !== scope.ruleId || item.rule_version !== scope.ruleVersion || (expectedAssessmentId !== undefined && assessmentId !== expectedAssessmentId.toLowerCase())) throw new AssessmentResponseScopeMismatch();
  if (item.schema_version !== "r11-assessment-http-1") return invalid();
  if (item.freshness !== "current" && item.freshness !== "stale" && item.freshness !== "unknown") return invalid();
  if (item.exposure_result !== "not_evaluated" && item.exposure_result !== "observed_path_only") return invalid();
  if (item.exploit_evidence_status !== "not_verified" || typeof item.reused !== "boolean") return invalid();
  const epochs = record(item.scope_epoch_map);
  if (Object.keys(epochs).length > 10064) return invalid();
  const scopeEpochMap = Object.fromEntries(Object.entries(epochs).map(([key, epoch]) => [text(key), epoch === null ? null : integer(epoch)]));
  const createdAt = text(item.created_at, 64);
  if (!/T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(createdAt) || !Number.isFinite(Date.parse(createdAt))) return invalid();
  const result = ruleResult(item.rule_result, scope);
  const assessmentStatus = status(item.status);
  if (result === null ? assessmentStatus !== "insufficient_evidence" : result.status !== assessmentStatus) return invalid();
  return { schema_version: item.schema_version, assessment_id: assessmentId, tenant_id: scope.tenantId, asset_id: identifier(item.asset_id), asset_snapshot_id: identifier(item.asset_snapshot_id), event_id: text(item.event_id, 200), rule_id: text(item.rule_id, 200), rule_version: integer(item.rule_version, 1, 2147483647), knowledge_epoch: item.knowledge_epoch === null ? null : integer(item.knowledge_epoch), scope_epoch_map: scopeEpochMap, rule_result: result, status: assessmentStatus, freshness: item.freshness, missing_requirements: strings(item.missing_requirements), conflicts: strings(item.conflicts), limitations: strings(item.limitations), exposure_result: item.exposure_result, exploit_evidence_status: item.exploit_evidence_status, input_digest: digest(item.input_digest), created_at: createdAt, reused: item.reused };
}
