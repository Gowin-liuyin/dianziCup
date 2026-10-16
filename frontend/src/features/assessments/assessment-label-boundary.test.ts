import { afterEach, describe, expect, it, vi } from "vitest";
import { createAssessment, getAssessment } from "./assessment-client";
import { syntheticAssessment, syntheticAssessmentId, syntheticScope } from "./assessment.fixture";

function response(body: unknown) { return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } }); }
afterEach(() => vi.unstubAllGlobals());
describe("R17 Label fix1 · explicit synthetic HTTP transport", () => {
  it.each(["𠮷".repeat(101), "𠮷".repeat(200), "  e\u0301𠮷  "])("sends and reads the exact untrimmed, unnormalized Label (%#)", async (ruleId) => {
    const saved = syntheticAssessment();
    const payload = { ...saved, rule_id: ruleId, rule_result: { ...saved.rule_result, rule_id: ruleId } };
    const calls: { path: string; options?: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => { calls.push({ path, options }); return response(path === "/v1/auth/csrf" ? { csrf_token: "synthetic-csrf", header_name: "X-CSRF-Token" } : payload); }));
    const request = { asset_id: syntheticScope.assetId, asset_snapshot_id: syntheticScope.snapshotId, rule_id: ruleId, rule_version: 1 };
    expect((await createAssessment(syntheticScope.tenantId, request)).rule_id).toBe(ruleId);
    expect(calls[1]?.options?.body).toBe(JSON.stringify(request));
    expect((await getAssessment({ ...syntheticScope, ruleId }, syntheticAssessmentId)).rule_id).toBe(ruleId);
    expect(calls).toHaveLength(3);
  });
  it.each(["", "𠮷".repeat(201)])("rejects an out-of-contract Label before any fetch (%#)", async (ruleId) => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    const request = { asset_id: syntheticScope.assetId, asset_snapshot_id: syntheticScope.snapshotId, rule_id: ruleId, rule_version: 1 };
    await expect(createAssessment(syntheticScope.tenantId, request)).rejects.toMatchObject({ status: 422, code: "validation_error" });
    await expect(getAssessment({ ...syntheticScope, ruleId }, syntheticAssessmentId)).rejects.toMatchObject({ status: 422, code: "validation_error" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
