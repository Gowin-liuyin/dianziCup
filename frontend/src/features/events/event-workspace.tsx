import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { getEventDetail, getEventList, getEvidence, type EventFilters } from "../../api/knowledge-client";
import type { ClaimOrigin, ClaimStatus, DimensionName, DimensionStatus, EventDetailResponse, EventListResponse, EvidenceResponse, Freshness } from "../../api/knowledge-contracts";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { readEventSelection } from "../../app/workspace-navigation";
import { EmptyState, ErrorPanel, StatusBadge } from "../../components/status";
import { PreparedEventWorkspace } from "../preparation/capability-workspace";

type Resource<T> = { kind: "loading" } | { kind: "loaded"; value: T } | { kind: "failed"; error: ApiProblem };
const dimensionLabels: Record<DimensionName, string> = { cvss: "CVSS 评分", epss: "EPSS 可能性", kev: "KEV 目录", cwe: "CWE 弱点", atlas: "ATLAS 映射", versions: "影响版本", literature: "论文关联", poc: "PoC 核查", exposure: "暴露统计" };
const dimensionStatusLabels: Record<DimensionStatus, string> = { available: "已取得", not_found: "未发现", not_applicable: "不适用", conflict: "有冲突", blocked: "受阻", failed: "失败", pending: "待处理" };
const claimStatusLabels: Record<ClaimStatus, string> = { supported: "有证据支持", disputed: "有争议", unverified: "未核验", superseded: "已被新版本替代", withdrawn: "已撤回" };
const originLabels: Record<ClaimOrigin, string> = { source_explicit: "原文明示", structured_source: "结构化来源", rule_derived: "规则推导", model_hypothesis: "模型假设", human_confirmed: "人工确认" };
const freshnessLabels: Record<Freshness, string> = { current: "当前", stale: "已过期", unknown: "时效未知" };

function SavedTime({ value }: { value: string | null }) {
  return value === null ? <span className="unknown-value">未知 / 未留存</span> : <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>;
}

function FreshnessBadge({ value }: { value: Freshness }) {
  return <span className={`freshness-label freshness-${value}`}>{freshnessLabels[value]}</span>;
}

function eventListStatus(resource: Resource<EventListResponse>): string {
  if (resource.kind === "loading") return "loading";
  if (resource.kind === "failed") {
    if (resource.error.status === 403) return "denied";
    if (resource.error.status === 404) return "not_connected";
    return "failed";
  }
  return resource.value.items.length === 0 ? "no_result" : "loaded";
}

function ResourceError({ error, collection, onRetry }: { error: ApiProblem; collection?: boolean; onRetry: () => void }) {
  let title = "查询未完成";
  let message = error.message;
  if (error.status === 404) {
    title = collection ? "情报服务待接通" : "记录不可访问";
    message = collection ? "事件服务没有返回可用入口。当前不是零记录结果；服务接通后请重新查询。" : "记录不存在，或当前会话没有查看权限。没有展示缓存内容。";
  } else if (error.status === 403) {
    title = "没有查看权限";
    message = "当前授权不允许查看此内容，请核对团队权限。没有返回记录标题或数量。";
  } else if (error.status === 503) {
    title = "依赖暂不可用";
    message = "当前查询失败，不能据此判断为空或无风险。已有记录需重新取得后展示。";
  } else if (error.code === "unsupported_filter") {
    title = "筛选能力尚未接通";
    message = "服务暂不支持本次筛选。请移除产品筛选后重试，不能把筛选失败当作没有匹配。";
  }
  return <div className="resource-error"><h3>{title}</h3><ErrorPanel error={error} message={message} onRetry={error.status === 403 ? undefined : onRetry} retryLabel="重新查询" /></div>;
}

function EventDetail({ id, onSessionExpired, isCurrent }: { id: string; onSessionExpired: () => void; isCurrent: () => boolean }) {
  const [resource, setResource] = useState<Resource<EventDetailResponse>>({ kind: "loading" });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setResource({ kind: "loading" });
    void getEventDetail(id, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setResource({ kind: "loaded", value }); }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure);
      setResource({ kind: "failed", error });
      if (error.status === 401) onSessionExpired();
    });
    return () => controller.abort();
  }, [id, retry, onSessionExpired, isCurrent]);

  return <section className="panel event-detail" aria-labelledby="event-detail-title">
    <div className="panel-heading"><div><p className="eyebrow">EVENT DETAIL / 事实与修订</p><h2 id="event-detail-title">事件详情</h2></div><a className="text-link" href="#events">返回列表</a></div>
    {resource.kind === "loading" && <p className="loading-state" role="status">正在取得事件事实与历史版本…</p>}
    {resource.kind === "failed" && <ResourceError error={resource.error} onRetry={() => setRetry((value) => value + 1)} />}
    {resource.kind === "loaded" && <div className="event-detail-body">
      <div className="event-title"><h3>{resource.value.event.title}</h3><FreshnessBadge value={resource.value.event.freshness} /><span className="small-note">{resource.value.data_mode === "fixture" ? "合成 / Fixture" : "真实 / Live"}</span></div>
      <code className="record-id">{resource.value.event.event_id}</code>
      <a className="button secondary" href={`#questions/${resource.value.event.event_id}`}>基于此事件提问 →</a>
      <h3 className="detail-section-title">九维富化</h3>
      <p className="small-note">各维度独立记录状态。未返回的维度没有结果，不能解释为不适用或完成。</p>
      {Object.entries(dimensionLabels).map(([name, label]) => {
        const dimensions = resource.value.dimensions.filter((dimension) => dimension.dimension === name);
        return <div className="dimension-row" key={name}><div className="dimension-name">{label}</div><div>{dimensions.length === 0 ? <span className="unknown-value">未提供该维度</span> : dimensions.map((dimension, index) => <div className="dimension-result" key={`${name}-${index}`}><span className="dimension-status">{dimensionStatusLabels[dimension.status]}</span><FreshnessBadge value={dimension.freshness} />{dimension.error_code && <code className="small-note">{dimension.error_code}</code>}<div className="citation-links">{dimension.citations.map((citation) => <a key={citation.evidence_id} href={`#events/${id}/evidence/${citation.evidence_id}/revision/${citation.revision_id}`}>查看引用：{citation.locator}</a>)}</div></div>)}</div></div>;
      })}
      <h3 className="detail-section-title">事实与来源断言</h3>
      {resource.value.claims.length === 0 && <EmptyState title="尚未取得事实记录" description="没有事实记录不代表不存在相关风险。" />}
      {resource.value.claims.map((claim) => <article className="claim-row" key={claim.claim_id}><div><code>{claim.predicate}</code><span className="claim-status">{claimStatusLabels[claim.status]}</span><span className="small-note">{originLabels[claim.origin]}</span></div><p>{claim.display_value}</p><div className="citation-links">{claim.evidence_ids.map((evidenceId, index) => <a key={evidenceId} href={`#events/${id}/evidence/${evidenceId}${claim.source_revision_id === null ? "" : `/revision/${claim.source_revision_id}`}`}>原文片段 [{index + 1}]</a>)}</div></article>)}
      <h3 className="detail-section-title">原文修订时间线</h3>
      {resource.value.revisions.length === 0 && <EmptyState title="尚未取得修订记录" description="历史版本需要保存的原文与修订记录，不能由当前来源信息推测。" />}
      {resource.value.revisions.map((revision) => <article className="revision-entry" key={revision.revision_id}><div className="revision-entry-title"><strong>修订 {revision.revision_number}</strong><span className="small-note">解析：{revision.parse_status}</span></div><code className="record-id">{revision.revision_id}</code><dl className="evidence-metadata"><dt>源发布时间</dt><dd><SavedTime value={revision.source_published_at} /></dd><dt>源修订时间</dt><dd><SavedTime value={revision.source_modified_at} /></dd><dt>首次观察</dt><dd><SavedTime value={revision.first_observed_at} /></dd><dt>入库完成</dt><dd><SavedTime value={revision.ingested_at} /></dd></dl>{revision.canonical_uri ? <a className="text-link" href={revision.canonical_uri} target="_blank" rel="noopener noreferrer">打开该版本来源地址 ↗</a> : <p className="small-note">该历史版本原文地址未留存</p>}</article>)}
    </div>}
  </section>;
}

function EvidenceInspector({ id, revisionId, onSessionExpired, isCurrent }: { id: string | null; revisionId: string | null; onSessionExpired: () => void; isCurrent: () => boolean }) {
  const [resource, setResource] = useState<Resource<EvidenceResponse>>({ kind: "loading" });
  const [retry, setRetry] = useState(0);
  const inspector = useRef<HTMLElement>(null);
  useEffect(() => {
    if (id === null) return;
    const controller = new AbortController();
    setResource({ kind: "loading" });
    void getEvidence(id, revisionId, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setResource({ kind: "loaded", value }); }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure);
      setResource({ kind: "failed", error });
      if (error.status === 401) onSessionExpired();
    });
    return () => controller.abort();
  }, [id, revisionId, retry, onSessionExpired, isCurrent]);

  useEffect(() => {
    if (id === null || resource.kind !== "loaded") return;
    inspector.current?.focus({ preventScroll: true });
    inspector.current?.scrollIntoView?.({ block: "start", behavior: "instant" });
  }, [id, resource.kind]);

  return <aside ref={inspector} tabIndex={-1} className="panel evidence-inspector" aria-labelledby="evidence-preview-title"><div className="panel-heading"><div><p className="eyebrow">EVIDENCE / 原文依据</p><h2 id="evidence-preview-title">证据检视</h2></div><span className="inspector-symbol" aria-hidden="true">⌁</span></div>
    {id === null ? <EmptyState title="选择原文引用" description="打开事件后，选择事实或维度引用，查看指定修订版本的准确片段。" /> : <>
      {resource.kind === "loading" && <p className="loading-state" role="status">正在取得指定版本证据…</p>}
      {resource.kind === "failed" && <ResourceError error={resource.error} onRetry={() => setRetry((value) => value + 1)} />}
      {resource.kind === "loaded" && <div className="evidence-body"><p className="small-note">{resource.value.data_mode === "fixture" ? "合成 / Fixture" : "真实 / Live"}</p><blockquote>{resource.value.quote_text}</blockquote><p className="boundary-note">引文存在 ≠ 内容支持</p><dl className="evidence-metadata"><dt>证据标识</dt><dd><code>{resource.value.span_id}</code></dd><dt>原文修订</dt><dd><code>{resource.value.revision_id}</code></dd><dt>定位类型</dt><dd>{resource.value.locator_kind === "legacy_unverified" ? "历史定位未核验" : resource.value.locator_kind}</dd><dt>Unicode 范围</dt><dd><code>[{resource.value.start_offset}, {resource.value.end_offset})</code></dd><dt>PDF 页码</dt><dd>{resource.value.page_number ?? "不适用 / 未留存"}</dd><dt>JSON 位置</dt><dd><code>{resource.value.json_pointer ?? "不适用 / 未留存"}</code></dd><dt>定位核验</dt><dd><SavedTime value={resource.value.verified_at} /></dd><dt>源发布时间</dt><dd><SavedTime value={resource.value.source_published_at} /></dd><dt>源修订时间</dt><dd><SavedTime value={resource.value.source_modified_at} /></dd><dt>首次观察</dt><dd><SavedTime value={resource.value.first_observed_at} /></dd><dt>入库完成</dt><dd><SavedTime value={resource.value.ingested_at} /></dd></dl>{resource.value.source_uri ? <a className="button secondary" href={resource.value.source_uri} target="_blank" rel="noopener noreferrer">打开来源地址 ↗</a> : <p className="small-note">该历史版本原文地址未留存</p>}</div>}
    </>}
  </aside>;
}

/** 所有事实来自冻结投影；换会话、换对象和错误时隐藏旧数据，原文用React文本渲染。 */
export function EventWorkspace() {
  const { state, error: sessionError, actionPending, sessionGeneration, expireSession, isSessionCurrent } = useAuthSession();
  const [selection, setSelection] = useState(() => readEventSelection(window.location.hash));
  const [filters, setFilters] = useState<EventFilters>({ limit: 20 });
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState("");
  const [riskType, setRiskType] = useState("");
  const [updatedAfter, setUpdatedAfter] = useState("");
  const [resource, setResource] = useState<Resource<EventListResponse>>({ kind: "loading" });
  const [retry, setRetry] = useState(0);
  const user = state.kind === "authenticated" ? state.user : null;
  const expired = useCallback(() => expireSession(sessionGeneration), [expireSession, sessionGeneration]);
  const isCurrent = useCallback(() => isSessionCurrent(sessionGeneration), [isSessionCurrent, sessionGeneration]);

  useEffect(() => {
    const changeSelection = () => setSelection(readEventSelection(window.location.hash));
    window.addEventListener("hashchange", changeSelection);
    return () => window.removeEventListener("hashchange", changeSelection);
  }, []);

  useEffect(() => {
    if (user === null || actionPending) return;
    const controller = new AbortController();
    setResource({ kind: "loading" });
    void getEventList(filters, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setResource({ kind: "loaded", value }); }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure);
      setResource({ kind: "failed", error });
      if (error.status === 401) expired();
    });
    return () => controller.abort();
  }, [filters, retry, user, actionPending, expired, isCurrent]);

  if (state.kind !== "authenticated" || actionPending) return <>{sessionError?.code === "session_expired" && <ErrorPanel error={sessionError} onRetry={() => { window.location.hash = "#session"; }} retryLabel="重新登录" />}<PreparedEventWorkspace authenticated={false} /></>;
  const disconnected = resource.kind === "failed" && (resource.error.status === 404 || resource.error.status === 403);
  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSelection(null);
    window.history.replaceState(null, "", "#events");
    setFilters({ q: query.trim(), product: product.trim(), risk_type: riskType.trim(), updated_after: updatedAfter || undefined, limit: 20 });
  }

  return <div className="research-grid event-research-grid"><div className="event-primary">
    <section className="panel capability-panel" aria-labelledby="event-feed-title"><div className="panel-heading"><div><p className="eyebrow">EVENTS / 事件流</p><h2 id="event-feed-title">情报列表</h2></div><StatusBadge state={eventListStatus(resource)} /></div>
      <form className="query-toolbar" onSubmit={submitSearch} aria-label="情报筛选"><div className="query-input"><label htmlFor="event-query">检索关键词</label><input id="event-query" placeholder="事件标题或公开标识" value={query} onChange={(event) => setQuery(event.target.value)} disabled={disconnected} /></div><div className="query-filters"><label>产品<input aria-label="产品筛选" placeholder="未支持时明确提示" value={product} onChange={(event) => setProduct(event.target.value)} disabled={disconnected} /></label><label>风险类型<input aria-label="风险类型筛选" placeholder="全部类型" value={riskType} onChange={(event) => setRiskType(event.target.value)} disabled={disconnected} /></label><button className="button" type="submit" disabled={disconnected || resource.kind === "loading"}>检索情报</button></div><label className="updated-filter" htmlFor="updated-after">修订时间之后<input id="updated-after" placeholder="ISO 8601（含时区）" value={updatedAfter} onChange={(event) => setUpdatedAfter(event.target.value)} disabled={disconnected} /></label><p className="small-note">时间筛选使用真实业务修订时间；本页数量不代表全部事件总数。</p></form>
      <div className="table-scroll"><table className="intelligence-table" aria-label="情报事件列表"><thead><tr><th scope="col">事件 / 公开标识</th><th scope="col">来源</th><th scope="col">状态 / 时效</th><th scope="col">首次发现</th></tr></thead><tbody>{resource.kind === "loaded" && resource.value.items.map((event) => <tr key={event.event_id}><th scope="row"><a className="event-record-link" href={`#events/${event.event_id}`}>{event.title}</a><code className="record-id">{event.external_ids.length ? event.external_ids.join(" · ") : "未提供公开标识"}</code></th><td><span className="data-value">{event.source_count}</span><span className="small-note"> 个可见来源</span></td><td><span className="event-status">{event.status}</span><FreshnessBadge value={event.freshness} /></td><td><SavedTime value={event.first_seen_at} /></td></tr>)}</tbody></table></div>
      {resource.kind === "loading" && <p className="loading-state" role="status">正在查询授权范围内的事件…</p>}
      {resource.kind === "failed" && <ResourceError error={resource.error} collection onRetry={() => setRetry((value) => value + 1)} />}
      {resource.kind === "loaded" && resource.value.items.length === 0 && <EmptyState title="本次查询没有事件记录" description="服务已完成此次查询并返回空结果。这不代表没有相关风险；可以调整筛选或查看来源范围。" />}
      {resource.kind === "loaded" && <div className="list-pagination"><span className="small-note">本页 {resource.value.items.length} 条 · {resource.value.data_mode === "fixture" ? "合成 / Fixture" : "真实 / Live"}</span><button className="button secondary" disabled={resource.value.next_cursor === null} onClick={() => { if (resource.value.next_cursor !== null) setFilters((current) => ({ ...current, cursor: resource.value.next_cursor ?? undefined })); }}>下一页</button></div>}
      <div className="panel-actions"><a className="button secondary" href="#sources">查看来源工作区</a></div>
    </section>
    {selection !== null && <EventDetail key={`${state.user.user_id}-${state.user.permission_version}-${selection.eventId}`} id={selection.eventId} onSessionExpired={expired} isCurrent={isCurrent} />}
  </div><EvidenceInspector key={`${state.user.user_id}-${state.user.permission_version}-${selection?.evidenceId ?? "none"}-${selection?.revisionId ?? "none"}`} id={selection?.evidenceId ?? null} revisionId={selection?.revisionId ?? null} onSessionExpired={expired} isCurrent={isCurrent} /></div>;
}
