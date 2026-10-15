# R03 执行器/游标初审 1 · 两项 Must 定向复核

What this change does: 新版在 PG 回执保存完整服务端请求指纹，并只接受当前具备持久恢复条件的任务引用。未完成窗口保存有界 pending refs，末页重新读 PG 核验后才提交最终水位。

本次报告写作开始：2026-10-15T13:00:02+08:00。**有限结论：原初审 Must 1、2 已关闭；固定版本的定向复核 passed，未发现新的可复现阻断。** 这不签整 R03、T07、T16 或 G-A accepted，不改全局 progress。原初审五个失败日志和 needs_changes 报告保留，关闭只对本次固定版本有效。

## 固定输入与审查边界

- 集成版本：08c2ff0f8ebcb4e5a0cc3c32d390bdb9518898c0；tree a17886aa315c9a93a371d964945a58a8a5c19612。
- 作者修复源码：7f8d5d72150d03df2fd4678003ac082df0450f2b；完整证据：aecdf308318cb60c78e02c896c990cd8e4e040cd；修复基底/主控 0012 schema：9b64b718b679f07538563a9cc31dfc70a7e23d97。
- 自建独立 worktree：C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review-recheck/dianzi；分支 codex/recovery-r03-executor-review-recheck。初始 clean；结束 `git diff --exit-code` 为 0，只有 `_review/` 审查脚本未跟踪。
- 真实检查 `author_files_equal.*` 确認目标与作者修复的五个文件字节对应 Git 差异为空：cursor_repository.py，unit cursor boundaries，原 cursor persistence，新 cursor review fixes，新 cursor review negative。作者该提交总共修改五个文件，包含一个业务文件和四个测试文件。
- 已读当前 AGENTS、最新版 ponytail-review 5.2.0、00/任务状态/交接、原 R03/T07/T16 与本轮要求的 T08，冻结 CR 的完整指纹、0012 NULL 兼容、有界 pending refs、不扫所有历史、legacy 明确失败补充；原初审报告与原负例、新作者报告及修复差异。沿源码调用链检查，不根据作者通过数字下结论。
- 本轮只新增本报告和 root `reports/runs/recovery_r03_executor_review_1_recheck_20261015/`；自有测试/runner/plugin 在独立 WT `_review/`。没有业务、公共模型/schema/migration/合同/progress/锁/认证/金标/阈值/分母修改，没有 commit/push、付费调用、真实来源访问或公共服务停止/升级。

12:56:04+08 preflight 实际核对专用测试库及用户身份、public head `0012_source_page_fingerprint`、request_sha256 列存在、私有文件 root/0600。只使用新的 cursor_fix 测试库；旧 0011 jobs 库、Redis、Celery 全程未使用。审查未执行迁移，作者 fixture 中对应已有 head 的 migration 入口只核对/无版本推进。

## 原 Must 关闭证据

1. **终态失败任务不能再作为当前可恢复凭据推进页或水位：closed。**

   [cursor_repository.py:538](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review-recheck/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:538) 收紧到 queued/retry_wait/running、有剩余尝试、完整调度/租约与同 job outbox；同来源/scope/entry_id/payload/digest 检查保留。job 行 `FOR UPDATE` 保持到页面事务结束。[第 655 行](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review-recheck/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:655) 在所有 callback 后重查页内引用，末页还重查本窗口全部有界 pending refs。

   原负例实际 enqueue 并执行 handler 得 permanent failed、blocked、max_attempts=1 exhausted 后，再请求 final 页：三项都 page_accepted=false，没有新 cursor/receipt 或 authoritative watermark。当前 permanent 例 source `ce7e47bf-f4ae-4bcd-9fe9-97dd9bc72e59`、job `0b8b1c68-a191-4ac7-96a9-06abd562a0a0` 的真实观察见 terminal_permanent_failed.observation.json；原状态仍 failed，payload 历史保持。

   新 22 PG 中实际前页 job 永久失败后接管、末页拒绝且既有页/水位不变；同页后一个 callback 改前引用终态也整页回滚；合法 queued/retry_wait/running 正例仍通过。另由 reviewer 自写额外 PG case：末页 callback 将前页 pending job 改 blocked 并创建当前恢复 job，末页拒绝后旧 job 回滚为 queued，cursor 与旧 receipt 不变、watermark 未推进。这个独立 case 覆盖“callback 后的前页状态”而不只复读作者测试。

   tracking 只保留 `{job_id,entry_id}` 引用，状态实时回查 PG，没有第二套任务状态；本窗口 refs 最多 1000、envelope 1MiB/深度16/node10000，connector position 64KiB。超限原子失败，不截断引用。新窗清空 tracking，完成窗口历史仍留在 receipt；真实正例确认旧已完成窗口的 terminal job 不阻断下一窗口。源码只有按 source/stream/page_key 的单页 receipt 查询，没有末页扫描全部历史。

2. **变化的请求不再被当成同页重放：closed。**

   [page_request_digest:86](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review-recheck/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:86) 使用版本化 canonical JSON，包含 source/stream、UTC 窗口、input/output cursor、完整有序 entries 全部字段、is_last_page、UTC/null watermark；dict key 排序，固定分隔符/UTF-8、allow_nan=False。没有 caller 自报指纹、repr/default=str 或裁掉未知字段。[回执校验:622](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review-recheck/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:622) 在来源/scope/有效 lease 之后检查 NULL 和摘要；旧 NULL 明确 legacy_page_receipt_unverifiable，不猜 hash。

   原两项重放负例现在 changed_entry_rejected=true、changed_completion_rejected=true；既有非末页与 pending 水位保持原样，receipt_count=1，没有新 callback/写入。新 PG 六种变化分别覆盖 entry_id、未知字段值、条目顺序、watermark、completion、output；所有变体冲突且不改原 cursor。key 顺序和等价 UTC 时区重放仍 callback-free reused，跨 Session 真实验证。

   legacy NULL receipt 与缺 tracking 的未完成旧窗口均明确失败，callback-free；过期 lease 优先拒绝。自写独立 PG case 再查询整行，证明 NULL 旧 receipt 与 cursor 均字典相等，没有“失败时补造指纹”。JSON unit 真实执行非有限数、未知对象、bytes/datetime/Decimal、非字符串 key、循环/深度/node/字节上限；额外四个 PG case 证明 bytes/datetime/NaN/非字符串 key 在 callback 前拒绝，页/receipt 无写入。

## 原五个负例的保真复跑

原 `_review/test_independent_negative.py` 整文件 byte-for-byte 复制到新独立 WT，SHA256 **8a1938fbb5be23d6f5f6f73a3dac69d987584f5f19100ffea09a7df5d26ce137**，与第一次初审完全一致。没有改输入、测试期望、失败门槛或脚本字段；本轮仍是同一个 reviewer，未参与业务修复。

原资源 fixture 硬编码旧库/0011，故本轮使用独立 pytest plugin 仅替换该 fixture 的环境身份核验到新库/0012，并重定向 observation RUN；测试函数字节和业务断言不动。plugin、复制脚本和所有 helper SHA256 纳入 manifest，便于复跑者检查这项资源适配。

原 cursor “完全相同重放”测试新增了第一次请求已有的同值 watermark；新完整指纹要求这个字段相同，新增 changed-watermark 负例同时要求冲突。保留原 reused/history 断言，属于纠正 fixture 输入的遗漏，不是降低行为要求或改金标。

## 独立命令、秒级时间与数量

所有测试 Python 为 D:/dianzi/backend/.venv/Scripts/python.exe；cwd 为本独立 WT/backend。完整 argv、+08 秒级时间/exit、SHA/tree 和 source/test SHA256 见同名 command.json；下表仅缩写目录。没有以作者的 269/81/5 作为本次统计。

| 检查 | 2026-10-15 +08 起止 | 独立结果 | exit | 证据 |
|---|---|---|---|---|
| `pytest -p independent_resource_plugin ../_review/test_independent_negative.py -v --no-cov` | 12:56:24–12:56:26 | 5 passed，0 failed/error/skip | 0 | original_five.*、5 observation.json |
| `pytest tests/integration/test_r03_cursor_review_fixes.py -v --no-cov` | 12:56:41–12:56:44 | 22 passed，0 failed/error/skip，真实 PG | 0 | new_pg_22.* |
| 原 jobs/cursor/T07/T16/T07+T08 contract/security 七文件 | 12:56:57–12:57:02 | 59 passed，0 failed/error/skip | 0 | related_59.* |
| `pytest tests/unit -q`，原 coverage 60 门 | 12:56:24–12:56:53 | 283 passed，61.10%，0 failed/skip；1 既有 Starlette warning | 0 | full_unit.*、unit.xml |
| reviewer 自写额外 PG 六边界 | 12:58:43–12:58:45 | 6 passed，0 failed/error/skip | 0 | independent_boundary_6.* |
| Ruff check 五修复文件 | 12:57:46–12:57:46 | All checks passed | 0 | ruff.* |
| Ruff format --check 五文件 | 12:57:46–12:57:46 | 5 files already formatted | 0 | format.* |
| mypy src | 12:57:46–12:57:47 | 64 source files，无问题 | 0 | mypy.* |
| 修复提交 diff --check | 同名回执 | 无源码空白错误 | 0 | diff_check.* |

分层：本轮专项 PG 共 85 项（原相关 PG 52 + 新 PG 22 + 原负例5 + reviewer额外6）；原相关另有 T16 显式内存 fixture 6、T08 recorded/fixture contract 1，不能叫真实来源。pure unit 独立保留原 60 门，不和专项 PG 覆盖率混合；283 来自固定集成版含当前网络/PDF回归，和作者较早基底 269 不同，计数不能相互冒用。

## 独立索引、装配和验证限度

已读真实 CBM 0.11.0/help 和 index_repository help。独立项目 recovery_r03_executor_review_1_recheck fast 索引固定 backend/src，819 nodes/3579 edges，partial/unusable/skipped均0；persistence=false，缓存仓外。架构与 page_request_digest/_verify_persisted_entry inbound trace 指向 commit_page，和 `rg_callers.log` 逐调用交叉核对；图只用于导航，实际状态/锁/事务判断以源码和 PG 断言为准。

第一次静态 runner 从 backend cwd 给 git 加了 backend/ pathspec，使 source_diff/queue_unchanged 实际范围为空。原控制回执保留；后用 repo-root cwd 重新核验，source_diff_corrected 实际输出 48185 bytes 修复差异，queue_unchanged_corrected 输出 0 bytes，author_files_equal 输出 0 bytes。最终判断只用更正后的范围，不把第一次空输出当“没改代码”。这是审查工具范围错误，不是产品失败。

本轮 **没有再跑 Celery/beat/Redis**。更正后的 Git 比较确认 workers、outbox 和实际 Celery 测试相对原 43b723 无变化；原固定源码的独立 2 项实际 queue pass 仍在[初审报告](G-A-R03-executor-review-1.md)及其原 run 目录，本轮不重复计作新实跑。0012 是消费前向 schema 的接口，未部署整套队列演练。

当前 production registry 仍只注册 record_source_fetch_failure；真实来源/解析/富化 handler 与 legacy knowledge_change 装配仍有明确后续缺口。SourceCursorRepository 尚无生产来源调用方。没有用本次修复通过推断整 R03/G-A 或来源监测链完成。

## 收尾、未检查项与后续建议

13:00:02+08 resource_closure.json 核对库仍为0012/request_sha256存在，所有测试子进程已返回、Session/engine 已关闭；无常驻 worker/Redis 或 shared daemon 操作。数据库测试历史保留，旧 0011 库未连接，无 drop/downgrade/清表。已通知主控释放新测试 PG。

最终 manifest 给本报告、每份日志/JUnit/receipt/observation 与独立脚本 SHA256；凭据扫描只检查完整私有 DSN、密码及所有密码八字符片段，不把公开测试 run_id 当秘密。连接值未放 argv/报告；日志先在内存脱敏再写，JUnit再脱敏，不改 outcome。

作者旧 31 pass/1 fail 的 watermark fixture 遗漏、69 pass/21 setup error 的 fixture 接线失败保留在作者证据，不覆盖初审失败，也不冒称本次运行。当前复核无业务失败/error/skip。初始几个读取路径猜错后由 rg 找到真实文件，未计成产品失败，未补造首读或 worktree 创建的秒级回执。

未检查：本轮实际 queue、Linux prefork/hard limit、真实外部来源/模型/FOFA、完整来源装配、连续监测/性能、frontend/e2e/manual、全后端集成/全安全套件、0012升级路径的独立迁移演练（属主控schema审查）。这些为 not_run/blocked_live，保持原限制；T08 只有相关 recorded 合同回归，本报告不签网络切片。

合同符合性：指纹、pending refs/上限、legacy 明确失败和最终水位均落实主控冻结补充，没有改验收/金标/分母。F1/E1 证据支持分页追踪、恢复资格、重放与事务安全；P1仅为有界恢复基础，不提供时效/吞吐成绩。

下一步建议：主控据本次有限复核关闭初审 Must 1、2；来源/R04 handler 装配和真实链需其自身冻结版本/独立验证，仍保留整卡最后前置和阶段门。

Looks good. Ship this scoped cursor fix. Not checked: 本轮实际队列、live与整 R03/G-A 最终验收。

报告完成与封存：2026-10-15T13:02:52+08:00。资源释放时刻以 13:00:02+08 独立收据为准。
