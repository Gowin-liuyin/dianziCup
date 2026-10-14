import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StatusBadge } from "./status";

afterEach(cleanup);

describe("T40-C04/C06 visible result state labels", () => {
  it.each([["stale", "已过期"], ["partial", "部分完成"], ["unknown", "未知"], ["not_configured", "未配置"], ["not_observed_or_stale", "待观测 / 已过期"], ["unavailable", "不可用"], ["provider_new_state", "未知状态：provider_new_state"], ["constructor", "未知状态：constructor"]])("keeps %s visibly distinct from success", (state, expectedLabel) => {
    render(<StatusBadge state={state} />);
    expect(screen.getByText(expectedLabel)).toBeTruthy();
    expect(screen.queryByText("就绪")).toBeNull();
    expect(document.querySelector(".confirmed")).toBeNull();
  });
});
