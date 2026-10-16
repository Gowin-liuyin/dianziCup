import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RecommendationContentView } from "./recommendation-content";
import { ReportContentView } from "./report-content";
import type { AssessmentReference, EvidenceReference } from "./recommendation-wire-types";
import { syntheticCandidate, syntheticIds, syntheticReport } from "./synthetic-wire-fixtures";

const evidence: EvidenceReference = { evidence_id: syntheticIds.evidence, source_id: syntheticIds.claim, document_id: syntheticIds.event, revision_id: syntheticIds.revision, block_id: "synthetic-block", start_offset: 0, end_offset: 4, quote_text: "test", quote_sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", scope: { visibility: "public", tenant_id: null }, support_kind: "supports", validation_status: "validated" };
function assetCandidate(status: AssessmentReference["status"] = "supported_applicability", savedEvidence = evidence) {
  const candidate = syntheticCandidate();
  candidate.kind = "supported_risk";
  candidate.reasons = [{ code: "asset_assessment", matched_key: syntheticIds.event, claim_id: null, citations: [], assessment_id: syntheticIds.claim }];
  candidate.assessments = [{ assessment_id: syntheticIds.claim, asset_id: syntheticIds.event, asset_snapshot_id: syntheticIds.revision, rule_id: syntheticIds.evidence, rule_version: 1, status, knowledge_epoch: 1, scope_epoch_map: {}, input_digest: "synthetic-input", missing_requirements: [], conflicts: [], limitations: [], evidence: [savedEvidence] }];
  return candidate;
}

afterEach(cleanup);
describe("saved asset evidence · isolated synthetic wire input, no live API", () => {
  it.each([
    ["supported_applicability", "支持适用"], ["excluded_with_evidence", "证据排除"],
    ["insufficient_evidence", "证据不足"], ["conflicting_evidence", "证据冲突"],
  ] as const)("keeps original evidence inspectable for %s", (status, label) => {
    render(<RecommendationContentView content={assetCandidate(status)} />);
    expect(screen.getByRole("heading", { name: `资产依据 · ${label}` })).toBeTruthy();
    expect(screen.getByText("test")).toBeTruthy();
    expect(screen.getByText(/synthetic-block.*Unicode.*0, 4/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /核查保存的原文版本/ }).getAttribute("href")).toBe(`#events/${syntheticIds.event}/evidence/${syntheticIds.evidence}/revision/${syntheticIds.revision}`);
  });
  it.each([
    ["supports", "支持关系"], ["refutes", "反驳关系"], ["context", "上下文材料"],
  ] as const)("preserves %s and unverified as separate evidence fields", (supportKind, label) => {
    render(<RecommendationContentView content={assetCandidate("insufficient_evidence", { ...evidence, support_kind: supportKind, validation_status: "unverified" })} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(/未核验，不能作为已确认依据/)).toBeTruthy();
    expect(screen.queryByText("已核验")).toBeNull();
    expect(screen.queryByRole("link", { name: /来源地址/ })).toBeNull();
  });
  it.each(["day", "week"] as const)("renders asset-only evidence in the canonical %s report group", (frequency) => {
    const report = syntheticReport().content.report;
    render(<ReportContentView report={{ ...report, frequency, supported_risks: [assetCandidate()], intelligence_updates: [] }} />);
    expect(screen.getByText("test")).toBeTruthy();
    expect(screen.getByRole("link", { name: /核查保存的原文版本/ }).getAttribute("href")).toContain(`/revision/${syntheticIds.revision}`);
    expect(screen.getByText("已核验")).toBeTruthy();
  });
});
