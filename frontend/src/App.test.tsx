import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("workbench shell", () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

  it("shows pending real probes without fake business statistics", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    render(<App />);
    expect(screen.getByRole("heading", { name: "运行概览" })).toBeTruthy();
    expect(screen.getByText("正在获取实际依赖状态…")).toBeTruthy();
    expect(screen.getByText("正在检查当前会话…")).toBeTruthy();
    expect(screen.queryByText(/\d+[\s]*(次|条|个|%)/)).toBeNull();
  });

  it("preserves the selected research workspace on reload without inventing data or API requests", async () => {
    const fetchFixture = vi.fn(async (input: RequestInfo | URL) => {
      if (input === "/v1/auth/me") return new Response(JSON.stringify({ error: { code: "unauthenticated", retryable: false } }), { status: 401 });
      if (input === "/v1/health/live") return new Response(JSON.stringify({ status: "live" }));
      if (input === "/v1/health/ready") return new Response(JSON.stringify({ status: "degraded", reason: "isolated fixture", dependencies: { worker: { state: "not_observed_or_stale" } } }), { status: 503 });
      throw new Error("Unexpected isolated fixture request");
    });
    vi.stubGlobal("fetch", fetchFixture);
    window.history.replaceState(null, "", "/#events");
    const firstRender = render(<App />);
    expect(screen.getByRole("heading", { name: "情报工作区" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "检索情报" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("情报服务待接通")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "证据检视" })).toBeTruthy();
    expect(screen.queryByText("暂无风险")).toBeNull();
    expect(screen.getByRole("link", { name: "情报列表" }).getAttribute("aria-current")).toBe("page");
    firstRender.unmount();
    render(<App />);
    expect(screen.getByRole("heading", { name: "情报工作区" })).toBeTruthy();
    expect(fetchFixture.mock.calls.every(([path]) => typeof path === "string" && ["/v1/auth/me", "/v1/health/live", "/v1/health/ready"].includes(path))).toBe(true);
  });

  it("returns a visible recovery path for an unknown workspace", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    window.history.replaceState(null, "", "/#constructor");
    render(<App />);
    expect(screen.getByRole("heading", { name: "工作区不存在" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "返回运行状态" }).getAttribute("href")).toBe("#runtime");
    window.history.replaceState(null, "", "/#tasks");
    fireEvent(window, new HashChangeEvent("hashchange"));
    expect(screen.getByRole("heading", { name: "调查与任务" })).toBeTruthy();
    expect(screen.getByText(/页面不会通过动画递增进度/)).toBeTruthy();
  });

  it.each([["events", "情报工作区"], ["sources", "来源与采集"]])("keeps the %s workspace while the skip link focuses main content", (page, heading) => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => undefined)));
    window.history.replaceState(null, "", `/#${page}`);
    render(<App />);
    fireEvent.click(screen.getByRole("link", { name: "跳到主要内容" }));
    expect(document.activeElement).toBe(document.getElementById("main-content"));
    expect(window.location.hash).toBe(`#${page}`);
    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "运行概览" })).toBeNull();
  });
});
