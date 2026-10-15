import type { Freshness } from "../../api/knowledge-contracts";
import { formatShanghaiTimestamp } from "../../app/date-time";

const freshnessLabels: Record<Freshness, string> = { current: "当前", stale: "已过期", unknown: "时效未知" };

export function SavedTime({ value }: { value: string | null }) {
  return value === null ? <span className="unknown-value">未知 / 未留存</span> : <time dateTime={value}>{formatShanghaiTimestamp(value)}</time>;
}

export function FreshnessBadge({ value }: { value: Freshness }) {
  return <span className={`freshness-label freshness-${value}`}>{freshnessLabels[value]}</span>;
}
