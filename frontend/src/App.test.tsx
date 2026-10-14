import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("workbench shell", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("shows pending real probes without fake business statistics", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<App />);
    expect(screen.getByRole("heading", { name: "运行概览" })).toBeTruthy();
    expect(screen.getByText("正在获取实际依赖状态…")).toBeTruthy();
    expect(screen.getByText("正在检查当前会话…")).toBeTruthy();
    expect(screen.queryByText(/\d+[\s]*(次|条|个|%)/)).toBeNull();
  });
});
