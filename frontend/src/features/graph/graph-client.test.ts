import { afterEach, describe, expect, it, vi } from "vitest";
import { getEventGraph } from "./graph-client";
import { graphFixture, graphFixtureEventId, fixtureGraphId } from "./graph.fixture";

afterEach(() => vi.unstubAllGlobals());
describe("R17 graph real same-origin client", () => {
  it("uses the fixed bounded route, cookies and no-store", async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify(graphFixture()))); vi.stubGlobal("fetch", request);
    await getEventGraph(graphFixtureEventId);
    expect(request.mock.calls[0]?.[0]).toBe(`/v1/events/${graphFixtureEventId}/graph?max_nodes=200&max_edges=400`);
    expect(request.mock.calls[0]?.[1]).toMatchObject({ credentials: "include", cache: "no-store" });
  });
  it("reads exact 1.1 HTTP metadata through the real fetchJson path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(graphFixture("r10-graph-1.1.0")))));
    const result = await getEventGraph(graphFixtureEventId); expect(result.rule_version).toBe("r10-graph-1.1.0");
  });
  it.each([401, 403, 404, 409, 503])("keeps HTTP %i failure as a problem", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "graph_unavailable", retryable: status === 503 } }), { status })));
    await expect(getEventGraph(graphFixtureEventId)).rejects.toMatchObject({ status });
  });
  it("rejects wrong event identity from a valid response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(graphFixture()))));
    await expect(getEventGraph(fixtureGraphId(999))).rejects.toMatchObject({ code: "invalid_response" });
  });
  it("rejects arbitrary paths and limits before fetch", async () => {
    const request = vi.fn(); vi.stubGlobal("fetch", request);
    await expect(getEventGraph("https://private.invalid")).rejects.toMatchObject({ status: 422 });
    await expect(getEventGraph(graphFixtureEventId, undefined, { maxNodes: 201 })).rejects.toMatchObject({ status: 422 });
    expect(request).not.toHaveBeenCalled();
  });
});
