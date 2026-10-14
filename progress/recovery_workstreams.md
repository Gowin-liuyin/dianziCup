# 恢复批次并行与文件所有权

首次创建时间：2026-10-14T20:56:36+08:00
最后更新时间：2026-10-14T20:56:36+08:00
集成分支：codex/full-delivery-recovery；实际初始SHA：8e265dc039a67319140f003f6a070ea714bf7bef；授权文档基线：b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b。

宿主4槽。当前R00有3个独立分析/验证工作包；冻结后释放槽建立新独立reviewer，后续默认主控+2实现+1review。默认继承主模型。无其他用户聊天或外部消息。

| 工作包 | Agent | 输入→输出 | 允许写入 | 结束条件/状态 |
|---|---|---|---|---|
| R00合同/集成 | /root | 用户授权+原合同→CR-R01–09、公共schema、manifest、纠偏/历史、阶段报告 | docs/decisions/CR-R*.md；docs/plan；contracts；progress；reports/tasks/R00.md；reports/stages/recovery/G-A.md；reports/runs/recovery_r00_20261014；tests/plan/test_public_api_v2.py；Git集成 | 新独立review后方生效；in_progress |
| R00基线与资源只读复现 | /root/baseline_runtime_probe | 8e265dc源树+审计→实测缺陷/资源证据 | reports/reviews/recovery/G-A-baseline-probe.md；reports/runs/recovery_baseline_probe_20261014/ | 旧审计核心问题及资源复核已落盘；awaiting_review |
| R00切片分析 | /root/recovery_mapping_audit | 全部T卡→R切片、最终合并验收与依赖无环 | reports/reviews/recovery/G-A-R00-mapping-analysis.md；reports/runs/recovery_mapping_20261014/ | 60T无遗漏分析已落盘；awaiting_review |
| R00计划验证器 | /root/r00_plan_validation | 冻结小schema→严格重复键/切片/状态校验与负例 | scripts/verify_plan.py；tests/plan/test_verify_plan.py；tests/plan/test_recovery_plan.py；reports/tasks/R00-validator.md；reports/runs/recovery_r00_validator_20261014/ | 原16+恢复24共40通过；awaiting_review |
| R00初审 | 待创建的新Agent | 冻结SHA与新旧合同→独立中文review | 单独reports/reviews/recovery/G-A-R00-review-1.md及原始日志 | 不参与实现/不改业务、复跑关键测试；pending |

公共schema、迁移编号、依赖锁、全局配置、状态与Git只归主控。当前共享checkout写集互不相交；实现者扩大范围须先交主控协调。各包已派发必读AGENTS/恢复11+12/相关T合同/Ponytail、六层及live分别记录、日志、输入输出、禁止项；不改金标/分母、不签accepted、不push。

后续业务实现从主控已提交正确合同基线建独立worktree，每个独立代码索引；review冻结SHA，作者可在另worktree继续。主控核实精确diff/commit与日志后集成，不以“完成”消息替代验收。

2026-10-14T21:22:01+08:00：R00候选最终49合同/计划测试通过，三实现/分析包均交付。provider_docs_probe报告已交付（官方文档，不是live）；docker_runtime_diagnosis独立安全诊断在途。R00独立review待新Agent，业务实现尚未启动。
