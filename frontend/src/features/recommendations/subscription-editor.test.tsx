import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiProblem } from "../../api/client";
import { SubscriptionEditor } from "./subscription-editor";

afterEach(cleanup);

describe("subscription local editor · explicit isolated synthetic inputs", () => {
  it("requires an explicit interest and does not submit an empty draft", () => {
    const submit = vi.fn(); render(<SubscriptionEditor canSubmit pending={false} error={null} onSubmit={submit} />);
    fireEvent.submit(screen.getByRole("form")); expect(submit).not.toHaveBeenCalled(); expect(screen.getByRole("alert").textContent).toContain("至少填写一个");
  });
  it.each(["not-a-uuid", "a0000000-0000-4000-8000-000000000001\nA0000000-0000-4000-8000-000000000001"])("rejects invalid and duplicate private asset ids: %s", (assets) => {
    const submit = vi.fn(); render(<SubscriptionEditor canSubmit pending={false} error={null} onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText("授权资产 UUID（每行一个）"), { target: { value: assets } }); fireEvent.submit(screen.getByRole("form")); expect(submit).not.toHaveBeenCalled(); expect(screen.getByRole("alert")).toBeTruthy();
  });
  it("submits only draft business values and preserves the priority direction", () => {
    const submit = vi.fn(); render(<SubscriptionEditor canSubmit pending={false} error={null} onSubmit={submit} />);
    fireEvent.change(screen.getByLabelText("产品关注（每行一个）"), { target: { value: " synthetic-package \n" } }); fireEvent.change(screen.getByLabelText("接收优先级范围"), { target: { value: "1" } }); fireEvent.change(screen.getByLabelText("订阅状态"), { target: { value: "disabled" } }); fireEvent.submit(screen.getByRole("form"));
    expect(submit).toHaveBeenCalledWith({ productKeys: ["synthetic-package"], assetIds: [], riskTopics: [], maximumPriorityBucket: 1, enabled: false }, null);
    expect(screen.getByText(/已保存的推荐与报告仍保留/)).toBeTruthy();
  });
  it("does not overwrite an unsaved draft when the current CAS version changes", () => {
    const submit = vi.fn(); const props = { canSubmit: true, pending: false, error: null, onSubmit: submit, currentVersion: 1 };
    const view = render(<SubscriptionEditor {...props} />); fireEvent.change(screen.getByLabelText("风险主题（每行一个）"), { target: { value: "synthetic-unsaved-topic" } });
    view.rerender(<SubscriptionEditor {...props} currentVersion={2} />); fireEvent.submit(screen.getByRole("form")); expect(submit).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("synthetic-unsaved-topic")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "保留输入，采用版本 2" })); fireEvent.submit(screen.getByRole("form")); expect(submit).toHaveBeenCalledWith(expect.objectContaining({ riskTopics: ["synthetic-unsaved-topic"] }), 2);
  });
  it("does not submit while lacking permission or while pending", () => {
    const submit = vi.fn(); const view = render(<SubscriptionEditor canSubmit={false} pending={false} error={null} onSubmit={submit} />); fireEvent.submit(screen.getByRole("form"));
    view.rerender(<SubscriptionEditor canSubmit pending error={null} onSubmit={submit} />); fireEvent.submit(screen.getByRole("form")); expect(submit).not.toHaveBeenCalled();
  });
  it("requires a successful version refresh after a server CAS rejection", () => {
    const submit = vi.fn(); const refresh = vi.fn(); render(<SubscriptionEditor canSubmit pending={false} currentVersion={1} initialDraft={{ productKeys: ["synthetic-unsaved-product"], assetIds: [], riskTopics: [], maximumPriorityBucket: 3, enabled: true }} error={new ApiProblem(409, "version_conflict", false)} onSubmit={submit} onRefresh={refresh} />);
    fireEvent.submit(screen.getByRole("form")); expect(submit).not.toHaveBeenCalled(); expect(screen.getByRole("button", { name: "保存订阅修改" }).hasAttribute("disabled")).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "重新读取版本" })); expect(refresh).toHaveBeenCalledOnce(); expect(screen.getByDisplayValue("synthetic-unsaved-product")).toBeTruthy();
  });
});
