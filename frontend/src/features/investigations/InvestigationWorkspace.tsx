import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem, type CurrentUser } from "../../api/client";
import { getEvidence } from "../../api/knowledge-client";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState, ErrorPanel } from "../../components/status";
import { getAssetSnapshot } from "../assets/asset-client";
import { AssetResponseScopeMismatch } from "../assets/asset-contracts";
import { cancelInvestigation, createInvestigation, getInvestigation, getInvestigationOperations } from "./investigation-client";
import { investigationNeedsPolling, validateInvestigationId, validateInvestigationSubmission, type InvestigationOperationPage, type InvestigationResponse, type InvestigationStrategy, type InvestigationSubmission } from "./investigation-contracts";
import "./investigations.css";

export interface InvestigationWorkspaceProps {
  user: CurrentUser | null; authScope: string; isCurrent: () => boolean;
  onFailure?: (error: ApiProblem) => void; onOpenEvent?: (eventId: string, evidenceId?: string) => void;
  onOpenEvidence?: (eventId: string, evidenceId: string, revisionId: string) => void;
  initialJobId?: string; initialEventId?: string;
}
const statusLabels: Record<string, string> = { queued: "已排队", running: "运行中", retry_wait: "等待重试", waiting_approval: "待人工确认", succeeded: "已完成", partial: "部分完成", failed: "失败", cancelled: "已取消", blocked: "受阻", stale: "已过期", reserved: "已预留，结果未知", not_configured: "未配置", skipped: "已跳过" };
const claimLabels = { source_fact: "来源事实", rule_result: "规则结论", project_suggestion: "项目建议" };
const MAX_AUTOMATIC_READS = 30;
const MAX_LOADED_OPERATIONS = 100;

function InvestigationStatus({ status }: { status: string }) {
  return <span className={`status-badge investigation-status status-${status}`}><span className="status-mark" aria-hidden="true" />{statusLabels[status] ?? `未知状态：${status}`}</span>;
}
function failureMessage(error: ApiProblem, action: string): string {
  if (error.status === 401) return "会话已失效，调查内容已清除。请重新登录。";
  if (error.status === 403) return error.code === "csrf_rejected" ? "写入的 Origin 或 CSRF 校验未通过。原样重试会重新取得会话 CSRF；请求键保持不变。" : "当前会话缺少此操作权限，或调查创建时的授权已变化。请核对授权。";
  if (error.status === 404) return "任务或输入不存在，或当前会话无权查看。此状态不能区分对象是否存在。";
  if (error.status === 409) return error.code === "workflow_changed" ? "调查的输入或绑定已变化，不能继续使用当前结果。请核对后明确开始新调查。" : "相同请求键与服务端请求发生冲突。保留本轮输入与请求键，不会自动更换键重试。";
  if (error.status === 422) return "输入未通过合同校验。事件、任务、资产及快照需完整 UUID；证据需成对填写 ID 与修订，最多 8 条。";
  if (error.status === 503) return "调查服务或依赖暂不可用。本次没有确认任务状态；核对服务后手动刷新。";
  if (error.code === "invalid_response") return "服务返回的数据不符合冻结合同，本次没有展示或沿用调查结果。";
  return action === "submit" ? "提交结果未确认。请保留相同输入与请求键原样重试；网络失败不能解释为未创建任务。" : "本次读取或取消结果未确认。请手动查询原任务，未知不等于已取消或已完成。";
}
function jobResultMessage(job: InvestigationResponse): string {
  if (job.result?.status === "stale") return "调查依赖已过期。以下内容仅供历史核查，不能确认当前结论。";
  if (job.status === "partial" || job.result?.status === "partial") return "本次调查仅部分完成。请一并阅读停止原因、缺失要求和未配置职责。";
  if (job.status === "waiting_approval" || job.result?.status === "waiting_approval") return "调查正在等待人工确认。本页未提供审批接口，不会自动继续执行。";
  if (job.status === "cancelled") return "服务端已确认任务取消。取消前的记录保留，不推断外部调用是否已产生结果。";
  if (job.status === "blocked") return "任务受阻。请核对服务端错误标识与依赖；不能将受阻解释为安全或无影响。";
  if (job.status === "failed" || job.result?.status === "failed") return "调查失败。已记录的操作不代表已取得完整、有效结论。";
  if (investigationNeedsPolling(job)) return "调查尚未完成；下方若有中间记录，也不能作为完整调查结果。";
  return job.result === null ? "尚未返回调查结果。等待状态不代表已取得证据或结论。" : "结论与引文按服务端记录展示。引文存在仍需核对其支持关系。";
}

function AuthorizedInvestigationWorkspace({ user, authScope, isCurrent, onFailure, onOpenEvent, onOpenEvidence, initialJobId = "", initialEventId = "" }: InvestigationWorkspaceProps & { user: CurrentUser }) {
  const [eventId, setEventId] = useState(initialEventId);
  const [question, setQuestion] = useState("");
  const [strategy, setStrategy] = useState<InvestigationStrategy>("B2b");
  const [assetId, setAssetId] = useState("");
  const [snapshotId, setSnapshotId] = useState("");
  const [references, setReferences] = useState<{ evidenceId: string; revisionId: string }[]>([]);
  const [submission, setSubmission] = useState<InvestigationSubmission | null>(null);
  const [jobIdInput, setJobIdInput] = useState(initialJobId);
  const [selection, setSelection] = useState<{ jobId: string; revision: number } | null>(initialJobId ? { jobId: initialJobId, revision: 0 } : null);
  const [job, setJob] = useState<InvestigationResponse | null>(null);
  const [jobPending, setJobPending] = useState(false);
  const [mutation, setMutation] = useState<"submit" | "cancel" | null>(null);
  const [failure, setFailure] = useState<{ error: ApiProblem; action: string } | null>(null);
  const [denied, setDenied] = useState<ApiProblem | null>(null);
  const [pollingStopped, setPollingStopped] = useState(false);
  const [operations, setOperations] = useState<InvestigationOperationPage | null>(null);
  const [operationsPending, setOperationsPending] = useState(false);
  const [operationsError, setOperationsError] = useState<ApiProblem | null>(null);
  const [operationRequest, setOperationRequest] = useState<{ cursor: string | null; revision: number }>({ cursor: null, revision: 0 });
  const [evidencePending, setEvidencePending] = useState<string | null>(null);
  const [evidenceError, setEvidenceError] = useState<ApiProblem | null>(null);
  const [evidenceRevisionChanged, setEvidenceRevisionChanged] = useState(false);
  const mounted = useRef(true), invalidated = useRef(false), mutationLocked = useRef(false);
  const reading = useRef<AbortController | null>(null), writing = useRef<AbortController | null>(null), evidenceReading = useRef<AbortController | null>(null);
  const binding = useRef<{ jobId: string; eventId: string; authScope: string; evidenceRevisions: ReadonlyMap<string, string> } | null>(null);
  const currentJobId = useRef<string | null>(initialJobId.toLowerCase() || null);
  const current = useCallback(() => mounted.current && !invalidated.current && isCurrent(), [isCurrent]);
  const failed = useCallback((error: ApiProblem) => {
    if (error.status === 401 || (error.status === 403 && error.code !== "csrf_rejected") || error instanceof AssetResponseScopeMismatch) {
      invalidated.current = true; reading.current?.abort(); writing.current?.abort(); evidenceReading.current?.abort();
      setDenied(error); setJob(null); setOperations(null); binding.current = null; currentJobId.current = null;
    }
    onFailure?.(error);
  }, [onFailure]);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; reading.current?.abort(); writing.current?.abort(); evidenceReading.current?.abort(); };
  }, []);

  useEffect(() => {
    const controller = new AbortController(); reading.current = controller;
    let timeout: number | undefined, reads = 0;
    setJob(null); setOperations(null); setPollingStopped(false); setEvidenceError(null); setEvidenceRevisionChanged(false);
    evidenceReading.current?.abort(); setEvidencePending(null);
    if (selection === null || !current()) { setJobPending(false); return () => controller.abort(); }
    const selected = selection;
    async function readJob() {
      if (controller.signal.aborted || !current()) return;
      setJobPending(true);
      try {
        const result = await getInvestigation(selected.jobId, controller.signal);
        if (controller.signal.aborted || !current()) return;
        if (result.result !== null && result.result.data_mode !== user.data_mode) throw new ApiProblem(502, "invalid_response", false);
        setJob(result); setOperationRequest((previous) => ({ cursor: null, revision: previous.revision + 1 })); reads += 1;
        if (investigationNeedsPolling(result)) {
          if (reads < MAX_AUTOMATIC_READS) timeout = window.setTimeout(() => void readJob(), 4000);
          else setPollingStopped(true);
        }
      } catch (error: unknown) {
        if (controller.signal.aborted || !current()) return;
        const problem = publicProblem(error); currentJobId.current = null; evidenceReading.current?.abort(); setJob(null); setOperations(null); setFailure({ error: problem, action: "lookup" }); failed(problem);
      } finally { if (!controller.signal.aborted && current()) setJobPending(false); }
    }
    void readJob();
    return () => { controller.abort(); if (timeout !== undefined) window.clearTimeout(timeout); };
  }, [selection, current, failed, user.data_mode]);

  const operationJobId = job?.job_id ?? null;
  useEffect(() => {
    const controller = new AbortController();
    setOperationsError(null);
    if (operationRequest.cursor === null) setOperations(null);
    if (operationJobId === null || !current()) { setOperationsPending(false); return () => controller.abort(); }
    const selectedJobId = operationJobId;
    setOperationsPending(true);
    void getInvestigationOperations(selectedJobId, operationRequest.cursor, controller.signal).then((page) => {
      if (controller.signal.aborted || !current()) return;
      setOperations((previous) => ({ items: operationRequest.cursor === null ? page.items : [...(previous?.items ?? []), ...page.items.filter((item) => !previous?.items.some((saved) => saved.operation_key === item.operation_key))], next_cursor: page.next_cursor }));
    }).catch((error: unknown) => {
      if (controller.signal.aborted || !current()) return;
      const problem = publicProblem(error); setOperationsError(problem); failed(problem);
    }).finally(() => { if (!controller.signal.aborted && current()) setOperationsPending(false); });
    return () => controller.abort();
  }, [operationJobId, operationRequest, current, failed]);

  function selectJob(id: string) {
    if (mutationLocked.current || !current()) return;
    try {
      const validated = validateInvestigationId(id.trim());
      currentJobId.current = validated; evidenceReading.current?.abort(); setEvidencePending(null);
      setJob(null); setOperations(null); setFailure(null); setOperationRequest({ cursor: null, revision: 0 });
      setSelection((previous) => ({ jobId: validated, revision: (previous?.revision ?? 0) + 1 }));
    } catch (error: unknown) { currentJobId.current = null; evidenceReading.current?.abort(); setJob(null); setOperations(null); setFailure({ error: publicProblem(error), action: "lookup" }); setSelection(null); }
  }
  async function submitFrozen(frozen: InvestigationSubmission) {
    if (mutationLocked.current || !current()) return;
    mutationLocked.current = true;
    reading.current?.abort(); evidenceReading.current?.abort(); currentJobId.current = null; setSelection(null); setJob(null); setOperations(null); setFailure(null); setMutation("submit");
    const controller = new AbortController(); writing.current = controller;
    const requestCurrent = () => !controller.signal.aborted && current();
    try {
      if (frozen.body.asset_id !== null && frozen.body.asset_snapshot_id !== null) {
        if (user.tenant_id === null || !user.permissions.includes("read:asset")) throw new ApiProblem(403, "permission_denied", false);
        await getAssetSnapshot(user.tenant_id, frozen.body.asset_id, frozen.body.asset_snapshot_id, controller.signal);
      }
      if (!requestCurrent()) return;
      const result = await createInvestigation(frozen, controller.signal, requestCurrent);
      if (!requestCurrent()) return;
      if (result.result !== null && result.result.data_mode !== user.data_mode) throw new ApiProblem(502, "invalid_response", false);
      binding.current = { jobId: result.job_id, eventId: frozen.body.event_id, authScope, evidenceRevisions: new Map(frozen.body.evidence_refs.map((reference) => [reference.evidence_id, reference.revision_id])) };
      currentJobId.current = result.job_id;
      setJobIdInput(result.job_id); setOperationRequest({ cursor: null, revision: 0 }); setSelection({ jobId: result.job_id, revision: 0 });
    } catch (error: unknown) {
      if (!requestCurrent()) return;
      const problem = publicProblem(error); setFailure({ error: problem, action: "submit" }); failed(problem);
    } finally { mutationLocked.current = false; if (requestCurrent()) setMutation(null); }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submission !== null || mutationLocked.current || !current()) return;
    const normalizedEventId = eventId.trim().toLowerCase();
    const frozen: InvestigationSubmission = { body: { question, event_id: normalizedEventId, evidence_refs: references.map((reference) => ({ event_id: normalizedEventId, evidence_id: reference.evidenceId.trim().toLowerCase(), revision_id: reference.revisionId.trim().toLowerCase() })), strategy, asset_id: assetId.trim() ? assetId.trim().toLowerCase() : null, asset_snapshot_id: snapshotId.trim() ? snapshotId.trim().toLowerCase() : null, version_comparison: null }, idempotencyKey: `investigation-ui-${crypto.randomUUID()}` };
    try { validateInvestigationSubmission(frozen); } catch (error: unknown) { setFailure({ error: publicProblem(error), action: "submit" }); return; }
    setSubmission(frozen); void submitFrozen(frozen);
  }
  async function cancel() {
    if (job === null || mutationLocked.current || !current() || !user.permissions.includes("write:asset")) return;
    mutationLocked.current = true; reading.current?.abort(); setJobPending(false); setMutation("cancel"); setFailure(null);
    const selectedJobId = job.job_id, controller = new AbortController(); writing.current = controller;
    const requestCurrent = () => !controller.signal.aborted && current();
    try {
      const result = await cancelInvestigation(selectedJobId, controller.signal, requestCurrent);
      if (!requestCurrent()) return;
      if (result.result !== null && result.result.data_mode !== user.data_mode) throw new ApiProblem(502, "invalid_response", false);
      setJob(result); setSelection((previous) => ({ jobId: selectedJobId, revision: (previous?.revision ?? 0) + 1 }));
    } catch (error: unknown) {
      if (!requestCurrent()) return;
      const problem = publicProblem(error); currentJobId.current = null; evidenceReading.current?.abort(); setJob(null); setOperations(null); setFailure({ error: problem, action: "cancel" }); failed(problem);
    } finally { mutationLocked.current = false; if (requestCurrent()) setMutation(null); }
  }
  async function openEvidence(evidenceId: string) {
    if (job === null || !current()) return;
    const eventBinding = binding.current;
    if (eventBinding === null || eventBinding.authScope !== authScope || eventBinding.jobId !== job.job_id || currentJobId.current !== job.job_id) return;
    if (!job.result?.evidence_ids.includes(evidenceId) && !job.result?.answer?.citations.some((citation) => citation.evidence_id === evidenceId)) return;
    const expectedRevisionId = eventBinding.evidenceRevisions.get(evidenceId);
    evidenceReading.current?.abort();
    const controller = new AbortController(); evidenceReading.current = controller;
    setEvidencePending(evidenceId); setEvidenceError(null); setEvidenceRevisionChanged(false);
    try {
      const evidence = await getEvidence(evidenceId, null, controller.signal);
      if (controller.signal.aborted || !current() || binding.current !== eventBinding || currentJobId.current !== eventBinding.jobId || eventBinding.authScope !== authScope) return;
      if (evidence.data_mode !== user.data_mode || evidence.span_id.toLowerCase() !== evidenceId) throw new ApiProblem(502, "invalid_response", false);
      if (expectedRevisionId !== undefined && evidence.revision_id.toLowerCase() !== expectedRevisionId) {
        setEvidenceRevisionChanged(true);
        throw new ApiProblem(502, "invalid_response", false);
      }
      if (evidence.source_uri !== null) {
        const source = new URL(evidence.source_uri);
        if (/[\s\\]/u.test(evidence.source_uri) || source.username || source.password || !["https:", "http:"].includes(source.protocol)) throw new ApiProblem(502, "invalid_response", false);
      }
      if (onOpenEvidence !== undefined) onOpenEvidence(eventBinding.eventId, evidence.span_id, evidence.revision_id);
      else onOpenEvent?.(eventBinding.eventId, evidence.span_id);
    } catch (error: unknown) {
      if (controller.signal.aborted || !current()) return;
      const problem = publicProblem(error); setEvidenceError(problem); failed(problem);
    } finally { if (!controller.signal.aborted && current()) setEvidencePending(null); }
  }
  function startNew() {
    if (mutationLocked.current || !current()) return;
    reading.current?.abort(); evidenceReading.current?.abort(); binding.current = null; currentJobId.current = null;
    setSelection(null); setSubmission(null); setQuestion(""); setJobIdInput(""); setJob(null); setOperations(null); setFailure(null); setOperationRequest({ cursor: null, revision: 0 });
  }
  if (denied !== null) return <section className="panel investigation-workspace"><ErrorPanel error={denied} message={failureMessage(denied, "lookup")} /><a className="button secondary" href="#session">核对会话与授权</a></section>;
  const locked = submission !== null || mutation !== null;
  const canReadAsset = user.tenant_id !== null && user.permissions.includes("read:asset");
  const canOpenEvidence = job !== null && binding.current?.jobId === job.job_id && binding.current.authScope === authScope && currentJobId.current === job.job_id && (onOpenEvidence !== undefined || onOpenEvent !== undefined);
  const result = job?.result ?? null;
  const canCancel = job !== null && ["queued", "running", "retry_wait", "waiting_approval"].includes(job.status);
  return <div className="investigation-workspace">
    <div className="investigation-intro"><div><p className="eyebrow">INVESTIGATE / 证据驱动</p><p>固定事件与可选资产快照，读取实际调查结果和操作记录。未知、缺证与停止原因保留。</p></div><span className="investigation-mode">{user.data_mode === "fixture" ? "显式 Fixture · 非 live" : "当前认证 API"}</span></div>
    <div className="investigation-grid">
      <section className="panel" aria-labelledby="investigation-input-title"><div className="panel-heading"><div><p className="eyebrow">INPUT / 冻结范围</p><h2 id="investigation-input-title">发起调查</h2></div></div>
        <form className="investigation-form" aria-label="调查输入" onSubmit={submit}>
          <label>事件标识<input value={eventId} disabled={locked} onChange={(event) => setEventId(event.target.value)} required placeholder="完整事件 UUID" /></label>
          <label>调查问题<textarea value={question} disabled={locked} onChange={(event) => setQuestion(event.target.value)} required rows={5} placeholder="描述需要核对的事实、支持证据与条件" /></label>
          <p className="small-note">{[...question].length} / 4096 字符；预算与权限由服务端控制。</p>
          <label>调查策略<select value={strategy} disabled={locked} onChange={(event) => { const value = event.target.value; if (value === "B2" || value === "B2b" || value === "B3") setStrategy(value); }}><option value="B2b">B2b · 缺口调查</option><option value="B2">B2 · 固定流程</option><option value="B3">B3 · 动态调度</option></select></label>
          <fieldset disabled={locked || !canReadAsset}><legend>可选资产输入</legend><label>资产标识<input value={assetId} onChange={(event) => setAssetId(event.target.value)} placeholder="asset UUID" /></label><label>资产快照标识<input value={snapshotId} onChange={(event) => setSnapshotId(event.target.value)} placeholder="固定 snapshot UUID" /></label></fieldset>
          <p className="small-note">{canReadAsset ? "资产与快照需同时填写；提交前复用授权快照接口核对绑定，服务端最终检查当前性。" : "当前会话无明确租户或 read:asset，只能提交不含资产的调查。"}</p>
          <fieldset disabled={locked}><legend>固定证据 · {references.length} / 8</legend>{references.map((reference, index) => <div className="investigation-reference" key={index}><label>证据 {index + 1} 标识<input value={reference.evidenceId} onChange={(event) => setReferences((previous) => previous.map((item, position) => position === index ? { ...item, evidenceId: event.target.value } : item))} required /></label><label>证据 {index + 1} 修订标识<input value={reference.revisionId} onChange={(event) => setReferences((previous) => previous.map((item, position) => position === index ? { ...item, revisionId: event.target.value } : item))} required /></label><button className="button secondary" type="button" onClick={() => setReferences((previous) => previous.filter((_, position) => position !== index))}>移除证据 {index + 1}</button></div>)}<button type="button" className="button secondary" disabled={locked || references.length >= 8} onClick={() => setReferences((previous) => [...previous, { evidenceId: "", revisionId: "" }])}>添加固定证据</button></fieldset>
          <button className="button" type="submit" disabled={locked}>{mutation === "submit" ? "正在提交调查…" : "提交调查"}</button>
        </form>
        {submission !== null && <div className="investigation-frozen"><h3>本轮请求已冻结</h3><code>{submission.idempotencyKey}</code><p className="small-note">提交结果未知时原样重试同一请求。开始新调查才生成新键；正文仅保留在当前页内存。</p><div className="investigation-actions">{binding.current === null && <button className="button secondary" disabled={mutation !== null} onClick={() => void submitFrozen(submission)}>原样重试本轮</button>}<button className="button secondary" disabled={mutation !== null} onClick={startNew}>开始新调查</button></div></div>}
        <form className="investigation-form investigation-lookup" aria-label="恢复调查任务" onSubmit={(event) => { event.preventDefault(); selectJob(jobIdInput); }}><h3>恢复 / 查询任务</h3><label>任务标识<input value={jobIdInput} disabled={mutation !== null} onChange={(event) => setJobIdInput(event.target.value)} required placeholder="保存的 job UUID" /></label><button className="button secondary" disabled={mutation !== null || !jobIdInput.trim()} type="submit">查询 / 刷新任务</button><p className="small-note">只查询当前会话拥有且有权访问的调查。请保存 UUID；页面刷新后可重新读取，不在浏览器存储保存正文。</p></form>
      </section>
      <div className="investigation-results">
        <section className="panel" aria-labelledby="investigation-result-title"><div className="panel-heading"><div><p className="eyebrow">RESULT / 服务端状态</p><h2 id="investigation-result-title">调查结果</h2></div>{job !== null && <InvestigationStatus status={job.status} />}</div>
          {mutation !== null && <p className="investigation-notice" role="status">{mutation === "submit" ? "等待服务确认接收。未返回 UUID 前提交结果未知。" : "正在请求取消。服务确认前不显示已取消。"}</p>}
          {jobPending && <p className="investigation-notice" role="status">正在读取任务状态…</p>}
          {failure !== null && <ErrorPanel error={failure.error} message={failureMessage(failure.error, failure.action)} />}
          {job === null && failure === null && mutation === null && !jobPending && <EmptyState title="尚未取得调查任务" description="提交调查或凭任务 UUID 恢复后，展示服务端状态、结论和调用记录。" />}
          {job !== null && <article className="investigation-result"><div className="investigation-job-line"><code>{job.job_id}</code><a className="text-link" href={`#investigations/${job.job_id}`}>任务链接 →</a></div><p className="investigation-notice" role="status">{jobResultMessage(job)}</p>
            <dl className="investigation-metadata"><dt>{job.finished_at === null ? "任务已用时间" : "完整任务耗时"}</dt><dd><strong>{job.elapsed_milliseconds} 毫秒</strong><span className="small-note"> · 服务端从创建到{job.finished_at === null ? "本次查询，尚未完成" : "任务结束"}，不是首字耗时</span></dd><dt>创建</dt><dd><time dateTime={job.created_at}>{formatShanghaiTimestamp(job.created_at)}</time></dd><dt>状态更新</dt><dd><time dateTime={job.updated_at}>{formatShanghaiTimestamp(job.updated_at)}</time></dd><dt>结束</dt><dd>{job.finished_at === null ? "尚未确认" : <time dateTime={job.finished_at}>{formatShanghaiTimestamp(job.finished_at)}</time>}</dd>{job.error_code !== null && <><dt>错误标识</dt><dd><code>{job.error_code}</code></dd></>}</dl>
            {pollingStopped && <p className="investigation-notice">已达到本页自动查询上限（30 次）。任务状态仍由服务端决定，可手动刷新。</p>}
            <div className="investigation-actions"><button className="button secondary" disabled={mutation !== null || jobPending} onClick={() => selectJob(job.job_id)}>手动刷新任务</button>{canCancel && <button className="button secondary" disabled={mutation !== null || !user.permissions.includes("write:asset")} onClick={() => void cancel()}>请求取消任务</button>}</div>{canCancel && !user.permissions.includes("write:asset") && <p className="small-note">取消需要服务端 write:asset 权限；当前会话只能查看。</p>}
            {result !== null && <><div className="investigation-result-head"><InvestigationStatus status={result.status} /><span className="investigation-mode">{result.data_mode === "fixture" ? "结果为 Fixture · 非 live" : "结果为 Live"}</span></div><dl className="investigation-metadata"><dt>停止原因</dt><dd><code>{result.stop_reason || "服务未提供"}</code></dd><dt>图版本</dt><dd><code>{result.graph_version}</code></dd></dl>
              <section aria-label="缺失要求"><h3>仍需核查</h3>{result.missing_requirements.length === 0 ? <p className="small-note">未返回额外缺失要求；这不等于资料已穷尽或资产安全。</p> : <ul className="investigation-gaps">{result.missing_requirements.map((requirement, index) => <li key={index}><code>{requirement}</code></li>)}</ul>}</section>
              {result.answer === null ? <EmptyState title="没有证据化回答" description="服务没有返回可展示的结构化回答，页面不会生成替代结论。" /> : <section className="investigation-answer" aria-label="调查结论"><h3>结论与支持</h3>{result.answer.claims.map((claim, index) => <article className="investigation-claim" key={index}><span className="small-note">{claimLabels[claim.kind]}</span><p>{claim.text}</p><div className="investigation-actions">{claim.support_ids.map((id) => <a key={id} className="text-link" href={`#investigation-citation-${id}`} onClick={(event) => { event.preventDefault(); document.getElementById(`investigation-citation-${id}`)?.focus(); }}>依据 [{(result.answer?.citations.findIndex((citation) => citation.evidence_id === id) ?? -1) + 1}]</a>)}</div></article>)}</section>}
              <section className="investigation-citations" aria-label="调查引用"><h3>原文核查</h3>{!canOpenEvidence && <p className="small-note">任务查询没有返回事件绑定或证据修订。本页不使用当前表单事件拼接链接；请回到原事件核查证据 ID。</p>}{result.answer?.citations.map((citation, index) => <article className="investigation-citation" id={`investigation-citation-${citation.evidence_id}`} tabIndex={-1} key={citation.evidence_id}><h4>引用 [{index + 1}]</h4><blockquote>{citation.quote}</blockquote><code>{citation.evidence_id}</code>{canOpenEvidence && <button className="button secondary" disabled={evidencePending !== null} onClick={() => void openEvidence(citation.evidence_id)}>核查固定证据 [{index + 1}] →</button>}</article>)}{result.evidence_ids.filter((id) => !result.answer?.citations.some((citation) => citation.evidence_id === id)).map((id) => <div className="investigation-evidence-id" key={id}><code>{id}</code>{canOpenEvidence && <button className="button secondary" disabled={evidencePending !== null} onClick={() => void openEvidence(id)}>核查证据 →</button>}</div>)}<p className="small-note">调查引文只含证据 ID 与片段，缺少修订及定位元数据。点击核查后复用证据 API 取得真实修订，并核对已提交的固定版本；引文不自动等于支持结论。</p>{evidencePending !== null && <p role="status" className="small-note">正在核对证据修订…</p>}{evidenceError !== null && <ErrorPanel error={evidenceError} message={evidenceRevisionChanged ? "固定证据绑定已过期：返回修订与本轮提交的固定修订不一致，未打开其他版本。请回到原事件重新核查，确认后明确开始新调查。" : failureMessage(evidenceError, "evidence")} />}</section>
              <section aria-label="实际角色收据"><h3>职责收据</h3>{result.receipts.length === 0 ? <p className="small-note">服务未返回角色收据。</p> : <ul className="investigation-receipts">{result.receipts.map((receipt, index) => <li key={`${index}:${receipt.role}`}><div><code>{receipt.role}</code><InvestigationStatus status={receipt.status} /></div><code>{receipt.reason_code}</code><p className="small-note">证据 {receipt.evidence_ids.length} 条 · 操作 {receipt.operation_keys.length} 条</p></li>)}</ul>}</section>
            </>}
          </article>}
        </section>
        <section className="panel" aria-labelledby="investigation-operations-title"><div className="panel-heading"><div><p className="eyebrow">OPERATIONS / 实际调用</p><h2 id="investigation-operations-title">工具与模型记录</h2></div><span className="small-note">{operations?.items.length ?? 0} 条已读</span></div><div className="investigation-operations">
          {operationsPending && <p className="small-note" role="status">正在读取操作记录…</p>}{operationsError !== null && <ErrorPanel error={operationsError} message={failureMessage(operationsError, "operations")} onRetry={() => setOperationRequest((previous) => ({ ...previous, revision: previous.revision + 1 }))} />}
          {operations === null && !operationsPending && operationsError === null && <EmptyState title="尚无已读操作" description="先取得有权查看的调查任务。这里只显示实际操作，不显示模拟角色台词。" />}
          {operations !== null && <>{operations.items.length === 0 && <EmptyState title="本页操作记录为空" description="服务没有返回操作记录，不能推断工具或模型已运行。" />}<ol className="investigation-operation-list">{operations.items.map((operation) => <li key={operation.operation_key}><div className="investigation-operation-head"><code>{operation.kind} / {operation.role}</code><InvestigationStatus status={operation.status} /></div><h3>{operation.tool_name ?? operation.model_version ?? "职责节点"}</h3><dl className="investigation-metadata"><dt>操作键</dt><dd><code>{operation.operation_key}</code></dd><dt>耗时</dt><dd>{operation.completed_at === null ? "未确认完成" : `${Date.parse(operation.completed_at) - Date.parse(operation.created_at)} 毫秒 · 记录时刻差`}</dd><dt>调用计数</dt><dd>工具 {operation.tool_calls} · 模型 {operation.model_calls}</dd><dt>输入 / 输出</dt><dd>{operation.input_bytes} / {operation.output_bytes} 字节</dd><dt>成本</dt><dd>未知</dd><dt>版本</dt><dd><code>{operation.policy_version}</code>{operation.prompt_version !== null && <> · <code>{operation.prompt_version}</code></>}</dd></dl></li>)}</ol><p className="small-note">按服务端操作键排序；预留状态表示结果未知，不代表调用成功。</p>{operations.next_cursor !== null && operations.items.length < MAX_LOADED_OPERATIONS && <button className="button secondary" disabled={operationsPending} onClick={() => setOperationRequest({ cursor: operations.next_cursor, revision: operationRequest.revision + 1 })}>加载更多操作</button>}{operations.next_cursor !== null && operations.items.length >= MAX_LOADED_OPERATIONS && <p className="small-note">已达到本页 100 条操作展示上限；刷新记录可重新读取首页。</p>}<button className="button secondary" disabled={operationsPending || job === null} onClick={() => setOperationRequest((previous) => ({ cursor: null, revision: previous.revision + 1 }))}>刷新操作首页</button></>}
        </div></section>
      </div>
    </div>
  </div>;
}

/** Private state and in-flight IO are scoped to the authenticated generation, user and permission version. */
export function InvestigationWorkspace(props: InvestigationWorkspaceProps) {
  if (props.user === null || !props.isCurrent()) return <section className="panel"><EmptyState title="登录后使用调查工作台" description="当前没有有效会话，未读取任务或资产。" /><a className="button secondary" href="#session">核对会话</a></section>;
  if (!props.user.permissions.includes("read:public")) return <section className="panel"><EmptyState title="当前会话无调查读取权限" description="需要服务端 read:public 权限。请核对团队授权。" /></section>;
  return <AuthorizedInvestigationWorkspace key={`${props.authScope}:${props.user.user_id}:${props.user.tenant_id}:${props.user.permission_version}:${props.initialJobId ?? ""}`} {...props} user={props.user} />;
}
