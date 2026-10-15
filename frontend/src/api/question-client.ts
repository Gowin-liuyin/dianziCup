import { ApiProblem, fetchJson, getCsrfToken } from "./client";
import { parseQuestionAnswer, validateQuestionId, validateQuestionSubmission, type QuestionAnswer, type QuestionSubmission } from "./question-contracts";

/** 序列化后保留原body/key；CSRF等待后复核会话，写入不自动重试。 */
export async function submitQuestion(submission: QuestionSubmission, isCurrent: () => boolean, signal?: AbortSignal): Promise<QuestionAnswer> {
  validateQuestionSubmission(submission);
  const body = JSON.stringify(submission.body);
  const idempotencyKey = submission.idempotencyKey;
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  const csrf = await getCsrfToken(signal);
  if (signal?.aborted || !isCurrent()) throw new ApiProblem(0, "request_canceled", false);
  return parseQuestionAnswer(await fetchJson("/v1/questions", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": idempotencyKey }, body }, signal));
}

export async function getAnswer(answerId: string, signal?: AbortSignal): Promise<QuestionAnswer> {
  const id = validateQuestionId(answerId);
  const answer = parseQuestionAnswer(await fetchJson(`/v1/answers/${id}`, {}, signal));
  if (answer.answer_id !== id) throw new ApiProblem(502, "invalid_response", true);
  return answer;
}
