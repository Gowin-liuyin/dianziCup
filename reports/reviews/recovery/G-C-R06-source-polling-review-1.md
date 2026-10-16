# G-C · R06 自动轮询切片独立审查 1

What this change does: 此改动通过可信部署开关，在既有 Celery beat 中每 60 秒安排固定公开来源轮询。轮询器仅在一个 PostgreSQL 事务内写入标准 SourcePageRequest 与既有 job/payload/outbox；实际来源 IO 仍交给原 source worker。

记录时间：2026-10-15T22:04:55+08:00。审查者：/root/r06_periodic_collection_independent_review，未参与被审实现。结论只覆盖 **R06:T49/T54 自动轮询装配子切片**；不签整 R06、原 T49/T54、G-C、九来源 live 或最终验收，不修改 accepted 状态。

## 冻结范围与依据

- 固定基线：`52433474f66a900c56ee6d5478337b0ec83d6eda`。
- 被审冻结：`93c458a0f97b65198d1fb690d42634b77342bb3c`。
- 独立干净工作树：`D:/wt/r06-source-polling-review-1`；分支 `codex/r06-source-polling-independent-review-1`。从冻结 SHA 新建，初始 git status 为空；未读作者活动工作树，也未修改业务、公共状态、金标、门槛或计分分母，未 commit/push。
- 相对基线恰为 8 文件、494 行新增：`settings.py`、新 `source_polling.py`、`workers/runtime.py`、两个 source_polling 测试、`CR-R06_periodic_collection.md`、`source_polling.md`、`infra/compose/compose.yaml`。无新增事实表或迁移。
- 已读实际 AGENTS、执行地图、task_state 和交接、manifest 的 R06 工作包、原 T49/T54、03/04/05/07 合同及 09 运维合同、新轮询小合同与运行手册。R06 在冻结公共状态仍是 pending；本报告不替作者或主控登记完成。
- 使用最新版 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`。按具体可触发行为审查，不以样式或缩行偏好制造 Must fix。

## 独立追踪与可观察行为

官方 CBM：WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` **0.11.0**。只索引本工作树 `backend/src`，独立 `XDG_CACHE_HOME=/tmp/dianzi-cbm-r06-source-polling-review-1-cache`，`CBM_ALLOWED_ROOT` 同 src 根；没有索引 secrets、holdout、报告或 fixtures。11 条 version/index/architecture/trace 命令均退出 0；索引 1,246 nodes / 6,267 edges，未索引、跳过、partial、unusable 文件均 0。追踪 poll_due_public_sources、enqueue_due_source_collections、enqueue_source_page、build_celery_application、dispatch_pending_jobs、consume_job、build_source_page_handler、execute_job，并以 rg 核对调用者、配置、测试和 compose 默认入口。

已确认：

1. `settings.py:64` 默认 false；compose `:20` 显式透传。`runtime.py:64–69` 只在开启时增加原 60 秒 beat 项，task 在 `:169–171` 注册，原 source handler 在 `:98–104` 装配。已用注册 task 的 `.run()` 验证 disabled 不触碰 build_engine；任务不接受 URL、租户等任意参数。
2. `source_polling.py:29–41` 的九 key 与 CATALOG_SOURCES 一致：vLLM 1,800 秒，其余 3,600 秒；`:54–60` 向下取 UTC 桶，微秒临界点及 +08/-05 时区得到相同窗口。每 root 请求固定 live、5 页，键包括 source 和 UTC bucket，payload 不包含每次 tick 的变化时间。
3. `source_polling.py:101–106` 先检查 manage_public_sources、无租户 system_admin，再取得事务级 PG advisory lock。四个真实 Python 进程同时首次 tick，仅一个创建九个 root；其余零个。另一个新进程读取同轮次不新增 root。已有 PG 唯一幂等与 payload digest 机制继续复用。
4. `source_polling.py:63–94` 有界读取最多 501 个 active 请求，SQL 在取回前对 >4,096 字节 payload 置空，校验失败明确抛错。正常空队列、缺 payload、空字节、非法 JSON、未知来源、额外 tenant、无时区和页数 0 已分别测试；4,096 字节合法填充请求通过，4,097 拒绝，失败轮次没有创建额外 job/outbox。
5. queued/running/retry_wait/waiting_approval 的手动或 continuation 工作均延后对应源；其他源仍可调度。terminal 失败和无关任务不被当成活跃来源。manual 与自动复用原源身份、PG 游标、source/stream 租约及注册事务锁，没有另一套来源真值。
6. 一个进程创建九个 job/outbox 后、提交前被真正 kill，PG 记录回滚为零，poll 锁释放；随后正常 tick 可创建九个。原主动抛错的事务回滚测试也通过。数据库错误转为明确固定错误，SourcePollingError 保留异常；均未返回 scheduled/queued=0 冒充成功，engine 最终释放。
7. 真实默认 60 秒 beat 经隔离 Redis 到原 runtime poll task，原 dispatch/consume 走 PG/outbox 到 source worker。测试显式注入 **空 OSV JSON transport**，其他八源明确 fixture_unselected_source/waiting_approval；只对 OSV 原 handler 的 FetchAttempt、live cursor 和 page receipt 提交作断言，不借坏样本内容证明语义。停用后重启 worker/beat，真实观察 65 秒没有新增自动 root；已有九 root ID/payload hash 保留，另一个已入队手动任务仍完成，第二页回执保留。

队列边界的精确含义：`:83` 检查的是**本轮入场时 >500**。独立负例在 500 个同源 active 下新增另外 8 源，达到 508；下一 tick 明确报错，数目保持 508。它提供单 tick 最多 9 的增长界和超过入场阈值后的拒绝，不是最终队列严格 ≤500 的保证。小合同用的是 “>500 本轮失败”，未冻结严格最终上限；因此此事实是使用限制，不在本审查中擅自扩成新增 Must fix 或修改阈值。

## 实际命令与结果

证据目录：`reports/runs/recovery_r06_source_polling_review_1_20261015/`。主要命令工作目录均为独立工作树 `/backend`。`*.command.json` 记录完整 argv、cwd、+08 起止和退出码；`commands.json` 汇总，CBM 另见 `cbm.commands.json`。原质量覆盖门为 60%，没有改配置或排除文件。

| 命令/检查 | 退出码 | 实际结果与日志 |
|---|---:|---|
| `uv sync --offline --frozen --extra semantic` | 0 | 本 WT 自有 .venv；92 锁定包，`own_uv_sync.log` |
| `pytest tests/unit/test_r06_source_polling.py --no-cov -q` | 0 | 17 passed；`unit_key.log` |
| `pytest tests/integration/test_r06_source_polling_pg.py --no-cov -q` | 0 | 10 真实 PG passed；`pg_original.log` |
| 报告目录 `test_review_boundaries.py --no-cov -q` | 0 | 24 passed，1 个外置 fixture 标记未注册 warning；`pg_new_boundaries.log` |
| 报告目录 `test_review_runtime_errors.py --no-cov -q` | 0 | 4 passed；`runtime_errors_recheck.log` |
| 报告目录 `test_review_broker.py --no-cov -o markers=real_pg -q -s` | 0 | 1 passed / 130.83 秒；实际原 60 秒 beat、65 秒 disabled 重启；`broker_default_chain_recheck.log` |
| `pytest tests/unit tests/contract tests/security -m 'not real_pg and not real_services and not real_search_tls' --cov-report=term --cov-report=xml:.../coverage_own_env.xml -q` | 0 | 1,777 passed、10 deselected、1 已有 StarletteDeprecationWarning；74.15% ≥ 原 60%；`pure_own_env.log` |
| `ruff check src tests` | 0 | `own_ruff.log` |
| `ruff format --check src tests` | 0 | 220 文件保持格式；`own_format.log` |
| `mypy src/ai_intel --cache-dir .../mypy_cache_own` | 0 | 93 source files；`own_mypy.log` |
| `git diff --check 5243347... 93c458a...` | 0 | `diff_check.log` 为空 |
| 专库 public 前后核对 | 0 | 前后均 0 关系，完全一致；`public_before.json` / `public_after.json` |
| CBM version/index/architecture/8 traces | 全 0 | `cbm_*.log` / `cbm.commands.json` |

以下实际红日志保留，没有删失败、改 skip 或改门槛：

- `pure_regression.log`：共享 `D:/dianzi/backend/.venv` 加本 WT PYTHONPATH，1,777 passed / 10 deselected，但 52.19% 导致退出 1。XML 同时统计 `D:/dianzi/backend/src` 与独立 WT 源码；重复分母 12,248 行。建立自身 editable .venv、同原命令/门槛复跑后只统计冻结源码 8,533 行，74.15% 且退出 0；这是审查仪器路径问题，不是产品回归。
- `broker_default_chain.log`：1 failed，退出 1。审查 fixture 将 str 传给需要 Path 的 ContentStore，两个子进程启动即 AttributeError，85 秒观察超时；启动日志完整保存。只修审查 fixture 为 Path 后复跑上述实际链成功，没有改业务代码。
- `runtime_errors.log`：2 failed / 2 passed，退出 1。审查 MagicMock 的 Session context 返回另一个 mock，检查错误的 begin 对象导致 AttributeError；明确设置 __enter__ 返回同一 session 后，原业务错误传播断言 4 passed。未修改产品异常处理。

## 隔离、停用和回滚

真实 PG 仅使用 `test_dianzi_r06_catalog_polling_20261015`、`DIANZI_TEST_RUN_ID=r06_catalog_polling_20261015`，沿用 test_r06_catalog_documents_pg 的 UUID schema fixture 和前向 migrations。凭据仅在进程内从授权 WSL connection.json 读取并换专库，不输出 DSN 或密码。专库 public 前后均为空；未触碰正在观察的 `test_dianzi_r04_pipeline_20261015`。

实际 runtime 的 connect_args 会设置 timeout options，因此 broker fixture 在**该专库**临时设 database-local search_path 指向自己的 UUID schema，使原 build_engine 保持未修改。结束后已 RESET，并查询确认没有残留 search_path 设置；未 ALTER 共享 role、未 downgrade、未改公共表。Redis 用 DB15 的 UUID global_keyprefix 与专有 queue；只删除已停本 run 的 key，非本 run key 保留。复查未留下 broker_fixture_entry.py 进程。worker/beat 子进程结束码 1 为 Windows 上审查主动终止的实际退出码，receipt 写明 review-controlled termination，不冒称自然退出 0。

停用的产品路径是关闭可信开关并重启 worker/beat，保留历史、游标与已入队任务；不清任务，不重置 cursor。无需数据库迁移或破坏性回滚。实际 65 秒恢复检查证明本切片行为，不能替代 R20 整套恢复/告警或 R22 长时间稳定性验收。

自动审批拒绝删除本次生成的 mypy 缓存，返回“blocked by policy”。缓存已保留；证据 manifest 将明确列为非交付衍生缓存，不影响原日志和测试结果。

## 缺陷、依赖与未查范围

本冻结调度差异中，未发现经独立复现的新增 Must fix 或 Should fix。PG/事务/权限/配置/默认装配及停用行为已按上述证据核验；未用作者通过日志代替独立结论。

基线 5243347 的新七源 worker 另审已发现两个 Must：CAC 缺最后生效正文仍标 full_text、OSV 非法时区/超精度被错误接受。它们不是本轮询器新增代码的问题，但**来源语义与 live 仍未通过**，须在各自审查中修复复验。本切片的调度、幂等和装配不依赖这些坏样本语义：只依据合法 SourcePageRequest、PG key/status/outbox 与显式空 OSV 页验证，不核发新七来源/整个自动采集成功。

未查：实际九来源外网、CNNVD 认证/API、签名 webhook、EPSS/KEV、付费模型或资产测绘、Docker/Linux prefork 容器进程（本次实际 worker 为 Windows native solo）、正式漏采参考集、发布到采集 ≤6h/P0 五分钟时效、六小时或七天持续观察、T49 完整指标告警、R20 恢复、源内容真实性及政策适用性。模拟 UTC 桶边界不计作持续运行。vLLM 30 分钟/其余 60 分钟是已冻结当前策略，不能证明五分钟目标。

评分证据仅支持 F1/E1/P1 中“固定来源有界持续轮询调度、PG 恢复幂等和装配可测”的能力；来源广度、真实时效及整个 R06/T49/T54/G-C 仍需独立后续材料。下一步建议修复并复验来源归一化两 Must，再按受控资源与独立参考集验证实际来源与时效。

**Verdict: Ship.** 限定为冻结 `93c458a0f97b65198d1fb690d42634b77342bb3c` 的自动轮询装配子切片；不表示依赖的来源语义、live、整任务或阶段已接受。
