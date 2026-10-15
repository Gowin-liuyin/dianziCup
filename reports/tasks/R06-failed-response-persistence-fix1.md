# R06 · 失败留证首次评审 Must 1 修复

状态 awaiting_review；本回归合同同步切片 complete，未经原独立 reviewer 定向复核不登记 accepted。固定前版材料 9eb01d7ba843116122a9a2462f3b74a2626cc48c，首次评审 G-C-R06-failed-response-review-1.md / dcfcab9 的 needs_changes 原意见保留。继续原工作树 D:/wt/r06-failed-response-persistence / codex/r06-failed-response-persistence，没有 spawn、push 或全局 state 修改。

本次先冻结代码 e1bae9db650df7946417cf42ec3817484514483a，再在该 SHA 上执行验收；每条 run JSON 保存实际 +08 起止、cwd、完整 argv、exit、code_sha 与源码字节 hash。报告实际创建时间2026-10-16T01:30:51.474039+08:00，封存时刻以新 run artifact_manifest.frozen_at 为准，不用计划时刻代替实际记录。

## 问题、修复与文件

原 test_r06_source_worker_pg.py 的九个失败场景将 content_objects 全部要求0，与已批准 CR-R06_failed_response_receipts 的独立 raw 保留合同冲突；新增 legacy wrapper 又将这些旧断言重复收集到常规 integration 入口。首次作者与独立 reviewer 的27/6红，以及新增43绿，全部留在原冻结材料，不能以新日志覆盖。

本次只同步原 test_catalog_failure_never_publishes_partial_page_or_cursor。storage、second_document、cursor_commit、continuation、invalid_page、blob_corrupt、blob_limit、wrong_type、timeout 九个 case 身份、原触发输入和 outcome 期待均保留，其余24个原场景不删不改。文档、revision、evidence、fetch_attempts、source_page_receipts、source_cursors 仍0，job_runs仍1；增加 text_blocks/claims/events为0、PG job error/attempt 精确值，以及 outbox 只指向原任务且数量严格等于原投递加合法 retry，不允许 continuation job。

仅六个已批准有 raw 的场景改原文期待：content_objects hash 集合严格等于该 job/attempt 的 receipt 引用集合，并再与固定输入原始 bytes 的预期 SHA 集合相等。每个 ordinal、HTTP、parse_outcome/error_code、hash/size、ContentStorage 字节读回精确核对。AVID tree 与坏 blob 分开；限流第二响应无伪 body。storage/wrong_type/timeout 无 raw 的原 count==0 断言明确保留，无 >=、xfail、skip 或放宽失败门槛。

删除 backend/tests/integration/test_r06_failed_response_legacy_pg.py 的重复导出文件。原33个用例现在只在原入口实际执行，新 test_r06_failed_response_persistence_pg.py 的43个用例保持原实现；本次 collection 为原33+新43=76，不再为109。没有用新的 wrapper 替代原入口。

原 catalog_worker_engine 的 hardcoded exact 旧库名阻止新独立库执行，主控明确批准将唯一断言改为 database 非空且 startswith("test_dianzi_r06_catalog_")，与已有 catalog_engine 受控 test 前缀一致。current_database==url.database、UUID schema、search_path、statement/lock/connect timeout、迁移 namespace 和只清理自有 schema 护栏全部保留。本作者实际只使用 test_dianzi_r06_catalog_failure_receipt_fix1_20261016 / run_id=r06_catalog_failure_receipt_fix1_20261016；通用 require_isolated_test_database 仍要求 exact run_id 库名、loopback、测试用户和独立端口，非 test DSN 拒绝边界单独复跑。

改动文件：原 source_worker PG 测试；删除旧 wrapper；新 run_checks.py；.gitattributes 只增加 recovery_r06_failed_response_persistence_fix1_20261016 的 -text/CR-at-EOL 和 log/xml -diff 精确规则。其余新增仅本报告和新 run 的命令/日志/XML/JSON/封存脚本。业务、迁移、公共模型/合同、认证、设置、依赖、runtime/API/frontend、评分/金标/分母和 progress 未改。

## 冻结命令与结果

新证据目录 recovery_r06_failed_response_persistence_fix1_20261016；全部产品检查 cwd 为本树 backend，复用已安装92 packages、本树 CPython3.12.13/.venv，不重新 sync、下载或修改锁文件。pytest 各命令均附 --no-cov -q --tb=short --junitxml=<run>/<label>.xml，完整名单见同名 JSON。

| label / 核心命令 | 实际结果 |
|---|---|
| pg_original33：`python -m pytest tests/integration/test_r06_source_worker_pg.py` | exit0；33 passed，33.57s，0skip |
| pg_new43：`python -m pytest tests/integration/test_r06_failed_response_persistence_pg.py` | exit0；43 passed，36.45s，0skip |
| pg_r04_19：`python -m pytest tests/integration/test_r04_source_jobs_pg.py` | exit0；19 passed，38.72s，0skip |
| pure_frozen：原冻结12个相关 unit/contract 文件 | exit0；568 passed，4.08s，0skip；1既有 Starlette deprecation warning |
| isolation_guard：原 test_r01_quality_checks.py 的 unsafe_test_database / isolated_database_accepts / ci_flag | exit0；11 passed、23 deselected，0skip；包括非test库/远端/错身份/默认端口拒绝，不回显synthetic凭据 |
| collect_r06：原 source_worker 与新43 PG文件 --collect-only | exit0；76 collected，不计业务通过数，无PG连接；删除wrapper后原33身份完整保留 |
| mypy_recheck：`python -m mypy src migrations/versions/0016_source_response_receipts.py` | exit0；96 source files |
| ruff / formatting：两个业务文件、四直接测试文件与新 runner | 各exit0；7文件检查/格式通过 |

最初 mypy 标签调用时少写实际模块名，完整 argv 是 python -m src migrations/versions/0016_source_response_receipts.py，exit1/No module named src.__main__；属于本作者调用仪器错误。原 mypy.log/json 保留，改正确命令后 mypy_recheck exit0，不计为业务失败，不修改类型门槛或源码。封存脚本初次手动Ruff两条长行输出已在工具记录，格式化后通过；没有冒充此前未捕获输出为封存日志。

PG三批同一新专库串行执行，避免不同schema共享 advisory lock 名称的争用；每例仍UUID隔离，各run public_before/public_after均[]。DSN只从获准 WSL private test-services/connection.json capture到内存，未进入 argv、报告或前端；不连接原旧worker专库、前次作者/评审专库或生产库，不启动daemon，不 downgrade。0新外网、模型、资产查询/扫描、PoC、付费或 provider 秘密读取。

## 原字节、层级与交接

历史审计将原作者 manifest 的86条目加 manifest 本身共87文件逐个与9eb固定 Git blob核对；本次不改历史 report/log/XML/manifest。新目录使用限定 -text 属性保全新原始 bytes；封存后逐 staged/blob hash复核，manifest本体SHA256随材料提交交付。secret_scan只比较获准runtime测试连接/口令，不读取provider秘密，命中计数以最终收据为准。

unit/contract：568相关用例passed；不是全项目覆盖率。integration：只上述原33+新43+原R04 19共95个PG+local store用例；整体integration目录/统一CI仍未运行，首次评审已记录的其他R05 collection缺口不由本修复关闭。security完整suite、frontend、e2e、live（含真实MinIO/外部九源/告警持续窗口）、manual均not_run；隔离资源边界11通过不冒充完整security。不存在新评分或连续运行分母。

生产调用方仍为 workers/runtime.py:100 handler注册/:131 execute_job，source_polling.py:129 enqueue，api/source_routes.py:170认证collect/:198 PG job读取，frontend source-client.ts:5与source-workspace.tsx:80既有消费链。本次只改测试，不新增公开receipt读接口或更改结果语义；原arXiv失败bytes缺口与初次根因unknown保持，实际MinIO/默认进程端到端由主控后续验证。

E1/F1/R1与T08/T16/T49仅引用原文失败审计和回归合同完整性证据，不签原整卡或R06/G-C。下一步交原独立reviewer对e1bae9d及新材料定向复核唯一Must；本作者只提交awaiting_review候选，没有self-accept。
