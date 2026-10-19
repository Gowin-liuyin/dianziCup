# R06 / R22 early collection · 2026-10-15

任务状态：`awaiting_review`；本次运行准备与启动实现 `complete`。真实观察窗口仍进行中，R06 广来源、R22 正式评测、T54 持续运行均未完成或通过；不得把自动结束记录作为验收结论。没有修改产品、合同、迁移、锁文件、共享 progress 或提交/push。

本次固定代码 `1927eeb00a7e0c1335f76340b0382f46102f08f2`，独立 detached 工作树 `D:/wt/gb-controlled-collection-1927`，启动前 `git status --porcelain` 空。远端阶段归档 `c229a7f...` 只作为主控已核交接背景，本次服务始终加载 1927。复用既有 Python 3.12 环境，以 PYTHONPATH 明确指定固定工作树 backend/src；没有安装依赖或下载模型。

## 输入、范围与实际资源

已读 AGENTS、执行图、恢复 R06/R22 任务卡、06 测试合同、task_state、交接、新版 Ponytail 5.2 full，以及旧 segment6 supervisor/prepare、segment5 collector、MinIO 段4脚本和固定版本的 API/worker/source/cursor 实现。修改仅在 `reports/runs/recovery_gb_controlled_collection_20261015/`、本报告；原 MinIO 段4只写了已授权且严格核对所有权后的 `service_stop.request`，由原守护器自行产生结束记录。

输入只有固定匿名公开 GET 来源 `nvd_ollama` 与 `vllm_vendor`。输出是认证 HTTP 提交、PG 任务与游标、原文响应 hash/分页收据、计数、时间质量和运行控制证据；不接模型、测绘、第三方资产或 PoC，不触发新付费 API。来源抓取仍由产品网关执行，固定域/URL、零重定向、7 秒最小轮询间隔、Retry-After 处理、最多 20 页与每任务最多 3 次尝试均来自冻结产品代码。

启动预检 `resource_preflight.json`：PG `test_dianzi_r04_pipeline_20261015` 为 `0014_grounded_answer_vectors`；没有 queued/running/retry_wait 旧任务，只有本次预检数据库连接；历史 105 events / 105 documents / 105 revisions / 434 evidence / 38 fetches / 38 page receipts 全部保留。Redis DB12 当时 key_count=0 且无旧消费者。主控未来 R06 新 schema/worker 须使用另库。

实际服务开始 `2026-10-15T19:45:24+08:00`，最晚 `2026-10-16T01:45:24+08:00`。Windows supervisor 实际 PID `20976`（venv launcher `40724`），登记的四个 Popen PID：API `3876`、worker `28472`、beat `20268`、collector `29732`；venv 启动器另有真正解释器后代，全部继承本次 Job。API 仅 `127.0.0.1:28010`，Redis12，队列 `gb_collection_1927`；beat shelf 在仓外用户缓存。worker 是 solo / concurrency1，禁用 gossip/mingle。

Windows Job 已通过 QueryInformationJobObject 实际读回：每进程 512 MiB、总 2 GiB、kill-on-close、host CPU 20% 硬限。独立 Job accounting 每秒检查累计 CPU 1200 秒；来源任务 running 年龄大于 35 秒则停止，数据库查询/连接各 3 秒超时；轮询还约有 1 秒调度余量。它不依赖已知存在延后问题的原 PROCESS_TIME CPU 终止行为。每进程日志 16 MiB，观察 JSONL 另有 16 MiB 停止门；日志、预算、依赖失败或子进程退出可导致早于 6 小时停止。最多 12 轮，每 1800 秒一轮、每源每轮20页，理论最多480源任务/1440任务尝试，另有500次本地 REST 调用上限。源 attempt_count 是 GET 次数的保守上界，因为轮询间隔拒绝等尝试可不出网。

MinIO 原段4已核 supervisor `28048`、child `28049` 的完整 cmdline、cwd、29400 端口、cgroup procs 后，请求其正常停止，实际于 `2026-10-15T19:45:06+08:00` 结束，原因由原脚本记录为 owned stop request；提前结束原因见 `minio_transition_request.json`。新同数据/身份段 `19:45:17+08` 开始，WSL supervisor `8440`、child `8461`、Windows WSL launcher `25760`，最晚 `2026-10-16T02:15:17+08:00`。沿用 cgroup CPU 0.5、768 MiB、0 swap、256 PID，另累计1800 CPU秒及16 MiB日志上限。二进制 SHA256 `10ec54df2dc51dfa1399b7187d9377a20bd1b50f22d123a756175173b0cfff75` 实核一致；它是本机开发构建，不称官方发行。对象和身份均未重置，health HTTP200 与身份一致性已核。底层 Docker 既有总截止 `2026-10-17T21:49:15+08:00` 晚于本次窗口。

## 已获得的真实证据

`ready_before_collection.json`：19:45:37+08，真实 PG/Redis/OpenSearch/worker/beat 均 ready，HTTP200 / DATA_MODE live。认证使用授权的 DPAPI 登录秘密和真实 PG 认证/CSRF；两个来源 POST 均 HTTP202，随后 GET `/v1/jobs/{id}` 均 HTTP200。首源任务：NVD `636e157f-3fe5-4560-8dd9-bc6a02ea7503`，vLLM `7d677cfa-f466-4396-80db-98125b4d1d5e`，PG 两者 succeeded、attempt_count1。

`first_source_observation.json` 于19:46:07+08落盘：两源各2次成功 HTTP200、4页原文hash/PG分页收据；计数暂为124 events / 125 documents/revisions / 474 evidence / 42 fetches / 42 receipts。vLLM 接续历史未完成游标（原观察窗口仍为15:26:21+08）并由第6页推进到第8页，没有重置原 cursor。NVD 新观察窗口已推进 offset40。后续计数应以 `collection_latest.json` 与实际 PG 为准，不把首轮局部快照冒充最终结果。

首快照时间质量：45条 NVD 历史修订缺 source_published_at，单列 missing；80条 vendor 已存修订为历史内容，发布时间到原入库已超过6小时，单列历史补采。future time 与缺 first_observed/ingested 当时均0。该统计包含旧库存，未建立独立参考集合，没有漏采分母、正式 p50/p95/max 或可问答完成延迟；不能判时效通过。空结果始终不是安全结论。原始产品 HTTP 时间和 PG 时间保留原值（可能 UTC/微秒），run 元数据统一秒级 +08，后续摘要可按同一时区规范化而不改原值。

19:48:16+08交接复核 `handoff_snapshot.json`：实际8个本窗口源任务均 succeeded，8次fetch均200（NVD3、vendor5），无本窗口failed/blocked/partial；截至19:48:07快照有148 events / 149 documents/revisions / 520 evidence / 46 fetches / 46 receipts。两源最后成功分别为NVD19:46:28+08与vendor19:46:48+08；45条NVD缺发布时间、104条vendor历史补采>6h仍单列。PG幂等复用与事件归并可导致documents/events计数不同，未据此改变口径。heartbeat四子进程均alive，Job累计CPU18.40625秒、峰值总内存444723200字节，API实际监听解释器PID36392；没有 runtime_end 或 minio service_end。该摘要时间已规范成秒级+08，原始证据保留。

## 命令、结果与未运行项

实际执行：

```text
git worktree add --detach D:/wt/gb-controlled-collection-1927 1927eeb00a7e0c1335f76340b0382f46102f08f2
D:/dianzi/backend/.venv/Scripts/python.exe -B reports/runs/recovery_gb_controlled_collection_20261015/inspect_runtime.py
codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/gb-controlled-collection-1927/backend/src --mode fast --name gb_collection_1927_src --persistence true
codebase-memory-mcp cli --json trace_path --function-name create_application --project gb_collection_1927_src --direction outbound --depth 4 --include-evidence true --format json --max-output-tokens 4000
codebase-memory-mcp cli --json trace_path --function-name dispatch_pending_jobs --project gb_collection_1927_src --direction both --depth 5 --include-evidence true --format json --max-output-tokens 4000
D:/dianzi/backend/.venv/Scripts/python.exe -B reports/runs/recovery_gb_controlled_collection_20261015/selfcheck.py
wsl -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_gb_controlled_collection_20261015/minio_transition.py
Start-Process wsl.exe ... python3 -u -B /mnt/d/dianzi/reports/runs/recovery_gb_controlled_collection_20261015/resume_minio.py -WindowStyle Hidden
reports/runs/recovery_gb_controlled_collection_20261015/launch.ps1
reports/runs/recovery_gb_controlled_collection_20261015/scan_secrets.ps1
```

以上准备/启动命令已实际执行；首次 preflight 因读错 evidence_spans 表名 exit1，修正为已读合同中的 evidence 后重跑exit0；首次复用非持久 CBM 项目返回 isError=true，两个原错误envelope保留，随后独立1927 src-only索引/trace均成功，1085nodes/5219edges、0 skipped/partial/unusable。CBM自动写入的索引文件已移入本次run，固定产品工作树恢复干净。错误记录在 `preparation_failures.json`，没有把环境/准备错误包装成业务测试失败或通过。

运行控制 selfcheck 实际一轮 exit0，含两项非法来源/页数边界、35秒边界、调用和CPU预算决策、固定来源URL/7秒合同、实际Windows Job限制读回；这不是产品pytest数量。启动前8个Python脚本 compile()语法检查exit0，加入秘密扫描脚本后最终9个脚本检查仍exit0，见 `syntax_check.json`。未跑产品完整 unit/contract/security/frontend/e2e 回归，因为未改产品且主控已另有冻结版本验证；本轮无新增产品测试。早期 HTTP→PG→worker→原文链实际运行仅是限定live证据。完整6小时、12轮、故障恢复、正式时效、广来源和T54均尚未验证。精准秘密扫描结果由 `secret_scan.json` 给出，窗口增长后的日志仍须在结束时复扫。

## 停止和交接

正常停止入口是在本次run创建 `stop.request`。supervisor终止自己创建的四个Popen后写 `runtime_end.json`；退出关闭本次Job，清理继承的解释器/网关后代，不按名字杀其他进程。MinIO单独在本次 `minio/service_stop.request` 创建停止请求，守护器只对已创建的8461进程组发送SIGTERM，必要时SIGKILL，写 `minio/service_end.json`；主控仍可能依赖该对象服务，提前停止须协调。自动截止不依赖聊天持续或无界sleep。

持续检查 `runtime_heartbeat.json`、`collection_latest.json`、`submissions.json`、`collection_observations.jsonl`、`runtime_end.json` 是否已产生；实际PID与截止以 start receipt 为准。结束后由主控取得PG最终快照/真实持续时间、失败/未知、游标恢复状态及日志hash，并重新扫描秘密，再做非作者审查。未收到新授权前不继续下一任务，也不把本报告写成 accepted。

评分证据仅为 E1/F1/P1 的两公源受控采集、PG/outbox/原文与早期观测起点；不代表八类来源、官方时效优秀档或正式持续运行通过。计划偏差仅为本报告已明示的early-observation限制、原始证据保留UTC/微秒并另出+08摘要、资源/日志门可能提前结束，未修改产品冻结合同或验收条件。下一建议是观察到真实结束并核对每轮缺失，再独立进行R06其它来源与正式参考集合建设。
