# CR-R07 · codec prompt_version oracle 对齐批次21（-1 → -2）

文档首次创建时间：2026-10-24T23:30:00+08:00（初稿；随提交 13a580e23=2026-10-24T23:35:11+08:00 入库，git 时间戳为权威）
本次写作开始时间：2026-10-24T23:30:00+08:00
状态：awaiting_independent_review；授权依据：批次21 有界批处理指令 C3.2（oracle 对齐须引用 git 历史可查的已审集成证据），范围仅限测试期望更新，生产代码零改动。

## 已审证据

`backend/tests/contract/test_r07_single_model_dimension_contract.py:37` 冻结断言 `metadata.prompt_version == "r07-model-fields-1"` 自 d8a3189bb 创建后从未维护；生产代码自 2026-10-16 起返回 `-2`，造成 16 个参数化红（red_inventory.md Section B1，与 2026-10-16 基线"16 条旧 codec 预期"完全吻合）。

`-2` 是已审集成结果，证据链（由批次21 独立证据检索复核，报告 `reports/runs/batch21_red_zero/research/oracle_evidence_research.md`）：

1. 提交 `7dae1d823`（2026-10-16T06:07:52+08:00）将 PROMPT_VERSION 由 -1 改为 -2；
2. 同提交入库 `docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md`（第 7 行明确记载该变更）；
3. `reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md`（第 5、21 行，随 `daacf92ab` 入库）为非作者独立初审，逐字记录 prompt `r07-model-fields-2`，Verdict: Ship。

## 改动

唯一改动：`test_r07_single_model_dimension_contract.py:37` 的断言期望 `-1` → `-2`，一处改动消化 16 红。文件前后哈希记录于 `reports/runs/batch21_red_zero/oracle_alignment_expectations.json`（batch17 head 期望替换的既有证据格式）。

## 明确不放宽的内容

- 第 38 行 `schema_version == "r07-model-field-extraction-1"` 断言未动（生产现行返回即 -1，无漂移）。
- codec 行为断言（单次调用、wire 字段、usage、fee、哈希长度、max tokens）全部保持。
- 生产代码、PROMPT_VERSION 常量、模型接线零改动；禁止反向把生产改回 -1。

## 验收与复跑

`cd backend && uv run python -m pytest tests/contract/test_r07_single_model_dimension_contract.py -q --no-cov` 预期 16 参数化全绿；C3.4 全量复跑确认 0 failed 无挪红。

本次写作结束时间：2026-10-24T23:30:00+08:00
最后更新时间：2026-10-25T01:5x+08:00（R-A 审查修正：时间声明对齐 git 入库事实）
