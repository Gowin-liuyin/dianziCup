# R-T05-RECHECK · T05 修复后定向复核报告（M1—M5）

- 复核对象：R-T05 判 needs_changes 后的修复态（commit **cb34cd0**「feat(T05/T06): R-T05 审查修复 M1-M5 + T06 认证与租户权限实现」）
- 复核者：R-T05 原审查者（非修复作者）｜复核时间：2026-10-01（本地时区）｜工作目录：`D:\dianzi`
- 复核依据：原审查 [R-T05.md](R-T05.md)（M1—M5、C-a—C-f、PROBE1/PROBE2）、`docs/tasks/T05_persistence_and_raw_store.md`、`docs/plan/03_data_contracts.md` §1/§3/§4、AGENTS.md
- 范围说明：T06 相关文件（`api/authentication.py`、`domain/access.py`、`tests/security/`）由并行任务轨实施，**不属本次复核**；其引发的仓库级 `ruff format --check` 失败仅作观察记录（§6 C2）。
- 本复核只写 `reports/reviews/R-T05_recheck.md` 与 [R-T05_recheck_runs.log](R-T05_recheck_runs.log)（原始命令、退出码与探针输出全量见该 log）；未改任何产品/测试/迁移/文档/进度文件。探针全部事务回滚，探针对象文件在系统临时目录并已清理，开发库无残留。
- 版本绑定：复核对象 SHA-256 见 §1，结论只对该版本负责。

## 1. 复核对象 SHA-256（绑定版本）

| 文件 | 字节 | SHA-256 |
|---|---|---|
| backend/migrations/versions/0002_constraints_and_text_blocks.py | 3561 | DEC2CE6845A85A769D668CE0A6C7776C82120165535241921BD04DA780C5B3B1 |
| backend/src/ai_intel/knowledge/models.py | 5221 | 72628CE919DCB992B36C79A17E08BE958E89DAEC995FC0D321FAA88CACA0A276 |
| backend/src/ai_intel/knowledge/revisions.py | 10623 | 388854B18BD360F6825CA95C57B6AD8A16BFAC282221CD232C100D1FE2011520 |
| backend/src/ai_intel/infrastructure/content_store.py | 3374 | D545FC54CBA783C36389E74C9A1EACF9EBC07A479BFD2D2C7F125E3E7BD55AAF |
| backend/tests/integration/test_t05_persistence_and_raw_store.py | 17069 | 36572E0F4CA4A9F294BCA8720C4CAB7B0F637626D8D874EDE5227501A4F42399 |
| reports/tasks/T05.md | 8521 | 82A138964A98EC03425F1AAA3ACD8EE3A7927A73860F98067AD8CAAC5E9ACB7A |
| docs/decisions/cr005_data_contract_alignment.md | 1720 | B57095EB8F4C12BDBCC741DB32E6CCEEFD6236C708B1646AE45A6BF6848A934D |
| reports/runs/t05_persistence_check.log | 767 | 9BE63619024C6F3AAC635DFB180C1D7F35C8BE8ED7778993E6B73E946231D880 |

工具版本（实测）：uv 0.10.9｜backend/.venv CPython 3.12.13、pytest 8.4.2｜真实 PostgreSQL 127.0.0.1:5432（T05 集成组未跳过，全部真库执行）。

## 2. 复跑命令表（本复核实测，log [A1]—[A7]）

| # | 命令 | 工作目录 | 退出码 | 结果 |
|---|---|---|---|---|
| 1 | `uv run pytest tests/integration/test_t05_persistence_and_raw_store.py -q --cov-fail-under=0` | backend | 0 | **11 passed** in 2.59s（真库真文件，无 skip） |
| 2 | `uv run pytest tests/unit -q` | backend | 0 | **34 passed**，cov **75.99%**（门槛 60） |
| 3 | `uv run pytest tests/integration -q --cov-fail-under=0` | backend | 0 | **17 passed** in 12.99s（T03 6 + T05 11） |
| 4 | `uv run ruff check .` | backend | 0 | All checks passed! |
| 5 | `uv run ruff format --check .` | backend | **1** | 1 file would be reformatted：`src/ai_intel/domain/access.py`（**T06 轨文件，超出本复核范围**）；25 files already formatted（T05 范围内全合规） |
| 6 | `uv run mypy src` | backend | 0 | Success: no issues found in **16 source files** |
| 7 | `uv run python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_t01.json` | 根 | 0 | **PLAN_OK**，无 BASELINE_* 违例 → 冻结未动 |

对照任务卡预期（11/11、34/34、17/17、ruff/mypy 0、PLAN_OK）：除第 5 项（T06 并行轨文件所致，非 T05 缺陷）外全部达成；测试数量与 T05.md §6.9「11/11 通过」一致。

## 3. M1—M5 逐项判定

### M1（C03 恒真 + cleanup 引用判定）：实现缺陷实测关闭 ✓；回归用例无判别力 → MF-2

- **实现**（`revisions.py:295-309`）：`cleanup_unreferenced_object` 现同时统计 `document_revisions.content_hash` 与 `documents.content_hash` 引用，任一 >0 即返回 False；零引用时删文件并同删 `content_objects` 行 ✓。
- **PROBE1 复现**（log [C1]，真库、事务回滚）：**仅** documents.content_hash 引用、content_objects 行在、文件在 → cleanup 返回 **False**、登记行保留、文件保留。修复前实现在此场景返回 True 并删文件（原 PROBE1）→ **实现层不变量恢复，M1 实现缺陷关闭**。
- **`test_cleanup_refuses_to_delete_referenced_object`**：断言拒删 + content_objects 行保留 + 文件存在 ✓，但**未复现 PROBE1 判别场景**——用例经 save 后 documents 与 revisions 同时引用该 hash，而修复前实现（仅查 document_revisions）在该场景同样返回 False，该用例对修复**无判别力**（缺陷可静默复活，log [D1]）。判别场景应为：仅 documents.content_hash 引用、无任何 revision 引用。
- **C03**（`test_database_failure_after_object_write_leaves_no_dangling_record`）：已改为真实失败路径——不存在文档 → **MissingDocumentError**（修复前为 FK IntegrityError，此断言有判别力）、`engine.begin()` **事务回滚**、孤儿对象清理返回 True 且文件删除、无指向缺失原文的 revision 行 ✓。残余：「无任何指向缺失原文的记录」仅查 revisions，未查 documents.content_hash 维度。

### M2（租户双向校验 + 0002 约束）：全部实测成立 ✓；负例覆盖缺口 → MF-2

- **service 层**（log [C2][C3]）：attach `visibility='tenant', tenant_id=None` → `TenantScopeViolation`（PROBE2 原场景关闭）；public 文档保存 tenant 修订 → 「revision scope does not match document scope」（修订-文档归属校验生效）✓。save/attach 均有 (visibility=='tenant')⇔(tenant_id 非空) 双向校验。
- **0002 约束实建**（log [B1]—[B3]，pg_constraint/information_schema 实测）：**5 表**（sources/documents/document_revisions/evidence/claims）× `ck_*_visibility` + `ck_*_tenant_xor` 共 10 条 CHECK 实存；PROBE A 以 documents 插入 (tenant, NULL) **实测被 `ck_documents_tenant_xor` 拒绝**（约束强制力非纸面）✓。
- **claims 组合索引**：`ix_claims_subject_predicate_status(subject, predicate, claim_status)` 实存 ✓（= 03 §4「claims(subject,predicate,status)」）。
- **当前修订部分唯一索引（原 C-b）**：`uq_current_revision_per_document UNIQUE(document_id) WHERE is_current` 实存，PROBE B 同文档双末版**实测被拒** → **C-b 关闭** ✓。
- **测试缺口**：save 层两条绕过分支（`revisions.py:90/92`）**无任何用例**（coverage 显示未执行）；C05 三例（含新增「缺 tenant」例）经与修复前实现对照（log [D3]）**全部无判别力**——旧实现对三例同样抛错，PROBE2 判别场景（public 修订 + tenant/None）未入测试 → 归入 MF-2。

### M3（TextBlock/引文一致性）：结构与哈希校验落地 ✓；03 §3.3 核心不变量未强制 → MF-1

- **结构**（log [B3]）：`text_blocks` 表（block_id/revision_id/ordinal/start_offset/end_offset/text_sha256/block_text + `uq_block_ordinal_per_revision` + 区间不倒置 CHECK）与 `evidence.block_id/quote_sha256/verified_at` 三列实存 ✓；`add_text_block` 落块哈希 ✓。
- **attach 校验**：quote_sha256 与块哈希不符 → `QuoteConsistencyError` ✓；block 不存在/属他修订 → 拒绝（PROBE6 实测拒绝）✓；**正例挂接** `test_evidence_attach_success_and_quote_consistency` 覆盖原零覆盖的插入路径 ✓，cleanup 拒删路径亦有正例 ✓。
- **但 03 §3.3 不变量仍未强制**（log [C4]—[C6]，真库实测）：
  - PROBE3：quote 与 `block_text[0:8]` **完全不同** → 被**接受**（`block.text[start:end] == quote_text` 不变量可绕过）；
  - PROBE4：start=1000/end=1200 **超出块范围** → 被**接受**（「范围合法」不变量可绕过）；
  - PROBE5：按合同语义传 `quote_sha256=hash(quote_text)` → 反被**拒绝**，即 `quote_sha256` 列实际语义是 hash(block_text)（整块哈希），与 03 §3.3 的 quote_sha256（引文哈希）**命名-语义不符**。
- 判定：M3 要求的「引文哈希校验」字面存在，但「quote 与原文一致性、区间合法性」（原 M3 明示要求）**未实现**，03 §3.3 在当前实现下仍不可验证 → 归入 MF-1。

### M4（命名对齐 + CR-005）：**条件接受**（理由与条件见下）

- **命名对齐** ✓：models/revisions/0002 全部使用 `revision_number`/`previous_revision_id`；旧名仅存于 0001 历史迁移与 0002 的 `alter_column` 改名对（正确做法）；live 列名实测一致（log [B3][F3]）。
- **CR-005** 具备「偏差/归属/不计分声明」三要素 ✓（「对应任务落地前，相关评分证据不计入，未知≠否定」）；分期归属（T07/T08/T09）与业务管线耦合的论证成立，「不提前批量建无关列」符合任务卡 §3。
- **不完全接受的理由**：偏差清单**不完整**——未如实列出原 M4 表中的多项偏差：`Document.canonical_uri/latest_revision_id`；`DocumentRevision.document_kind/language/normalizer_version/source_published_at/source_modified_at/first_observed_at/ingested_at`；`EvidenceSpan.locator_kind`（现为 locator）及 page_number/bounding_box/json_pointer；`TextBlock block_kind/page_number/section/json_pointer/table_headers`；`FetchAttempt.source_record_id/raw_sha256/response_size_bytes/effective_uri/requested_at/completed_at/status_code/error_code/rate_limit_wait_seconds`（仅列 new_event_count）。变更单应是完整偏差台账，遗漏项无归属与不计分口径 → 作为接受条件 C1。

### M5（证据链）：显著改善，仍未闭环 → MF-3

- `reports/runs/t05_persistence_check.log` 现含批次时间、四段（unit/integration/security/lint-type）、测试数与**逐段退出码**（34 passed·unit exit=0；17 passed·integration exit=0；9 passed·security exit=0；ruff exit=0 mypy exit=0）——较修复前 87 字节矛盾日志实质改善 ✓。
- 但对照本次要求「**逐段命令**+退出码」与任务卡 §6（命令、工作目录、开始/结束、退出码、测试数、失败/skip、日志路径、输入版本）：
  1. 日志**无逐段实际命令**（只有 `== unit ==` 等段标签），无工作目录/结束时间/输入版本；
  2. **缺 `ruff format --check` 段**（报告 §4 载该项）；
  3. T05.md §6.9 称日志为「逐段命令+退出码」的完整批次——**与日志实际内容不符**；
  4. **报告与日志数字不一致**：T05.md 首行与 §2/§4 仍载修复前数字（unit 30/30 cov 72.73%、9/9、15/15），所引日志为 34/34 cov 76.10%、17/17，§6.9 又记 11/11——同一报告三套数字且未标注批次归属。
- 说明（log [F1]）：日志覆盖率（523 stmts/76.10%）与本复跑（529 stmts/75.99%）小幅漂移，因 T06 并行轨在复核期间仍在改 src（authentication.py 两轮间 132→138 stmts），**不属数字编造**；但证据链要求引用可复现的逐段命令输出。

## 4. T05.md §6.9 修复附录逐条核对（诚实性）

| §6.9 声明 | 复核结果 |
|---|---|
| M1 cleanup 双引用检查 + 同删 content_objects；新增拒删测试；C03 改真实失败路径 | 实现与 C03 **属实**（PROBE1 复现拒删 ✓）；「M1 探针场景」一词不准确——测试未覆盖 PROBE1 判别场景（MF-2） |
| M2 双向校验 + 归属校验 + 0002 CHECK/索引/部分唯一（C-b 关闭） | **全部实测属实**（含约束强制力 PROBE A/B）；「C05 增缺 tenant 负例」属实但该负例无判别力（MF-2） |
| M3 text_blocks + 三列 + add_text_block/attach 校验 + 正例 | 结构与正例**属实**；「引文一致性」表述超出实际校验范围（03 §3.3 不变量可绕过，MF-1） |
| M4 命名对齐 + CR-005 分期单 | 命名**属实**；CR-005 清单不完整（C1） |
| M5 日志「逐段命令+退出码」完整批次且与报告一致 | **不成立**（MF-3：无逐段命令、缺 format 段、报告三套数字） |
| 条件项：C-b 已建 / C-e 增完整性校验 / C-a 保持 not_run / C-c、C-d、C-f 如实登记 | **属实**：C-b 实测关闭；C-e 可见于 `content_store.py:46-49`（已存在对象重算哈希，损坏抛 ValueError）；C-a not_run 未冒充 ✓ |

未发现新的夸大、编造、密钥泄漏；not_run 项如实。

## 5. 必须修复项（needs_changes 依据）

### MF-1〔M3 残留·合同/数据〕03 §3.3 引文不变量仍可绕过（PROBE3/4/5 实测）

- `attach_evidence_span` 未校验 `block_text[start_offset:end_offset] == quote`，未校验区间在块内合法，`quote_sha256` 语义为整块哈希而非引文哈希。
- 要求：挂接时强制 03 §3.3 三不变量（引文=原文切片、hash 一致、范围合法），不一致抛 `QuoteConsistencyError`；`quote_sha256` 按合同改存 hash(quote_text)（块哈希已有 `text_sha256` 承担），或若维持现语义须在 CR-005 明列该命名偏差及理由；补负例（quote 篡改、区间越界、越序区间）与对应正例断言。

### MF-2〔M1/M2 残留·测试判别力〕新增回归用例对修复前实现无判别力（log [D1]—[D3]）

- `test_cleanup_refuses_to_delete_referenced_object`、C05 三例在**修复前实现下同样通过**；PROBE1 判别场景（仅 documents.content_hash 引用）与 save 层绕过负例（`revisions.py:90/92`）、PROBE2 判别场景（public 修订 + tenant/None）均无用例——缺陷可静默复活，违反任务卡 §5「负例不能只测『没有报错』」的判别意图。
- 要求：补 4 个判别性用例：① 仅 documents 引用 → cleanup 拒删且行/文件保留；② save 传 (tenant, None) 或 (public, 非空) → TenantScopeViolation；③ save 修订 visibility/tenant 与文档不一致 → TenantScopeViolation；④ attach (tenant, None) 挂 public 修订（PROBE2 原场景）→ TenantScopeViolation。并把 C03 的「无指向缺失原文的记录」断言扩到 documents.content_hash 维度。可用测试实证判别力（对旧实现跑应失败）。

### MF-3〔M5 残留·证据链〕运行日志仍不满足「逐段命令+退出码」且与报告不一致

- 要求：重生成 `t05_persistence_check.log`（或新批次日志）为逐段**实际命令**+工作目录+起止时间+退出码+测试数+失败/skip+输入版本（代码版本/哈希），补 `ruff format --check` 段；同步更新 T05.md 首行与 §2/§4 的测试数/覆盖率至修复后真实值（11/11、17/17、34/34），或明确标注「修复前批次」与「修复后批次」两套数字的归属，消除同一报告三套数字并存。

## 6. 条件项与观察（不阻断，建议随 MF 项一并处理）

- **C1**（→M4 接受条件）：CR-005 分期单补齐 §3 所列遗漏偏差（canonical_uri、latest_revision_id、document_kind、language、normalizer_version、locator_kind、TextBlock block_kind/定位列、FetchAttempt 全字段集），每条给出归属与不计分口径。
- **C2**：`ruff format --check` 当前 exit=1，源文件 `src/ai_intel/domain/access.py`（T06 轨，复核范围外）；T05.md §4「全 0」在仓库级已不成立，待 T06 轨收口后复测登记。
- **C3**：coverage 缺口仍在：`revisions.py:59`（content_objects 幂等登记）、`:170/:210`（MissingRevisionError 两处）、`:226`（跨修订 block 拒绝，PROBE6 已实测但无用例）——建议随 MF-2 一并补。
- **C4**：日志覆盖率与复跑存在小幅漂移（T06 轨活跃编辑所致，log [F1]）；报告引用数字时建议绑定代码版本。
- **C-a/C-c/C-d/C-f**：维持原审查口径（旧库真实升级 not_run 如实；dev DSN 占位口令建议环境注入；共享 dev 库 downgrade 风险如实登记；session_scope 正例待持久化接入）。

## 7. 结论

**needs_changes**（必须修复：MF-1、MF-2、MF-3；M4 条件接受，条件 C1；条件项 C2—C4 建议一并处理）。

- **正面确认（实测）**：M1 实现缺陷关闭（PROBE1 判别场景复现拒删，行/文件保留）；M2 实现缺陷关闭（PROBE2/PROBE2b 拒绝），0002 的 5 表 CHECK、claims 组合索引、当前修订部分唯一索引**实建且强制**（PROBE A/B），**C-b 关闭**；C-e 关闭；text_blocks/证据三列与挂接正例落地，跨修订 block 拒绝生效；命名对齐（revision_number/previous_revision_id）；CR-005 机制成立；复跑 **11/11、34/34、17/17、ruff check 0、mypy 0、PLAN_OK** 与 §6.9「11/11」一致。
- **阻断原因**：① 03 §3.3 引文-原文不变量仍可绕过（PROBE3/4 实测接受、PROBE5 语义倒置），属数据合同问题；② M1/M2 新增回归用例对修复前实现无判别力，PROBE1/PROBE2 判别场景与 save 层负例缺失，缺陷可静默复活，属测试真实性问题；③ M5 证据链仍不完整（日志无逐段命令/缺 format 段、报告三套数字不一致），属诚实性/证据问题。按 AGENTS.md §3/§9 与任务卡 §7，存在合同/数据/证据问题不得判 accepted。
- **冻结核对**：`verify_plan --baseline contracts/baselines/plan_baseline_t01.json` → PLAN_OK（exit 0），冻结合同未被改动，无升级项触发。
