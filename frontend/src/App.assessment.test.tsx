import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

describe("default assessment navigation", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.history.replaceState(null, "", "/");
  });

  it("keeps unauthenticated assessment navigation without issuing asset or assessment requests", async () => {
    const fetchFixture = vi.fn(async (input: RequestInfo | URL) => {
      if (input === "/v1/auth/me") return new Response(JSON.stringify({ error: { code: "unauthenticated" } }), { status: 401 });
      if (input === "/v1/health/live") return new Response(JSON.stringify({ status: "live" }));
      if (input === "/v1/health/ready") return new Response(JSON.stringify({ status: "degraded", reason: "explicit unit fixture", dependencies: {} }), { status: 503 });
      throw new Error("unexpected isolated fixture request");
    });
    vi.stubGlobal("fetch", fetchFixture);
    window.history.replaceState(null, "", "/#assessments");
    render(<App />);
    await screen.findByRole("heading", { name: "登录后进行资产研判" });
    expect(screen.getByRole("heading", { name: "资产影响研判" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "影响研判" }).getAttribute("aria-current")).toBe("page");
    expect(screen.queryByRole("combobox", { name: "授权资产" })).toBeNull();
    expect(fetchFixture.mock.calls).toHaveLength(3);
  });
});
