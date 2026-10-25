# P-03 · MCP/OAuth/CLI 三插件（含 /tasks producer 链并入）

- 文档首次创建时间：2026-10-25T10:00:00+08:00
- 本次写作开始时间：2026-10-25T10:00:00+08:00
- 最后更新时间：2026-10-25T10:00:00+08:00
- 状态：立项卡（待评审）；实施批的步骤依据

## 目标

把公开集成面补齐为可用生态：**/tasks typed-task producer 链**（OQ-4）+ **MCP server 传输** + **OAuth/OIDC 认证** + **运维 CLI**，对应评分项：完整 Agent 对外集成（R18 后续）、公开 API 面完整性。

**OQ-4 的 /tasks producer 并入本卡的理由**（批处理授权时要求明确判断）：/tasks 端到端闭环（ask 受理入队 + typed job 绑定 + 发布）与三插件共享同一公共合同域（公开读路由语义、认证上下文、typed job 契约）——`PublicTaskBindingService` 的三个方法（bind/publish_result/read_in_session）就是 MCP server 与 CLI 轮询任务结果的读面；单列会造成同一批冻结断言（`test_r18_public_read_producer_pg.py:250` 的 503 桩语义）被两个批次先后触碰、两次 CR。并入后一次 CR 一次重测。

## 现状与已有基础（路径全部实测存在）

- 公开只读路由（4 条）：`backend/src/ai_intel/api/public_extension_routes.py`（GET /vulns :140、/vulns/{id} :148、/sources :157、/tasks/{task_id} :165；错误映射 :135-138）。
- reader：`backend/src/ai_intel/api/public_extension_reads.py`（`PublicExtensionReadService` :145，公开方法 search_vulns/get_vuln/list_sources/get_task_result :812）。
- **/tasks 桩**：`get_task_result` 恒 503（`public_extension_reads.py:812-816`；OQ-4 记录的行号 801-805 已漂移），冻结断言 `backend/tests/integration/test_r18_public_read_producer_pg.py:250`。
- **producer 零装配**：`backend/src/ai_intel/api/public_task_bindings.py`（表定义 :60-104、不可变触发器 :106-120、`PublicTaskBindingService` :265、`bind_in_session` :421、`publish_result_in_session` :539、`read_in_session` :594）——src 零调用方，app.py 未装配；迁移 `backend/migrations/versions/0031_public_task_bindings.py`。6 个测试文件已覆盖合同/unit/integration/security 面（`backend/tests/contract/test_r18_public_task_binding_contract.py` 等，全清单见盘点）。
- 同族未接线模块：`backend/src/ai_intel/api/public_risk_summary.py`（有实现无路由）。
- typed job 基础设施（可直接复用）：`backend/src/ai_intel/infrastructure/outbox.py`（事务内 enqueue_job）、`backend/src/ai_intel/workers/executor.py`（默认原子 + detached 执行器）、`workers/jobs.py`（租约/状态权威）、`workers/runtime.py`（**真实队列是 Celery+Redis**）、`workers/investigation.py`（Celery 任务样例）。
- MCP：**backend 侧零实现**；SDK 客户端侧已有 stdio MCP：`sdk/python/ai_intel_client/mcp_stdio.py`、`mcp_adapter.py`（冻结 read-tool DTO 的官方 MCP transport handlers）+ 测试 `sdk/python/tests/test_mcp_adapter.py`；决策文档 `docs/decisions/CR-R18_http_mcp_transport.md`。
- OAuth/OIDC：**零实现**（backend src 对 oauth/oidc/jwt 零匹配）；现有鉴权为自研 Bearer/API-key：`backend/src/ai_intel/api/auth_routes.py`、`authentication.py`、`credentials.py`、`credential_models.py`、`auth_state.py`、`actor_references.py`。
- CLI：backend 无 `__main__`/click/typer/`[project.scripts]`；仓库根 `scripts/` 有运维脚本（`admin_user.py`、`backup_restore.py`、`migrate.py`、`security_scan.py` 等）；SDK CLI：`sdk/python/ai_intel_client/cli.py`（entry `dianzi-intel`，`sdk/python/pyproject.toml:25`）。
- 测试面：R18 公开面 unit 10 文件、integration 5、security 2、contract 11（全清单见盘点报告）。

## 分批步骤（每批一个可提交单元）

- **B1 /tasks producer 链**（触冻结合同——见风险1）：ask 受理路径在既有同步应答外按需入队 typed job（或新增显式异步受理开关，默认关），`PublicTaskBindingService.bind_in_session` 装配进受理流程，`get_task_result` 从 503 桩改为经 `read_in_session` 的真实读取（503→404 语义变更走 CR）。验收：`test_r18_public_read_producer_pg.py` 按修订后合同全绿 + 新增 producer integration 全绿；离线全量 failed 0。
- **B2 MCP server 传输**（backend 侧）：`backend/src/ai_intel/api/mcp_routes.py` 或独立 server 进程装配 read-tool 的 MCP transport（复用 SDK 侧 `mcp_adapter.py` 的 DTO 合同，对称实现 server 端），工具面=公开只读 4 端点 + /tasks。验收：新增 contract + integration 测试全绿（stdio 合同对拍 SDK 客户端）。
- **B3 OAuth/OIDC**（触认证合同——见风险2）：新增 OIDC 授权码流 provider（issuer 发现、PKCE、会话映射到既有 `AuthenticationSessionService`），自研 Bearer/API-key 保持默认，OAuth 显式配置才启用。验收：新增 security + integration 测试全绿；`test_r01_*`/`test_r02_*` 认证回归全绿。
- **B4 运维 CLI**：`backend/pyproject.toml` 增加 `[project.scripts]` 入口 + `backend/src/ai_intel/cli.py`（migrate/admin/smoke/backup 子命令包装既有 `scripts/` 能力，不新增任意 SQL/shell 工具——安全边界不变）。验收：CLI 合同测试 + `uv run dianzi-intel --help` 冒烟。

## 明确不做

- 不做 MCP write 工具、任意 URL 读取、任意 SQL/shell 工具（AGENTS.md 安全边界）。
- 不引入第三方 OAuth 服务的真实外呼测试（provider 交互以本地 fixture/模拟 issuer 验证；真实提供方联调记 not_run）。
- 不把 Celery 结果后端当业务真相（PostgreSQL 权威不变量）。

## 风险与合同触点

1. **B1 触冻结断言**：`get_task_result` 的 503 桩语义被 `test_r18_public_read_producer_pg.py:250` 冻结；503→404/200 语义变更必须 CR + 该文件全量重测（批次22 CR 的重测纪律）。
2. **B3 触认证公共合同**：`auth_routes`/`actor_references` 的会话语义被 R01/R02/R18 多面测试冻结；OIDC 身份映射不得绕过 `tenant`/`role` 边界（安全测试 44 文件为回归门）。
3. **B2 触公开 DTO**：MCP 工具响应复用公开读 DTO（`graph_contracts.py` 链）——字段级合同以既有 DTO 为准，不另造平行结构。
4. typed job 入队不得破坏 outbox 事务一致性（`outbox.py` 的 enqueue 契约测试 `backend/tests/contract/test_t07_jobs_outbox.py` 为回归门）。

## 预估批次数

4（B1–B4 各一批；B1/B3 各含一次 CR）。

---

## 路径核对记录（2026-10-25T10:1x+08:00 复核：脚本化逐一 ls 全部引用路径 106 项，唯一失配 experiments/run_eval.py 的误写已修正为仓库根路径；核对脚本输出见 reports/runs/batch23_projects_path_check.txt）

- 抽查核对：`public_extension_routes.py` 4 路由行号、`public_task_bindings.py` 三方法行号、`0031_public_task_bindings.py`、Celery 依赖（`backend/pyproject.toml:15`）、SDK mcp 两文件、`docs/decisions/CR-R18_http_mcp_transport.md` 均存在。
- 确认不存在（已搜索核实）：backend 侧 MCP server、OAuth/OIDC/JWT 实现、backend CLI 入口、`PublicTaskBindingService` 生产调用方、/tasks typed producer 链、backend/scripts/ 目录、除 GitHub Actions 外的 CI 配置。
