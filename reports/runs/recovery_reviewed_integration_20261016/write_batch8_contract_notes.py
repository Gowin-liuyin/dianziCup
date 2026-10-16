"""Record compatible internal bindings and correct a gate-field count without changing code."""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path = ROOT / "docs/decisions/CR-R06_reprepared_nine_script_binding.md"
old = path.read_text(encoding="utf-8-sig")
if old.count("原gate14fields不加nonce") != 1:
    raise RuntimeError("unexpected historical gate wording")
new = old.replace("原gate14fields不加nonce", "原gate13fields不加nonce")
new += f"\n\n## 字段计数更正 · {NOW}\n\n主控原18:21记录的14是计数笔误。原非作者jointfix2已对冻结observer observe.py:40–54及CORE b110 run_binding.py:433–459核对：精确13键为root_live_authorized、product_sha、observer_sha、product_root、run_id、segment_id、started_at、supervisor_limits_verified、source_scope、maximum_seconds、postgres_port、redis_port、opensearch_port；无nonce键。原observer和CORE字段/输入字节不改，不能添加第14键。segment_id仍绑定segment_+nonce。此处修正文档计数，原历史正文中14的证据由此明确更正，不改变任何gate/阈值/授权。Root批准，待原非作者仅文档差异核对；不需重跑191或新增native。旧Product1cdb已确认preclaim缺陷，CORE+OPS静态放行不能替代合格新Product/资源身份激活门。\n"
path.write_text(new.rstrip() + "\n", encoding="utf-8", newline="\n")
documents = {
    "CR-R16_persisted_cursor_configuration.md": f"""# CR-R16 · 持久游标签名配置

文档首次创建时间：{NOW}
本次写作开始/结束时间：{NOW} / {NOW}
状态：approved_for_implementation；Root配置待新非作者审查。
授权：本批R16/T36–T38，已批准事实/任务PG权威及重启持久能力。

原CandidateDiscoveryService已要求服务端SecretStr，但默认worker未接且不能用随机进程键或模型密钥临时代替。新增可选ApplicationSettings.revalidation_cursor_signing_key，环境REVALIDATION_CURSOR_SIGNING_KEY，仅小写64hex/32bytes；未配置None意味着该能力未配置，不创建进程内新权威。生产/staging拒绝已知三种fixture键，秘密隐藏错误与序列化。真实CurrentUser DPAPI文件只存仓外，实际创建20:38:14.5941439+08，配置字段本身不证明worker使用它。

兼容/迁移：可选字段不破坏既有部署/认证会话；已签游标保持相同key重启才能继续，显式换key旧游标必须拒绝并重查，绝不回退未签游标。部署通过已有guarded秘密加载器注入，key不进job/API/日志/前端。PG事实/绑定/epochs不迁移、不改schema。回滚停用新重判入口、保留PG历史/原key，不伪造安全结果。原T最终依赖和验收未缩减。

任务/测试影响：R16默认worker/API、R20秘密/重启、T36–39；14配置边界例已经Root离线通过，服务重启/真实PG游标/secret注入/defaultfactory仍not_run，不能将字段存在签R16。Root唯一settings/config所有权，独审冻结代码后才有限放行；金标/分母/性能门不变。
""",
    "CR-R18_public_read_identity_bindings.md": f"""# CR-R18 · 公开读取身份与组件计数绑定

文档首次创建时间：{NOW}
本次写作开始/结束时间：{NOW} / {NOW}
状态：approved_for_implementation；producer/SDK新切片独审后生效。
授权：R18/T32/T35及既有CR-R04/09/冻结public_api_extensions_v1；不改变schema/评分/盲测。

GET /api/v1/vulns/{{id}}的路径主键是event_id，响应vulnerability.event_id必须等于请求；intel_id保留NormalizedIntel原标识。复用共享EventDetail聚合，不用字符串格式猜两种主键。GET tasks/{{task_id}}响应task.task_id及poll_uri必须绑定自己同一task_id固定任务路径；不得任意URL/跨对象引用。

SDK输入只支持原请求q/limit/cursor：q最多4096字符、limit strict整数1..100默认20、cursor非空最多2048；ID为canonical UUID，不新增类别过滤/公共response字段。MCP create_current_read_tool_server默认原两工具兼容既有调用，以显式include_extended_tools=True启冻结六只读工具；主控默认产品入口必须最终启六，兼容参数不能冒充整六接通。缺producer返回明确not_configured，不用fixture假成功。

RiskSummary.evaluated_components为实际执行研判的请求组件数，包含被评估但unknown的组件，不代表确定结论数。不得大于真实请求组件数；complete必须每个请求index恰一结果，不删除未知或缺项来缩分母。SDK仅有envelope时检查<=len(results)、indices在返回范围、complete无空/unknown/conflict/stale；check_stack持有原request再核真实范围。partial不机械要求已执行数等于原请求数。claim/event在真实PG的归属、支持与ACL由producer核验，UUID与payload一致不代替证据语义。

兼容/迁移：原14schema/八DTO/四态/风险等级/工具预算保持，新增typedmodels逐字段等价冻结扩展合同；server与SDK同时固定绑定。回滚关闭新增公开适配入口，保留旧读路径和PG历史；不回退clean或删除结果。Task状态/异步联合不变。影响R18/R14/R20/R21与六tool/native取消/身份错配/风险分子分母回归，所有实际命令/范围由各新非作者审查记录；原金标、阈值、预算、模型价格未变。
""",
}
for name, text in documents.items():
    target = ROOT / "docs/decisions" / name
    if target.exists():
        raise RuntimeError("contract already exists")
    target.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")
print({"recorded_at": NOW, "r06_document_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "new_compatible_contracts": list(documents)})
