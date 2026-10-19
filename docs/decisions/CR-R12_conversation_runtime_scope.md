# CR-R12 · 多轮问答组合与事件范围过滤

文档首次创建时间：2026-10-17T11:34:08.241+08:00
本次写作开始时间：2026-10-17T11:34:08.241+08:00
状态：approved_for_implementation；源代码与兼容性须独立审查，不据此签 accepted。
依据：已授权 R00–R24 批次的 R12 完整多轮、多跳、混合检索、私有信息出境与 PostgreSQL 权威范围；不改变评分、金标、分母或公开 DTO。

## 问题与最小接口

当前 ConversationContextService、证据包与真实生成/critic 存在，但默认问答尚未组合；HybridQuery 没有 event_ids，直接用于限定事件的会话会扩大召回范围。证据包 paths 尚为空，资产影响/规则映射也未完成，不能把两条互为反向的关系计作独立多跳。

内部 HybridQuery 新增 event_ids: tuple[UUID, ...]，最多20，默认空保持旧查询行为；非空时事实、向量、OpenSearch 与图候选全部在召回前过滤。HybridRetriever 增可选 before_io 回调，默认 None 兼容旧调用，配置时各外部 IO/阶段重复当前授权/范围验证。字段不进入新公开 API；禁止只在结果返回后过滤。

新 ConversationAnswerRuntime 复用 PG admission/context/bundle、真实 GenerationClient、原引用和 critic 校验；最终在同一 PG 事务重读 epoch、快照、上下文版本、证据与真实路径，再保存答案/终态并 acknowledge。回复重放也重核当前性。私有内容默认禁止未知出境授权；生成预算、实际 UTF-8 请求字节及使用量分别记录，未知 token/费用不能伪填。计数器缺失若合同需要，明确 blocked，而不是无限模型调用。

路径须使用真实 PG 图的独立有向边及完整证据，不重复计正反边。现有 component→event→fix 可作为两个必要边的 source 路径；尚缺资产/规则或标准能力时保留 required gap、unknown/partial，不声称全部多跳范围完成。范围内关键证据缺失不得输出确定论断。

## 兼容、迁移与回滚

无依赖锁、数据库迁移、公开 DTO 或历史答案改写。原查询空 event_ids 与无 before_io 行为保持；新组合服务由 Root 后续接线。回滚恢复旧工厂，保留 PG 会话、答案、历史及未完成任务；未接线不得签产品链路。

## 任务、测试与审查

唯一实现者 r12_conversation_answer_runtime_implementation：hybrid_contracts.py、hybrid.py、opensearch_client.py、新 conversation_answer_runtime.py 及直属测试。Root 独占公共入口/合同/状态。六类验收保留；必要负例为所有分支 event 过滤、权限撤销/指代/历史范围/版本竞争、未知或冲突不提升、真实双模型失败、关键边删除、最终事务失败、重放及完整耗时。PG/OpenSearch/模型/browser 需真实执行，未运行 not_run；fixture 不计 live。冻结后新非作者独立审查。

本次写作结束时间：2026-10-17T11:34:08.242+08:00
