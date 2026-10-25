# DECISIONS_pending —— 批次23 三项评审裁决决策简报

- 文档首次创建时间：2026-10-25T09:25:00+08:00
- 本次写作开始时间：2026-10-25T09:25:00+08:00
- 最后更新时间：2026-10-25T09:25:00+08:00
- 授权状态：GOAL 指令（批次23 起）授权方式B——按本文各节"建议项"自决执行；本简报保留作为用户复核依据。任何一项证据不足以支撑建议时，该项标注"证据不足待用户"不执行。
- 约束：三项均不修改金标/阈值/评分分母；裁决只通过 CR + 对应 oracle/映射修订落地，每处修订引用本文证据。

---

## 裁决① r05 legacy-0013 种子可读性 vs fail-closed（19 例）

### 失败现象与例数

- `tests/integration/test_r05_question_api_pg.py`：19 failed / 5 passed（`reports/runs/batch21_integration_unlocked/test_r05_question_api_pg_pf.txt`，失败清单 15 个测试名含参数化共 19 例：11 例 `503 question_processing_failed`、4 例生成 barrier 超时、4 例 401/403/404 复检类错误码错位——`test_r05_question_api_pg_pf.txt:12-16、:22-26、:30-35、:40-45、:59-64、:78-83、:97-102、:116-121` 等）。
- 根因链（甄别报告 `reports/runs/batch22_d_triage/triage_report.md` §test_r05_question_api_pg 节）：`question_api` fixture（`test_r05_question_api_pg.py:96-161`）基于 `vector_database` fixture（`test_r05_vector_persistence.py:131-186`），后者加载**哈希锁定的 0013 时代 legacy 种子**（`load_legacy_0013_seed`，`test_r05_vector_persistence.py:55-128`；种子 JSON `fixtures/recorded/r05_legacy_0013_vllm_public_v1.json` sha256 断言 `6170ce55…`，:58-61），迁移到现行 head 后问答管线取证 `retrieval/service.py:211 → read_evidence → _evidence_projection → classify_stored_revision_mode({})` 抛 `RevisionModeUnavailableError: stored_source_mode_unavailable`（`revision_mode.py:13-26`），非预期异常被 `answering/service.py:546-549` 统一为 `question_processing_failed`，生成 wire 未触达导致 barrier 超时与复检断言连锁红。
- 产品侧合同出处：`48f96b5ba`（2026-10-17，G-C/G-D 评审并入）把 revision-mode fail-closed 并入读路径——`source_metadata` 缺 `data_mode` 字符串即拒绝读取。这是**有 CR 的故意变更**。
- 同根因但**不在本裁决计数内**：`test_r05_vector_persistence.py` 2 例 B（`test_event_retrieval_reuses_real_pg_vectors_and_exact_evidence`、`test_corrupt_derived_chunk_is_rejected_instead_of_cited`，pf :20-91、:91-161）与 1 例 A（pgvector 0.8.2 vs 0.8.7，pf :12-18；pgdg main 已无 0.8.2，OQ-5 记录外部阻塞）。该文件因 A 例离线不可能全绿，其 2 例 B 留待 pgvector 版本裁决时以同一 stamp 模式一并处理，本裁决不触碰。

### 选项

**选项 A（产品侧为 legacy 行定义读取规则）**：让 `classify_stored_revision_mode` 对 `{}` 元数据按迁移纪元回填/降级读。
- 影响的合同：公共读合同（`knowledge_read_service._revision_mode`、`document_read_service`、公网投影）与 `revision_mode.py` 分类器本身；需新增迁移或行内纪元标记才能区分"0013 纪元行"与"损坏/漏标行"（行内无纪元信息）。
- 不可逆性：高——读语义对全部存量数据生效；"未知行推定可读"直接违反仓库不变量"未知不等于否定"与 fail-closed 合同；且触碰已评审的 48f96b5ba 合同需反向 CR。

**选项 B（测试侧裁决：fixture 层补注，种子与断言零改动）**：在 `question_api` fixture 内（拿到 `vector_database` 引擎之后、装配应用之前）对种子 `document_revisions` 行补 `source_metadata={"data_mode": "fixture"}`（分类器 `revision_mode.py:24` 明确接受无 policy 版本的 fixture 标注；与批次22 种子对齐 CR 的 stamp 形态一致）。
- 影响的断言：**零**。种子文件字节不变（哈希锁定断言 :58-79 全部不动）；`vector_persistence` 自身的 `source_metadata == {}` 断言（:217）在自己的 fixture 作用域内不受影响（stamp 只发生在 question fixture 内）；19 例断言零改动。
- 不可逆性：低——只影响本 fixture 的数据形态；语义上等价于"新合同下数据接入的正确标注形态"，与批次22 已评审的 CR-seed_data_mode_alignment_batch22 同构（r05 当时被该 CR 明示排除、归本裁决）。

### 建议项及理由

**建议 B**。理由：(1) fail-closed 合同是经评审的新合同，旧种子冻结的"无标注行必然可读"语义已被取代，裁决应让测试对新合同可表达而非回退合同；(2) raw 种子的 `{}` 形态断言（:217）继续保留在 vector_persistence 内，**fail-closed 行为仍被持续验证**（无标注行 → stored_source_mode_unavailable 的路径在 r04/r06 多个已绿用例中覆盖）——不掩盖失败；(3) 原文可追溯不受损：种子文件哈希锁定原样保留，stamp 是读取层的显式、有注释的裁决动作。

### 执行后验证命令

```
cd backend && uv run python -m pytest tests/integration/test_r05_question_api_pg.py -q --no-cov   # 容器内（run_id=r05_pgvector_20261015 既有钉定）
uv run python -m pytest tests/unit tests/contract tests/security -q -k "question or revision_mode" --no-cov   # 宿主定向回归
uv run python -m pytest tests/unit tests/contract tests/security -q   # 全量对照 6252 passed / 0 failed
```

---

## 裁决② r04_source_documents evidence 计数 2→4（合同演化，1 例）

### 失败现象与例数

- `tests/integration/test_r04_source_documents.py::test_a_b_a_creates_three_revisions_and_preserves_old_evidence`：1 failed / 24 passed（`reports/runs/batch21_integration_unlocked/test_r04_source_documents_pf.txt:13-26`，`AssertionError: assert 4 == 2`，断言点 `test_r04_source_documents.py:254-261`——revision 1 的 evidence 行计数）。
- 根因（triage §test_r04_source_documents 节）：测试冻结于 `df214c664`（2026-10-15）。此后 `cb868896c`、`8d48c95ec`、`f3c2e41e3`（10-16/10-17）扩展了 CVSS 事实的 qualifier 链——现行 `source_documents.py:697-733` 对每个 score 事实要求 authority + vectorString 各一条独立 evidence 行。对 vendor fixture（`fixtures/recorded/vllm_vendor_20261015_public.json`）revision 1 = affected_product 1 条 + score 1 条 + 2 条 qualifier = **4 条**，确定性、与环境无关。同文件 revision 去重断言（:249-253 的 [1,2,3]）通过，证明只有计数断言滞后。

### 选项

**选项 A（保持 2）**：需回退产品的 evidence 粒度合同（CVSS authority/vectorString 不再各建 evidence 行）。影响：公共证据投影合同与 R06/R07 已绿的 evidence 链路断言；违背已评审合同演化；不可逆性高（逆向变更单）。

**选项 B（oracle 对齐 2→4）**：把 :254-261 的期望计数更新为 4（并按 locator 维度断言，锁定"affected_product 1 + score 1 + qualifier 2"的构成，防止未来粒度再变时静默通过）。
- 影响的断言：仅这一处计数期望；产品代码零改动。
- 不可逆性：低——测试期望跟随已入库合同，属批次21 同类 oracle 对齐先例（codec -1→-2、迁移 head 0026→0031 均走 CR）。

### 建议项及理由

**建议 B**。理由：(1) 4 条是产品现行已评审合同下的确定性输出，断言滞后是冻结时点问题（triage 已排除环境因素）；(2) 按构成断言比纯数字更强，符合"测试验证可观察行为"纪律；(3) 不改分母/金标——该计数是单 revision 的 evidence 行数，不是任何指标分母。

### 执行后验证命令

```
cd backend && uv run python -m pytest tests/integration/test_r04_source_documents.py -q --no-cov   # 容器内
uv run python -m pytest tests/unit tests/contract -q -k "source_documents or evidence" --no-cov   # 宿主定向
```

---

## 裁决③ 公网读错误码 `public_read_unavailable` vs 冻结 `not_configured` 映射（5 例）

### 失败现象与例数

5 例、3 文件（pf FAILED 行原样引用）：
1. `reports/runs/batch21_integration_unlocked/test_r18_public_read_producer_pg_pf.txt`：`test_r18_public_read_producer_pg.py::test_mixed_source_modes_do_not_return_fixture_as_live`（1 例，`'public_read_unavailable' == 'not_configured'`，断言 `test_r18_public_read_producer_pg.py:219-223`）。
2. `test_r18_public_producer_fix1_pg_pf.txt`：`test_mixed_source_modes_do_not_return_fixture_as_live`、`test_independent_missing_mode_fails_without_live_relabel`（2 例；后者回溯指向冻结独立评审探针 `reports/runs/r18_qualified_root_integration_20261017/original/test_independent_pg.py:102`，fix1 文件原样 import 断言，`test_r18_public_producer_fix1_pg.py:15-52`）。
3. `test_r18_public_producer_fix2_pg_pf.txt`：同名 2 例。
- 触发数据：`seed_intelligence(pg_engine, mode="live")`（`test_r18_public_read_producer_pg.py:130-140`）stamp `{"data_mode": "live"}` **无** `data_mode_policy_version`——按现行分类器（`revision_mode.py:20-26`）live 必须带 `TRUSTED_SOURCE_MODE_POLICY` 才可信 → 抛未分类异常。

### 根因甄别修正（重要，与 triage 报告的差异）

triage 报告家族2 推断"`public_extension_reads.py:228` 的 `classify_revision_mode` 抛 `RevisionModeUnavailableError`（ValueError 子类）被路由 137 行 `(SQLAlchemyError, ValueError)` 捕获"。**执行时核实不成立**：`classify_revision_mode` 包装器（`public_extension_reads.py:117-122`，`48f96b5ba` 引入）**已经**把 `RevisionModeUnavailableError` 转为 `PublicReadUnavailable` → 路由 `except PublicReadUnavailable` → `not_configured`。真实逃逸点是 KnowledgeReadService 投影调用：`public_extension_reads.py:251`（`read_evidence`，citations 路径）、`:275`、`:583`、`:604`（`event_detail`）抛出的 `KnowledgeProjectionError`（`knowledge_read_service.py:61`，**ValueError 子类**，消息同为 `stored_source_mode_unavailable`）被路由 `(SQLAlchemyError, ValueError)` 桶捕获 → `public_read_unavailable`（retryable=True）。

### 选项

**选项 A（探针/断言侧：接受 public_read_unavailable 新语义）**：更新 3 个测试文件断言与冻结独立评审探针。影响：触碰盲测/评审材料（`test_independent_pg.py` 属 2026-10-17 资格评审冻结物），必须走变更记录并统一重测全部对照；且"存储模式无法分类"本质是**配置态**（数据修正前永久存在），retryable=True 会引发无意义重试——语义倒退。
- 不可逆性：高（冻结评审材料改动 + 语义降级）。

**选项 B（产品侧映射修订：知识投影错误归入配置态）**：在 `public_extension_reads.py` 的 4 个 `self.knowledge.*` 调用点把 `KnowledgeProjectionError` 包装为 `PublicReadUnavailable`（→ 503 `not_configured`，retryable=False），与既有 `classify_revision_mode` 包装器（:117-122）完全同构。
- 影响的合同：仅公网读路由的错误码归类；两个错误码都是 503 且不泄露数据内容（fail-closed 保持）；普通 `ValueError`（参数类）仍走 `public_read_unavailable` 不变；`SQLAlchemyError` 基础设施错误映射不变。
- 不可逆性：低——一行类包装；冻结探针与全部断言零改动。

### 建议项及理由

**建议 B**。理由：(1) 语义正确——"存储数据的来源模式无法按当前政策分类"是数据/配置态问题（修复数据前恒定存在），不是可重试的基础设施抖动；冻结探针的 `not_configured`（retryable=False）正是这个语义；(2) 与产品内既有包装器同构，最小一致；(3) 零冻结材料改动——5 例断言（含独立评审探针）原样保留并通过。

### 执行后验证命令

```
cd backend && uv run python -m pytest tests/integration/test_r18_public_read_producer_pg.py tests/integration/test_r18_public_producer_fix1_pg.py tests/integration/test_r18_public_producer_fix2_pg.py -q --no-cov   # 容器内（钉定 run_id 见 batch21 plan）
uv run python -m pytest tests/unit tests/contract -q -k "public" --no-cov   # 宿主定向（公网读离线合同）
```

---

## 执行记录（方式B，随执行更新）

- 裁决①：待执行
- 裁决②：待执行
- 裁决③：待执行
