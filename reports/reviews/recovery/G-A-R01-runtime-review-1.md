# G-A / R01 · 真实运行、Compose 与 CI 独立初审 1

What this change does: 本批把隔离 Compose、真实 API/worker/beat 和检查入口连接起来。PostgreSQL 保存最近执行观测，API 在依赖失败或观测过期时返回 503；Celery 的结果不成为业务真相。

审查意见：**needs_changes**。独立自动复跑通过，真实冷启动复跑发现一个阻断，开发安全搜索的应用配置还存在一个确定的装配缺口。这里只给初审意见，不修改任务状态，不写 accepted，不签整 R01、原 T 卡或 G-A。审查者未参与实现；只写本报告与 `reports/runs/recovery_r01_runtime_review_1_20261015/`，没有业务源码、迁移、合同、依赖、金标、分母、进度、提交或 push 改动。

本轮已记录容器/自动检查执行窗口为 2026-10-15T00:59:23+08:00 至 01:23:39+08:00；后续只读 case 核对、无容器 IO 的合成权限负例和文档检查另有记录。报告实际文件时刻见 [review_file_receipt.json](../../runs/recovery_r01_runtime_review_1_20261015/review_file_receipt.json)。所有运行时命令的 cwd、Asia/Shanghai 秒起止、argv、真实 exit 和原始输出在同名 JSON / stdout / stderr 文件中；静态读取批次在 `commands.jsonl` 和编号日志中。

## 冻结输入、依据与归属

冻结工作树：`C:\Users\yinha\.codex\worktrees\recovery-r01-infra\dianzi`，分支 `codex/recovery-r01-infra`。开始、结束读取均 clean，HEAD 保持 `0b6a7ad5e984439855cd97124d70095c608adb58`，其 tree 为 `5b0bf52cf83271b0a60acae0ea27e6e494745282`。最终源码为 `d7290cf4240929aa98bfbcc381d9e35c32a534a4`，tree 为 `b7adda7a1c99c04eb9ccc798e0b4a0a2cab4491e`；源码至证据 HEAD 的 backend/frontend/infra/scripts/config/.github 差异为空。

正确合同比较基线是 `8b3927d7e012ebeeaf0db2afd30e67d6c5d4bbe4`，tree `d2d49f8fe11ffa854e97d9d550646ca9350fa8d8`，已经实查它是 HEAD 祖先。它包含先前的认证边界修复，不能把这些已有修改算作 infra 作者新写的功能。`05aa146` 只用于区分 infra 自身交付和原始日志的 diff 检查，不替代合同基线。

| 交付来源 | 本冻结 WT 中的祖先 | 独立核对 |
|---|---|---|
| quality `2b79c8087ee49bf6c6926359fab793977f3d6117` | `f7fdf9149b76f47fa57db6d724df74f7514d507a` | stable patch-id 相同 |
| quality `c918279c003925844c2444b768a2c81e427ffb33` | `c71d0db46a6bf092cf32b189ce3fa68a17424757` | stable patch-id 相同 |
| quality `453893dfc6815288b9f6985b2d632a4493c68458` | `7fe8db0e35cde4bd87836339492cccbd014a8d59` | stable patch-id 相同 |
| quality `e895852ee0b3cfce44436469f21ed37ee9f07ceb` | `05aa1469f83b9db76c35ab4ed4f7a5eec5ad6c79` | stable patch-id 相同 |
| root runtime `ca6aec29bda0c63d0451ddea41bc6f1f22a3f76e` | `4fa79ef017d958958e1d61a30bda6c43652e7a73` | 全提交 patch-id 不同；runtime.py、runtime_observations.py、database.py、0005 迁移、models.py 文件差异为空。它是 root 交付祖先，不是 infra 自行改公共迁移/模型。 |

已读真实 AGENTS、00 执行地图、恢复 11/12 的 R01、T02/T03/T06/T40、02 架构、05 API、06 测试、09 运维、状态与交接。适用合同明确：实际依赖装配；测试 DSN 不得触达常规库；0 项/skip/失败不得假绿；锁定安装、非 root、可重启；切片不自动通过整卡和阶段。作者 R01-infra 报告只用于找材料，下面结论来自独立源码/运行复核。

本轮按最新 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md` 审查。预期负载是受限本地单 API、一个 Linux prefork worker、一个 beat 和单节点搜索，不假定生产吞吐。另派未参与实现的只读子审检查 CI/guard；其未操作容器或读秘密，结论与主审独立运行相互核对。

## Must fix

1. **前端容器再启动时缓存目录不可写，整栈启动失败**（`infra/compose/compose.yaml:151`，`infra/docker/frontend.Dockerfile:8`；P1）。
   - **这是什么：**前端以 `node` 非 root 用户运行，read-only 根文件系统仅为 Vite 的 `.vite`、`.vite-temp` 提供 tmpfs。首启可以返回 HTTP 200。
   - **问题：**同一批准项目七服务 `stop` 后执行全 profiles 的 `up -d --wait --wait-timeout 180 --pull never --no-build`，01:17:09–01:18:36 实际 87.031 秒、exit 1。其余六服务 healthy，frontend exited(1)；Vite 实际报 `EACCES`，不能写 `/app/node_modules/.vite-temp/vite.config.ts.timestamp-….mjs`。源码没有固定这两个缓存挂载的 uid/gid/mode。Docker 文档说明 tmpfs 权限可能在重启时重置；这是与本次故障相符的权限根因，失败瞬间的 mode 数值未取得，不编造它。[Docker tmpfs 说明](https://docs.docker.com/engine/storage/tmpfs)
   - **最小修复与复验：**为两个 cache tmpfs 明确设置镜像中实际 node uid/gid（本镜像实查 1000/1000）及其可写 mode。保留非 root 和 read-only。复验必须包括首次创建、同容器 stop/start、七服务冷停/启动、容器内缓存目录权限、HTTP 和 Compose wait，不能只重建一次得到 HTTP 200。
   - **不修的影响：**T03/R01 的可重启部署不能成立。临时 force-recreate frontend（no-deps、no-build、pull never）只恢复了交接时运行状态，不是源码修复或冷启动通过。证据：`cold_up.json/.stderr.log`、`cold_frontend_logs.stdout.log/.stderr.log`、`inspect_final.stdout.log`、`frontend_recreate.json`、`frontend_tmpfs.stdout.log`。

2. **开发 base 的安全搜索没有与 API 匹配的 CA/认证装配**（`infra/compose/compose.yaml:63`、`:76`，`backend/src/ai_intel/api/app.py:155`，`backend/src/ai_intel/infrastructure/settings.py:41`；P2）。
   - **这是什么：**base 保留 OpenSearch 安全插件，容器自己的健康检查使用 HTTPS、admin 凭据和 `curl -k`。测试 overlay 则明确关闭 demo/security，改成 HTTP。
   - **问题：**照开发文档启用 base `search` 并把其 HTTPS 地址填进 `OPENSEARCH_URL`，API 的 HTTPX 客户端保持默认 `verify=True`、显式 `trust_env=False`，没有 CA 参数；Settings、Compose API/worker/scheduler 也没有独立搜索用户名/SecretStr 密码或 CA 挂载。官方 Docker 安装行为是默认 demo 配置使用自签证书。因而这条 base 配置无法用已提供的配置渠道完成受信 TLS 与认证；把用户名/密码塞进普通 str URL 也不能补齐 CA。[OpenSearch Docker 安装说明](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/)
   - **最小修复与复验：**增加窄的显式 CA 路径与独立秘密认证配置，挂载被授权 CA，并把它们传给健康探测的 HTTPX 客户端。保持证书/主机名验证，不用关闭 TLS、关闭安全插件或带秘密的 URL 修开发路径。用安全插件开启的隔离服务证明正确 CA+凭据可 ready，错误/缺 CA 或凭据仍 503，且错误/日志不回显秘密。
   - **不修的影响：**本批只能证明 security-off 测试 overlay 的搜索连接，不能声称 base 开发整栈已接通。此 finding 是配置与实际客户端默认行为的静态证明，**安全 base 的完整启动实跑本轮 not_run**；没有把测试 overlay 成功或作者日志伪装成它的结果。证据：`07_compose_source.log`、`14_tls_and_scope_read.log`。未为这一检查增加搜索容器、拉取或修改全局环境。

## Should fix

3. **45 秒观测有效性与实际 tick/消费缺少 CI 行为回归**（`backend/src/ai_intel/infrastructure/runtime_observations.py:30`、`backend/src/ai_intel/workers/runtime.py:70`、`backend/tests/unit/test_r01_worker_configuration.py:44`）。
   - **这是什么：**就绪状态现在取决于 PG 中的执行时点，并拒绝未来或过期观测。
   - **问题：**当前自动测试只断言队列配置及 scheduler 字符串。独立搜索未找到对 `read_runtime_readiness`、观测写入、45 秒边界或 `ObservedScheduler.tick` 行为的测试；full integration 覆盖输出也显示新增观测模块未执行。本轮真实停机负例通过，但它尚未成为 CI 的可复跑回归。
   - **最小修复与复验：**补一个独立 PG schema 的行为测试，核对未观测、新鲜、45 秒边界、过期、未来及 PG 失败，外加实际 tick/消费写入结果的窄断言。合成时间只用于确定性边界测试，仍保留真实 stop/过期/恢复证据，不将模拟时钟计为 live。
   - **不修的影响：**以后把 readiness 改成“只要有行就 ready”，CI 仍可能全绿。无需新增框架或更改覆盖门槛。证据：`16_runtime_boundary_tests.log`、`scope_integration.stdout.log`。

未发现需要扩展层级、万能服务、额外队列或新依赖才能解决本包问题的理由。现有运行入口只注册执行观测任务；复用 Celery PersistentScheduler、PG upsert 与一个健康查询是合适的规模。没有可量化的 Lean 删除项，不虚报节省行数。

## 独立运行与测试证据

唯一运行项目为 `dianzi-test-r01_infra_20261015`。先核对实际 Compose labels、config_files、working_dir、镜像 ID 和 host network，再操作本项目。实际 PG 为 25436 / `test_dianzi_r01_infra_20261015` / `test_dianzi_r01_infra`；Redis 26383；搜索 HTTP/transport 29201/29301；API 28201；旧前端 25201。只将指定 root 0600 仓库外 connection.json 捕获为变量注入，不输出其内容或 DSN/密码；未读 DPAPI、KEYS、.env、其它项目连接。没有 production downgrade/down，没有清库/删卷，没有操作 root/quality/frontend 其它项目，也未延长父 deadline。

`inspect.stdout.log` 实查七容器在 host network，PortBindings 为空；不能把 base ports 的 localhost 字符串当 host 模式隔离。`listeners.stdout.log` 实查 PG、Redis、API、frontend 为 127.0.0.1，搜索为 IPv4-mapped loopback。CPU/内存/PID 与配置相符；app 10001:10001、frontend node、cap_drop ALL、read-only、无 proxy ENV。官方数据镜像 digest 与实际 image ID 对应；本轮没有新增 pull/build。

backend 实际 image ID：`sha256:34b24db5595ed36fc608f39f648d5a9a2288cb03a2ca8f1ecd123044158ea7b0`。frontend 实际 image ID：`sha256:de3c406ba2f65e60273a8e545de8ce0eca3bd9b6c54aebd62de33d8bc382c439`，仍是旧骨架。独立逐文件核对 66 个必要 backend/src、迁移、锁及 frontend 输入文件：镜像字节与冻结 clean WT 一致；与 Git blob 的 LF 归一化 SHA256 也一致。首次直接 blob/raw 比较失败是仓库 `core.autocrlf=true` 的 CRLF 差异，已明确诊断，原失败保留，不把它当源码差异。见 `image_source_expected.json`、`12_hash_diagnosis.log` 和 `image_source_verified_*.stdout.log`。

| 实际命令与 cwd | 开始–结束（2026-10-15，+08:00） | 真实结果 | 证据 |
|---|---|---|---|
| backend：`uv run --locked pytest tests/unit/test_r01_worker_configuration.py tests/contract/test_r01_compose_configuration.py tests/contract/test_r01_quality_checks.py tests/security/test_r01_admin_error_redaction.py tests/security/test_r01_http_authentication.py -q --cov-fail-under=0 --junitxml=…` | 01:04:37–01:04:57 | 64 pass / 0 fail / 0 error / 0 skip，exit 0 | pytest_runtime JSON/XML/raw logs |
| WT：`python scripts/dev.py check --scope unit --timeout-seconds 600` | 01:09:31–01:09:38 | 59 pass / 0 fail/error/skip，exit 0；保留 60% 门，实际 63.88% | scope_unit raw；scope_summary.json |
| 同入口 `--scope contract` | 01:12:04–01:12:21 | 125 pass / 0 fail/error/skip，exit 0 | scope_contract raw |
| 同入口 `--scope security` | 01:12:22–01:12:26 | 35 pass / 0 fail/error/skip，exit 0 | scope_security raw |
| 同入口 `--scope integration` | 01:13:46–01:14:35 | 41 pass / 0 fail/error/skip，exit 0，包含 T03 文件现有 6 例中的真实 restart 和保卷 down/up；C04 有两个分例，C05 另作明确合成负例 | scope_integration raw |
| backend：`uv run --locked ruff check . ../scripts/dev.py` / `ruff format --check . ../scripts/dev.py` | 01:16:00–01:16:01 | 各 exit 0 | ruff/format JSON/raw |
| backend：`uv run --locked mypy src ../scripts/dev.py` | 01:16:01–01:16:02 | 51 文件无错误，exit 0 | mypy JSON/raw |
| 全 profiles 冷停后 `up -d --wait --wait-timeout 180 --pull never --no-build` | 01:17:09–01:18:36 | exit 1，87.031 秒，frontend EACCES | cold_up JSON/raw |

四 scope 共 260 个通过；64 个定向检查与它们重叠，不能相加说成 324 个不同测试。非 unit 的 cov0 沿用原 scope 合同；未改全局 unit 门。pytest 在 Windows 冻结 WT 原 venv 执行，访问真实 Linux 容器；Linux 容器内运行行为另外实测，不声称另建 Linux pytest venv 或运行 GitHub 流水线。

真实 runtime / API 检查如下（assertion 数是检查器断言数，不是正式评测分母）：

- 01:06:27–01:06:28，实际 PG 预创建唯一随机测试用户，HTTP 登录、me 的 tenant/role/live、错误 Origin、注销、注销后 401，6 断言通过；随机密码、session、CSRF 不输出。`auth_live.*`。
- 01:06:29–01:06:36，停止本项目 worker/beat；边检查源码边等待真实时间，01:07:16 两条 PG 观测分别为 48.281659 / 48.280417 秒，API 503，数据库/缓存/搜索仍 ready，worker/scheduler 均 not_observed_or_stale。5 断言通过；01:07:16–01:07:41 恢复成功，随后确认重新 ready。首轮采样年龄 43 秒仍 200、69 秒变 503也保留；它没有替代第二轮 45–60 秒窗口的精确负例。`expiry_observations.json`、`expiry_stop.*`、`expiry_restore.*`、`health_restored.*`。
- 01:09:16–01:09:18，在同一专用 PG 新建独立测试 schema，仅写 0004 alembic_version，给真实 health router 注入该独立 Engine（不是 fake PG）。实际返回 503/migration_required；默认 public 0005 以及旧 schema 0004 均未改变，没有 downgrade 或 startup 自动迁移，3 断言通过。`old_schema_verified.*`。
- 01:09:18–01:09:31，Linux API 容器读取锁定运行配置并实际 Redis inspect worker，Celery 5.6.3、JSON、唯一 ai_intel 默认队列、无结果 backend、ignore_result、30/25 秒限时、prefork TaskPool、实际 concurrency=1；6 断言通过。`queue_live.*`。PG 中 worker 观测来自真正消费 observe_worker，scheduler 来自真正 tick；不把观测当业务任务完成。
- 01:10:20–01:10:21 停本项目 PG；`health_pg_failed` 503/not_ready/database unavailable，登录 503/authentication_unavailable 且无秘密回显，2 登录错误断言通过。01:10:52–01:10:53 恢复 PG，01:10:53–01:11:30 全 profiles 恢复；01:12:03 API 200，重新观测约 3.25 秒。`pg_stop.*`、`auth_pg_failed.*`、`pg_restore.*`、`up_all.*`、`health_pg_restored.*`。

独立 CI/guard 复核确认实际发现 unit/contract/security/integration/frontend；JUnit 0 项、缺报告、skip、error/failure、超时和工具非零都不能成功。实际 64 个定向检查包含这些负例。test project 必须与 run_id 相同；DSN 必须 PG、loopback、精确 test 库/test_ 用户/非常规端口，5432 只有显式匹配容器例外。Compose COMPOSE_* 与 host 应用变量分开；本轮原“缺依赖”负例未被宿主秘密污染。关闭保卷，fixtures 只执行期连接，不在 import/collect-only 联网。完整 YAML 可检查不等于 GitHub 实跑。CI 当前也没有把不存在的旧前端 e2e 计为通过。

T03-C05 本轮另在报告目录检查器内显式注入合成 PermissionError，验证实际 T03 wrapper 抛 `UsageError/blocked`、integration 入口退出 4，不通过 skip 或 SQLite 回退；2 断言通过。`fixture_permission.*` 有实际时段和 exit。这个 fixture 无容器 IO，没有修改真实 daemon 权限，不能称为真实失去容器权限的现场演练。

官方 CBM CLI v0.11.0 在仓库外独立 cache `/tmp/dianzi-cbm-r01-runtime-review-1-20261015` 只索引 backend/src 和必要 scripts，分别 539 nodes/2048 edges、90/288；无秘密/holdout/run 目录索引或图落回冻结树。已读当前 help/graph schema 和 worker/API outline；所有动态入口由 rg 与 Compose command、API 注册和 task 注册交叉核对，不能把图中未显示的动态路径当不存在。相关 raw 为 `cbm_index/scripts/trace.*`、17/18 编号日志。

## 失败、限制、合同边界和交接

保留真实失败：冷启动 frontend EACCES；完整 delivery 的直接 `git diff --check 05aa146 HEAD` exit **2**，仅原始日志尾部空白，源码/infra/config/scripts diff 检查 exit 0。没有删改 raw 日志、没有自行改 .gitattributes，主控可按其既有精确定点策略处理证据格式。

审查工具自身的失败也保留：最初 CBM `schema` 不是 v0.11.0 的 tool，随后按 help 使用 get_graph_schema；一次未传 project，一次 PowerShell 引号导致 rg regex error，均已纠正读取。首次旧 schema 验证把 search_path 放 URL query，但默认 build_engine 明确注入 timeout options，导致探针没有进入旧 schema；改为 health router 的真实独立 Engine 后通过，不能把首工具输入错误算作迁移业务缺陷。首次镜像 raw SHA 的 CRLF 问题前文已解释。`search_base_path` grep exit1 是 demo 安装 shell 只调用 Java Installer、无匹配文本；随后读取公开 wrapper 验明，不当作搜索运行失败。这些失败均未改成 skip 或删除。

GitHub CI=not_run；base 安全搜索整栈=not_run；新 UI 浏览器、e2e=not_run；模型/FOFA/来源产品 live、正式性能/稳定性窗口和人工验收=not_run。本包 Linux 基础服务的真实行为已运行，不等于真实模型/语义检索/来源接通。87.031 秒是一次失败冷启动耗时；没有成功冷启动延迟或持续吞吐结论。

R02 的 session/登录窗口/audit 仍在内存，R03 的业务 claim/retry/outbox/cursor 链仍缺。这些继承缺口不被最近观测或基础队列配置覆盖。主控随后消息告知 `b504` 成功登录占限流窗口修复、新 UI 候选及另一个行为复核正在进行；本审未把后续代码或其测试回填本冻结 SHA，后续需按新候选定向复核。当前 R01 总报告/状态仍 in_progress，只是 infra 自报告 awaiting_review，不由本审更新。

运行交接：01:21:25–01:21:36 只 force-recreate 本项目 frontend 恢复首启；此后七服务 healthy，旧前端 HTTP 200，API ready 200、PG 观测约 6.24 秒。01:23:39 后停止全部容器操作、没有后台复跑；已明确通过消息把唯一项目交给新 WT `recovery-r01-infra-fix` 的原 infra 作者，由其只修 tmpfs 并冻结后申请定向复核。原冻结 WT 和失败证据不改。父 daemon deadline 保持 2026-10-17T21:49:15+08:00。

评分证据仅支持 E1/R2 的隔离工程、真实依赖/执行观测及诚实测试切片；不认证这些评分项整项、U01 全链路、整 T02/T03/T06/T40、R01 或 G-A。合同/门槛/分母未变。下一步是修 1、2并定向复验，补 3 的窄回归；之后再由新阶段 reviewer 核对集成后的 G-A 所有切片。

**Verdict: fix 1 and 2 first.** 不提前签阶段，原始失败保留。

Not checked: GitHub 云 CI、开发安全搜索实跑、新 UI/e2e、R02/R03 完整持久化和业务执行、模型/来源 live、正式性能及持续运行、人工最终验收。
