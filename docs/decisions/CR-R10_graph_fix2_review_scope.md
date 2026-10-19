# R10 Fix2 · 独立复核的当前读保证范围补充

依据：主控 2026-10-16 明确确认，应把 no-epoch 增强限定到已证实的提交窗口；保留故障注入红例，不把手动覆盖 scope version 的直接 SQL 当成正常产品 publish 漏增 epoch。本补充解释限定服务级 Ship，未改变原 R10 验收、评分分母、公共 Relation、写入协议、业务状态或 accepted。

冻结代码仍为 `08b141bd437c1de70a8435a1f7f6c448a131ed0d`，核心 src 与 `11d24131aff176cc97f138d2e4a222cd378590d4` 同字节；规则 `r10-graph-1.2.0` / schema=1。原 CR-R10_graph_fix2.md、最终材料 `ff5aa737f37c7a591bee6758485e745a0e83b086` 的 raw/Git blob 不覆写。本补充与独立报告一起封存。

原 CR 中“首次集合不存在的新可见 claim/evidence/关联，在真实提交窗口及不 bump epoch 对照中必须返回 409”应按以下实际范围理解：

| 输入与提交窗口 | 本次实际证据 | 保证范围 |
|---|---|---|
| 首次 RR 查询后、RC fresh support SELECT 前提交新增可见 claim/evidence/event_documents；fixture 不增 epoch | 三类均 409，完整 fresh input hash 变化 | 已证实的 no-epoch 增强窗口 |
| 已读输入的父权限、claim/current、event version 或 scope epoch 变化 | 409；当前 role/tenant 403、session revoked 401 | 锁原可见输入与当前身份/版本的范围，原断言保持 |
| 第二次 RC support SELECT 已执行后、epoch 锁前新增输入，正常增 epoch | claim/evidence/association 三个对照均 409 | 正常写入协议仍须同事务维护 epoch/业务版本 |
| 同一晚窗口直接 SQL 挂接新 evidence/association，或正常 publish 后手动恢复旧 epoch | 三类 200 且下一次 fresh digest 已变化；独立单 claim 同样红 | DB 协议故障注入；不能声称防住任意时序、未来插入或直接重置 version |

`GraphReadInputs` 只锁首次实际读取的可见身份。锁后完整重读可发现当时已经提交的新增输入；FOR SHARE 旧身份集合没有为所有未来插入建立范围锁。正常 `KnowledgeRepository.publish` 通过 `save_change_publication` 增 epoch；独立晚窗口 probe 主动把 epoch 恢复原值。静态追踪尚未找到合规产品新增可见输入却漏增 epoch 的提交路径。若后续接入发现此类路径，须修正写入协议并复跑；本补充不豁免 epoch 要求，也不降低原 current/ACL 断言。

证据：`reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1-recheck2.md`；`reports/runs/recovery_r10_pg_evidence_graph_review1_recheck2_20261016/` 的 original9、fresh_pg、independent8、late_fence6_actual 原命令、源码、观察和 JUnit。晚窗口预期 409 的红例不改期待、不转 skip。第一次 late_fence6 因 reviewer 钩子替换未生效实际仍为早窗口，其 v1 源和 6 passed 日志独立保留，不能冒充晚窗口通过。

结论仅用于固定 PG read service/router 工厂和本次定向修复。main App、Neo4j 投影/重建与全图一致性、UI、真实来源/模型、live/manual、整 R10/G-C 仍须后续实际验收。固定 regex 也不构成通用自然语言理解或官方语义准确率承诺。
