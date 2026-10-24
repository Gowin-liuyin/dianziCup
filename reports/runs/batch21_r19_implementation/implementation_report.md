# 批次21 C5.3 · R19 标注工具与开发集基础设施 —— 实现报告

- 任务编号：批次21 C5.3（R19 dev-set 基础设施）
- 任务状态：`awaiting_review`（代码与产物完成，等待评审；未自行标 accepted）
- 实现状态：`complete`（本批改动域内）；验证状态：unit `passed`、integration（互操作 validate）`passed`、live `not_run`（无外部模型/来源依赖，属设计内离线批次）
- 文档首次创建时间：2026-10-25T03:39:49+08:00
- 最后更新时间：2026-10-25T03:39:49+08:00
- 实现开始时间戳：2026-10-25T03:14:50+0800（date +%Y-%m-%dT%H:%M:%S%z 原始输出；`timestamps.txt` 记录种子构建时刻 2026-10-25T03:36:16+0800 与报告落盘时刻）
- 分支：codex/full-delivery-recovery；HEAD `b467cd69c`；实现前工作区已有 batch21 既有未提交改动，未触碰
- 实现规格：`reports/runs/batch21_r19_r21_research/r19_plan.md` 步骤 A–E（已完整读取并逐步执行）

## 1. 改动文件（git status 实证）

新建：
- `benchmarks/schemas/dev_set_manifest_v1.json` —— R19 本地装配格式 schema（非公共合同）
- `scripts/annotation/build_synthetic_seed.py` —— pilot_cases → candidate_case_v1 种子适配器
- `scripts/annotation/assemble_dev_set.py` —— 多 bundle 装配 CLI
- `scripts/annotation/tests/test_dev_set_assembly.py` —— 直属测试（10 例，独立成文件）
- `benchmarks/manifests/r19_synthetic_dev_seed_v1.json` —— 产物1（20 synthetic/dev 种子）
- `benchmarks/manifests/r19_dev_set_assembly_v1.json` —— 产物2（1 real + 20 synthetic dev-set manifest）
- `reports/runs/batch21_r19_implementation/*` —— 本报告与全部命令证据

追加（仅追加一节，未改既有内容）：
- `docs/runbooks/annotation_preparation.md` —— “开发集装配（批次21 C5.3 新增）”节

未修改（核过 git status）：`scripts/annotation/prepare.py`、`benchmarks/schemas/candidate_case_v1.json`、`fixtures/synthetic/pilot_cases.json`、`benchmarks/manifests/r19_public_dev_candidate_v1.json`、`backend/` 全部文件。

## 2. 实现内容

- **schema（步骤A）**：`dev_set_manifest_v1.json` 定义信封（schema_version/prepared_at/cases/candidate_sha256/summary）+ summary 内装配字段（dev_set_id、assembled_at、source_bundles[]{path,candidate_sha256,case_count,data_kind_counts}、counts.by_data_kind/by_split、label_status_counts（恒全 awaiting_human_label）、gold（human_gold_count const 0、gold_status const none_no_human_labels、formal_evaluation const not_run/null/null）、dev_set_sha256、scale_statement 固定串）。`id/hash/time/source/evidence/candidate_case` 定义在校验时从 candidate_case_v1.json 合并提供（复用其 $defs，不复制公共合同文本）。设计取舍见 §5 偏差2。
- **种子适配器（步骤B）**：只读 pilot_cases.json；20 例全部映射 `data_kind=synthetic`、`split=dev`、`source_kind=fixture`、`uri=urn:synthetic:<case_id>`；`event_family_id` 由去尾数字前缀推导（12 个稳定家族，修订/同族同 split）；evidence span 取该案例 `input` 规范化 JSON（ensure_ascii=false、sort_keys、紧凑分隔符）的前缀 ≤240 字符，start_offset=0、end_offset=len(quote)、quote_sha256/locator json_pointer="/"全部离线可验；`candidate_origin=model_assisted`；`candidate_task` 只写场景任务并声明提案仅作复核参照；limitations 指回原 case_id、记录旧值域降级、声明提案非金标、许可 unknown/unverified；输出经 `validate_candidates` 自检后用 `write_new` 独占新建。
- **装配 CLI（步骤C）**：`--bundle`（可多次，≥1 否则 BUNDLE_REQUIRED）+ `--output`（独占新建）+ 可选 `--dev-set-id`（缺省由 dev_set_sha256 前 16 位派生）+ 可选 `--scan-root`（复用 scan_leaks）。逐 bundle 复用 `validate_candidates`（含 candidate_sha256 绑定）→ 显式拒绝 holdout split（HOLDOUT_SPLIT_REFUSED）与任何非 awaiting_human_label 的 case（LABEL_STATUS_NOT_AWAITING）→ 全部 cases 合并后再跑一次同规则校验，使跨 bundle 重复 case_id（DUPLICATE_CASE）与家族/alias/document_id/URI 键域跨 split（FAMILY_SPLIT_LEAK）被拒绝 → 生成 counts/label_status_counts/gold/dev_set_sha256（只绑定 cases+counts+label_status_counts，同输入确定）→ 输出前按 dev_set_manifest_v1 自校验（DEV_SET_SCHEMA_INVALID）→ stdout 只打印计数与状态，不打印案例内容。
- **测试（步骤D）**：10 例全绿（数字见 §3），覆盖计划表格 1–10 全部用例；负例全部只改临时副本，不触碰仓内产物。
- **文档（步骤E）**：runbook 追加节落盘。`reports/acceptance/dataset.md` 未建（超出本任务声明改动域，见 §5 偏差3）。

## 3. 真实测试命令与结果（全部在仓库根 D:\dianzi 执行）

| 命令 | 证据文件 | 结果 |
|---|---|---|
| `VIRTUAL_ENV=D:\dianzi\backend\.venv uv run python -m unittest discover -s scripts/annotation/tests -p "test_dev_set_assembly.py" -v` | test_dev_set_assembly.txt | **Ran 10 tests in 4.446s，OK，exit=0（10 passed / 0 failed / 0 skipped）** |
| `VIRTUAL_ENV=… uv run python -m unittest discover -s scripts/annotation/tests -p "test_prepare*.py" -v` | test_prepare_existing_group.txt | Ran 40 tests in 65.076s，OK，exit=0 |
| `VIRTUAL_ENV=… uv run python -m unittest discover -s scripts/annotation/tests -p "test_crash_recovery.py"` | test_crash_recovery_group.txt | Ran 22 tests，OK，exit=0 |
| `VIRTUAL_ENV=… uv run python -m unittest discover -s scripts/annotation/tests -p "test_fd_metadata_error.py"` | test_fd_metadata_group.txt | Ran 7 tests，OK，exit=0 |
| `VIRTUAL_ENV=… uv run python scripts/annotation/build_synthetic_seed.py --input fixtures/synthetic/pilot_cases.json --output benchmarks/manifests/r19_synthetic_dev_seed_v1.json` | build_seed_command.txt | exit=0；case_count=20，candidate_sha256=b69208ae…7481f |
| `VIRTUAL_ENV=… uv run python scripts/annotation/assemble_dev_set.py --bundle benchmarks/manifests/r19_public_dev_candidate_v1.json --bundle benchmarks/manifests/r19_synthetic_dev_seed_v1.json --dev-set-id r19_dev_set_assembly_v1 --output benchmarks/manifests/r19_dev_set_assembly_v1.json` | assemble_command.txt | exit=0；case_count=21，dev_set_sha256=dac8842e…5156 |
| `VIRTUAL_ENV=… uv run python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_synthetic_dev_seed_v1.json` | validate_seed_prepare.txt | **exit=0**（candidate_count=20，human_gold_count=0） |
| `VIRTUAL_ENV=… uv run python scripts/annotation/prepare.py validate --input benchmarks/manifests/r19_dev_set_assembly_v1.json` | validate_dev_set_prepare.txt | **exit=0**（candidate_count=21，human_gold_count=0） |
| 泄漏抽查（python 内联，banned 标记含 expected_result 键值特征/R-REV-01 等） | artifact_leak_spotcheck.txt | RESULT: CLEAN，exit=0 |

退出码全部以追加模式记录（`cmd > file 2>&1; echo "exit=$?" >> file`），未用管道取 $?。既有 40+22+7 例回归全部通过，说明新增文件未破坏既有标注切片。

## 4. 验收对照（任务六条）

1. schema 存在且自洽 —— 是：gold.human_gold_count const 0、formal_evaluation status/numerator/denominator const not_run/null/null、scale_statement const 固定串，另有 gold_status/gold 块 additionalProperties:false；测试 1/3 实证。
2. build_synthetic_seed.py 20 例转合规 bundle —— 是：产物通过 validate_candidates 与 prepare.py validate exit 0；real 候选文件未动。
3. assemble_dev_set.py 多 bundle 合并 + 跨 bundle 家族隔离复检 + holdout 拒绝 + 非 awaiting 拒绝 —— 是：测试 2/6/4 分别以 FAMILY_SPLIT_LEAK/HOLDOUT_SPLIT_REFUSED/LABEL_STATUS_NOT_AWAITING 实证。
4. 10 用例全绿 —— 是：10 passed / 0 failed（4.446s）。
5. 两个产物通过 prepare.py validate —— 是：两条命令均 exit 0（证据文件在案）。
6. 见本报告 §3/§5。

## 5. 偏差与合同说明（非静默，逐条报告）

1. **测试解释器选择**：任务给定 `uv run python -m unittest …`，但仓库根无 pyproject，`uv run python` 解析到的 Python 3.14.3 无 jsonschema（ModuleNotFoundError，prepare.py 硬依赖）。采用最小改动形式 `VIRTUAL_ENV=D:\dianzi\backend\.venv uv run python …`（与 runbook 既有 backend/.venv 一致；实测 `VIRTUAL_ENV` 前缀下 uv run 确实使用该 venv）。discover 参数、执行目录、分组方式与要求完全一致。
2. **dev-set manifest 信封结构（步骤A 与验收5 的调和）**：r19_plan 步骤A 列出装配字段；但 candidate_case_v1 的 candidate_bundle 为 additionalProperties:false，若这些字段放顶层，产物2 永远无法通过 `prepare.py validate`，与硬验收5“两个产物文件通过 prepare.py validate（最硬互操作回归）”直接冲突。处理：信封采用 candidate_bundle 兼容形状（schema_version/prepared_at/cases/candidate_sha256/summary），步骤A 全部字段以原名/原常量放入 `summary`（schema 以 const 固定 gold 三常量与 scale_statement）。步骤A 的字段清单、常量、minItems、digest 规则全部保留；candidate_case_v1 与 prepare.py 未动；产物2 实测 exit 0。此为显式设计决定，如评审认为必须顶层，可按变更单调整 schema 与装配器（测试 1/3/9 会同步失败提示）。
3. **`reports/acceptance/dataset.md` 未创建**：r19_plan 步骤E 提及该骨架，但本次委托的改动域未包含 `reports/acceptance/`；未越权创建，留给有该域授权的任务。
4. **`progress/task_state.json` 未更新**：不在本次改动域内，由协调方按本报告登记 T46 相关状态（建议保持 pending/partial，不因工具就绪改绿）。
5. **装配器检查顺序**：显式 holdout/label_status 拒绝先于逐 bundle validate_candidates，使精确错误码可观察（否则 schema const 会先报 SCHEMA_INVALID）。对合法输入无可观察差异，与计划第3/4条“拒绝”语义一致。
6. **家族推导结果**：20 例合成种子归并为 12 个 event_family（SYN-REV/VER/UNK/CONF/EMPTY/TENANT/PERS/TIME/LINK/DOC/EVID/WITHDRAW），全部 dev split，满足 T46-C01 同族同 split。

## 6. 本批未达成事项（与 r19_plan §6 一致，如实入 OQ）

真实双人独立标注、分歧裁决与身份核验（T46-C02 真人半边）；冻结 manifest 与签字；真实规模扩展（当前 1 real + 20 synthetic 种子，仅覆盖 06_testing:39 的“20 题验证标注规则”区间）；实际镜像/索引输入的泄漏审计（scan 仅为显式公开树局部检查，当前装配物无 holdout、needle 为空）。工具侧行为已就绪并被测试覆盖，不伪装真人完成。

## 7. 下一任务建议

C5.4 评测 harness（r21_plan §3.1）以 `benchmarks/manifests/r19_dev_set_assembly_v1.json`（dev_set_id=r19_dev_set_assembly_v1，dev_set_sha256=dac8842e6202285246a5e2d4c0ed7c045d218a0eff7f2075d9ca8b044b135156）为输入；无 dev-set 时须显式 blocked 而非空跑；harness 不得把 21 例 awaiting_human_label 候选当金标计分。
