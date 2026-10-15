import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AmbientBackdrop } from "./ambient-backdrop";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("decorative background lifecycle", () => {
  it("stays outside the accessible business interface", () => {
    render(<AmbientBackdrop />);
    expect(screen.getByTestId("ambient-backdrop").getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("pauses on document visibility changes and resumes when visible", () => {
    const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(false);
    render(<AmbientBackdrop />);
    expect(screen.getByTestId("ambient-backdrop").getAttribute("data-paused")).toBe("false");
    hidden.mockReturnValue(true);
    fireEvent(document, new Event("visibilitychange"));
    expect(screen.getByTestId("ambient-backdrop").getAttribute("data-paused")).toBe("true");
    hidden.mockReturnValue(false);
    fireEvent(document, new Event("visibilitychange"));
    expect(screen.getByTestId("ambient-backdrop").getAttribute("data-paused")).toBe("false");
  });
});
