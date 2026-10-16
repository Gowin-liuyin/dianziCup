import { ApiProblem, fetchJson, getCsrfToken } from "../../api/client";
import { isAssetIdentifier } from "../assets/asset-contracts";
import { parseAssessmentResponse, validateAssessmentRequest, type AssessmentRequest, type AssessmentResponse, type AssessmentScope } from "./assessment-contracts";

/** Creates one fixed-snapshot assessment through the existing authenticated, no-store request path. */
export async function createAssessment(tenantId: string, input: AssessmentRequest, signal?: AbortSignal, isCurrent: () => boolean = () => true): Promise<AssessmentResponse> {
  const request = validateAssessmentRequest(input);
  const csrfToken = await getCsrfToken(signal);
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const response = await fetchJson("/v1/assessments", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken }, body: JSON.stringify(request) }, signal, [], 30_000, [200]);
  return parseAssessmentResponse(response, { tenantId, assetId: request.asset_id, snapshotId: request.asset_snapshot_id, ruleId: request.rule_id, ruleVersion: request.rule_version });
}

export async function getAssessment(scope: AssessmentScope, assessmentId: string, signal?: AbortSignal): Promise<AssessmentResponse> {
  if (!isAssetIdentifier(assessmentId)) throw new ApiProblem(422, "validation_error", false);
  validateAssessmentRequest({ asset_id: scope.assetId, asset_snapshot_id: scope.snapshotId, rule_id: scope.ruleId, rule_version: scope.ruleVersion });
  return parseAssessmentResponse(await fetchJson(`/v1/assessments/${encodeURIComponent(assessmentId)}`, {}, signal, [], 10_000, [200]), scope, assessmentId);
}
