# CR-种子对齐 · R04/R06/R07 时代集成种子补 stamp data_mode（批次22 目标1）

文档首次创建时间：2026-10-25T05:00:00+08:00
本次写作开始时间：2026-10-25T05:00:00+08:00
状态：awaiting_independent_review；授权依据：批次22 计划目标1（(d) 类甄别后修复），上游合同依据：revision-mode fail-closed 读合同（提交 `48f96b5ba`，2026-10-17 引入，已审集成）。

## 依据链

批次21 C2 逐文件执行（run5/run6）暴露 72 个真实失败；甄别报告 `reports/runs/batch22_d_triage/triage_report.md` 确认 56 例同源：2026-10-17 之前的集成种子资产（`seed_source_document`/catalog save/paper 种子等）落库 `source_metadata={}`（models.py:88 server_default），而 `classify_stored_revision_mode`（revision_mode.py:13-26）对无 `data_mode` 的元数据 fail-closed（`stored_source_mode_unavailable`）。同期之后的新测试（如 test_r18_current_risk_summary_pg.py:99）都显式 stamp `{"data_mode": "fixture", ...}`——反证这是种子资产滞后于已审合同，而非环境差异或产品缺陷。

## 改动（仅测试种子资产，非 legacy 路径）

1. `backend/tests/integration/test_r04_knowledge_api_pg.py` `seed_source_document`：非 legacy 分支的 `document_revisions.insert().values(...)` 增加 `source_metadata={"data_mode": "fixture"}`（legacy 分支保持 server_default `{}`——legacy 行可读性属 r05 裁决，本 CR 不触及）。修复 r04_knowledge_api_pg(10) + r04_api_review_regressions(7)。
2. `backend/tests/integration/test_r06_catalog_documents_pg.py` 的 save/paper 种子：`source_metadata` 增加 `"data_mode": "fixture"`。修复 r06_catalog(1) + r06_document_api(6) + r06_source_boundary(3) + r07_job_execution 的 synthetic_bounded_paper 路径 + r14_read_adapters(1) 等复用文件。
3. `backend/tests/integration/test_r06_source_excerpt_event_proof_pg.py` `response()`：增加 `data_mode="fixture"`（一行，与该文件 :185 既有 stamp 同构）。修复 8 例。
4. `backend/tests/integration/test_r18_api_key_post_lock_time_pg.py`：会话冻结期限（2026-10-17 绝对日期，时间炸弹）改为相对时钟（issued_at 起 +N），一行。
5. `backend/tests/integration/test_r07_cvss_authority_scope_fix_pg.py`、`test_r07_enrichment_publication_pg.py`、`backend/tests/integration/test_r14_default_runtime_pg.py`（经 prepared_submission）：同族种子 stamp（prepared_submission 内 revision_metadata 增加 data_mode）。

## 明确不放宽的内容

- 不改任何断言值/期望值；不改产品代码；不改 legacy 行的种子语义。
- 不触及的三项（另有记录）：r05_question_api 19 例（legacy-0013 可读性 vs fail-closed 的裁决，OQ-5）、r04_source_documents 1 例（evidence 计数 2→4，合同演化裁决，OQ-5）、家族 2 公网读错误码映射 5 例（产品行为，OQ-5）、pgvector 0.8.2 钉版（pgdg main 已无 0.8.2，OQ-5）、r07_job_execution 1 例 D 类（先取证）。

## 验收与复跑

容器逐文件重跑受影响文件（`reports/runs/batch22_d_triage/plan_batch22.json`，自由文件改为独立库消除串扰），预期上述 56 例转绿；全量离线保持 0 failed。文件前后哈希记录于 `reports/runs/batch22_d_triage/seed_alignment_expectations.json`。

本次写作结束时间：2026-10-25T05:00:00+08:00
最后更新时间：2026-10-25T05:00:00+08:00
