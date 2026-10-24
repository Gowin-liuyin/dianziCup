# 独立审查（非作者）· 批次21 C3 "历史红清零三件套" 证据与变更单复核

- 审查人：R-A（非作者视角，独立审查）
- 审查时间戳：2026-10-25T00:01:27+0800（ Asia/Shanghai，`date +%Y-%m-%dT%H:%M:%S%z` 实测）
- 文档首次创建时间：2026-10-25T00:01:27+0800
- 最后更新时间：2026-10-25T00:01:27+0800
- 审查基线：分支 `codex/full-delivery-recovery`；C3 检查点提交 `13a580e23b0f09eb5249a27879574ece5f4faf14`（`git merge-base --is-ancestor 13a580e23 HEAD` 通过）。审查开始时 HEAD=`b4407f833`，审查期间 HEAD 前移至 `ee283de3e`（C5 groundwork，23:52:36 提交）；本报告全部结论锚定 `13a580e23` 及其 diff，不受后续提交影响。工作树中与本审查无关的未提交修改（`progress/OPEN_QUESTIONS.md`、`progress/goal_state.json`、`reports/runs/batch21_timeline.md`、`scripts/dev_integration_container.py`、`reports/runs/batch21_red_zero/c31_r20_t06_t02_rerun3.txt`）未被本审查触碰。
- 审查人权限遵守声明：仅使用 git 只读命令、`uv run python -m pytest` 复跑、以及写入本报告目录 `reports/reviews/batch21/`；未修改任何业务文件、测试文件或 `reports/runs/` 既有文件。

## 一、复跑结果（真实命令与退出码）

复跑均在 `D:/dianzi/backend` 执行，命令模式：`uv run python -m pytest <files> -q --no-cov > <文件> 2>&1; echo "exit=$?" >> <文件>`（管道未吞退出码，`exit=` 为 shell `$?` 原值）。

1. C3.1 组：`tests/security/test_r20_secret_provenance.py tests/security/test_t06_authentication_and_scope.py tests/unit/test_t02_project_skeleton.py`
   - 结果：**303 passed，exit=0**，493.72s（0:08:13）。
   - 证据：`reports/reviews/batch21/r_a_c31_rerun.txt` 第 6 行 `303 passed in 493.72s (0:08:13)`、第 7 行 `exit=0`。
   - 与作者留痕一致：`reports/runs/batch21_red_zero/c31_r20_t06_t02_rerun3.txt`（工作树当前版）同为 `303 passed / exit=0`；作者 `rerun2` 如实记录了中间态 `2 failed, 301 passed, exit=1`（`test_r20_secret_provenance.py` 1 例 + `test_t06_authentication_and_scope.py:162`），未发现伪造全绿的痕迹。
2. C3.2/C3.3 组：`tests/contract/test_r07_single_model_dimension_contract.py tests/contract/test_r11_r08_forward_migrations.py tests/contract/test_recovery_forward_migrations_0023_0026.py`
   - 结果：**67 passed，exit=0**，3.64s。
   - 证据：`reports/reviews/batch21/r_a_c32_c33_rerun.txt` 第 2 行 `67 passed in 3.64s`、第 3 行 `exit=0`；与作者 `reports/runs/batch21_red_zero/c32_c33_targeted_rerun.txt`（67 passed / exit=0）一致。
3. 佐证：`test_all_real_codecs_preserve_single_attempt_contract_and_metadata` 收集恰 **16** 个参数化（`pytest ... --collect-only -q` 计数=16），与 CR-R07 "16 个参数化红" 及 `reports/runs/batch20_offline_baseline/red_inventory.md` 第 56-61 行 B1 组（16 条，`r07-model-fields-2` vs `r07-model-fields-1`）完全吻合。

## 二、C3.2（CR-R07 prompt_version oracle 对齐）证据链核对

| CR 声称 | 核对结果 | 证据 |
| --- | --- | --- |
| 提交 `7dae1d823` 将 PROMPT_VERSION 由 -1 改为 -2 | **属实** | `git show 7dae1d823 -- backend/src/ai_intel/enrichment/model_fields.py` 第 35-36 行：`-PROMPT_VERSION = "r07-model-fields-1"` / `+PROMPT_VERSION = "r07-model-fields-2"` |
| 同提交入库 `docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md` 第 7 行记载该变更 | **属实** | `git show 7dae1d823 --stat` 列出该 CR 文件（+25）；该文件第 7 行：`变更：model_fields.PROMPT_VERSION 从 r07-model-fields-1 到 r07-model-fields-2` |
| `reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md` 第 5、21 行逐字记录 prompt `r07-model-fields-2`，Verdict: Ship，随 `daacf92ab` 入库 | **属实** | 该文件第 5 行 `**Verdict: Ship，仅限本次输入切片...**`；第 21 行 `...prompt \`r07-model-fields-2\`...`；`git show daacf92ab --stat` 首行即该审查文件（+67，提交信息 "review: freeze independent R07 input slice verdict"，2026-10-16T07:07:15+08:00，早于 C3 五天以上） |
| 测试断言自 `d8a3189bb` 创建后从未维护 | **属实** | `git log --diff-filter=A -- backend/tests/contract/test_r07_single_model_dimension_contract.py` 唯一创建提交为 `d8a3189bb`（2026-10-16T02:52:17+08:00） |
| 唯一改动：第 37 行 `-1`→`-2`；第 38 行 schema 断言未动 | **属实** | `git diff 6795db3e6..13a580e23 -- <该测试文件>` 仅 1 处替换：`-assert metadata.prompt_version == "r07-model-fields-1"` → `+...-2`（@@ -34,7 +34,7 @@，断言在第 37 行）；第 38 行 `schema_version == "r07-model-field-extraction-1"` 在上下文中原样保留；生产 `SCHEMA_VERSION` 在 7dae1d823 diff 中未变 |

## 三、C3.3（迁移 head 期望 0019/0026 → 0031）证据链核对

| CR 声称 | 核对结果 | 证据 |
| --- | --- | --- |
| 提交 `0291d1975` 引入 `0031_public_task_bindings` | **属实** | `git show 0291d1975 --stat`：`backend/src/ai_intel/migrations/versions/0031_public_task_bindings.py \| 68 +++`（2026-10-17T10:32:38+08:00） |
| G-E 复查文件第 17、55 行：0031 blob 未变、真实 PG migration child 升至 0031 exit 0 | **属实** | `reports/reviews/recovery/G-E-R18-typed-task-binding-review-1-recheck-batch17-7acd9ea9.md` 第 17 行 `...0031 migration blob未变...`；第 55 行 `...完整migration child到\`0031_public_task_bindings\` exit0并退出...` |
| 维护先例 root_batch17 将 7 个 integration 测试 head 期望 0030→0031，哈希留痕 | **属实** | `reports/runs/recovery_reviewed_integration_20261016/root_batch17_forward_head_expectations.json` 含 7 处 `0031_public_task_bindings` 且引用 `0030_revalidation_actor_bindings`（`grep -o ... \| wc -l` = 7） |
| 改动=两文件三断言位置；REVISIONS 冻结元组不动 | **属实** | `git diff 6795db3e6..13a580e23 -- 两文件`：`test_r11_r08_forward_migrations.py` 第 49 行 `get_heads()` 0019→0031 + `iterate_revisions("head","0016")` 显式 15 项清单（0031..0017）；`test_recovery_forward_migrations_0023_0026.py` 第 83 行 `get_heads()` →`0031`、`range(26,0,-1)`→`range(31,0,-1)`、iterate 显式 9 项（0031..0023）。无其他改动 |
| C2 追加：`test_r11_r08_migration_head_regression.py` 第 26 行守卫 0019→0031 一行改动；`r11_forward_fixtures.py` 不改 | **属实** | `git show b4407f833 -- <前者>`：单行 `"0019_aggregate_observations"`→`"0031_public_task_bindings"`（@@ -23,7 +23,7 @@，断言在第 26 行），文件 docstring 自述 "only the original revision guard is adapted" 与 CR 引述一致；`r11_forward_fixtures.py` 未出现在 C2/C3 任何 diff 中 |
| 红清单 B2（2 条迁移 head 红） | **属实** | `reports/runs/batch20_offline_baseline/red_inventory.md` 第 84-93 行、第 254 行（历史遗留-迁移head 2 条），错误行号 ：49 / :83 与当前断言行号一致 |

## 四、oracle_alignment_expectations.json 前后哈希核对

对 `reports/runs/batch21_red_zero/oracle_alignment_expectations.json`（三文件三组 old/new sha256）逐项实测（`git show <rev>:<path> | sha256sum` 与 `sha256sum <worktree>`）：

| 文件 | old_raw_sha256 | 实测 old（6795db3e6 blob） | new_raw_sha256 | 实测 new（当前工作树） |
| --- | --- | --- | --- | --- |
| test_r07_single_model_dimension_contract.py | 3d3d008d…230646 | **一致** | e69a7fa1…3aa41f7 | **一致** |
| test_r11_r08_forward_migrations.py | f4a75f95…5f928f9 | **一致** | de7df3f4…6ed436a | **一致** |
| test_recovery_forward_migrations_0023_0026.py | c25d224d…2e3d0（截断书写，全值见 JSON） | **一致** | 16738d7d…148e3d0（同上） | **一致** |

结论：**任务判据满足**——old 与 `13a580e23` 之前最近提交 `6795db3e6` 的文件内容哈希一致；new 与当前文件一致。两点精确说明：

1. 指令中提到的 `b4407f833` 实际是 `13a580e23` **之后**的 C2 提交，其 blob 已是新 oracle 内容（如 test_r07 blob=61a692eb…），不可能匹配 old；old 的正确前置点是 `6795db3e6`（C1，C3 前最后一个检查点）。
2. 仓库内 blob 均为 LF（三个文件 blob CR 计数=0），工作树因 `core.autocrlf=true` 为 CRLF（CR 计数 64/66/180）。因此记录中 old 是 `git show` 的 LF blob 哈希、new 是工作树 CRLF 原始字节哈希——口径混合但两个判据各自成立；`git diff 6795db3e6..13a580e23`（LF 域）直接证实内容变更仅为 oracle 替换。建议后续同类文件注明哈希取自哪种字节域。

## 五、C3.1 登记表扩展语义核对

以 `uv run python`（backend 环境）做 JSON 级比对：

1. **前 136 条逐条相等**：当前 `reports/security/recovery_fixture_false_positives.json` `records[0:136]` 与 `reports/runs/batch20_secret_classification_20261024/classification_records_54_ready_to_land.json` `records[0:136]` 逐条相等（True）；且与 `13a580e23` 前一版（`git show 6795db3e6:…`）的 136 条逐条相等（True）。`schema_version/scope/span_units/recorded_at/history` 均未变（recorded_at 仍为 2026-10-15T22:42:46+08:00）。
2. **追加 54 条与提案逐条相等**：`records[136:190]` == `reports/runs/batch21_r20_registry_extension_20261024/registration_proposal.json` 的 `table_records`（54 条，True）；亦等于 batch20 文件 `records[136:190]`（True）。`old_records_unchanged=true`、`total_records=190`、`new_records=54`。
3. **纯追加**：`git diff 13a580e23~1..13a580e23 --numstat -- reports/security/recovery_fixture_false_positives.json` = `1134 0`（0 删除，纯插入）。
4. **bundle 与绑定**：`fixture_bindings` 22 个路径；zip 实测 sha256 `72d9d734bd4b81df041788becbd8ac1ecb47ca4780ff887a9ba70204d0e9236b` 与提案 `fixture_bundle.raw_sha256` 及 CR-R20 声明一致；该 zip 由 `13a580e23` 新增（`--diff-filter=A` 唯一提交）；`prior_proposal_sha256=af832d0b…` 与原提案文件实测 sha256 一致；原提案 `proposals` 恰 82 行（"原 82 行提案" 属实）。54 条记录均带 `fixture_origin`（source_commit/path/line/blob/sha256、data_mode=fixture，与原提案同构）与 `review_ref`（前缀 `reports/reviews/recovery/G-B-secret-fixture-classification.md` + batch20 总结 + OQ-3 决议，54/54）。
5. **R20 测试合同扩展与 CR 描述一致**：`git diff 6795db3e6..13a580e23 -- backend/tests/security/test_r20_secret_provenance.py` 含 EXTENSION 提案/bundle 装载、`registration_for()`、`isolated_copy` 按归属提案取 bindings/bundle（原哈希校验语义保留）、`assert len(current) == PROPOSAL["total_records"] + EXTENSION["new_records"]` 与 `assert current[136:] == EXTENSION["table_records"]`；参数化测试集合扩为两提案并集。

## 六、冻结材料与扫描器未改动核对（git diff 均应为空，实测全部为空）

| 路径 | `git diff 13a580e23~1..13a580e23 --stat` |
| --- | --- |
| `scripts/security_scan.py`（CR-R20 "不放宽扫描器"） | 0 字节（空）✔ |
| `reports/runs/recovery_r20_secret_provenance_20261016/`（原提案 + `registry_original_bytes.bin`） | 0 字节（空）✔ |
| `fixtures/synthetic/security/r20_secret_provenance_20261016.zip`（原 bundle） | 0 字节（空）✔ |

另核实：原 82 行提案中样本行确实存在（`frontend/src/features/assets/asset-client.test.ts` line=23 行样本），且该登记文件字节未变（其 `raw_sha256=be7e9d73…` 与当前文件实测一致——R20 参数化套件把守并通过）。**未独立复算** 该样本 `match_sha256/value_sha256` 三字段全等：复算须运行 `generate_extension.py`（其 docstring 与第 147-149 行表明会回写 live registry 表并写 `reports/runs/` 产物，且要求表先回滚 136），超出本审查只读边界，记 `not_run`（见第八节）。

## 七、CR 内容如实性审查

1. 三份 CR 状态均为 `awaiting_independent_review` / 引用历史 CR 为 `awaiting_review`，**无任何把 awaiting_review 写成已审/accepted 的表述**；R20 提案 `review_status=awaiting_independent_review` 一致。
2. CR-R20 "明确不放宽的内容" 经第六节 diff 核实属实（扫描器零改动）；登记仍为精确位置+精确字节哈希豁免，测试合同把守属实。
3. CR-R07 "生产代码、PROMPT_VERSION 常量、模型接线零改动" 属实（C3 diff 无任何 `backend/src/` 文件）。
4. CR-migration "迁移文件、alembic 配置、生产代码零改动" 属实（C3 diff 无 `migrations/`、无 `src/`）。
5. 复跑留痕链（rerun1→rerun2 有 2 红→rerun3 全绿）如实反映修复过程，无编造通过数。

## 八、发现与结论

### 确认通过（关键项）

1. C3.1/C3.2/C3.3 全部六条指定测试独立复跑全绿（303 passed / 67 passed，均 exit=0），无挪红迹象（三文件 diff 仅含声称的 oracle/合同改动）。
2. C3.2 证据链真实：`7dae1d823` 确改 PROMPT_VERSION -1→-2，CR 与非作者独立初审（Verdict: Ship）在 git 历史可查、行号准确。
3. C3.3 证据链真实：`0291d1975` 确引入 0031，G-E 复查与 batch17 先例文件存在且内容吻合；三处断言改动与 CR 逐字对应，REVISIONS 冻结未动。
4. oracle 前后哈希表 old/new 与 git 实测一致（判据成立，含 CRLF 口径说明）。
5. 登记表 136→190 为纯追加：前 136 条与扩展前逐条相等，后 54 条与提案 `table_records`、batch20 待落地文件逐条相等；原 bundle/原提案/original_bytes.bin 一字未改；扩展 bundle sha 与声明一致。
6. 扫描器 `scripts/security_scan.py` 在 C3 中零改动，"不放宽" 声明属实。
7. 三份 CR 无夸大、无越权状态声明。

### needs_changes（3 条，均为文档/留痕级，不推翻实现）

1. **CR-R20 路径拆分数字与提案不符**：`docs/decisions/CR-R20_secret_registry_extension_batch21.md` 第 19 行称 22 个路径为 "10 个 `frontend/src/` 测试文件…12 个 `reports/runs/` 历史证据文件"；实测提案 `fixture_bindings` 及 54 条记录的唯一路径为 **8 frontend + 14 reports/runs**（记录数分布 27/27）。总数 22 正确，拆分错误。应更正为 8/14（或给出其 10/12 的实际统计口径）。
2. **CR-R07 与 CR-migration 的声明时间戳晚于其入库提交，不真实**：两文件均在 `13a580e23`（提交时间 2026-10-24T23:35:11+08:00）首次入库且此后零改动（`git diff 13a580e23..HEAD` 为空），却分别声明 "文档首次创建/最后更新 23:40:00" 与 "23:45:00"；CR-migration 的 "C2 追加（23:5x）" 小节也在 23:35:11 提交内，而其描述的 C2 代码改动落在 8 秒后的 `b4407f833`（23:35:19）。声明时间与 git 事实矛盾，应改为真实写作/提交时间（R20 CR 的 23:30 早于 23:35:11，无此问题）。
3. **C3.1 终态复跑日志在检查点提交内被截断**：`13a580e23` 内的 `reports/runs/batch21_red_zero/c31_r20_t06_t02_rerun3.txt` 仅 4 行进度点、无统计行与退出码（`\ No newline at end of file`）；完整日志（303 passed / exit=0）目前只存在于**未提交**的工作树修改中。独立复跑已复现同结果，故不影响绿的事实，但应尽快提交完整日志（或补一份完整留痕），使检查点自含证据。

### not_run（含理由）

- `generate_extension.py` 复跑一致性：脚本会回写 live registry 表（须先回滚 136）并写入 `reports/runs/` 既有产物，超出本审查"不改业务文件/不改 reports/runs"边界，未执行；已用替代证据覆盖其核心输出语义（第五节 1-4 项全部逐条比对通过）。
- 样本行 match_sha256/value_sha256 三字段独立复算：依赖上述生成器口径（quote-frame 逻辑），同上 `not_run`；已验证样本行存在且登记文件字节未变。

### 观察项（不构成 needs_changes）

- `oracle_alignment_expectations.json` 的 old（LF blob）/new（CRLF 工作树）哈希口径混合，建议后续注明字节域。
- 登记表扩展未追加 `history` 条目、未更新 `recorded_at`（沿袭该文件既有做法——136 条时 history 也仅 1 条覆盖 36→51），54 条新增记录的追溯依赖提案文件 + batch20 文件 + R20 测试合同；登记表所有者可在后续 CR 中统一 history 惯例。
- 审查期间 HEAD 由 `b4407f833` 前移至 `ee283de3e`，工作树存在与本审查无关的未提交修改；本报告结论不受影响。

## 九、最终判定

批次21 C3 "历史红清零三件套" 的实现、复跑与证据链**整体成立**：三份 CR 如实描述改动、引用的已审证据在 git 历史中真实存在、登记表扩展语义与冻结边界全部核实通过。存在 **3 条 needs_changes**（CR-R20 路径拆分数字、两份 CR 声明时间戳与提交事实矛盾、检查点内复跑日志截断），均为文档/留痕修正，不需改动任何业务代码或测试，修正后本审查无保留意见。
