import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CurrentValidity, RecommendationContentView, type RecommendationContent } from "./recommendation-content";

const content: RecommendationContent = { key: { event_id: "a0000000-0000-4000-8000-000000000001", subscription_id: "b0000000-0000-4000-8000-000000000001", material_version: "synthetic-material-v1" }, kind: "prioritize_verification", priority_bucket: 0, reasons: [{ code: "asset_assessment", matched_key: "synthetic-asset", claim_id: null, citations: [], assessment_id: "c0000000-0000-4000-8000-000000000001" }], assessments: [{ assessment_id: "c0000000-0000-4000-8000-000000000001", asset_id: "d0000000-0000-4000-8000-000000000001", asset_snapshot_id: "e0000000-0000-4000-8000-000000000001", rule_id: "f0000000-0000-4000-8000-000000000001", rule_version: 1, status: "insufficient_evidence", evidence: [], missing_requirements: ["synthetic-configuration-missing"], conflicts: [], limitations: [] }], observed_at: "2026-10-15T08:00:00Z", source_changed_at: null, validity_as_of: "2026-10-15T09:00:00Z", freshness_at_cutoff: "unknown", current_status: "unverified", current_freshness: "unknown", current_state_checked_at: "2026-10-15T09:00:00Z", limitations: [] };
afterEach(cleanup);
describe("frozen pure content views · isolated synthetic inputs, no API", () => {
  it("keeps missing source time and assessment evidence gaps visible", () => {
    render(<RecommendationContentView content={content} />); expect(screen.getByText("未知 / 未留存")).toBeTruthy(); expect(screen.getByText(/synthetic-configuration-missing/)).toBeTruthy(); expect(screen.getByText(/不能解释为已经确认影响/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /核查事件/ }).getAttribute("href")).toContain(content.key.event_id); expect(screen.getByRole("link", { name: content.assessments[0]?.asset_id }).getAttribute("href")).toContain(content.assessments[0]?.asset_id);
  });
  it.each(["stale", "withdrawn", "unknown"] as const)("does not relabel frozen history as current when overlay is %s", (status) => {
    render(<><CurrentValidity status={status} reason="synthetic-source-revision" checkedAt="2026-10-16T09:00:00Z" /><RecommendationContentView content={{ ...content, current_status: "supported", current_freshness: "current" }} /></>);
    expect(screen.getByText(/请勿作为当前有效结论使用/)).toBeTruthy(); expect(screen.getByText("有支持依据")).toBeTruthy(); expect(screen.getByText(/生成时的记录/)).toBeTruthy();
  });
  it("limits evidence exclusion to the saved asset and rule", () => { render(<RecommendationContentView content={{ ...content, kind: "excluded_with_evidence" }} />); expect(screen.getByText(/不能解释为绝对安全/)).toBeTruthy(); });
});
