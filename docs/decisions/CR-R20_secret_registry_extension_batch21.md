# CR-R20 · 秘密分类登记扩展批次21（54 条历史 finding 落地）

文档首次创建时间：2026-10-24T23:30:00+08:00
本次写作开始时间：2026-10-24T23:30:00+08:00
状态：awaiting_independent_review；授权依据：批次21 有界批处理指令 C3.1（OQ-3 决议后的落地路径），范围仅限本登记扩展，不放宽扫描器、不改动任何规则/分母/阈值。

## 扩展依据

t06 安全扫描存在 54 处遗留未分类 finding（`progress/OPEN_QUESTIONS.md` OQ-3；批次20 决议修正后保存为待落地提案 `reports/runs/batch20_secret_classification_20261024/classification_records_54_ready_to_land.json`）。批次20 已逐条验证全部为合成值并带证据链，因触碰 R20 冻结登记控制（`tests/security/test_r20_secret_provenance.py` 冻结 total_records=136）而回退，明确落地须走本变更单程序。本 CR 即该程序：

1. 提案材料生成于 `reports/runs/batch21_r20_registry_extension_20261024/`（`generate_extension.py` 可复跑复核，`registration_proposal.json` 含 54 行提案、22 个路径的 fixture_bindings、bundle sha、table_records 精确追加记录）。
2. fixture bundle：`fixtures/synthetic/security/r20_registry_extension_batch21.zip`（zip_stored、条目时间戳固定 1980、按 raw_sha256 去重条目，sha256=72d9d734bd4b81df041788becbd8ac1ecb47ca4780ff887a9ba70204d0e9236b）。
3. 登记表 `reports/security/recovery_fixture_false_positives.json`：136→190，仅追加，原 136 条未动（`old_records_unchanged=true`，提案内 table_records 与实际追加逐条相等，由 R20 测试断言把守）。

## 逐条来源说明

54 条记录全部来自批次21 指令认可的既有证据链，不新增任何未验证值：

- 范围：22 个路径——8 个 `frontend/src/` 测试文件（assessments×4、investigations×3、recommendations×1）与 14 个 `reports/runs/` 历史证据文件（recovery_gc_integrated_e310 rosters×3、r07 默认入口/input_audit 各轮 probes×4、r08 aggregates×1、r11 sbom resources×2、r18 api_key probes×2、`story_fixture_20261023/verify_story.py`×1、r11 review1 resource×1）。
- 每条记录含 `fixture_origin`（source_commit/source_path/source_line/source_blob/source_sha256/data_mode=fixture）与 `review_ref`（前缀 reports/reviews/recovery/G-B-secret-fixture-classification.md，附批次20 总结与 OQ-3 决议引用），全部为 10-14 至 10-24 期间证据脚本与前端测试中的合成凭据字面量。
- 推导字段（line、match_sha256、value_sha256）按 R20 原 82 行提案的同一约定由当前文件字节计算，生成器对每条验证 raw_sha256 与当前字节一致；line/match_sha256/value_sha256 推导口径已对原提案已知行核对一致（asset-client.test.ts 第 23 行样本三字段全等）。

## 明确不放宽的内容

- 扫描器 `scripts/security_scan.py` 的 PATTERNS、SCAN_ROOTS、正则、分类规则零改动。
- 登记仍为"精确位置+精确字节哈希"豁免：文件任何字节变更、复制、新形状凭据均不继承豁免（由 R20 既有参数化测试继续把守，现已扩展到新登记的 22 个路径）。
- exact 秘密字节检测（exact_secret_match）与路径边界检测不变。
- 原冻结材料（`registry_original_bytes.bin`、原 82 行提案、bundle `r20_secret_provenance_20261016.zip`）一字未改。

## 测试合同扩展（本 CR 唯一代码层改动）

`backend/tests/security/test_r20_secret_provenance.py`：

- 新增 EXTENSION 提案与 bundle 装载；`registration_for()` 按路径解析归属提案；`isolated_copy` 使用归属提案的 bindings/bundle 校验（原校验语义不变）。
- `test_original_registry_bytes_and_all_54_records_are_preserved`：`len(current) == 136 + 54` 且 `current[136:] == EXTENSION["table_records"]`（新增精确绑定）；原 54 条与前缀断言保持不变。
- 各参数化行为测试（变更即吊销、复制不继承、精确字节覆盖、新形状仍拒绝、混合行尾拒绝）的 ROWS/PATHS/UNIQUE_VALUES 扩展为两提案并集，覆盖新增登记。

## 验收与复跑

- `uv run python -m pytest tests/security/test_r20_secret_provenance.py tests/security/test_t06_authentication_and_scope.py tests/unit/test_t02_project_skeleton.py -q --no-cov`（结果落 `reports/runs/batch21_red_zero/c31_r20_t06_t02_rerun.txt`）。
- 评审人复核点：generate_extension.py 复跑一致性（表须先回滚 136）、loader 对 190 条全解析、t06 转绿且其余 security 套件无新红。

本次写作结束时间：2026-10-24T23:30:00+08:00（初稿；文档随提交 13a580e23=2026-10-24T23:35:11+08:00 入库，git 时间戳为权威）
最后更新时间：2026-10-25T01:5x+08:00（R-A 审查修正：范围路径计数 10/12→8/14）
