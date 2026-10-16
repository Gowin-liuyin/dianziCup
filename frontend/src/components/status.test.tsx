import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LoadingState, StatusBadge } from "./status";

afterEach(cleanup);

describe("T40-C04/C06 visible result state labels", () => {
  it.each([["blocked", "已阻塞"], ["retry_wait", "等待重试"], ["succeeded", "本次任务已完成"]])("labels the actual %s task state without claiming dependency readiness", (state, label) => {
    render(<StatusBadge state={state} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.queryByText("就绪")).toBeNull();
  });
  it("announces an ongoing read without a made-up progress percentage", () => {
    render(<LoadingState description="正在读取指定历史版本…" />);
    expect(screen.getByRole("status").textContent).toBe("正在读取指定历史版本…");
    expect(screen.getByRole("status").parentElement?.getAttribute("aria-busy")).toBe("true");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
  it.each([["stale", "已过期"], ["partial", "部分完成"], ["unknown", "未知"], ["not_configured", "未配置"], ["not_observed_or_stale", "待观测 / 已过期"], ["unavailable", "不可用"], ["provider_new_state", "未知状态：provider_new_state"], ["constructor", "未知状态：constructor"]])("keeps %s visibly distinct from success", (state, expectedLabel) => {
    render(<StatusBadge state={state} />);
    expect(screen.getByText(expectedLabel)).toBeTruthy();
    expect(screen.queryByText("就绪")).toBeNull();
    expect(document.querySelector(".confirmed")).toBeNull();
  });
});
