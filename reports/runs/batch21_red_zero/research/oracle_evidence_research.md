# 批次21 历史红清零 · Oracle 证据核查（只读检索）

- 文档首次创建时间：2026-10-24T23:05:52+0800
- 最后更新时间：2026-10-24T23:05:52+0800
- 检索环境：`D:\dianzi`，Git Bash（Windows），仅使用只读命令（`git rev-parse / log -S / show / merge-base`、`grep`、`sed`、`ls`、`date`）。未运行 pytest，未修改任何工作树文件，未执行任何改变 git 状态的命令。
- 实际 HEAD：`e5832ed92430d6fe500690c0a3f9cbd360cb03f9`（"checkpoint: batch21 C0 cold start, timeline and baseline snapshot"）。任务书所引 `6c9bb455c`（"checkpoint: batch20 followup decisions - worker spawn fix, OQ-3 proposal material, smoke diagnosis"）经 `git merge-base --is-ancestor` 验证为其祖先。本报告全部引文在两个提交上均可查，行号以当前 HEAD 工作树为准。
- 方法：`git log -S "<string>"` 定位字符串引入/消失的提交；`git show --stat/--name-only` 摘录；`grep -n` 定位文档佐证行号。测试验证状态 `not_run`（本任务为纯证据检索）。

---

## 任务A：codec prompt_version（16 个历史红）

### A1. 红的冻结断言（原样引用）

文件：`backend/tests/contract/test_r07_single_model_dimension_contract.py`
- 该文件自创建后从未修改：`git log --oneline --follow` 仅 `d8a3189bb`（2026-10-16 02:52:17 +0800，"feat(enrichment): add bounded single model dimension extraction"）一条。同信息孪生提交 `b3cc1a2ae`（同时间戳）亦为 HEAD 祖先（合并历史两线各一）。
- 第 1 行（docstring）：`"""Synthetic one-call wire and frozen DimensionAttempt contract checks; live is not run."""`
- 第 13-16 行参数化 + 第 32-42 行断言上下文（原样）：

```python
@pytest.mark.parametrize("dimension", DIMENSIONS)
@pytest.mark.parametrize(
    "provider", ["openai", "anthropic", "deepseek_openai", "deepseek_anthropic"]
)
...
    metadata = result.model_attempts[0]
    assert metadata.provider == provider
    assert metadata.requested_model == metadata.response_model == client.approved_model
    assert metadata.outcome == "succeeded"
    assert metadata.http_status == 200
    assert metadata.prompt_version == "r07-model-fields-1"
    assert metadata.schema_version == "r07-model-field-extraction-1"
    assert metadata.call_id == "offline-fixture-call"
    assert metadata.usage.input_tokens == 20
    assert metadata.usage.output_tokens == 1
    assert metadata.fee == "unknown"
```

- 冻结断言在第 37 行：`assert metadata.prompt_version == "r07-model-fields-1"`。
- 16 红数量核对：`DIMENSIONS = ("atlas", "versions", "literature", "poc")`（`backend/tests/unit/test_r07_single_model_dimension.py:19`），4 维 × 4 provider = 16 个参数化实例。

### A2. `r07-model-fields-1` 何时引入

- `git log -S "r07-model-fields-1" -- backend/src/`：最早为 `6463e62bd`（2026-10-16 00:39:08 +0800，"feat(G-C/R07): generate four evidence-bound model field candidates"），diff 第 56 行 `+PROMPT_VERSION = "r07-model-fields-1"`。
- -1 状态当时经过独立审查：`reports/reviews/recovery/G-C-R07-single-model-dimension-review-1.md`（审查代码 `d8a3189bb`，材料 `b05e63462`）第 60 行显示该审查实跑了 `tests/contract/test_r07_single_model_dimension_contract.py`；第 103 行 Verdict：`Verdict: Ship. 仅 d8a3189 单维接口代码与 b05e634 配套冻结材料的离线 unit/contract/security 切片。` 该审查文档由 `ae6f623d1`（2026-10-19 17:08:42 +0800，"checkpoint: capture current workspace and evidence"）归档入库。

### A3. `r07-model-fields-2` 引入提交

- `git log -S "r07-model-fields-2" --oneline --all -- backend/` 唯一命中：`7dae1d82363d8459f3546fee4b92137559dcb5aa`（2026-10-16 06:07:52 +0800，"R07 bound field evidence inputs and parse pinned taxonomies"）。
- `git show --stat`：8 文件，+1374/-37。核心 diff（`backend/src/ai_intel/enrichment/model_fields.py`）：
  ```
  -PROMPT_VERSION = "r07-model-fields-1"
  +PROMPT_VERSION = "r07-model-fields-2"
  ```
- 该提交**未触碰** `test_r07_single_model_dimension_contract.py`（stat 文件清单不含它），只新增了其他测试与 CR 文档——冻结断言由此开始滞后。
- 当前 HEAD 生产值：`backend/src/ai_intel/enrichment/model_fields.py:49` `PROMPT_VERSION = "r07-model-fields-2"`（第 172 行经 `prompt_version=PROMPT_VERSION` 进入 AttemptMetadata）。

### A4. 审查/决策佐证（grep `docs/ reports/reviews/ reports/tasks/ progress/` 全部命中）

1. `docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md`（随 7dae1d823 同提交入库）：
   - 第 3 行：`状态：awaiting_review；实现切片，整 R07 和默认 App 接线未验收。记录：2026-10-16，Asia/Shanghai。...`
   - 第 7 行：`变更：model_fields.PROMPT_VERSION 从 r07-model-fields-1 到 r07-model-fields-2；输出 schema r07-model-field-extraction-1 不变。内部选择规则 evidence_selection.SELECTION_VERSION=r07-field-selection-1。...`
   - 第 23 行（验收段）：`...原模型143与字段集102回归期待不改。新非作者 reviewer 复跑冻结 SHA；...`
   - 第 27 行（Fix1 补充，主控 2026-10-16 明确指令）：`Fix1补充（主控2026-10-16明确指令）：保留7dae1d82及其历史材料。...主控runtime首次接线以最终source SHA和上述prompt/selection版本为准。`
2. `reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md`——非作者独立初审，随 `daacf92ab`（2026-10-16 07:07:15 +0800，"review: freeze independent R07 input slice verdict"）入库：
   - 第 5 行：`**Verdict: Ship，仅限本次输入切片及已批准的共享必要上下文校验 seam。** 四项初审 Must 已在冻结新版本独立闭合，当前没有该范围内遗留阻断。...本审查未写 accepted 或 progress。`
   - 第 21 行：`...模型输出 schema 仍 r07-model-field-extraction-1，prompt r07-model-fields-2，selection r07-field-selection-1；未发布的修复由 root 首次接线使用最终 SHA，不重解释历史任务。`
   - 第 67 行（英文 Verdict）：`Verdict: Ship, within the stated slice only. ...`
3. 后续任务报告持续把 -2 记为冻结版本：`reports/tasks/R07-input-capabilities.md:9`、`reports/tasks/R07-input-capabilities-fix2.md:13`、`reports/tasks/R07-input-capabilities-fix3.md:37`、`reports/tasks/R07-model-fields.md:37`。
4. `docs/decisions/CR-R07_input_audit_fingerprint.md`（随 `014de5854`，2026-10-16 08:55:21 +0800，"docs(r07): freeze input audit PG evidence and unresolved predecessor regression" 入库）：将 `model_fields PROMPT_VERSION/SCHEMA_VERSION` 冻结进新 enqueue 的 `model_input_versions` 执行指纹（409 语义），进一步确认 -2 为权威版本。
5. 红的登记现状：`progress/OPEN_QUESTIONS.md` OQ-3，第 33 行状态更新（2026-10-24T11:3x+08:00），第 35 行：`影响：t06 维持唯一历史红（16 codec + 2 迁移 head + 1 t06 = 19 failed 最终余量）；不影响其他批次。`

### A5. 任务A结论

- 引入提交：**`7dae1d82363d8459f3546fee4b92137559dcb5aa`，2026-10-16 06:07:52 +0800**。
- 是否伴随审查/CR证据：**是**。同一正式提交内含 CR 文档（`docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md:7` 明确记载 -1→-2 变更及其不变量边界）；约 1 小时后非作者独立初审 Verdict: Ship（`reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md:5/:21/:67`，随 `daacf92ab` 入库）逐字记录 `prompt r07-model-fields-2` 为冻结审查结果；其后多个 CR/任务报告与当前 HEAD 生产代码一致。
- 按本仓库规则（git 历史可查的正式提交 + 审查/决策文档佐证）：**已审集成证据充分**。支持将 `backend/tests/contract/test_r07_single_model_dimension_contract.py:37` 期望更新为 `"r07-model-fields-2"`。该断言属"前序切片冻结期望未随已审变更更新"的滞后回归，更新测试期望不触碰生产代码、金标、评分分母。
- 需在 CR 中如实记录的限定：
  1. 两份审查均自述"未写 accepted / 未放行整 R07"——但放行范围恰为本输入切片，prompt_version 取值 -2 正是被审内容本身，属放行范围内事实；状态推进仍须评审人确认。
  2. CR 第 23 行"原模型143与字段集102回归期待不改"指另外两套回归套件（full-input 模型套件与字段集套件，另见第 27 行"原full-input143期待保留"），并未重新冻结本合同测试的 prompt_version 期望；第 27 行 Fix1 补充反而指明 runtime 接线以"上述prompt/selection版本"（即 -2）为准。
  3. 该 16 红自 2026-10-16 07:07（`ed0e14a03` 同日引入 0020 前，即 7dae1d823 落地后）起即为已登记的已知红（OQ-3），非本批次新引入。

---

## 任务B：迁移 head 0031（2 个历史红）

### B1. 红的冻结期望（原样引用）

1. `backend/tests/contract/test_r11_r08_forward_migrations.py`
   - 创建：`27a533c93`（2026-10-16 05:16:59 +0800，"Freeze forward asset inventory and safe aggregate history migrations"，该文件 +54 行）；孪生提交 `c842333fe` 同信息。此后从未修改（`git log --follow` 仅此两条）。
   - 第 12-15 行（REVISIONS 定义）：
     ```python
     REVISIONS = (
         ("0018_asset_inventory", "0017_enrichment_job_workflows"),
         ("0019_aggregate_observations", "0018_asset_inventory"),
     )
     ```
   - 第 45-54 行（原样）：
     ```python
     def test_production_chain_has_single_forward_head():
         config = Config()
         config.set_main_option("script_location", str(MIGRATIONS))
         scripts = ScriptDirectory.from_config(config)
         assert scripts.get_heads() == ["0019_aggregate_observations"]
         assert [revision.revision for revision in scripts.iterate_revisions("head", "0016")] == [
             "0019_aggregate_observations",
             "0018_asset_inventory",
             "0017_enrichment_job_workflows",
         ]
     ```
   - 冻结断言在第 49 行。
2. `backend/tests/contract/test_recovery_forward_migrations_0023_0026.py`
   - 创建：`3d193e2bb`（2026-10-16 11:31:17 +0800，"Recovery checkpoint integrate independently reviewed forward 0023 0026"）；此后从未修改。
   - 第 20-25 行（REVISIONS 定义）：
     ```python
     REVISIONS = (
         ("0023_enrichment_input_audit", "0022_sbom_sidecars", "r07"),
         ("0024_conversation_context", "0023_enrichment_input_audit", "r12"),
         ("0025_graph_projection", "0024_conversation_context", "r10"),
         ("0026_api_key_credentials", "0025_graph_projection", "r18"),
     )
     ```
   - 第 79-88 行（原样）：
     ```python
     def test_complete_alembic_chain_has_one_head_and_no_revision_gap() -> None:
         config = Config()
         config.set_main_option("script_location", str(MIGRATIONS))
         scripts = ScriptDirectory.from_config(config)
         assert scripts.get_heads() == [REVISIONS[-1][0]]
         history = list(scripts.walk_revisions("base", "heads"))
         assert [int(revision.revision[:4]) for revision in history] == list(range(26, 0, -1))
         assert [
             revision.revision for revision in scripts.iterate_revisions("head", REVISIONS[0][1])
         ] == [row[0] for row in reversed(REVISIONS)]
     ```
   - 冻结断言在第 83 行（`REVISIONS[-1][0]` = `"0026_api_key_credentials"`）。
3. 实际 head 静态核对：`backend/migrations/versions/` 现有 0001-0031；`0031_public_task_bindings.py:5-6` `revision = "0031_public_task_bindings"` / `down_revision = "0030_revalidation_actor_bindings"`，链线性，单 head = 0031。
4. 红起点推定（由文件零修改史 + 迁移引入时间）：r11_r08 测试自 `ed0e14a03`（2026-10-16 07:07:06 +0800，引入 `0020_hybrid_retrieval`）起 0019 期望失配；0023-0026 测试自 `9e6abcab9`（2026-10-16 13:13:43 +0800，引入 `0027_recommendation_history`）起 0026 期望失配。此后 `1cdb9e7d9`（15:57:12，0028+0029）、`30db1ae63`（16:46:06，0030）、`0291d1975`（10-17 10:32:38，0031）继续累积。

### B2. 0031 引入提交

- `git log --oneline --follow -- backend/migrations/versions/0031_public_task_bindings.py` 唯一命中：`0291d197587141b9f7f5da0d01800d8cbdf58d11`（2026-10-17 10:32:38 +0800，"checkpoint G-C: package public ask schema, retain identity audit, and integrate typed task bindings"），共 80 文件，含 `0031_public_task_bindings.py`（68 行）、`backend/src/ai_intel/api/public_task_bindings.py`（647 行）等。
- 同提交随附的决策/审查/集成文档（`git show --name-only` 过滤 docs/reports）：
  - `docs/decisions/CR-R18_*.md` 共 8 个（含 `CR-R18_task_qa_publication_receipt.md`、`CR-R18_workflow_transaction_enqueue.md` 等）
  - `reports/reviews/recovery/G-E-R18-typed-task-binding-review-1-recheck-batch17-7acd9ea9.md`
  - `reports/runs/recovery_reviewed_integration_20261016/`（含 `root_batch17_forward_head_expectations.json` 等 40+ 证据文件）
  - `reports/tasks/Root-batch17-integration.md`、`reports/stages/recovery/G-C.md`

### B3. 审查/决策佐证

1. `reports/reviews/recovery/G-E-R18-typed-task-binding-review-1-recheck-batch17-7acd9ea9.md`（非作者独审复查，随 0291d1975 同提交入库）：
   - 第 1-3 行：`# R18 typed task binding · 非作者首独审复查` / `本轮限定切片复查通过：原两项业务 Must 已被新源码修复，窄 ActorReference 异常断言纠正符合现有合同。建议 Root 依据本报告处理切片验收；我未签 accepted、未改中央状态。整 R18 仍 partial：...`
   - 第 17 行：`...原16在2133与3e84的 Git 原字节也精确相同；0031 migration blob未变。非 import SHA256 515ca803...`
   - 第 55 行：`五窗均：PG16实际 160014；...完整migration child到0031_public_task_bindings exit0并退出，之后才启动pytest。...`
2. 编号授权链（实现前）：`reports/tasks/R18-typed-task-bridge-analysis.md:168`（`0031占用状态：...编号仍Root唯一，不能据本报告自行创建0031...必要binding迁移需Root先确认并登记`；`:187` 下一步建议 Root 冻结最小 DDL 并确认 0031 所有权）；`docs/decisions/CR-R18_workflow_transaction_enqueue.md:10`（`public_task_bindings如确需0031由Root唯一后续设计并登记，不由作者创建空表`）；`docs/decisions/CR-R18_task_qa_publication_receipt.md:15`（`0031仅Root前向合入隔离测试库，Source912库保持0030`）。
3. Root 集成证据（同提交）：`reports/tasks/Root-batch17-integration.md:17`：`导入f316经独立275+3离线/17真实PG的八typed绑定文件与0031前向迁移；Root90直属离线通过，默认getter/publisher尚未接通，整R18仍partial。七原integration head期望仅0030→0031八处输入跟进，source912数据库/运行WT保持0030；7组实际Root新head PG未运行，不能拿f316或9d证明。精确替换原hash/新hash在root_batch17_forward_head_expectations.json。`
   `reports/runs/recovery_reviewed_integration_20261016/root_batch17_forward_head_expectations.json`（created_at 2026-10-17T02:06:35.402Z）：`"only_test_forward_head_replacement": true`、`"protected_Source_database_not_migrated": true`，对 7 个 integration 测试文件记录 0030→0031 期望替换及逐文件 old/new raw SHA256（如 `test_r16_revalidation_runtime_pg.py` replacements=2，old `4ee15d9d...` → new `8a4619af...`）。

### B4. 先例核查（任务指定命令）

- `git log -S "0019_aggregate_observations" --oneline -- backend/tests/`：`27a533c93`、`c842333fe`（创建测试时写入 0019 期望）；`ed0e14a03`、`ba69d6cbc`、`d56a1ed30`、`0892b6af7`、`2fe903eaf`（只改变其他测试文件中该字符串出现次数）。`test_r11_r08_forward_migrations.py` 自创建后 0 次修改 → **0019 期望从未被更新过**。
- `git log -S "0026_api_key_credentials" --oneline -- backend/tests/`：仅 `3d193e2bb`（创建 0023-0026 测试时以 `REVISIONS[-1][0]` 写入 0026 期望）→ **0026 期望从未被更新过**。
- `grep -rn "get_heads" backend/tests/`：全测试库仅此两处断言（两红本身），无其他可参照的合同测试 head 更新记录。
- 如实记录：`3d193e2bb`（写入 0026 期望）提交标题自称 "independently reviewed forward 0023 0026"，但该提交内不含任何 docs/reports 文件（`--name-only` 过滤为空），审查佐证未随提交归档。
- **真正同型先例**：Root 在 `0291d1975` 内对 7 个 integration 测试做的 0030→0031 head 期望替换，带 `root_batch17_forward_head_expectations.json` hash 清单——这正是"迁移 head 前进时同步更新测试期望"的已入库先例；两个合同测试只是该次维护的被遗漏对象。

### B5. 任务B结论

- 引入提交：**`0291d197587141b9f7f5da0d01800d8cbdf58d11`，2026-10-17 10:32:38 +0800**。
- 是否有已审证据支持把两个测试期望更新为 0031：**充分**。依据：(1) 0031 由正式 checkpoint 提交引入，同提交携带非作者独审复查文档（复查通过、真实 PG migration child 到 `0031_public_task_bindings` exit0、`0031 migration blob未变`）；(2) Root 集成报告与 `root_batch17_forward_head_expectations.json` 构成同批"测试 head 期望 0030→0031"的 hash 级正式先例；(3) 0031 编号授权链（bridge-analysis 预检 → CR-R18 授权 Root → Root 落地）完整可查。
- 需在 CR 中如实记录的限定与**额外改动面**：
  1. 复查文档自述"我未签 accepted"，验收由 Root 依据该报告处理；Root 的集成记录（`Root-batch17-integration.md`）在同一正式提交内，构成接受侧证据，状态推进仍须评审人确认。
  2. `source912 数据库保持0030` 是运行库状态；两个红测试断言的是 `scripts.get_heads()`（迁移脚本目录的 head），不是运行库 `alembic_version`，二者不冲突，更新期望不改变"保护库不迁移"的既定事实。
  3. **只改两个 heads 断言行不够**：head=0031 下，`test_r11_r08_forward_migrations.py:50-54` 的 `iterate_revisions("head","0016")` 期望列表、`test_recovery_forward_migrations_0023_0026.py:85` 的 `list(range(26, 0, -1))`（需改为覆盖 31 个修订）与 `:86-88` 的 `iterate_revisions("head", REVISIONS[0][1])` 期望列表同样失配。CR 必须一并覆盖，否则红只是从第 49/83 行挪到相邻断言。
  4. 两个文件的期望分别对 0020-0031（12 个迁移）与 0027-0031（5 个迁移）累积滞后，且从未维护；本次属清偿累积滞后期望，不属修改金标或降低门槛。

---

## 附：检索命令清单（全部只读）

```
git rev-parse HEAD
git log -S "r07-model-fields-2" --oneline --all -- backend/
git log -S "r07-model-fields-1" --oneline --all   /  -- backend/src/
git show --stat 7dae1d823 / b3cc1a2ae / daacf92ab / 014de5854 / 0291d1975 / 27a533c93 / 3d193e2bb
git show 7dae1d823 -- backend/src/ai_intel/enrichment/model_fields.py
git show 6463e62bd -- backend/src/ai_intel/enrichment/model_fields.py
git show 7dae1d823:docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md
git show 014de5854:docs/decisions/CR-R07_input_audit_fingerprint.md
git merge-base --is-ancestor d8a3189bb|b3cc1a2ae|6c9bb455c HEAD
git log --oneline --follow -- backend/tests/contract/test_r07_single_model_dimension_contract.py
git log --oneline --follow -- backend/tests/contract/test_r11_r08_forward_migrations.py
git log --oneline --follow -- backend/tests/contract/test_recovery_forward_migrations_0023_0026.py
git log --oneline --follow -- backend/migrations/versions/0031_public_task_bindings.py
git log -S "0019_aggregate_observations" --oneline -- backend/tests/
git log -S "0026_api_key_credentials" --oneline -- backend/tests/
grep -rn "r07-model-fields-2" docs/ reports/reviews/ reports/tasks/ progress/
grep -rn "0031_public_task_bindings" docs/ reports/reviews/ reports/tasks/ progress/
grep -rn "get_heads" backend/tests/
sed/grep on reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md, G-C-R07-single-model-dimension-review-1.md, G-E-R18-typed-task-binding-review-1-recheck-batch17-7acd9ea9.md, reports/tasks/Root-batch17-integration.md, R18-typed-task-bridge-analysis.md, progress/OPEN_QUESTIONS.md
cat reports/runs/recovery_reviewed_integration_20261016/root_batch17_forward_head_expectations.json
date +%Y-%m-%dT%H:%M:%S%z
```

## 验证状态

- unit / integration / live：`not_run`（本任务为只读证据检索，未运行 pytest，属约定允许范围）。
- manual：`passed`——全部引文取自 `git show` / `grep` / `sed` / `cat` 的原始输出；文件路径与行号以当前 HEAD（`e5832ed92`）工作树为准；`6c9bb455c` 为其祖先，引文在两提交上一致。
