import { describe, expect, it } from "vitest";
import { readWorkspacePage } from "./workspace-navigation";

describe("workspace hash boundary", () => {
  it.each(["", "#main-content"])("uses runtime for the entry %s", (hash) => expect(readWorkspacePage(hash)).toBe("runtime"));
  it.each(["events", "sources", "graph", "questions", "assets", "tasks", "changes", "reports", "session", "runtime"])("restores the registered %s workspace", (page) => expect(readWorkspacePage(`#${page}`)).toBe(page));
  it.each(["#constructor", "#__proto__", "#events/other", "#events?tenant=other"])("rejects an unregistered page %s", (hash) => expect(readWorkspacePage(hash)).toBe("missing"));
});
