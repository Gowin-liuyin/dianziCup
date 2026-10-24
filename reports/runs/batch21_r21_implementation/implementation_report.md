# 批次21 C5.4 · T47/R21 评测框架骨架 —— 实现报告

- 任务编号与状态：T47 / R21-C5.4 骨架切片，实现状态 `complete`（代码与测试），验证状态 unit `passed`；整体置 `awaiting_review`，未自行判 accepted
- 执行方案：`reports/runs/batch21_r19_r21_research/r21_plan.md` §3 骨架设计、§4 步骤 A–C+D（步骤 E 可选项本批 not_run）
- 实现时间窗：2026-10-25T00:52:00+08:00 开始（读方案/核对合同），首次全绿 2026-10-25T03:39:41+08:00 前后，本报告落盘 2026-10-25T03:43:02+08:00
- 运行时点 HEAD：测试与收据生成时为 `b467cd69c3042d6...`（brunch codex/full-delivery-recovery），报告撰写时 HEAD 已被并行切片推进至 `cce9e1d901dd18ad8169de020634d24da13cc6f5`；收据内 code_sha256 为实测当时值

## 1. 改动文件（全部新增，无既有模块 diff）

- `backend/src/ai_intel/evaluation/__init__.py`（包说明）
- `backend/src/ai_intel/evaluation/records.py`：ResultRecord（frozen pydantic，字段显式）、MetricTriple 三元组、CodeFingerprint（git HEAD 40hex+dirty）、`beijing_timestamp()`（秒级 +08:00）、`canonical_sha256`/`file_sha256`/`compute_code_fingerprint`
- `backend/src/ai_intel/evaluation/configs.py`：ExperimentConfig（extra=forbid、`model_config` 别名字段、`data_mode` 恒 fixture、`cost_cap` 恒 Literal[0]）、AblationFlags 五轴 default 全 on + `ablation_status()`、`load_experiment_config`（schema 失败/未知字段 → `config_schema_invalid`）、`load_dev_set_manifest`（缺失 `blocked_input_missing`、无效 `blocked_input_invalid`、holdout 混入 `blocked_holdout_split_detected`、声明金标 `gold_scoring_not_implemented`、hash 不符 `blocked_data_hash_mismatch`）
- `backend/src/ai_intel/evaluation/registry.py`：B0/B2/B2b/B3 available、B1 not_implemented、B4_ref not_reproduced、B5 partial（call_spec 均带 file:line：hybrid.py:347/:360、graph.py:59/:64、revalidation/service.py:65/:88/:199）
- `backend/src/ai_intel/evaluation/runners.py`：CaseRunner 协议 + CaseRunContext（可比性上下文）+ `resolve_model_gate`（fixture 放行；真实 provider 无凭据 `model_credential_missing`、有凭据仍被 cost_cap=0 拦 `model_budget_not_authorized`）+ InvestigationGraphStubRunner（真实调用 `build_investigation_graph(strategy, stub_executor, InMemorySaver())` 离线执行）+ RetrievalStubRunner（面向 HybridRetriever.retrieve 调用规格的 stub）+ RegistrationOnlyRunner（B1/B4_ref/B5 只产如实登记记录，无指标）
- `backend/src/ai_intel/evaluation/metrics.py`：`metrics_for_outcome`（0 gold ⇒ accuracy/critical_claim_accuracy/evidence_support 恒 `not_computable_no_gold`、numerator=null、denominator=case_count；三率 `computed_fixture_scale`）、`summarize_run_metrics`、`coverage_matrix`（逐 case 全可见）、`assert_metric_pair_present`（单指标提升声明拒绝）
- `backend/src/ai_intel/evaluation/writers.py`：RunSummary 收据模型（含固定页眉 "fixture-scale，非正式指标，不是官方评分材料"、`cross_baseline_comparison="not_generated"`）、writer 三条固定标注缺一即拒（`fixture_scale_annotation_missing`）、metrics 缺任一率拒（`incomplete_metric_pair`）、收据目录独占创建（`run_receipt_directory_exists`）、live 通道 `write_live_results_receipt` 恒拒绝 `live_results_forbidden_budget_zero`
- `backend/src/ai_intel/evaluation/replay.py`：`compare_runs` 字段级 diff（hash 门 + summary/record 行为字段；时延/时间戳列为排除项；单侧缺失以 sentinel 呈现不丢 case）
- `experiments/configs/`（7 份）：`b0_retrieval.json`、`b2_four_roles.json`、`b2b_nine_roles.json`、`b3_gap_scheduling.json`、`b5_full_recompute.json` 可执行配置 + `b1_single_agent.not_implemented.json`、`b4_external.not_reproduced.json` 如实登记
- `experiments/run_eval.py`（CLI）：`run` / `compare` 子命令；退出码 0 通过（含如实登记 blocked）/ 1 失败（failed 记录或收据拒绝）/ 2 参数·配置·注册表错误 / 3 未建设（manifest 声明金标）/ 4 输入阻塞（manifest 缺失·无效·hash 不符·模型门阻塞）
- `backend/tests/unit/test_t47_baselines_and_ablation.py`：19 个测试，覆盖计划 §5 C01–C06 全部骨架级断言 + manifest 输入面 + 配置/注册表负例 + 复跑比较 + CLI 端到端 4 条（subprocess 真跑）
- 本证据目录：`fixture_input/`（显式 synthetic fixture manifest + 2 份演示配置）、`runs/eval_*/`（3 份真实收据）、`cli_demo_log.txt`、`test_run_log.txt`、本报告

## 2. 真实测试命令与结果（cwd=backend）

- `uv run python -m pytest tests/unit/test_t47_baselines_and_ablation.py -q --no-cov`
  → **19 passed in 8.32s，exit=0**（完整输出见 `test_run_log.txt`；此前迭代 16 passed→3 failed→修复→19 passed，未跳过任何用例）
- `uv run ruff check src/ai_intel/evaluation/ tests/unit/test_t47_baselines_and_ablation.py ../experiments/run_eval.py` → All checks passed
- `uv run ruff format`（按仓库 ruff format 规范重排 6 文件后）→ 全部通过
- `uv run mypy src/ai_intel/evaluation/` → Success: no issues found in 8 source files
- CLI 演示（`cli_demo_log.txt`，追加模式记录退出码）：
  1. B2b fixture 真跑（本目录 fixture manifest，hash 已验证）→ exit=0，`status_counts={"completed": 2}`，`accuracy_status=not_computable_no_gold`，收据 `runs/eval_20261025T034130745224+0800-B2b/`
  2. 同配置复跑 → exit=0，收据 `...034140488821...`
  3. `compare` 两次收据 → exit=0，`behaviorally_identical=true`，三个 hash 门全等，diff 为空
  4. 非 fixture provider 演示配置 → exit=4，`status_counts={"blocked_model_missing": 2}`，六指标分子全 null（C06），无任何模型调用/费用
  5. shipped `experiments/configs/b2b_nine_roles.json` → exit=4 `blocked_input_invalid: dev_set_id missing`（见 §4 外部阻塞）
  6. shipped `b5_full_recompute.json` → 同上 exit=4
- 改动域核查：`git status --porcelain` 中 backend/ 既有模块零 diff；新增仅 evaluation/、T47 测试、experiments/（未触碰 retrieval/investigation/revalidation/answering、schema/迁移/公共合同、benchmarks/）

## 3. 评分项/验收对照

1. evaluation/ 骨架模块真实存在且被测试覆盖：✅（records/registry 基线表/指标三元组/fixture-scale 强制 writer/复跑 compare 均有专属测试）
2. 五配置 + B1/B4 如实登记：✅（7 份 JSON 全部通过 schema 与注册表校验；B1/B4 配置注明不可用原因，runner 产 blocked/not_reproduced 记录且 metrics 为空）
3. CLI 对 fixture 数据真实可执行 + schema 校验失败拒绝：✅（演示 1–4；未知字段 exit=2 `config_schema_invalid` 由测试 `test_cli_rejects_invalid_config_schema` 覆盖）
4. 测试全绿真实数字：✅ 19 passed / 0 failed / 0 skipped
5. 硬约束：未扩 Strategy Literal（B1 以注册表表达）；消融开关只在 evaluation 层声明（`switch_declared_mechanism_not_wired`）；分母恒 case_count 不删 case；一切输出带 fixture-scale 标注与 disclaimer；0 gold ⇒ accuracy `not_computable_no_gold`；费用上限=0，真实模型路径恒 blocked；未写任何正式指标声明

## 4. 未通过/未运行/外部阻塞

- **R19 dev-set manifest 尚为中间形态**：演示 5/6 时 `benchmarks/manifests/r19_dev_set_assembly_v1.json` 已存在（并行 Agent 写入中），但顶层只有 `candidate_sha256/cases/prepared_at/schema_version/summary`，缺 r19_plan 步骤 A 合同的 `dev_set_id` 与 `gold` 块 → harness 如实 `blocked_input_invalid` exit=4，不空跑、不猜接口、不做兜底放宽。C5.3 最终装配落地后（含 dev_set_id/cases/gold）无需改本骨架代码即可真跑 21 cases。
- 步骤 E（integration 冒烟：隔离 PG + FixtureSemanticModels + main_path_story 真跑 B0/B2b）：**not_run**（可选项，骨架验收不依赖；r21_plan §4-E 已预留转后续轮）
- B0/B5 行为级验证（真实 PG）、B1 实现、B4 复现、行为级消融、金标评分、正式冻结与配对实验：本批不可达，如实 not_implemented/not_reproduced/not_run，未预填任何提升百分比
- live 结果通道：存在但恒拒绝（`live_results_forbidden_budget_zero`），测试覆盖

## 5. 合同与计划偏差（显式声明，未静默处理）

1. **C01 的 config_sha256 跨基线不同**：r21_plan §5 C01 字面预期 B0/B2/B2b/B3 的 config_sha256 "相同"，但按 §3.1 该 hash 绑定整份配置（含 baseline_id/strategy），跨基线必然不同。实现取 config_sha256=整份配置 hash（复跑绑定语义正确），测试改为断言"资源字段跨基线一致 + config_sha256 逐基线绑定正确 + 同基线复跑不变"（replay 测试覆盖）。若评审要求"跨基线相同"，需改 hash 口径为剥离基线标识的资源配置 hash，走变更单。
2. **`data_ref.expected_sha256` 允许 null**：R19 装配未完成时期望 hash 不可知；null 时记录实测 hash 且 `data_hash_verified=false`，不虚构期望值。装配冻结后应回填。
3. **`code_ref.expected_head` 允许 null**：分支由并行切片持续推进，强校验会误伤；null=只记录实测 HEAD+dirty。
4. **compare 以 `run_eval.py compare` 子命令交付**而非计划 §3.5 的独立 `experiments/compare_runs.py` 文件：本批授权改动域仅列 `experiments/run_eval.py` 一个 CLI 文件，故比较逻辑放 evaluation/replay.py + CLI 子命令；后续轮可加薄封装脚本。
5. **blocked_model_missing 的 run 退出码=4**：计划未明确规定该场景退出码；按 dev.py "4 资源阻塞" 语义选取（failed 才是 1），CLI docstring 已写明。
6. **CLI 对 shipped 配置的演示只到 blocked**：按硬约束演示不绕过 R19 输入面；fixture 真跑由本证据目录的 synthetic manifest 承担。

## 6. 下一任务建议

- C5.3 装配定稿后：回填 7 份 shipped 配置的 `expected_sha256`，用真实 21-case dev-set 重跑 CLI 演示与复跑比较（骨架零改动）。
- 可选步骤 E（integration 冒烟）与行为级消融、B1 实现、B4 复现：需模型授权/DB/预算，进正式 R21 轮并走变更单。
- 评审关注点建议：偏差 1（config_sha256 口径）与偏差 5（blocked 退出码）需要评审人确认或发变更单。

- 文档首次创建时间：2026-10-25T03:43:02+08:00
- 最后更新时间：2026-10-25T03:43:02+08:00
