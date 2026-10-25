# CR-r05_legacy_seed_annotation_batch23

- 文档首次创建时间：2026-10-25T09:45:00+08:00
- 本次写作开始时间：2026-10-25T09:45:00+08:00
- 最后更新时间：2026-10-25T09:45:00+08:00
- 状态：awaiting_review（裁决执行件，依据 progress/DECISIONS_pending.md 裁决①建议项；GOAL 指令授权方式B）
- 关联：`48f96b5ba`（G-C/G-D fail-closed 合同）；`CR-seed_data_mode_alignment_batch22.md`（同构 stamp 先例，r05 被其明示排除归本裁决）；`reports/runs/batch22_d_triage/triage_report.md` test_r05 节

## 裁决（引用简报证据）

r05 legacy-0013 哈希锁定种子（`fixtures/recorded/r05_legacy_0013_vllm_public_v1.json`）保持字节不变；其 `document_revisions` 行的 `source_metadata` 由 `question_api` fixture 在 v2 读合同下以 `{"data_mode": "fixture"}` 补章后作答。产品侧 fail-closed 合同（无标注行 → `stored_source_mode_unavailable`）不回退；"legacy 行在迁移中保持 `{}`"的保真断言（`test_r05_vector_persistence.py:217`，位于未受本 CR 影响的 fixture 作用域）继续生效。

- 失败证据：`reports/runs/batch21_integration_unlocked/test_r05_question_api_pg_pf.txt` 19 failed / 5 passed（11 例 503 question_processing_failed + 4 例 barrier 超时 + 4 例错误码错位）；根因链 triage test_r05 节。
- 选项 A（产品侧 legacy 读取规则）被否：行内无纪元信息，需新迁移/新列才能区分"0013 纪元行"与"漏标行"，触碰公共读合同与迁移，且"未知行推定可读"违反 fail-closed 不变量（不可逆性高）。
- 选项 B（本 CR）：19 例断言零改动、种子零改动；补章是读取 fixture 内显式、有注释的裁决动作。

## 改动

1. `backend/tests/integration/test_r05_question_api_pg.py`：`question_api` fixture 开头（装配应用前）对种子 revision 行执行 `UPDATE ... SET source_metadata={"data_mode": "fixture"}`（经 `vector_database.begin()`；分类器 `revision_mode.py:24` 接受无 policy 版本的 fixture 标注；种子恰 1 行 document_revisions，`test_r05_vector_persistence.py:212` 断言）。
2. 不改：种子 JSON 与其哈希锁定断言、`vector_database` fixture、`load_legacy_0013_seed`、任何测试断言值、产品代码。

## 明确不做

- 不处理 `test_r05_vector_persistence` 的 2 例同根因 B（该文件另有 pgvector 0.8.2 的 A 例外部阻塞，OQ-5 记录 pgdg main 无 0.8.2；留待 pgvector 版本裁决时以同一 stamp 模式一并处理）。
- 不改金标/阈值/分母；不动 48f96b5ba fail-closed 合同。

## 验证

- 容器逐文件：`tests/integration/test_r05_question_api_pg.py`（钉定 run_id=`r05_pgvector_20261015`，port 5432，与 batch21 pf 证据同条件）——19 例从失败清单消失。
- 宿主定向：`uv run python -m pytest tests/unit tests/contract tests/security -q --no-cov -k "question or revision_mode"`。
- 全量回归：backend 离线全量 failed 仍为 0。

本次写作结束时间：2026-10-25T09:45:00+08:00
