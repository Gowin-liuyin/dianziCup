# CR-R18 · 公开读取身份与组件计数绑定

文档首次创建时间：2026-10-16T21:18:22+08:00
本次写作开始/结束时间：2026-10-16T21:18:22+08:00 / 2026-10-16T21:18:22+08:00
状态：approved_for_implementation；producer/SDK新切片独审后生效。
授权：R18/T32/T35及既有CR-R04/09/冻结public_api_extensions_v1；不改变schema/评分/盲测。

GET /api/v1/vulns/{id}的路径主键是event_id，响应vulnerability.event_id必须等于请求；intel_id保留NormalizedIntel原标识。复用共享EventDetail聚合，不用字符串格式猜两种主键。GET tasks/{task_id}响应task.task_id及poll_uri必须绑定自己同一task_id固定任务路径；不得任意URL/跨对象引用。

SDK输入只支持原请求q/limit/cursor：q最多4096字符、limit strict整数1..100默认20、cursor非空最多2048；ID为canonical UUID，不新增类别过滤/公共response字段。MCP create_current_read_tool_server默认原两工具兼容既有调用，以显式include_extended_tools=True启冻结六只读工具；主控默认产品入口必须最终启六，兼容参数不能冒充整六接通。缺producer返回明确not_configured，不用fixture假成功。

RiskSummary.evaluated_components为实际执行研判的请求组件数，包含被评估但unknown的组件，不代表确定结论数。不得大于真实请求组件数；complete必须每个请求index恰一结果，不删除未知或缺项来缩分母。SDK仅有envelope时检查<=len(results)、indices在返回范围、complete无空/unknown/conflict/stale；check_stack持有原request再核真实范围。partial不机械要求已执行数等于原请求数。claim/event在真实PG的归属、支持与ACL由producer核验，UUID与payload一致不代替证据语义。

兼容/迁移：原14schema/八DTO/四态/风险等级/工具预算保持，新增typedmodels逐字段等价冻结扩展合同；server与SDK同时固定绑定。回滚关闭新增公开适配入口，保留旧读路径和PG历史；不回退clean或删除结果。Task状态/异步联合不变。影响R18/R14/R20/R21与六tool/native取消/身份错配/风险分子分母回归，所有实际命令/范围由各新非作者审查记录；原金标、阈值、预算、模型价格未变。

## 2026-10-16T22:27:47+08:00 · PG producer内部身份映射澄清

依据R18既定NormalizedIntel语义与现有PG schema，intel_id绑定documents.document_id，revision_id只引用同document的当前归一化revision；这是内部字段接线，公开schema/评分/权限/分母不变。Vulnerability路径仍event_id，intel_id由当前可见event_documents→document/revision关联取得。多来源用共享事件聚合并保留每条证据文档归属，禁止一个document冒充全部event；稳定业务排序选择可投影的当前document，缺关联/归一化/权限时明确缺口。

实际冻结六SDK工具是ask/check_stack两POST与search_vulns/get_vuln/list_sources/get_task_result四GET；Root派单中getAssetRiskSummary命名错误已更正，未新增工具或GET。risk摘要属于check_stack的冻结envelope。当前backend仅questions/assessments/jobs，缺公共typed task关联时返回not_configured，不能把任意job包装成ask/stack成功。

Source.enabled表示该来源在当前固定注册与global polling配置下是否可自动调度，不新增逐来源持久状态或把global开关当逐源证据。health与data_mode按真实采集收据/原文metadata，未知保留。兼容性：既有reader和ID不迁移、不重写历史；回滚移除新增公开adapter入口，PG源数据保留。影响R18 producer/SDK pagination/身份错配、权限、来源状态及风险分母测试；新非作者必须核本澄清是否准确落实授权，尚不等于producer验收。
