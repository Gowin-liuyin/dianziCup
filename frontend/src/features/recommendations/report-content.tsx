import { formatShanghaiTimestamp } from "../../app/date-time";
import { RecommendationContentView, type RecommendationContent } from "./recommendation-content";

/** ReportCandidate 冻结历史的展示字段；不会重算报告窗口或当前业务结论。 */
export interface ReportContent {
  subscription_id: string;
  policy_version: "r15-recommendation-policy-1";
  frequency: "day" | "week";
  window_start: string;
  cutoff_at: string;
  generated_at: string;
  temporal_mode: "as_of_cutoff";
  window_basis: "first_material_observed_at";
  supported_risks: RecommendationContent[];
  verification_items: RecommendationContent[];
  excluded_items: RecommendationContent[];
  intelligence_updates: RecommendationContent[];
  partial: boolean;
  continuation_keys: { subscription_id: string; event_id: string; material_version: string }[];
  stop_reason: "disabled" | "no_items_in_window" | "complete" | "item_budget";
  limitations: string[];
}

export function ReportContentView({ report }: { report: ReportContent }) {
  const sections = [{ label: "有依据的影响", items: report.supported_risks }, { label: "优先核验", items: report.verification_items }, { label: "有证据排除", items: report.excluded_items }, { label: "情报更新", items: report.intelligence_updates }];
  return <div className="report-content"><h3>{report.frequency === "day" ? "日报" : "周报"} · 保存的历史内容</h3><dl className="recommendation-meta"><dt>本人订阅</dt><dd><code>{report.subscription_id}</code></dd><dt>观察窗口起点</dt><dd><time dateTime={report.window_start}>{formatShanghaiTimestamp(report.window_start)}</time></dd><dt>数据截止时刻</dt><dd><time dateTime={report.cutoff_at}>{formatShanghaiTimestamp(report.cutoff_at)}</time></dd><dt>实际生成时刻</dt><dd><time dateTime={report.generated_at}>{formatShanghaiTimestamp(report.generated_at)}</time></dd><dt>排序策略版本</dt><dd><code>{report.policy_version}</code></dd></dl><p className="small-note">报告按截止时刻冻结；窗口依据首次实质观察时间，来源修订时间独立保留。生成时间不替代来源发布时间。</p>
    {report.partial && <p className="recommendation-boundary">报告仅包含本次预算内的部分记录，另有 {report.continuation_keys.length} 项待续处理。不能将此视为完整范围。</p>}{report.stop_reason === "disabled" && <p className="recommendation-boundary">该订阅在生成时已退订，未生成新提醒。历史仍可核查。</p>}{report.stop_reason === "no_items_in_window" && <p className="recommendation-boundary">冻结窗口内没有报告条目，不能据此判断没有风险。</p>}
    {sections.map((section) => <section className="report-category" key={section.label}><div className="recommendation-item-heading"><h3>{section.label}</h3><span className="recommendation-tag">保存 {section.items.length} 项</span></div>{section.items.length === 0 ? <p className="small-note">本报告该分组没有保存条目。</p> : <ul className="recommendation-list">{section.items.map((item) => <li key={`${item.key.event_id}:${item.key.material_version}`}><RecommendationContentView content={item} /></li>)}</ul>}</section>)}
    {report.limitations.length > 0 && <p className="recommendation-boundary">报告范围限制：{report.limitations.join("；")}</p>}
  </div>;
}
