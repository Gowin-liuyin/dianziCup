import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("workbench shell", () => {
  it("shows disconnected state without fake business statistics", () => {
    render(<App />);
    expect(screen.getByTestId("connection-status").textContent).toContain("未连接");
    expect(screen.queryByText(/\d+[\s]*(次|条|个|%)/)).toBeNull();
  });
});
