import { useState, type FormEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { getSourceJob } from "../../api/source-client";
import type { SourceJob } from "../../api/source-contracts";
import { getInvestigation, getInvestigationOperations } from "../investigations/investigation-client";
import type { InvestigationOperationPage, InvestigationResponse } from "../investigations/investigation-contracts";
import { EmptyState, ErrorPanel } from "../../components/status";

type LookupFailure = { error: ApiProblem; kind: "job" | "investigation" };

function failureText(failure: LookupFailure): string {
  if (failure.error.status === 401) return "会话已失效，没有展示任务内容。";
  if (failure.error.status === 403) return "当前会话不能查看这条任务。没有权限不等于任务不存在。";
  if (failure.error.status === 422) return "标识不是完整 UUID。没有把无效输入当成查询成功。";
  if (failure.error.status === 404) return "没有这条任务记录。这不是零条成功结果。";
  return "查询没有完成。失败不能解释为没有任务。";
}

/** Reads saved job and investigation receipts. An empty form is not an empty history. */
export function TaskWorkspace() {
  const [jobId, setJobId] = useState("");
  const [investigationId, setInvestigationId] = useState("");
  const [job, setJob] = useState<SourceJob | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [operations, setOperations] = useState<InvestigationOperationPage | null>(null);
  const [failures, setFailures] = useState<LookupFailure[]>([]);
  const [pending, setPending] = useState(false);
  const [queried, setQueried] = useState(false);

  async function lookup(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setFailures([]);
    setJob(null);
    setInvestigation(null);
    setOperations(null);
    setQueried(true);
    const failures: LookupFailure[] = [];
    try {
      if (jobId.trim()) {
        try {
          setJob(await getSourceJob(jobId.trim()));
        } catch (error: unknown) {
          failures.push({ error: publicProblem(error), kind: "job" });
        }
      }
      if (investigationId.trim()) {
        try {
          const found = await getInvestigation(investigationId.trim());
          setInvestigation(found);
          setOperations(await getInvestigationOperations(found.job_id));
        } catch (error: unknown) {
          failures.push({ error: publicProblem(error), kind: "investigation" });
        }
      }
    } finally {
      setFailures(failures);
      setPending(false);
    }
  }

  return <section className="panel" aria-labelledby="task-title">
    <div className="panel-heading"><div><p className="eyebrow">OPERATIONS / 任务收据</p><h2 id="task-title">任务轨迹</h2></div></div>
    <form className="query-toolbar" aria-label="查询任务收据" onSubmit={(event) => void lookup(event)}>
      <label htmlFor="task-job-id">来源或富化任务标识<input id="task-job-id" value={jobId} onChange={(input) => setJobId(input.target.value)} placeholder="job UUID" /></label>
      <label htmlFor="task-investigation-id">调查任务标识<input id="task-investigation-id" value={investigationId} onChange={(input) => setInvestigationId(input.target.value)} placeholder="investigation UUID" /></label>
      <button className="button" type="submit" disabled={pending || (!jobId.trim() && !investigationId.trim())}>{pending ? "正在查询…" : "查询收据"}</button>
    </form>
    {!queried && <EmptyState title="尚未查询" description="没有输入标识。这不是零条任务，也不是能力未建设。" />}
    {failures.map((failure) => <ErrorPanel key={failure.kind} error={failure.error} message={failureText(failure)} />)}
    {job !== null && <dl className="evidence-metadata"><dt>任务</dt><dd><code>{job.job_id}</code></dd><dt>状态</dt><dd>{job.status}</dd><dt>错误</dt><dd>{job.error_code ?? "无"}</dd></dl>}
    {investigation !== null && <dl className="evidence-metadata"><dt>调查</dt><dd><code>{investigation.job_id}</code></dd><dt>状态</dt><dd>{investigation.status}</dd><dt>停止原因</dt><dd>{investigation.result?.stop_reason ?? "尚未停止"}</dd></dl>}
    {operations !== null && operations.items.length === 0 && <p className="small-note">这条调查还没有工具调用。没有调用不等于调查成功。</p>}
    {operations !== null && operations.items.length > 0 && <ul className="inspection-list">{operations.items.map((item) => <li key={item.operation_key}>{item.tool_name ?? item.role} · {item.status}</li>)}</ul>}
  </section>;
}
