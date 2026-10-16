import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("default investigation navigation", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it.each(["#investigations", "#investigations/00000000-0000-4000-8000-000000000001"])("keeps anonymous route %s without private requests", async (hash) => {
    const fetchFixture = vi.fn(async (input: RequestInfo | URL) => {
      if (input === "/v1/auth/me") return new Response(JSON.stringify({ error: { code: "unauthenticated" } }), { status: 401 });
      if (input === "/v1/health/live") return new Response(JSON.stringify({ status: "live" }));
      if (input === "/v1/health/ready") return new Response(JSON.stringify({ status: "degraded", reason: "explicit unit fixture", dependencies: {} }), { status: 503 });
      throw new Error("unexpected isolated fixture request");
    });
    vi.stubGlobal("fetch", fetchFixture);
    window.history.replaceState(null, "", `/${hash}`);
    render(<App />);
    await screen.findByRole("heading", { name: "登录后使用调查工作台" });
    expect(screen.getByRole("heading", { name: "证据调查工作台" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Agent 调查" }).getAttribute("aria-current")).toBe("page");
    expect(fetchFixture.mock.calls).toHaveLength(3);
  });
});
