import type { Citation } from "../../api/knowledge-contracts";
import type { ReactNode } from "react";
import type { EvidenceReference } from "./recommendation-wire-types";

function SavedEvidenceSpan({ eventId, evidenceId, revisionId, quote, locator, children }: { eventId: string; evidenceId: string; revisionId: string; quote: string; locator: string; children?: ReactNode }) {
  return <div className="recommendation-evidence"><blockquote>{quote}</blockquote><span className="small-note">原文定位：{locator}</span>{children}<a href={`#events/${eventId}/evidence/${evidenceId}/revision/${revisionId}`}>核查保存的原文版本 <code>{revisionId}</code></a></div>;
}

/** 引用直接打开保存的事件/证据/修订，正文仅作为文本渲染。 */
export function SavedCitation({ eventId, citation }: { eventId: string; citation: Citation }) {
  return <SavedEvidenceSpan eventId={eventId} evidenceId={citation.evidence_id} revisionId={citation.revision_id} quote={citation.quote} locator={citation.locator} />;
}

const supportLabels: Record<EvidenceReference["support_kind"], string> = { supports: "支持关系", refutes: "反驳关系", context: "上下文材料" };

/** 资产收据保存的证据独立呈现关系与核验状态；不构造未提供的来源地址。 */
export function SavedAssessmentEvidence({ eventId, evidence }: { eventId: string; evidence: EvidenceReference }) {
  return <SavedEvidenceSpan eventId={eventId} evidenceId={evidence.evidence_id} revisionId={evidence.revision_id} quote={evidence.quote_text} locator={`${evidence.block_id} · Unicode [${evidence.start_offset}, ${evidence.end_offset})`}>
    <dl className="recommendation-meta"><dt>证据关系</dt><dd>{supportLabels[evidence.support_kind]}</dd><dt>核验状态</dt><dd>{evidence.validation_status === "validated" ? "已核验" : "未核验，不能作为已确认依据"}</dd></dl>
    <p className="small-note">引文存在不等于内容支持；上下文材料不作为支持或排除依据。</p>
  </SavedEvidenceSpan>;
}
