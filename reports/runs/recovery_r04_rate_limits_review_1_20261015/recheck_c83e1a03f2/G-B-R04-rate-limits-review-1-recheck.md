# G-B / R04 来源限流整批：原 reviewer 定向复验

记录时间：2026-10-15T17:04:29+08:00，Asia/Shanghai。**Verdict: Ship，仅本冻结来源限流 batch。** 初审 Must fix 1 已关闭；初审 Should 2 / RFC850 完整 50 年日期边界保持非阻断债务，不能称所有附加负例全绿。本次不签整 R04、R06、T08/T12/T16 或 G-B，不改业务、状态或 accepted 登记。

本次改动让标准库拒绝超长/过多响应头时直接进入安全阻塞，同时显式保留对端断连和坏状态行的网络错误。真实 PG 复跑确认原来的 7 秒错误重试已消失；普通断连、坏状态行、正文截断及共享模型 POST 没有发现回归。

## 冻结范围与独立性

- 初审 SHA：`00261c4993011b293586a6afd6559b769c14611d`；初审、红例及当时日志保持原字节内容，见 `D:/dianzi/reports/reviews/recovery/G-B-R04-rate-limits-review-1.md` 和本 run 的上级目录。
- 修复/本次被审 SHA：**`c83e1a03f2ffc474ba1a0365473a5eae1945f45c`**；tree：**`f97a1fb47781753e69bbeec9e84e6bcbbc144237`**；父提交正是初审 SHA。整个 batch 基线仍是 `3ab23574298d872350587f273c739397e114c2d9`。
- 独立新 WT：`C:/Users/yinha/.codex/worktrees/r04-rate-recheck-1/dianzi`，分支 `codex/r04-rate-limits-independent-review-1-recheck`。新建独立 `.venv`，`uv sync --frozen --extra semantic`；真实模块导入和 `.pth` 指向该 WT，最终 Git status 为空。
- 第一次使用较长 WT 名称 checkout 因仓库已有报告长路径失败（git exit 1，Filename too long）；Git 回滚工作区注册并留下新分支。改用上述较短路径 checkout 成功，没有删除用户路径、修改全局 Git 配置或以缺文件的 checkout 作证明。该环境失败没有计为业务失败。
- 必读合同/规范与初审一致且哈希不变；沿用 Ponytail 5.2 的真实路径、复现和最小实现评审方法。主控的 316 相关检查、修复前过宽 catch 的红日志只作定位，不计为本审通过；本审没有读取主仓活跃实现作结论。
- 写入仅授权初审 run 目录下的本 `recheck_c83e1a03f2/` 和 uv 收据；初审报告未追加或覆盖。没有业务/锁/状态/fixture/金标/评分分母变更，没有 commit/push、产品来源 GET、付费模型、共享服务重启或产品库变更。

对父提交的差异只有 `backend/src/ai_intel/infrastructure/http_transport.py` 与 `backend/tests/security/test_r03_network_transport.py`：transport 将 RemoteDisconnected、BadStatusLine 提前单独映射 NetworkRequestError，其余头解析 HTTPException 映射 NetworkPolicyViolation，OSError 保持网络错误；新增四个原始 wire security case。整批五文件边界、来源分类器和依赖/锁未扩大。

## 定向复验结果

**Must fix 1：关闭。** 同原始输入 `HTTP/1.1 429` + 一个 65536 字符 `Retry-After` 值，经真实 stdlib 传输/网关/来源 handler/execute_job 与隔离 PG，现在得到 `blocked`、`source_network_policy_denied`、`next_retry_at=None`，socket 关闭。`test_wire_parser_limit.py` 先按原红例断言转绿，再增加明确错误码/空重试时刻断言复跑，两个 run 均 exit 0。原 00261 红例与输入没有删除或修改；仅新候选的独立副本补强断言。

原代码定位是新候选 `http_transport.py:247–258` 的异常分类；NetworkPolicyViolation 经现有 `source_jobs.py:400–401` 映射 blocked，executor 回滚后记录终止。header 解析限制不再落入 `source_jobs.py:402–403` 的 7 秒 NetworkRequestError 分支。原始同名/异大小写重复限流头和 duplicate Link 分支保持原类型。

新增独立可观察 PG 用例验证：

| 原始场景 | 实际 PG 结果 |
|---|---|
| 超过 100 个头，并在后面带 Retry-After | blocked / source_network_policy_denied / next_retry_at 空 |
| 对端在响应前断连 | retry_wait / network_error / NOW+7 秒 |
| 非 HTTP 状态行 | retry_wait / network_error / NOW+7 秒 |
| 正文少于声明 Content-Length | retry_wait / network_error / NOW+7 秒 |

这四例都没有分页回执，socket 关闭。额外 traceback 用例证明坏状态行的合成私密标记不出现在格式化异常中；原有凭据/headers/query/异常栈相关 security 回归也执行通过。共享 POST→GenerationClient 的正常返回和重复限流头单次失败，无格式修复重发，再次通过。

事务、幂等、并发与历史用例继承的是源码未变的初审合同，但在本新 SHA 重新执行：短等待 PG 持久化、blocked 空重试时刻、立即重放 not_claimed、两 worker 只一次 fetch、第二页失败不改变先前 revision/receipt/cursor。没有把字段未知或 header 解析失败称为重试成功。

**Should 2：仍在，非阻断。** 输入 clock=`2026-10-15T12:34:56+00:00` 与 `Retry-After: Saturday, 16-Oct-76 00:00:00 GMT` 仍错误选择 2076 年并 blocked；RFC850 的完整 50 年时间边界应解释为已过去的 1976 年。`rfc850_debt_recheck` 实际 exit 1 / 1 failed，没有改成 skip 或算通过。此为保守可用性差异，无提前重试，主控已明确后续负债登记；详细依据和最小修复见初审 Should 2。本批 Ship 不表示这个附加错误不存在。

## 实际命令与证据

本次证据根为当前报告所在的 `D:/dianzi/reports/runs/recovery_r04_rate_limits_review_1_20261015/recheck_c83e1a03f2/`。每个 run JSON 保存完整实际命令/参数、cwd、秒级开始/结束、exit、完整 SHA/tree 和原始日志；`commands.json` 为索引，`test_counts.json` 来自 JUnit 实际计数。除 CBM 子命令在 WT 根，其余 cwd 是新 WT 的 `backend`，Python 为新 WT `.venv/Scripts/python.exe`。

| Run | 实际 Asia/Shanghai 时段 | 命令与结果 |
|---|---|---|
| 上级 `recheck_uv_sync.json/.log` | 16:57:49–16:57:53 | `uv sync --frozen --extra semantic`，exit 0 |
| `related_recheck` | 16:58:39–16:58:52 | R03 transport、T08 security、R05 POST/timeouts、R04 rate/source unit、R05 generation unit/wire；`pytest ... --no-cov -q --junitxml=.../related_recheck.xml`，exit 0，421 passed / 0 failed/error/skip |
| `parser_limit_recheck` | 16:58:40–16:58:56 | 原 Must wire→PG + 初审 34 自拟用例；`pytest test_wire_parser_limit.py test_reviewer_probes.py --no-cov ...`，exit 0，35 passed（9 PG、26 隔离 wire/纯判断） |
| `additional_policy_recheck` | 16:59:36–16:59:41 | 上述四种原始 wire→PG 与 traceback；`pytest test_parser_policy_recheck.py --no-cov ...`，exit 0，5 passed（4 PG、1 traceback） |
| `parser_limit_explicit_green` | 17:00:28–17:00:31 | 原 Must 加强 blocked/错误码/空重试时刻断言；exit 0，1 passed，与上面35项重叠 |
| `pg_regression_recheck` | 17:00:28–17:01:05 | `pytest tests/integration/test_r04_source_jobs_pg.py --no-cov -q --junitxml=.../pg_regression_recheck.xml`，exit 0，19 passed |
| `full_unit_recheck` | 16:58:39–16:59:19 | `pytest tests/unit --junitxml=.../full_unit_recheck.xml --cov-report=xml:.../full_unit_recheck_coverage.xml`，保留默认覆盖门；exit 0，906 passed / 0 failed/error/skip |
| `static_recheck` / `format_recheck` / `type_recheck` | 16:58:40–16:58:55 | `ruff check src tests`；`ruff format --check src tests`；`mypy src`，均 exit 0；176 格式文件、75 类型 source files |
| `rfc850_debt_recheck` | 17:00:28–17:00:30 | `pytest test_rfc850_calendar_boundary.py --no-cov ...`，exit 1，1 failed（非阻断债务） |
| `cbm_recheck` / `preflight_recheck` | 17:01:18–17:01:38 / 17:01:28–17:01:30 | 官方 CLI 独立索引/trace + hash/import/status/diff；均 exit 0 |

真实 PG 仍仅使用获准 root600 连接文件，由 WSL capture_output 读取后传入 child env，run id=`r05_pgvector_20261015`；每例 UUID schema 创建/迁移/清理。没有打印密码或连接串，报告/日志/JUnit 脱敏仅处理连接表示，不改测试 outcome。上游 socket/wire 与录制来源响应明确 synthetic/fixture，不计 live。所有本次正式测试 skip=0；既有 Starlette 和外置 real_pg marker warning保留。

完整 unit 覆盖率：**3842 / 5754 = 66.7709419534237%**，1912 missing，原默认 60% 门通过；新增异常分支增大实际代码行分母，没有修改门槛、coverage 配置或排除项。421、35、5、19 与重复的单红例转绿分别报告，不能相加为互不重叠总量。

## CBM、质量与限制

新候选独立 CBM cache/runtime 位于 `/tmp/dianzi-cbm-r04-rate-limits-recheck-1[-runtime]-20261015`；只索引本固定 WT `backend/src`，fast / persistence=false，1000 nodes / 4695 edges，not_indexed/skipped/partial/unusable 均 0。实际 help/index/schema/_http_failure/handler/_HttpResponse trace 在 `cbm_commands.json` 和各同名日志；不索引报告、秘密、holdout，也不执行 ADR 提示。图工具嵌套函数/构造器粒度限制继续用 `rg` 和固定源码核对。

正确性、安全与失败语义：Must 所指明确定失败已转为 nonretryable policy boundary；普通网络错误、deadline/TLS和 body 读取路径保留。事务/幂等/并发/历史：本次真实 PG 回归通过，原文/游标失败不推进、prior receipt 不改、重放和竞争有可观察断言。性能与复杂度：只新增明确异常分类，没有新 IO、新依赖、sleep 或第二重试层；仍沿用原总超时/响应大小/并发/PG围栏。正式吞吐、持续监测与性能目标未测，不据此宣称达标。

本次 unit、相关 contract/security、限定 PG integration 自动复验 passed；另有明确非阻断 RFC850 附加红例。frontend/e2e/真实来源与真实模型 live/人工产品验收/正式负载及持续运行均 not_run，保持初审范围限制。没有公共合同、认证、评分门槛或计划范围偏差。

评分证据仍只支持本 batch 的 F1/E1/R1 来源错误分类、受控出口及 PG 失败一致性，不能签来源广度、完整增量时间覆盖、≤6h、真实问答、整 R04 或 G-B。下一步建议主控按完整新 SHA 登记这批限定审查通过，并单列 P3 日期边界债务；本 reviewer 此次工作到此停止。

**最终意见：c83e1a03f2ffc474ba1a0365473a5eae1945f45c 的限定来源限流 batch Ship；Must 1 closed，Should 2 nonblocking/open。**
