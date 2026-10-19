# R07 · 发布父级 ACL 与来源写入锁顺序修复

状态：awaiting_review。两项限定修复的实现 complete；自动回归见下文。
原独立探针仍有 2 个失败，整 R07 与 G-C 不放行；未自行 accepted、push 或更新主 checkout/progress。
报告实际封存时间、命令时间和字节哈希由本轮 raw_manifest 绑定。

基线：71e594cb958bd93d21fb7ed66574b3cba4cc47e1。
代码冻结：a80408fb35addf35c04a91d255f20fb9a987423e。
工作树：D:/wt/r07-pub-fix；分支：codex/r07-publication-acl-lock-fix。
证据目录：reports/runs/recovery_r07_publication_acl_lock_fix_20261016/。

## 输入输出与修改文件

输入仍为认证 AccessScope、PG 事件及不可变修订快照、最多九个 DimensionAttempt、request_id 和有时区时间。
成功输出仍为原 PublishedEnrichmentDimension 及 PG 回执；撤权、清单不完整、非法候选或过期新请求明确拒绝，事务不半写。

| 文件 | 实际修改 |
|---|---|
| backend/src/ai_intel/enrichment/inputs.py | 全清单在第一次对象 IO 前检查 source/document/revision 三级 ACL 和派生范围 |
| backend/src/ai_intel/enrichment/publication.py | 按实际 PG 事件关联预锁父对象；回执前权限复核；新请求保留完整 current/CAS |
| backend/tests/integration/test_r07_publication_acl_lock_fix_pg.py | 15 个真实隔离 PG 回归，包括实际 advisory 等待观察 |
| docs/decisions/CR-R07_multisource_enrichment_publication.md | 记录权限、历史重放兼容性、锁顺序与实际调用方 |
| 本报告与本轮运行目录 | 原始失败、命令、源码字节、共享文件不变哈希与封存清单 |

未改 signals.py/signal_sources.py、共享来源写者、合同 schema、迁移、认证、runtime、app、UI、指标或盲测材料；九维、原 T19/T20/T21 验收范围保留。

## 两项根因及最小修复

旧 inputs 仅查修订 ACL 和 source.category，公开修订的父 source/document 撤权后仍会读对象字节。
旧 publication 只在候选引用检查中间接校来源，合法 FAILED 空 candidate 可以绕过撤权父行。
现复用 DocumentReadService._visible 的严格公共三级条件，并通过 VisibilityScope 与认证范围验证私有派生限制。
输入整份 roster 必须全部通过后才读任何对象；发布包含无候选维度也重查全部来源。

发布先从 PG event_documents/document_revisions/documents 真实关联取得来源，多个 source 标识排序取得既有 source advisory；
随后 source FOR SHARE、按 document/revision 标识排序的 FOR UPDATE，再取得 publication scope advisory 和 event 行锁。
持父锁后再核对实际映射；候选或 model_copy 的 source_id 不能控制锁。
source FOR SHARE 阻止父 ACL 在提交前变动，同时兼容外键 KEY SHARE。
没有捕获数据库死锁伪造成功、关闭并发、增大超时或增加无界重试。

幂等历史重放仍返回原 result/claim 标识，允许原文 current 或事件版本变化；回执重放先重查当前父级权限。
新的请求仍进行 current/CAS 和原文快照检查；来源先提交时旧快照发布明确拒绝，且没有新事实/回执半写。
旧单来源格式、多来源完整收据、原非法候选整体 rollback 均由保留回归核验。

## 实际调用方与锁路径证据

官方 WSL Ubuntu-22.04 root CBM CLI：/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp。
本工作树 backend/src 独立 full index、graph schema、完整限定名双向 trace 和 rg 均实际运行，见 caller_before_* 与 caller_frozen_* 的 log/json。
CBM 的少数文件级 heuristic caller 已用 rg 和源代码逐项核对，未依据 graph 的空 caller 推论无调用。

persist_source_response 在 begin_nested 内调用 ensure_source_registration；基线 source_documents.py 第 373 行已取得 source advisory，
第 415 行是真实入口调用，不只存在于 worker。随后 _persist_member 取 document advisory/行锁，再经 EventRepository 获取 scope/event。
source_jobs.collect_page 的真实 catalog 路径也先 ensure_source_registration；直接 persist_catalog_documents 不取得 publication scope 锁。
save_document_revision 只按 document/content 取锁；EventRepository 在 scope 后取 event，不反向锁文档。
rg 未找到名为 publish_document 的独立产品入口；存在的实际修订入口为 save_document_revision。
source_documents/catalog_documents/revisions/event_linking/persistence/signals/signal_sources 与基线 Git blob 完全相同，见 manifest。

## 命令与真实结果

独占 Python 3.12.13 venv 由 `uv sync --locked --offline --extra semantic` 建立；未下载模型或更改锁文件。
PG 仅使用私有 WSL connection.json 捕获后注入；未输出 DSN/密码。
数据库 test_dianzi_r06_catalog_r07_pub_fix_20261016，DIANZI_TEST_RUN_ID=r06_catalog_r07_pub_fix_20261016；
每例 catalog_engine 使用 UUID schema、statement_timeout=15000、lock_timeout=5000；没有开发 DSN 或破坏性 downgrade。
每条完整 argv、cwd、开始/结束 +08:00、退出码、pytest XML 和 source runtime hash 均在同名 json/log/xml 中。

| 实际命令入口及证据 | 退出码 | 真实结果 |
|---|---:|---|
| run_checks.py negative baseline_original_probe9 | 1 | 基线同字节独立探针 5 failed / 4 passed，真实 40P01 重现 |
| run_checks.py pytest baseline_fix_tests tests/integration/test_r07_publication_acl_lock_fix_pg.py | 1 | 最初 14 case 全 red；当时源码尚未修改 |
| run_checks.py pytest fix_tests_attempt1 ... | 1 | 13 passed / 1 failed；新多源屏障暂停了非竞争来源，仪器修正保留日志 |
| run_checks.py pytest fix_tests_attempt2 ... | 0 | 14 passed |
| run_checks.py pytest fix_tests_attempt3 ... | 0 | 15 passed，补实际 PG 来源锁身份反例 |
| run_checks.py pytest fix_pg_wait_observation ... | 0 | 15 passed，pg_locks 观察实际未授予 advisory 后释放 |
| run_checks.py pytest frozen_pg92 ... | 1 | 91 passed / 1 failed；错误并行运行旧阻塞屏障造成同 DB advisory 干扰，保留原失败 |
| run_checks.py pytest frozen_pg92_serial ... | 0 | 旧 77 + 新 15 = 92 passed；0 failed/error/skipped |
| run_checks.py pytest frozen_unit_contract202 ... | 0 | 202 passed；0 failed/error/skipped |
| run_checks.py pytest frozen_security203 tests/security | 0 | 203 passed；0 failed/error/skipped，1 个第三方 deprecation warning |
| run_checks.py negative frozen_original_probe9_serial | 1 | 不改原字节/期待：7 passed / 2 failed；4 个 real_pg marker warning |
| run_checks.py checks frozen_static | 0 | Ruff、format 各通过；mypy 99 source files 无问题 |
| run_checks.py cbm caller_frozen | 0 | index/schema/5 个限定 trace/rg 全部实际通过 |
| run_checks.py scan frozen_secret_scan | 0 | 原仓库模式与实际 PG 密码、完整 DSN 精确扫描通过；已有精确 fixture 分类保留 |

92 项串行最终 PG 实际时间：2026-10-16T03:14:12.000043+08:00 至 03:15:49.583739+08:00，pytest 95.22s。
完整 pytest 文件清单见 frozen_pg92_serial.json 与 frozen_unit_contract202.json，未用缩写命令冒充完整 argv。
本任务不重复完整 pure；既有 1992 passed / 1 CPU red、75.82% coverage、原 60 门槛均保留，未宣称 CPU 或 startup535 已由本修复解决。

## 原探针保留失败与仪器边界

独立原文件 SHA256：ebfc4dc423c5cdd32972adbad6eb4a9c92def6fd28261affa91a68f0fd7b22c3，
本轮副本与原 reviewer 当前文件字节相同。原 extended.xml 是先前 8 参数 case 的历史记录；
后续追加多来源读反例后当前原文件为 9 case。两份分母、代码与原 extended log/json/xml 均保留，未删例、改期待或 skip。

剩余一项是真实 CVSS 不同 authority 被误判 conflict，由另一独占作者处理；本文件未改该规则。
另一项原并发探针的 after_cursor_execute 屏障要求 publisher 取得 scope/advisory 后才释放已经持 source/document 的 writer；
修复后 publisher 按正确顺序等待 writer 的 source，原屏障不释放 writer。
串行重跑实际结果为 writer AssertionError、publisher 55P03，无 40P01，但该原探针仍记 failed，不能用“无死锁”把它涂绿。
新四个并发 case 覆盖单源/多源和 source-first/publisher-first，实际 pg_locks 观察第二事务等待；
source-first 为 writer completed + publisher stale_snapshot_rejected，publisher-first 均 completed；
源锁排序、无重复回执、历史 replay、0 半写均断言，保持有限超时。
原 reviewer 仍须独立设计新时序实跑后决定是否关闭并发 Must，不能只读作者测试签字。

## 评分证据、偏差与交接

F2/F3 与 T19-C06/T21-C06：三级父 ACL、全清单首次 IO 前撤权、空候选发布与历史回执撤权断言。
T19-C04/T21-C04：原重复请求、事件/原文变化后历史标识保持、并发请求回归。
T20-C04/C06：原字段/evidence 篡改拒绝、非法候选整事务回滚及多来源准确引用未削减。
P2：仅证明回归行为；没有准确率、召回率、外部源或真实模型指标。

合同偏差：无范围或计分变更；CR 仅明确本来要求的 ACL、锁顺序和兼容性。
运行偏差：首轮并行 PG/旧屏障的资源干扰与新测试仪器错误已全部归档，最终 PG 使用相同 freeze 串行取得通过。
原始 pytest 日志含工具产生的行尾空格，按原字节保存；代码、CR 与报告的 diff 检查单独通过。
运行目录专属 .gitattributes 仅关闭该目录的 Git 换行转换，保证 byteblob/日志/manifest 哈希跨 checkout 不变，未全局忽略代码检查。
live、manual、frontend、e2e 均 not_run；真实模型、FOFA、外部来源与资产能力本轮没有新增调用或通过声明。
下一步：主控合并此代码/证据与独占 CVSS 修复后，原 reviewer 冻结新 SHA 独立复核；整 R07 与 G-C 仍待放行。
