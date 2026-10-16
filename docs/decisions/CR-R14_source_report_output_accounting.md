# CR-R14 · 来源报告消费与实际输出预算

文档首次创建时间：2026-10-17T01:48:19+08:00
本次写作开始时间：2026-10-17T01:48:19+08:00
状态：approved_for_implementation；新非作者核对合同、冻结代码和真实 PG 前不得签验收。

授权依据：R00–R24 有界批次中的 R07 原文证明、R14 真实职责协作，以及已冻结 CR-R07_structured_fact_proof_bridge。此补充不改变公开 DTO、工具权限、最多八次工具调用、评分阈值、金标或分母。

## 接线和行为

默认 InvestigationWorkflowService 的 SourceEnricher 复用 StructuredFactProofReader、build_source_report_reader 与 read_enrichment_source_reports。服务工厂只注入已配置 ContentStorage；authenticated ActorReference、AccessScope、同一线程空闲 Connection 均从服务运行上下文取得，不从请求体取得。所有引用先通过原 InvestigationRequest 校验，最多八个；全部读取共用原五秒或调查剩余时间中更小的绝对 deadline。每次最多八个 facts 的原限制保持，整个节点最多六十四个 facts，不将单次限制误写为总八个。

读取保持 reported/partial/not_found、逐事实原 condition/freshness/origin、证据和缺口。它证明来源报告了一个值，不代表资产受影响、强关系成立或引文支持整个回答。原四强图谓词门、EvidenceResponse.current_supported 和 QA 的原引文支持语义不放宽；本切片不声称九维全部完成或富化写入适配已接。缺 reader、空引用、部分报告、冲突和超时分别记录明确原因，不包装为空成功。仅在完整真实证明存在时记录报告读取成功；原文、规则或权限变化不得借旧回执续跑。

## 实际输出预算

现有 node 回执 reserve 的 output_bytes 为零，而 complete_operation 保存整个状态而不计实际 UTF-8 JSON 长度。新规则必须在共享完成边界核查全部调用者，按冻结 JSON 编码的实际字节计数，并保留未完成 model/tool 的既有输出预留。node 至少预留一个可容纳固定预算失败回执的有界容量；成功输出不能超过任务剩余总预算。失败只保存固定 error_code，不保存、截断或冒充成功的大报告；任何无法保存该固定失败回执的边界应在开始 IO 前停止。不得在完整输出被拒绝后仍将它留在返回值、LangGraph checkpoint 或公开结果中。

已完成旧回执和历史字节不重写；新任务绑定明确的 source_report_consumer_version 与 operation_output_accounting_version。旧版本运行按既有配置不一致规则停止，不静默迁移、重新预留付费操作或重置预算。重放使用真实 PG 回执，崩溃后未知不自动再次调用外部服务。固定预算错误需在共同恢复路径优先停止，不改成 operation_outcome_unknown 或伪造成功。

## 兼容、回滚和验证

无需新表、迁移、依赖或新工具。默认工厂、内部服务可选注入、配置绑定与所有 complete_operation 调用者同步；保留旧直接构造的未配置行为。回滚撤销新消费者注入并停止新规则版本活动任务，保留所有已保存事实、任务、原失败日志和历史。

R07/R14/R17/R20 受影响。作者须先复跑原 348 调查离线及 304 来源证明离线，再增加真实 UTF-8 多字节边界、累计预算、reserved 操作、失败回执、重放、unknown、ACL/epoch/租约、超时和大报告不进入 checkpoint 的反例。新的独立 reviewer 亲跑默认工厂及真实 PG 消费，不以 helper 测试替代接线。模型、浏览器、live、人工与性能如未执行仍为 not_run；整卡和阶段不得因本补充改绿。

## 修订记录

2026-10-17T01:48:19+08:00，Root：依据真实 clock 工具 UTC 17:48:19 换算北京时间；立即纠正初稿误写的未来 01:49:00，未以文件时间推断。写作结束和冻结代码 SHA 由本轮执行收据追加，不写自身提交 SHA。
