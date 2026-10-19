# Root · batch13 worker 连接峰值共同根因诊断

What this change does: 本轮只核对固定产品版本的两次失败、连接边界和原始证据。没有修改业务代码，没有连接 PostgreSQL，也没有把缺失的连接 owner 样本补成结论。

任务：`batch13_worker_connection_diagnosis`；诊断交付 `awaiting_review / complete`，产品仍按原独审 `needs_changes`。unit、integration、live、manual 均 `not_run`，业务测试数 0。本报告不更新任务状态，不签 accepted，不提交或 push。

任务实际开始：2026-10-17T02:57:04+08:00。文档首次创建/本次写作开始：2026-10-17T03:04:10+08:00。写作结束/证据截止在末尾记录。10 分钟有界诊断；使用的工具调用均在 60 秒内。

固定产品：`bc089809c03472582f6256b495a6f9a2a308a5d2`。只读工作树：`D:/wt/batch13-default-product-review1`，分支 `codex/batch13-default-product-review1`，检查时 HEAD `00e3eb978f09a8b2f2a5e88cd5a3c56a7bac6c22`；此后报告/证据提交不代替固定产品代码。七个连接相关源码原始 SHA 全部匹配该工作树的冻结 manifest。Root 主树检查时 HEAD 仍为 bc，有多项既有未提交修改，全部保留。

已读 AGENTS、00 执行索引、R01/R14 恢复卡、任务状态、09 运维交付合同、CR-R01、CR-R14 LangGraph 持久化合同、R01/R14 与 Root batch13 报告、原独审报告。使用 Ponytail-review 5.3.1 的具体触发路径和最小修正原则。任务状态中 R01 的较早 accepted 范围不覆盖本次新生命周期缺陷或 R14 整卡。

## 结论及证据等级

**确定的产品缺陷**：固定 bc 的 `backend/migrations/env.py:38` 创建 QueuePool engine，只退出 `engine.connect()` 上下文，没有在 finally 中 dispose 自建 engine。`current_migration_revision` 在 `infrastructure/database.py:84` 有同一缺陷，但这两个 run 没有调用该 helper，不能把它归入实际第三连接。

**最小共同解释，但不是逐连接 owner 已证实**：迁移池留下一条已归还池、尚未关闭的底层会话；调查工作流同时需要一条业务连接和一条 checkpoint 连接，形成 1+2=3。这个解释同时符合两次运行的 peak 3、显式 API/worker/adapter 关闭后目标库仍 1，以及进程退出后目标库归零。原日志没有创建栈、连接 backend PID、application_name 或每条连接的数据库身份，因此无法把三条具体会话逐条归给 migration / workflow / checkpoint。不得写“已准确找出每个 3 的 backend owner”。

**观测限制**：review sampler 把真实 psycopg 连接对象强引用在 `CONNECTIONS` 列表中。这避免对象被提前回收、漏计连接，但也改变无显式 dispose 路径的 GC 时机。当前证据证明确定性关闭边界缺失和此 instrumented 继续运行进程中的留存；不能据此声称普通无采样进程必然长期漏同一会话。最小修正仍应显式 finally dispose，不依赖 GC。

## 原两次失败和 owner 证据

原 run 根：`D:/wt/batch13-default-product-review1/reports/runs/batch13_default_product_review1_20261017/`。本轮安全摘录、原文件 hash 和七文件冻结核对在 `reports/runs/batch13_worker_connection_diagnosis_20261017/safe_evidence.json`。

| 原窗口 | 实际时间 +08:00 | controller 身份 | 原结果 | 目标库退出后结果 |
|---|---|---|---|---|
| `product.py` | 02:45:24.264–02:45:37.190 | PID 43212；birth 2026-10-16T18:45:23.569453Z | exit 1；peak 3；显式 shutdown 后目标库 1 | `cleanup_receipt.json` 于 02:46:10.961 观察 0，身份核验后 drop 成功 |
| `supplement_product.py` | 02:48:00.971–02:48:15.681 | PID 2404；birth 2026-10-16T18:48:00.267647Z | exit 1；peak 3；显式 shutdown 后目标库 1 | 后续新进程 resume shutdown 目标库 0，身份核验后 drop 成功；没有紧接原第二进程退出的独立逐连接采样 |
| 独立 `resume_product.py` | 02:49:48.864–02:50:10.036 | PID 3140；birth 2026-10-16T18:49:48.133694Z | 不运行迁移/worker；PG peak 1；shutdown 0；exit 1 | 原目标库 drop 真；Edge Windows observed peak 17，超原 cap 16 |

原 launcher 分别 PID 29964 / 25208；其 birth、完整 pwsh/conhost 归属在原两份 product receipt。sampler 是 controller 内线程，不是独立 PID。两条计数函数入口都指向同一 `tracked_connect`，一次返回真实对象后只 append 一次；没有看到同一真实 connect 被双重 append 的路径。

第一 `resource_guard_failure.json` 保存 `phase=real worker entry, direct dispatch`、`connections=3`、`elapsed=8.921s`，这证明具体超限采样位置。第二同名 supplement guard 文件目前保存的是后续 resume 的 `owned_count=17 / connections=0 / elapsed=117.283s`，原第二 guard 被路径复用覆盖；第二 `product_receipt.json` 仍独立保留 peak 3 / shutdown 1 / exit 1。reviewer 在内部消息报告第二 +9.125s；本轮 rg 没找到单独保存该原始 guard 的文件，因此具体第二超限时刻只标 reviewer 说明，不伪称独立原样验证。

原 `raw_artifacts_exact.tar.gz` 封存 160 个原文件，archive SHA 为 `98b179108047871408e7907b6e1f189aba98f8f9269026bf773a27f5e5c138ee`。其 sealed_at 为 02:57:11.737，晚于 resume；不能用该封存时间假定它恢复了此前已覆盖的第二 guard。两份失败 receipt、第一 guard 和 Edge 17 原结果均未删除或改写。

guard 在首次超限后停止 sampler，因此 3 与 Edge 17 都是实际观测峰/下界，不是停止后的连续上界。原角色为 superuser、rolconnlimit=-1、server max_connections=50，原标记明确 physical_two_connection_limit=false；原逻辑 guard 的 2 上限不是数据库物理限额。

## 生命周期与备选路径核查

| 候选连接 | 固定源码/原运行事实 | 关闭边界与判断 |
|---|---|---|
| 迁移自建 QueuePool | `env.py:38`；两次均先 `run_migrations` | 连接 close 归还 pool；无 engine.dispose。已证实产品生命周期缺陷；实际第三 backend owner 缺样本 |
| worker 业务连接 | `workers/investigation.py:159`、`workflow_service.py:464` | claim 和 actor-read Session 在 execute 前退出；execute 的外层连接跨图执行存在；consume finally dispose，完整执行后释放 |
| LangGraph checkpoint | `checkpoint_runtime.py:105/114`；在 workflow outer connection 内开启 | direct psycopg 上下文包住 graph；无辅助 ConnectionPool。所用本地 psycopg `Connection.__exit__` 非 pool 分支调用 close。工作期间第二条连接是短期合法重叠，未发现 exit 后残留代码路径 |
| runtime 的内部业务事务/工具 | `workflow_service.py:569/574/876/879` | Session 明确 bind 已有 connection，证据 reader/read adapter 也复用它，未创建另一业务 engine |
| 默认 API / module global app | `api/app.py:55/81` 与尾部 global factory | lifespan finally dispose；review explicit factory 使用 NullPool。第二在导入 helper/API 时未配置数据库，之后才配置 explicit factory，仍 peak 3，所以“额外 configured global app”不能解释共同故障；第一 global engine 本身存在不等于建立连接 |
| fixture seed / admin / API adapter | 两个 probe 中 admin先 dispose；seed使用传入 NullPool engine | sampler计所有本进程未closed对象，不按数据库过滤。worker peak 时 admin步骤已结束；shutdown残留查询显式按目标datname筛选。三个峰值对象分别在哪个数据库仍缺原样样本 |
| SDK / 公共 HTTP reader | SDK 六方法在 worker 返回并读取结果之后开始；SDK 使用普通 HTTP client | 第一超限发生在 worker阶段。SDK 不创建 PG engine；不能解释先发生的 peak 3 |
| `current_migration_revision` | 固定 helper 静态缺 finally | 两个 probe、执行调用链及相关代码未找到本次调用；属于需同步修的同类缺陷，不是本次实测归因 |

API 与 worker 的 resource-only NullPool adapter 没有改业务 factory、权限、reader 或模型；原证据不验默认 QueuePool 5+5 的生产连接峰。原 no-DB/no-migration resume 的 peak 1 支持问题出在之前包含迁移/worker的窗口，但因它同时去掉迁移和 worker，不能单独隔离其中哪一个 owner。

本轮复用的冻结 CBM 索引 tree `1a332a650ca492648cdacdf965f97e9d2952ccdcd506ecd2892ba13ba1b35340`，224 Python files、2924 nodes、17338 edges、0 partial/unusable parses。既有 `worker_execute` trace 指向通用 executor，不能代替专用调查 worker 的逐连接证据；本轮以真实专用 caller 和源码连接边界交叉核对，没有重建大图。

## 最小修正及可靠再复验

1. 在 R01 已独审的 912 修正合入 Root 新固定候选后，确认 `env.py` 和 `current_migration_revision` 的自建 engine 都在 finally dispose。这里不再扩大 migration、pool 或 workflow 业务补丁。
2. 复验只补现有 sampler 的安全 identity：每次连接成功保存 controller PID/birth、序号、backend PID、创建时单调时间、allowlisted caller 文件/函数/行号、owner 标签；只保存 target/root-admin 数据库标签，不保存 DSN、环境或参数值。不使用单独 SQL sampler 会话；读取当前连接的 `connection.info.backend_pid` 等已有信息，避免观察者占第三条。
3. 分段在同一继续运行进程中执行：admin关闭 → forward migration返回 → controlled checkpoint setup返回 → API idle → direct worker graph → worker返回 → API lifespan退出。每段保存 opened/closed identities 和安全 count，继续采样到实际 process exit。migration返回应无 migration owner 存活；worker图内预期业务+checkpoint最多2；返回后二者均关闭。不要靠强制关 instrumented connection 或 GC 掩盖生命周期缺口。
4. 独立观测目标库 residual 时先停止 actor SQL，再让既有 admin连接做按目标库身份过滤的读查询，原本在root-admin库的观察者单独列为 observer；不能把这条观察者算 actor目标库连接，也不能静默减掉真正的目标库会话。记录物理限制是否存在，与逻辑2连接 guard保持区分。
5. 使用 append-only/唯一 phase 文件名保存每次 guard 事件，保留原两次失败与 Edge 17 下界。第二原 guard 缺失不得用新绿色重跑补写成旧历史。连接复验与后续 Edge≤16 浏览器资格是独立问题；不能修改原16门槛或把登录后未运行的业务检查记通过。

预期新的 R01 finally修复只移除 migration owner，保留 R14 的两条合法工作期连接。如果新候选仍实测3，按新 identity 样本决定是 API并发、其他 actor连接还是泄漏；没有该样本时再次停在证据不足，不猜第三池。

## 本轮命令、交付和未运行

新增文件仅本报告及 `reports/runs/batch13_worker_connection_diagnosis_20261017/` 的只读证据摘录脚本、safe JSON、命令receipt、stdout与验证日志。没有改原 WT 报告/日志、业务/合同/指标/秘密文件、Root已有修改或共享状态。

| 本轮实际命令 | exit / 结果 |
|---|---|
| `git show bc089809...:backend/migrations/env.py` 与 `...:backend/src/ai_intel/infrastructure/database.py`；相关 `rg -n` / `Get-Content` 只读 | 固定源码两处缺 finally 已核；详细source七文件hash 7/7 match |
| `D:/dianzi/backend/.venv/Scripts/python.exe -B .../extract_safe_evidence.py` | 0；0.094秒；0业务测试/0新DB连接；完整own Windows tree观测4≤8；PID/birth见同名command.json |
| `ruff format .../extract_safe_evidence.py` | 0；格式化1文件 |
| 初次 `ruff check .../extract_safe_evidence.py` | 1；BLE001 broad Exception；修为明确OSError/ValueError/KeyError/TypeError，不加忽略规则 |
| 最终 `ruff format --check`、`ruff check`、再次只读摘录 | 均0；摘录0.062秒、own Windows树4；初次receipt/stdout另存.initial副本，未覆盖历史 |
| 摘录退出后按原PID/birth复核、七源hash复核、输出URL字面扫描 | exit0；同身份活进程0，七源match7；未出现postgres连接URL字面值。这不是读取秘密值做的exact-secret scan |

准备时数次只读命令使用不存在的 `ai_intel/worker`、`ai_intel/tasks`、`enrichment/runtime.py` 或09文档路径，返回1；随后用rg实际发现复数workers、runtime_policy及09_operations_delivery再读取。另一次过宽文件搜索输出截断，随后缩小检索范围。这些是诊断命令定位失败，不是业务测试失败；未隐藏成skip。

新业务unit/integration/live/manual全部not_run。没有DB/资源操作、native MCP客户端、模型、浏览或外部调用，没有修改原secret/DPAPI/环境文件。读取probe源码用于生命周期核对不读取其私有运行输入。未证实所有三条backend owner；第二guard原样缺失；普通无强引用采样GC行为、生产QueuePool、broker、真实browser链、最终新候选连接上限均未运行。

合同/计划偏差：没有公共合同、依赖、认证、分母或阈值变更。按AGENTS §8两次无进展停止扩大patch；提供已证确定性关闭缺陷、共同解释及最小identity缺口，不把资源stop造成的ConnectError算产品登录缺陷。E1/R2/A1仅得到生命周期边界、真实失败保留和复验方法证据，不增加正式性能、完整Agent或评分通过项。

下一任务建议：Root冻结已合912的新候选，授权原非作者按上面小型identity补录复验连接；产品其他Must与Edge资源资格分别继续，不能由本诊断签整阶段。

Verdict: 修复已证R01关闭边界；第三连接逐backend owner仍缺测。没有“原两次全根因已闭合”或产品Ship结论。

本次写作结束、最后更新与证据截止：2026-10-17T03:05:14+08:00。任务从02:57:04开始，仍在10分钟有界窗口内；此后只做本交付哈希/空白核对，不运行产品或资源检查。
