import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { URL as NodeURL } from "node:url";
import { ApiProblem } from "../../api/client";
import { AssessmentResponseScopeMismatch, parseAssessmentResponse, validateAssessmentRequest } from "./assessment-contracts";
import { syntheticAssessment, syntheticAssessmentId, syntheticNode, syntheticScope } from "./assessment.fixture";

const request = { asset_id: syntheticScope.assetId, asset_snapshot_id: syntheticScope.snapshotId, rule_id: syntheticScope.ruleId, rule_version: 1 };
describe("R17 assessment contract · explicit synthetic input, no live", () => {
  it("accepts the frozen synthetic receipt serialized by the actual R11 PostgreSQL HTTP suite", () => {
    const payload: unknown = JSON.parse(readFileSync(new NodeURL("../../../../reports/runs/recovery_r17_assessment_panel_20261016/backend_serialized_receipt_example.json", import.meta.url), "utf8"));
    const parsed = parseAssessmentResponse(payload, { tenantId: "fixture-tenant-71a43dab49264dba927cee9c55c3590a", assetId: "6206ff83-71fe-4511-8180-95de341e8c4d", snapshotId: "15f34f18-de7c-55d0-96d8-fc8ff0a00b11", ruleId: "4b5750de-df1a-4941-b75b-97e0d726c23f", ruleVersion: 1 });
    expect(parsed.status).toBe("supported_applicability");
    expect(parsed.rule_result?.evaluation_tree.evidence_ids).toEqual(["3db744c1-9243-45f7-a92e-2ce5b2acb42e"]);
    expect(parsed.rule_result?.evaluation_tree.asset_field_refs).toEqual(["snapshot:15f34f18-de7c-55d0-96d8-fc8ff0a00b11:/components/0"]);
  });
  it.each(["supported_applicability", "excluded_with_evidence", "insufficient_evidence", "conflicting_evidence"] satisfies Array<ReturnType<typeof syntheticAssessment>["status"]>)("preserves %s, null epochs, missing fields and independent exposure", (status) => {
    const parsed = parseAssessmentResponse(syntheticAssessment(status), syntheticScope);
    expect(parsed.status).toBe(status); expect(parsed.knowledge_epoch).toBeNull(); expect(parsed.scope_epoch_map.public).toBeNull();
    expect(parsed.exploit_evidence_status).toBe("not_verified"); expect(parsed.rule_result?.evaluation_tree.value).toBe("unknown");
    expect(parsed.rule_result?.evaluation_tree.asset_field_refs).toEqual(["/components/0/version"]);
  });
  it("accepts strict endpoints of the rule version and Unicode label length", () => {
    expect(validateAssessmentRequest({ ...request, rule_id: "例".repeat(200), rule_version: 2147483647 }).rule_version).toBe(2147483647);
    expect(validateAssessmentRequest({ ...request, asset_id: request.asset_id.toUpperCase() }).asset_id).toBe(request.asset_id);
  });
  it.each([{ ...request, tenant_id: "untrusted" }, { ...request, rule_version: "1" }, { ...request, rule_version: true }, { ...request, rule_version: 0 }, { ...request, rule_version: 1.5 }, { ...request, rule_version: 2147483648 }, { ...request, rule_id: "x".repeat(201) }, { ...request, asset_id: "../private" }])("rejects invalid request and body identity: %j", (input) => {
    expect(() => validateAssessmentRequest(input)).toThrow(ApiProblem);
    try { validateAssessmentRequest(input); } catch (error) { expect(error).toMatchObject({ status: 422, code: "validation_error" }); }
  });
  it.each(["tenant_id", "asset_id", "asset_snapshot_id", "rule_id", "rule_version"])("fails closed on top-level %s identity mismatch", (field) => {
    expect(() => parseAssessmentResponse({ ...syntheticAssessment(), [field]: field === "rule_version" ? 2 : "a0000000-0000-4000-8000-000000000099" }, syntheticScope)).toThrow(AssessmentResponseScopeMismatch);
  });
  it("rejects another GET identity and nested snapshot/rule mismatch without exposing it", () => {
    expect(() => parseAssessmentResponse(syntheticAssessment(), syntheticScope, "a0000000-0000-4000-8000-000000000099")).toThrow(AssessmentResponseScopeMismatch);
    const response = syntheticAssessment();
    expect(() => parseAssessmentResponse({ ...response, rule_result: { ...response.rule_result, rule_id: "another-rule" } }, syntheticScope)).toThrow(AssessmentResponseScopeMismatch);
    expect(parseAssessmentResponse(response, syntheticScope, syntheticAssessmentId).assessment_id).toBe(syntheticAssessmentId);
  });
  it.each([{ freshness: "expired" }, { status: "safe" }, { exploit_evidence_status: "lab_verified" }, { exposure_result: "software_fixed" }, { schema_version: "future" }, { created_at: "2026-10-16T12:00:00" }, { input_digest: "not-a-hash" }, { prepared: { secret: "synthetic-private" } }, { scope_epoch_map: { public: -1 } }])("rejects unexpected or malformed response: %j", (mutation) => {
    expect(() => parseAssessmentResponse({ ...syntheticAssessment(), ...mutation }, syntheticScope)).toThrow(ApiProblem);
  });
  it("keeps unpublished rule null as insufficient, and validates projection status consistency", () => {
    expect(parseAssessmentResponse({ ...syntheticAssessment(), rule_result: null, missing_requirements: ["unsupported_rule"], freshness: "stale" }, syntheticScope).rule_result).toBeNull();
    expect(() => parseAssessmentResponse({ ...syntheticAssessment("supported_applicability"), rule_result: null }, syntheticScope)).toThrow(ApiProblem);
    expect(() => parseAssessmentResponse({ ...syntheticAssessment("supported_applicability"), rule_result: syntheticAssessment().rule_result }, syntheticScope)).toThrow(ApiProblem);
  });
  it("rejects extra tree fields, duplicate node identities and excessive depth", () => {
    const response = syntheticAssessment();
    const result = response.rule_result;
    for (const tree of [{ ...syntheticNode(), secret: "synthetic-private" }, { ...syntheticNode(), child_results: [syntheticNode()] }]) expect(() => parseAssessmentResponse({ ...response, rule_result: { ...result, evaluation_tree: tree } }, syntheticScope)).toThrow(ApiProblem);
    let tree = syntheticNode();
    for (let depth = 0; depth < 8; depth += 1) tree = { ...syntheticNode(), node_id: `depth-${depth}`, child_results: [tree] };
    expect(() => parseAssessmentResponse({ ...response, rule_result: { ...result, evaluation_tree: tree } }, syntheticScope)).toThrow(ApiProblem);
  });
});
