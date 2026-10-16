# G-C / R07 source IO deadline · 新独立初审

报告写作开始：2026-10-17T06:03:35+08:00（实际 clock UTC 2026-10-16 22:03:35）。

本次变更行为：原文读取退出第一短事务后，以共同绝对 deadline 读取冻结原文，再进入第二短事务核身份、权限、版本、模式与完整指纹。Windows 固定 worker 和共享 CPU guard 改为 DETACHED_PROCESS；4096 字节私有 stdin、稳定 native handle 与失败 owner 保留共同约束清理。

结论：**LimitedShip，仅当前源码的本地 unit/contract/security 与共享原生调用回归切片**。本轮未复现业务代码 Must fix。PG、实际 MinIO、真实 held guardian/reader 故障和完整 CBM guest 资源证据尚未取得，不能验收整 R07、R14、T19/T20/T30/T31 或阶段门；状态保持 awaiting_review，完整验证 partial。

## 固定版本、依据与修改边界

- Source：`ab3869665b084a4a8674c9081c8eff7a731c01e9`，独立 WT `D:/wt/r07-io-review1`，branch `codex/r07-io-review1`。审查者未参与 source IO/native cleanup 实现。
- Material：`10ef32189a2f63010d4b70762b7f5cda3aad3e99`。合同基线 `8c48b61c02860166bdda0986e984058e8a824188`；WIP `4d85343a6117f1be215313aacd4652a554e334e4` / material `5a7fdf22ab22968637f685025b285ff143bfd7bf`；首 native fix `dc2925b1dce7d479c253d3b086d70e0901052e21` 均独立保留。
- 已读 AGENTS、执行地图、R07 卡、T19/T20/T30/T31、03/04/05 合同、task_state、作者最终报告、原证明桥及主仓库未提交的 [CR-R07_source_io_deadline](D:/dianzi/docs/decisions/CR-R07_source_io_deadline.md) 追加。使用 [Ponytail 5.3.1 review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md)。另委托未参与实现的只读子审核全部存储签名与共享 guard 调用链，未委托测试资源。
- 本轮只新建独立 review 报告、ownrun、两个 malformed native 负例与薄复跑入口。未修改业务、schema、依赖锁、state、auth、阈值、gold、分母、旧 oracle；未 push、未读 private/.env/holdout、未调用付费或实际来源接口。主仓库已有修改未覆盖。

## 字节、断言与批准范围核查

`prepare_review.py` 实际 exit0：从固定 material Git blob 读取 raw ZIP，亲核 **333371B / 172 members / SHA256 `14c3f91151e8d4f054e581c827d44d75ca1f4fdbe2ec47ccb26d40c158c32376`**，逐成员大小和 SHA256 全吻合。17 源码/测试 raw 与 reviewer checkout 仅行尾规范化差异；checkout 各文件实际 hash 单列，不伪称与 raw 字节相同。

`assertion_inventory.py` 实际 exit0：**494 原 assert / 17 比较 / changed0**。六个共享旧测试整个 Git blob 与基线相同：`test_r20_native_cpu_guard.py`、`test_r05_process_limits.py`、`test_r04_real_parsing.py`、`test_r05_semantic.py`、`test_r05_semantic_contract.py`、`test_r20_process_startup.py`。原 CPU 一秒门和原并发 oracle 未改。该清单明确 source IO 测试原断言比较版本为 dc292，其他直属测试为 8c48，M02 为原 raw；不将其说成所有断言都来自同一历史版本。

M02 原 **5097B / `cd9b913f169683ca19940cd60c480a1561cd93f73541f3a975581d9b08903ce4`** 与 adapted **5164B / `04472b763dcb4671ebdabdcc87386f31e09d2e0a6ee3bd38c1bdcc3ced6ea444`** 已亲核。adapted 只为 ObservedStore 增 optional keyword 与原样转发，assert AST 不变。两版均保存在 ownrun 根，642B 原 fixture 桥未改；**真实 PG 未复跑，两版都 not_run**。本轮未使用 test 硬编码 DSN 或作者旧 service 收据。

相对 4d/5a7，业务差异限定在 content worker/content_store 和共享 guard creationflag；相对 8c48 全部七业务/十直属测试符合批准 seam。共享 `process_limits.py:138` 唯一改动为 creationflags，handle_list、PIPE/DEVNULL、Job/no-breakaway、READY、guard lifecycle、CPU/memory、slot2 保持。`git diff --check` 对当前 backend 变更实际 exit0。

## 源码路径、触发与可观察结果

1. [content_store.py:181](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:181) 在 Popen 前拒绝完整 UTF-8 envelope 超过 4096B；[容量检查:146](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:146) 只用于 fresh sole-writer pipe。检查不可用或容量不足时不写 config，不把 GetNamedPipeInfo 当任意时点 free 容量证明。worker [58](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/_content_read_worker.py:58) 先读受限配置，guard 在 [66](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/_content_read_worker.py:66) 后启动。父 startup/communicate/清理均使用原 deadline，原 0.15s 断言独立通过。
2. [cleanup:247](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:247) 开始即登记 owner，独立处理 kill、wait、guardian、reader、stdin/stdout；[314](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:314) 仅完整清理后移除 owner/返 slot。[317](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:317) 给主异常加固定 note，保留原 Timeout/KeyboardInterrupt 对象；无主异常时传播 cleanup 的取消。外部原 36 取消负例独立通过，failure owner 的 process/native 可追踪；这些故障 API 是 mock，不能据此声称真实 held 故障已验。
3. [native owner:54](D:/wt/r07-io-review1/backend/src/ai_intel/infrastructure/content_store.py:54) 持 worker handle，等待 terminal 后以真实 birth/exit 限定直接 guardian；EOF、枚举/权限/query/Close 与不明身份分开。现有 mock 阴性覆盖与真实正常/Timeout/取消资源闭合通过；本轮没有人为造成真实 guardian 拒绝、hard-exit、held reader 或 held handle。
4. [reader:833](D:/wt/r07-io-review1/backend/src/ai_intel/knowledge/structured_fact_proofs.py:833) 第一围栏退出后，[877](D:/wt/r07-io-review1/backend/src/ai_intel/knowledge/structured_fact_proofs.py:877) 将同一绝对 deadline 传存储；[894](D:/wt/r07-io-review1/backend/src/ai_intel/knowledge/structured_fact_proofs.py:894) 最后锁输入并重核 mode/完整 fingerprint/Actor。R14 `workflow_service.py:1337` 到 `source_report_node.py:46` 不逐 ref 重置五秒。Missing、Timeout、read_failed、store_unavailable、invalid 保持分类，unknown/unverified 不升为 reported/Strong/QA 支持；真实 driver IDLE/ACL/source epoch 并发围栏仍待 PG 证明。

自建真实输入 `b'{"storage":"local",'` 与 `b'{"storage":"unknown"}'` 通过固定 native worker，均返回 ValueError，不返回成功或空原文；worker 终态闭合、failed owner 为空、两个容量 slot 可再次取得。未修改源 worker 或原断言。

## 自行执行命令、退出与计数

运行根 `D:/wt/r07-io-review1`。每条 receipt 保存完整 argv、backend cwd、真实时间、整数 child exit、source hashes、Windows PID/birth/parent、峰值和终态；raw stdout/stderr/XML 在 [ownrun](D:/wt/r07-io-review1/reports/runs/r07_source_io_deadline_review1_20261017)。实际 interpreter 为 `C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe`（下表记 P），已装依赖从原 venv site-packages 加入 PYTHONPATH。实际 pwsh login=false。APP_ENV=test/DATA_MODE=fixture，禁来源/生成，清除外部 test/service 凭据变量。

| 真命令（P + ownrun 入口） | exit / 实际结果 | Windows 完整树 / 限制 |
|---|---|---|
| `run_native_review.py review_native_source` | **2**，collection1error；自建参数误名 request（pytest 保留名），未启动 worker；已更名，原红保留 | peak4 / residual0 |
| `run_native_review.py review_native_source_retry1` | **0 / 75 passed / 27.13s**，原73+自建2 | peak8 / residual0，slot2 returned / failedowners=[] |
| `run_native_review.py review_native_shared` | **0 / 32 passed / 15.25s**，当前 ab386 重跑 | peak8 / residual0 |
| `run_native_review.py review_native_callers` | **0 / 99 passed / 4.99s**，2 个 runpy import RuntimeWarning 原样保留 | peak7 / residual0 |
| `run_native_review.py review_direct_storage` | **0 / 71 passed / 1.95s** | peak6 / residual0，slot2 returned |
| `run_pure_review.py frozen_combined_review1` | **0 / 658 passed / 15.56s**，658 actual distinct / duplicates0 | peak6 / residual0 |
| `checks.py review_cleanup_cancel36 -m pytest <ownrun>/test_cleanup_cancel_red.py -q --no-cov --junitxml=<ownrun>/review_cleanup_cancel36.xml` | **0 / 36 passed / 0.12s**，原红输入未改 | peak4 / residual0 |
| `checks.py review_mypy195 -m mypy src/ai_intel` | **0 / 195 source files** | peak4 / residual0 |
| `run_quality_review.py`（原 author 两组 argv） | **0**；`review_ruff17` 全通过、`review_format17` 17 files already formatted | 两组 peak5 / residual0 |
| `prepare_review.py`；`assertion_inventory.py`；`summarize_review.py` | 各 **0**；172members/17source；494assert/17比较；935distinct/duplicate0 | 纯离线材料，不计业务 tests |

五组 75+32+99+71+658 = **935 当前源码 distinct XML testcase**。其中 2 为自建输入，32 为本轮重跑共享 native；不是作者 901 的抄录。外部 cancel36 是已有 source 取消行为的再次验证，不加进 935。旧 dc292 69native、658、4d cap12/cap11/无XML红均不计当前总数。

薄入口复用 raw `checks.py`、birth-aware Win32 `batch13_process_metadata.py`、成熟 `runtime_limits.original.py` OwnedJob；未复制大监控或 CIM scanner。native child40s / whole≤60、完整 Windows cap10、per-process512MiB / Job1GiB、CPUrate833 / 24logical=1.9992CPU、生产 slot2/原CPU1 门均未放宽。source helper29.515s、Job peak188076032B、最小可用 RAM1210671104B；shared helper17.829s。Job final active1仅当前 controller，真实新 Windows descendants 最终0。Root 排窗 source→交回→shared/caller；PG/WSL 不与 native 重叠。

## 当前 CBM 与完整调用交叉

官方 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` **0.11.0**。独立 cache `/tmp/cbm-r07-io-review1-ab386966`；固定 source src-only index `r07_io_review1_src`，新图 **2715nodes / 16095edges**。实际入口：`run_cbm_review.py cbm_review_index index_repository --repo-path /mnt/d/wt/r07-io-review1/backend/src --name r07_io_review1_src --mode fast --persistence false`；read/guard `trace_path --direction both --depth 3 --include-evidence true --format json`；`cbm_review_version --global-help`，四组 tool exit0，没有失败重试或再次 index。

**CBM 资源 coverage partial，完整 guest 合计/最终终态 unknown。** 现有成熟 helper 只记录 tool subtree，不能将其 combined10当完整guest≤16通过。index实际 subtree：sh **21692 / PPID21689 / ticks10320907** → timeout **21706 / PPID21692 / ticks10320911** → CBM **21707 / PPID21706 / ticks10320911**。父21689及其上祖先身份/ticks未捕获；trace 父24182/25334也未捕获；shared PID1未作为 subtree root，但未取得完整 Actor→PID1 祖先链。本轮未为此追加 scanner/再 index，原 receipt保留，纠偏见 [cbm_coverage_review.json](D:/wt/r07-io-review1/reports/runs/r07_source_io_deadline_review1_20261017/cbm_coverage_review.json)。Windows部分 peak7/residual0可信，Linux3只能描述工具子树；version太短未采到Linux peak也不能说 guest0。

CBM默认排除 `ai_intel/assets`；其16个py文件以源码 rg补查本切片 symbol，无 storage/guard引用。graph 对 ContentStore.read_verified 只识别 store_bytes caller，动态 Protocol 调用由 [完整 rg](D:/wt/r07-io-review1/reports/runs/r07_source_io_deadline_review1_20261017/review_source_callers_rg.txt) 补齐。生产协议含 ContentStore、MinioContentStore、VerifiedContentRecorder、FrozenVerifiedContent 四实现和13直属 override；旧单参 monkeypatch 只走省略 deadline 旧路径。全部生产直接读调用覆盖 `revalidation/verified_content:78/80`、`enrichment/inputs:137/139`、`assessment/rule_persistence:533`、`_content_read_worker:96`、`recommendations/candidate_loader:318`、`minio_store:89/101`、`enrichment/taxonomy_inputs:409`、`content_store:408`、`knowledge/revisions:213`、`structured_fact_proofs:877`。

共享 guard图与 rg吻合唯一 `_start_windows_cpu_guard` 调用 `process_limits:254`，三个生产消费者：content worker66、PDF worker20、semantic393；semantic 的 heuristic 边只经源码核定，未将推测视为已证调用。旧图不签当前代码，图排除和动态漏边公开保留。

## 未测、风险与下一步

- **PG69、原 unchanged M02、adapted M02、SQLState 57014/55P03/08006、真实 driver 无SQL观察 IDLE、权限/mode/source epoch 两围栏：not_run。** 资源资格未提供；没有把 fixture/作者日志替代这些证明。
- **实际 MinIO service：not_run。** SDK loopback 的慢 headers/chunks/drip、断流、hash、Unicode、大小、并发 deadline 已属于本轮 unit；不计 actualMinIO/live。真实模型、来源、FOFA、产品性能、持续运行、frontend/e2e/manual同为 not_run。
- **真实 content guardian 初始化拒绝、READY后 hard-exit、held reader/guardian/handle：not_run。** `test_r20_native_cpu_guard.py:242` 的产品故障参数主要 PDF/semantic；content 清理取消/权限/query/held 以 API mock覆盖。最小后续验证是一条获资源窗的真实 content guard故障，检查原 typed 主错误、worker/guardian终态与 slot可复用；不改共享生命周期、CPU门或资源阈值。现无具体复现的新代码缺陷，列为验证缺口，不伪报 bug。
- **完整 CBM guest资源祖先/终态：unknown**，不作为资源 green，当前图仅源代码辅证。无需重复索引修饰同一结果。

评分证据仅支持 F2/F3 原文支持读取边界及 A1/E1 消费者 typed 失败/资源清理的代码级能力；没有 live分、效果指标、整卡 accepted。下一步 Root 提供合格隔离 PG/MinIO资源时另开有界复验，保留 original/adapted M02、旧red和本次 ownrun。当前先冻结本有限初审，停止测试资源占用。

Verdict: **LimitedShip**。Not checked: PG/实际MinIO/真实held故障/完整CBM guest预算及最终终态。
