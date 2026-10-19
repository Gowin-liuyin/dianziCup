# G-C · 集成 8a1b04d 独立回归验证

What this change does: The frozen tree combines reviewed source failure receipts, typed enrichment candidates, shared generation timeout handling, event detail UI, process startup guards and exact version comparison. This report verifies the combined tree and keeps its failed checks visible.

任务状态：`awaiting_review`。本轮为非作者、独立集成验证，**不是 G-C 最终阶段放行**，不登记 accepted。结论：完整回归仍失败，R20 四个产品红例未关闭；其他限定检查如下。只新增本报告及 `reports/runs/recovery_gc_integrated_8a_validation_20261016/`，业务实现未修改。

## 固定身份、依据与权限

独立 detached 工作树：`D:/wt/gc-8a-validation`；HEAD 始终 `8a1b04d48346d8550f0326a77f003246a0ebbab5`，tree `c614a6cb784c8fab422a14479d14ea4b6303493c`。创建后初始 tracked/untracked clean；结束 tracked diff 空。主工作树 `D:/dianzi` 有用户与其他任务未提交材料，本 reviewer 全程未写入。没有 spawn、commit、push、accepted 或状态文件修改。

采用 Ponytail review 5.2.0。已读 AGENTS、00 执行图、恢复 11/12 的 G-C 和 R04/R05/R06/R07/R11/R17/R20 卡、03/05/06 合同、固定 task_state/交接及本批四份新 CR；读取 canonical 独立报告：R06 failed-response fix1、R07 core v2/public-signals/model-fields recheck、R05 predispatch、R11 version-ranges recheck、R17 event-detail recheck、R20 startup review。报告中的 limited Ship 均未扩大为整卡或阶段验收。

`component_source_identity.json` 对 14 个关键文件逐一比较集成 HEAD 与 b781/cb340/facf/ef247/df0fa/647/535/8f5 的 Git blob，14/14 精确相同，含已修正 0016 迁移。checkout CRLF raw SHA 和 Git blob SHA 分列，未把换行差异当内容漂移。最后 `runtime_identity.json` 在清除 PYTHONPATH 的新子进程中核对六个实际 module.__file__ 均位于本 WT 的 backend/src，未借用主目录/作者业务模块。

输入限固定源码、原测试和显式合成/公开录制 fixtures；输出是原日志、JUnit、coverage、隔离数据库观察、源身份和本报告。不读 gold/holdout、DPAPI、provider 密钥或真实资产；无真实来源、模型、测绘或付费调用。唯一私有配置读取为主控授权的 WSL 测试连接，捕获到内存后只建立本专库 DSN，不输出值、写入 argv 或材料。

## 环境与真实命令

所有时间均为 2026-10-16、Asia/Shanghai (+08:00)。每条 `<label>.command.json` 保存完整 argv、cwd、起止、exit、HEAD/tree；同名 stdout/stderr 原字节保存。表中简写 `R` 指本 run 绝对目录，`B` 指本 WT/backend，`F` 指本 WT/frontend；实际参数没有省略，详见 receipts 与 `command_index.json`。

自有 Python 3.12.13。初次 `uv sync --offline --locked --all-extras --no-install-project --project backend` 在 02:53:39–02:53:45 exit0，resolved93/installed92；这是依赖环境，尚未安装本项目。主控授权修正后，02:59:05–02:59:07 `uv sync --offline --locked --all-extras --project backend` exit0，离线构建并安装本 WT editable 项目，未改 lock。实测 pytest8.4.2/pytest-cov6.3.0/coverage7.16.2、semver3.1.0/packaging26.3、SQLAlchemy2.1.1/psycopg3.3.6、Ruff0.16.9/mypy1.20.2/pypdf6.20.1。Node24.13.1/npm11.8.0；02:54:59–02:55:08 在 F 执行自有 `npm ci --offline --no-audit --no-fund` exit0，未改主 node_modules。

| label / cwd | 实际核心命令 | +08 起止 | exit / 结果 |
|---|---|---|---|
| backend_full_pure_actual / B | `.venv/Scripts/python.exe -m pytest tests/unit tests/contract tests/security -m "not real_pg" -q -p no:cacheprovider --basetemp R/backend_pytest_tmp --junitxml R/backend_full_pure.xml --cov-report xml:R/backend_coverage.xml` | 02:54:31.640638–02:57:02.960335 | **1；2489 passed / 11 failed / 10 deselected / 0 errors/skips**；pytest143.38s；coverage77.22%，原60%门通过 |
| privacy_environment_recheck / B | 原失败的质量隐私1、动态隐私3、TLS隐私2、仓库扫描1，精确4个 node 表达式收集7例；`--no-cov -q -p no:cacheprovider --basetemp D:/wt/gc-8a-validation-tmp/privacy_recheck --junitxml R/privacy_environment_recheck.xml` | 03:00:08.509774–03:00:53.126034 | 0；7 passed，0 error/skip；41.23s。只修自有环境，不替代首次完整回归结果 |
| pg_selected_actual / B | `pytest` 下文6文件，`--no-cov -q --tb=short -p no:cacheprovider --basetemp R/pg_pytest_tmp --junitxml R/pg_selected.xml` | 02:57:44.098068–03:00:47.906514 | 0；136 passed，0 error/skip；179.95s |
| shared_generation_boundary / B | `pytest R/test_shared_generation_boundary.py --no-cov -q -p no:cacheprovider --basetemp D:/wt/gc-8a-validation-tmp/generation_boundary --junitxml R/shared_generation_boundary.xml` | 03:04:04.672669–03:04:07.204521 | 0；4 passed，0 error/skip；0.61s |
| backend_ruff / B | `python -m ruff check src tests` | 02:58:08–02:58:08 | 0 |
| backend_format / B | `python -m ruff format --check src tests` | 02:58:09–02:58:09 | 0；264 files |
| backend_mypy / B | `python -m mypy src --cache-dir R/mypy_cache` | 02:58:09–02:58:23 | 0；106 source files |
| frontend_unit / F | `node node_modules/vitest/vitest.mjs run --reporter=default --reporter=junit --outputFile.junit=R/frontend_unit.xml` | 02:58:08–02:58:37 | 0；25文件/352 passed，0 fail/skip |
| frontend_typecheck / F | `node <npm-cli.js> run typecheck` | 02:58:37–02:58:40 | 0 |
| frontend_lint / F | `node <npm-cli.js> run lint` | 02:58:40–02:58:46 | 0 |
| frontend_build / F | `node <npm-cli.js> run build -- --outDir R/frontend_dist` | 02:58:46–02:58:50 | 0；53 modules，JS267.89kB、CSS37.79kB |
| event_fixture_browser / WT | `node frontend/node_modules/@playwright/test/cli.js test --config R/event_fixture.config.mjs` | 03:01:16.012107–03:01:23.409805 | 0；**3 passed**，0 fail/skip，6.6s；fixture browser，不计live |

完整回归按 JUnit 分层：unit **1888 pass/4 fail**；contract **341 pass/1 fail**；security **260 pass/6 fail**。总数2500实际执行，另10 real_pg deselected；不把 deselection 当 skip 或通过。只有这一轮完整回归，未进行碰巧转绿的 full 重试。完整命令未使用 `--no-cov`、改 addopts 或改原 CPU 断言；后续限定 PG/隐私/跨调用方测试显式 no-cov，不声称它们重新通过整体覆盖门。

完整套件三条 warning 为既有 Starlette/httpx deprecation 及两个 PDF worker runpy 预导入 warning，原输出保留。它们未当作 skip 或伪造成功。

## Must fix

1. **R20 原 Windows 进程门仍有四个实际失败**（`backend/tests/unit/test_r20_native_cpu_guard.py:86/143/154`；产品 `backend/src/ai_intel/infrastructure/process_limits.py:157`）。
   - **What this is:** 受限 worker 应保留短 CPU 任务结果，在 guardian 硬退出时清理进程树，并满足原累计 kernel+user CPU `<1s` 断言。
   - **Problem:** short task 返回3221225540且 stdout为空；python-gil-held 未产生 TREE；native-gil-held-idle 实测 `(5781250+4218750)/10000000 = 1.0s`；native-cpu 为 `(6093750+7031250)/10000000 = 1.3125s`，两者均不满足 `<1s`。未测得短任务的独立启动CPU，故不从空stdout推断其精确耗尽时点。
   - **Fix:** 交主控安排原边界的独立根因诊断与受控早期启动/监督接缝修复；保留原累计口径、就绪/wall门和全部原测试。本轮只读，不为此扩大补丁或提出未经验证的内核保证。
   - **If we skip it:** 正常短任务可丢结果，且硬退出场景超过原限额。R20/完整回归不能登记 passed。535 限定 startup Ship 与新五例通过不关闭这些旧门。

## 首次另外七红：验证环境原因与有界复核

首次未安装 editable 项目；六个嵌套隐私例自行改写 PYTHONPATH 后，子 pytest 未形成预期 JUnit（contract为缺 failure.xml；security为内存JUnit marker不存在），不能算已验证秘密脱敏行为。最小环境修复是按原锁离线安装本项目，不改原测试、conftest、插件或预期。新子进程实际 module 路径已另核，而非仅依赖父 PYTHONPATH。

第七例的全仓扫描命中本 reviewer 错置于 reports 的 pytest 临时合成凭据夹具。原目录在03:00:08.3706275完整 Move-Item 至 `D:/wt/gc-8a-validation-tmp/backend_pytest_tmp`；移动前解析/等值核对明确绝对源目标，并逐文件核 SHA/数量，`temp_relocation.json`保留原/新位置及所有字节身份。没有删文件、分类豁免或改扫描器。`temporary_scan_findings_paths_only.json`只列旧 path/pattern/count/合成原因，不打印匹配值；它是诊断清单，不是扫描allowlist。主控后来的命名建议未倒填成已发生位置。

随后只重跑原七节点，7/7通过；原完整11红和其JUnit不覆盖、不删除，不改总分母为2496绿或宣称全套已通过。PG临时目录在全部用例结束后另完整迁往同一自有仓外目录，`pg_temp_relocation.json`逐文件核验；先前因子Windows PowerShell缺 Get-FileHash 的启动失败发生在Move前，原 exit1/log/脚本快照保留，换自有.NET哈希仪器后成功。没有再次运行产品测试。

最初 generic runner 把位置后的 `--cwd` 当命令，WinError2、0测试；receipt缺结束时点，未补造。真实测试只以 `_actual` receipt/JUnit计数。首次 CBM schema 少 project exit1也保留，按真实help补参数后成功。初次 `^{tree}` 被PowerShell误解析的只读命令错误亦未当身份结果；最终身份用 `git show --format=%T` 与实际模块复核。以上均是仪器问题，不是产品通过或产品业务失败。

## 真实 PG 的限定行为

先读六文件及其引用 fixture：catalog/worker 是专用库前缀+UUID schema；R04引用 `empty_schema_engine`，实际校验 current_database/current_user，逐例建/清自己UUID schema；R07复用 catalog fixture。均无破坏性 downgrade。未运行包含其他旧硬编码 dev DSN 的全 integration。

专库 `test_dianzi_r06_catalog_gc_8a_20261016`，run_id `r06_catalog_gc_8a_20261016`。从授权 WSL Ubuntu-22.04/root 的 test-services/connection.json private capture 到内存；只在 postgres目录库核身份并创建该确切新库。调用原 `require_isolated_test_database`，保持 exact run_id、loopback、显式端口、test用户和密码护栏。未连接 G-B/root collector/R07 reviewer 业务库，未创建 daemon、重启共享服务或降级迁移。

| 原文件 | 实际 passed |
|---|---:|
| test_r06_source_worker_pg.py | 33 |
| test_r06_failed_response_persistence_pg.py | 43 |
| test_r06_catalog_documents_pg.py | 21 |
| test_r04_source_jobs_pg.py | 19 |
| test_r07_signal_claim_values_pg.py | 13 |
| test_r07_literature_target_scope_pg.py | 7 |

全部136例为真实PG、离线来源输入/local content store；0fail/error/skip。实际0016升级、表/约束、失败raw留证、业务回滚无游标推进、重复/并发、重读、GC、typed值、公共文献内嵌私有目标拒绝等原断言保留。`pg_isolation_before/after.json`显示 public表始终[]、最终UUID schema[]，实际身份检查未替换成fixture真假值。原测试子进程DSN只经环境传递；日志/JUnit沿原脱敏hook，外层再针对已获准测试连接值核验，不记录值。费用/外部能力仍unknown/not_run。

## 调用链、共享超时与产品缺口

先实际运行官方 CBM0.11.0 help；独立缓存 `/tmp/dianzi-cbm-gc-integrated-8a-validation-20261016`，只允许本WT/backend/src，fast/persistence=false。src索引1409节点/7128边，not_indexed/skipped/partial/unusable均0；默认排除assets和__pycache__，不称全仓图。随后真实schema/architecture和 qualified traces覆盖runtime.consume_job、source handler、record_response、GenerationClient.generate、generate_model_field_attempts、enrich_structured_fields；另在实际assessment与assets目录单独索引，分别34/81和76/243，并 trace version assertion、Hunter/Quake collect。未索引reports、秘密、gold或holdout，未采纳ADR写入建议。

源码 rg 与 OpenAPI共同核对，不以无图边证明无产品路径：runtime.py:100建固定handler、:131 consume_job调execute_job；source_jobs.py:445创建recorder，嵌套record_response :456委派独立收据，:512把回调交_fetch_catalog_page，在parse前先留证。CBM对嵌套函数只解析到file节点，故由实际源码和136 PG补足。收据normalized仍不表示文档/任务成功，原事务/权限边界保留。

GenerationClient.generate 的 inbound实际包括 grounding.generate_grounded_answer和model_fields._generate_field，再上溯QA service和字段入口。现行共享预派发 `remaining_seconds` 异常在generation.py:409–413变为固定GenerationFailure(model_network_timeout)，QA grounding.py:261–262保留attempts并传播，service.py:346继续记录typed失败。完整套件的原17个predispatch测试全部通过；本run新增4provider×R07真实 `_generate_field→GenerationClient.generate` 到期负例也通过，精确FAILED/model_network_timeout、空候选/metadata、0DNS/POST、slot可复用。不是替换generate的mock，不使用真实key或供应商。最初BareNetworkTimeout没有在集成8a这条候选传播路径重新泄出，未知/失败未变成空成功。

`source_callers`遍历全部backend/src与frontend/src，结合默认app装配源码和无依赖连接生成的16个 `/v1` OpenAPI paths，确认R07 structured/model候选、R11 assertion comparator、R08 aggregate connector当前仍无新的生产consumer/发布API。默认API已有event/document/evidence/question和source collect路由，不能从“候选零inbound”否认既有R04/R06/QA真实路径。此次未验证九维PG生产worker/自动富化发布、真实taxonomy加载/语义支持、版本OSV→typed证据→资产/条件/四态→OpenVEX、aggregate provider到UI等最终链路。这些是原限定组件尚未完成的产品范围，不包装成新已修复缺陷。

## 前端与浏览器边界

自有完整352 frontend测试/type/lint/build通过。build自动写本WT的tracked tsbuildinfo；生成字节保存为run内bin，随后只将这一生成缓存恢复HEAD Git blob，`tsbuildinfo_restore.json`记录两SHA和恢复时刻；业务/测试/lock未改。

先向主控报告并获准Vite+Edge、独占loopback25486、单worker、90秒总/30秒每例、白名单fixture、无trace/video。当前冻结 `r17_event_detail_fixture.spec.ts`实际只有3例：1366/390原历史引用键盘流及503局部失败。计划中沿canonical组合口述7的数量在真实collection后纠正为3，未追加别的文件凑7。三例0fail/skip/flaky；JSON/JUnit和9张截图保存。view_image实际查看390按钮和1366详情截图，可见fixture/过期标识、维度状态与40/44px按钮原测试仍通过；不推定完整可访问性认证。结束25486无listener，未复用root API或已有用户浏览器。

## 八层状态、评分边界与交接

| 层 | 本轮结论 |
|---|---|
| unit | **failed**；1888/4完整层结果，R20四红未关闭；新增R07共享超时4仅限定passed |
| contract | 首完整341/1；editable修复后原1节点passed，其他原结果保留；未重跑全contract |
| security | 首完整260/6；自有tmp/editable修复后原6节点passed；未重跑完整security，不能覆盖首次原红 |
| integration | 选定真实PG136 passed；完整integration/真实worker/API/MinIO未跑 |
| frontend | 352单元/type/lint/build passed |
| e2e | 事件详情fixture3 passed；真实backend完整e2e **not_run** |
| live | **not_run**；0真实来源/provider/model/测绘/资产/PoC；外部真实能力不计通过 |
| manual | **not_run**；无人工金标/法规裁决/终验；截图只作本次视觉观察 |

F1/E1/R1的失败来源留证与事务回滚、F2的typed权限/未知边界、F3共享模型故障传播、D2事件详情fixture有本轮局部证据；不从这些计出覆盖率、95%准确率/召回、吞吐或连续时长。P1/E1仍受原CPU失败约束。整R06/R07/R11/R17/R20、原T六验收、G-C门、性能和正式评分均不由本报告验收。

无业务合同/计划变动；实际执行偏差为上述自有环境、仪器和fixture计数，更正及原失败均保留。外部缺失与未执行不写成业务失败，业务红也不伪装环境阻塞。

封存：`artifact_manifest.json`列本报告与run各实际文件raw SHA256/bytes，缓存/temp单独说明，仓外tmp补充清单另存；`raw_attributes.txt`给主控精确文件 -text 建议，reviewer未改根.gitattributes。manifest本体SHA见 `artifact_manifest.sha256`，seal独立引用本体，避免循环自引用。完整raw日志、JUnit、coverage数据库/XML、命令和首次红均保留。

下一任务建议：主控保留此次完整回归failed，针对R20四红授权独立诊断/最小修复；修复后由新冻结安排有界独立回归。继续R07等生产接线时按能力DAG和阶段门执行。本 reviewer到此停止，不签阶段、不越权改进度。

Verdict: fix 1 first. Not checked: whole G-C acceptance, real model/source/provider runtime, full integration/security rerun after the environment correction, true product e2e/live, performance and human acceptance.
