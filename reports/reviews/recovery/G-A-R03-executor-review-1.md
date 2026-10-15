# R03 / T07 / T16 执行器与游标独立初审 1

What this change does: 该改动把任务输入、租约、重试、outbox 和分页游标交给 PostgreSQL 保存。Celery 只交付 job_id，受控 handler 的业务效果与任务完成状态在同一 PG 事务提交。

报告开始写作：2026-10-15T12:27:10+08:00。结论：**needs_changes，先修复 1、2**。这只是固定版本的执行器/游标切片初审，不签整 R03、T07、T16 或 G-A accepted，不登记全局 progress。

## 固定版本、权限和检查范围

- 作者源码/测试：43b723bd08eb41a56d40e5733338fe6021992178；基线：3465b47ce618bed6fa45cfecccd88b2b595e04b9。
- 独立完整证据 checkout：cb75fb1d0e11d40efb5abf54598a41322241c911；tree：0e823c6d26e09a375b505d1ab3f75b714bedf067。`git diff 43b723bd HEAD -- backend/src backend/tests` 无输出，业务与测试未变化。
- 独立 worktree：C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review/dianzi；分支 codex/recovery-r03-executor-review。初始 status clean；结束只有 `_review/` 未跟踪审查脚本，tracked diff 为空。
- 主工作区已有其他流修改，全部保留。本审查只新增本报告和 `reports/runs/recovery_r03_executor_review_1_20261015/`；负例、runner、pytest evidence 路径插件仅在独立 worktree `_review/`。
- 已读 AGENTS.md、00 执行索引、02/03/04/05 合同、manifest.recovery.R03、原 T07/T16、固定版 R03-executor.md 与任务状态；另读主控工作区 CR-R04-R03_job_cursor_execution.md 的公开 connector dict、内部 envelope、未完成原窗口接管、release 失效和最终页水位补记。
- 使用最新版 ponytail-review 5.2.0；审查源码 6 文件、16 文件差异、调用方及相关测试。没有业务/schema/migration/依赖/锁/认证/金标/阈值/分母/全局状态修改，没有 commit、push、付费调用、真实来源访问或公共服务停止/升级。

负例使用实际 PG 输入与查询，不使用作者通过数字作结论。运行资源为主控独占测试库、Redis loopback 26379 DB8；12:20:45+08 preflight 核对测试库/用户身份、head `0011_job_delivery_and_cursors`、私有连接文件 root/0600 与 Redis 0 key。连接值只在私有读取子进程和环境内存中流转，没有放 argv/报告；日志先脱敏后落盘。

## Must fix

1. **终态失败任务被当成可恢复条目，最终页和水位仍会提交**（[cursor_repository.py:428](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:428)，判断范围 428–432）

   - **What this is:** 原文未取得时，分页必须有同来源、同租户、同 entry_id 的可恢复失败 job，才能替代 revision 提交页。该判断目前只拒绝 succeeded/cancelled。
   - **Problem:** 审查实际 enqueue 同来源/条目 payload，再由 execute_job 形成 permanent failed、blocked、max_attempts=1 的 exhausted failed 三种终态。三种终态都被 `commit_page(...is_last_page=True)` 接受：receipt 和 `last_successful_page=1` 已提交，`window_complete=true`，authoritative watermark 实际推进。`_claim_job` 只认领 queued/retry_wait/expired running，恢复扫描也只看 running；这些终态没有自动重放路径。三例都违反 04/W01.4 与冻结 CR“可恢复的失败任务”条件，属于确证业务失败。
   - **Fix:** 将可接受状态收紧到实际可调度/可恢复的非终态，并验证剩余尝试和所需 durable delivery；拒绝 failed、blocked、cancelled、succeeded 及耗尽任务。永久错误需要人工修复时保留页未完成，不以这类 job 提交水位。最小修复是共享明确的“当前可恢复”判断及对应 PG 回归，不增加另一个状态源。
   - **If we skip it:** 缺失原文被最终页成功与水位掩盖，后续增量窗口可能跳过该条目。

   实际证据：`independent_negative.log` / `negative.xml` 的前三项；`terminal_permanent_failed.observation.json`、`terminal_blocked.observation.json`、`terminal_attempts_exhausted.observation.json`。例如 permanent failed job `ed90bfdd-b3f1-4fef-a9c8-c659219a1012`，source `a1b7bbd2-122a-47c6-a795-d848b5b3c123`，12:24:26+08 观察到 page_accepted=true，状态 failed，attempt=1/max=5，水位已提交。独立负例见 `_review/test_independent_negative.py:47`。

   复验要求：三种终态均拒绝、页内写入/receipt/cursor/watermark 不变；有剩余尝试且 durable 的合法恢复任务仍允许；保留原同 scope/source/entry/digest 拒绝回归。若前置任务后来变为永久失败，也应在最终页提交前重新验证当前恢复资格。

2. **分页回执只比较游标和数量，变化的重放被静默认作原页**（[cursor_repository.py:487](C:/Users/yinha/.codex/worktrees/recovery-r03-executor-review/dianzi/backend/src/ai_intel/ingestion/cursor_repository.py:487)，判断范围 487–494）

   - **What this is:** 相同冻结窗口与 input cursor 构成 page_key；有效租约下的完全相同重放应 callback-free 返回既有 receipt。当前回执只核对 input_cursor、output_cursor、entry_count。
   - **Problem:** 实际先提交 entry_id=original-entry，再以同 key/cursor/count 提交 new-entry-not-saved，返回 reused=true，callback 只收到原条目，返回引用仍属于原条目。另先提交空的非末页 input/output={}，再以相同 key/cursor/count 改为末页；第二次也 reused=true，但 `window_complete=false`、watermark=null、pending 水位仍保留。两例均已跨 Session 提交并查询验证，没有借租约失效制造失败。
   - **Fix:** 由服务端保存并比对版本化 request fingerprint：全量且有序的 entries、is_last_page、规范 UTC watermark，加现有 input/output cursor；source/stream/frozen window 可一并纳入。采用确定性的 JSON 规范化与 SHA256，拒绝不可规范化值，不通过 repr/default=str、删字段或 caller 自报指纹规避。主控若新增列应做前向迁移；旧 receipt 无指纹时明确 fail closed、callback-free、不改页/游标/水位，不能默认为匹配或重跑并覆盖旧回执。
   - **If we skip it:** 新条目没有落库却拿到成功重放回执，或者窗口无法完成但调用方获得 reused 结果；与“页中所有输入可追踪、最终页才推进水位”的合同不符。

   实际证据：`changed_replay_entries.observation.json`、`changed_replay_completion.observation.json` 与 `negative.xml` 后两项。条目例 source `7a1a84c3-3ddc-4d6c-92e1-f0c2c2f9426c`；完成标记例 source `076a8f6d-0b4f-4bf3-b5ed-3adcc222feea`，12:24:26+08 观察 receipt_count=1 且窗口仍未完成。源码见独立负例第 76、101 行。没有单独测试只变 watermark 的输入；其未参与回执匹配由上述源码静态确证，不能把它写成第六项实际复现。

   复验要求：完全相同请求正常 reused 且不再写业务；entries 内容/身份/顺序、completion 或 watermark 变化均冲突并无额外 callback/状态变化；旧 receipt 无指纹明确拒绝；前次 callback 失败后正确重试仍能提交。

## 独立真实命令与结果

完整 argv、cwd、+08 秒级起止、exit、源码/测试 SHA256 见同名 command.json；测试输入固定本 worktree。Python 为 D:/dianzi/backend/.venv/Scripts/python.exe，不安装新依赖。相关检查使用 `--no-cov` 是专项测试关闭覆盖统计，完整 unit 单独保留原门槛，未降低 60%。

| 检查 | 2026-10-15 +08 实际起止 | 数量与结果 | exit | 日志/回执 |
|---|---|---|---|---|
| `python -m pytest tests/unit -q --junitxml=.../unit.xml` | 12:21:04–12:21:22 | 206 passed，0 failed/skip，60.28%；1 Starlette 既有 warning | 0 | independent_unit.*、unit.xml |
| `python -m pytest` R03 jobs/cursor、原 T07/T16、T07/T08 contract、R03 security 七文件 | 12:21:04–12:21:09 | 59 passed，0 failed/skip | 0 | independent_related.*、related.xml |
| `python -m pytest -p review_plugin tests/integration/test_r03_executor_celery.py -v --no-cov` | 12:21:26–12:22:50 | 2 passed，0 failed/skip；实际进程 82.31 秒 | 0 | independent_celery.*、celery.xml、r03_*_processes.json |
| `python -m pytest ../_review/test_independent_negative.py -v --no-cov` | 12:24:25–12:24:27 | 5 failed，0 passed/skip；两项 Must fix 的实际反例 | 1 | independent_negative.*、negative.xml、5 observation.json |
| Ruff check 16 改动文件 | 12:22:51–12:22:51 | All checks passed | 0 | ruff.* |
| Ruff format --check 同 16 文件 | 12:22:51–12:22:51 | 16 files already formatted | 0 | format.* |
| mypy src | 12:22:51–12:22:52 | 60 source files，无问题 | 0 | mypy.* |
| `git diff <base> <source> --check` | 同名回执 | 无源码空白错误 | 0 | diff_check.* |

59 项分层核对为 52 实际 PG：R03 jobs 15、cursor 27、原 T07 6、T07 PG contract 1、security 3；另有 T16 显式内存 fixture 6、T08 recorded/fixture contract 1。实际 queue 2 项另运行 PostgreSQL、Redis 与原生 Celery 进程，未计为 live 来源能力。

实际 queue 第一项启动 interrupted_worker，然后中断，两个 replacement solo worker 与 beat 恢复。断言中断事务效果为 0；真实等待 60 秒 lease 到期，恢复后的 attempt=2，正常重复消息任务 attempt=1，两个 source 各只有一条业务效果。第二项使用不可用的本地 broker 证明不 published，等待持久交付退避，再实际投递并回滚发布事务后重投，业务效果仍一条。`review_plugin` 仅重定向测试模块 EVIDENCE 到本轮独立 run 目录；没有改变业务/断言/时钟/租约或 fixture handler 行为。

## 调用链与装配边界

真实 CBM 0.11.0 help 和 index_repository help 已读；独立项目 `recovery_r03_executor_review_1` fast 索引 backend/src，60 Python files，756 nodes / 3260 edges，partial/unusable/skipped 均 0，persistence=false，缓存仓外。固定 SHA/tree 和每文件 hash 见命令/manifest。

`get_architecture` 第一次通过 Windows argv 传数组字符串，被 CLI 当成单个 aspect 拒绝，exit 1 原日志保留；按真实 help 改为单值 overview 后 exit 0。它是工具参数错误，不是产品失败。`complete_job` inbound trace 找到 schedule_retry_or_fail、execute_job、consume_job，与 `rg` 调用搜索交叉核对，原调用方 expected_attempt 已更新。没有用图的推测标签替代源码判定。

已核对 PG authority payload/digest/scope、并发幂等与 rollback、两个 worker 的 SKIP LOCKED、owner+expected_attempt+expiry fencing、过期未接管及同 owner 旧 attempt 拒绝、retry_due/backoff/exhaustion、broker commit gap 重投、业务效果与状态同事务、页 savepoint/失败不推进、generation/release/restart、原窗口恢复、空页与最终水位、双流与迟到修订。上述既有成功边界由本次 59 和 queue 2 的断言支持，不能覆盖新增的五个失败反例。

生产 `EXECUTION_HANDLERS` 只有 `record_source_fetch_failure`（runtime.py:87）；它记录已经观察到的失败，不执行来源发现/抓取。来源 repository 没有实际生产调用方；旧知识发布仍产生 `knowledge_change`，当前无 handler，消费会 unsupported_job_type blocked。作者已明确披露，属于待 R04/后续装配缺口，不作为假称通过或额外猜测 bug；这轮不验收整个监测链。

## 资源收尾、证据完整性与未检查项

12:26:38+08 `resource_closure.json` 确认 schema 仍 0011、Redis DB8 0 key、自有 6 PID 均不存在；fixture 清理只针对两次独立随机 run 的 routing/delivery tag/pidbox 成员，没有 flush。实际清理移除 1 条本 run 未确认投递、5 个 pidbox 成员和 2 个队列关联 key；PG 审查历史保留。公共 Docker/PG/Redis daemon 没有停止/升级；资源已经通知主控释放。

`credential_scan.json` 扫描本 run 输出的完整私有 DSN、密码及每个密码 8 字符片段，0 hit；最终交付 manifest 继续给所有证据和独立脚本 SHA256。最终扫描初次还误把非秘密 DIANZI_TEST_RUN_ID 加入 secret 集，两个独立脚本命中该公开测试标识；原假阳性回执保留为 credential_scan_final_initial.json，收紧到私有 DSN/密码/密码八字符后为 0 hit，并未删改测试日志。初始 runner 曾写错预期 revision 名而 AssertionError，确认迁移实际 revision 后修正；未执行迁移/业务修改，也不算 PG 业务失败。首读与 worktree 创建控制台过程没有补造秒级回执。

未检查：Linux prefork 与 hard time limit、外部真实来源/模型/FOFA、连续监测/性能指标、前端/e2e/manual、全后端集成/全安全套件、0011 空库升级路径（主控 schema 审查范围）。live/not_run 或 blocked_live 保持；有限 solo queue integration 不代替 live。没有独立吞吐/时效/准确率成绩。

评分证据仅支持 F1 的任务/游标基础、E1 的事务/隔离/有界恢复、P1 的到期恢复能力；两项失败使游标切片不能放行。原 T07-C01–C06、T16-C01–C06 保留，整卡最终前置和 R20/R06 等切片不由本次签收。没有冻结合同/计划或阈值变更；缺陷与装配不足如上，不把静态或 fixture 解释成完整产品能力。

下一任务建议：主控冻结前向 receipt 指纹模型/迁移（如必要），原作者在允许范围修复 1、2，重新冻结源码与日志，再进行新的有界定向独立复验；不先签整阶段。

Verdict: fix 1 and 2 first. Not checked: 上述 live、部署与跨切片最终验收。

报告完成与证据封存：2026-10-15T12:30:32+08:00；资源关闭的独立实测仍以 12:26:38+08 收据为准。
