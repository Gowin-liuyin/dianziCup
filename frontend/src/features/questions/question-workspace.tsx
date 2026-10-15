import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { getAnswer, submitQuestion } from "../../api/question-client";
import { validateQuestionId, validateQuestionSubmission, type AnswerClaimKind, type QuestionAnswer, type QuestionSubmission } from "../../api/question-contracts";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState, ErrorPanel } from "../../components/status";
import "./questions.css";

const claimLabels: Record<AnswerClaimKind, string> = { source_fact: "来源事实", rule_result: "规则结论", project_suggestion: "项目建议" };
const freshnessLabels = { current: "当前有效", stale: "已过期，需重新核对", unknown: "时效未知" };

function failureMessage(error: ApiProblem, submitting: boolean): string {
  if (error.status === 401) return "会话已失效，请重新登录。当前回答已清除。";
  if (error.status === 403) return error.code === "csrf_rejected" ? "会话写入校验未通过；原样重试会重新取得CSRF，问题与请求键保持不变。" : "当前会话没有问答或回答查看权限，请核对团队授权。";
  if (error.status === 404) return "回答不存在，或当前会话不可查看。没有展示历史回答。";
  if (error.status === 409) {
    if (error.code === "answer_in_progress") return "同一请求仍在处理中。请稍后原样重试，不会自动发起新的生成。";
    if (error.code === "answer_failed") return "同一请求已失败。核对服务状态后再明确开始新问题。";
    return "请求键发生冲突或同一请求暂不可重放。保留原问题与请求键，不自动更换键。";
  }
  if (error.status === 422) return submitting ? "请求未通过校验。请输入一个完整事件UUID及1至4096字符问题；本轮只支持资料库单事件。" : "回答标识未通过校验，请输入完整UUID。";
  if (error.status === 429) return "问答服务当前繁忙或已达到限额。没有自动重试，请稍后再决定操作。";
  if (error.status === 503) {
    if (error.code === "question_models_not_configured") return "生成模型尚未配置，未生成回答。请联系管理员核对模型配置。";
    if (error.code === "answer_evidence_unavailable") return "当前合法证据不足，未生成确定回答。请回到事件页核对证据。";
    if (error.code === "answer_evidence_changed") return "依赖证据已变化，当前没有取得有效回答。请核对修订后明确开始新问题。";
    if (error.code === "answer_verification_failed") return "回答核验未通过，未展示未经支持的结论。";
    return "模型或证据服务暂不可用、超时或核验失败。本次没有取得有效回答。";
  }
  if (submitting) return "提交结果未确认，请保留本轮问题与请求键原样重试；网络或格式错误不能解释为未提交。";
  return error.code === "invalid_response" ? "回答格式不符合冻结合同，本次没有展示回答。" : "本次未取得回答。恢复连接后手动查询，失败不代表没有相关事实。";
}

function CompletedAnswer({ answer, eventId }: { answer: QuestionAnswer; eventId: string | null }) {
  let validEventId: string | null = null;
  try { validEventId = eventId === null ? null : validateQuestionId(eventId.trim()); } catch { validEventId = null; }
  return <article className="question-answer" aria-label="完整证据回答">
    <div className="question-answer-status"><span className="question-mode">{answer.data_mode === "fixture" ? "合成 / Fixture · 隔离数据" : "真实 / Live"}</span><span className={`question-freshness freshness-${answer.freshness}`}>{freshnessLabels[answer.freshness]}</span><strong>{answer.latency_milliseconds} 毫秒 · 完整回答耗时</strong></div>
    {answer.freshness !== "current" && <p className="question-warning" role="status">{answer.freshness === "stale" ? "这是已过期回答，不能据此确认当前结论。重新提交问题将重新核对证据。" : "服务未确认该回答的当前性，不能将未知解释为有效或无风险。"}</p>}
    <h3>完整回答</h3><p className="question-answer-text">{answer.answer_text}</p>
    {answer.claims.length === 0 && <EmptyState title="未提供关键结论" description="回答正文没有结构化结论，不能由页面补造事实。" />}
    {(["source_fact", "rule_result", "project_suggestion"] as const).map((kind) => {
      const claims = answer.claims.filter((claim) => claim.kind === kind);
      return <section className="question-claim-group" aria-label={claimLabels[kind]} key={kind}><h3>{claimLabels[kind]}</h3>{claims.length === 0 ? <p className="small-note">未提供{claimLabels[kind]}</p> : claims.map((claim, index) => <div className="question-claim" key={`${kind}-${index}`}><p>{claim.text}</p><div className="question-supports">{claim.support_ids.map((supportId, supportIndex) => <a key={`${supportId}-${supportIndex}`} href={`#citation-${supportId}`} onClick={(event) => { event.preventDefault(); document.getElementById(`citation-${supportId}`)?.focus(); document.getElementById(`citation-${supportId}`)?.scrollIntoView?.({ block: "nearest", behavior: "instant" }); }}>依据 [{answer.citations.findIndex((citation) => citation.evidence_id === supportId) + 1}]</a>)}</div></div>)}</section>;
    })}
    <section className="question-limitations" aria-labelledby="question-limitations-title"><h3 id="question-limitations-title">覆盖与限制</h3>{answer.limitations.length === 0 ? <p>服务未返回额外限制；这不等于已穷尽所有来源、版本或资产条件。</p> : <><p>本次回答存在以下覆盖边界，请与结论一起阅读。</p><ul>{answer.limitations.map((limitation, index) => <li key={index}>{limitation}</li>)}</ul></>}</section>
    <section className="question-citations" aria-labelledby="question-citations-title"><h3 id="question-citations-title">原文引用</h3><p className="small-note">引文存在不等于内容支持。打开固定修订片段，逐条核对结论。</p>{validEventId === null && <p className="small-note">此回答未返回事件标识，无法确认内部事件链接；仍可核对引文、修订标识和来源原文。</p>}{answer.citations.length === 0 && <EmptyState title="没有原文引用" description="本次未提供可追溯原文，不能据此生成来源事实。" />}{answer.citations.map((citation, index) => <article tabIndex={-1} id={`citation-${citation.evidence_id}`} className="question-citation" key={citation.evidence_id}><h4>引用 [{index + 1}] · {citation.locator}</h4><blockquote>{citation.quote}</blockquote><dl className="question-metadata"><dt>证据</dt><dd><code>{citation.evidence_id}</code></dd><dt>原文修订</dt><dd><code>{citation.revision_id}</code></dd></dl><div className="question-actions">{validEventId !== null && <a className="text-link" href={`#events/${validEventId}/evidence/${citation.evidence_id}/revision/${citation.revision_id}`}>检视固定修订证据 [{index + 1}] →</a>}{new URL(citation.source_uri).protocol === "https:" ? <a className="text-link" href={citation.source_uri} target="_blank" rel="noopener noreferrer">打开来源原文 [{index + 1}] ↗</a> : <span className="small-note">来源仅提供HTTP地址，本页不打开该外链</span>}</div></article>)}</section>
    <dl className="question-metadata question-answer-metadata"><dt>回答标识</dt><dd><code>{answer.answer_id}</code></dd><dt>开始时间</dt><dd><time dateTime={answer.started_at}>{formatShanghaiTimestamp(answer.started_at)}</time></dd><dt>完成时间</dt><dd><time dateTime={answer.completed_at}>{formatShanghaiTimestamp(answer.completed_at)}</time></dd></dl>
  </article>;
}

function AuthenticatedQuestions({ initialEventId }: { initialEventId: string }) {
  const { state, sessionGeneration, isSessionCurrent, expireSession, actionPending } = useAuthSession();
  const [eventId, setEventId] = useState(initialEventId);
  const [question, setQuestion] = useState("");
  const [answerId, setAnswerId] = useState("");
  const [submission, setSubmission] = useState<QuestionSubmission | null>(null);
  const [pending, setPending] = useState<"submit" | "lookup" | null>(null);
  const [answer, setAnswer] = useState<QuestionAnswer | null>(null);
  const [answerEventId, setAnswerEventId] = useState<string | null>(null);
  const confirmedAnswerScope = useRef<{ answerId: string; eventId: string } | null>(null);
  const [failure, setFailure] = useState<{ error: ApiProblem; submitting: boolean } | null>(null);
  const [completed, setCompleted] = useState(false);
  const active = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; active.current?.abort(); }; }, []);

  async function runRequest(kind: "submit" | "lookup", frozen?: QuestionSubmission) {
    if (inFlight.current || actionPending || !isSessionCurrent(sessionGeneration)) return;
    const controller = new AbortController();
    active.current = controller;
    inFlight.current = true;
    setPending(kind);
    setAnswer(null);
    setFailure(null);
    const current = () => mounted.current && !controller.signal.aborted && isSessionCurrent(sessionGeneration);
    try {
      const result = kind === "submit" && frozen !== undefined ? await submitQuestion(frozen, current, controller.signal) : await getAnswer(answerId.trim(), controller.signal);
      if (!current()) return;
      if (state.kind !== "authenticated" || result.data_mode !== state.user.data_mode) throw new ApiProblem(502, "invalid_response", false);
      setAnswer(result);
      setAnswerId(result.answer_id);
      if (kind === "submit" && frozen !== undefined) {
        confirmedAnswerScope.current = { answerId: result.answer_id, eventId: frozen.body.event_ids[0] };
        setCompleted(true);
      }
      setAnswerEventId(confirmedAnswerScope.current?.answerId === result.answer_id ? confirmedAnswerScope.current.eventId : null);
    } catch (error: unknown) {
      if (!current()) return;
      const problem = publicProblem(error);
      setFailure({ error: problem, submitting: kind === "submit" });
      if (problem.status === 401) expireSession(sessionGeneration);
    } finally {
      if (current()) { inFlight.current = false; setPending(null); }
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || submission !== null || actionPending || !isSessionCurrent(sessionGeneration)) return;
    const frozen: QuestionSubmission = { body: { question, mode: "library", event_ids: [eventId.trim().toLowerCase()] }, idempotencyKey: `question-ui-${crypto.randomUUID()}` };
    try { validateQuestionSubmission(frozen); } catch (error: unknown) { setAnswer(null); setFailure({ error: publicProblem(error), submitting: true }); return; }
    setSubmission(frozen);
    setCompleted(false);
    void runRequest("submit", frozen);
  }
  function startNewQuestion() {
    if (inFlight.current || actionPending || !isSessionCurrent(sessionGeneration)) return;
    setSubmission(null); setCompleted(false); setAnswer(null); setFailure(null); setQuestion("");
  }

  const locked = submission !== null || pending !== null || actionPending;
  return <div className="question-workspace"><div className="question-scope"><p className="eyebrow">LIBRARY / 单事件证据研究</p><p>基于当前有权查看的事件资料提问。此次只支持资料库单事件，不支持资产研判、历史时间或自动调查。</p><span className="question-mode">当前会话：{state.kind === "authenticated" && state.user.data_mode === "fixture" ? "合成 / Fixture · 隔离数据" : "真实 / Live"}</span></div><div className="question-workspace-grid">
    <section className="panel question-input-panel" aria-labelledby="question-input-title"><div className="panel-heading"><div><p className="eyebrow">ASK / 从证据开始</p><h2 id="question-input-title">提出问题</h2></div><span className="small-note">library</span></div><form className="question-form" aria-label="单事件问答" onSubmit={submit}><label htmlFor="question-event-id">事件标识<input id="question-event-id" value={eventId} disabled={locked} onChange={(event) => setEventId(event.target.value)} placeholder="一个完整事件UUID" required /></label><label htmlFor="question-text">你的问题<textarea id="question-text" value={question} disabled={locked} onChange={(event) => setQuestion(event.target.value)} rows={6} required placeholder="描述你需要核对的事实、机制或修复依据" /></label><p className="small-note">{[...question].length} / 4096 字符。未知与缺失会明确显示，页面不会补造答案。</p><button className="button" disabled={locked} type="submit">{pending === "submit" ? "等待完整回答…" : "提交问题"}</button></form>
      {submission !== null && <div className="question-frozen"><h3>{completed ? "本轮已取得回答" : "本轮请求已冻结"}</h3><dl className="question-metadata"><dt>事件</dt><dd><code>{submission.body.event_ids[0]}</code></dd><dt>请求键</dt><dd><code>{submission.idempotencyKey}</code></dd></dl><p className="small-note">结果未知时保留相同问题、事件和请求键。原样重试沿用同一业务请求；开始新问题后首次提交才生成新键。</p><div className="question-actions">{!completed && <button className="button secondary" disabled={pending !== null || actionPending} onClick={() => void runRequest("submit", submission)}>原样重试本轮</button>}<button className="button secondary" disabled={pending !== null || actionPending} onClick={startNewQuestion}>开始新问题</button></div></div>}
      <form className="question-form question-lookup" aria-label="查询已保存回答" onSubmit={(event) => { event.preventDefault(); void runRequest("lookup"); }}><h3>读取已保存回答</h3><label htmlFor="question-answer-id">回答标识<input id="question-answer-id" value={answerId} disabled={pending !== null || actionPending} onChange={(event) => setAnswerId(event.target.value)} placeholder="保存的answer UUID" required /></label><button className="button secondary" type="submit" disabled={pending !== null || actionPending || !answerId.trim()}>查询 / 刷新回答</button><p className="small-note">服务端重新检查所有权与当前性。问题与回答正文只在本页内存中保留；返回后可凭回答标识查询。</p></form>
    </section>
    <section className="panel question-result-panel" aria-labelledby="question-result-title"><div className="panel-heading"><div><p className="eyebrow">ANSWER / 结论与依据</p><h2 id="question-result-title">回答与证据</h2></div><span className="small-note">完整完成后显示</span></div>{pending !== null && <p className="question-loading" role="status">{pending === "submit" ? "正在提交问题并等待完整回答。未返回结果前不能判断结论。" : "正在重新读取回答及其当前性…"}</p>}{failure !== null && <ErrorPanel error={failure.error} message={failureMessage(failure.error, failure.submitting)} />}{answer !== null && <CompletedAnswer answer={answer} eventId={answerEventId} />}{answer === null && pending === null && failure === null && <EmptyState title="尚未提出问题" description="提交问题或查询已保存回答后，这里展示服务端确认的结论、限制和原文引用。" />}</section>
  </div></div>;
}

/** 登录上下文是唯一身份来源；会话切换由App代次key卸载全部私有问答状态。 */
export function QuestionWorkspace({ eventId = "" }: { eventId?: string }) {
  const { state, actionPending, error: sessionError } = useAuthSession();
  if (state.kind === "loading") return <section className="panel"><p className="loading-state" role="status">正在恢复问答会话…</p></section>;
  if (state.kind !== "authenticated") return <section className="panel question-access">{sessionError !== null && <ErrorPanel error={sessionError} />}<EmptyState title="登录后使用证据问答" description="当前没有有效会话，未读取事件或回答。" /><a className="button secondary" href="#session">前往登录</a></section>;
  if (!state.user.permissions.some((permission) => permission === "read:public" || permission === "read:tenant")) return <section className="panel"><EmptyState title="没有问答访问权限" description="当前会话没有资料读取授权，请联系团队管理员。" /></section>;
  if (actionPending) return <section className="panel"><p className="loading-state" role="status">正在核对会话，请稍后操作…</p></section>;
  return <AuthenticatedQuestions initialEventId={eventId} />;
}
