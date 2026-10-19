# G-C · R06 失败响应留证 fix1 定向复核

本变更行为：将原九源 worker 回归的失败原文期待同步到已批准 CR，保留原失败输入、业务回滚和不推进游标的要求，并移除重复导出旧测试的 wrapper。生产留证接线、0016 迁移和业务合同没有改变。

**Verdict: Ship，限失败留证及此次原回归合同同步切片。** 首次评审唯一 Must 1 已闭环；没有新增 Must/Should finding。不签整 R06、G-C、原 T08/T49 accepted，不写 progress，不推送。

实际复核记录时刻2026-10-16T01:40:12+08:00；最终封存时刻见新 run artifact_manifest。原 reviewer、非作者、无 spawn；新独立工作树 `D:/wt/r06-failed-response-review-1-recheck`，分支 `codex/r06-failed-response-review-1-recheck`。固定材料 `b7817239022caed52ba6b8912b2d827c58a60181`、修复代码 `e1bae9db650df7946417cf42ec3817484514483a`、前版材料 `9eb01d7ba843116122a9a2462f3b74a2626cc48c`、原业务代码 `e192234550fdd1c405d165a7a93772a952b8ea5b`。本轮命令在 b781 HEAD 上执行；e1 到 b781 只增加材料，产品源码身份按 e1/Git blob 另记。首次评审报告和红日志固定在 `dcfcab9a39157b08f12567b7008fd4e88a1ac71c`，没有覆盖或追删。

沿用 Ponytail 5.2 review，并核对 AGENTS、00、R06/T08/T49、冻结 03/04/05/06 与 CR-R06_failed_response_receipts 的本次影响；读取作者 R06-failed-response-persistence-fix1.md、新 run 和当前 state/交接。9eb 到 e1 的业务、迁移、公共合同、progress diff 为空；本 reviewer 只新增本报告与新独立 run，未改业务、产品测试、fixture、合同、阈值、金标、依赖或状态。

## Must 1 复验与原不变量

问题原定位：新增 legacy 文件 `test_r06_failed_response_legacy_pg.py:17` 把仍要求 raw=0 的旧失败断言再次收集进 integration。首次独立复跑为27 passed/6 failed；新增六绿不能抵消原红。fix1 删除的是这份新重复导出 wrapper，原 `test_r06_source_worker_pg.py` 仍为原入口，其 33 个场景现在只执行一次。

独立 AST 对照 [case_identity_audit.json](../../runs/recovery_r06_failed_response_review_1_recheck_20261016/case_identity_audit.json) 证明全部函数名、九失败参数化、输入及 outcome 断言前缀一致；除目标失败断言和数据库 fixture 外，其他函数 AST 完全相同。原其余24场景不删不改；没有 skip/xfail、排除难例、改阈值/分母或用新 wrapper 替代原入口。独立 collect 为33+43=76，原 wrapper 文件不存在。

修复后原失败断言的检查位置为 `backend/tests/integration/test_r06_source_worker_pg.py:311` 起：documents/revisions/evidence/fetch_attempts/source_page_receipts/source_cursors 仍为0，并新增 text_blocks/claims/events 为0；job_runs 仍1，status/error/attempt 精确核对；outbox 只能指向原 job，数量严格为原投递加合法 retry，不能产生 continuation job。

六个允许 retained raw 的场景现按固定输入核验，而非只接受被测输出：second_document/cursor_commit/continuation 使用原 arXiv fixture bytes，invalid_page 使用固定坏 bytes，blob_corrupt 使用固定 tree 与篡改 blob bytes，blob_limit 为 tree 与无 body 的429。`:347`–`:365` 要求 content_objects hash 集合同时等于该 job/attempt 的 receipt 引用集合与 fixture bytes 的 SHA 集合，逐 ordinal 检查 size/hash/store.read_verified 字节；`:337`–`:346` 精确检查来源、job、attempt、HTTP、parse_outcome/error。storage/wrong_type/timeout 在`:357`仍明确要求 content_objects=0，hash/size 同为空。此修订落实独立失败留证，不削减业务回滚或来源成功判据。

主控明确批准的 fixture 改动仅 `:51`：hardcoded 旧库名改为非空 `test_dianzi_r06_catalog_` 前缀。`:55` current_database 与 URL 一致、UUID schema、search_path、15s statement/5s lock/5s connect timeout、migration namespace 和仅清理自身 schema 均保留；独立 AST 验证只有该数据库断言改变。新 reviewer DB 另有通用 exact run_id/loopback/测试用户/端口护栏，非 test DSN 等11个隔离负例通过。

## 真实复跑证据

新 run：[recovery_r06_failed_response_review_1_recheck_20261016](../../runs/recovery_r06_failed_response_review_1_recheck_20261016)。同名 JSON 保存完整 argv、cwd、实际 +08 起止、exit 和 b781 HEAD；pytest log/XML 保存原输出和计数。所有 pytest cwd 为本树 backend，带 `--no-cov -q --tb=short --junitxml=<run>/<label>.xml`。新本树 `.venv` 为 CPython3.12.13，offline frozen semantic sync exit0、92 packages；sync.json/log 捕获真实命令和起止，未联网下载。

| label / 核心命令 | 实际结果 |
|---|---|
| pg_original33：`python -m pytest tests/integration/test_r06_source_worker_pg.py` | exit0，33 passed，33.97s，0skip |
| pg_new43：`python -m pytest tests/integration/test_r06_failed_response_persistence_pg.py` | exit0，43 passed，38.36s，0skip |
| pg_r04_19：`python -m pytest tests/integration/test_r04_source_jobs_pg.py` | exit0，19 passed，61.38s，0skip |
| pg_independent17：`pytest -p tests.conftest <run>/test_review_pg.py` | exit0，17 passed，20.37s，0skip |
| pure：原冻结12个相关 unit/contract 文件，完整名单见 pure.json | exit0，568 passed，5.68s，0skip；1既有 Starlette deprecation warning |
| isolation_guard：`tests/contract/test_r01_quality_checks.py -k 'unsafe_test_database or isolated_database_accepts or ci_flag'` | exit0，11 passed/23 deselected，0skip |
| collect_r06：原33 + 新43两文件 `--collect-only` | exit0，76 collected，0.48s；不计业务通过数 |
| mypy：`python -m mypy src migrations/versions/0016_source_response_receipts.py` | exit0，96 source files |
| ruff / formatting：9个业务/公共依赖/直接测试文件 | 各exit0；检查通过、9 files already formatted；完整名单见JSON |
| material_audit：旧87、新32+manifest、原场景AST与fixture核验 | exit0；计数、SHA、字节与case身份一致 |
| 独立CBM index/schema/5条qualified both trace + rg callers | 各exit0；索引1265 nodes/6403 edges，0 skipped/partial/unusable |

四批 PG 顺序执行，只用 `test_dianzi_r06_catalog_failure_review_fix1_20261016`，run_id=`r06_catalog_failure_review_fix1_20261016`，不共享作者 fix1、旧作者、首次 reviewer 或原 hardcoded worker 库。DSN 从获准 WSL Ubuntu-22.04 -u root private connection.json capture 到内存，不打印或写 argv/材料；每批 public_before/public_after 均[]，每例独立 UUID schema，只清理自己的 schema。未新建 daemon、未修改共享/生产/collector 库，未 downgrade。

真实迁移随 PG fixture 从空 UUID schema 执行到0016；新43中的 table/model/FK/constraint 检查与新 Python 进程 PG+local raw 读回实际通过，migration 本身另被 mypy 检查。坏XML/JSON/AVID、无body/HTTP200空bytes、store和receipt INSERT失败、主业务回滚不推进cursor、GC、幂等并发、租约/授权/重处理测试仍通过。

独立17复用首次 reviewer 自拟仪器的正确版本，仅从新WT模块读取fixture和本专库；覆盖假job、错jobtype/source/stream、未来/越过payload窗口、更早冻结窗口、正常九源收据与业务回滚无text_blocks/continuation。首次仪器误判 retry outbox 的16/1红与原始源仍在dcfcab9中，本轮不重写；正确期待仍要求两条outbox均指向原job。

CBM 使用新 src-only root/cache/project，qualified trace 覆盖 build_source_page_handler、_fetch_catalog_page、execute_job、SourceResponseRecorder.record_response、register_response_content。rg 和源码交叉确认真实 runtime.py:100/:131、source_polling.py:129、source_routes.py:170/:198 的调用链仍有效；嵌套handler和回调边不能只靠graph证明，已用源码补证。响应独立PG事务仍先核已提交 job context、内容锁/store核验/receipt commit，再解析；原业务事务仍单独控制文档/游标/continuation，normalized仍不表示任务成功。fix1 未更改这些代码。

## 原字节、范围与八层

旧材料以9eb固定 Git blob为准，manifest86条目+manifest自身共87：87/87原作者bytes、大小和manifest一致；旧manifest本体SHA256=`c1e27d18e97ae718b8244446bd08ba488ac67fa5b2356706ca620260c84f8e3f`。fix1以b781固定blob为准，manifest32条目+自身33：33/33一致；新manifest本体SHA256=`cf585ab7063ffda419532951e903259d6bb1a2fca579b41edd0bda0e108dd1d4`，与root给定值相符。分列old87_bytes.json和fix33_bytes.json，旧27/6红及作者fix1首条错误mypy调用均保留。

本reviewer checkout旧材料21处、新材料1处与blob的换行差异按每文件hash/CRLF数单列，不判为篡改，不normalize原日志。作者.gitattributes新增3条仅针对fix1 run保留raw bytes和log/xml显示边界；不是全局禁检查。产品测试与.gitattributes的 `git diff --check 9eb HEAD` exit0。本 reviewer 新run用core.autocrlf=false stage并逐字节验证；新manifest本体hash在最终交付返回，root可对本run增加精确 -text 属性。

| 层 | 限定结论 |
|---|---|
| unit | 相关568组合中的unit passed；完整项目unit/覆盖率 not_run |
| contract | 相关纯合同、隔离11及PG模型/迁移定向passed；不签全部合同层 |
| integration | 原33、新43、R04 19、自拟17 PG+local store定向passed；完整integration/统一CI not_run，首次R05 collection缺口未关闭 |
| security | 授权/假context/秘密metadata/资源隔离负例passed；完整security suite not_run |
| frontend | not_run；未改变前端API/UI合同 |
| e2e | not_run；未启动默认API/Celery/beat/浏览器端到端 |
| live | not_run；真实MinIO、默认真实来源入口、外部九源/八类、告警与持续窗口缺口保留 |
| manual | not_run；没有人工裁决、正式评分或整卡验收 |

0新外网/模型/测绘/资产/PoC/付费请求，provider/DPAPI秘密读取0；只有获准测试连接在内存中使用，秘密扫描结果见最终收据。E1/F1/R1、T08/T16/T49仅登记失败原文留证与回归合同完整性证据；来源真实覆盖、漏采参考集合、时间统计、T08/T49原六案例、告警解除/费用unknown和长期监控要求完整保留。

下一建议：root可集成本失败留证切片及合法回归同步，再安排真实MinIO、默认入口和受限管理员收据读层；本意见不扩大为整R06/G-C签字。

Verdict: **Ship（限定上述切片）。** Not checked: 全项目八层/覆盖、统一CI、真实MinIO和默认live入口、外部长期窗口、前端端到端与人工验收。
