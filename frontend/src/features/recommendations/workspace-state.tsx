import { type ApiProblem } from "../../api/client";
import { EmptyState, ErrorPanel } from "../../components/status";

export function RecommendationError({ error, onRetry }: { error: ApiProblem; collection?: boolean; onRetry?: () => void }) {
  let message = error.message;
  if (error.status === 404) message = "记录不存在，或当前会话不能访问该记录。";
  if (error.status === 403) message = "当前会话没有访问权限，私有结果已清除。请重新核对授权。";
  if (error.status === 403 && error.code === "csrf_rejected") message = "写入会话校验未通过，本次操作没有完成。请重新核对会话后提交。";
  if (error.status === 409) message = "订阅已被其他操作更新。本次输入尚未保存，请重新读取版本后核对并提交。";
  if (error.status === 503) message = "服务暂不可用。本次查询未完成，不能据此判断无推荐或无风险。";
  if (error.status === 503 && error.code.includes("not_configured")) message = "订阅与报告服务尚未配置。本次操作未完成，不能解释为零记录或无风险。";
  if (error.status === 400 || error.status === 422) message = "输入未通过校验，请核对关注范围、版本或生成批次。";
  return <ErrorPanel error={error} message={message} onRetry={error.status === 401 || error.status === 403 ? undefined : onRetry} retryLabel={error.status === 409 ? "重新读取版本" : "重试查询"} />;
}

export function RecommendationLoading({ description }: { description: string }) {
  return <div className="recommendation-loading" aria-busy="true"><p className="loading-state" role="status">{description}</p><div aria-hidden="true"><span /><span /><span /></div></div>;
}

export function PrivateWorkspaceAccess({ loading, expired, title }: { loading: boolean; expired: boolean; title: string }) {
  if (loading) return <section className="panel"><RecommendationLoading description="正在确认访问会话…" /></section>;
  return <section className="panel"><EmptyState title={expired ? "会话已失效，私有结果已清除" : title} description="订阅、推荐与报告从当前认证用户的授权范围读取。" /><div className="panel-actions"><a className="button secondary" href="#session">核对会话与权限</a></div></section>;
}
