import { describe, expect, it } from "vitest";
import { readGraphSelection, readWorkspacePage } from "./workspace-navigation";

describe("event-scoped graph hash route", () => {
  const id = "A1000000-0000-4000-8000-000000000001";
  it("restores and normalizes one exact event UUID", () => {
    expect(readGraphSelection(`#graph/${id}`)).toEqual({ eventId: id.toLowerCase() });
    expect(readWorkspacePage(`#graph/${id}`)).toBe("graph");
  });
  it.each(["#graph", "#graph/../private", "#graph/https://external.invalid", `#graph/${id}/extra`, `#graph/${id}?tenant=other`, `#graph/${id}/evidence/${id}`, `#graph/${id}%2fextra`])("does not accept a forged route: %s", (hash) => {
    expect(readGraphSelection(hash)).toBeNull();
    expect(readWorkspacePage(hash)).toBe(hash === "#graph" ? "graph" : "missing");
  });
});
