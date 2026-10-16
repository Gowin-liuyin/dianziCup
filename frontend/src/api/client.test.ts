import { randomBytes } from "node:crypto";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem, fetchJson, getCsrfToken, getCurrentUser, getReadiness, getSessionSnapshot, loginSession, logoutSession } from "./client";

const fixtureUser = { user_id: "fixture-user", tenant_id: "fixture-tenant", role: "analyst", permissions: ["read:public"], permission_version: 1, data_mode: "fixture" };
const fixtureNonce = randomBytes(32).toString("hex");

function mockResponse(body: unknown, status = 200) {
  return vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
}

afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

describe("strict R01 HTTP boundary — synthetic response fixtures", () => {
  it("parses server identity without accepting a made-up permission version", async () => {
    mockResponse(fixtureUser);
    expect(await getCurrentUser()).toEqual(fixtureUser);
    mockResponse({ ...fixtureUser, permission_version: "1" });
    await expect(getCurrentUser()).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("reads identity and nonce from one me response without exposing nonce in the user object", async () => {
    mockResponse({ ...fixtureUser, csrf_token: fixtureNonce });
    const snapshot = await getSessionSnapshot();
    expect(snapshot.user).toEqual(fixtureUser);
    expect(snapshot.csrfToken).toBe(fixtureNonce);
    expect(Object.hasOwn(snapshot.user, "csrf_token")).toBe(false);
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0]?.[0]).toBe("/v1/auth/me");
  });

  it.each([undefined, null, "", "  ", 4])("rejects invalid atomic snapshot nonce %j without another request", async (invalidNonce) => {
    mockResponse({ ...fixtureUser, csrf_token: invalidNonce });
    await expect(getSessionSnapshot()).rejects.toMatchObject({ code: "invalid_response" });
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1);
  });

  it.each([{ role: "root" }, { data_mode: "demo" }, { tenant_id: 4 }, { permissions: ["read:public", 2] }])("rejects invalid auth context %j", async (invalidFields) => {
    mockResponse({ ...fixtureUser, ...invalidFields });
    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiProblem);
  });

  it("does not expose raw exception text or an unsafe trace identifier", async () => {
    mockResponse({ error: { code: "internal_error", message: "fixture-sensitive-dsn", retryable: true }, trace_id: "https://fixture-secret.example" }, 500);
    await expect(getCurrentUser()).rejects.toMatchObject({ message: "操作未完成，请重试或联系管理员。", traceId: undefined, retryable: true });
  });

  it("does not interpret prototype property names as known error codes", async () => {
    mockResponse({ error: { code: "constructor", message: "fixture", retryable: false } }, 500);
    await expect(getCurrentUser()).rejects.toMatchObject({ message: "操作未完成，请重试或联系管理员。" });
  });

  it("keeps __proto__ dependency names as ordinary own fields", async () => {
    mockResponse({ status: "degraded", reason: "fixture", dependencies: Object.fromEntries([["__proto__", { state: "unknown" }]]) }, 503);
    const readiness = await getReadiness();
    expect(Object.keys(readiness.dependencies)).toEqual(["__proto__"]);
    expect(Object.getPrototypeOf(readiness.dependencies)).toBe(Object.prototype);
    expect(readiness.dependencies["__proto__"]).toEqual({ state: "unknown", reason: undefined });
  });

  it("rejects a CSRF response with an unexpected header", async () => {
    mockResponse({ csrf_token: fixtureNonce, header_name: "Authorization" });
    await expect(getCsrfToken()).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("preserves 503 readiness instead of treating failure as an empty success", async () => {
    mockResponse({ status: "not_ready", reason: "fixture database missing", dependencies: { database: { state: "not_configured" } } }, 503);
    expect(await getReadiness()).toEqual({ status: "not_ready", reason: "fixture database missing", dependencies: { database: { state: "not_configured", reason: undefined } } });
  });

  it("requires a server login identity and a valid expiry", async () => {
    mockResponse({ user_id: "fixture-user", csrf_token: fixtureNonce, expires_at: "never" });
    await expect(loginSession("fixture-user", "fixture-password")).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("rejects a logout body that did not confirm revocation", async () => {
    mockResponse({ status: "queued" });
    await expect(logoutSession(fixtureNonce)).rejects.toMatchObject({ code: "invalid_response" });
  });

  it("bounds unresponsive requests and classifies timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn((_input: RequestInfo | URL, options?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      options?.signal?.addEventListener("abort", () => reject(new DOMException("fixture abort", "AbortError")), { once: true });
    })));
    const request = getCurrentUser();
    const assertion = expect(request).rejects.toMatchObject({ code: "request_timeout", retryable: true });
    await vi.advanceTimersByTimeAsync(10_000);
    await assertion;
  });

  it("keeps an explicit question budget bounded without changing the default", async () => {
    vi.useFakeTimers();
    let requestSignal: AbortSignal | null | undefined;
    vi.stubGlobal("fetch", vi.fn((_input: RequestInfo | URL, options?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      requestSignal = options?.signal;
      requestSignal?.addEventListener("abort", () => reject(new DOMException("fixture abort", "AbortError")), { once: true });
    })));
    const assertion = expect(fetchJson("/v1/questions", {}, undefined, [], 90_000)).rejects.toMatchObject({ code: "request_timeout", retryable: true });
    await vi.advanceTimersByTimeAsync(10_001);
    expect(requestSignal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(79_999);
    await assertion;
  });

  it.each([0, 120_001, Number.NaN])("rejects an unbounded or invalid request budget %s before I/O", async (budget) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(fetchJson("/v1/questions", {}, undefined, [], budget)).rejects.toBeInstanceOf(RangeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});


describe("HTTP errors with non-JSON upstream bodies", () => {
  it.each([401, 403, 503])("preserves status %s and never exposes upstream text", async (status) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("fixture upstream private body", { status })));
    await expect(getCurrentUser()).rejects.toMatchObject({ status });
  });
});

describe("R15 opt-in expected HTTP status · explicit synthetic transport", () => {
  it("rejects a 202 body even when it resembles a completed receipt", async () => { mockResponse({ generation_id: "synthetic-future-generation", completed: true }, 202); await expect(fetchJson("/api/v1/subscriptions/synthetic/generate", {}, undefined, [], 10_000, [200])).rejects.toMatchObject({ status: 502, code: "invalid_response" }); });
  it.each([200, 201, 202])("preserves legacy default acceptance of successful status %s", async (status) => { const body = { synthetic: "legacy-response" }; mockResponse(body, status); expect(await fetchJson("/synthetic-legacy")).toEqual(body); });
  it.each([200, 201])("accepts an explicitly allowed creation status %s", async (status) => { mockResponse({ synthetic: "creation" }, status); expect(await fetchJson("/api/v1/subscriptions", {}, undefined, [], 10_000, [200, 201])).toEqual({ synthetic: "creation" }); });
  it.each([401, 403])("keeps access denial %s ahead of expected-status checking", async (status) => { mockResponse({ error: { code: status === 401 ? "session_expired" : "forbidden", retryable: false } }, status); await expect(fetchJson("/api/v1/reports", {}, undefined, [], 10_000, [200])).rejects.toMatchObject({ status, code: status === 401 ? "session_expired" : "forbidden" }); });
  it("preserves parsing errors without disclosing non-JSON response content", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("synthetic-private-source", { status: 200 }))); await expect(fetchJson("/api/v1/reports", {}, undefined, [], 10_000, [200])).rejects.toMatchObject({ code: "invalid_response" }); });
});
