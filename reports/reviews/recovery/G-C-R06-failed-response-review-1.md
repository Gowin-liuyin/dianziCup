# G-C · R06 失败响应留证首次独立评审

本变更行为：来源 HTTP200 的实际响应字节先写入内容存储并在独立 PostgreSQL 事务登记收据；随后解析、文档、游标和后续任务仍由原业务事务处理。解析或业务事务失败时，已提交原文保留；收据的 normalized 只说明解析完成，不表示任务成功或来源 live 已接通。

结论：**needs_changes，先修复问题 1。** 新接线和原文留证的定向检查通过，但原回归期待尚未按 CR 同步，提交中新增的 legacy wrapper 在常规 integration 收集中仍会产生六个失败。此意见只针对本失败留证切片，不签整 R06、G-C 或原 T08/T49 accepted。

评审记录时刻：2026-10-16T01:15:21+08:00；最终封存实际时刻见本 run 的 artifact_manifest.json。新非作者评审，未 spawn。独立工作树 `D:/wt/r06-failed-response-review-1`，分支 `codex/r06-failed-response-review-1`，产品固定 `9eb01d7ba843116122a9a2462f3b74a2626cc48c`；业务提交 `e192234550fdd1c405d165a7a93772a952b8ea5b`；基线 `c3a2abc9a5246993eabb351d26cfeb51d0270b31`。root 合同 `114c42d645e237e20c9812fcc79d63f0f2e96717` / `a2be6ef4ad6407897b68352300dadd101f247c21` 在固定树中的 cherry-pick 为 `10b9b5f825b028cf9da0eb2feadbec75bda71c11` / `33ff7bc16d0bb1f3fed4f1a9ee7ec9edf4dda2c8`。

读取 AGENTS、00 执行索引、12 的 R06、T08/T49、03/04/05/06、CR-R06_failed_response_receipts、作者 R06-failed-response-persistence.md、progress/task_state.json/交接，以及最新 Ponytail 5.2 review。Ponytail 只用于审查，不修改业务。主工作区现有未提交报告和状态未碰；本树仅新增本报告与独立 run，不改业务、公共合同、产品测试、阈值、金标、依赖或 state，无 push。

## Must fix

1. **合同已经改变，常规 integration 入口仍包含必红的旧断言。** 定位：`backend/tests/integration/test_r06_failed_response_legacy_pg.py:17` 导出旧测试函数；实际失败点为 `backend/tests/integration/test_r06_source_worker_pg.py:278` / `:283`。`.github/workflows/ci.yml:91` 调用 `scripts/dev.py check --scope integration`，`scripts/dev.py:162` 直接收集 `tests/integration`。

   - **职责：** 旧测试要求失败后文档与游标不发布。新 CR 要求相同失败后独立 raw/receipt 保留，因此六场景的 `content_objects == 0` 已不再是正确期待。
   - **问题与复现：** 在本专库运行原提交新增的 `pytest tests/integration/test_r06_failed_response_legacy_pg.py --no-cov -q --tb=short`，exit 1，27 passed / 6 failed；失败为 second_document、cursor_commit、continuation、invalid_page、blob_corrupt、blob_limit，全在旧 all-content-rollback 断言得到 1 或 2。独立 `--collect-only` 同时收集原文件、wrapper、新 PG 文件共 109 个用例，exit 0，确认 wrapper 的旧失败属于默认目录入口。新增六个 CR 对照通过不能使该入口通过。
   - **最小合法修复：** 经 root 的合同同步变更，更新原 `test_catalog_failure_never_publishes_partial_page_or_cursor` 的这六场景：文档、revision、evidence、fetch_attempts、source_page_receipts、source_cursors 仍为 0，job_runs 仍为 1；仅将 raw 对象期待改为与该 job/attempt 的 retained receipt hash 精确集合相等，并校验真实字节/hash/size、HTTP、ordinal、parse_outcome/error_code。storage/wrong_type/timeout 的无 raw 期待继续保留。保持原九个失败场景、原其余 24 个场景和 case 身份，直接复跑原 33 用例；然后去除 wrapper 的重复收集或将历史复现适配器留在 run 证据目录。原红日志和冻结 Git blob 完整保存；不得 xfail/skip、排除原难场景、只跑新六绿或用 wrapper 替代修正后的原入口。原 hardcoded 专库 fixture 与统一 CI 库的隔离路由由 root 单独协调，不能为此允许非 test 库或删除资源护栏。
   - **若不修：** 正确的新留证行为仍导致项目 integration 检查失败，无法形成可运行的回归合同，也不能用 43 新绿宣称相关回归已通过。复验须提供原 33、43 新 PG、R04 19、纯相关 568 的真实日志，并确认没有重复收集故意失败用例。

## 已核对的业务边界

CR 对六个旧期待的修订本身合理，不削减原强不变量。旧六场景的触发输入与新参数化对照相同；new 对照保留旧业务表零写、job count 与 blocked/retry_wait 期待，并增加 claims/events 零写、独立 receipt 数量、content_objects 精确 hash 集合与实际 store 读回。新增 raw/receipt 是失败审计，未进入成功 fetch/文档/来源覆盖/评分分母；它不推进 cursor、不修改历史 failed job。原三种无可保留字节场景仍按无对象处理。修 parser 后从 retained bytes 重处理而旧失败历史不改，已在真实 PG 复跑。

独立 CBM 只索引本树 `backend/src`，新 cache/project `dianzi-cbm-r06-failed-response-review-1` / `r06-failed-response-review-1-src`；index 为 1265 nodes / 6393 edges，0 skipped/partial/unusable，schema 成功。对 handler、_fetch_catalog_page、execute_job、SourceResponseRecorder.record_response/mark_outcome、register_response_content、cleanup_unreferenced_object 使用含项目前缀的 qualified name 双向 trace。工具不能索引嵌套 collect_page，search 返回 0；因此不能只凭 graph 断言闭环，已用独立 callers.log 和源码核对真实入口及嵌套闭包。

实际生产链为 `workers/runtime.py:100` 的 SOURCE_JOB_TYPE handler 注册与 `:131` execute_job，`source_polling.py:129` 的服务端轮询 enqueue，`api/source_routes.py:170` 的认证 collect 与 `:198` 的 PG job 读取。executor 先提交 claim，再以 FOR UPDATE 业务事务运行 handler；失败回滚业务后另开事务写有界重试。recorder 使用部署同一 Engine 的另一 Session，读取已提交 job/attempt/owner/public scope，再独立保存 raw 与 receipt；不依赖未提交 source/job FK，也不调用任意 URL/SQL/shell 工具。

记录器先核对 system_admin/public、真实 running job 类型、owner、attempt、lease 到期、payload source/stream/window。独立补充的假 job、错误 jobtype/source/stream、未来窗口、晚于 payload 窗口均拒绝且无 receipt/content_object；更早的恢复冻结窗口按原语义保留精确值。作者 owner/attempt/tenant/expired 四负例复跑通过。request/cursor 只持 SHA；上游 final_url/header/正文/身份/凭据不进入收据 metadata 或日志，body 只进入有界内容存储。

真实 PG 覆盖坏 XML/JSON、AVID tree/blob 分 ordinal、网络无 body、HTTP200 真空 body（空 hash/size 0）、对象写与读回失败、真实 INSERT CHECK false、业务 PG/OSError 回滚、重复/并发、失效 context、GC 拒删、数据库 nullable/check 三值逻辑、模型/迁移一致及新 Python 进程 PG+local store 重读。GC 仍先锁 hash、检查全部引用，再 DELETE-before-store；新 receipt FK 和新增引用计数拒绝清理失败留证。0016 只新增表/索引，downgrade 明确拒绝破坏审计历史。

独立正常九源检查确认每个真实 worker fixture 返回 succeeded/partial，receipt 为 normalized、固定来源/job、实际 hash/size；AVID 为两收据。独立业务 rollback 检查另验证 text_blocks 为 0、job 仅原任务；outbox 两条都指向原 job，分别为初始投递和失败后的合法 retry，没有 continuation job。

## 独立命令、退出码与计数

证据目录：[recovery_r06_failed_response_review_1_20261016](../../runs/recovery_r06_failed_response_review_1_20261016)。每条命令同名 JSON 保存完整 argv/cwd/实际上海起止/exit/fixed SHA，log 保留输出，pytest XML 保存计数。Python 为本树 offline frozen semantic 的 `.venv` CPython 3.12.13；uv sync exit 0 / 92 packages，初始 sync 的精确起止未捕获，不补造。pytest 以下均带 `--no-cov -q --tb=short --junitxml=<run>/<label>.xml`，不据此声称全局覆盖率通过。

| label / 核心命令，pytest cwd 均为本树 backend | 真实结果 |
|---|---|
| pg_new：`python -m pytest tests/integration/test_r06_failed_response_persistence_pg.py` | exit 0，43 passed / 0 skipped，41.79s；含原六场景新 CR 对照 |
| pure：12 个作者冻结的相关 unit/contract 文件，完整名单见 pure.json | exit 0，568 passed / 0 skipped，5.80s；1 既有 Starlette deprecation warning |
| pg_legacy：`python -m pytest tests/integration/test_r06_failed_response_legacy_pg.py` | exit 1，27 passed / 6 failed / 0 skipped，40.88s；原函数对象和原期待未改 |
| pg_r04：`python -m pytest tests/integration/test_r04_source_jobs_pg.py` | exit 0，19 passed / 0 skipped，42.84s |
| pg_independent：`pytest -p tests.conftest <run>/test_review_pg.py` | exit 1，16 passed / 1 failed，21.28s；评审仪器误把合法 retry outbox 当 continuation，见下段 |
| pg_independent_recheck：同独立检查文件 | exit 0，17 passed / 0 skipped，18.68s |
| mypy：`python -m mypy src migrations/versions/0016_source_response_receipts.py` | exit 0，96 source files |
| ruff / formatting：9 个产品/公共依赖/直接测试文件 | 各 exit 0，All checks passed / 9 already formatted；完整文件名单见 JSON |
| collect_r06：原 worker + legacy + new PG 三文件 `--collect-only` | exit 0，109 collected；无资源连接、无业务通过计数 |
| collect_integration：`pytest tests/integration --collect-only` | exit 2，546 collected / 1 collection error；既有 R05 `test_r05_generation` 导入缺口，非本 diff，不修、不计通过 |
| CBM index/schema/qualified traces 与 rg callers | 成功收据逐条封存；工具失败尝试也保留，见下段 |
| artifact_audit / original_bytes_audit_recheck | 各 exit 0，86/86 manifest 条目、87/87 原作者 bytes 对固定 Git blob 一致 |

专用 PG 仅 `test_dianzi_r06_catalog_failure_review_20261016`，run_id `r06_catalog_failure_review_20261016`。获准 WSL Ubuntu-22.04 -u root private connection.json 只 capture 到内存；不输出 DSN，不读取 provider/DPAPI。CREATE DATABASE 只在该新 test 库不存在时执行；每例 catalog UUID schema 或原 empty_schema fixture 隔离后清理自己的 schema，各 PG run public_before/public_after 均 []。未启动 daemon、未写共享/生产/旧 collector 库，未 downgrade，0 新外网/模型/测绘/付费/PoC 请求。

失败仪器全部保留：首次 qualified trace 缺项目前缀 exit 1；首次 search 用 `|` 经 WSL shell 解释 exit 127；collect_page qualified/search 无节点 exit 1/0，改用源码补证。首次独立 PG 的 outbox 期待错误，确认 `workers/jobs.py:303` 合法重试后，仅修评审自己的仪器为两条且均同原 job，初始源保存在 review_instrument_initial.py，原日志不改。首次 raw audit 遍历 run 目录得到 86，却错误要求 87，exit 1；第 87 是目录外任务报告，修为 manifest 86 条目加 manifest 自身后 87/87，初始脚本与日志保留。它们不算产品业务失败，也不能从最终绿覆盖初始失败。

作者历史失败单列核验：初迁移 26 setup errors 为 sa.Bigsa.Integer，固定 a2/33f 已修并由本轮真实迁移 + migration mypy 复验；schema 比较 1 fail 为 TIMESTAMP 时区编译仪器，现固定 dialect compile；旧 rate limits 无 bind 仪器 3 fail，仅新增两行 Mock 注入，原期待不改。作者所有初红/后绿原日志仍可从固定 blob 复现，不将环境/仪器错误冒充业务通过或业务错误。

## 原字节、八层状态与未检查

作者 manifest 有 86 条目，含目录外任务报告；加 manifest 自身为 87 个冻结材料。独立从原作者工作树读取原 bytes，与 `git show 9eb:<path>` 对照，87/87 完全一致。本评审 checkout 因 Git 换行设置有 21 个文件 bytes 不同；manifest 比较仍以 Git blob 和原作者 raw 为准，差异逐文件 size/hash/CRLF 数写入 original_bytes_comparison.json 与 author_manifest_audit.json。没有 normalize 原失败日志。代码/合同范围 `git diff --check c3a2abc HEAD -- backend/src backend/tests backend/migrations docs/decisions` exit 0；原始日志中的 CRLF/失败空格不据此抹平，root 集成需本 run 精确 -text 属性。

| 八层 | 本切片意见与边界 |
|---|---|
| unit | 本轮相关纯文件 passed；不是全部项目 unit/覆盖门 |
| contract | 本轮相关解析/边界/DB 模型合同 passed；旧六回归同步仍 needs_changes |
| integration | PG + local store 定向通过项如上；27/6 原回归与全目录 collection error 保持 failed，不能总体 passed |
| security | public 管理员/假 context/metadata 定向负例 passed；完整 security suite not_run |
| frontend | not_run；新 receipt 无公开 API/UI 字段，本轮仅源码核对既有消费链 |
| e2e | not_run；未默认启动 API/Celery/beat/浏览器或做新版本端到端 |
| live | not_run；真实 MinIO、新版本外部九源/八类、模型、告警与连续窗口均未运行 |
| manual | not_run；无人工裁决或正式评分验收 |

本轮新增文件仅报告与 run 脚本/仪器/log/JSON/XML/manifest；实际修改名单以最终 run manifest 和 Git staged list 为准。E1/F1/R1/T08/T16/T49 只对应原文失败可追溯、PG 权威、恢复与权限这部分证据；R06 各类真实入口、独立漏采参考集合、无/未来发布时间统计、持续监测，T08 C01–C06 全卡和 T49 告警/解除/费用 unknown 等原验收完整保留，不由本定向检查签通过。

下一任务建议：root 按 CR 同步原回归期待与 CI 隔离入口，冻结最小修复后请本 reviewer 定向复验；随后独立安排 MinIO、默认入口和管理员只读 receipt 展示。业务接线无需因本问题扩大重写。

Verdict: **needs_changes；先修复 1。** Not checked: 真实 MinIO、外部 live、完整项目八层回归/覆盖、默认进程端到端和人工验收。
