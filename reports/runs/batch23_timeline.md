# batch23 时间线（唯一进度真相源）

- 文档首次创建时间：2026-10-25T08:56:00+08:00
- 本次写作开始时间：2026-10-25T08:56:00+08:00
- 最后更新时间：2026-10-25T08:56:00+08:00

## 定位

- 批次21/22 已完成并推送（终局报告 reports/tasks/Root-final-report.md）。
- 批次23 授权：本提示词（裁决准备、拓扑收尾与大件立项）。
- 裁决区：**留空 → 方式A生效**——W2 只产出三份决策简报（progress/DECISIONS_pending.md），不执行任何裁决修复；后续批次执行裁决前必须先拿到用户明示。
- 起点 HEAD：0f72e6d85（goal 收束提交）；工作树仅 .zcode/ 未跟踪。分支 codex/full-delivery-recovery。

## 工作项状态

- W1 审计族预置库拓扑：**完成（2026-10-25T09:3x+08:00）——52 passed / 0 failed / 0 errors，容器 exit=0**
- W2 三项裁决简报：完成（progress/DECISIONS_pending.md，方式B 执行中）
- W3 大件立项卡 ×4：pending
- W4 顺手收尾：pending
- W5 质量门与宿主探测：pending
- W6 收尾：pending

## W1 · 审计族预置库拓扑（2026-10-25T08:56–09:3x）

- 勘探：审计族 = 1 helper（`backend/tests/r07_input_audit_helpers.py`）+ 5 测试文件（integration 3 + security 2），helper 断言 `(127.0.0.1, 25432, test_dianzi_r07_input_audit_20261016)` + `DIANZI_TEST_RUN_ID=r07_input_audit_20261016`。
- 复现（`repro_conflict/`，per-file 正确钉定 run_id+25432）：6 errors 全部 `DuplicateObject` 于 `install_audit_proposal` 的 `ADD CONSTRAINT ck_enrichment_step_input_audit`——**诊断精确化**：OQ-5 归因于"provisioning 迁移 head 与 helper install 冲突"，实际冲突是 helper 自身在 fresh schema 里 `run_migrations(head)`（含 0023，已采纳 test proposal 的 DDL）与 `install=True` 重装的内在冲突，与 provisioning 库状态无关（0023 于 2026-10-16 09:55 并入，晚于审计测试冻结语义"proposal 是安装者"）。
- 修复 1（fixture 层一行）：`owned_audit_engine` 的 `run_migrations(...)` 增加 `target_revision="0022_sbom_sidecars"`——恢复 helper docstring 自己声明的合同（"Test-only forward proposal; the production 0023 migration remains root-owned"）与 legacy 测试意图（先 0017 旧行快照→`install_audit_proposal` 中途安装→旧行保留断言）。业务代码零改动、断言零改动。
- 修复 2（测试层，镜像 batch22 的 R06_PROOF_TRACE_DIR 读写分离先例）：`test_r07_input_audit_pg.py` 的 observation 写入加 `R07_INPUT_AUDIT_TRACE_DIR` 环境变量重定向 + `mkdir(parents=True)`（原路径写冻结目录 `recovery_r07_input_audit_20261016`——该目录在仓库中不存在且容器 /repo 只读，固定 FileNotFoundError）；harness `build_environment` 注入 `/out/r07_input_audit_trace`。观察文件实际落盘 `fixed_run3/r07_input_audit_trace/nvd_current_selection_observation.json`，冻结目录零触碰。
- 修复 3（harness 层）：组模式支持可选 `port` 字段（`group.get("port", 5432)`，历史组计划零影响）——batch21 审计组只含 3 个 integration 文件且组模式硬编码 5432；security 2 文件含裸导入 `test_r06_catalog_documents_pg`（`fixed_run2/` 52 errors 全部为 helper :65 端口断言 + ModuleNotFoundError 两类），需 5 文件同组同 pytest 收集（batch21 的裸导入解析先例）+ 端口 25432。
- 迭代记录（非同根因扩补丁，是三层独立前置逐层解锁）：repro（复现内在冲突）→ fixed_run1（per-file：integration 3 文件 26 中 25 绿、security 2 文件 ModuleNotFoundError 暴露收集顺序层）→ fixed_run2（组模式 5432：52 errors 全部端口断言，暴露组端口层）→ fixed_run3（组模式 + port 25432：**全绿**）。
- 验收：`fixed_run3/audit_family_batch23.txt` 末行 `52 passed, 2 warnings in 136.21s`；harness exit=0。审计族从批次21 以来的"第三层迁移状态冲突"停止点推进到真实全绿。

## 裁决区记录

- GOAL 指令（批次23 起）覆盖原批次23 提示词的留空裁决区：**方式B 生效**——三项裁决按简报建议项执行（每项独立 CR + 受影响测试全绿 + 独立 commit）。

（按时间追加）
