import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SavedCitation } from "./saved-citation";

afterEach(cleanup);
describe("saved citation presentation · isolated synthetic input", () => {
  it("links the specific event, evidence and revision without rendering source markup", () => {
    render(<SavedCitation eventId="a0000000-0000-4000-8000-000000000001" citation={{ evidence_id: "b0000000-0000-4000-8000-000000000001", revision_id: "c0000000-0000-4000-8000-000000000001", quote: "<img src=x onerror=alert(1)> synthetic source text", locator: "synthetic:block:0-54", source_uri: "https://example.invalid/synthetic-source" }} />);
    expect(screen.queryByRole("img")).toBeNull(); expect(screen.getByText(/<img src=x/)).toBeTruthy();
    expect(screen.getByRole("link").getAttribute("href")).toBe("#events/a0000000-0000-4000-8000-000000000001/evidence/b0000000-0000-4000-8000-000000000001/revision/c0000000-0000-4000-8000-000000000001");
  });
});
