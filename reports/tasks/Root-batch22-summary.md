# Root · 批次22 总结

文档首次创建时间：2026-10-25T05:45:00+08:00
本次写作开始时间：2026-10-25T05:45:00+08:00
最后更新时间：2026-10-25T05:45:00+08:00
任务状态：awaiting_review；工作分支 codex/full-delivery-recovery；导入前 HEAD fb0b97c7a。

## 目标完成情况

1. **目标1（(d) 类甄别与修复）：完成主体**。甄别报告（`reports/runs/batch22_d_triage/triage_report.md`）确认 72 失败中 66 例同源三大根因家族；按 CR `docs/decisions/CR-seed_data_mode_alignment_batch22.md`（含实现轮追加节）落地种子对齐 + 独立项修复（9 文件 +24/−6，零断言值/零产品代码/零 legacy 语义改动），容器重跑 **46 failed → 13 failed**；trace 读写分离修复（R06_PROOF_TRACE_DIR，原冻结证据目录零触碰）后再 **→ 6 failed**。净修复 40 例。
2. **目标2（SourceEnricher 预算）：按停止条件闭环**。调研（`reports/runs/batch22_source_enricher_research/research.md`）证实三条实现路径全部触碰冻结断言或公开 DTO——OQ-6 登记，未改任何代码。
3. **目标3（R24-A 材料整理）：完成**。18 条候选清单（`reports/runs/batch22_r24a_materials/r24a_candidate_materials.md`）；关键口径澄清：R24 是交付冻结卡而非修复验证卡；**R24-A 开工被 R22:T52/T53/T54 + R18:T51 + R21:T47/T48 accepted 硬阻塞**，此前仅骨架范围可零人工推进。
4. **目标4（拓扑方案）：部分完成**。自由文件独立库（消除串扰）已入 plan_batch22 并实证（r07_input_capabilities 的共享库串扰类随独立库消失）；审计族三层前置条件精确记录（drivername/25432 已解，迁移状态冲突按纪律停止）；pgvector 0.8.2 钉版不可行（pgdg main 已无该版本）记 OQ-5。

## 真实测试与结果

| 验证 | 退出码 | 结果 |
| --- | --- | --- |
| 种子对齐后宿主定向（unit+contract/security -k 过滤） | 0 | 1163 passed |
| 容器逐文件重跑 35 受影响文件 | 混合 | 46 failed → 13 failed |
| r06 proof 文件（读写分离后） | 0 | 12 passed，pg_case 写入 /out（冻结目录零触碰） |
| 宿主全量（种子变更后） | 1* | 6252 passed / 1 failed（r07 [headers] 抖动，复跑 3 passed） |
| 剩余 (d) 类 | — | 6 failed：3 legacy/unknown 可读性探针（OQ-5 裁决）+ 2 D 类待取证 + 1 advisory 待 error_code 取证 |

*exit=1 同前：仅由设计内 blocked（83）与已复跑转绿的 1 例抖动贡献。

## 仍开放（全部有记录）

- OQ-5 增补：r05 legacy-0013 可读性裁决（19 例）、r04_source_documents evidence 计数裁决（1 例）、家族 2 公网读错误码映射（5 例，产品行为需评审）、pgvector 版本（pgdg main 无 0.8.2）、审计族预置状态库方案、r07_job_execution/r14_default_runtime/r14_read_adapters 取证。
- R24-A：上游 accepted 前仅骨架可动。

## 合同与计划偏差

1. CR"56 例转绿"算术不可达（含其自身排除项且有文件归属错误）——实现代理如实上报，实际 CR 范围修复 41 例根因、可观转绿 33+7（trace 拦截）；CR 已追加说明。
2. CR 第 4/5 条的修改点物理位于共享 helper（credentials pg_case / prepared_submission / seeded_event）——代理最小扩展 5 个落点文件，35 文件复跑证实 24 个全绿消费方零回归。
3. r18 修法修正：issued_at 改相对时钟会打破 credentials 自身用例，实际只改 expires_at 一行。

## 下一任务建议

1. 剩余 6 例按 OQ-5 取证/裁决推进（需评审介入的 3 项：legacy 可读性、evidence 计数、错误码映射）。
2. 候选池大件（多跳问答/推荐历史/MCP/OAuth/CLI 三插件/安全 CI 框架）——均为多日特性开发，建议逐项立项评估后再排批。
3. R19 人工标注窗、R22 资源窗仍是 R24-A 与正式评测的硬前置。

本次写作结束时间：2026-10-25T05:45:00+08:00；本报告为有界收敛轮的证据索引，不是阶段验收或 push 声明。
