# 恢复批次并行与文件所有权

首次创建时间：2026-10-14T20:56:36+08:00
最后更新时间：2026-10-15T01:47:36+08:00
集成分支：codex/full-delivery-recovery；实际初始SHA：8e265dc039a67319140f003f6a070ea714bf7bef；授权文档基线：b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b。

宿主4槽。R00已独立通过；当前主控TLS/集成、行为最终复核、缓存冷启动定向复核、R02持久化只读准备。默认继承主模型。无其他用户聊天或外部消息。下列旧表保留历史，当前分工以本次登记为准。

| 当前工作包 | Agent / 冻结基线 | 写集与资源所有权 | 结束条件 |
|---|---|---|---|
| 核心集成/安全搜索/PG边界 | /root / b504c237 | 主仓app/settings/tests、公共迁移/合同/锁、progress/阶段报告、唯一Git/push；root裸测试资源 | 冻结TLS实现并真实验证、公共R02小接口落盘后分工 |
| 行为修复独立最终复核 | /root/r01_independent_review / d30eeab1 | 只main自己的review/run；冻结recheck-final WT只读 | 独立扫描/限流/UI42与访客浏览器；说明Vitest仍阻断，不背书整R01 |
| 基础设施缓存独立定向复核 | /root/r01_runtime_review / 32d16a4+eff45e5 | 只自己的review/run；独占dianzi-test-r01_infra_20261015的冷停启；冻结WT只读 | 19合同与实际冷启动/权限/七服务，交回项目；TLS不纳入本次通过 |
| 持久化接口分析 | /root/r02_persistence_preflight / d30eeab1 | 只R02-preflight报告/自己的run，不改业务/迁移/schema/状态 | 给出可复用表、类型兼容、事务/ACL/验收映射，禁止签accepted |

缓存作者已交付32d16a4/eff45e5并结束，未push/accepted；新的实施包使用另一独立worktree，禁止改正在复核的冻结版本。Vitest4候选497740a仍等待CR-R10新明确批准。

## 当前文件所有权与冻结流水线

| 工作包 | Agent / 基线 | 唯一写集 | 当前交付与结束条件 |
|---|---|---|---|
| R01核心运行/集成 | /root / a1b8aae | backend API/auth/settings、迁移/models/locks/infra/CI、progress、阶段文档、Git | 主仓修认证根因；实际worker/浏览器/Compose待实现，独立review后集成 |
| R01前端 | /root/r01_frontend / 189990c+b07596c | 自有WT frontend/src、直接测试/e2e、自有报告/日志；禁止锁/公共配置 | 已交30用例及构建，修同会话快照和nonce误报后交新SHA；不签accepted/push |
| R01质量 | /root/r01_quality / c918279 | 自有WT scripts/dev.py、测试安全配置及指定原卡测试、自有报告/日志 | 2b79c80/c918279/453893d/e895852交付；195证据，需独立集成复核；不要重复ebedb39 |
| R01行为独立初审 | /root/r01_independent_review / 固定4a17ca7 | 主仓自身review报告及recovery_r01_behavior_review_1_20261014原始日志；不改业务 | needs_changes，6项真实缺陷/误报，复核待新冻结修复版；不签整R01 |
| R01 Vitest主版本候选 | /root/r01_vitest_candidate / d0a179e | 独立WT package/lock必要vite配置、自己的报告与run两个精确attrs | 4.1.11真实兼容候选；未并入main，CR-R10新授权后才能应用 |

以上是当前权威登记，下表保留历史分工与结论。迁移编号/共享schema/锁/全局状态由主控统一；任何授权单一其他写者只限具体独立候选。

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

2026-10-14T22:07:43+08:00：R00修复候选15d0272由r00_independent_review在独立worktree定向复核；r01_resources仅准备外部PG/Redis和Compose插件与自身报告；r01_quality仅只读设计检查入口，代码所有权为scripts/dev.py、backend/tests/conftest.py、T02 unit、T03/T05/T07 integration、T07 jobs contract、新R01质量合同及自身报告；收到批准baseline前不写业务。主控负责公共接口/locks/迁移/infra/CI，当前无前端实现者。


2026-10-14T22:19:34+08:00：独立reviewer /root/r00_independent_review 已在冻结15d0272bd2a9e25d19397d8147e9c3cbe6016f9b完成56/56与静态检查、切片正负例、新干净Windows/WSL基线0/0。依据[reports/reviews/recovery/G-A-R00-review-1-recheck.md](../reports/reviews/recovery/G-A-R00-review-1-recheck.md)仅登记R00与三个R00输出切片accepted、九CR生效；原整T不自动接受，G-A未过门、未push。R01质量/前端从该批准合同基线独立worktree实施。真实PG16.14/pgvector0.8.2与Redis7.4.11资源已认证读写/重启/负例，仍非应用集成。
