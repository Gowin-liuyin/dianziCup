# R11 / T27–T28 PostgreSQL 规则与研判内部切片

状态：内部结构已由主任务明确批准并冻结；实现 awaiting_review，不批准公共 API、认证、生产迁移或整卡验收。基线 e310f7735bd499c4d9fbcefe8a644e2309a16a62；T27 纯函数来源 328ed7a933a9a81ec715f447235f4b933e0ed506，生命周期修复 ddfbf8c。0017/0018/0019 迁移采用既有 281371b072a696d972aa3c38519b8646393c98e2 与 c842333fe56a4ab3018a3216a8ddcd6a34639ae1，不重写或改动迁移。

## 权威与修改范围

读取 AGENTS、执行地图、恢复 R11/U04/U05/U08、03 §3.6–3.8、04 W06/W07、05、06、T27/T28 和完整 CR-R11_condition_rules_proposal。PG 是唯一事实状态；本切片新增内部 Table 映射，业务入口不自动建表。0021 生产迁移由主任务独占。仅新增 rule_persistence.py、rule_service.py、assessment_persistence.py、assessment_service.py、唯一内部 persistence_contracts.py 及直属新测试/报告/run。API、worker、assets、pure 条件/版本、公共 schema、认证、依赖、全局进度不改。

## 输入输出

`RuleService(engine, session_token, content_store)` 使用既有 `lock_authenticated_scope`，不接受请求体 tenant/role/policy。

- `create_candidate(rule, bindings)` 固定 AST、范围和来源引用，重复相同版本返回原身份，异内容拒绝。
- `record_leaf_review(rule_id, version, binding, decision, reason)` 对既有 PG claim/evidence 与精确叶、当前源文本摘要保存独立人工审核收据；decision 只接受 supports/refutes，审核者必须具备相应管理权限且不能是候选作者。没有真实人工输入仍为 pending_semantic_review；测试审核者明确 fixture，不计 live。
- `validate(rule_id, version)` 以固定服务端策略产历史验证收据。既有 claim_evidence.validated 只证明现有发布链，不独自证明其支持本规则必要条件；语义支持必须另有有效的精确审核收据。调用参数没有 necessary_condition_supported 布尔。
- `publish(rule_id, version)` 重新核验所有来源/证据/审核/范围与当前输入，自动发布关闭；经独立有权限审核者才能从 validated 转 published。`retire` 单向保留历史；再次验证不倒退 published/retired。

`AssessmentService(engine, session_token, content_store)`：`prepare(asset_id,snapshot_id,rule_id,version)` 返回固定且有类型的规则/资产/全部事件来源 roster、源证据、审核摘要、知识 epoch、范围关注和身份版本。`commit(prepared)` 自行评估纯引擎，短事务再核对输入；没有模型/网络调用。`read(assessment_id)` 返回证据包且实时回查所有父级 ACL 与 current 状态；历史结论与 freshness 分离。

## 表与约束提案

共享既有 knowledge metadata，新增 condition_rule_versions（AST 内容所有阶段不可变、单向 lifecycle）、rule_support_bindings（rule/version/node/condition digest/claim/evidence FK）、rule_leaf_reviews（审核 actor/reason、支持或反驳、精确源输入 digest 的追加历史）、rule_validation_receipts（固定 policy/validator、完整 input roster 与 pending/conflicts）、assessment_results（tenant/asset/snapshot/rule/version/input digest/固定任务策略唯一键、树/span/资产 refs 的不可变输出）、assessment_scope_watches（包、事件、范围与 epoch 的规范描述，包括空规则范围；T36 反向索引和调度仍未完成）。

主任务补充冻结：同 rule_id 的所有版本必须保持 event/scope/rule_kind 家族身份；foreign family 即使提交新 version 也统一 404。每个 family 只能有一个 status=published 版本，使用 PostgreSQL partial unique index `uq_current_published_rule_family` 和事务 family 锁保障。先显式 retire 旧版，再 publish 已审新版；遇另一个 published 返回 typed `rule_requires_retirement_of_published_version`，不自动替换或选择 latest。旧 retired 版仍可读历史，不能复活 current。root 0021 继承该约束；新增两发布者并发与数据库绕过服务的 unique 负例、旧版历史/新版发布验证。

`knowledge_epoch` 仅投影现有 scope_epochs 的 public 行，不称 global epoch，不求和，也不新建 counter。public 行不存在时 scalar 与 map 对应值均为 typed null；租户及其他分区逐键保存 scope_epoch_map。当前性只按完整 map/source/asset/rule/审核 input digest 比较，绝不只按 scalar。03 §3.8 未规定 global counter 实现，此内部兼容说明不改公共 DTO/schema，未来 API 合同需明确投影语义。

source→document→revision 当前配对（含当前 document content_hash）、claim assertion、事件关联、block/Unicode 左闭右开坐标、quote/hash、原文对象 hash 必须分别核验。所有派生范围不宽于来源/文档/修订/claim/span。source blob 读取只使用 PG hash，不能接受任意路径/URL。原文不存在或损坏显式失败，不返回否定。源对象单个 2 MiB、总 8 MiB、来源 roster 20、支持绑定 64 上限。准备输入在既有 rule_validation_receipts 增加可选 typed prepared_assessment 审计字段；提交按 receipt_id+actor 查 PG 并与传入类型完全相等核验，防止伪造历史输入；没有第七张表。

短事务锁定真实认证会话/用户、指定资产 current、全部 source 父行/文档修订、相关 publication scope、event/rule 和实际 claim/evidence/assertion/link 行。锁序依据实际 source_documents 的 source/document→publication/event、InventoryService 的 asset→tenant publication 和 KnowledgeRepository 的 publication→claim 顺序：在等 publication 前不持 claim 锁；事件/claim/evidence 均在 publication 后。公共规则研判额外锁与记录资产租户 epoch。提交前所有 epoch/roster/digest/current/lifecycle 比较。资产或知识变保存 stale；角色/权限/ACL 变化拒绝且不写结果。相同执行键幂等返回历史身份，绝不把旧结果恢复 current。规则发布/退役复用现有 change/epoch/outbox 同事务记录。

## 验证与未覆盖

新 unit/contract 验证 typed 边界、scope watch 和执行摘要；隔离真实 PG integration/security 验证来源核验、语义待审、独立审批、三版本四态、配置差异、网络与软件分栏、replay、rollback、源修订/资产/角色/ACL 并发、历史不覆盖。测试数据为显式 fixture；数据库仅 test_dianzi_r11_assessment_20261016，随机 schema 隔离、forward only，无 downgrade 或删除已有数据库。

frontend/e2e/live/manual 均 not_run，费用 unknown，外部模型/provider/source 0 calls。没有真人金标，不声称 3→5 产品真值或 G-D 通过。API/worker 接线、生产 0021、T36 重判调度、OpenVEX、真人标签均留主任务/后续切片。已知 candidate 且无 published 规则的输出实际保存 no_published_rule 范围描述；完全没有 rule 行的任意查询空结果生成尚未接线，不声称该流程完成。
