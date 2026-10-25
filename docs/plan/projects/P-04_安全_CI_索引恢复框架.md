# P-04 · 安全/CI/索引恢复框架

- 文档首次创建时间：2026-10-25T10:05:00+08:00
- 本次写作开始时间：2026-10-25T10:05:00+08:00
- 最后更新时间：2026-10-25T10:05:00+08:00
- 状态：立项卡（待评审）；实施批的步骤依据

## 目标

把分散的安全/恢复能力收敛为**可重复执行的框架**：CI 流水线真实跑容器集成层、索引（OpenSearch）恢复 runbook 与 rebuild 工具化、安全门（秘密扫描/R20 登记/CPU 资源门）CI 化聚合，对应评分项：工程化交付质量（T45/T50/T51、R20 后续）、"静态 PoC 核查不等于运行成功"的持续验证。

## 现状与已有基础（路径全部实测存在）

- CI：`.github/workflows/ci.yml`（唯一 CI 文件，120 行）——backend job（ruff/mypy → compose 拉 PG/Redis/OpenSearch+TLS fixture → 四层测试）+ frontend job（lint/typecheck/tests/build）。**集成层在 CI 里是否真实可跑未验证**（容器资源窗依赖，宿主 OQ-1 数据面问题归用户）。
- 秘密扫描：`scripts/security_scan.py`（t06，扫描 backend/src、scripts、frontend/src、frontend/dist、reports/runs；190 条分类登记）。
- R20 秘密登记控制：`backend/tests/security/test_r20_secret_provenance.py`（冻结 total_records=190，从 `reports/runs/recovery_r20_secret_provenance_20261016/registration_proposal.json` 与 `reports/runs/batch21_r20_registry_extension_20261024/registration_proposal.json` 读登记，bundle sha256 强校验）；fixture bundle：`fixtures/synthetic/security/r20_secret_provenance_20261016.zip`、`fixtures/synthetic/security/r20_registry_extension_batch21.zip`；分类表 `reports/security/recovery_fixture_false_positives.json`。
- CPU/资源门：`backend/src/ai_intel/infrastructure/process_limits.py`（原生内存限制+采样 CPU 强制）；测试 `backend/tests/unit/test_r20_native_cpu_guard.py`、`test_r20_process_startup.py`。
- 安全测试面：`backend/tests/security/` 44 文件（全清单见盘点）。
- 索引恢复素材：OpenSearch 客户端/索引/检索 `backend/src/ai_intel/retrieval/opensearch_client.py`、`indexing.py`、`hybrid.py`、`runtime_policy.py`；部署 `infra/compose/compose.yaml` + `infra/compose/opensearch/opensearch.yml`；TLS 测试栈 `infra/compose/compose.search-secure.test.yaml` 等。**索引重建工具不存在**（历史证据 `reports/runs/recovery_reviewed_integration_20261016/parallel_0149_receipt.json` 记录 `indexes=rebuild_required`，无 rebuild 执行器）。
- 备份恢复：`scripts/backup_restore.py`（离线操作员备份 + 空库带标记 rehearsal 恢复）；测试 `backend/tests/unit/test_r20_backup_restore.py`、`backend/tests/integration/test_r20_backup_restore_pg.py`；历史 rehearsal worktree `.git/worktrees/r20-backup-rehearsal`、`r20-restore-rehearsal`。
- 容器验证路径：`scripts/dev_single_container.py`（单容器冒烟编排）、`scripts/smoke_main_path.py`（退出码合同 0/1/2）、`scripts/dev_integration_container.py`（逐文件 integration harness，batch23 已扩展组模式端口钉定）。

## 分批步骤（每批一个可提交单元）

- **B1 索引 rebuild 工具**（纯增量）：新增 `backend/src/ai_intel/retrieval/rebuild.py`——从 PostgreSQL 权威事实重建 OpenSearch 索引（复用 `indexing.py` 的写入路径），`--dry-run` 统计与真实重建两段式；直属 unit/contract 测试（fixture OS 或合同级 mock，显式标记）。验收：新测试全绿；`test_t30_hybrid_retrieval.py` 无回归。
- **B2 索引恢复 runbook + 集成验证**：`docs/runbooks/index_recovery.md`（备份→rebuild→一致性核对的命令级步骤）+ integration 测试（单容器 harness 加 OpenSearch 面——资源允许时）。验收：runbook 中每条命令有对应测试或 not_run 记录。
- **B3 CI 集成层验证与聚合**（触 CI 公共面——见风险1）：`.github/workflows/ci.yml` 增加 integration container job（复用 `dev_integration_container.py`，2g/2cpu 一次性容器）与安全门聚合 job（t06 + R20 + mypy strict 输出归档）。验收：CI 语法校验（actionlint 或 yaml parse）+ 本地等价命令链全绿（真实 CI 运行记 not_run——无运行器授权）。
- **B4 安全门盘点收口**：把 44 个 security 测试 + t06/R20/CPU 门映射为一份 `docs/runbooks/security_gates.md` 检查清单（每门:命令、期望退出码、失败处置），与 CI 聚合 job 对应。

## 明确不做

- 不在无授权运行器时宣称 CI 真实通过（命令本地等价执行 + not_run 记录）。
- 不修宿主 WSL2/Docker 数据面（OQ-1 归用户）；CI 集成层 job 的真实运行依赖资源窗。
- 不改 R20 冻结登记（扩展仍走 R20 提案程序）；不改金标/阈值。

## 风险与合同触点

1. **B3 触 CI 公共面**：workflow 变更影响全部后续提交的门禁语义——步骤前需 CR（含"CI 不把 blocked 记为通过"的退出码约定）。
2. **B1 触索引合同**：`hybrid_schema.py` 的索引 schema 与 `runtime_policy.py` 开关语义被 `test_t30_hybrid_retrieval.py` 冻结——rebuild 只能复用既有写入路径，不得另建平行索引结构（PostgreSQL 权威不变量）。
3. **B2 的真实 OpenSearch 集成**依赖容器资源与镜像（pgdg/OS 镜像拉取），受宿主数据面现状限制——not_run 显式记录。

## 预估批次数

4（B1–B4 各一批；B3 含一次 CR）。

---

## 路径核对记录（2026-10-25T10:1x+08:00 复核：脚本化逐一 ls 全部引用路径 106 项，唯一失配 experiments/run_eval.py 的误写已修正为仓库根路径；核对脚本输出见 reports/runs/batch23_projects_path_check.txt）

- 抽查核对：`.github/workflows/ci.yml`、`scripts/security_scan.py`、`backend/tests/security/` 44 文件、`backend/src/ai_intel/infrastructure/process_limits.py`、`scripts/backup_restore.py` 及其两个测试、`infra/compose/` 11 项清单、两个 R20 fixture zip 均存在。
- 确认不存在（已搜索核实）：索引 rebuild 执行器（仅历史证据记录 rebuild_required 状态）、backend/scripts/ 目录、独立 rehearsal 脚本文件（能力内置于 backup_restore.py）、其它 CI 平台配置。
