import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TaskWorkspace } from "./task-workspace";

const jobId = "10000000-0000-4000-8000-000000000021";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TaskWorkspace", () => {
  it("does not treat an empty form as zero tasks or an unwired page", () => {
    render(<TaskWorkspace />);
    expect(screen.getByText("尚未查询")).toBeTruthy();
    expect(screen.queryByText(/待接通/)).toBeNull();
  });

  it("shows a saved job status and does not call the investigation route", async () => {
    const fetch = vi.fn(async (path: string) => new Response(JSON.stringify({
      job_id: jobId, status: "blocked", attempt_count: 1, error_code: "model_budget_not_authorized", result_ref: null, created_at: "2026-10-16T00:00:00Z", finished_at: null,
    }), { status: path.includes(jobId) ? 200 : 404 }));
    vi.stubGlobal("fetch", fetch);
    render(<TaskWorkspace />);
    fireEvent.change(screen.getByLabelText("来源或富化任务标识"), { target: { value: jobId } });
    fireEvent.submit(screen.getByRole("form", { name: "查询任务收据" }));
    expect(await screen.findByText("blocked")).toBeTruthy();
    expect(screen.getByText("model_budget_not_authorized")).toBeTruthy();
    expect(screen.queryByText("已取得")).toBeNull();
    expect(fetch.mock.calls.some(([path]) => String(path).includes("/investigations/"))).toBe(false);
  });
});
