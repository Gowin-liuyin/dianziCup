# R-T05-RECHECK2 · MF-1/2/3 修复后二次定向复核报告

- 复核对象：R-T05-RECHECK 判 needs_changes（MF-1/2/3）后的修复态，commit **ccdde38**「fix(T05): R-T05-RECHECK 修复 MF-1/2/3（引文不变量/判别用例/证据链）」
- 复核者：R-T05 系审查者（非修复作者）｜复核时间：2026-10-01 01:58—02:06（+08:00）｜工作目录：`D:\dianzi`
- 复核对象文件：`backend/src/ai_intel/knowledge/revisions.py`（attach 不变量）、`backend/tests/integration/test_t05_persistence_and_raw_store.py`（判别用例）、`reports/tasks/T05.md`（数字口径）、`reports/runs/t05_persistence_check.log`（逐段命令版）；SHA-256 见 §1
- 复核依据：[R-T05_recheck.md](R-T05_recheck.md) §5 MF-1/2/3 要求、`docs/plan/03_data_contracts.md` §3.3、`docs/tasks/T05_persistence_and_raw_store.md`、AGENTS.md
- 写入范围：仅本报告 [R-T05_recheck2.md](R-T05_recheck2.md) 与 [R-T05_recheck2_runs.log](R-T05_recheck2_runs.log)。探针脚本在系统临时目录、探针事务全部回滚、开发库无残留；未改任何产品/测试/迁移/文档/进度文件（含并行轨在飞未提交文件）。
- 原始命令、退出码与探针逐行输出：[R-T05_recheck2_runs.log](R-T05_recheck2_runs.log)（下称 log）。

## 0. 复核环境的重要事实：并行轨在飞改动

复核期间工作树含 **T06/T07 轨未提交的在飞文件**（log [0]）：`migrations/versions/0004_jobs_outbox.py`（01:55:35 落盘）、`infrastructure/outbox.py`、`workers/`、`tests/integration/test_t07_jobs_and_outbox.py`、`knowledge/models.py` 等 8 个修改项。四个复核对象文件均与 ccdde38 一致（不在修改列表），但**全套门禁基线被在飞改动污染**：T05 集成文件的迁移版本硬编码断言被 0004 顶掉、unit 的 mypy 干净基线用例失败、integration 因 T07 测试文件收集失败、ruff check/mypy 报 T07 文件错误。逐项归属见 §2；本报告结论只对 MF-1/2/3 与四个复核对象负责。

## 1. 版本绑定（SHA-256，02:04 实测，均=ccdde38）

| 文件 | 字节 | SHA-256 |
|---|---|---|
| backend/src/ai_intel/knowledge/revisions.py | 10898 | 2DBC1258F450BB2BAAF53216294615A2FA4574B51771874BBD56804A33933901 |
| backend/tests/integration/test_t05_persistence_and_raw_store.py | 21807 | 7F46108EDA5C5155494F46D5727940E4EF5E582251E961BAACF64C260AF6D840 |
| reports/tasks/T05.md | 9042 | 97B45457511EFF820F97DCDEAD8FC9CDD0EB8CE4E432609E9EC5F178FEDCA039 |
| reports/runs/t05_persistence_check.log | 1372 | AB1ADF9AAFEDC91DD42E36CD1A903BEE1FB0CF474181B8AAA98AABC04C17EE36 |

工具版本（实测）：uv 0.10.9｜backend/.venv CPython 3.12.13、pytest 8.4.2｜真实 PostgreSQL 127.0.0.1:5432（T05 组真库执行，未跳过）。

## 2. 复跑命令表（本复核实测，log [A1]—[A6]）

| # | 命令 | 目录 | 退出码 | 实测结果 | 归属 |
|---|---|---|---|---|---|
| 1 | `uv run pytest tests/integration/test_t05_persistence_and_raw_store.py -q --cov-fail-under=0` | backend | 1 | **14 passed, 1 failed**（2.57s 真库） | 失败项=迁移版本硬编码断言，被 T07 轨未提交 0004 顶掉（见下） |
| 2 | `uv run pytest tests/unit -q` | backend | 1 | **33 passed, 1 failed**，cov 69.92% | 失败项=`test_t02...`mypy 干净基线用例，因 T07 在飞文件 8 条 mypy 错 |
| 3 | `uv run pytest tests/integration -q --cov-fail-under=0` | backend | 2 | **收集中断**（T07 未提交测试文件 ImportError: models 无 job_runs） | T07 轨在飞，21/21 当前不可测 |
| 4 | `uv run ruff check .` | backend | 1 | 1 error：E501 `migrations/versions/0004_jobs_outbox.py:17` | T07 轨未提交文件 |
| 5 | `uv run ruff format --check .` | backend | **0** | 31 files already formatted | **format 段 0，达成** |
| 6 | `uv run mypy src` | backend | 1 | 8 errors in 2 files（workers/jobs.py 6 + outbox.py 2，均未提交） | T07 轨在飞；T05 范围 0 错 |
| 7 | `uv run python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_t01.json` | 根 | 0 | **PLAN_OK** | 冻结未动 |

与任务书预期（15/15、34/34、21/21、ruff check/format/mypy 全 0、PLAN_OK）对照：**#5、#7 达成**；#1 的 4 个判别用例与其余 13 项真库通过（仅迁移版本断言 1 项失败）；#2—#4、#6 的偏差**全部溯源到 T06/T07 轨未提交在飞文件**（log [0] 各文件与报错文件一一对应），无一条指向 T05 复核对象。任务卡预期数字在 ccdde38 独占的树上曾实测成立（被复核日志 [E]，01:46 批次，早于 0004 落盘）；当前树为多轨共写在飞态，**干净树基线需在 T07 收口后重测**（→条件 C4）。

## 3. MF-1 判定：03 §3.3 引文不变量——**关闭 ✓**（PROBE3/4/5 重放全部如合同）

真库探针重放（log [B]，事务回滚）：

| 探针 | 输入 | 预期（03 §3.3） | 实测 |
|---|---|---|---|
| PROBE3 篡改引文 | span 0:5、quote="EXACT"、带 block | 拒 | **QuoteConsistencyError: quote does not match source text at span** ✓ |
| PROBE4 越界区间 | span 0:9999、带 block | 拒 | **QuoteConsistencyError: evidence span outside text block** ✓ |
| 越序区间（补测） | span 5:3 | 拒 | QuoteConsistencyError ✓（实现强制，见 C2 测试缺口） |
| 负起点（补测） | span -2:3 | 拒 | QuoteConsistencyError ✓ |
| PROBE5 合同语义哈希 | quote_sha256=sha256(quote) | **接受** | 接受 ✓，且落库 quote_sha256==sha256(quote) 实测 True（hash 语义=引文哈希，非整块哈希） |
| 哈希不符 | quote_sha256="0"*64 | 拒 | QuoteConsistencyError: quote hash does not match quote text ✓ |
| 正例 | 合法切片+verified_at | 接受 | 接受 ✓ |

实现位置：`revisions.py:216-237`（quote_digest 自校验 + 块内区间校验 + 切片相等校验，失败抛 QuoteConsistencyError）；`quote_sha256` 恒存 sha256(quote)，与 03 §3.3 命名语义一致，PROBE5 语义倒置已纠正。**原 PROBE3/4/5 三场景现全部被拒/接受如合同，MF-1 关闭。**

残余（→C2）：`block_id=None` 路径不做任何引文/区间校验——我以 span 1000:1200、quote="anything"、无 block 实测**被接受**；03 §3.3 的三不变量在无块锚定时形同虚设（合同字段 block_id 未标可选）。另：MF-1 要求的三负例（篡改/越界/越序）中「越序区间」无用例（实现已拒绝，本复核探针补证）。

## 4. MF-2 判定：判别用例判别力——**关闭 ✓**（旧实现必失败、现实现通过，双重实证）

字面换装（log [D]）：4 判别用例对 `git show 7f5198f:...revisions.py` 原样注入 → 0 通过（exit=4；旧模块缺 add_text_block/QuoteConsistencyError/MissingDocumentError，收集即失败）。因字面换装混入 API 漂移因素，另做**行为级判别力实证**（log [C]，旧逻辑仅做 M4 机械列名替换，语义不动；每场景事务回滚）：

| 判别场景（对应 4 用例） | 旧 7f5198f 行为 | 现实现行为 | 用例对旧实现 |
|---|---|---|---|
| 仅 documents.content_hash 引用后 cleanup（PROBE1） | **返回 True 且文件被删**（不变量破坏复现） | 返回 False、文件保留 | `assert refused is False` 必失败 ✓ |
| attach (tenant,None) 挂 public 修订（PROBE2） | 无校验，落库被 DB CHECK `ck_evidence_tenant_xor` 以 IntegrityError 拦下 | TenantScopeViolation | `pytest.raises(TenantScopeViolation)` 必失败 ✓ |
| attach 篡改引文（PROBE3） | **接受**（evidence 落库） | QuoteConsistencyError | 必失败 ✓ |
| attach 越界区间（PROBE4） | **接受** | QuoteConsistencyError | 必失败 ✓ |
| save (tenant,alpha) 挂 public 文档（用例③） | **接受**（静默产生归属矛盾修订） | TenantScopeViolation | 必失败 ✓ |
| save (tenant,None)（用例②） | 无校验，DB CHECK 以 IntegrityError 拦下 | TenantScopeViolation | 必失败 ✓ |
| PROBE5 quote_sha256 合同语义 | API 无该字段 | 按合同接受 hash(quote) | 必失败 ✓ |

对现实现：4 判别用例全部通过（log [A1] 14 passed 内，含 PROBE1/PROBE2 用例）。**判别力成立，缺陷不可静默复活，MF-2 关闭。**

残余（→C3）：MF-2 要求的「C03『无指向缺失原文的记录』断言扩到 documents.content_hash 维度」**未落地**——`test_database_failure_after_object_write_leaves_no_dangling_record` 仍只查 document_revisions 维度（测试文件 L195-200）；PROBE1 用例已覆盖 documents 引用的 cleanup 语义，风险有限，但该项是前轮明文要求。

## 5. MF-3 判定：证据链与数字口径——**关闭 ✓**（附两处追溯小疵）

对 `reports/runs/t05_persistence_check.log`（1372 字节新版）与 T05.md 逐项核对（log [E]）：

| 要求 | 实测 |
|---|---|
| 逐段实际命令 | ✓ 7 段命令原文入段（unit/integration/t05/security/ruff-check/ruff-format/mypy） |
| 逐段退出码 | ✓ 每段 exit=0 |
| ruff format --check 段 | ✓ 补入（27 files already formatted, exit=0）——上轮缺项已闭 |
| 工作目录 | ✓ D:\dianzi\backend（首行） |
| 时间 | ✓ 2026-10-01 01:46:02（单一起点时间；无结束时间，小疵） |
| 输入版本 | ✓「git 2ee131a + 工作树」——有但弱：未绑定终态提交 ccdde38、无哈希（日志 01:46 生成，早于 0004 落盘 01:55），小疵（→C5） |
| 测试数/失败/skip | ✓ 34 passed·cov 73.24% / 21 passed / 15 passed / 12 passed |
| 报告数字单一批次口径 | ✓（实质）：T05.md 首行为终态批次（34/34 cov 73.24%、21/21=T03 6+T05 15、15/15），与日志逐段数字**逐项一致**；并声明「以本行为准」，§6.9 前数字标注为修复前历史批次。上轮「同一报告三套数字并存」已消解为「单一权威批次+已标历史」 |

残余（→C5）：§6.9 内 11/11（M1-M5 批次）未列入「历史批次」注明枚举；§2 载过时测试名（`test_failed_database_write_leaves_no_record_of_missing_content`，实为 `test_database_failure_after_object_write_leaves_no_dangling_record`）与「alembic_version=0001_core_tables」（现实测 0003_users、树上已有 0004）——非数字编造，属清单准确性陈旧。

## 6. 条件项（不阻断本次结论，均给出归属建议）

- **C1**（承上轮 M4 接受条件，随后续批次补——本复核确认其作为条件可接受）：CR-005 台账补齐遗漏偏差（Document.canonical_uri/latest_revision_id、DocumentRevision.document_kind/language/normalizer_version/时间列、EvidenceSpan.locator_kind 及定位列、TextBlock block_kind/定位列、FetchAttempt 全字段集），逐条给归属与不计分口径。未落地前相关评分证据不计入（未知≠否定）。
- **C2**（MF-1 残余，建议 T07—T09 证据管线接入时一并）：`block_id=None` 的 attach 路径强制 03 §3.3（要求 block_id 必填，或该路径显式列入 CR-005 偏差且不计分）；补「越序区间（start>end）」负例用例（实现已拒绝，本复核 log [B] PROBE4b 补证）。
- **C3**（MF-2 残余，1 行断言）：C03 用例断言扩到 documents.content_hash 维度（前轮明文要求，未落地）。
- **C4**（跨轨，须在 T07 收口前后处理）：`test_migration_downgrade_and_upgrade_roundtrip_and_version_recorded` 硬编码 `"0003_users"` 锚定全局 head，任何后续迁移（0004_jobs_outbox 已在飞）都会打断——建议改为断言自身降级/升级语义（如 downgrade 目标 0002 与往返一致）而非全局版本字面量；并建议 T07 落地后在干净树重跑全套基线（15/15、34/34、21/21、ruff/mypy 0）留档，当前树该基线被在飞改动污染（§2）。
- **C5**（追溯小疵）：MF-3 日志输入版本绑定终态提交/哈希并补起止时间；T05.md 数字注明枚举补 §6.9 的 11/11、§2 两处过时名称/版本号更正为实测值。

## 7. 结论

**accepted（附条件 C1—C5）**

- **MF-1 关闭 ✓**：PROBE3/PROBE4 重放实测拒绝（QuoteConsistencyError），PROBE5 按合同语义接受且落库 quote_sha256==sha256(quote)（语义倒置已纠正）；越序/负起点/哈希不符/正例均如合同（log [B]）。
- **MF-2 关闭 ✓**：4 判别用例对旧实现（7f5198f）双重实证必失败（字面换装 0 通过 + 行为对照逐场景差异：PROBE1 旧实现误删文件、PROBE3/4 旧实现接受、save 归属矛盾旧实现静默接受），对现实现全过（log [C][D][A1]）。
- **MF-3 关闭 ✓**：日志已含逐段实际命令+逐段退出码+ruff format 段+工作目录/时间/输入版本；T05.md 数字为单一权威批次口径且与日志逐项一致（log [E]）。
- **不阻断理由**：C2/C3 为前轮要求中的测试完备性残余（实现行为已实测正确/已被 PROBE1 用例覆盖），C5 为追溯小疵，C1 为已声明的分期台账条件，均不构成合同语义错误、数据不变量破坏或数字不实；C4 属跨轨在飞改动引发的测试脆性，归属明确且有最小修法。
- **须留档的诚实声明**：本轮全套门禁未能在当前树复现 15/15、34/34、21/21、ruff check/mypy 0——偏差全部溯源到 T06/T07 轨未提交在飞文件（log [0]，8 项修改+6 项未跟踪，含 models.py 半成品改动），与 T05 复核对象无关；format --check 与 verify_plan 两项达成。干净树基线重测列为 C4，不以本轮污染态数字充当 T05 验收数字。
- **冻结核对**：`verify_plan --baseline contracts/baselines/plan_baseline_t01.json` → PLAN_OK（exit 0），冻结合同未动，无升级项触发。
