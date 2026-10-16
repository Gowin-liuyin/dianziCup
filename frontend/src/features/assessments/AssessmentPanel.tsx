import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem, type CurrentUser } from "../../api/client";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { EmptyState, ErrorPanel } from "../../components/status";
import { isAssetIdentifier, type AssetSnapshot } from "../assets/asset-contracts";
import { completenessLabels } from "../assets/asset-status";
import { createAssessment, getAssessment } from "./assessment-client";
import { AssessmentResponseScopeMismatch, validateAssessmentRequest, type AssessmentResponse, type ConditionEvaluation, type ConditionValue } from "./assessment-contracts";
import "./assessment.css";

export interface AssessmentPanelProps {
  user: CurrentUser; snapshot: AssetSnapshot | null; currentSnapshotId: string | null; authScope: string;
  isCurrent: () => boolean; onFailure?: (error: ApiProblem) => void; onOpenEvent?: (eventId: string, evidenceId?: string) => void;
}
type Resource = { kind: "idle" | "cancelled" } | { kind: "loading" } | { kind: "loaded"; response: AssessmentResponse } | { kind: "failed"; error: ApiProblem };
const assessmentLabels = { supported_applicability: "支持适用", excluded_with_evidence: "证据排除", insufficient_evidence: "证据不足", conflicting_evidence: "证据冲突" };
const conditionLabels: Record<ConditionValue, string> = { true: "条件成立", false: "条件不成立", unknown: "条件未知", conflict: "条件冲突" };
const ruleKindLabels = { software_applicability: "软件适用性", observed_path: "观测路径", research_prerequisites: "研究前提" };
const freshnessLabels = { current: "后端标记：current", stale: "已过期 · 待重新验证", unknown: "时效未知" };

function Notes({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return <section className="assessment-notes"><h4>{title}</h4>{items.length === 0 ? <p className="small-note">{empty}</p> : <ul>{items.map((item, index) => <li key={`${index}:${item}`}><code>{item}</code>{item === "unsupported_rule" && <span>没有可支持此次判断的已发布规则。</span>}</li>)}</ul>}</section>;
}
function AssessmentError({ error, retry }: { error: ApiProblem; retry: () => void }) {
  let message = error.message;
  if (error.status === 401) message = "会话已失效，已清除评估结果。请重新登录。";
  if (error.status === 403) message = error.code === "csrf_rejected" ? "会话校验未通过，已清除评估结果。请重新核对会话。" : "当前会话没有评估权限，已清除评估结果。";
  if (error.status === 404) message = "资产、快照、规则或评估不可用：不存在，或当前会话无权查看。";
  if (error.status === 409) message = "评估输入或证据完整性未通过校验。本次未获得可用结论，请核对规则与资产版本。";
  if (error.status === 422) message = "请填写规则标识（1–200 字符）与规则版本（1–2147483647 的整数），并选择固定资产快照。";
  if (error.status === 503) message = "评估依赖未配置或暂不可用。本次没有可用结果，不能解释为没有影响。";
  if (error.code === "invalid_response") message = "返回数据与当前合同或所选输入范围不一致，评估内容已清除。请核对接口与会话。";
  return <ErrorPanel error={error} message={message} onRetry={error.retryable ? retry : undefined} retryLabel="重试同一输入" />;
}
function ConditionNode({ node, eventId, onOpenEvent, depth = 1 }: { node: ConditionEvaluation; eventId: string; onOpenEvent?: AssessmentPanelProps["onOpenEvent"]; depth?: number }) {
  const canOpenEvent = isAssetIdentifier(eventId) && onOpenEvent !== undefined;
  return <li className="assessment-node"><details open={depth === 1}><summary><code>{node.node_id}</code><span className={`assessment-condition condition-${node.value}`}>{conditionLabels[node.value]}</span></summary>
    <div className="assessment-node-body"><p className="assessment-reason">原因 <code>{node.reason_code}</code></p>
      {node.asset_field_refs.length > 0 && <div className="assessment-field-refs"><strong>资产字段依据</strong>{node.asset_field_refs.map((field, index) => <code key={`${index}:${field}`}>{field}</code>)}</div>}
      {node.evidence_ids.length > 0 && <div className="assessment-evidence-links"><strong>原文证据引用</strong><p className="small-note">引用标识需回到事件核查原文与支持关系；本投影未提供引文正文和文档版本。</p>{node.evidence_ids.map((evidenceId, index) => canOpenEvent && isAssetIdentifier(evidenceId) ? <button key={`${index}:${evidenceId}`} type="button" className="button secondary" onClick={() => onOpenEvent?.(eventId, evidenceId)}>核查证据 <code>{evidenceId}</code></button> : <p key={`${index}:${evidenceId}`} className="small-note"><code>{evidenceId}</code> · 当前详情入口不可用</p>)}</div>}
      {node.missing_requirements.length > 0 && <Notes title="节点缺口" items={node.missing_requirements} empty="" />}
      {node.observed_conflict_ids.length > 0 && <Notes title="保留的节点冲突" items={node.observed_conflict_ids} empty="" />}
      {node.limitations.length > 0 && <Notes title="节点限制" items={node.limitations} empty="" />}
      {node.child_results.length > 0 && <ol className="assessment-tree">{node.child_results.map((child) => <ConditionNode key={child.node_id} node={child} eventId={eventId} onOpenEvent={onOpenEvent} depth={depth + 1} />)}</ol>}
    </div></details></li>;
}
function ResultView({ response, history, onOpenEvent }: { response: AssessmentResponse; history: boolean; onOpenEvent?: AssessmentPanelProps["onOpenEvent"] }) {
  return <article className="assessment-result" aria-label="保存的固定快照评估">
    <div className="assessment-result-heading"><div><p className="eyebrow">SAVED ASSESSMENT / 保存的评估</p><h3>{assessmentLabels[response.status]}</h3></div><span className="small-note">{response.reused ? "复用已保存回执" : "已保存回执"}</span></div>
    {(history || response.freshness !== "current") && <p className="assessment-warning">{history ? "历史快照结果，保留原结论；不代表当前资产。" : "当前结论有效性尚未确认。"} {response.freshness === "stale" ? "输入已变化，请重新评估当前快照。" : "请结合后端时效与输入范围核查。"}</p>}
    <div className="assessment-state-grid"><div><span>原始四态结论</span><strong>{assessmentLabels[response.status]}</strong><code>{response.status}</code></div><div><span>独立时效</span><strong>{freshnessLabels[response.freshness]}</strong><code>{response.freshness}</code></div><div><span>路径暴露 / PoC</span><strong>{response.exposure_result === "observed_path_only" ? "仅观测路径" : "路径未评估"}</strong><span>PoC 未验证 · 不确认利用成功</span></div></div>
    <p className="assessment-boundary">软件适用、网络暴露与利用验证分别核查。证据排除仅限本规则与固定输入，不能解释为绝对安全。</p>
    <dl className="assessment-metadata"><dt>评估标识</dt><dd><code>{response.assessment_id}</code></dd><dt>资产 / 快照</dt><dd><code>{response.asset_id}</code><code>{response.asset_snapshot_id}</code></dd><dt>规则版本</dt><dd><code>{response.rule_id} / v{response.rule_version}</code></dd><dt>关联事件</dt><dd><code>{response.event_id}</code>{onOpenEvent !== undefined && isAssetIdentifier(response.event_id) && <button type="button" className="button secondary" onClick={() => onOpenEvent(response.event_id)}>核查关联事件</button>}</dd><dt>保存时间</dt><dd><time dateTime={response.created_at}>{formatShanghaiTimestamp(response.created_at)}</time></dd><dt>知识 epoch</dt><dd><code>{response.knowledge_epoch ?? "未知 · null"}</code></dd><dt>输入摘要</dt><dd><code>{response.input_digest}</code></dd></dl>
    <div className="assessment-gap-grid"><Notes title="评估缺口" items={response.missing_requirements} empty="后端未列出缺口；这不证明资产绝对安全。" /><Notes title="保留冲突" items={response.conflicts} empty="后端未列出冲突。" /></div>
    <Notes title="评估限制" items={response.limitations} empty="后端未列出附加限制；固定规则范围仍适用。" />
    <section className="assessment-tree-section"><div className="assessment-section-heading"><h4>条件树与证据</h4><span className="small-note">{response.rule_result === null ? "无可用规则执行结果" : ruleKindLabels[response.rule_result.rule_kind]}</span></div>
      {response.rule_result === null ? <EmptyState title="规则尚不能支持判定" description="未发布、失效或必要证据不足时，后端保留证据不足与具体缺口。请核对规则发布状态与证据。" /> : <><p className="small-note">规则执行原态：{assessmentLabels[response.rule_result.status]} · 条件摘要 <code>{response.rule_result.condition_sha256}</code></p><ol className="assessment-tree"><ConditionNode node={response.rule_result.evaluation_tree} eventId={response.event_id} onOpenEvent={onOpenEvent} /></ol><Notes title="规则执行限制" items={response.rule_result.limitations} empty="未列出附加限制。" /></>}
    </section><details className="assessment-epochs"><summary>查看原始范围 epoch（null 保留未知）</summary><pre>{JSON.stringify(response.scope_epoch_map, null, 2)}</pre></details>
  </article>;
}
function FixedSnapshotPanel({ user, snapshot, currentSnapshotId, isCurrent, onFailure, onOpenEvent }: AssessmentPanelProps & { snapshot: AssetSnapshot; user: CurrentUser & { tenant_id: string } }) {
  const [ruleId, setRuleId] = useState("");
  const [ruleVersion, setRuleVersion] = useState("1");
  const [assessmentId, setAssessmentId] = useState("");
  const [resource, setResource] = useState<Resource>({ kind: "idle" });
  const [denied, setDenied] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const lastAction = useRef<"create" | "read">("create");
  useEffect(() => () => { generation.current += 1; controller.current?.abort(); }, []);
  const history = currentSnapshotId !== null && snapshot.snapshot_id !== currentSnapshotId;
  let snapshotHeading = "SELECTED SNAPSHOT / 当前快照";
  if (history) snapshotHeading = "SAVED HISTORY / 历史快照";
  if (currentSnapshotId === null) snapshotHeading = "CURRENT POINTER / 当前指针待复核";
  function clearIntent() { generation.current += 1; controller.current?.abort(); setResource({ kind: "idle" }); }
  function cancel() { generation.current += 1; controller.current?.abort(); setResource({ kind: "cancelled" }); }
  async function run(action: "create" | "read") {
    if (denied || !isCurrent()) return;
    const requestGeneration = ++generation.current;
    controller.current?.abort();
    const requestController = new AbortController(); controller.current = requestController; lastAction.current = action;
    setResource({ kind: "loading" });
    const current = () => generation.current === requestGeneration && !requestController.signal.aborted && isCurrent();
    try {
      if (!/^\d+$/.test(ruleVersion)) throw new ApiProblem(422, "validation_error", false);
      const request = validateAssessmentRequest({ asset_id: snapshot.asset_id, asset_snapshot_id: snapshot.snapshot_id, rule_id: ruleId, rule_version: Number(ruleVersion) });
      const response = action === "create" ? await createAssessment(user.tenant_id, request, requestController.signal, current) : await getAssessment({ tenantId: user.tenant_id, assetId: snapshot.asset_id, snapshotId: snapshot.snapshot_id, ruleId: request.rule_id, ruleVersion: request.rule_version }, assessmentId, requestController.signal);
      if (current()) { setResource({ kind: "loaded", response }); setAssessmentId(response.assessment_id); }
    } catch (failure: unknown) {
      if (!current()) return;
      const error = publicProblem(failure);
      if (error.status === 401 || error.status === 403 || error instanceof AssessmentResponseScopeMismatch) { setDenied(true); setAssessmentId(""); }
      setResource({ kind: "failed", error }); onFailure?.(error);
    }
  }
  function submit(event: FormEvent<HTMLFormElement>, action: "create" | "read") { event.preventDefault(); void run(action); }
  return <section className="panel assessment-panel" aria-labelledby="assessment-panel-title">
    <div className="panel-heading"><div><p className="eyebrow">ASSESS / 固定输入自查</p><h2 id="assessment-panel-title">条件与证据研判</h2></div><span className="assessment-mode">{user.data_mode === "fixture" ? "显式 Fixture · 非 live" : "当前认证 API"}</span></div>
    {!denied && <><div className="assessment-snapshot"><span className="eyebrow">{snapshotHeading}</span><strong>快照 #{snapshot.snapshot_number}</strong><code>{snapshot.snapshot_id}</code><p className="small-note">实际观察 <time dateTime={snapshot.observed_at}>{formatShanghaiTimestamp(snapshot.observed_at)}</time> · {completenessLabels[snapshot.inventory_completeness]}</p>
      {(history || currentSnapshotId === null) && <p className="assessment-warning">{history ? "选择的是历史输入；新评估也不会覆盖历史或证明当前状态。" : "当前资产指针尚未重新确认，所选快照不能视为当前状态。"}</p>}
      {snapshot.components.some((component) => component.version === null) && <p className="small-note">该快照含版本未知的组件声明。缺字段保留未知，不自动补成否定。</p>}
    </div>
    <form className="assessment-form" onSubmit={(event) => submit(event, "create")}><div className="assessment-rule-fields"><label>已知规则标识<input name="rule_id" value={ruleId} required autoComplete="off" onChange={(event) => { clearIntent(); setRuleId(event.target.value); }} placeholder="已登记规则的 rule_id" /></label><label>固定规则版本<input name="rule_version" value={ruleVersion} type="text" inputMode="numeric" required autoComplete="off" onChange={(event) => { clearIntent(); setRuleVersion(event.target.value); }} /></label></div><p className="small-note">选择单条已知规则与版本。未发布或缺证据时保留证据不足，未知规则由服务端明确返回不可用。</p><div className="assessment-actions"><button className="button" type="submit" disabled={resource.kind === "loading" || ruleId.length === 0}>评估固定快照</button>{resource.kind === "loading" && <button className="button secondary" type="button" onClick={cancel}>停止等待</button>}</div></form>
    <form className="assessment-saved-form" onSubmit={(event) => submit(event, "read")}><label>重读保存的评估 UUID<input name="assessment_id" value={assessmentId} autoComplete="off" onChange={(event) => { clearIntent(); setAssessmentId(event.target.value); }} placeholder="填写评估标识，并保持同一快照与规则" maxLength={36} required /></label><button className="button secondary" type="submit" disabled={resource.kind === "loading" || !isAssetIdentifier(assessmentId) || ruleId.length === 0}>读取保存结果</button></form></>}
    <div aria-live="polite" aria-busy={resource.kind === "loading"}>{resource.kind === "idle" && <EmptyState title="等待指定规则与版本" description="尚未请求评估，没有结果不等于零影响。不会从组件名或网络声明推测安全。" />}{resource.kind === "loading" && <p className="loading-state" role="status">正在读取真实评估路径…</p>}{resource.kind === "cancelled" && <p className="assessment-warning" role="status">已停止等待。停止等待不会撤销服务端可能已提交的评估；重新提交相同输入可恢复幂等回执。</p>}{resource.kind === "failed" && <AssessmentError error={resource.error} retry={() => { void run(lastAction.current); }} />}</div>
    {resource.kind === "loaded" && <ResultView response={resource.response} history={history || currentSnapshotId === null} onOpenEvent={onOpenEvent} />}
  </section>;
}

/** The parent owns authenticated scope changes; remounting also prevents old private responses from restoring the panel. */
export function AssessmentPanel(props: AssessmentPanelProps) {
  const { user, snapshot } = props;
  if (user.tenant_id === null || !user.permissions.includes("read:asset")) return <section className="panel assessment-panel"><EmptyState title="当前会话无资产研判权限" description="需要明确租户与 read:asset；不按角色名称补授权限。" /></section>;
  if (snapshot === null) return <section className="panel assessment-panel"><EmptyState title="请选择固定资产快照" description="在授权资产目录中选择当前或历史快照，再指定规则。尚无输入不等于没有影响。" /></section>;
  if (snapshot.tenant_id !== user.tenant_id) return <section className="panel assessment-panel"><EmptyState title="快照与当前认证范围不一致" description="未显示私有快照或发送评估。请重新读取当前会话的授权资产。" /></section>;
  return <FixedSnapshotPanel key={`${props.authScope}:${user.user_id}:${user.tenant_id}:${user.permission_version}:${snapshot.asset_id}:${snapshot.snapshot_id}`} {...props} snapshot={snapshot} user={{ ...user, tenant_id: user.tenant_id }} />;
}
