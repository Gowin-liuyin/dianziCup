# G-E · R18 public ask 独立审查 1

首次创建：2026-10-17T07:09:47+08:00（已读 UTC 工具时钟换算）。本报告为固定源码的独立审查；结论 `needs_changes`，不登记 accepted，不签整 R18 或阶段通过。实际 PG 与 CBM 排他窗口尚未执行。

这项改动做什么：新增 `build_public_ask_router`，把公开 `/ask` 的原始 JSON、cookie/Bearer 和幂等键接到既有 `GroundedQuestionService.ask`。route 用当前真实 credential 建立内部 actor，200 返回共享服务已完成的 QAAnswer；不支持的调查、多资产、多轮和历史问题保留共享服务的明确拒绝。

## 固定范围与独立性

- 受审 source：`5028566db834a44d4124d37a6de5cb39c25786c7`。
- 独立工作树：`D:/wt/r18-public-ask-review1-20261017`；分支 `codex/r18-public-ask-review1-20261017`。由 Root repository 的固定 commit 建立，未审作者移动目录中的业务代码。
- 直接父提交：`6aeb40b5d47573176c251485622649d4c58c91db`。作者报告声明其为 `0bcabdcb5a511ce83e92b74683597c63b7a9a9cf` 加 `b482afb4dc256df959142129de19921ba0c4ac21` 的四个只读依赖；本次围绕 source 的实际调用链审查，不替代依赖切片全部历史验收。
- source 只新增四个文件：`backend/src/ai_intel/api/public_ask_routes.py`，对应 unit、contract、integration 三个测试文件。独立 `git show` 与 snapshot 的 LF 字节逐一相等，Git blob 分别为 `f4a8e23148419a45805e9253ab4e434a6530646b`、`3aeea99a2484611365af1e2c962397cf5941f05a`、`eaa4a408dc50c8ce30558bc5ea1d5d4c1f101d38`、`ec67c8b9c14d9b6e84d3b6fe94bab3b27b228c75`。
- 已读 AGENTS、00 execution map、R18 recovery card、T35/T51、03/04/05、状态与最近交接，Root 当前 `CR-R18_public_ask_route.md`、credential/actor/reservation/public envelope CR；使用 Ponytail plugin 5.3.1 review。没有派孙代理。
- 本次只新增本报告与自有 run 证据、探针和 runner；未修改业务、原测试断言、进度、金标、阈值、依赖或公共合同。未 commit/push。

## Must fix

1. **P2：深层 JSON 逃逸为普通 500**（[public_ask_routes.py:195](D:/wt/r18-public-ask-review1-20261017/backend/src/ai_intel/api/public_ask_routes.py:195)，[json_output.py:27](D:/wt/r18-public-ask-review1-20261017/backend/src/ai_intel/infrastructure/models/json_output.py:27)）
   - **是什么：**route 调用冻结公开 parser 后仅捕获 `ValueError`。共享 `strict_json_object` 先执行 `json.loads`，随后才检查最大深度 32 和最大节点数 1000。
   - **问题和输入：**`{"question":` + 20000 个 `[` + `"fixture"` + 20000 个 `]` + `}`，共 40022 字节；带合法语法的 fixture Bearer、单一幂等键与 JSON Content-Type。它远小于 1MiB，但 JSON decoder 抛 `RecursionError`；真实 TestClient HTTP 为 500，body 是普通服务器错误，而不是合同规定的 422 `application/problem+json`。本负例无 PG、模型或真实秘密。
   - **最小修复：**在此 route 的解析异常边界将 `RecursionError` 与 `ValueError` 映射到同一固定 422；或者经公共 helper 的既定 ownership 授权，让 `strict_json_object` 把 decoder 递归失败转换成 `ValueError`。保留既有深度/节点/1MiB限制，不能提高 Python 递归上限或扩大 JSON 深度来掩盖错误。
   - **不修影响：**公开的畸形输入绕过统一错误合同；SDK 得不到稳定的 validation problem，合法认证客户端能触发未处理异常。未观察到凭据泄漏或数据库写入，不扩大该结论。
   - **复验：**保留并在新的独立 source 上复跑 `test_review_http_negatives.py::test_deep_json_returns_public_422_without_unhandled_error[20000]`，要求 422、`error.code=validation_error`、problem 媒体类型和 no-store；同时复跑原 route 54 个 unit/contract、浅深度 33/1500、嵌套重复键和超限体积负例。当前红证据是 `independent_http_negatives_corrected_fixture.{command.json,stdout.log,junit.xml}`；`snapshot_inspection.json` 独立记录原始 decoder 异常类型 `RecursionError`。

风格偏好没有列为阻断；未发现另一个已有可复现场景的 Must。

## 已核验行为与证据边界

| 项目 | 结果和证据 | 限制 |
|---|---|---|
| cookie/Bearer、匿名、混合、重复、query | 新 unit/contract 及自有负例拒绝重复 Authorization、cookie、幂等、媒体 header 和大小写 query 凭据；混合 cookie/Bearer 不借 cookie 身份 | PG 当前状态尚未实际复跑 |
| cookie Origin/CSRF | 缺失、重复、错误值、外域在调用 PG/service 之前拒绝；复用原 `validate_write_request` | fixture HTTP 断言，尚非默认 App 浏览器实测 |
| raw JSON/DTO | 无效 UTF8、NaN、重复 JSON 字段、伪造租户/owner/role/scopes/actor/data_mode、非公开 UUID/timestamp、空问题明确 422；1MiB 本身可接受、加一字节拒绝；嵌套重复/无效 surrogate/overflow 拒绝 | 深层 decoder Must 仍红；TestClient 会合并生成器块，体积探针不冒充真实 uvicorn 分块网络实测 |
| 当前 principal/actor | route 132–145 每次 scope_provider 开新短事务，用同一 credential 锁当前 principal；初次锁和 actor 创建同事务，READ_PUBLIC 从实际 scope 取得 | 静态追踪、unit identity/事务计数；真实 PG expiry/revoke/owner 竞态未跑 |
| shared ask 新预约/额度/重放 | `answering/service.py` 309 起使用同 actor 和 credential；390 起先锁身份，新 answer insert 成功后同事务消费 ask bucket，冲突分支不消费；prior/replay 走当前授权读取 | 已复跑相关 unit/contract；新 PG rollback、并发与两 owner 尚待真实窗口 |
| 外部 IO/最终围栏 | route 的初次 engine.begin 在 `questions.ask` 之前退出；scope_provider 返回前退出事务。共享服务 guard 在外部 IO 前、最终事务验证当前 actor 与 DBclock/证据/epoch/期限；actor 原始权限与当前权限交集，owner/tenant/role/版本不符拒绝 | 源码和相关 unit/contract；PG 实际锁行为尚未认证为通过 |
| 公开结果/错误/秘密 | 200 使用完整 shared QAAnswer model dump，no-store；过期 alias 稳定为 answer_failed。401/403/404/429/503 分类与 Retry-After 不回显敏感异常；actor 无 raw token，route 无凭据输出/日志调用 | 无真实模型、费用或吞吐结论 |
| 真实前端 parser | 独立 source 上新捕获的 fixture HTTP JSON 由实际 `parseQuestionAnswer` 接受；extra authority、task、缺引用、伪 support 和危险 URI 拒绝，共 6 个真实 Node/TS 断言 | fixture response，不是 PG/浏览器/live |

## 真实执行记录

自有 run：[r18_public_ask_review1_20261017](D:/wt/r18-public-ask-review1-20261017/reports/runs/r18_public_ask_review1_20261017)。完整 argv、cwd、起止、exit、birth-aware 外层 PowerShell 全子树和残留在各 `.command.json`；stdout/stderr/JUnit 原始文件保留。统一命令前缀为：

`D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/r18_public_ask_review1_20261017/review_checks.py LABEL ...`

runner 复用已审 `batch13_checks_helper` 与 `batch13_process_metadata`，先加入固定 `D:/wt/r06-activation-database-fix5-20261017/reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py` 的原生 OwnedJob，再启动 check child。实查 512MiB/process、1GiB/job、原生 active cap10、宿主24逻辑核 CPU rate833（约2核）；每条 timeout60s。普通运行 Windows outer peak5–8、owned残留0；各 `.native_job.json` 保存实际 query/readback。未启动 WSL、PG、生产 daemon，未读取 DPAPI/付费密钥或调用付费模型/测绘接口。

| label / `...` 的实际参数 | exit | 实际结果 |
|---|---:|---|
| `route_unit_contract -m pytest --no-cov -q tests/unit/test_public_ask_routes.py tests/contract/test_public_ask_route_contracts.py --junitxml=...` | 0 | 54 passed，10.13s |
| `credential_service_regression -m pytest --no-cov -q`：credential/post_lock/actor/question credential/question routes/public write 的 6 unit + 5 contract，具体11路径见收据 | 0 | 203 passed，4.57s |
| `grounded_output_regression -m pytest --no-cov -q tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py --junitxml=...` | 0 | 113 passed，3.36s |
| `independent_http_negatives -m pytest --no-cov -q ../reports/runs/.../test_review_http_negatives.py --junitxml=...` | 1 | 12 passed、3 failed；reviewer 初始 cookie fixture 错用了 `dianzi_session`，非产品错误，原红保留 |
| `independent_http_negatives_corrected_fixture` 同上，改用真实 SESSION_COOKIE_NAME，并增加 depth20000 | 1 | 14 passed、1 failed，0.91s；唯一业务红是 Must1 |
| `public_pg_collection -m pytest --no-cov --collect-only -q tests/integration/test_public_ask_route_pg.py tests/integration/test_r18_question_credential_pg.py tests/integration/test_r05_question_api_pg.py` | 0 | 67 collected；public19+old48，actual PG=0 |
| `route_ruff -m ruff check` 四受审文件 | 0 | 四文件通过 |
| `route_format -m ruff format --check` 四受审文件 | 0 | 四文件通过 |
| `route_mypy -m mypy src/ai_intel/api/public_ask_routes.py --cache-dir=nul` | 0 | 新 route 一文件通过 |
| `capture_fresh_http ../reports/runs/.../capture_wire.py` | 0 | 重跑一个已执行 fixture 用例生成新 HTTP JSON，不增加 distinct 数 |
| `frontend_real_parser --node ../reports/runs/.../frontend_wire.cjs` | 0 | 实际 TS 5.7.3 parser 的 6 断言通过 |
| `snapshot_inspection ../reports/runs/.../inspect_snapshot.py` | 0 | 逐个 git-show 核四源码，确认无请求体 OpenAPI metadata、确认 RecursionError，XML 去重 |

最终有效输入版本的 distinct pytest case：385，384 passed、1 failed、0 skipped；初始错 cookie fixture 的3红作为仪器/输入失误保留，不能拿其重复通过计数。TypeScript6断言另列，不混入 pytest。所有子集显式 `--no-cov`，原全仓60%覆盖门没有执行，也没有降低。

作者材料仅作为待核输入读过：`D:/dianzi-public-ask-route/reports/tasks/R18-public-ask-route.md` 和 `reports/runs/r18_public_ask_route_20261017/{final_offline.command.json,frontend_response.command.json,evidence_manifest.json}`。作者 285offline、TS5assert、PG67collect 的绿色结论没有替代上述独立执行。

## 未检查、计划偏差与交接

实际 PG `not_run`：B 窗正用于 Root component debug，本 reviewer 没有抢资源。必须在 Root nonce/OID/COMMENT 隔离窗口跑 public19 与 old48，核当前 cookie/Bearer、两个 owner、quota rollback/重放、expiry/revoke、外部 IO 时撤销、current evidence/epoch 和 pending 两 router 并发；collect 不算 passed。

CBM 新独立 WT 的窄 index/architecture/schema/trace `not_run`：等待 Root full16/≤60s 排他窗及执行端口，没有自行启动 WSL。当前只做源码 `rg` caller、schema/export/config 追踪；图索引结果不能替代源码判断。

默认 Root App 尚未 mount 这个 route；固定 App CORS allow_headers 也没有 Authorization。独立 bare-router OpenAPI 确认 `/api/v1/ask` 有 response model，但没有 requestBody metadata。作者已诚实声明这些 Root ownership 接线缺口，本报告不把它们当作者偷偷削减范围；它们仍阻断默认公开产品和整 R18/T35/T51 验收。Root 后续应关联冻结 AskRequest，而不是用内部允许 optional null 的 schema 扩大公开输入。

真实模型/语义资源、live、浏览器、e2e、性能、云 CI/CD、人工均 `not_run`，没有评分优秀、生产可用或全阶段结论。评分证据仅涉及当前 R18/T35 route、T04 公开输入/QA 投影和 T32 credential/budget 接线的离线检查；未替代原T35六项、T51六项和R18全部客户端/插件/异步要求。

下一步：唯一作者修复 Must1，冻结新 source；本非作者在新独立 snapshot 保留原深层 JSON oracle 复验，再由 Root 安排真实 PG 与 CBM 窗。既有状态由 Root 根据完整真实证据登记。

Verdict：先修复 1。本次不 Ship；实际 PG、CBM 和默认挂载缺口保持可见。

## 后续计数勘误 · 2026-10-17T07:21+08:00

原始 `public_pg_collection.stdout.log` 的 67 个实际 node ID 逐文件统计为 public18 + question-credential25 + old-cookie24。前文 public19 + old48 继承了作者/交接的手算口径，现明确更正；总67不变、原18个公开PG案例完整保留，没有增删 case、改断言或分母。原报告与原红的已封副本、原收据不覆盖。fix1 复核另见独立新 source `3873c113c7a1a4a7412dcc8a57c6480ea0f83f0c` 的追加报告，本旧502报告不为新 source 背书。
