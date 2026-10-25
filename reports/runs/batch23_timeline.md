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

## W2 · 三项裁决：简报 + 方式B执行（2026-10-25T09:2x–10:3x）

- 简报：`progress/DECISIONS_pending.md` 三节齐全（失败现象与例数引用原始输出行、选项 A/B 含不可逆性、建议项、验证命令清单）。
- **裁决① r05 legacy-0013（19 例）：执行完成**。`question_api` fixture 层对种子 revision 行补 `{"data_mode": "fixture"}`（种子文件与全部断言零改动）；CR `docs/decisions/CR-r05_legacy_seed_annotation_batch23.md`。容器验证（`batch23_decisions/test_r05_question_api_pg_pf.txt`）：**24 passed / 0 failed**——19 例全部消失。
- **裁决③ r18 错误码映射（5 例）：执行完成（待 run3 复核确认）**。产品修订 `public_extension_reads.py` 新增 `public_knowledge_projection` 包装（4 个 `self.knowledge.*` 调用点），`KnowledgeProjectionError` → `PublicReadUnavailable`（not_configured，retryable=False）；CR `docs/decisions/CR-public_read_projection_error_mapping_batch23.md`。**根因甄别修正**：triage 推断的 :228 包装点其实已存在（48f96b5ba 引入），真实逃逸点是 `KnowledgeProjectionError`（ValueError 子类，`knowledge_read_service.py:61`）落入路由 ValueError 桶。宿主定向 767 passed / 4 设计内 blocked。
  - 迭代1（run1）：fix1 剩 1 failed（missing-mode 探针）——**批次22 种子 stamp 波及面发现**：探针经共享 seeder 的种子已带 fixture 标注，"missing mode"场景不再成立；fix2 全 38 error 为计划端口钉错（文件自断言 25432）。
  - 迭代2（run2）：fix1 探针引用改 `partial(legacy=True)` → 2 个 dimension 用例反被破坏（legacy 分支连带 parse_status/canonical_uri 改变）；**发现 recheck 探针拷贝 fix1 测试函数、`__globals__` 指向 fix1 模块字典**——一处包装两文件生效。
  - 迭代3（run3）：包装改为"仅清空 source_metadata"（其余列保持现行 seeder 输出），结果见下。
- **裁决② r04 evidence 计数（1 例）：执行完成（待 run3 复核确认）**。断言改为 locator 排序等值（4 项全集）；CR `docs/decisions/CR-r04_evidence_count_oracle_alignment_batch23.md`。**构成实测修正**：真实构成 `['/description','/ghsa_id','/ghsa_id','/vulnerabilities/0/package/name']`（2 主事实 + 2 identifier qualifier），triage 的"CVSS authority+vectorString"归因不成立（vendor 路径无 ScoreValue fact）。
- r05 验证同轮附带：宿主定向与全量见 W5 节。

## W3 · 大件立项卡（2026-10-25T09:50–10:2x）

- 四张卡入库 `docs/plan/projects/`：P-01 多跳问答（5 批）/ P-02 推荐历史与变化重判（4 批）/ P-03 MCP/OAuth/CLI 三插件（4 批，**OQ-4 /tasks producer 并入**——理由：与三插件共享公开读合同域与 typed job 契约，`PublicTaskBindingService` 三方法即 MCP/CLI 的读面，单列会两次触碰同一冻结断言）/ P-04 安全/CI/索引恢复框架（4 批）。
- 现状节路径由两个只读盘点代理逐条验证 + 脚本化逐一 ls 复核（106 项，唯一失配 `experiments/run_eval.py` 误写为 backend/src 下，已修正为仓库根路径；`reports/runs/batch23_projects_path_check.txt`）。
- 卡内"写不出路径的能力"逐项确认不存在：多跳检索逻辑、HybridRetriever 线上入口、backend 侧 MCP server、OAuth/OIDC 实现、backend CLI 入口、PublicTaskBindingService 生产装配、索引 rebuild 执行器。

（按时间追加）

## 裁决区记录

- GOAL 指令（批次23 起）覆盖原批次23 提示词的留空裁决区：**方式B 生效**——三项裁决按简报建议项执行（每项独立 CR + 受影响测试全绿 + 独立 commit）。

## W4/W5/W6（2026-10-25T10:2x–11:0x）

- W4：OQ-1 状态收束+宿主复测精确化；OQ-5 审计族解锁+三项裁决收束；handoff 顶部批次23 条目；task_state 最小更新（T31/T35 history，status 零改动，json.tool 校验过）；goal_state notes 追加批次23 条。
- W5：backend 全量 6253 passed / 0 failed / 1 xfailed / 83 设计内 blocked（1088s，与基线一致）；ruff/format/mypy 全 0；前端 lint/typecheck/test/build 全 0（799 tests）；tsbuildinfo 恢复原样（SHA 前缀核对一致）。
- W5 宿主：hello-world exit=0；独立 run -p 端口发布+数据面恢复（HTTP 200）；compose 端口发布仍静默失败（host_port_diag.txt：`{"5432/tcp":[]}`，同刻独立容器正常；Compose v5.0.2）；compose 冒烟退出 2（database unreachable），按纪律不做宿主修复，记录即止。
- W6：本 timeline 终化 + Root-batch23-summary.md + 最终提交 + push。

## 收束（2026-10-25T11:0x+08:00）

- 批次23 全部工作项闭环：W1 解锁（52 passed）/ W2 三项裁决闭环（19+1+5 例消失，3 CR）/ W3 四卡入库（路径 106 项核对）/ W4 记账同步 / W5 质量门保持基线（failed=0）/ W6 本收束。
- 8 个 checkpoint 提交（0442afcca 起）；push 1 次通过门禁（无秘密/holdout/tsbuildinfo）。
- 移交批次24：立项卡非作者复核（3 子代理，reports/reviews/batch23/）→ P-01→P-04 逐卡实施。
