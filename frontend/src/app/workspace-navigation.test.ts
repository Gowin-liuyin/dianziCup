import { describe, expect, it } from "vitest";
import { readEventSelection, readWorkspacePage } from "./workspace-navigation";

describe("workspace hash boundary", () => {
  it.each(["", "#main-content"])("uses runtime for the entry %s", (hash) => expect(readWorkspacePage(hash)).toBe("runtime"));
  it.each(["events", "sources", "graph", "questions", "assets", "tasks", "changes", "reports", "session", "runtime"])("restores the registered %s workspace", (page) => expect(readWorkspacePage(`#${page}`)).toBe(page));
  it.each(["#constructor", "#__proto__", "#events/other", "#events?tenant=other"])("rejects an unregistered page %s", (hash) => expect(readWorkspacePage(hash)).toBe("missing"));
  it("retains exact event/evidence/revision UUIDs for a historical citation", () => {
    const eventId = "00000000-0000-4000-8000-000000000001";
    const evidenceId = "00000000-0000-4000-8000-000000000002";
    const revisionId = "00000000-0000-4000-8000-000000000003";
    const hash = `#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`;
    expect(readWorkspacePage(hash)).toBe("events");
    expect(readEventSelection(hash)).toEqual({ eventId, evidenceId, revisionId });
    expect(readEventSelection(`${hash}/unexpected`)).toBeNull();
  });
});
