import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiProblem } from "../../api/client";
import { PrivateWorkspaceAccess, RecommendationError, RecommendationLoading } from "./workspace-state";

afterEach(cleanup);

describe("recommendation presentation states · isolated synthetic inputs", () => {
  it.each([401, 403])("does not offer retry after denied access %s", (status) => {
    render(<RecommendationError error={new ApiProblem(status, "request_failed", false)} onRetry={vi.fn()} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("alert")).toBeTruthy();
  });
  it("distinguishes a missing or hidden collection from an unconfigured service", () => {
    render(<RecommendationError error={new ApiProblem(404, "not_found", false)} collection />);
    expect(screen.getByText(/记录不存在，或当前会话不能访问/)).toBeTruthy();
    expect(screen.queryByText(/尚未配置/)).toBeNull();
  });
  it("reserves the unconfigured message for an explicit 503 code", () => {
    render(<RecommendationError error={new ApiProblem(503, "recommendations_not_configured", true)} collection />);
    expect(screen.getByText(/服务尚未配置/)).toBeTruthy();
    expect(screen.getByText(/不能解释为零记录或无风险/)).toBeTruthy();
  });
  it("keeps CAS rejection actionable without announcing success", () => {
    const retry = vi.fn(); render(<RecommendationError error={new ApiProblem(409, "version_conflict", false)} onRetry={retry} />);
    expect(screen.getByText(/输入尚未保存/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重新读取版本" })); expect(retry).toHaveBeenCalledOnce();
  });
  it("does not interpret a dependency failure as a no-risk result", () => {
    render(<RecommendationError error={new ApiProblem(503, "service_unavailable", true)} />);
    expect(screen.getByText(/不能据此判断无推荐或无风险/)).toBeTruthy();
  });
  it("labels loading and session expiry without sending requests", () => {
    render(<><RecommendationLoading description="正在读取冻结报告…" /><PrivateWorkspaceAccess loading={false} expired title="登录后继续" /></>);
    expect(screen.getByRole("status").textContent).toBe("正在读取冻结报告…");
    expect(screen.getByRole("heading", { name: "会话已失效，私有结果已清除" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "核对会话与权限" }).getAttribute("href")).toBe("#session");
  });
});
