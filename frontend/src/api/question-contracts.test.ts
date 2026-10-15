import { describe, expect, it } from "vitest";
import { questionAnswerFixture, questionFixtureIds as ids } from "../features/questions/question.fixture";
import { parseQuestionAnswer, readQuestionRoute, validateQuestionSubmission, type QuestionSubmission } from "./question-contracts";

describe("question contract — isolated fixture, not live", () => {
  it("preserves frozen fields, complete milliseconds and separate claim kinds", () => {
    const answer = parseQuestionAnswer(questionAnswerFixture());
    expect(answer.latency_milliseconds).toBe(1234);
    expect(answer.claims.map((claim) => claim.kind)).toEqual(["source_fact", "rule_result", "project_suggestion"]);
    expect(answer.citations[0]?.revision_id).toBe(ids.revision);
  });
  it.each([null, [], {}, { ...questionAnswerFixture(), latency_ms: 1234 }, { ...questionAnswerFixture(), kind: "task" }, { ...questionAnswerFixture(), claims: null }, { ...questionAnswerFixture(), citations: null }, { ...questionAnswerFixture(), limitations: null }, { ...questionAnswerFixture(), data_mode: "demo" }, { ...questionAnswerFixture(), freshness: "valid" }, { ...questionAnswerFixture(), latency_milliseconds: -1 }, { ...questionAnswerFixture(), latency_milliseconds: 1.5 }, { ...questionAnswerFixture(), latency_milliseconds: Number.MAX_SAFE_INTEGER + 1 }, { ...questionAnswerFixture(), started_at: "2026-02-30T07:00:00Z" }, { ...questionAnswerFixture(), completed_at: "2026-10-14T07:00:00Z" }, { ...questionAnswerFixture(), answer_text: " " }, { ...questionAnswerFixture(), claims: [{ text: "unsupported", kind: "source_fact", support_ids: [] }] }, { ...questionAnswerFixture(), claims: [{ text: "invented", kind: "rule_result", support_ids: [ids.other] }] }, { ...questionAnswerFixture(), citations: [...questionAnswerFixture().citations, ...questionAnswerFixture().citations] }, { ...questionAnswerFixture(), limitations: Array.from({ length: 101 }, () => "limit") }])("rejects incomplete, mismatched or forged wire %#", (wire) => expect(() => parseQuestionAnswer(wire)).toThrow(/格式/));
  it.each(["javascript:alert(1)", "data:text/html,test", "https://user:password@example.test/", "https://example.test/\\evil", "https://example.test/\nmalicious"])("rejects unsafe source URI %s", (sourceUri) => expect(() => parseQuestionAnswer({ ...questionAnswerFixture(), citations: [{ ...questionAnswerFixture().citations[0], source_uri: sourceUri }] })).toThrow(/格式/));
  it("accepts valid Unicode and counts codepoints, while preserving raw question", () => {
    const submission: QuestionSubmission = { body: { question: "😀".repeat(4096), mode: "library", event_ids: [ids.event] }, idempotencyKey: "isolated-key" };
    expect(() => validateQuestionSubmission(submission)).not.toThrow();
    expect(() => validateQuestionSubmission({ ...submission, body: { ...submission.body, question: "😀".repeat(4097) } })).toThrow(/校验/);
  });
  it.each(["", "  ", "a\0b", "\ud800"])("rejects invalid input without relying on server: %#", (question) => expect(() => validateQuestionSubmission({ body: { question, mode: "library", event_ids: [ids.event] }, idempotencyKey: "isolated-key" })).toThrow(/校验/));
  it("parses only bounded event routes and normalizes identifiers", () => {
    expect(readQuestionRoute(`#questions/${ids.event.toUpperCase()}`)).toEqual({ eventId: ids.event });
    expect(readQuestionRoute("#questions/invalid")).toBeNull();
    expect(readQuestionRoute(`#questions/${ids.event}/extra`)).toBeNull();
  });
});
