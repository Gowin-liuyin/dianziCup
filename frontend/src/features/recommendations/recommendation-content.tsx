import type { Citation, Freshness } from "../../api/knowledge-contracts";
import { formatShanghaiTimestamp } from "../../app/date-time";
import { SavedAssessmentEvidence, SavedCitation } from "./saved-citation";
import type { EvidenceReference } from "./recommendation-wire-types";

type ReasonCode = "product_match" | "risk_topic_match" | "asset_assessment" | "high_consequence";
type AssessmentStatus = "supported_applicability" | "excluded_with_evidence" | "insufficient_evidence" | "conflicting_evidence";

/** 冻结 pure contracts.py 的展示字段；尚不是公开 HTTP 响应解析器。 */
export interface RecommendationContent {
  key: { subscription_id: string; event_id: string; material_version: string };
  kind: "supported_risk" | "prioritize_verification" | "excluded_with_evidence" | "intelligence_update";
  priority_bucket: 0 | 1 | 2 | 3;
  reasons: { code: ReasonCode; matched_key: string; claim_id: string | null; citations: Citation[]; assessment_id: string | null }[];
  assessments: { assessment_id: string; asset_id: string; asset_snapshot_id: string; rule_id: string; rule_version: number; status: AssessmentStatus; evidence: EvidenceReference[]; missing_requirements: string[]; conflicts: string[]; limitations: string[] }[];
  observed_at: string;
  source_changed_at: string | null;
  validity_as_of: string;
  freshness_at_cutoff: Freshness;
  current_status: "supported" | "disputed" | "unverified" | "superseded" | "withdrawn";
  current_freshness: Freshness;
  current_state_checked_at: string;
  limitations: string[];
}

const kindLabels: Record<RecommendationContent["kind"], string> = { supported_risk: "有依据的影响", prioritize_verification: "优先核验", excluded_with_evidence: "有证据排除", intelligence_update: "情报更新" };
const reasonLabels: Record<ReasonCode, string> = { product_match: "产品关注匹配", risk_topic_match: "风险主题匹配", asset_assessment: "授权资产研判", high_consequence: "高影响后果依据" };
const assessmentLabels: Record<AssessmentStatus, string> = { supported_applicability: "支持适用", excluded_with_evidence: "证据排除", insufficient_evidence: "证据不足", conflicting_evidence: "证据冲突" };
const freshnessLabels: Record<Freshness, string> = { current: "当前", stale: "已过期", unknown: "未知" };
const claimLabels: Record<RecommendationContent["current_status"], string> = { supported: "有支持依据", disputed: "存在冲突", unverified: "未核验", superseded: "已被后续版本替代", withdrawn: "已撤回" };

function SavedTime({ value }: { value: string | null }) { return value === null ? <span>未知 / 未留存</span> : <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>; }

export function RecommendationContentView({ content }: { content: RecommendationContent }) {
  return <div className="recommendation-content"><div className="recommendation-item-heading"><strong>{kindLabels[content.kind]}</strong><span className="recommendation-tag">P{content.priority_bucket}</span></div><a className="text-link" href={`#events/${content.key.event_id}`}>核查事件 <code>{content.key.event_id}</code></a>
    <dl className="recommendation-meta"><dt>实质变化版本</dt><dd><code>{content.key.material_version}</code></dd><dt>首次实质观察</dt><dd><SavedTime value={content.observed_at} /></dd><dt>来源修订时间</dt><dd><SavedTime value={content.source_changed_at} /></dd><dt>冻结判断时刻</dt><dd><SavedTime value={content.validity_as_of} /></dd><dt>冻结时效</dt><dd>{freshnessLabels[content.freshness_at_cutoff]}</dd></dl>
    <h3>推荐理由与支持依据</h3><ul className="recommendation-reasons">{content.reasons.map((reason, index) => <li key={`${reason.code}:${reason.matched_key}:${index}`}><strong>{reasonLabels[reason.code]}</strong><p>匹配关注：<code>{reason.matched_key}</code></p>{reason.claim_id !== null && <p>事实记录：<code>{reason.claim_id}</code></p>}{reason.assessment_id !== null && <p>研判收据：<code>{reason.assessment_id}</code></p>}{reason.citations.map((citation) => <SavedCitation key={`${citation.evidence_id}:${citation.revision_id}`} eventId={content.key.event_id} citation={citation} />)}</li>)}</ul>
    {content.assessments.map((assessment) => <section className="recommendation-assessment" key={assessment.assessment_id}><h3>资产依据 · {assessmentLabels[assessment.status]}</h3><dl className="recommendation-meta"><dt>授权资产</dt><dd><a className="text-link" href={`#assets/${assessment.asset_id}`}><code>{assessment.asset_id}</code></a></dd><dt>固定快照</dt><dd><code>{assessment.asset_snapshot_id}</code></dd><dt>研判收据</dt><dd><code>{assessment.assessment_id}</code></dd><dt>发布规则</dt><dd><code>{assessment.rule_id}</code> · 版本 {assessment.rule_version}</dd></dl>{assessment.evidence.map((evidence) => <SavedAssessmentEvidence key={`${evidence.evidence_id}:${evidence.revision_id}:${evidence.block_id}:${evidence.start_offset}:${evidence.support_kind}`} eventId={content.key.event_id} evidence={evidence} />)}{assessment.missing_requirements.length > 0 && <p className="recommendation-boundary">证据缺口：{assessment.missing_requirements.join("；")}</p>}{assessment.conflicts.length > 0 && <p className="recommendation-boundary">冲突：{assessment.conflicts.join("；")}</p>}{assessment.limitations.length > 0 && <p className="small-note">研判限制：{assessment.limitations.join("；")}</p>}</section>)}
    <details className="recommendation-current-history"><summary>生成时保存的当前状态</summary><dl className="recommendation-meta"><dt>事实状态</dt><dd>{claimLabels[content.current_status]}</dd><dt>时效</dt><dd>{freshnessLabels[content.current_freshness]}</dd><dt>当时检查时刻</dt><dd><SavedTime value={content.current_state_checked_at} /></dd></dl><p className="small-note">这些字段保留生成时的记录；本次读取的有效性以单独的当前状态为准。</p></details>
    {content.kind === "prioritize_verification" && <p className="recommendation-boundary">优先核验表示证据仍需核对，不能解释为已经确认影响。</p>}{content.kind === "excluded_with_evidence" && <p className="recommendation-boundary">证据排除只针对上述固定快照与规则范围，不能解释为绝对安全。</p>}{content.limitations.length > 0 && <p className="small-note">范围限制：{content.limitations.join("；")}</p>}
  </div>;
}

export const currentValidityLabels = { current: "当前有效", stale: "已过期，待重新核对", withdrawn: "已撤回", unknown: "当前有效性未知" };
export function CurrentValidity({ status, reason, checkedAt }: { status: "current" | "stale" | "withdrawn" | "unknown"; reason: string; checkedAt: string }) {
  return <div className="report-current"><span className={`recommendation-tag is-${status}`}>{currentValidityLabels[status]}</span><p>当前检查原因：{reason}</p><p>本次核对 <SavedTime value={checkedAt} /></p>{status !== "current" && <p className="recommendation-boundary">以下为保存的历史内容，请勿作为当前有效结论使用。</p>}</div>;
}
