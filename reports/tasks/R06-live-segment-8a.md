# R06-live-segment-8a · 固定产品版本的真实采集启动段

本段状态 `needs_changes`；runtime bootstrap 实现 `complete`，来源首轮 integration/live `failed`，六小时观察 `not_run`。代码产品固定 `8a1b04d48346d8550f0326a77f003246a0ebbab5`，观察器脚本固定 `1c4cce9770bfa29d08728a0131f7fc7fe714f9bc`，观察器独立 checkout 为补材料提交 `b08824f738ca185776916ae02689d8507f956c5c`。三者不能混称产品版本。本报告不修改 progress，不签 accepted，不代表 R20 安全/恢复或阶段通过。

## 范围、输入输出和版本

执行者 `/root/r06_owned_six_hour_live_runtime_integration`。读取 AGENTS、执行图、task_state、R01/R03/R06/R20/R22 恢复卡、API 与测试合同、原 R01 recovery/owned stop、R06 integrated runtime/bootstrap 和 MinIO segment4，以及观察器独立复核。应用 Ponytail 5.2.0 的复用和最小自检要求。

仅新增本报告、`reports/runs/recovery_r06_live_segment_8a_20261016/` 和仓外 owned runtime/control。产品 worktree `D:/wt/r06-live-8a-20261016`、分支 `codex/r06-live-8a-20261016` 始终 clean、只读固定 8a；观察器 worktree `D:/wt/r06-live-observer-20261016` 保持原三脚本字节，原路径运行。gate 的 `product_root` 直接指定产品 worktree，没有 adapter、monkeypatch 或改产品源码。观察器 gate 与真实 live journal 在新 observer WT 原 reports/runs 路径，本报告 run 保存终态副本和哈希。

输入为独有 PG、同一授权 MinIO 身份/原对象目录、独有 Redis 前缀和原默认 source beat；输出为 PG 事实、原始对象、安全投影观察链、受控进程 start/end/guard 和真实失败材料。没有新模型/测绘/付费调用、PoC、扫描、发布、push、源码依赖变更、迁移回滚、flushDB 或卷删除。来源请求外部费用状态 `unknown`；不能把模型请求 0 写成全部网络费用已知为 0。

## 受控资源和实际生命周期

原 R01 daemon boot `8ee1634d-0b2e-4279-8426-2ae855e3b997`，本轮实际 `stop_owned.py --check` 匹配其 supervisor PID13/startticks/cgroup。原父级 8GiB/2CPU/2048pids 不变，截止 `2026-10-17T21:49:15+08:00`。专用 Docker CLI 使用原 portable、client-config 和 `unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock`，不用系统默认 Docker。

数据库仅新建 `test_dianzi_r06_catalog_live_8a_20261016`，forward upgrade 到实际版本名 `0016_source_response_receipts`；旧数据库只读登记 name/OID，不迁移或写入。Redis DB15 初始已有 2 键，全部保留；自有 prefix `r06-live-8a-20261016:` 初始 0 键，queue `r06_live_8a_20261016`，不覆盖旧键或 flush。PG 唯一任务真值，Celery 无结果 backend。

第一 MinIO 段 **03:46:10→03:50:09**，owned stop、exit0、无 OOM；监听 127.0.0.1:29400，保留原对象目录。Linux 独有 cgroup 512MiB、swap0、1CPU、128pids，真实 boot/PID/startticks/executable/cgroup 在 minio_start.json。API 28013、单 solo worker、原默认 beat、原字节 observer 的采集段 **03:47:57→03:50:08，共131秒**。原计划自动截止 **09:47:57**，没有达到。Windows Hidden launcher18960，实际 supervisor48020，记录 CreationTime/parent/command；继承 owned Job 512MiB/process、2GiB总、host CPU20%、1200累计CPU秒，结束前实际 CPU56.515625秒、峰值内存474279936B。

唯一真实调度器为默认 beat，source_polling_enabled=true；原九源，vLLM30分钟/其余60分钟、每轮5页和 PG 唯一3次重试不变。无 REST source submitter。单组件8MiB log、observer 1MiB snapshot/16MiB总持久门不变。监督心跳60秒；原 observer poll30秒及原默认 snapshot策略未改。

原1000守卫代码按 fetch_attempts计数，**不等同1000 wire HTTP保证**，此口径缺口已报告 root。固定source GET/POST均0 redirect、最多2请求/page、3attempt/job，因此 source HTTP 保守上界6/job；本段使用 Cloudflare DoH，A/AAAA各一次 HTTPS，resolver默认5 redirect，包含DoH时保守上界78/job。首次实际11jobs的全潜在上界858，实际 wire HTTP 数 `unknown`，9 response receipts与7fetch_attempts均不能作为全部交换数。未来第二段须另冻结明确wire budget与停止余量，不复用首段500job设置声称满足1000wire。

## 实际启动、首轮失败与保全

API `/v1/health/ready` 实际HTTP200，PG/cache/search/worker/scheduler全部 ready；MinIO `/minio/health/live` 实际HTTP200。认证用户已在新PG创建，但端到端 login/logout 验证位于九源首轮之后，因提前停止而 **not_run**；不能把预创建用户算认证流程通过。浏览器/frontend均 not_run。

默认 beat 实际创建9个 `source-poll-v1:` 根任务。停止时共有11source jobs：6succeeded、1blocked、1running、3queued；八源有实际响应收据，vLLM尚无收据。9条source_response_receipts包含AVID双响应；7fetch_attempts、6业务page receipts。停止后独立只读查询显示74文档、74修订、1266证据、81content objects。1266条证据全部核 block坐标与quote SHA256，0错误；不将此写成内容语义支持验证。归档 source_results 保留实际类别/原来源，不把失败或有原文但业务未提交的源涂绿。

watchdog触发对象为 `ollama_releases` job `5e3d6b02-67d2-4193-89cf-f1a1e4460c59`：03:49:31.837689开始，03:49:33.757975有HTTP200、616865B、normalized response receipt；03:50:08业务任务仍running。原 lease截止03:50:31.837689。35秒是本地监督器守卫，未更改或宣称官方验收门；事务未完成的精确原因交独立诊断。PG running/lease/历史收据未改，未用手工成功替代。首轮 verifier按规则 exit1，完整失败log/command receipt保留。

原观察器实际exit0，终态 `owned_supervisor_stop`；完整replay独立核六条链记录、record/state hash与end receipt成功。journal33521B、latest14096B、end601B；终态全部归档，原文件哈希见 terminal_seal_receipt.json。exit0只说明观察器正常收口，不能说明六小时通过。opaque after/page_token仅安全hash/长度，未输出raw操作token。原3h04m27或1156集成段未拼接。

时效按全部74已存修订原分母记录：publication unknown23、future0、older-than-six-hours51。已知发布时间51项的ingested_at差值P50 26011134.868409秒、P95 70456406.368409秒、max79481888.868409秒；这是首次历史目录发现，不是持续新发布时效或漏采率。独立参考集合/漏采分母not_run，不能宣称6小时目标。

## 诊断对象导出和后续准备

root追加指令后，仅MinIO只读诊断段 **03:54:15→03:55:02，47秒**、exit0/无OOM，真实boot/PID/startticks/cgroup先 `--check` 后写stoprequest。该段在新≤120秒指令到达前的配置deadline为1800秒；按新指令实际47秒关闭，原start/end未覆盖。没有API/worker/beat或新增source HTTP。

root指定的官方公开release原文经真实MinIO `read_verified`导出到仓外 `D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin`，检查绝对路径/非symlink、新建 `xb`，不覆盖用户文件。SHA256 `25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7`、616865B；正文不进repo/log/prompt。最小payload和公共来源receipt见release_export_receipt.json。其余80对象本轮全部MinIO read_verified **not_run**。

系统DNS只对七个固定注册域执行resolve，0HTTP：均返回非global地址，原网关会拒绝，不能切system绕校验。公开probe只记录hostname/count/global布尔，不输出秘密。第二采集段待独立诊断和root的有限guard/DoH预算冻结，不盲重跑同一根因；本段不续写。

## 真实命令和核验

完整operational command/start/end/exit见run内prepare/verify/diagnose/export/seal等receipt；主要前缀为自有离线环境 `D:/dianzi-runtime-cache/r06-live-8a-20261016/runtime_env/.venv/Scripts/python.exe -B`。

| 命令/检查 | 实际结果 |
|---|---|
| `uv sync --frozen --offline --no-config --no-python-downloads --no-install-project` 自有runtime_env | exit0，无依赖网络下载/共享venv修改 |
| 原 observer `observe.py` 缺gate | 实际exit1；追加完整main自检env访问0/engine调用0 |
| `launch.ps1 prepare` 首次/一次修正 | exit1/0；首次把空SecretStr误判非空，发生在DB创建前，原red保留；纠正只检查是否有值 |
| `launch.ps1 start` | Hidden launcher真实启动；后续start/heartbeat证明四组件活着 |
| `launch.ps1 verify` | exit1，九源收据未齐先触发running watchdog |
| `launch.ps1 diagnose` | exit0，真实PG read-only根因时间/状态/receipt |
| MinIO诊断 `stop_owned.py --check` / stop | exit0/0，boot/process/cgroup匹配后owned request |
| `launch.ps1 export` | exit0，真实MinIO hash/size读回和仓外新文件 |
| `launch.ps1 seal` | exit0，六条terminal链replay、1266坐标/hash、82文件已知secret值扫描0finding |
| `selfcheck.py` / final | exit0/0，missinggate完整main0env/0engine、固定blob/product clean、最终5实际source AST与本包语法 |
| operational Ruff `--select E9,F` 初始/final | exit1/0，两个unused import；追加delivery脚本又发现两项unused import，保留red并修正复跑；旧实际启动MinIO源码另存launched_minio_segment.py.txt |
| protected Docker IDs与closed-process检查 | 17容器/28镜像/20卷；本任务runtime匹配进程0，28013/29400 listener0，MinIO cgroup为空 |

仪器限制保留：新venv无psutil，启动前改用原Windows CIM读取CreationTime/parent/command，没有安装依赖；首次CBM trace错用qualified前缀，返回function not found，原raw留存，纠正后取得实际LSP链；首次复用R01 inventory函数缺其preparation_evidence输入而失败，改为专用CLI只读ID计数，不把首次算通过。完整产品pytest/contract/security/frontend/E2E不在本次执行，not_run；格式/mypy未执行，Ruff仅语法/未使用变量切片，不冒称全质量检查。

## 实际CBM和交接

官方0.11.0 CLI实际help/index-help/schema-help/schema查询与src-only fast索引，独有项目 `r06_live_8a_src_20261016`，1409nodes/7128edges，0skip/partial/unusable；默认assets目录排除，不声称它已索引。索引只读固定8a `backend/src`，生成的owned `.codebase-memory`经绝对路径验证移到仓外cache，不留产品diff；未索引reports/holdout/secret。真实qualifiedtrace从runtime.poll_due_public_sources→source_polling.enqueue_due_source_collections→source_jobs.enqueue_source_page→outbox.enqueue_job有LSP0.97；动态handler/worker/cursor persistence和observer PG read用固定源码AST/rg补证，不能将heuristic file/API caller当运行证明。

当前 **所有本任务采集/诊断服务已关闭**。原R01 daemon及根测试服务继续由root控制；不要用本任务stop脚本终止根daemon。采集段停止入口是本run `stop_owned.py --check`后 `stop_owned.py`，仅核Windows CreationTime/command再写owned request；已结束时必须拒绝。MinIO独立入口各段 `minio_stop_owned.py`/diag `stop_owned.py`，先核Linux boot/startticks/executable/cgroup。停止后的旧run禁止prepare/start重跑、observer有terminal不可续写。资源/data/旧receipt保留，不kill数字PID或flush全局。

下一步由root已派非作者离线重放该公开release对象和真实隔离PG，确认持久化耗时/lease/任务硬时间关系。guard或预算修改仅在新owned bootstrap、新run、独立审核后生效；新开始与初始历史计数分别记录。F1/P1/E1证据支持真实有界启动、失败保全和PG/原文可追溯，不支持来源全接通、六小时窗口、正式时效、完整安全或阶段accepted。
