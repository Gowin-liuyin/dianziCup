# T40-A · 后端接口合同核对报告（只读取证）

- 任务：T40-A（G3-T40 前端认证/工作台的权威接口合同核对）
- 范围：只读 `backend/`（含 T02/T06 实现与测试）、`contracts/`、`docs/plan/05_api_and_tool_contracts.md`、`progress/task_state.json`、`scripts/admin_user.py`、`infra/compose/compose.yaml`；仅写本报告
- 未做：未改任何代码；未跑全量测试（仅只读探针 + 读测试取证）；不输出任何密钥值（仅字段名）
- 取证方式：读源码与测试；用 `backend\.venv\Scripts\python.exe` + `fastapi.testclient.TestClient` 对 `create_application()` 做只读 HTTP 形状探针（探针脚本在 %TEMP%，未落仓库）
- 取证日期：2026-09-30 之后的本轮会话；代码基线 = 当前工作树（git 未做任何写操作）

---

## 0. 结论摘要（先看这里）

**核心事实：后端目前只有 2 个真实业务端点（health），认证/CSRF/当前用户/注销全部没有 HTTP 路由。**
T06 的认证能力以 Python 服务类 `AuthenticationSessionService`（`backend/src/ai_intel/api/authentication.py`）实现并通过安全测试，但没有挂到 FastAPI 路由；`create_application()`（`backend/src/ai_intel/api/app.py`）只装配 `/health` 路由。前端 T40 若按 `docs/plan/05_api_and_tool_contracts.md` 的 `/auth/login`、`/auth/me` 等路径开发，全部会命中 404。

### 端点表（以代码为准，实测状态码）

| 方法 | 真实路径 | 实测响应 | 来源 | T40 可用性 |
|---|---|---|---|---|
| GET | `/health/live` | 200 `{"status":"live"}` | `api/app.py:22-25` | 可用（探活） |
| GET | `/health/ready` | 503 `{"status":"not_ready","reason":"..."}` | `api/app.py:27-36` | 可用（依赖未接入时如实 not_ready） |
| GET | `/openapi.json` | 200，OpenAPI 3.1.0，info={title:"ai-intel-backend", version:"0.1.0"}，paths 仅含上述两条 | FastAPI 自动生成 | 可用作类型生成源，但只覆盖 health |
| GET | `/docs`、`/redoc` | 200（Swagger/Redoc HTML） | FastAPI 自动生成 | 仅开发调试 |
| — | `POST /auth/login`、`GET /auth/me`、`GET /auth/csrf`、`POST /auth/logout` | **404 `{"detail":"Not Found"}`（实测）** | 无实现 | **不可用（缺口）** |
| — | `/v1/*`（计划统一前缀） | **404（实测）** | 无实现 | **不可用（缺口）** |
| — | 其余 05 §3 清单（/sources /events /assets ...） | 无路由 | 未实现（T24+ 未开始） | 不可用 |

实测探针输出（节选，非密钥）：

```
GET /health/live  -> 200 {"status":"live"}
GET /health/ready -> 503 {"status":"not_ready","reason":"external dependencies not configured (database/cache/search 由 T03/T05 接入)"}
GET /auth/me      -> 404 {"detail":"Not Found"}
POST /auth/login  -> 404 {"detail":"Not Found"}
GET /openapi.json -> 200  openapi paths: ['/health/live', '/health/ready']
```

### 缺口清单（详见 §6）

1. 无 `POST /auth/login`、`GET /auth/me`、`GET /auth/csrf`、`POST /auth/logout` 任何 HTTP 路由（T40-C01/C02/C05 无法接通真实接口）。
2. 无统一错误体（计划 `error.code/message/retryable/details/trace_id`）；现状 404/405 是 FastAPI 默认 `{"detail":...}`，422 是 `{"detail":[{type,loc,msg,input}]}`，服务端异常是 **500 text/plain "Internal Server Error"**。
3. 认证异常（InvalidCredentialsError/SessionExpiredError/CsrfRejectionError/LoginRateLimitedError/PermissionDeniedError/CrossTenantAccessError）未映射到任何 HTTP 状态码（401/403/404/429 语义只存在于 Python 层）。
4. 会话 Cookie 名、CSRF 提交头/字段名、CSRF 下发方式均未在代码中定义（只有 cookie 属性字典）。
5. 无 CORS/中间件配置；无会话刷新/续期端点（TTL 30 分钟硬过期）。
6. 计划中的 `Idempotency-Key`、cursor 分页、`/v1` 前缀、202+job_id 约定均无实现。
7. `contracts/schemas/schema_bundle.json` 只含 5 个领域记录 schema，**不含任何 HTTP 请求/响应 DTO**，无法按 T40 要求"API 客户端从合同生成"出认证接口类型。

---

## 1. 可用端点（真实路径，以代码为准）

### 1.1 HTTP 层唯一业务端点

`backend/src/ai_intel/api/app.py`（全文 41 行）：

- `create_application() -> FastAPI`：`FastAPI(title="ai-intel-backend", version="0.1.0")` + 仅 `include_router(build_health_router())`。
- `GET /health/live`（`app.py:22-25`）→ 200，body `{"status": "live"}`。语义：仅进程存活，不代表依赖可用。
- `GET /health/ready`（`app.py:27-36`）→ **503**，body `{"status": "not_ready", "reason": "<未接入原因文本>"}`。语义：外部依赖（database/cache/search）未接入时如实 not_ready，不得谎报 ready。依赖接入细节见 `infrastructure/settings.py:71-78 describe_dependency_readiness`（database/cache → configured|not_configured；search → configured|degraded_search_not_configured）。

### 1.2 FastAPI 自动端点（非业务，但前端可依赖）

- `GET /openapi.json`：OpenAPI 3.1.0；info.title=`ai-intel-backend`，info.version=`0.1.0`；**paths 只有 /health/live、/health/ready**。可用作"当前真实合同"的机器可读源（但 T35 前不会有认证/业务路径）。
- `GET /docs`、`GET /redoc`、`GET /docs/oauth2-redirect`：Swagger/Redoc 页面。

### 1.3 明确不存在的端点（实测 404）

`POST /auth/login`、`GET /auth/me`、`GET /auth/csrf`、`POST /auth/logout`、`GET /v1/auth/me` 均返回 404 `{"detail":"Not Found"}`。**不要按 05 §3 清单猜路径开发真实调用**——那份是"待实现接口"计划，不是现状。

### 1.4 非 HTTP 但属于认证合同的真实入口

- `scripts/admin_user.py`：管理 CLI（预创建用户，无公共注册）。入参 `username`、`--tenant <id|none>`、`--role <role>`；密码经环境变量键名 `ADMIN_USER_PASSWORD` 或无回显提示读取（不进 argv/日志；本报告不记任何值）。约束：`system_admin` 必须 `--tenant none`，其余角色必须带租户；重复用户名非零退出。
- 前端运行所需的服务地址/端口：**仓库中不存在 API 服务启动命令**（`scripts/dev.py` 只有 check/services 子命令；`infra/compose/compose.yaml` 只编排 postgres/redis/opensearch，数据服务端口仅绑 127.0.0.1）。uvicorn 装在 venv 里但无任何脚本/编排启动 `ai_intel.api.app:app`。

---

## 2. 请求/响应字段与枚举（认证状态/租户/权限语义）

### 2.1 认证域对象（`api/authentication.py`，服务层，非 HTTP DTO）

| 对象 | 字段（仅字段名） | 语义 |
|---|---|---|
| `Principal`（:47-53） | user_id, tenant_id, role | 已认证主体，由服务端从有效会话得出 |
| `UserAccount`（:56-64） | user_id, username, password_hash, tenant_id, role | 预创建用户，只存 Argon2id 哈希（$argon2 前缀），无明文 |
| `SessionRecord`（:67-75） | session_id, user_id, expires_at, csrf_token, revoked | 不透明会话；session_id 存的是服务端 SHA-256(`_session_key`, :309-312)，**明文 token 不落存储** |
| `login()` 入参（:212-214） | username, password, origin, client_key | client_key 用于登录限流 |
| `login()` 返回（:234-246） | (session_token, SessionRecord) | session_token=`secrets.token_urlsafe(32)`；csrf_token=`secrets.token_urlsafe(32)`，绑定会话 |

数据库 `users` 表（`migrations/versions/0003_users.py`）：user_id, username(unique), password_hash, tenant_id(nullable), role(CHECK 四值), created_at；CHECK：`(tenant_id IS NULL AND role='system_admin') OR tenant_id IS NOT NULL`。

### 2.2 角色与权限（`domain/access.py`）

- `Role`（StrEnum，四值）：`tenant_admin` / `system_admin` / `analyst` / `viewer`。
- 权限串（6 个）：`read:asset`、`write:asset`、`read:public`、`manage:users`、`read:audit`、`manage:public_sources`。
- 权限矩阵 `ROLE_PERMISSIONS`（access.py:27-34）：
  - system_admin：全部 6 权限，tenant_id 必为 None
  - tenant_admin：read:asset, write:asset, read:public, manage:users, read:audit（**无 manage:public_sources**）
  - analyst：read:asset, read:public
  - viewer：**仅 read:public**
- `permission_version` = `PERMISSION_VERSION` = 1（`AccessScope` 携带；前端可据此判断权限表代际）。
- 越权抛 `PermissionDeniedError("permission required: <permission>")`（不静默降级）。

### 2.3 租户与可见性语义（访问状态）

- `AccessScope`（frozen dataclass）：user_id, tenant_id, role, permissions, permission_version；**只由服务端从会话构造**（`AuthenticationSessionService.build_access_scope` :271-276），请求体自报 user_id/tenant_id/role 无入口，若有提交则记审计事件 `identity_spoof_attempt`（只记字段名 submitted_keys + trace_id，不记值）。
- 记录可见性两值：`public`（全员可读）与 `tenant`（仅同租户；tenant_id 相等且非空）。未知可见性一律不可见（`can_access` :67-73）。
- 跨租户/不可见 → `CrossTenantAccessError("resource not found")`：**统一 404 语义**（由调用方转换），不泄露对象名称与存在性。
- 范围化查询范式 `filter_visible_rows(scope, rows) -> list[int]`：公共证据与私有资产按同一规则分离，不可见行不进结果。

### 2.4 其他领域枚举（`domain/enums.py`，供 T40 状态组件对齐）

`SourceCategory`(8 值)、`DocumentKind`(7)、`ClaimOrigin`(5: source_explicit/structured_source/rule_derived/model_hypothesis/human_confirmed)、`ClaimStatus`(5: supported/disputed/unverified/superseded/withdrawn)、`ConditionValue`(4: true/false/**unknown**/conflict，unknown≠false)、`DimensionStatus`(7: available/not_found/not_applicable/conflict/blocked/failed/pending)、`FreshnessStatus`(3: current/stale/unknown，缺观察时间不得填 current)、`RuleStatus`(4)、`AssessmentStatus`(4: supported_applicability/excluded_with_evidence/insufficient_evidence/conflicting_evidence)、`ToolStatus`(7: 含 denied/failed/budget_exhausted/not_configured，语义互异)、`JobStatus`(8: queued/running/retry_wait/waiting_approval/succeeded/partial/failed/cancelled)、`PocStatus`(4: static_reviewed≠lab_verified)。

### 2.5 本地 OpenAPI / JSON Schema 现状

- **OpenAPI**：仓库无静态 openapi 文件；唯一机器可读合同是运行时 `GET /openapi.json`（仅 health 两条）。
- **JSON Schema**：`contracts/schemas/schema_bundle.json`（由 `domain/schema_export.py` 确定性生成：sort_keys+固定缩进+schema_version）：`schema_version=1`，generator=`ai_intel.domain.schema_export`，含 5 个记录 schema：`SourceRecord`（source_id,name,category,base_origin,scope）、`DocumentRecord`（document_id,kind,title,published_at?,retrieved_at,content_hash,scope）、`EvidenceRecord`（evidence_id,document_id,span,quote,supports_claim）、`ClaimRecord`（claim_id,subject,predicate,object_value,claim_status,claim_origin,condition_value,freshness,asserted_at,observed_at?,scope）、`AssessmentRecord`（assessment_id,asset_id,claim_id,status,decided_at,evidence_ids,scope）。**均为领域记录 schema，不含认证/会话/错误响应 DTO。**
- `contracts/task_manifest.json`、`contracts/requirements.json`、`contracts/baselines/plan_baseline_t01.json` 是任务/评分合同，不是 API schema。

---

## 3. CSRF 流程（cookie/token 名、提交方式、拒绝行为）

来源：`api/authentication.py`（T06-C04 实测断言见 `tests/security/test_t06_authentication_and_scope.py:95-112`）。

1. **令牌生成与绑定**：登录成功时随会话生成 `csrf_token = secrets.token_urlsafe(32)`（:239），与 `SessionRecord` 一一绑定；会话以 SHA-256(明文 token) 为键存服务端。
2. **写请求校验** `validate_write_request(session_token, csrf_token, origin)`（:278-292），顺序与拒绝行为：
   1. 会话未知/已注销/已过期 → `SessionExpiredError("session is not valid")`
   2. CSRF 不匹配（`hmac.compare_digest` 常量时间比较）→ `CsrfRejectionError("csrf token mismatch")`
   3. Origin 缺失（None）或不在允许清单 → `CsrfRejectionError("origin not allowed")`
3. **登录本身不查 CSRF，但查 Origin**：`login()` 中 origin 非 None 且不在 `allowed_origins` → `CsrfRejectionError("origin not allowed")`（:217-218）。
4. **Cookie 策略** `cookie_attributes()`（:294-296）：`httponly=True`、`samesite="strict"`、`secure`（仅 `APP_ENV=production` 为 True；`cookie_secure_for_environment` :78-80 显式 False 而非默认放行）。测试证据：`test_cookie_policy_requires_secure_in_production`。
5. **未定义（=缺口）**：
   - **Cookie 名**：全仓库无 `set_cookie`/cookie 名常量（grep 0 命中）；只有属性字典。计划要求"由登录响应或认证后的 csrf 接口取得，前端内存使用"，但取值通道（响应体字段 vs cookie vs 头）未定。
   - **CSRF 提交方式**：header 名（如 X-CSRF-Token）或 body 字段名未定义——服务层签名只有 `csrf_token` 参数。
   - **允许 Origin 清单**由构造参数 `allowed_origins` 注入（测试用 `https://workbench.test`），生产取值未接线到 settings（`ApplicationSettings` 无 allowed_origins 字段）。
   - **无 CORS 中间件**（`create_application()` 的 user_middleware 为空，实测）：若前端与 API 不同源，浏览器跨源带凭据请求将被同源策略拦下，与"不得用开放跨域加 credentials"的 05 §1 约定之间缺少落地配置。

---

## 4. 错误行为（状态码与消息形状）

### 4.1 实测 HTTP 形状

| 场景 | 实测状态码 | 实测 body 形状 | 依据 |
|---|---|---|---|
| 未匹配路由（含全部 /auth/*） | 404 | `{"detail":"Not Found"}`（JSON） | FastAPI 默认；探针实测 |
| 方法不允许 | 405 | `{"detail":"Method Not Allowed"}`（JSON） | FastAPI 默认 |
| 请求校验失败（path/query/body 类型或缺参） | 422 | `{"detail":[{"type":"int_parsing","loc":["path","item_id"],"msg":"Input should be a valid integer...","input":"abc"}]}` | FastAPI 0.142.2 默认 RequestValidationError handler；探针实测同版本形状 |
| 服务端未捕获异常 | **500，content-type text/plain** | `Internal Server Error`（纯文本，非 JSON） | 探针实测（`raise_server_exceptions=False`） |
| `/health/ready` 依赖未就绪 | 503 | `{"status":"not_ready","reason":"..."}`（**注意：不是统一错误体**） | app.py:27-36 |

### 4.2 计划 vs 现状

- 05 §2 计划统一错误体：`error.code, error.message, error.retryable, error.details, trace_id`；**现状完全没有**：无自定义 exception_handler（实测 exception_handlers 只有 FastAPI/Starlette 内置 HTTPException/RequestValidationError 两个），业务错误无错误体模板。
- 计划状态码语义（400/401/403/404 统一/409/422/429/503）目前**只以 Python 异常类表达**，未映射 HTTP：

| 异常类 | 消息文本（现状唯一"文案"） | 计划语义 | 现状 HTTP 映射 |
|---|---|---|---|
| `InvalidCredentialsError`（继承 PermissionError） | "invalid credentials"（用户不存在与密码错完全一致，不泄露账户细节；T06-C05 断言两消息相等） | 401 | 无（若在路由内抛出会变 500 text/plain） |
| `SessionExpiredError` | "session is not valid"（未知/注销/过期三态统一） | 401 | 无 |
| `CsrfRejectionError` | "csrf token mismatch" / "origin not allowed" | 403（或 401） | 无 |
| `LoginRateLimitedError` | "too many login attempts" | 429 | 无 |
| `PermissionDeniedError` | "permission required: <permission>" | 403 | 无 |
| `CrossTenantAccessError` | "resource not found" | 404（与不存在统一） | 无 |
| `AuditEventError` | "sensitive field refused in audit event: <key>" | 内部 500/配置错误 | 无 |

- **网络失败/断线**：后端无从表达（属前端行为）；05 §10 要求前端对 queued/running/partial/failed/stale/not_configured 分别展示，接口侧目前连错误体都不提供。
- **5xx 消息形状**：纯文本 "Internal Server Error"，无 trace_id —— 若 T40 需要统一解析错误 JSON，5xx 路径必须按"响应可能不是 JSON"处理。
- 审计安全：审计事件拒绝敏感字段名（password/cookie/token/secret/authorization，大小写不敏感子串匹配，:44,336-343），每事件必带 trace_id；`test_audit_and_sources_carry_no_secret_values_t06_c06` 断言日志无密码/会话 token。

---

## 5. 会话生命周期（登录/刷新/过期/退出）

| 阶段 | 现状行为（服务层） | 证据 |
|---|---|---|
| 创建用户 | 仅预创建：`create_precreated_user`（服务）+ `scripts/admin_user.py`（CLI，落 PostgreSQL users 表）。**无公共注册**（测试断言服务无 `register` 属性、新目录无预置账号） | authentication.py:198-210；test_precreated_users_only_and_no_default_production_account |
| 登录 | 凭证校验（Argon2id verify）→ 签发 session_token(32B 随机) + csrf_token(32B 随机)；TTL = `SESSION_TTL_SECONDS = 1800`（30 分钟）；成功清空该 client_key 的失败计数 | authentication.py:19,212-246 |
| 登录失败 | 统一 "invalid credentials" 并记审计 `login_failed`（reason=invalid_credentials + trace_id）；计一次失败 | :220-233 |
| 登录限流 | 同 client_key 15 分钟窗口（`LOGIN_WINDOW_SECONDS=900`）内失败 ≥5 次（`MAX_LOGIN_ATTEMPTS=5`）→ `LoginRateLimitedError`，不确认账号存在 | :19-21,314-334 |
| 会话校验 | `validate_session` → Principal；未知/revoked/过期（`expires_at <= now`）统一 `SessionExpiredError` | :257-269 |
| **刷新/续期** | **不存在**：无滚动续期、无 refresh 端点，TTL 到点硬过期（测试用 31 分钟时钟推进断言过期） | test_expired_or_unknown_session... |
| 退出 | `logout(session_token)`：服务端置 `revoked=True`，立即失效，**重复注销幂等**；审计 `logout` | :248-255；test_session_lifecycle_and_idempotent_logout |
| 时钟/过期可测性 | 可注入 clock；过期会话过不了写闸门（`validate_write_request` 同样检查过期） | test_identity_spoof_attempt_is_audited_and_write_gate_checks_expiry |
| 凭据存储 | 密码只存 Argon2id 哈希（$argon2 前缀，无明文）；会话明文 token 只以 SHA-256 键存在 | test_password_is_stored_only_as_argon2_hash；:309-312 |
| Cookie 生命周期属性 | HttpOnly + SameSite=Strict；production 强制 Secure（Max-Age/Path/Domain 未定义） | :294-296 |

**前端相关提醒**：会话恢复（T40-C05"刷新后状态恢复"）依赖 `GET /auth/me` 之类的服务端会话回读端点——**该端点不存在**，刷新后无法恢复真实用户/权限，只能记为缺口。

---

## 6. 与 T40 需求的实际缺口清单

对照 `docs/tasks/T40_frontend_shell.md` §4/§5 与 `docs/plan/05_api_and_tool_contracts.md`：

| # | T40 需求 | 现状 | 缺口等级 |
|---|---|---|---|
| G1 | §4.1"使用后端 session/CSRF"；§4.6"接通真实 health/auth 接口" | 认证只有服务类，**无任何 /auth HTTP 路由**（login/me/csrf/logout 全 404 实测） | **阻断**：T40-C01/C02/C05 无法接真实接口 |
| G2 | 当前用户接口（05: GET /auth/me：当前用户、tenant、角色，不返回凭据） | 不存在；Principal(user_id,tenant_id,role) 只在 Python 层 | 阻断（工作台"真实用户/权限"展示无数据源） |
| G3 | CSRF 取值/提交通道合同（05 §1：登录响应或 csrf 接口取得，前端内存使用） | csrf_token 存在但**下发通道、cookie 名、提交 header/字段名均未定义**；无 GET /auth/csrf | 阻断（前端无法实现写请求） |
| G4 | 统一错误体 `error.code/message/retryable/details/trace_id`（05 §2） | 无；404/405=`{"detail":"..."}`，422=`{"detail":[{type,loc,msg,input}]}`，5xx=**text/plain**，/health/ready 又是第三种形状 | 高（T40-C03 错误面板只能按三种形状分别写解析） |
| G5 | 401/403/429/404 语义 | 只有 Python 异常类与消息文本，无 HTTP 状态码映射 | 高（前端无法据状态码分流"转登录/无权限/限流"） |
| G6 | 会话过期→刷新/恢复（T40-C05） | TTL 30 分钟硬过期，**无续期/刷新端点** | 中（可用"过期即重新登录"降级，但需在报告标注） |
| G7 | CORS/跨源带凭据（前端 dev server 与 API 分端口是常态） | 无 CORS 中间件、allowed_origins 未进 settings、无启动命令/端口约定 | 高（开发态联调即被浏览器同源策略挡住） |
| G8 | "API 客户端从合同生成或严格匹配类型"（§4.2） | `schema_bundle.json` 仅有 5 个领域记录 schema；`/openapi.json` 仅 health；**无认证/错误 DTO 合同** | 高（认证类型只能手写"严格匹配"，须在 T40.md 记为偏离） |
| G9 | T40-C04 stale/partial/unknown 语义 | 枚举合同齐备（FreshnessStatus/DimensionStatus/ClaimStatus/ConditionValue/ToolStatus/JobStatus，见 §2.4） | 无缺口（类型层面可做）；但尚无业务接口返回这些值 |
| G10 | T40-C03 掉线/重试 | health/live、health/ready 可用作掉线探测（ready 语义诚实） | 小缺口：ready 常态 503（依赖未接入），前端须区分"not_ready=降级"与"网络断线" |
| G11 | 前端运行需要 API base URL/启动方式 | 无 uvicorn 启动脚本/编排服务；compose 只有 postgres/redis/opensearch（端口仅 127.0.0.1） | 中（需 T35 或变更单补 API 服务入口） |
| G12 | 05 §2 写接口 `Idempotency-Key`、cursor 分页、`/v1` 前缀、202+job_id | 全部无实现 | 低（属 T35 统一业务 API 范围；T40 只需不假设存在） |

### 建议给 T40 的最小合同口径（不改后端前提下的诚实做法）

1. **API 客户端只把 `GET /health/live`、`GET /health/ready` 当已实现端点**；auth 调用层按本报告 §3/§5 的服务层语义先定义 TypeScript 接口并标注 `blocked_backend_route`，不得假装已联通。
2. 错误解析写成三形状兼容：`{detail: string}`、`{detail: DetailItem[]}`（422）、非 JSON 文本（5xx）；并对计划的 `error.*` 统一体做"待合同"占位。
3. T40-C01/C02/C05 的验收在 auth 路由落地前只能记 `blocked`（缺最小所需输入：POST /auth/login、GET /auth/me、POST /auth/logout、GET /auth/csrf 四个路由 + 错误体/cookie/header 命名合同），不得用 mock 冒充通过。
4. 需要后端配合的最小合同变更（建议走变更单）：定 cookie 名、CSRF header 名、错误体形状、状态码映射、allowed_origins 配置项、会话续期策略。

---

## 7. 取证记录

- 读取：`backend/src/ai_intel/api/app.py`、`api/authentication.py`、`domain/access.py`、`domain/enums.py`、`domain/schema_export.py`、`infrastructure/settings.py`、`migrations/versions/0003_users.py`、`scripts/admin_user.py`、`backend/tests/unit/test_t02_project_skeleton.py`、`backend/tests/security/test_t06_authentication_and_scope.py`、`backend/tests/unit/test_t06_access_scope_boundaries.py`、`docs/tasks/T40_frontend_shell.md`、`docs/plan/05_api_and_tool_contracts.md`、`progress/task_state.json`、`reports/tasks/T06.md`、`infra/compose/compose.yaml`、`contracts/schemas/schema_bundle.json`（经 `build_schema_bundle()` 摘要）。
- 运行：`backend\.venv\Scripts\python.exe <TEMP>\t40_contract_probe.py / t40_contract_probe2.py`（只读 TestClient 探针；输出见 §0/§1/§4）。退出码 0。
- **未运行**：全量 pytest（按任务约束 not_run）；不修改任何仓库文件（本报告除外）。
- 任务状态引用：`progress/task_state.json` — T02 accepted/complete、T06 accepted/complete（security 9/9、unit 34/34、integration 回归 15/15、live=not_run）；T40 pending/not_started。
- 测试取证（未改）：T06-C01 会话生命周期、T06-C02 跨租户不可见无名称泄露、T06-C03 请求体自报身份忽略、T06-C04 CSRF+Origin 拒绝、T06-C05 过期/限流/统一报错、T06-C06 审计与源码无密钥值；T02-C06 health/ready 诚实 not_ready。
- 密钥处理：本报告仅出现字段/变量名（ADMIN_USER_PASSWORD、DATABASE_URL、auth_secret_ref、POSTGRES_PASSWORD 等），**未记录任何值**；compose 中的开发占位值亦未复制。
