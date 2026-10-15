import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiProblem, publicProblem } from "../../api/client";
import { getDocumentDetail, getDocumentList, getDocumentRevisions, type DocumentFilters } from "../../api/document-client";
import { documentKinds, sourceCategories, type ContentCoverage, type DocumentDetailResponse, type DocumentKind, type DocumentListResponse, type DocumentRevisionsResponse, type DocumentSummary, type SourceCategory } from "../../api/document-contracts";
import type { EvidenceResponse } from "../../api/knowledge-contracts";
import { useAuthSession } from "../../app/auth-session";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { readDocumentSelection } from "../../app/workspace-navigation";
import { EmptyState, ErrorPanel, StatusBadge } from "../../components/status";
import "./documents.css";

type Resource<T> = { kind: "loading" } | { kind: "loaded"; value: T } | { kind: "failed"; error: ApiProblem };
const kindLabels: Record<DocumentKind, string> = { advisory: "安全公告", paper: "论文", standard: "技术标准", policy: "政策法规", article: "研究文章", repository_record: "仓库记录" };
const categoryLabels: Record<SourceCategory, string> = { structured_vulnerability: "结构化漏洞库", vendor_advisory: "厂商公告", security_community: "安全社区", code_repository: "代码仓库", technical_blog: "技术博客", academic_paper: "学术论文", technical_standard: "技术标准", policy_regulation: "政策法规" };
const coverageLabels: Record<ContentCoverage, string> = { full_text: "全文", abstract: "仅摘要", feed_excerpt: "订阅片段", metadata: "仅元数据", unknown: "覆盖未知" };
const parseLabels: Record<DocumentSummary["parse_status"], string> = { pending: "待解析", parsed: "已解析", partial: "部分解析", failed: "解析失败", legacy_unverified: "历史解析未核验" };
const locatorLabels: Record<EvidenceResponse["locator_kind"], string> = { text: "文本位置", pdf_page: "PDF 页码", json_pointer: "JSON 位置", legacy_unverified: "历史定位未核验" };
function modeLabel(mode: "live" | "fixture"): string { return mode === "live" ? "真实 / Live" : "合成 / Fixture"; }
function SavedTime({ value }: { value: string | null }) { return value === null ? <span className="unknown-value">未知 / 未留存</span> : <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>; }
function Publication({ document }: { document: DocumentSummary }) {
  if (document.published_precision === "instant") return <><SavedTime value={document.source_published_at} /><span className="small-note">精确时刻</span></>;
  return <><span>{document.published_at_raw ?? "未知 / 未留存"}</span><span className="small-note">{document.published_precision === "calendar_date" ? "仅日期 · 时刻未知" : "精度未知"}</span></>;
}
function DocumentError({ error, collection = false, onRetry }: { error: ApiProblem; collection?: boolean; onRetry: () => void }) {
  let title = "查询未完成";
  let message = error.message;
  if (error.status === 404) { title = collection ? "资料服务待接通" : "资料或版本不可访问"; message = collection ? "当前入口未取得资料结果，不能解释为空。" : "资料或修订不存在，或当前会话无法查看。没有展示缓存标题。"; }
  if (error.status === 403) { title = "没有资料查看权限"; message = "当前授权不允许查看资料，请核对团队权限。未展示记录标题或数量。"; }
  if (error.status === 503) { title = "资料依赖暂不可用"; message = "本次读取失败，不能据此判断为空或无风险。恢复服务后请重新查询。"; }
  return <div className="resource-error"><h3>{title}</h3><ErrorPanel error={error} message={message} onRetry={error.status === 403 ? undefined : onRetry} retryLabel="重新查询资料" /></div>;
}
function EvidenceBlock({ evidence, index }: { evidence: EvidenceResponse; index: number }) {
  return <article className="document-evidence">
    <div className="document-evidence-heading"><h4>原文片段 {index + 1}</h4><span className="small-note">{evidence.verified_at === null ? "定位未核验" : "定位已核验"}</span></div>
    <blockquote>{evidence.quote_text}</blockquote>
    <details><summary>展开定位与证据记录</summary><dl className="document-metadata">
      <dt>证据标识</dt><dd><code>{evidence.span_id}</code></dd><dt>原文修订</dt><dd><code>{evidence.revision_id}</code></dd>
      <dt>定位方式</dt><dd>{locatorLabels[evidence.locator_kind]}</dd><dt>Unicode 范围</dt><dd><code>[{evidence.start_offset}, {evidence.end_offset})</code></dd>
      <dt>PDF 页码</dt><dd>{evidence.page_number ?? "不适用 / 未留存"}</dd><dt>JSON 位置</dt><dd><code>{evidence.json_pointer ?? "不适用 / 未留存"}</code></dd>
      <dt>片段哈希</dt><dd><code>{evidence.quote_sha256}</code></dd><dt>定位核验时间</dt><dd><SavedTime value={evidence.verified_at} /></dd>
    </dl></details>
  </article>;
}

function DocumentInspector({ id, revisionId, isCurrent, onExpired }: { id: string; revisionId: string | null; isCurrent: () => boolean; onExpired: () => void }) {
  const [resource, setResource] = useState<Resource<DocumentDetailResponse>>({ kind: "loading" });
  const [request, setRequest] = useState({ offset: 0, retry: 0 });
  const [pending, setPending] = useState(true);
  const [pageError, setPageError] = useState<ApiProblem | null>(null);
  const selectedRevision = useRef(revisionId);
  const inspector = useRef<HTMLElement>(null);
  const focused = useRef(false);
  const [history, setHistory] = useState<Resource<DocumentRevisionsResponse>>({ kind: "loading" });
  const [historyRequest, setHistoryRequest] = useState({ offset: 0, retry: 0 });
  const [historyPending, setHistoryPending] = useState(true);
  const [historyError, setHistoryError] = useState<ApiProblem | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setPending(true); setPageError(null);
    if (request.offset === 0) setResource({ kind: "loading" });
    void getDocumentDetail(id, selectedRevision.current, request.offset, controller.signal).then((value) => {
      if (controller.signal.aborted || !isCurrent()) return;
      selectedRevision.current = value.document.revision_id;
      setResource((previous) => {
        if (request.offset === 0 || previous.kind !== "loaded") return { kind: "loaded", value };
        const combined = [...previous.value.evidence, ...value.evidence];
        if (previous.value.data_mode !== value.data_mode || new Set(combined.map((span) => span.span_id)).size !== combined.length || combined.length > value.evidence_total) return { kind: "failed", error: new ApiProblem(502, "invalid_response", true) };
        return { kind: "loaded", value: { ...value, evidence: combined } };
      });
      setPending(false);
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure); setPending(false);
      if (request.offset > 0 && error.status !== 401 && error.status !== 403 && error.status !== 404) setPageError(error);
      else setResource({ kind: "failed", error });
      if (error.status === 401) onExpired();
    });
    return () => controller.abort();
  }, [id, request, isCurrent, onExpired]);

  useEffect(() => {
    const controller = new AbortController(); setHistoryPending(true); setHistoryError(null);
    void getDocumentRevisions(id, historyRequest.offset, controller.signal).then((value) => {
      if (controller.signal.aborted || !isCurrent()) return;
      setHistory((previous) => {
        if (historyRequest.offset === 0 || previous.kind !== "loaded") return { kind: "loaded", value };
        const items = [...previous.value.items, ...value.items];
        if (previous.value.data_mode !== value.data_mode || new Set(items.map((item) => item.revision_id)).size !== items.length) return { kind: "failed", error: new ApiProblem(502, "invalid_response", true) };
        return { kind: "loaded", value: { ...value, items } };
      }); setHistoryPending(false);
    }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure); setHistoryPending(false);
      if (historyRequest.offset > 0 && error.status !== 401 && error.status !== 403 && error.status !== 404) setHistoryError(error);
      else setHistory({ kind: "failed", error });
      if (error.status === 401) onExpired();
    });
    return () => controller.abort();
  }, [id, historyRequest, isCurrent, onExpired]);

  useEffect(() => {
    if (resource.kind !== "loaded" || focused.current) return;
    focused.current = true;
    inspector.current?.focus({ preventScroll: true });
    inspector.current?.scrollIntoView?.({ block: "start", behavior: "instant" });
  }, [resource.kind]);

  return <section ref={inspector} tabIndex={-1} className="panel document-inspector" aria-labelledby="document-detail-title">
    <div className="panel-heading"><h2 id="document-detail-title">资料检视</h2><a className="text-link" href="#documents">关闭详情</a></div>
    {resource.kind === "loading" && <p className="loading-state" role="status">正在取得资料版本与原文…</p>}
    {resource.kind === "failed" && <DocumentError error={resource.error} onRetry={() => setRequest({ offset: 0, retry: request.retry + 1 })} />}
    {resource.kind === "loaded" && <div className="document-detail-body">
      <p className="document-mode">{modeLabel(resource.value.data_mode)} · {kindLabels[resource.value.document.document_kind]} · {resource.value.document.is_current ? "当前版本" : "历史版本"}</p>
      <h3 className="document-title">{resource.value.document.title}</h3>
      <div className="document-flags"><span>修订 {resource.value.document.revision_number}</span><span>{parseLabels[resource.value.document.parse_status]}</span><span>{coverageLabels[resource.value.document.content_coverage]}</span></div>
      {!resource.value.document.is_current && <p className="document-boundary">正在查看保存的历史修订，标题和证据属于此版本。<a href={`#documents/${id}`}>查看当前版本 →</a></p>}
      <dl className="document-metadata"><dt>来源</dt><dd>{resource.value.document.source_name}</dd><dt>来源类别</dt><dd>{categoryLabels[resource.value.document.source_category]}</dd>
        <dt>文档标识</dt><dd><code>{id}</code></dd><dt>原文修订</dt><dd><code>{resource.value.document.revision_id}</code></dd>
        <dt>发布日期精度</dt><dd className="document-date"><Publication document={resource.value.document} /></dd><dt>源发布时间</dt><dd><SavedTime value={resource.value.document.source_published_at} /></dd>
        <dt>源修订时间</dt><dd><SavedTime value={resource.value.document.source_modified_at} /></dd><dt>首次观察</dt><dd><SavedTime value={resource.value.document.first_observed_at} /></dd><dt>入库完成</dt><dd><SavedTime value={resource.value.document.ingested_at} /></dd>
        <dt>许可</dt><dd>{resource.value.license_identifier ?? "未知 / 未留存"}{resource.value.license_uri && <a className="text-link" href={resource.value.license_uri} target="_blank" rel="noopener noreferrer">查看许可原文 ↗</a>}</dd>
      </dl>
      {resource.value.document.canonical_uri ? <a className="button secondary" href={resource.value.document.canonical_uri} target="_blank" rel="noopener noreferrer">打开此版本来源地址 ↗</a> : <p className="small-note">此版本来源地址未留存或不可安全展示。</p>}
      {resource.value.source_notes.length > 0 && <div className="document-source-notes"><h4>来源与覆盖说明</h4>{resource.value.source_notes.map((note, index) => <p key={index}>{note}</p>)}</div>}
      <div className="document-history"><h4>选择保存的版本</h4>
        {history.kind === "loading" && <p role="status" className="small-note">正在取得版本记录…</p>}
        {history.kind === "failed" && <DocumentError error={history.error} onRetry={() => setHistoryRequest({ offset: 0, retry: historyRequest.retry + 1 })} />}
        {history.kind === "loaded" && <><label htmlFor="document-revision">原文修订版本</label><select id="document-revision" value={resource.value.document.revision_id} onChange={(event) => { window.location.hash = `#documents/${id}/revision/${event.target.value}`; }}>
          {!history.value.items.some((item) => item.revision_id === resource.value.document.revision_id) && <option value={resource.value.document.revision_id}>正在检视：修订 {resource.value.document.revision_number}</option>}
          {history.value.items.map((item) => <option key={item.revision_id} value={item.revision_id}>修订 {item.revision_number} · {item.is_current ? "当前" : "历史"} · {item.title}</option>)}
        </select><p className="small-note">已取得 {history.value.items.length} 个版本 · {history.value.next_offset === null ? "本次版本查询已结束" : "还有版本未加载"}</p>
          {history.value.next_offset !== null && <button className="button secondary" disabled={historyPending} onClick={() => setHistoryRequest({ offset: history.value.next_offset ?? 0, retry: 0 })}>{historyPending ? "加载版本中…" : "加载更多历史版本"}</button>}
        </>}
        {historyError && <ErrorPanel error={historyError} message="后续历史版本读取失败，已取得的版本仍在此处；版本记录尚未完整。" onRetry={() => setHistoryRequest((value) => ({ ...value, retry: value.retry + 1 }))} />}
      </div>
      <div className="document-text-heading"><h4>原文与证据片段</h4><span className="small-note">已取得 {resource.value.evidence.length} / {resource.value.evidence_total} 段</span></div>
      <p className="document-boundary">引文存在不等于内容支持。资料中的主张尚不能作为本系统确认的风险结论。</p>
      {resource.value.document.content_coverage !== "full_text" && <p className="document-coverage-note">{resource.value.document.content_coverage === "unknown" ? "正文覆盖范围未知，不能认定已保存全文。" : `覆盖：${coverageLabels[resource.value.document.content_coverage]}。未保存完整正文。`}</p>}
      {resource.value.evidence.length === 0 && <EmptyState title="没有可定位的原文片段" description="该版本尚未返回可核查正文。请结合覆盖说明与原文链接检查，不能解释为没有相关风险。" />}
      {resource.value.evidence.map((span, index) => <EvidenceBlock key={span.span_id} evidence={span} index={index} />)}
      {pageError && <ErrorPanel error={pageError} message="后续原文读取失败，已取得的片段不代表全文；本次证据尚未完整。" onRetry={() => setRequest((value) => ({ ...value, retry: value.retry + 1 }))} />}
      {resource.value.next_evidence_offset !== null && <button className="button secondary document-more" disabled={pending} onClick={() => setRequest({ offset: resource.value.next_evidence_offset ?? 0, retry: 0 })}>{pending ? "加载原文中…" : "加载更多原文片段"}</button>}
    </div>}
  </section>;
}

/** 资料只读投影沿用认证代次；换会话、换版本或权限拒绝时不显示旧资料。 */
export function DocumentWorkspace() {
  const { state, error: sessionError, actionPending, sessionGeneration, expireSession, isSessionCurrent } = useAuthSession();
  const [selection, setSelection] = useState(() => readDocumentSelection(window.location.hash));
  const [filters, setFilters] = useState<DocumentFilters>({ limit: 20 });
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<DocumentKind | "">("");
  const [category, setCategory] = useState<SourceCategory | "">("");
  const [resource, setResource] = useState<Resource<DocumentListResponse>>({ kind: "loading" });
  const [retry, setRetry] = useState(0);
  const user = state.kind === "authenticated" ? state.user : null;
  const isCurrent = useCallback(() => isSessionCurrent(sessionGeneration), [isSessionCurrent, sessionGeneration]);
  const expired = useCallback(() => expireSession(sessionGeneration), [expireSession, sessionGeneration]);
  useEffect(() => { const navigate = () => setSelection(readDocumentSelection(window.location.hash)); window.addEventListener("hashchange", navigate); return () => window.removeEventListener("hashchange", navigate); }, []);
  useEffect(() => {
    if (user === null || actionPending) return;
    const controller = new AbortController(); setResource({ kind: "loading" });
    void getDocumentList(filters, controller.signal).then((value) => { if (!controller.signal.aborted && isCurrent()) setResource({ kind: "loaded", value }); }).catch((failure: unknown) => {
      if (controller.signal.aborted || !isCurrent()) return;
      const error = publicProblem(failure); setResource({ kind: "failed", error }); if (error.status === 401) expired();
    }); return () => controller.abort();
  }, [filters, retry, user, actionPending, isCurrent, expired]);
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSelection(null); window.history.replaceState(null, "", "#documents");
    setFilters({ q: query.trim(), document_kind: kind || undefined, source_category: category || undefined, limit: 20 });
  }
  if (user === null || actionPending) return <section className="panel document-anonymous">{sessionError?.code === "session_expired" && <ErrorPanel error={sessionError} />}<EmptyState title="登录后核查资料" description="资料与原文版本需要当前团队会话。尚未执行资料查询，不能判断资料数量。" /><a className="button" href="#session">登录并核对权限</a></section>;
  const status = resource.kind === "loading" ? "loading" : resource.kind === "failed" ? (resource.error.status === 403 ? "denied" : "failed") : resource.value.items.length === 0 ? "no_result" : "loaded";
  return <div className="document-workspace"><section className="panel document-catalog" aria-labelledby="document-list-title">
    <div className="panel-heading"><h2 id="document-list-title">已保存资料</h2><StatusBadge state={status} /></div>
    <form className="document-search" onSubmit={search} aria-label="资料筛选"><label htmlFor="document-query">检索关键词<input id="document-query" value={query} onChange={(event) => setQuery(event.target.value)} maxLength={500} placeholder="已保存资料的标题关键词" /></label>
      <div className="document-filter-row"><label htmlFor="document-kind">资料类型<select id="document-kind" aria-label="资料类型" value={kind} onChange={(event) => setKind(documentKinds.find((value) => value === event.target.value) ?? "")}><option value="">全部资料</option>{documentKinds.map((value) => <option key={value} value={value}>{kindLabels[value]}</option>)}</select></label>
      <label htmlFor="document-category">来源类别<select id="document-category" aria-label="来源类别" value={category} onChange={(event) => setCategory(sourceCategories.find((value) => value === event.target.value) ?? "")}><option value="">全部来源类别</option>{sourceCategories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></label></div>
      <button className="button" type="submit" disabled={resource.kind === "loading"}>检索资料</button><p className="small-note">仅检索已保存标题。资料覆盖与风险确认分别核查。</p>
    </form>
    {resource.kind === "loading" && <p role="status" className="loading-state">正在查询授权范围内的资料…</p>}
    {resource.kind === "failed" && <DocumentError error={resource.error} collection onRetry={() => setRetry((value) => value + 1)} />}
    {resource.kind === "loaded" && <><p className="document-page-count">本页 {resource.value.items.length} 条 · {modeLabel(resource.value.data_mode)}</p>
      {resource.value.items.length === 0 && <EmptyState title="本次查询没有资料记录" description="本次授权范围与筛选没有返回资料，不能推论相关研究或风险不存在。" />}
      <ul className="document-list" aria-label="已保存资料列表">{resource.value.items.map((document) => <li key={document.document_id} className={selection?.documentId === document.document_id ? "document-selected" : undefined}>
        <div className="document-record-kind"><span>{kindLabels[document.document_kind]}</span><span>{coverageLabels[document.content_coverage]}</span></div>
        <a href={`#documents/${document.document_id}`} className="document-record-link" aria-current={selection?.documentId === document.document_id ? "true" : undefined}>{document.title}</a>
        <p className="document-record-source">{document.source_name} · 修订 {document.revision_number}</p><div className="document-date"><Publication document={document} /></div>
      </li>)}</ul>
      <div className="document-pagination"><button className="button secondary" disabled={filters.cursor === undefined} onClick={() => setFilters((value) => ({ ...value, cursor: undefined }))}>回到第一页</button><button className="button secondary" disabled={resource.value.next_cursor === null} onClick={() => { setSelection(null); window.history.replaceState(null, "", "#documents"); setFilters((value) => ({ ...value, cursor: resource.value.next_cursor ?? undefined })); }}>下一页资料</button></div>
    </>}
  </section>
    {selection === null ? <aside className="panel document-prompt"><p className="eyebrow">原文核查</p><h2>读资料<br />留意证据范围</h2><p>选择资料，核查保存的版本、发布时间精度与原文覆盖。</p><dl><dt>论文</dt><dd>研究主张与确认事实分别核查。</dd><dt>标准与政策</dt><dd>版本、建议、义务和适用范围以原文为准。</dd><dt>原文证据</dt><dd>定位已核验仍需确认片段是否支持论断。</dd></dl><p className="document-boundary">未知保持未知</p></aside> : <DocumentInspector key={`${selection.documentId}:${selection.revisionId}`} id={selection.documentId} revisionId={selection.revisionId} isCurrent={isCurrent} onExpired={expired} />}
  </div>;
}
