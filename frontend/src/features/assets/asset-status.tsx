import type { ApiProblem } from "../../api/client";
import { ErrorPanel } from "../../components/status";
import { AssetResponseScopeMismatch, type InventoryCompleteness } from "./asset-contracts";

export const completenessLabels: Record<InventoryCompleteness, string> = { complete_for_declared_scope: "声明范围内完整", partial: "部分清单", unknown: "完整性未知" };
const importErrors: Record<string, string> = {
  inventory_upload_size_limit: "文件必须非空且不超过 1 MiB。",
  invalid_encoding: "文件编码不受支持，请使用 UTF-8。",
  missing_csv_mapping: "CSV 必须明确映射字段与列名。",
  invalid_csv_mapping: "CSV 映射必须包含 package_name；列名不可重复。",
  invalid_csv_columns: "CSV 表头与映射列名不一致，请核对文件第一行。",
  invalid_csv: "CSV 行或引号格式无效，请核对原文件。",
  unsupported_field: "文件包含当前协议不支持的字段，请核对 JSON v1 / CSV 组件字段。",
  invalid_field_type: "文件字段类型无效；配置值应保持字符串、布尔或 null。",
  timezone_required: "观察时间必须明确时区，例如 +08:00 或 Z。",
  missing_package_name: "组件缺少 package_name，请核对组件字段。",
  invalid_package_name: "组件 package_name 无效，请核对包身份字段。",
  unsupported_format_version: "JSON 的 format_version 必须为 1。CycloneDX / SPDX 尚不支持。",
  unsupported_format: "清单格式不受支持，请选择 JSON v1 或 CSV 组件清单。",
  invalid_json: "JSON 格式无效，请核对原文件语法。",
  invalid_string: "输入文本为空、过长或包含控制字符，请核对文件字段。",
  json_depth_limit: "JSON 嵌套层级超出服务端上限。",
  component_limit: "组件声明数量超过服务端上限（10000 项）。",
  duplicate_component: "组件声明重复，请核对 components 字段。",
  duplicate_value: "声明列表中存在重复值，请核对原文件。",
  conflicting_version_scheme: "组件 version_scheme 与声明生态不一致。",
  unsupported_purl: "组件 purl 不符合当前支持协议。",
  invalid_image_digest: "组件 image_digest 格式无效。",
  invalid_inventory_completeness: "inventory_completeness 声明无效。",
  missing_declared_scope: "声明范围内完整时必须提供非空 declared_scope。",
  unexpected_csv_mapping: "JSON 清单不接受 CSV 列映射。",
  invalid_timestamp: "观察时间格式或时区值无效。",
  idempotency_conflict: "导入请求与原幂等键不一致。请核对先前操作，勿用新键重复提交。",
  asset_name_conflict: "已有资产的名称与输入不同；本入口不支持改名。",
};
export function AssetError({ error, onRetry, retryLabel }: { error: ApiProblem; onRetry?: () => void; retryLabel?: string }) {
  let message = importErrors[error.code];
  if (error.status === 401) message = "会话已失效，私有资产已清除。请重新登录。";
  if (error.status === 403) message = error.code === "csrf_rejected" ? "会话写入校验未通过，请重新验证会话后再导入。" : "当前会话没有此项资产权限，请联系租户管理员。";
  if (error.status === 404) message = "该资产或快照不可用。它可能不存在，或当前会话无权查看。";
  if (error.status === 503) message = "资产服务暂不可用，恢复后可重试。已取得的页面仅供查看，当前有效性尚未重新验证。";
  if (error.status === 502) message = "资产响应与当前合同或会话范围不一致，结果未用于展示。导入是否提交需从资产列表核对。";
  if (error instanceof AssetResponseScopeMismatch) message = "资产响应与当前会话范围不一致，已清除私有资产工作区。请重新核对会话与权限。";
  return <ErrorPanel error={error} message={message} onRetry={onRetry} retryLabel={retryLabel} />;
}
