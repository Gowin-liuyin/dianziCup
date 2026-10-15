import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { collectSourcePage, getSourceJob } from "../../api/source-client";
import { validateSourceSubmission, type SourceJob, type SourceJobStatus, type SourceKind, type SourceSubmission } from "../../api/source-contracts";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState, ErrorPanel } from "../../components/status";
import "./sources.css";

const sourceNames: Record<SourceKind, string> = { nvd_ollama: "NVD · Ollama", vllm_vendor: "vLLM · 厂商公告" };
const jobStates: Record<SourceJobStatus, { label: string; description: string }> = {
  queued: { label: "已排队", description: "PG已保存本页任务，等待worker执行；尚不能判断来源已采集。" },
  running: { label: "本页处理中", description: "服务端记录本页正在处理。此页面没有自动轮询，请手动刷新核对。" },
  retry_wait: { label: "等待重试", description: "服务端将按任务策略重试。无需重复提交新一轮，可稍后手动刷新。" },
  succeeded: { label: "本页处理完成", description: "仅本页任务成功，后续页仍可能排队或运行；本页不能证明整个来源采完。" },
  partial: { label: "部分完成", description: "本轮页数上限已到或只完成部分处理，来源仍可能有后续页；请核对错误码和服务端游标。" },
  failed: { label: "本页失败", description: "本页未完成。核对安全错误码与运行依赖后再决定是否开始新一轮。" },
  blocked: { label: "任务已阻塞", description: "存在需要处理的前置条件，不能当作完成；核对错误码和依赖，处理后再操作。" },
  cancelled: { label: "任务已取消", description: "服务端记录该任务已取消；这不代表其他分页任务也已取消。" },
  waiting_approval: { label: "待人工确认", description: "任务正在等待批准，本页面没有批准或取消接口。" },
};

function SourceTime({ value }: { value: string | null }) {
  return value === null ? <span>未知 / 未留存</span> : <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>;
}

function failureMessage(error: ApiProblem, submit: boolean): string {
  if (error.code === "invalid_response") return submit ? "服务返回的数据格式不符合接口约定；提交结果未确认，请保留本轮请求原样重试。" : error.message;
  if (error.status === 401) return "会话已失效，请重新登录；当前客户端身份已清除，不代表服务端撤销已确认。";
  if (error.status === 403) return error.code === "csrf_rejected" ? "会话写入校验未通过；可原样重试取得新的CSRF，来源和请求键保持不变。" : "当前会话没有来源管理权限，请重新核对无租户系统管理员身份。";
  if (error.status === 404) return "任务不存在或当前会话不可查看。没有展示旧任务或历史数量。";
  if (error.status === 409) return "幂等键与已保存请求冲突。请核对任务记录；不要通过自动更换请求键绕过冲突。";
  if (error.status === 422) return submit ? "请求未通过校验，请检查带时区的过去窗口、固定来源与1至20页范围。" : "任务标识未通过校验，请输入完整UUID后重新查询。";
  if (submit) return "提交结果未确认。请求可能已入队；请保留本轮窗口和请求键原样重试，不要把网络错误当作未提交。";
  return "本次未取得PG任务状态，不能判断任务为空或已完成。恢复服务后手动刷新。";
}

function SourceJobDetails({ job }: { job: SourceJob }) {
  const state = jobStates[job.status];
  return <article className="source-job-details" aria-label="当前单页任务"><div className="source-job-state"><span className={`source-job-mark source-state-${job.status}`} aria-hidden="true" /><div><h3>{state.label}</h3><p>{state.description}</p></div></div><dl className="source-metadata"><dt>任务标识</dt><dd><code>{job.job_id}</code></dd><dt>执行尝试</dt><dd>{job.attempt_count} 次</dd><dt>创建时间</dt><dd><SourceTime value={job.created_at} /></dd><dt>结束时间</dt><dd><SourceTime value={job.finished_at} /></dd><dt>安全错误码</dt><dd><code>{job.error_code ?? "未返回错误码"}</code></dd><dt>内部结果引用</dt><dd><code>{job.result_ref ?? "尚无结果引用"}</code></dd></dl></article>;
}

function SourceAdminWorkspace() {
  const { sessionGeneration, isSessionCurrent, expireSession, state } = useAuthSession();
  const [sourceKind, setSourceKind] = useState<SourceKind>("nvd_ollama");
  const [streamKind, setStreamKind] = useState<"live" | "backfill">("live");
  const [windowEnd, setWindowEnd] = useState(() => formatShanghaiTimestamp(new Date().toISOString()));
  const [maxPages, setMaxPages] = useState("5");
  const [submission, setSubmission] = useState<SourceSubmission | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [pending, setPending] = useState<"submit" | "lookup" | null>(null);
  const [failure, setFailure] = useState<{ error: ApiProblem; submit: boolean } | null>(null);
  const [job, setJob] = useState<SourceJob | null>(null);
  const [jobId, setJobId] = useState("");
  const active = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; active.current?.abort(); };
  }, []);

  async function runRequest(kind: "submit" | "lookup", frozen?: SourceSubmission) {
    if (inFlight.current || !isSessionCurrent(sessionGeneration)) return;
    const controller = new AbortController();
    active.current = controller;
    inFlight.current = true;
    setPending(kind);
    setJob(null);
    setFailure(null);
    const current = () => mounted.current && !controller.signal.aborted && isSessionCurrent(sessionGeneration);
    try {
      const result = kind === "submit" && frozen !== undefined ? await collectSourcePage(frozen, current, controller.signal) : await getSourceJob(jobId.trim(), controller.signal);
      if (!current()) return;
      setJob(result);
      setJobId(result.job_id);
      if (kind === "submit") setAccepted(true);
    } catch (error: unknown) {
      if (!current()) return;
      const problem = publicProblem(error);
      setFailure({ error: problem, submit: kind === "submit" });
      if (problem.status === 401) expireSession(sessionGeneration);
    } finally {
      if (current()) { inFlight.current = false; setPending(null); }
    }
  }

  function submitCollection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || submission !== null) return;
    const frozen: SourceSubmission = { sourceKind, body: { window_end: windowEnd, stream_kind: streamKind, max_pages: Number(maxPages) }, idempotencyKey: `source-ui-${crypto.randomUUID()}` };
    try { validateSourceSubmission(frozen); } catch (error: unknown) { setFailure({ error: publicProblem(error), submit: true }); return; }
    setSubmission(frozen);
    setAccepted(false);
    void runRequest("submit", frozen);
  }

  function newRound() {
    if (inFlight.current) return;
    setSubmission(null);
    setAccepted(false);
    setFailure(null);
    setWindowEnd(formatShanghaiTimestamp(new Date().toISOString()));
  }

  const locked = submission !== null || pending !== null;
  return <div className="source-workspace"><div className="source-scope-note"><span className="eyebrow">FIXED SOURCES / 有界调度</span><p>仅管理两个固定公开来源。任务状态读取PG，不代表整个来源覆盖、持续在线或监控总量。</p><span className="source-mode">{state.kind === "authenticated" && state.user.data_mode === "fixture" ? "合成 / Fixture" : "真实 / Live"} · 模式来自当前会话</span></div>
    <div className="source-workspace-grid"><section className="panel source-submit-panel" aria-labelledby="source-submit-title"><div className="panel-heading"><div><p className="eyebrow">COLLECT / 固定来源</p><h2 id="source-submit-title">提交采集轮次</h2></div></div>
      <div className="source-catalog"><div><strong>NVD · Ollama</strong><p>固定Ollama关键词；每个任务处理一页。</p><code>nvd_ollama</code></div><div><strong>vLLM · 厂商公告</strong><p>固定官方仓库公开公告；服务端处理分页游标。</p><code>vllm_vendor</code></div></div>
      <form className="source-form" onSubmit={submitCollection} aria-label="固定来源采集"><label htmlFor="source-kind">固定来源<select id="source-kind" disabled={locked} value={sourceKind} onChange={(event) => { if (event.target.value === "nvd_ollama" || event.target.value === "vllm_vendor") setSourceKind(event.target.value); }}><option value="nvd_ollama">NVD · Ollama</option><option value="vllm_vendor">vLLM · 厂商公告</option></select></label><div className="source-form-row"><label htmlFor="source-stream">采集流<select id="source-stream" disabled={locked} value={streamKind} onChange={(event) => { if (event.target.value === "live" || event.target.value === "backfill") setStreamKind(event.target.value); }}><option value="live">实时流 / live</option><option value="backfill">回补流 / backfill</option></select></label><label htmlFor="source-max-pages">本轮页上限<input id="source-max-pages" type="number" min="1" max="20" step="1" disabled={locked} value={maxPages} onChange={(event) => setMaxPages(event.target.value)} required /></label></div><label htmlFor="source-window">观察窗口截止（含时区）<input id="source-window" value={windowEnd} onChange={(event) => setWindowEnd(event.target.value)} disabled={locked} required /></label><p className="source-boundary">窗口是本轮观察标识，不保证上游快照或完整时间过滤。202只表示PG受理，不表示来源采完。</p><button className="button" type="submit" disabled={locked}>{pending === "submit" ? "正在提交…" : "提交本轮采集"}</button></form>
      {submission !== null && <div className="source-frozen-request"><h3>{accepted ? "本轮已受理" : "本轮请求已冻结"}</h3><dl className="source-metadata"><dt>来源与流</dt><dd>{sourceNames[submission.sourceKind]} / {submission.body.stream_kind}</dd><dt>固定窗口</dt><dd><SourceTime value={submission.body.window_end} /></dd><dt>页上限</dt><dd>{submission.body.max_pages}</dd><dt>幂等请求键</dt><dd><code>{submission.idempotencyKey}</code></dd></dl><p>重试保留相同来源、请求体、窗口和请求键。开始新一轮后，首次提交会生成新键；上一轮结果未知时请先原样重试。</p><div className="source-actions">{!accepted && <button className="button secondary" disabled={pending !== null} onClick={() => void runRequest("submit", submission)}>原样重试本轮</button>}<button className="button secondary" disabled={pending !== null} onClick={newRound}>开始新一轮</button></div></div>}
    </section>
    <section className="panel source-query-panel" aria-labelledby="source-query-title"><div className="panel-heading"><div><p className="eyebrow">JOB / PG单页任务</p><h2 id="source-query-title">任务状态查询</h2></div><span className="small-note">手动刷新</span></div><form className="source-form" aria-label="查询单页任务" onSubmit={(event) => { event.preventDefault(); void runRequest("lookup"); }}><label htmlFor="source-job-id">任务标识<input id="source-job-id" placeholder="输入已保存的job UUID" value={jobId} onChange={(event) => setJobId(event.target.value)} disabled={pending !== null} required /></label><button className="button secondary" type="submit" disabled={pending !== null || !jobId.trim()}>{pending === "lookup" ? "正在查询…" : "查询 / 刷新任务"}</button><p className="source-boundary">保存任务标识可在返回本页后重新查询。此处没有任务历史、全来源计数或自动轮询。</p></form>
      {pending !== null && <p className="source-loading" role="status">{pending === "submit" ? "正在提交固定来源任务，等待PG回执…" : "正在读取指定任务的PG状态…"}</p>}
      {failure !== null && <ErrorPanel error={failure.error} message={failureMessage(failure.error, failure.submit)} />}
      {job !== null && <SourceJobDetails job={job} />}
      {job === null && pending === null && failure === null && <EmptyState title="尚未查询任务" description="提交一轮取得任务标识，或输入已有标识查询。尚未查询不等于没有任务。" />}
    </section></div>
  </div>;
}

/** 管理请求仅对无租户系统管理员开放，模式与权限均取服务端会话。 */
export function SourceWorkspace() {
  const { state, actionPending, error, sessionGeneration } = useAuthSession();
  if (state.kind === "loading" || actionPending) return <section className="panel"><EmptyState title="正在核对调度权限" description="身份和权限确认后才允许访问来源管理接口。" /></section>;
  if (state.kind !== "authenticated" || state.user.role !== "system_admin" || state.user.tenant_id !== null) return <section className="panel source-access-panel"><EmptyState title="没有来源调度权限" description="仅无租户的系统管理员可提交固定公开源和查询任务；此页面尚未发送来源管理请求。" />{error?.code === "session_expired" && <ErrorPanel error={error} />}<a className="button secondary" href="#session">核对会话与权限</a></section>;
  return <SourceAdminWorkspace key={`${state.user.user_id}-${state.user.permission_version}-${sessionGeneration}`} />;
}
