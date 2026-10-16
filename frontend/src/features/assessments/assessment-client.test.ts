import { afterEach, describe, expect, it, vi } from "vitest";
import { createAssessment, getAssessment } from "./assessment-client";
import { syntheticAssessment, syntheticAssessmentId, syntheticScope } from "./assessment.fixture";

function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }); }
const input = { asset_id: syntheticScope.assetId, asset_snapshot_id: syntheticScope.snapshotId, rule_id: syntheticScope.ruleId, rule_version: 1 };
afterEach(() => vi.unstubAllGlobals());
describe("R17 assessment HTTP client · explicit synthetic transport", () => {
  it("uses the original Cookie/CSRF path and exact four-field body, then GET", async () => {
    const fetch = vi.fn<(path: string, options?: RequestInit) => Promise<Response>>(async (path) => response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : syntheticAssessment()));
    vi.stubGlobal("fetch", fetch);
    await createAssessment(syntheticScope.tenantId, input); await getAssessment(syntheticScope, syntheticAssessmentId);
    expect(fetch).toHaveBeenNthCalledWith(2, "/v1/assessments", expect.objectContaining({ method: "POST", credentials: "include", cache: "no-store", body: JSON.stringify(input) }));
    const [, options] = fetch.mock.calls[1] ?? [];
    expect(new Headers(options?.headers).get("X-CSRF-Token")).toBe("synthetic-csrf");
    expect(new Headers(options?.headers).get("Idempotency-Key")).toBeNull();
    expect(fetch).toHaveBeenLastCalledWith(`/v1/assessments/${syntheticAssessmentId}`, expect.objectContaining({ credentials: "include", cache: "no-store" }));
  });
  it("validates before IO and checks the latest intent after CSRF before writing", async () => {
    const fetch = vi.fn(async () => response({ csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" })); vi.stubGlobal("fetch", fetch);
    await expect(createAssessment(syntheticScope.tenantId, { ...input, rule_version: 0 })).rejects.toMatchObject({ status: 422 });
    await expect(getAssessment(syntheticScope, "../private")).rejects.toMatchObject({ status: 422 }); expect(fetch).not.toHaveBeenCalled();
    await expect(createAssessment(syntheticScope.tenantId, input, undefined, () => false)).rejects.toMatchObject({ code: "request_canceled" }); expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each([401, 403, 404, 409, 422, 503])("preserves HTTP failure %i and sends no fallback result", async (status) => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ error: { code: "synthetic-failure", retryable: status === 503 } }, status)));
    await expect(getAssessment(syntheticScope, syntheticAssessmentId)).rejects.toMatchObject({ status });
  });
  it("rejects 201/202 and a valid receipt for another requested identity", async () => {
    for (const status of [201, 202]) { vi.stubGlobal("fetch", vi.fn(async () => response(syntheticAssessment(), status))); await expect(getAssessment(syntheticScope, syntheticAssessmentId)).rejects.toMatchObject({ code: "invalid_response" }); }
    vi.stubGlobal("fetch", vi.fn(async () => response({ ...syntheticAssessment(), asset_snapshot_id: "a0000000-0000-4000-8000-000000000099" })));
    await expect(getAssessment(syntheticScope, syntheticAssessmentId)).rejects.toMatchObject({ code: "invalid_response", retryable: false });
  });
});
