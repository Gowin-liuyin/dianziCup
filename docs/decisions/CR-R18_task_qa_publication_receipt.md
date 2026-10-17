# CR-R18 · 同事务任务QA不可变发布回执

首次创建时间：2026-10-17T09:53:51+08:00
状态：approved建设授权内实施；准确性awaiting独立review
主控：Root；原 public API/TaskResultEnvelope/QAAnswer schema及评分/分母不变。

现grounded_answers.model_trace可更新，只有request digest/reservation/usage，没有不可变task关联或逐声明支持回执；不能向JSON添task_id后称其为可信锚。复用现investigation_operations完成后immutable trigger，固定operation_key node:public_qa_publication/kind node/role qa/status succeeded，并持久化严格output_json。字段为schema_version r18-task-qa-publication-1、task_id、answer_id、request_sha256、workflow_input_sha256、response_sha256、public_epoch、generation_operation_key model:qa、verification_operation_key model:critic。所有kind/role/state实际取既有受验证枚举，若源码不同须在本CR明确核对而非静默转换。

public request digest复用0031绑定canonical实现；response hash为QAAnswer.model_dump(mode=json)的ensure_ascii=False/sort_keys=True/separators=(comma,colon) UTF8 SHA256。receipt job_id等于task_id、request digest匹配原绑定，completed_at等于真正answer.completed_at；call_key依现configuration_digest(input/key/request)验证。模型generation/critic成功不可变operation的真实value/attempts、prompt/request digests、owner/job/input/时间全部匹配；draft claims/citations严格与answer一致并重用既有validate_citations/validate_support_verdicts，rendered answer_text不得藏未核声明。同步trace只作一致性辅助，不作immutable证明。

读取只用caller Session/当前scope；先实际owned/completed row，复用成熟bounded Source/Doc/Revision/Event/Claim/Evidence闭包、真实原文引用与当前epoch重验，未知/冲突/撤回/权限下降不升级current。不得另开Session、commit/close、生成/计费或修改pending expiry。Root唯一授权answering/service.py提取同Session只读函数，旧read_grounded_answer仍保留expire/auth及最终认证检查并委托，旧caller兼容。

无该真实回执时固定拒绝，现同步旧回答不迁为task success。future publisher必须真实QA结果/真实generation+critic记录/此immutable回执/typed binding locator/complete_job在同caller事务及当前actor/lease/attempt/deadline下发布，rollback不留下成功；不能先独立ask提交后伪装leased atomic publication。新读port与publisher分别固定源独审再Root装配。

兼容/迁移：不新增表、migration或公共API字段；历史sync QA读取原样，已有generic jobs不自动typed；0031仅Root前向合入隔离测试库，Source912库保持0030。缺receipt/port返回明确unavailable，不丢历史或伪current。回滚：恢复新reader/shared读取seam的源版本，已有不可变回执保留但不输出未接通能力；不downgrade DB/删除job/覆盖历史。

任务/测试影响：R05/R14/R18、T31/T35/T49暴露切片；sameSession owned/digest/task/response hash、pub/critic回执、引用Span/ACL/epoch/stale/unknown/同事务回滚及真实PG待验。fixtures显式synthetic model/publication不计live，人工Gold/阈值/分母/多跳与9职责最终范围不变。338离线作者和19PG collect不是产品通过，独审与真实publisher仍需完成。

修订记录：2026-10-17T09:53:51+08:00 Root冻结必要内部proof seam；无新的费用/外部服务/权限或验收门变更。
