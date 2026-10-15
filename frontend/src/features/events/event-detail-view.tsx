import { useRef } from "react";
import type { Citation, ClaimOrigin, ClaimStatus, ClaimSummary, DimensionName, DimensionStatus, Enrichment, EventDetailResponse, RevisionSummary } from "../../api/knowledge-contracts";
import { EmptyState } from "../../components/status";
import { FreshnessBadge, SavedTime } from "./event-display";

const dimensionLabels: Record<DimensionName, string> = { cvss: "CVSS 评分", epss: "EPSS 可能性", kev: "KEV 目录", cwe: "CWE 弱点", atlas: "ATLAS 映射", versions: "影响版本", literature: "论文关联", poc: "PoC 核查", exposure: "暴露统计" };
const dimensionNames: readonly DimensionName[] = ["cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"];
const dimensionStatusLabels: Record<DimensionStatus, string> = { available: "已取得", not_found: "未发现", not_applicable: "不适用", conflict: "有冲突", blocked: "受阻", failed: "失败", pending: "待处理" };
const dimensionStatusNotes: Record<DimensionStatus, string> = {
  available: "已保存此维度的引用，具体支撑关系仍以来源断言为准。",
  not_found: "在已查询范围内未发现结果，不能据此排除风险。",
  not_applicable: "服务将此维度标为不适用，不代表其他维度没有风险。",
  conflict: "来源存在冲突，保留各项断言，不在页面自动裁决。",
  blocked: "此维度的处理受阻，已保存的其他信息仍可核查。",
  failed: "此维度处理失败，不能把失败解释为未发现。",
  pending: "此维度尚待处理，当前没有完成结论。",
};
const claimStatusLabels: Record<ClaimStatus, string> = { supported: "有证据支持", disputed: "有争议", unverified: "未核验", superseded: "已被新版本替代", withdrawn: "已撤回" };
const originLabels: Record<ClaimOrigin, string> = { source_explicit: "原文明示", structured_source: "结构化来源", rule_derived: "规则推导", model_hypothesis: "模型假设", human_confirmed: "人工确认" };
const revisionParseLabels: Record<RevisionSummary["parse_status"], string> = { pending: "待解析", parsed: "已解析", partial: "部分解析", failed: "解析失败", legacy_unverified: "历史解析未核验" };
const documentKindLabels: Record<RevisionSummary["document_kind"], string> = { advisory: "安全公告", article: "技术文章", paper: "论文", repository_record: "仓库记录", standard: "标准", policy: "政策" };

function evidenceHref(eventId: string, evidenceId: string, revisionId: string | null): string {
  return `#events/${eventId}/evidence/${evidenceId}${revisionId === null ? "" : `/revision/${revisionId}`}`;
}

function ClaimState({ claim, inDimension = false }: { claim: ClaimSummary; inDimension?: boolean }) {
  return <><span className={`claim-status claim-status-${claim.status}`}>{claimStatusLabels[claim.status]}</span><span className="claim-origin">{inDimension ? `依据：${originLabels[claim.origin]}` : originLabels[claim.origin]}</span></>;
}

function DimensionResult({ dimension, claims, eventId, selectedEvidenceId, selectedRevisionId }: { dimension: Enrichment; claims: ClaimSummary[]; eventId: string; selectedEvidenceId: string | null; selectedRevisionId: string | null }) {
  const linkedClaims = claims.filter((claim) => dimension.claim_ids.includes(claim.claim_id));
  const missingClaimCount = dimension.claim_ids.filter((claimId) => !claims.some((claim) => claim.claim_id === claimId)).length;
  const provenance = <dl className="dimension-provenance"><dt>观测时刻</dt><dd><SavedTime value={dimension.observed_at} /></dd><dt>来源版本</dt><dd>{dimension.source_version ?? "未提供"}</dd></dl>;
  return <div className="dimension-result" data-status={dimension.status}>
    <div className="dimension-state-line"><span className={`dimension-status dimension-status-${dimension.status}`}>{dimensionStatusLabels[dimension.status]}</span><FreshnessBadge value={dimension.freshness} /></div>
    <p className="dimension-state-note">{dimensionStatusNotes[dimension.status]}</p>
    {linkedClaims.map((claim) => <div className="dimension-claim" key={claim.claim_id}><div className="dimension-claim-state"><ClaimState claim={claim} inDimension /></div><p className="dimension-value">{claim.display_value}</p><button type="button" className="text-link dimension-fact-link" onClick={() => { const element = document.getElementById(`claim-${claim.claim_id}`); element?.focus({ preventScroll: true }); element?.scrollIntoView?.({ block: "start", behavior: "instant" }); }}>查看断言与依据</button></div>)}
    {linkedClaims.length === 0 && <p className="dimension-value-missing">未提供可展示的关联事实值</p>}
    {missingClaimCount > 0 && <p className="dimension-state-note">有 {missingClaimCount} 条关联断言未在本次响应中提供，无法展示其值。</p>}
    {dimension.observed_at === null && dimension.source_version === null ? <details className="dimension-observation"><summary>观测时刻与来源版本</summary>{provenance}</details> : provenance}
    {dimension.error_code && <p className="dimension-error">错误代码 <code>{dimension.error_code}</code></p>}
    {dimension.citations.length > 0 && <div className="dimension-citations">{dimension.citations.map((citation, index) => <div className="dimension-citation" key={`${citation.evidence_id}-${citation.revision_id}-${index}`}>
      <a className="text-link" href={evidenceHref(eventId, citation.evidence_id, citation.revision_id)} aria-current={selectedEvidenceId === citation.evidence_id && selectedRevisionId === citation.revision_id ? "location" : undefined}>查看引用：{citation.locator}</a>
      <details><summary>展开原文摘录</summary><p className="citation-excerpt">{citation.quote}</p><span className="small-note">修订 <code>{citation.revision_id}</code></span></details>
    </div>)}</div>}
  </div>;
}

function RevisionEntry({ revision, detail }: { revision: RevisionSummary; detail: EventDetailResponse }) {
  const revisionEvidence = new Map<string, Pick<Citation, "evidence_id" | "revision_id">>();
  for (const dimension of detail.dimensions) {
    for (const citation of dimension.citations) {
      if (citation.revision_id === revision.revision_id) revisionEvidence.set(citation.evidence_id, citation);
    }
  }
  for (const claim of detail.claims) {
    if (claim.source_revision_id === revision.revision_id) {
      for (const evidenceId of claim.evidence_ids) revisionEvidence.set(evidenceId, { evidence_id: evidenceId, revision_id: revision.revision_id });
    }
  }
  return <article className="revision-entry" aria-label={`修订 ${revision.revision_number} ${revision.revision_id}`}>
    <div className="revision-entry-title"><strong>修订 {revision.revision_number}</strong><span className={`revision-parse revision-parse-${revision.parse_status}`}>{revisionParseLabels[revision.parse_status]}</span></div>
    <p className="revision-kind">{documentKindLabels[revision.document_kind]}{detail.event.latest_revision_id === revision.revision_id && <span className="revision-latest">事件指向的最新修订</span>}</p>
    <dl className="evidence-metadata revision-identifiers"><dt>原文修订</dt><dd><code>{revision.revision_id}</code></dd><dt>文档</dt><dd><code>{revision.document_id}</code></dd><dt>来源</dt><dd><code>{revision.source_id}</code></dd></dl>
    <dl className="evidence-metadata"><dt>源发布时间</dt><dd><SavedTime value={revision.source_published_at} /></dd><dt>源修订时间</dt><dd><SavedTime value={revision.source_modified_at} /></dd><dt>首次观察</dt><dd><SavedTime value={revision.first_observed_at} /></dd><dt>入库完成</dt><dd><SavedTime value={revision.ingested_at} /></dd></dl>
    <div className="citation-links">{[...revisionEvidence.values()].map((citation, index) => <a key={citation.evidence_id} href={evidenceHref(detail.event.event_id, citation.evidence_id, citation.revision_id)}>此修订的原文片段 [{index + 1}]</a>)}</div>
    {revisionEvidence.size === 0 && <p className="small-note">此响应未提供该修订的可定位片段。</p>}
    {revision.canonical_uri ? <><a className="text-link" href={revision.canonical_uri} target="_blank" rel="noopener noreferrer">打开留存来源地址 ↗</a><p className="small-note revision-link-note">外部地址可能已修订；历史引用以上方保存片段为准。</p></> : <p className="small-note">该历史版本原文地址未留存</p>}
  </article>;
}

/** 按冻结投影展示关联值与版本，不生成维度数值、裁决或任务状态。 */
export function EventDetailView({ detail, selectedEvidenceId, selectedRevisionId }: { detail: EventDetailResponse; selectedEvidenceId: string | null; selectedRevisionId: string | null }) {
  const dimensionsSection = useRef<HTMLElement>(null);
  const claimsSection = useRef<HTMLElement>(null);
  const revisionsSection = useRef<HTMLElement>(null);
  function showSection(section: HTMLElement | null) {
    section?.focus({ preventScroll: true });
    section?.scrollIntoView?.({ block: "start", behavior: "instant" });
  }
  return <div className="event-detail-body">
    <header className="event-context"><div className="event-title"><h3>{detail.event.title}</h3><FreshnessBadge value={detail.event.freshness} /><span className={`event-data-mode event-data-mode-${detail.data_mode}`}>{detail.data_mode === "fixture" ? "合成 / Fixture" : "真实 / Live"}</span></div>
      <p className="event-public-ids">{detail.event.external_ids.length > 0 ? detail.event.external_ids.join(" · ") : "未提供公开标识"}</p>
      <dl className="event-context-metadata"><dt>事件类型</dt><dd>{detail.event.event_type}</dd><dt>保存状态</dt><dd>{detail.event.status}</dd><dt>可见来源</dt><dd>{detail.event.source_count}</dd><dt>首次发现</dt><dd><SavedTime value={detail.event.first_seen_at} /></dd></dl>
      <details className="event-identifiers"><summary>事件标识与关联产品</summary><code className="record-id">{detail.event.event_id}</code><p className="small-note">关联产品标识</p>{detail.event.primary_product_ids.length > 0 ? detail.event.primary_product_ids.map((productId) => <code className="record-id" key={productId}>{productId}</code>) : <p className="small-note">未提供产品标识</p>}</details>
      {detail.event.freshness !== "current" && <p className="event-freshness-note">{detail.event.freshness === "stale" ? "事件已标为过期；以下保留已保存的信息，不能当作当前结论。" : "事件时效未知；请结合来源版本与观测时间核查。"}</p>}
      <a className="button secondary" href={`#questions/${detail.event.event_id}`}>基于此事件提问 →</a>
    </header>
    <nav className="event-section-navigation" aria-label="事件详情阅读位置"><button type="button" onClick={() => showSection(dimensionsSection.current)}>九维富化</button><button type="button" onClick={() => showSection(claimsSection.current)}>事实与来源断言</button><button type="button" onClick={() => showSection(revisionsSection.current)}>原文修订时间线</button></nav>
    <section ref={dimensionsSection} tabIndex={-1} className="event-detail-section" aria-labelledby="event-dimensions-title"><h3 id="event-dimensions-title" className="detail-section-title">九维富化</h3>
      <p className="small-note">各维度独立记录状态。未返回的维度没有结果，不能解释为不适用或完成。显示值来自本次响应中的关联断言。</p>
      {dimensionNames.map((name) => { const dimensions = detail.dimensions.filter((dimension) => dimension.dimension === name); return <article className="dimension-row" key={name} aria-label={dimensionLabels[name]}><h4 className="dimension-name">{dimensionLabels[name]}</h4><div>{dimensions.length === 0 ? <span className="unknown-value">未提供该维度</span> : dimensions.map((dimension, index) => <DimensionResult key={`${name}-${index}`} dimension={dimension} claims={detail.claims} eventId={detail.event.event_id} selectedEvidenceId={selectedEvidenceId} selectedRevisionId={selectedRevisionId} />)}</div></article>; })}
    </section>
    <section ref={claimsSection} tabIndex={-1} className="event-detail-section" aria-labelledby="event-claims-title"><h3 id="event-claims-title" className="detail-section-title">事实与来源断言</h3>
      <p className="small-note">引文存在不等于内容支持。模型假设、已撤回和已被替代的断言保留各自状态。</p>
      <p className="manual-review-boundary">人工复核：当前只读接口未提供任务状态或确认入口。</p>
      {detail.claims.length === 0 && <EmptyState title="尚未取得事实记录" description="没有事实记录不代表不存在相关风险。" />}
      {detail.claims.map((claim) => <article className={`claim-row claim-row-${claim.status}`} id={`claim-${claim.claim_id}`} tabIndex={-1} key={claim.claim_id}><div><code>{claim.predicate}</code><ClaimState claim={claim} /></div><p>{claim.display_value}</p><p className="claim-revision">来源修订 <code>{claim.source_revision_id ?? "未提供"}</code></p><div className="citation-links">{claim.evidence_ids.map((evidenceId, index) => <a key={evidenceId} href={evidenceHref(detail.event.event_id, evidenceId, claim.source_revision_id)}>原文片段 [{index + 1}]</a>)}</div>{claim.evidence_ids.length === 0 && <p className="small-note">未提供可定位的原文片段。</p>}</article>)}
    </section>
    <section ref={revisionsSection} tabIndex={-1} className="event-detail-section" aria-labelledby="event-revisions-title"><h3 id="event-revisions-title" className="detail-section-title">原文修订时间线</h3>
      <p className="small-note">保留本次响应中的来源与修订顺序。修订号属于各自文档；这不是合并或重判的执行记录。</p>
      {detail.revisions.length === 0 && <EmptyState title="尚未取得修订记录" description="历史版本需要保存的原文与修订记录，不能由当前来源信息推测。" />}
      {detail.revisions.map((revision) => <RevisionEntry key={revision.revision_id} revision={revision} detail={detail} />)}
    </section>
  </div>;
}
