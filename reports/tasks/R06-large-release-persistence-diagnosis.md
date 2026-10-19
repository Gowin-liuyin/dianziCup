# G-C / R06 大 release 保存独立诊断

What this change does: This report traces a real 616,865-byte release response through the unchanged 8a handler. Two isolated PostgreSQL replays measure parsing, storage, evidence writes and cursor commit. It changes no product code or acceptance limit.

诊断状态：**awaiting_review / complete**。产品修复：**not_started**。原 live 段仍为 **failed**，R06/T16/T54 的完整 live、正式时效、持续运行验收仍未通过；不登记 accepted。

结论：**35 秒本地守卫是实际终止的直接原因，逐 JSON 字段同步写库是已复现的主要耗时，两者同时成立。** 相同公开原文在两次独立 PG 重放中分别用 55.656 / 54.600 秒成功提交；其中整页保存占 55.438 / 54.433 秒。11,827 个文本块各触发 6 次 SQL，共 70,962 次；两轮 SQL 总数均为 71,344。没有支持“数据库长期锁死”的重放证据。原失败瞬间没有 PG writer 采样，因此不能反推该瞬间完全没有短暂等待。

## 范围、版本和依据

- 工作树：`D:/wt/r06-release-pg-diagnosis`；分支：`codex/r06-release-pg-diagnosis`。
- 被审代码：`8a1b04d48346d8550f0326a77f003246a0ebbab5`；Git tree：`c614a6cb784c8fab422a14479d14ea4b6303493c`。代码、测试、合同、配置、前端与 progress 的 diff 均为空。
- 原工具观察版本：`1c4cce9770bfa29d08728a0131f7fc7fe714f9bc`；原产品与 observer 未改。原报告/日志未覆盖。
- 已读取仓库 AGENTS、00 执行索引、12 的 R06、T12/T16/T07/T09、03/04/05/06 合同、01 评分映射、07 来源资源、09 运维、task_state 与交接。依照已读取的插件 `ponytail/5.2.0/skills/ponytail-review/SKILL.md` 核对调用方、真实负载与最小修复。
- 唯一报告为本文件；其余新增文件只在 `reports/runs/recovery_r06_large_release_pg_diagnosis_20261016/`。未修改 state、业务源、业务测试、公共配置、阈值；未提交、push、发布或自行 accepted。
- 0 HTTP / 外部 API / 资产请求；未启动 API、Celery worker、beat 或 MinIO。只读检查原测试库；写操作仅为新建、forward 迁移和运行自有隔离测试库。

## 原始失败和故障后状态

原段 `D:/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016/` 的已封存时间为 **2026-10-16 03:47:57–03:50:08 +08:00，131 秒**。`runtime_end.json` 原因是 `source_running_watchdog`，api/worker/beat 退出码均 1，observer 0。这不构成 6 小时连续运行，也不能补记浏览器或正式时效通过。

| 原事件（+08:00） | 已验证事实 |
|---|---|
| 03:49:31.837689 | job `5e3d6b02-67d2-4193-89cf-f1a1e4460c59` 被认领 running，attempt=1 |
| 03:49:33.757975 | HTTP 200 响应的 observed_at；0016 独立收据后来标记 normalized，616,865 B、目标 SHA 一致 |
| 03:50:08 | 本地守卫结束受控段；从认领到结束约 36.162 秒 |
| 03:50:31.837689 | 原 job 的 lease_expires_at；守卫在有效租约结束前终止 |
| 03:55:01 | 原 owner 以 MinIO `read_verified` 导出公开响应到仓外；不是本诊断重新联网抓取 |
| 03:59:41.455 / 04:08:46.221 | 本诊断两次原库只读快照；job 仍 running，文档/修订/页收据/FetchAttempt 均 0，source cursor 行为 0 |

后两次快照均 `transaction_read_only=on`，原库除审计连接外 session=0、locks=0。第二次还确认原页对象的 PG content_objects 行=1、response receipt 引用=1、revision response 引用=0。因此响应及其 CAS 登记与独立收据保留，业务页、文档和游标事务撤销；未留下 writer 事务。没有主动修复原 running job、过期租约或旧 outbox。

这说明 **normalized 只表示响应解析成功，不表示页保存、cursor 或 job 已完成**，与 `SourceResponseRecorder.mark_outcome` 的合同一致。原页失败没有推进游标；原始响应能保留用于再解析。真实 MinIO 中可能存在的未登记成员对象数量，本轮未访问和清理，不能声称已验证。

## 输入与离线重放边界

原文只留仓外：`D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin`。

SHA-256：`25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7`；大小 **616,865 B**。执行前及最终审计均重新验证 hash/大小。安全来源收据为原段 `release_export_receipt.json`，payload 为 `source_kind=ollama_releases, stream_kind=live, window_end=2026-10-15T19:00:00Z, remaining_pages=5`。

重放为 **真实原文离线重放 PG**：显式注入仅接受固定 page=1 URL 的 fixture fetcher，body 与原 raw 完全相同；调用原 `execute_job → collect_page`，使用真实 PostgreSQL、原权限判断、原内容 hash 校验、原文档/证据/cursor/receipt 路径。`stream_kind=live` 仅表示原游标分区，不能据此把离线 transport 算 live。

原收据未保存响应 Link headers，无法恢复原实际 next cursor。本轮明确用空 headers 的终页 fixture，输入页面=1、下一页=0；没有猜原 header，也没有宣称重放验证了真实分页 continuation/outbox。真实 next-page job 的代码路径已静态核对，仍需后续真实边界复验。

内容库使用自有仓外 `ContentStore`，不是 MinIO 替身的 live 证明。每次使用全新数据库、job/request key、对象根；未重复原 job/request key。42 次 store、22 次 read_verified 均走原完整 hash 校验；最终 21 个物理 CAS 对象全部复验 hash。数据库只 forward 到当前 `0016_source_response_receipts`，无 downgrade、旧 schema 清理或 dev DSN。

WSL 私有 connection.json 仅 `subprocess capture_output` 后在内存解析；DSN 未进入 argv、stdout 或报告。子进程环境仅保留 Windows 必需路径变量与自有 PG URL，不读取 DPAPI/模型/供应商秘密。原 20% Windows Job CPU rate、每进程 512 MiB、总 2 GiB 限制原样用于真正重放；不是放宽业务 CPU 限制。

## 完整调用链和共享调用方

官方 WSL 工具 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` **0.11.0**，独立 cache `/tmp/dianzi-cbm-r06-large-release-diag-20261016`、项目 `r06_large_release_diag_8a_20261016`。03:59:24.968–04:00:23.764 +08:00，version/index/schema/10 条双向 depth=2 trace 共 13 命令均 exit 0。仅索引本工作树 `backend/src`，persistence=false；1409 nodes / 7128 edges，not_indexed/skipped/partial/unusable 均 0。工具按现有排除规则排除 `ai_intel/assets`，不含测试、报告、raw、fixture、holdout；未使用作者 cache。schema 与每条 trace 原始结果保存于本 run。

追踪：`workers/runtime.py:100,131` 注册/消费 → `workers/executor.py:92–125` 短事务 claim，随后业务事务 → `source_jobs.py:435–452` 来源注册、cursor claim、独立 recorder → `source_jobs.py:503–528` `_fetch_catalog_page`、normalize、登记响应、保存 catalog → `catalog_pages.py:334–375` release 检查与每记录 `parse_json_document` → `catalog_documents.py:177–305` PG advisory/document 锁、CAS、修订、文本块、证据 → `source_jobs.py:560–589` cursor/page receipt/release、若有下一页则 enqueue/outbox → `executor.py:111–125` 完成 job 与外层提交。

仓库没有名为 `persist_sources.py` 的实现；当前对应路径为 `source_documents.py` 的 `persist_source_response` 和 `catalog_documents.py` 的 `persist_catalog_documents`。前者负责 NVD/vendor，后者负责 release 等 catalog。没有为了跟随任务用语制造另一条保存路径。

`all_source_callers.log` 与 CBM 相互核对了所有源代码调用方：

- `ensure_source_registration`：source API、polling、handler、`persist_source_response`；固定 source 事务锁和 identity/scope 校验不能删除。
- `save_document_revision/register_response_content`：catalog、结构化 source、handler，以及独立 response recorder；CAS hash 锁与 `cleanup_unreferenced_object` 共享，GC 会检查 response receipt 引用。
- `add_text_block/attach_evidence_span`：catalog 和 source_documents 共用；必须保留 revision 存在、ACL、Unicode 范围和 quote hash 判断。不能只修 release 入口而破坏其他 source。
- `commit_page`：handler 唯一业务源调用；每 revision 再核对 source/scope，页收据、cursor 和 continuation outbox 由同外层事务提交。
- `execute_job`：runtime；`renew_lease` 的源码只有定义，没有当前 handler/runtime 调用。job 与 source 都是 60 秒租约，本轮未延长或跳过围栏。

CBM 对闭包/动态注册的部分 caller 显示文件级 heuristic；精确调用位置以上述源码与 `rg` 为准，不把图推断当完整动态证明。

## 真实命令、结果与计时

工作目录均为本工作树；子进程执行目录为 `backend`。Python 为已有 `D:/dianzi/backend/.venv/Scripts/python.exe -B`，不修改其依赖或安装采样库。CBM 全 argv、起止、退出码在 `commands.jsonl`；重放全 argv 在 `replay_*_command.json`，无连接串。

| 命令 | +08:00 起止 | exit / 结果 |
|---|---|---|
| `control.py replay 1` | 04:01:22.515–04:01:23.112 | 1；bootstrap 导入 control 未 guard main，未进入 handler，无 job |
| `control.py replay 2` | 04:02:06.360–04:02:08.436 | 1；缺 psutil，已 forward 0016，未创建 job/进入 handler |
| `control.py replay 3`，真正重放 1 | 04:03:20.022–04:04:18.115 | 0；子命令 58.094 秒；handler/PG 提交成功 |
| `control.py replay 4` 的一次前置拒绝 | controller 未记录起止，工具观测 2.550598 秒 | 1；attempt glob 错计 process_identity，尚未建库或 spawn；另存前置失败收据，不能编造完整时间 |
| `control.py replay 4`，真正重放 2 | 04:05:49.191–04:06:45.839 | 0；子命令 56.656 秒；handler/PG 提交成功 |
| `control.py snapshot_after` | 见 commands.jsonl，快照 04:08:46.221 | 0；原库 read-only，原失败状态保持 |
| `audit.py` | 审计收据 04:09:36.541 | 0；两个真正重放完整性、四个自有子 PID 已停、四库无残留 session、raw/DSN 未进入日志 |
| Git HEAD/code diff/diff-check | 见 commands.jsonl | 全 exit 0；被审代码 8a 保持 |

前置失败已完整保留，不计业务失败或通过。guard import/std lib process identity 的独立前置检查 exit 0 后才继续。主控明确澄清最多 2 重放按真正 `execute_job/handler` 计，当前正好 2；没有第三次真正重放。两次失败、两次真正重放及一次前置拒绝的已记录 wall 合计 **119.956598 秒 < 240 秒**，每子命令均 <120 秒。没有把失败改为 skip。

封存 wrapper 另有一次 UTF-8 task_state 被 Windows 默认 GBK 读取的前置错误（exit 1、工具 wall=2.568827 秒），未进入 seal 或触碰业务；显式 UTF-8 后 seal precheck exit 0。该记录保存在 `seal_preflight_encoding_failure.json`，不计 PG 重放或业务测试。此后没有扩大诊断到依赖安装、额外重放或产品补丁。

两轮均输入 **1 页 / 20 个 raw release**，解析后 20 个文档、11,827 个 blocks、计划证据 11,827、成员 payload 总 616,844 B。最终各库：documents=20、revisions=20、text_blocks=11,827、evidence=11,827、page_receipts=1、response_receipts=1、FetchAttempt=1、content_objects=21、source cursor=1（generation=1、last_successful_page=1、lease 已释放）、outbox=1（最初 enqueue，非真实 continuation）。非法证据=0。

第二轮使用 `perf_counter` 精确 wall；第一轮 `monotonic` 在本 Windows 环境呈约 15.6ms 粒度，因此第一轮细小阶段出现 0，不能当零成本。CPU 是 `process_time`，为诊断子进程及其采样线程 CPU，非 PG server CPU或原 API/beat 全进程树；其粒度约 15.6ms。阶段为包含下层调用的累计值，不可相加作为总耗时。

| 阶段 | 第一次 wall / CPU 秒 | 第二次 wall / CPU 秒 |
|---|---:|---:|
| execute_job（含最终业务提交） | 55.656 / 36.344 | **54.600 / 36.422** |
| normalize_catalog_page | 0.047 / 0.031 | 0.039 / 0.047 |
| persist_catalog_documents | **55.438 / 36.234** | **54.433 / 36.266** |
| 20 次 save_document_revision | 0.220 / 0.047 | 0.154 / 0.141 |
| 11,827 次 add_text_block | 17.087 / 11.797 | 17.471 / 11.313 |
| 11,827 次 attach_evidence_span | 28.044 / 18.266 | 27.249 / 18.531 |
| 42 次本地 CAS store | 0.284 / 0.047 | 0.198 / 0.141 |
| 22 次本地 CAS read_verified | 粒度内 / 0.016 | 0.011 / 0.047 |
| cursor commit_page | 0.047 / 0.031 | 0.043 / 0.031 |
| complete_job | 0.015 / 粒度内 | 0.005 / 粒度内 |

两次均有 SQL 形状计数；未输出 statement/binds/正文。第二次 SQL 客户端 execute 累计 **31.802 秒**，不是纯 server 执行时间，也不是完整保存 wall。主要计数为 revision SELECT=23,734（其中块存在/ACL 校验为 23,654）、text_blocks INSERT/UPDATE/SELECT 各 11,827、evidence INSERT=11,827。每块 2 SELECT revision + INSERT block + UPDATE block metadata + SELECT block + INSERT evidence，即 **6×11,827=70,962，占全部 SQL 99.46%**；其余为每文档和固定事务/收据/cursor/最终检查。

每 0.5 秒只读采样：第一轮 109、第二轮 107 快照，blocking_pids / ungranted lock / Lock wait 快照均 0。第二轮合计状态观测 active=7、idle in transaction=100、idle=213，Client wait=312、IO wait=0；这些是状态观测条数，不是唯一进程数或时间占比。所有语句最大 client execute <0.028 秒。短等待可能被采样漏掉，但没有几十秒单语句、锁阻塞或 IO stall 证据。

35 秒时仍在推进：第一轮 35.109 秒已写 13 文档/7,312 证据/44,097 SQL；第二轮 35.446 秒已写 14 文档/7,910 证据/47,700 SQL。页尚未提交，继续原路径后全部在有效 60 秒租约内提交。这是有具体输入的守卫误杀复现，不是仅根据常量大小猜测。

## Must fix

1. **本地守卫先于业务租约杀掉正常保存**（原运行 `supervise.py:88–94`；产品 `workers/jobs.py:18,219–239`、`cursor_repository.py:333,426–440`）。

   **触发 / 问题：**同 SHA 的合法 release 页在无长锁等待的两个隔离 PG 运行中需约 55 秒；running 超过 35 秒时原守卫直接终止整个 API/worker/beat。原 job 租约当时仍有效，造成整页回滚、游标未提交和真实段中断。

   **最小修复建议：**只修改运行工具 owner 的有界守卫，在 run hard deadline、既有资源/CPU/日志/请求预算以内，按已存 job `lease_expires_at` 决定停止时间；可采用 `min(run_hard_deadline, existing_lease_expires_at + 5s rollback/cleanup grace)`。不延长业务 lease，不跳过 source/job 围栏，不把超过 lease 的结果标成功；到期仍由原 PG 围栏拒绝提交和原恢复逻辑处理。本轮未改任何守卫。

   **为什么有界且安全：**等待至既有 60 秒租约只使用已经授权的任务生命周期；5 秒只给失败撤销/收尾，绝不允许额外事实提交；hard deadline 和原 Windows Job 限制优先，失去进展/预算耗尽仍停止。不会扩大外部请求范围、并发、CPU、问答性能或正式门槛。冻结 R06/T卡/03–06 中没有 35 秒页采集业务指标；01/06 映射的官方 P1 是发布/发现至采集≤6小时，与本地 35 秒守卫不同。

   **若不修 / 复验：**当前相同真实输入会继续在正常保存中被杀。工具 owner 应以该 raw/hash、原 CPU/内存与严格 hard deadline 复验有效 lease 下不误杀、过期且不能提交时有界收尾、所有子进程/事务结束；随后另开真实 MinIO/live 段，保留原 red 段，不重写为通过。

## Should fix

2. **每个 JSON 字段六次 SQL 把一页保存推到租约边缘**（`catalog_documents.py:261–300`；`knowledge/revisions.py:212–243,245–328`；`catalog_pages.py:334–370`）。

   **触发 / 问题：**20 条真实 release 内部包含大量 asset/元数据字段，规范化生成 11,827 个 blocks。catalog 对每块调用查 revision、插入 block、更新元数据，再查 revision ACL、查 block、插入 evidence；证据正确，但事务同步等完整解析结果后才到 cursor，保存占整段 99% 左右。该实例已在两个全新数据库稳定复现 54–55 秒；第二次距 job lease 结束仅约 5.4 秒，真实 HTTP / MinIO 与同时运行的 API/beat 未在离线重放中计入。

   **最小修复建议：**在已有 revision 保存路径增加窄的批量块/证据写入：每 revision 校验父记录和 scope 一次，纯业务校验 Unicode 区间/quote/hash/metadata 后，在同一事务批量插入带最终 metadata 的 blocks/evidence。避免 INSERT 后逐块 UPDATE 与相同 revision 的重复 SELECT；保留独立单条入口的严格校验。不得删除原文/证据、缩页、截 asset 字段或改变 hash/去重/ACL/CAS 锁来“提速”。本轮未实现该建议。

   **若不修 / 复验：**仅改守卫仍保留约 7.1 万次 SQL 和极小 lease 余量；不能由本地 CAS 成功保证真实 MinIO/live 成功。修复后用同 raw/hash 与现有资源限制重新记录 SQL 数、stage wall/CPU、20 修订/11,827 证据逐条回切、同事务 cursor/outbox、坏 quote/租户拒绝/中断回滚及重复投递，不放宽业务门槛。T16 §4.3 / W01 要求解析不要阻塞原始采集 cursor 的完整异步切片仍需单独核对，本诊断没有把性能补丁等同整卡合同通过。

## 未证与评分证据

- **已证：**实际守卫终止点、响应独立收据保留而业务页回滚、cursor 未推进、原库当前无 writer；同原文两轮真实 PG 的逐字段 N+1 与无长锁等待的成功提交。
- **未证：**原失败瞬间 writer 精确等待事件；原真实 Link header/下一页 cursor；同真实 MinIO 的完整保存、lease 是否足够、故障自动恢复、停机回补/重复投递；独立参考漏采集合、正式≤6h指标、完整持续运行、浏览器。空 header 离线终页不能补齐这些 live 条件。
- **unit/项目 integration/contract 回归：not_run**，本轮无产品改动。诊断 PG 重放观察 2 次 exit 0；artifact audit 1 次 exit 0；两个前置子失败和一次前置拒绝仍保留。没有据此捏造 pytest 测试数或标准性能成绩。
- **F1/P1/E1：**本报告提供真实输入的保存/回滚与运行边界证据，不签来源完整性、时效或稳定性通过。**R1/D1/X1：**提供来源 hash、未伪造事实、可复现调用链及新独立审查证据；不自动判分。
- **资源收尾：**04:09:36.541 审计时 PID 48852、41472、31216、43216 均 inactive，Popen 均 wait 结束；真正重放的 creation time 和资源上限保存在 process_identity 收据。四个自有数据库无其它 session；采样线程均已停止。数据库和仓外对象留供审查，未做未授权清理。WSL/PG 资源 owner 继续控制其服务。

原/本轮文件的原始 bytes 与 SHA 见 `original_evidence_manifest.json`、`artifact_manifest.json`；执行脚本版本快照、命令、失败日志、两轮结果/采样、只读前后快照与 audit 都在本 run。raw 本文只记录 hash/大小，未复制正文到报告、索引、提示词或提交。exact body / credential-bearing PG URL 检查为 0；该扫描不冒称读取和比对了 DPAPI/provider 秘密。

下一建议：先由工具 owner 做第 1 条有界守卫修复的独立审查，再由业务 owner 做第 2 条保存往返削减与合同回归，之后在新真实受控段复验。原 live 红记录与其它恢复工作可继续保留和独立推进。

Verdict: fix 1 and 2 first. No live gate approval.

Not checked: real MinIO persistence and original pagination headers; original in-flight PG wait state; formal timing and continuous live monitoring.
