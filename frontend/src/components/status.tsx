import type { ApiProblem } from "../api/client";

const statusLabels: Record<string, string> = { ready: "就绪", live: "可响应", loaded: "已取得本页", no_result: "本次查询为空", not_ready: "未就绪", degraded: "部分不可用", unavailable: "不可用", not_configured: "未配置", not_connected: "待接通", not_observed_or_stale: "待观测 / 已过期", unknown: "未知", stale: "已过期", partial: "部分完成", loading: "检查中", pending: "待处理", waiting_approval: "待人工确认", failed: "失败", blocked: "已阻塞", retry_wait: "等待重试", succeeded: "本次任务已完成", denied: "无权限", queued: "已排队", running: "运行中", cancelled: "已取消" };

/** 文本标识与颜色共同表达状态，未知状态不解释为成功。 */
export function StatusBadge({ state }: { state: string }) {
  const confirmed = state === "ready" || state === "live";
  const label = Object.hasOwn(statusLabels, state) ? statusLabels[state] : `未知状态：${state}`;
  return <span className={`status-badge ${confirmed ? "confirmed" : "attention"}`}><span aria-hidden="true" className="status-mark" />{label}</span>;
}

export function ErrorPanel({ error, message, onRetry, retryLabel = "重试" }: { error: ApiProblem; message?: string; onRetry?: () => void; retryLabel?: string }) {
  return <div className="error-panel" role="alert"><p>{message ?? error.message}</p>{error.traceId && <p className="trace-id">追踪标识 <code>{error.traceId}</code></p>}{onRetry && <button className="button secondary" onClick={onRetry}>{retryLabel}</button>}</div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><h3>{title}</h3><p>{description}</p></div>;
}

/** 静态骨架表达读取等待，不展示虚构百分比或运行进度。 */
export function LoadingState({ description }: { description: string }) {
  return <div className="resource-loading" aria-busy="true"><p className="loading-state" role="status">{description}</p><div className="resource-loading-lines" aria-hidden="true"><span /><span /><span /></div></div>;
}
