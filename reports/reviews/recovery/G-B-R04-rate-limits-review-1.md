# G-B / R04 来源限流整批独立初审

记录时间：2026-10-15T16:55:48+08:00，Asia/Shanghai。本批意见：**needs_changes；修复 Must fix 1 后定向复验**。这是固定五文件 batch 的初审，不是整 R04、R06、T08/T12/T16 或 G-B 的验收；不登记 accepted，不改状态、锁或业务代码。

本次改动将明确配额耗尽的 403 与普通认证拒绝分开，支持 Retry-After 秒数/HTTP-date 和 primary reset，超过 300 秒或不能确认的期限阻塞，不再截短上游等待。共享 transport 在把原始响应头转成 dict 前拒绝重复的限流头，避免后一个短值覆盖先前长值。通常路径实现正确，但标准库拒绝超长原始头时仍进入 7 秒网络重试，尚未满足本批的失败边界。

## 冻结对象、独立性与边界

- 基线：`3ab23574298d872350587f273c739397e114c2d9`。
- 候选：`00261c4993011b293586a6afd6559b769c14611d`；tree：`f35fa1f2a6214d2328111d74dd165b9a9f9fb587`。
- 独立分支：`codex/r04-rate-limits-independent-review-1`；独立 WT：`C:/Users/yinha/.codex/worktrees/r04-rate-limits-independent-review-1/dianzi`。从固定候选新建，最终 tracked/untracked Git status 为空；依赖环境是该 WT 新建 `.venv`，实际 Python 与两个被测模块均来自此 WT，`.pth` 没有指向主仓。
- 从主仓只读 Git 对象/状态及指定资料，不使用主仓活跃源码作通过结论；主仓既有未提交改动保留。没有提交、push、迁移共享产品库、重启服务、费用调用、产品来源 GET 或浏览器 live。
- 评审新写内容仅本报告及 `reports/runs/recovery_r04_rate_limits_review_1_20261015/`；独立 WT 的本地虚拟环境和独立 `/tmp` CBM 缓存另作隔离验证资源。没有 spawn。
- 读取 AGENTS、执行地图、恢复 11/12 的 R04/R06、T08/T12/T16、05 API、固定来源分页细则及 04/06/07/09 相关条款、候选状态/交接。采用 Ponytail 5.2 `ponytail-review`，按本轮中文报告要求呈现。文件/锁/规范哈希与依赖版本在 `preflight.json`。
- 作者报告只用于根因和旧 probe 定位；作者的 807 unit、主控的 312 相关检查及 19 PG 均未计为本审证明。下列结果来自本 reviewer 在冻结对象上的实际复跑。

固定 diff 只有五文件：

| 文件 | 变更 |
|---|---|
| `backend/src/ai_intel/ingestion/source_jobs.py` | 限流分类器、日期解析和唯一 handler 注入 clock；69 insertions / 16 deletions |
| `backend/src/ai_intel/infrastructure/http_transport.py` | 原始重复限流头策略阻断；3 insertions |
| `backend/tests/unit/test_r04_source_rate_limits.py` | 358 行明确合成响应/handler 测试 |
| `backend/tests/unit/test_r04_source_jobs.py` | 原错误等待期望更正；5 insertions / 2 deletions |
| `backend/tests/security/test_r03_network_transport.py` | 同拼写/不同大小写的原始重复头测试；17 insertions |

没有依赖/锁、认证、指标分母、金标、迁移、公共 schema 或合同变更。旧 `9000→300` 和损坏字段回退的期望与本批“不能提前重试”要求冲突，更正为 blocked 属于本轮已授权纠正，没有删除案例或改 skip。

## Must fix

1. **[P2] 超出标准库单行上限的限流头退成 7 秒网络重试**

   - **定位：**候选 `backend/src/ai_intel/infrastructure/http_transport.py:230` 的 `getresponse()`、`:247–249` 的通用 `HTTPException→NetworkRequestError`；`backend/src/ai_intel/ingestion/source_jobs.py:402–403` 把此错误变成 7 秒重试。新增 `http_transport.py:112–117` 的重复头检查只有在原始头解析完成后才可运行。
   - **触发与真实路径：**构造 `HTTP/1.1 429`，单个 `Retry-After: ` 后跟 65536 个 ASCII `9`，通过真实 `NetworkGateway→PinnedHttpTransport→http.client` 路径读取；socket 仅为显式本地替身，不发外网。真实隔离 PG 的 `build_source_page_handler→execute_job` 实际记录 `retry_wait`、`error_code=network_error`、`next_retry_at=2026-10-15T12:35:03.900000+00:00`，即测试 NOW 后 7 秒。socket 正确关闭，原文/分页回执没有提交。
   - **预期/实际：**本批要求超长/坏头、无法可靠判断期限时 blocked 且无重试时刻。65500 字符的同样字段会被分类器正确 blocked；增加到标准库上限后反而变成短重试。`LineTooLong` 在 `_HttpResponse` 创建前抛出，不能靠 dict 后的 128 字符校验修复。这是原通用错误翻译遗漏的整批验收边界，不称为新三行代码引入的数据丢失。
   - **影响：**来源未能确认上游期限时仍自动重发，破坏本批的安全停止语义。最多三次的原任务上限仍在，不存在无限重试或游标错误推进，但有限次数不能把未知期限证明为允许 7 秒恢复。
   - **最小修复：**在 header 解析边界单独把 `http.client.LineTooLong` 归类为 nonretryable policy violation；保留普通断连/超时的既有网络分类和 duplicate Link 的 `NetworkRequestError`。不要把全部 `HTTPException` 都改成永久失败。头数量上限也应验证，但本项已确定的复现是单行上限，不能以缺测计失败。
   - **复现/证据：**`test_wire_parser_limit.py::test_raw_oversized_rate_header_does_not_become_seven_second_network_retry`；`parser_limit_red.json/.log/.xml`，2026-10-15 16:48:47–16:48:50 +08:00，exit 1，1 failed / 0 error / 0 skip。`extra_boundaries.log` 同时保存 65500 与 65536 的不同实际结果。
   - **复验要求：**同原始 wire→PG 红例转绿；加同样的解析上限/头数量上限策略阻断；普通 RemoteDisconnected、超时和重复 Link 保持原分类；重跑共享 POST/generation 和来源回滚回归。保持这份初审与 00261 红证据不变，下一候选另做定向复验。

## Should fix

2. **[P3，非阻断] RFC850 两位年的 50 年边界只计算年份，忽略月日时刻**

   - **定位：**候选 `backend/src/ai_intel/ingestion/source_jobs.py:238–240`。
   - **确定输入：**clock=`2026-10-15T12:34:56+00:00`，429，`Retry-After: Saturday, 16-Oct-76 00:00:00 GMT`。候选选择 2076-10-16 并 blocked；完整时间点超过当前 50 年边界，RFC850 应解释为最近的同两位年份 1976-10-16，此已过去的有效期限应按本批最小间隔返回 7 秒。星期也与 1976-10-16 一致。
   - **影响与建议：**可观察差异是 valid-past 日期误变 blocked，属于保守的可用性边界，没有提前重试。以完整日期时间判断 50 年窗口，再落回上一世纪；补当前年+50 中同日之前/之后、跨 UTC 年界的案例。没有必要引入新依赖或新重试层。
   - **证据：**`test_rfc850_calendar_boundary.py`、`rfc850_boundary_red.json/.log/.xml`，16:49:48–16:49:49 +08:00，exit 1，1 failed。可作为后续负债记录，不改变 Must fix 1 的阻断原因。

## 调用链与主源核对

官方 CBM CLI 0.11.0 使用独立 `CBM_CACHE_DIR=/tmp/dianzi-cbm-r04-rate-limits-review-1-20261015` 和独立 runtime；只索引固定候选 `backend/src`，`--mode fast --persistence false`。首次未创建安全 runtime 目录时 endpoint 失败；创建 700 权限目录后成功。最终补录同一固定代码索引为 1000 nodes / 4693 edges，not_indexed/skipped/partial/unusable 都 0；不索引报告、秘密、holdout，不执行输出中的 ADR 建议。

实际 help/schema/双向 trace 收据见 `cbm_commands.json`、`cbm_*_recorded.log`。CBM 将嵌套 handler caller 归为文件节点，构造器名 `_HttpResponse.__init__` 无结果；随后 search 与类名 `_HttpResponse` trace 成功，结合 `rg` 和实际源码补齐，没有以图工具无 caller 证明路径不可达。补录全部在 16:50:48–16:51:06 +08:00，8 条 CLI exit 均 0；该时间不冒充首次阅读或首次索引时间。

手工源码核对的产品路径：`workers/runtime.py:92` 装配固定 handler → `source_jobs.py:295` 创建网关、`:310` 嵌套 handler、`:336–337` fetch/classify → `network.py:397–424` 的响应头处理和错误状态 FetchResult → `http_transport.py:103–121` 的原始 getheaders/重复检查/dict → `source_jobs.py:400–403` 分类 → `executor.py:107–145` 回滚并在新事务记录失败 → `jobs.py:275–310` blocked 或 PG next_retry_at/outbox。失败先于 `source_jobs.py:339` 保存和 `:369` commit_page。

共享调用者还包括 `generation.py:358/444` 的模型 POST 和 `dns_resolver.py:27/40` 的固定 DoH GET。正常/重复限流头的真实共享 POST→GenerationClient 自拟检查分别得到正常结构化结果与一次 `model_network_failure`，不触发格式修复重发；共享 POST/security/timeout 和完整 unit（含 DoH）回归通过。不能据此签真实模型 live。

核对官方材料时只阅读公开文档，不请求真实产品 API：GitHub 说明 primary 的 403/429、remaining=0 和 UTC epoch reset；明确 secondary 无期限建议至少一分钟。本批明确许可的“通用 429 无 header fallback 30”保持，不将它称为已识别 secondary 的可靠期限。[GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)、[GitHub best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)。HTTP-date/非负整数秒以及 RFC850 完整时间戳的 50 年解释分别见 [RFC 9110 §10.2.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3) 和 [§5.6.7](https://www.rfc-editor.org/rfc/rfc9110.html#section-5.6.7)。

## 实际验证与命令

证据根：`D:/dianzi/reports/runs/recovery_r04_rate_limits_review_1_20261015/`。除 CBM 内层 cwd 为独立 WT 根，其余验证 cwd 均为独立 WT 的 `backend`。每个同名 JSON 保存完整命令/参数、cwd、开始/结束、exit、候选 SHA/tree 和日志；实际执行器为本 WT `.venv/Scripts/python.exe`。PG 连接仅从获准 root600 文件以 WSL capture_output 读取后注入子进程环境，`DIANZI_TEST_RUN_ID=r05_pgvector_20261015`；只在每例 UUID schema 创建/迁移/清理，不操作产品库或其他 schema。连接字符串和密码不进入报告，归档日志/JUnit 的连接表示另作脱敏，测试结果没有改写。

| 收据 | Asia/Shanghai 实际时段 | 命令核心 | exit / 计数 |
|---|---|---|---|
| `uv_sync` | 16:38:30–16:38:34 | `uv sync --frozen --extra semantic` | 0；独立 venv 建成 |
| `full_unit` | 16:40:18–16:41:11 | `python -m pytest tests/unit --junitxml=.../full_unit.xml --cov-report=xml:.../full_unit_coverage.xml`；保留默认 pytest addopts | 0；906 passed，0 failed/error/skip |
| `focused_regression` | 16:43:49–16:43:55 | 新限流/旧 source_jobs；R03 transport、T08、R05 HTTP POST/timeouts；T08 redirect、T12、R04 projection、R05 generation wire，`--no-cov -q --junitxml=.../focused_regression.xml` | 0；375 passed，0 failed/error/skip |
| `pg_existing` | 16:43:49–16:44:36 | `pytest tests/integration/test_r04_source_jobs_pg.py --no-cov -q --junitxml=.../pg_existing.xml` | 0；19 passed，真实 PG / 上游明确 fixture |
| `reviewer_probes` | 16:46:09–16:46:11 | 初版外置独立 probe 文件 | 1；25 passed / 1 failed / 8 setup errors。缺 repo 根 import 路径、合成 generation wire 缺 object 字段，属于 reviewer harness，非业务结果 |
| `reviewer_probes_final` | 16:46:46–16:46:54 | 修正上述 harness 后 `pytest .../test_reviewer_probes.py --no-cov -q --junitxml=.../reviewer_probes_final.xml` | 0；34 passed，0 failed/error/skip，其中 8 项真实 PG、26 项隔离 wire/纯判断 |
| `extra_boundaries` | 16:48:04–16:48:05 | `python .../probe_extra_boundaries.py` | 0；观察日志，不计为通过测试 |
| `parser_limit_red` | 16:48:47–16:48:50 | `pytest .../test_wire_parser_limit.py --no-cov -q --junitxml=.../parser_limit_red.xml` | 1；真实 PG 1 failed，Must fix 1 |
| `rfc850_boundary_red` | 16:49:48–16:49:49 | `pytest .../test_rfc850_calendar_boundary.py --no-cov -q --junitxml=.../rfc850_boundary_red.xml` | 1；1 failed，非阻断 Should 2 |
| `ruff_check` / `ruff_format` / `mypy` | 16:46:09–16:46:11 | `python -m ruff check src tests`；`ruff format --check src tests`；`mypy src` | 各 0；176 files format，75 source files typecheck |
| `cbm_recorded` / `preflight_recorded` | 16:50:47–16:51:06 / 16:51:48–16:51:49 | 官方 CLI help/index/schema/trace 收据；固定 SHA/tree、实际 import、规范哈希及 `git diff --check BASE HEAD` | 0；diff check 0，干净 WT |

覆盖率原始 XML：**3842 / 5745 = 66.87554395126196%**；1903 missing，默认 60% 门通过。没有改 coverage 配置、分母或排除规则。375 相关项含完整 unit 的子集；34 probe 的 8 PG 与已有 19 PG 分开，不将各层通过数相加称为互不重叠的总量。所有正式测试 skip=0。既有 Starlette warning 和外置 probe 的 real_pg marker warning保留。

## 六类边界与质量结论

| 方面 | 已验证事实及边界 |
|---|---|
| 正确性/正常 | 200 短路；原 4xx/5xx 分类保持；short Retry-After ceil 且 ≥7；两个期限取较晚者；>300 不截短。RFC850 边界误阻断另列 Should 2 |
| 缺失/冲突 | 401/普通403 auth；403 primary reset 的短/长/缺失；429 无 header fallback；坏日期、合并值、129/5000/65500 字符值阻塞。超 stdlib 行上限为 Must 1 |
| 安全 | 原始同名/异大小写三种限流头均在 dict 前拒绝，socket 关闭；重复 Link 保持原 NetworkRequestError。无 secret 回显、任意 URL、SQL 或 shell 新入口 |
| 事务/失败语义 | 真实 PG 的新限流五例与原 19 项验证未提交原文/回执/游标；blocked 无 next_retry_at，短等待持久化，立即重投 not_claimed；Must 1 的 PG 状态确为不应发生的 retry_wait |
| 幂等/并发/历史 | 同响应重放不修改头；四线程独立 clock；两 PG worker 同任务仅一次 fetch/attempt，另一个 not_claimed；第二页长限流不改变先前成功 receipt/cursor/revision |
| 性能/复杂度 | 新分类器对有界 header 集合线性扫描，数值/日期长度有界；无睡眠、新重试层、新依赖或常驻可增长状态。共享请求并发槽/总超时/源租约仍复用既有机制。没有负载/吞吐/持续时间实测，不能报告性能达标 |

Standards：本批命名、docstring、类型及最小直接实现未发现需另报的规范违例，静态检查已通过。Spec：Must 1 是本批超长/未知期限安全停止的缺口；Should 2 是确定的 RFC850 保守解析差异。没有风格性、猜测性或无复现的 finding，没有建议额外架构。

分层记录：unit 默认入口 passed，但有额外 Should 红例；相关 contract passed；integration/security 对本批 **failed**（Must 红例），通常 PG/共享传输回归 passed。frontend/e2e/live/人工产品验收/正式性能/持续运行 **not_run**，本轮未借旧 live 或模型结果补签。头数量超过标准库上限尚无本 reviewer 初审 probe，属于缺测，不计为已确认失败。

评分证据仅支持 F1/E1/R1 的来源失败分类、受控出口、PG 回滚/重复与并发边界，以及 P1 所需失败不伪装成功；不证明八类来源、完整增量窗口、≤6h、真实模型问答、完整 R04 或 G-B 达标。R06 的广度/时间过滤/重叠补采仍独立保留。

下一步仅建议：提交覆盖 Must 1 的最小 transport 修复并冻结新 SHA，由本原 reviewer 定向复验。本初审保持 00261 与失败证据；Should 2 另行明确修复或登记非阻断负债。

**Verdict: fix 1 first. 本批 needs_changes。**
