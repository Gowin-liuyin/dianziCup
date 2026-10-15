# G-A / R01 行为独立审查 1

审查者：`/root/r01_independent_review`，新建且未参与本批实现。初次核验：2026-10-14T23:38:57+08:00；最终证据快照：2026-10-15T00:03:15+08:00，Asia/Shanghai。任务意见：**本次早期 HTTP 认证、前端会话与检查脚本切片 needs_changes**。不登记状态、不签整 R01、整 T06/T40 或 G-A。

固定候选：`4a17ca7b967a10d6077ba5219984a2d1a74cf320`，tree=`afbffca93704545866b79283e551ec461e0d6ecc`；基线：`f0b154ee0e10100bc9a9d293ebeded13926d0a42`。审查 checkout：`C:\Users\yinha\.codex\worktrees\recovery-r01-candidate\dianzi`，分支 `codex/recovery-r01-candidate`。初始及最终 `git status --short` 均为空。构建曾改写已跟踪的 `frontend/tsconfig.tsbuildinfo`，仅还原了本次构建产生的这一文件，日志 `restore_generated_build_state.*`；业务源码未改。

本改动把认证路由装入默认应用与 `/v1`，区分依赖未配置/不可达，引入严格登录输入与安全错误响应；前端使用 Cookie 与内存 CSRF 恢复会话、显示真实健康状态，脚本实际执行测试并检查数量和隔离资源。会话、登录计数、审计仍在进程内存；PG 用户目录的接线不等于 PG 会话持久化。R02 必须完成跨进程会话/限流与真实 PG 验证，这个分段限制没有计为完成。

## 依据与覆盖

已阅读本候选 AGENTS、`prompts/12_full_delivery_parallel_push.txt`、执行地图与计划 02/03/05/06/08/09、R01/R02 卡、T02/T03/T06/T40 卡、CR-R01–09、public v2 schema、manifest、当前状态和交接。文件哈希见 [snapshot.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/snapshot.json)。采用本机新版 [ponytail-review SKILL.md](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，中文及完整交付要求优先。作者报告仅作定位线索，下述判断来自独立执行与源码核对。

检查实际默认入口、认证输入/Origin/CSRF/注销/过期、服务器权限上下文、前端刷新和退出的竞态、私有身份清除、未知/失败/超时语义、测试脚本计数与 DSN/Compose 防误用、迁移百分号编码及调用方。假设负载是 FastAPI 同步路由允许同客户端并发，浏览器同域多标签共享 Cookie；没有把单线程演示当作部署负载。

**关键限制：**没有跑真实 PG/Redis/OpenSearch、worker/scheduler、Compose、进程重启持久化、浏览器 E2E、外部模型/来源/供应商、历史账本或真实私有资产读搜导出。认证夹具测试与拒绝本地关闭端口仅证明相应边界，不能填补这些缺口。

## 必须修复

1. **[P1] 同客户端并发错误登录绕过五次限制。** 位置：[authentication.py:228](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/authentication.py:228)、[authentication.py:334](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/authentication.py:334)、[authentication.py:345](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/authentication.py:345)。检查计数在用户查询之前，记录失败在查询/Argon2 之后，两者没有原子预留。自主输入：同一 TestClient 客户端八个并发 POST `/v1/auth/login`，错误密码，目录查询处用 Barrier 模拟慢 PG 查询；实际八个均为 401，全部进入凭据校验，预期超过五个的请求在校验之前 429。顺序六次输入为 `[401,401,401,401,401,429]`，证实问题在并发而非整个限流入口不存在。影响：窗口上限在实际同步线程负载下失效，也无法限制并行 Argon2 消耗。最小修复：用原子操作预留同客户端窗口/在途额度，完成时按明确成功/失败策略结算；锁只覆盖计数，不能覆盖数据库或密码计算。R02 再把同语义迁移到共享后端。复验：保留慢目录并发例与顺序例，验证超过上限的请求不进入密码校验，且异常时释放在途额度。证据：[backend_behavior_probe.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/backend_behavior_probe.log)，明确为隔离 HTTP + 延迟目录边界复现，未声称真实 PG 并发测试通过。

2. **[P2] 非 ASCII CSRF 请求头触发 500。** 位置：[authentication.py:309](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/authentication.py:309)、[auth_routes.py:173](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/auth_routes.py:173)。自主输入：先正常登录，再向 logout 发送有效 Cookie、允许 Origin、原始 `X-CSRF-Token` 字节 `FF`；ASGI 可把该头解码为 Latin-1 字符。预期 403 `application/problem+json`，实际 500 `text/plain; charset=utf-8`。`hmac.compare_digest` 的字符串输入只接受 ASCII，这条路径的 TypeError 没被边界转换。随后 `/me` 仍 200，说明错误没有撤销会话；不是权限绕过，但把恶意/损坏输入变成了服务器异常。最小修复：在比较前严格拒绝非法 CSRF 编码/格式，或使用明确字节编码比较，并仍返回固定的 CSRF 拒绝错误。复验：ASCII 错误值、空值、非 ASCII、正常 CSRF 均走预期状态且不回显值。证据同上，观察点 `non-ASCII CSRF header is rejected`。

3. **[P2] 会话恢复可以把用户 A 与用户 B 的 CSRF 拼接。** 位置：[auth-session.tsx:35](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/src/app/auth-session.tsx:35)、[auth_routes.py:134](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/auth_routes.py:134)。自主输入：restore 的 `/me` 取到 A 后，另一标签登录 B 更换同域 Cookie，再完成 `/csrf`。预期拒绝混合身份并清除/重新取得一致上下文；实际组件显示 `review-user-a / review-tenant-a`，保留 B 的 CSRF，随后 logout 针对 B 成功。组件的 requestGeneration 只能识别本组件旧请求，无法识别 Cookie 的外部更换。独立组件例 7 pass/1 fail；另用实际认证路由在同 Cookie jar 按 A 登录→A `/me`→B 登录→B `/csrf`→logout 复现，确认这种响应组合真实可达。影响：页面身份/权限与服务端动作主体不一致；当前已证实的是身份展示和注销，不推断已经发生资产跨租户读取。最小修复：用一次认证读取返回同一会话的用户与 CSRF，或给两次读取返回可核对的会话关联并在前端拒绝不一致；只再读一次 `/me` 无法原子解决多标签切换。复验：保留 A→B 的边界输入、旧 restore 在 logout 后完成的输入、退出失败与过期清理，再跑真实浏览器多标签例。证据：[frontend_behavior_probe.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/frontend_behavior_probe.log)、[cross_tab_http_probe.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/cross_tab_http_probe.log)。前者 mock HTTP，后者真实路由但使用显式内存账户夹具；浏览器层 not_run。

4. **[P2] 固定候选仍有依赖审计阻断。** 位置：[package.json:35](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/package.json:35)、[package-lock.json:4023](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/package-lock.json:4023)。自主 `npm ci` 成功但报告受影响包；`npm audit --json` 退出 1，受影响包 1 moderate + 2 critical，锁中 Vitest/@vitest/mocker 为 3.2.7、tinypool 为 1.1.1。扫描列出 [GHSA-82fw-gwwq-j7x9](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)、[GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3)、[GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr)。这些是开发工具依赖的审计结果，本轮没有运行漏洞 PoC，也未证明生产浏览器包可被利用。预期质量门有解决后的审计证据；当前仍为非零，不能因为 build/test 通过忽略。最小修复：把获批的主版本升级实际落实到新冻结候选与锁文件，然后锁定安装、lint/typecheck/test/build、审计全部复跑；本报告不为主控另一 worktree 尚未应用的候选背书。证据：[frontend_audit.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/frontend_audit.log)。

5. **[P2] 秘密扫描把明确测试夹具当作秘密，安全 scope 失败。** 位置：[test_t06_authentication_and_scope.py:181](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/tests/security/test_t06_authentication_and_scope.py:181)、[test_t06_authentication_and_scope.py:218](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/tests/security/test_t06_authentication_and_scope.py:218)、[client.test.ts:45](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/frontend/src/api/client.test.ts:45)。自主安全 suite 实际 27 passed / 1 failed，T06-C06 在 `frontend/src/api/client.test.ts` 的 `csrf_token: "fixture-csrf"` 命中 `token` 后只允许两种开发占位值。预期明确隔离测试夹具可以存在，同时真实前端/日志凭据依然被拒绝；实际干净候选无法通过安全检查。没有证据把这一字符串定为真实泄漏。最小修复：给明确测试文件/fixture 标记建立局部、可审查识别规则，继续扫描产品源码、构建和运行日志，并用新增负例证明真实凭据仍被拒绝；不降低正则长度门槛、不全局关闭检查、不把本失败改 skip。复验：全 `tests/security` 无失败/skip，且真实形态凭据植入检查非零。证据：[backend_security.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log)。

6. **[P2] 框架 404/405 未遵守统一 Problem 合同。** 位置：[app.py:73](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/app.py:73)、[problems.py:10](C:/Users/yinha/.codex/worktrees/recovery-r01-candidate/dianzi/backend/src/ai_intel/api/problems.py:10)。当前只注册 RequestValidationError handler。自主 GET `/v1/auth/missing` 与 GET `/v1/auth/login` 分别得到 404/405 `application/json` 的 `detail`，预期计划 05 §2 / CR-R04 的 `application/problem+json` 与兼容 error/trace_id。影响：错误可观测性及消费者格式不一致；没有发现凭据回显。最小修复：把框架 HTTP 异常接到固定消息的 Problem 入口，保留如 405 Allow 的标准头，不用原始异常 detail 填敏感内容。复验：404、405、422、401、403、429、503 的状态、媒体类型、字段和 trace_id 都有独立断言。证据：[backend_behavior_results.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/backend_behavior_results.json)。

## 实际复跑

下面 B 为 `C:\Users\yinha\.codex\worktrees\recovery-r01-candidate\dianzi\backend`，F 为同根目录 `\frontend`，R 为同根目录。完整原始 argv、cwd、开始/结束秒级 +08:00、真实 wall、exit、count、日志位置在 [commands.json](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/commands.json)，各记录另有同名 JSON，日志没有把失败覆盖为成功。

| cwd / 实际命令 | exit | 实际结果 | 日志 |
|---|---:|---|---|
| B `uv sync --locked` | 0 | 创建本 WT 环境并按锁安装 | `backend_sync.log` |
| B `uv run --locked pytest tests/unit -q` | 0 | 57 passed，0 skip；coverage 63.27%，保留 60% 门槛 | `backend_unit.log` |
| B `uv run --locked pytest tests/security -q --cov-fail-under=0` | 1 | 27 passed / 1 failed，0 skip；非 unit 层按脚本约定不套 unit 覆盖门槛 | `backend_security.log` |
| B `uv run --locked pytest tests/contract -q -m "not real_pg" --cov-fail-under=0` | 0 | 106 passed / 1 deselected，0 skip；仅离线子集 | `backend_contract_fixture.log` |
| B `uv run --locked ruff check .` | 0 | 无 lint 错误 | `backend_ruff.log` |
| B `uv run --locked ruff format --check .` | 0 | 85 files already formatted | `backend_format.log` |
| B `uv run --locked mypy src` | 0 | 48 source files，无类型错误 | `backend_mypy.log` |
| F `npm.cmd ci` | 0 | 安装成功，依赖审计告警保留 | `frontend_ci.log` |
| F `npm.cmd run lint` / `npm.cmd run typecheck` | 各 0 | 无 lint/类型错误 | `frontend_lint.log` / `frontend_typecheck.log` |
| F `npm.cmd run test -- --run` | 0 | 4 files / 30 passed，0 skip；候选配置 1 worker | `frontend_test.log` |
| F `npm.cmd run build` | 0 | 30 modules，生成构建 | `frontend_build.log` |
| F `npm.cmd audit --json` | 1 | 受影响包 1 moderate + 2 critical | `frontend_audit.log` |
| R `backend\.venv\Scripts\python.exe scripts/dev.py check --scope contract --fixture-only --timeout-seconds 60` | 0 | 真正运行并报告 tests=106 / failed=0 / errors=0 / skipped=0；1 real_pg deselected | `script_contract_fixture.log` |
| F `node <候选 frontend/node_modules/vitest/vitest.mjs> run --config <本 run/vitest.review.config.mjs> --reporter verbose --reporter junit --outputFile <本 run/frontend_behavior.junit.xml>` | 1 | 自主 8 例：7 passed / 1 failed，0 skip | `frontend_behavior_probe.log` |
| B `uv run --locked python <本 run/backend_behavior_probe.py>` | 1 | 47 观察点：43 匹配 / 4 不匹配；两项为 404/405 同根因；不是新增 unit 通过数量 | `backend_behavior_probe.log` |
| B `uv run --locked python <本 run/cross_tab_http_probe.py>` | 0 | 成功复现响应拼接和 B 注销，exit 0 是复现成立，不是修复通过 | `cross_tab_http_probe.log` |
| F `npm.cmd run test:e2e -- --list` | 0 | 发现 3 个例，实际执行 0；list JSON 的 skipped 不当作已跑后跳过 | `frontend_e2e_discovery.log` |
| R `git diff --check` | 0 | 无当前 diff 空白错误；候选最终 status 为空 | `source_boundary.log` / `snapshot.json` |

Vitest 外置审查配置第一次错误选择环境模块，exit 1 / 0 tests / 1 harness error，见 `frontend_behavior_probe_initial.log`；修正本 run 配置后才得到 7/1 行为结果，没有把环境错误冒充业务失败。前端超时例用 fake timers 前进 10001ms，只验证分类，不报告真实 10 秒性能。安全/合同层使用 `--cov-fail-under=0` 与现有非 unit 检查约定一致，unit 的 60% 冻结值没有变。

## 自主正负例与调用链证据

除了上述缺陷，实际观察符合预期的路径包括：默认及 `/v1` live 200、未配依赖 ready 503/not_ready、未配认证 login 503；严格 password 的数值/null/数组/对象/空/超长输入均 422 且不回显哨兵；自报 tenant/role/permissions 422 并只审计字段名；缺失/非法/null Origin 403；缺失/错误 CSRF 或缺 Origin 的 logout 403；正常 logout 清 Cookie 且 `/me` 立即 401，注入时钟的过期会话 401。实际默认 PG 目录使用合成配置连接本机关闭端口 9 时 login/ready 都 503，不出现默认成功。

DSN 自主输入拒绝常规开发库、非 loopback、常规用户、默认 5432、query pivot；销毁开发项目在 IO 前拒绝，未执行任何真实 down/清库/downgrade。测试报告零项→3、skip→4、error→1、非零工具返回保留、损坏 XML→1。实际 contract 脚本确实发现并跑了 106 项，不是只看 helper。迁移 percent URL 经真实 `Config` 读取保持编码，生产 build_engine 正确解码；交叉核对 `migrated_engine`、迁移 env、集成调用与 `current_migration_revision`，没有实际升级/降级本机数据库。候选 contract 的 downgrade 名称测试只替换 Alembic command 以检查配置，不是实际 downgrade。纯 `postgresql://` 的专用 DSN 在本锁环境能够建立 engine，未把先前怀疑的 driver 问题列为缺陷。

前端独立例确认：退出请求仍在途中即清身份；旧 CSRF 请求晚到不会补回已清身份；退出网络失败明确未确认撤销；过期恢复清除身份；unknown dependency 状态保留；未知服务错误不回显私有 detail；超时与空结果分开。当前工作台没有硬编码业务风险数字。本轮没有证明前端以外的历史对象/索引有效性或完整租户隔离。

没有已注册 CBM 工具，使用 WSL 官方 portable CLI v0.11.0，先看真实 help/schema，再在 `/tmp/dianzi-cbm-r01-behavior-review-1-20261014` 建立三个独立项目，`--persistence false`：backend/src 524 nodes / 1974 edges；frontend/src 58 / 164（3 个测试文件按 fast 模式排除，已用源码/rg/实际测试补核）；scripts 89 / 283。源树与三个范围的 Git blob 清单 SHA256=`603693eda4e234a3d7d98164b235489db2860635ad988dd190bde3f2c1ed5c14`，绑定本候选 tree，不引用主仓活动图。

最终 `cbm_tmp_*` 日志包含 architecture/schema、AuthProvider→API client、认证写闸门及隔离 guard callers。图对 `validate_write_request`/迁移显示 caller=0，源码和 [rg_callers.log](D:/dianzi/reports/runs/recovery_r01_behavior_review_1_20261014/rg_callers.log) 确认真实路由/测试调用，未把“无边”当作没有入口。`refreshSession` 为 hook 内 callback，CLI 查不到；改 trace AuthProvider，并直接读 closure/caller。

工具初轮把 XDG_CACHE_HOME 误用为缓存变量，发现预期目录不存在后按 [官方 CBM 配置](https://github.com/DeusData/codebase-memory-mcp/blob/main/docs/CONFIGURATION.md) 改用 CBM_CACHE_DIR，重新独立 index/query；三个初轮默认缓存项目只按本审查唯一名称删除，最终图保留在 `/tmp`。`cbm_schema_initial` 缺 project、`cbm_trace_front` 找不到 callback、`cbm_config_get_help` 不支持该参数等真实非零也都保留。此轮相关 wall 为秒级，没有遇到此前 860 秒异常，不伪造旧事件正常时长。

## 尚缺证据与推进意见

| 层 | 本切片意见 | 边界 |
|---|---|---|
| unit | passed | 仅候选 unit suite；不能说明实际 PG/worker 可用 |
| contract | failed | 离线 suite 106 passed，但自主 404/405 格式不符；1 real_pg deselected 不是完整合同通过 |
| security | failed | 并发/非 ASCII 问题与 T06-C06 扫描失败；真实资产/跨租户读搜导出未验 |
| frontend | failed | 常规 30 passed；自主恢复切换例失败；组件证据不是浏览器验收 |
| integration / e2e / live / manual | not_run | 首轮未跑真实 PG/容器、浏览器、外部能力与人工视检 |

对资源与性能，仅看到了连接/pool 的配置边界及关闭端口负例。还需在隔离 PG 上测试锁等待/慢查询对 ready 的实际时限，以及多进程/重启、撤销传播、共享限流；目前不能把“配置超时”当成每条 SQL 都有有界执行证据。不可变历史、失效重判和搜索回查属于后续任务，本报告不给它们 passed。未新增基础框架或依赖，检查脚本复用 JUnit/成熟工具、认证复用 Argon2/SQLAlchemy 的方向合理；没有有具体案例的多余复杂度删除项，不编造可节省行数。

审查产物仅本报告及 `reports/runs/recovery_r01_behavior_review_1_20261014/` 下的外置复现脚本、日志、命令和快照；未改金标、阈值、计分分母、公共合同、状态或用户秘密，也未 push。E1/R2 的锁定安装、静态检查、默认路由与明确故障证据可供后续引用；安全 gate、完整运行工程及浏览器验收尚不闭合，不折算分数或整卡完成。

**结论：先修 1–6 并冻结新 SHA 定向复核，本切片暂不放行。** Compose/worker、隔离 PG 持久化和后续测试准备可以在不依赖本切片“已通过”结论的边界内继续独立开发；不得登记整 R01/R02 前置已满足，也不得越过 G-A 阶段检查点。下一步优先复验此处缺陷，再做真实 PG/浏览器与阶段集成的新独立审查。

