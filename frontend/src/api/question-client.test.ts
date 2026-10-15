import { afterEach, describe, expect, it, vi } from "vitest";
import { questionAnswerFixture, questionFixtureIds as ids } from "../features/questions/question.fixture";
import { getAnswer, submitQuestion } from "./question-client";
import type { QuestionSubmission } from "./question-contracts";

const submission: QuestionSubmission = { body: { question: "隔离问题", mode: "library", event_ids: [ids.event] }, idempotencyKey: "isolated-key" };
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
describe("question client — isolated fixture, not live", () => {
  it("allows a bounded cold question to complete after the normal ten-second HTTP budget", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => {
      if (String(input).endsWith("csrf")) return response({ csrf_token: "isolated-token", header_name: "X-CSRF-Token" });
      return new Promise<Response>((resolve, reject) => {
        const timer = setTimeout(() => resolve(response(questionAnswerFixture())), 12_000);
        options.signal?.addEventListener("abort", () => { clearTimeout(timer); reject(new DOMException("fixture abort", "AbortError")); }, { once: true });
      });
    }));
    const request = submitQuestion(submission, () => true);
    const assertion = expect(request).resolves.toMatchObject({ answer_id: ids.answer });
    await vi.advanceTimersByTimeAsync(12_000);
    await assertion;
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it("sends exact frozen body, cookie credentials, CSRF and request key", async () => {
    const calls: { path: string; options: RequestInit }[] = [];
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, options: RequestInit = {}) => { calls.push({ path: String(input), options }); return response(String(input).endsWith("csrf") ? { csrf_token: "isolated-token", header_name: "X-CSRF-Token" } : questionAnswerFixture()); }));
    await submitQuestion(submission, () => true);
    expect(calls.map((call) => call.path)).toEqual(["/v1/auth/csrf", "/v1/questions"]);
    expect(calls[1]?.options.credentials).toBe("include");
    expect(calls[1]?.options.body).toBe(JSON.stringify({ question: "隔离问题", mode: "library", event_ids: [ids.event] }));
    expect(new Headers(calls[1]?.options.headers).get("X-CSRF-Token")).toBe("isolated-token");
    expect(new Headers(calls[1]?.options.headers).get("Idempotency-Key")).toBe("isolated-key");
  });
  it("fences late CSRF when session changes and makes no paid write", async () => {
    let current = true;
    const fetchMock = vi.fn(async () => { current = false; return response({ csrf_token: "isolated-token", header_name: "X-CSRF-Token" }); });
    vi.stubGlobal("fetch", fetchMock);
    await expect(submitQuestion(submission, () => current)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("cancels before acquiring CSRF", async () => {
    const fetchMock = vi.fn(); vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController(); controller.abort();
    await expect(submitQuestion(submission, () => true, controller.signal)).rejects.toMatchObject({ code: "request_canceled" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([401, 403, 404, 409, 422, 429, 503])("preserves HTTP %s errors and never retries", async (status) => {
    const fetchMock = vi.fn(async () => response({ type: "about:blank", title: "isolated failure", status, error: { code: "insufficient_evidence", retryable: true } }, status)); vi.stubGlobal("fetch", fetchMock);
    await expect(getAnswer(ids.answer)).rejects.toMatchObject({ status });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("rejects a different answer or malformed identifier", async () => {
    const fetchMock = vi.fn(async () => response({ ...questionAnswerFixture(), answer_id: ids.other })); vi.stubGlobal("fetch", fetchMock);
    await expect(getAnswer(ids.answer)).rejects.toMatchObject({ code: "invalid_response" });
    await expect(getAnswer("../private")).rejects.toMatchObject({ status: 422 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
