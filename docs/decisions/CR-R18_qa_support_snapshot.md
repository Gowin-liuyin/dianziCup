# CR-R18 · 任务问答生成时事实快照见证

文档首次创建时间：2026-10-17T11:34:08.241+08:00
本次写作开始时间：2026-10-17T11:34:08.241+08:00
状态：approved_for_implementation；冻结实现须独立复验原反例与新增共享范围，不能据此 accepted。
依据：本次批次的真实 QA/critic、当前事实与历史不覆盖、未知不等于否定、PG 权威；公开 DTO、金标、阈值、分母、MAX23、模型/累计字节预算不变。

## 已复现问题和根因

reader 的全称条件检查把同 span 另一事件的 supported/false 事实当作当前答案无效。删除该检查又会放过原 supported/current claim 仅 condition true→conflict 的变化。独立 SQLite 最小反例已实跑；原 PG 触发与拒绝断言保留。现有 collector ClaimSummary 没有 subject/condition/freshness，有限图投影也不能覆盖所有支持事实；QA 文本不能猜映射为数据库 claim_id。

## 最小内部见证

新 read_qa_support_snapshot 在原 actor/scope/source 支持闭包及同 Session 中读取明确 event 与实际 evidence IDs 的 current/public/validated supports 关联事实。使用已有完整事件输入锁/256行预算；不按 condition/status/freshness 真值过滤负态。snapshot v1 包含 event_id、有序 evidence IDs、稳定排序的完整事实与整个 payload 摘要；主体、谓词、object、condition/status/freshness、来源版本/日期保持。禁止创建另一套事实真相。

QA 和 critic 的现有不可变 RoleReceipt.output 保存同一真实快照，真实 GenerationRequest 不可信 evidence_texts 包含这些事实状态；helper 的 None 分支保持旧字节兼容，新可信任务发布要求新见证并显式内部 prompt/version。reader 重建实际 request/wire 摘要并在原锁、身份、租约、deadline 和 epoch 围栏后重算同范围快照。不相关已有 false、明确未知可由 quote/critic 判断，不作全称误拒；生成后的 condition 变化使旧见证失效。保守闭包中无关后续变化也会失效，这是明确限制，不宣称逐 QA claim 精确失效。

8个 evidence、256行、现有单文本/请求/累计 bytes 与模型调用上限保持；超限 partial，不截必要事实、不伪填费用或 padding。无见证旧任务 fail closed 并明确 legacy 限制，历史结果不重写，不冒充当前可信发布。

## 兼容、迁移、回滚和文件归属

无公开 DTO/表/迁移/锁文件变更。仅内部 QA 见证、生成 helper、workflow receipt 和 reader 必要变化。唯一作者 r18_qa_reader_support_binding_fix 拥有新 investigation/qa_support_snapshot.py、generation_requests.py、reader、workflow_service.py 的见证 delta 及直属测试；workflow 基于 plugin eea5294 固定 overlay，保留账本 bytes 与原 helper 委托，另列未审依赖。Root 统一集成，不让多 Agent 同写。

回滚停止新可信发布；保留旧/新模型、节点与答案回执及历史，旧无见证不能被新 reader 假称通过。新内部请求版本与原 receipt 必须分开。原模型请求绑定/错 critic/权限/epoch/租约/正文变化等负例全部保留；初始 true/false/unknown/conflict 与后续变化、跨 event 同 span、预算/重放/事务至少定向复验。实际 PG/模型/worker/defaultApp 不得以离线绿代签。

本次写作结束时间：2026-10-17T11:34:08.242+08:00
