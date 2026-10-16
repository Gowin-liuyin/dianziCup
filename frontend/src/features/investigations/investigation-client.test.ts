import { afterEach, describe, expect, it, vi } from "vitest";
import { cancelInvestigation, createInvestigation, getInvestigation, getInvestigationOperations } from "./investigation-client";
import { fixtureJob, fixtureJobId, fixtureOperation, fixtureOtherJobId, fixtureSubmission } from "./investigation.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
afterEach(() => vi.unstubAllGlobals());
describe("R17 investigation authenticated HTTP client · explicit synthetic transport", () => {
  it("uses exact POST body, session CSRF and stable idempotency key, then owner-scoped GET and encoded cursor", async () => {
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path, options) => response(path === "/v1/auth/csrf" ? { csrf_token: "explicit-fixture-csrf", header_name: "X-CSRF-Token" } : path.includes("/tool-runs") ? { items: [fixtureOperation("z:next")], next_cursor: null } : fixtureJob(), options?.method === "POST" ? 202 : 200));
    vi.stubGlobal("fetch", fetch);
    const submission = fixtureSubmission();
    await createInvestigation(submission); await createInvestigation(submission);
    await getInvestigation(fixtureJobId); await getInvestigationOperations(fixtureJobId, "a:/cursor?");
    const writes = fetch.mock.calls.filter(([, options]) => options?.method === "POST");
    expect(writes).toHaveLength(2);
    expect(writes[0]?.[0]).toBe("/api/v1/investigations");
    expect(writes[0]?.[1]).toMatchObject({ body: JSON.stringify(submission.body), credentials: "include", cache: "no-store" });
    expect(new Headers(writes[0]?.[1]?.headers).get("X-CSRF-Token")).toBe("explicit-fixture-csrf");
    expect(new Headers(writes[1]?.[1]?.headers).get("Idempotency-Key")).toBe(submission.idempotencyKey);
    expect(new Headers(writes[0]?.[1]?.headers).has("Authorization")).toBe(false);
    expect(fetch.mock.calls.at(-1)?.[0]).toBe(`/api/v1/investigations/${fixtureJobId}/tool-runs?limit=20&cursor=a%3A%2Fcursor%3F`);
  });
  it("uses CSRF for cancellation and preserves unknown outcome until actual response", async () => {
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path) => response(path === "/v1/auth/csrf" ? { csrf_token: "explicit-fixture-csrf", header_name: "X-CSRF-Token" } : fixtureJob("cancelled"))); vi.stubGlobal("fetch", fetch);
    expect((await cancelInvestigation(fixtureJobId)).status).toBe("cancelled");
    const [, options] = fetch.mock.calls[1] ?? [];
    expect(options).toMatchObject({ method: "POST", credentials: "include", cache: "no-store" });
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("explicit-fixture-csrf");
    expect(options?.body).toBeUndefined();
  });
  it("validates before IO and refuses writes after CSRF resolves into an obsolete session", async () => {
    const fetch = vi.fn(async () => response({ csrf_token: "explicit-fixture-csrf", header_name: "X-CSRF-Token" })); vi.stubGlobal("fetch", fetch);
    await expect(getInvestigation("../../private")).rejects.toMatchObject({ status: 422 });
    await expect(createInvestigation({ ...fixtureSubmission(), idempotencyKey: "invalid key" })).rejects.toMatchObject({ status: 422 });
    expect(fetch).not.toHaveBeenCalled();
    let checks = 0;
    await expect(createInvestigation(fixtureSubmission(), undefined, () => ++checks === 1)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fetch).toHaveBeenCalledTimes(1);
    checks = 0;
    await expect(cancelInvestigation(fixtureJobId, undefined, () => ++checks === 1)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it.each([401, 403, 404, 409, 422, 503])("preserves HTTP %i without returning fake result", async (status) => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ error: { code: status === 409 ? "workflow_changed" : "explicit-fixture-failure", retryable: status === 503 } }, status)));
    await expect(getInvestigation(fixtureJobId)).rejects.toMatchObject({ status, retryable: status === 503 });
  });
  it("rejects unexpected HTTP status and response identity rather than accepting unrelated jobs", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response(fixtureJob(), 202)));
    await expect(getInvestigation(fixtureJobId)).rejects.toMatchObject({ code: "invalid_response" });
    vi.stubGlobal("fetch", vi.fn(async () => response(fixtureJob("queued", fixtureOtherJobId))));
    await expect(getInvestigation(fixtureJobId)).rejects.toMatchObject({ code: "invalid_response" });
  });
});
