import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ReportContentView, type ReportContent } from "./report-content";

const report: ReportContent = { subscription_id: "a0000000-0000-4000-8000-000000000001", policy_version: "r15-recommendation-policy-1", frequency: "day", window_start: "2026-10-14T09:00:00Z", cutoff_at: "2026-10-15T09:00:00Z", generated_at: "2026-10-16T09:00:00Z", temporal_mode: "as_of_cutoff", window_basis: "first_material_observed_at", supported_risks: [], verification_items: [], excluded_items: [], intelligence_updates: [], partial: false, continuation_keys: [], stop_reason: "no_items_in_window", limitations: [] };
afterEach(cleanup);
describe("report frozen-time view · explicit isolated synthetic inputs", () => {
  it("shows distinct cutoff, actual generated time and unknown risk on an empty window", () => {
    render(<ReportContentView report={report} />); expect(screen.getByText(/不能据此判断没有风险/)).toBeTruthy(); expect(document.querySelector('time[datetime="2026-10-15T09:00:00Z"]')).toBeTruthy(); expect(document.querySelector('time[datetime="2026-10-16T09:00:00Z"]')).toBeTruthy(); expect(screen.getByText(/生成时间不替代来源发布时间/)).toBeTruthy();
  });
  it("labels a partial weekly report and its continuation separately from saved group counts", () => {
    render(<ReportContentView report={{ ...report, frequency: "week", partial: true, stop_reason: "item_budget", continuation_keys: [{ subscription_id: report.subscription_id, event_id: "b0000000-0000-4000-8000-000000000001", material_version: "synthetic-material-v1" }] }} />); expect(screen.getByRole("heading", { name: "周报 · 保存的历史内容" })).toBeTruthy(); expect(screen.getByText(/另有 1 项待续处理/)).toBeTruthy(); expect(screen.getAllByText("保存 0 项")).toHaveLength(4);
  });
  it("states unsubscribe history without inventing an active reminder", () => { render(<ReportContentView report={{ ...report, stop_reason: "disabled" }} />); expect(screen.getByText(/生成时已退订，未生成新提醒/)).toBeTruthy(); });
});
