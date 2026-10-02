# T40-B · 前端现状图（T40 实现准备，只读盘点）

- 任务：T40-B（T40 前端准备，只读 frontend + 写本报告）｜阶段：G3
- 性质：**现状盘点与落点建议**，未修改任何代码、未新建任何源文件、未复制被测实现作期望值
- 证据基线：HEAD `630d0f8`（main）；盘点时间：2026-10-01（本 session 实测）
- 本报告为 T40 实现前的现状图；文中「建议」均未实施，实施由 T40 主任务按 `docs/tasks/T40_frontend_shell.md` 执行

---

## 1. 现有目录与文件清单

### 1.1 frontend/ 实际布局（排除 node_modules/，实测 `Get-ChildItem -Recurse`）

```
frontend/
├── .npmrc                  # engine-strict=true
├── .nvmrc                  # 24
├── eslint.config.js        # flat config：tseslint recommended + react-hooks recommended；ignores: dist, node_modules
├── index.html
├── package.json            # 见 §2
├── package-lock.json       # 177770 B（T02 实测，vitest ^3 升级后重生成）
├── tsconfig.json           # 见 §3
├── tsconfig.tsbuildinfo    # 构建产物但被 git 跟踪（可忽略项，见 §5）
├── vite.config.ts          # @vitejs/plugin-react + vitest config：environment=jsdom, globals=false
├── dist/                   # 构建产物（.gitignore 已忽略）
│   ├── index.html
│   └── assets/index-DMf2nLNV.js
└── src/
    ├── main.tsx            # createRoot + StrictMode 挂载 App
    ├── App.tsx             # 工作台外壳：h1 + data-testid="connection-status"（「未连接」显式状态）
    └── App.test.tsx        # 1 个 Vitest 用例（防假业务统计）
```

**不存在的目录/文件（T40 目标产物全部待建）**：

| 路径 | 状态 | T40 相关性 |
|---|---|---|
| `frontend/src/app/` | 不存在 | 目标产物（任务卡 §3） |
| `frontend/src/components/` | 不存在 | 目标产物（任务卡 §3） |
| `frontend/src/features/`（任意 feature 模块） | 不存在 | 任务卡 §4.2「按 features 分模块」 |
| `frontend/tests/`（含 `t40_frontend_shell.test.tsx`） | 不存在 | 任务卡指定测试位置 |
| `frontend/e2e/` | 不存在 | 任务卡允许修改但非最低验收载体 |
| `frontend/src/api/` / 任何 fetch 封装 | 不存在 | T40-C01/C03/C05 依赖 |
| `frontend/src/types/` / 任何类型定义 | 不存在 | 任务卡 §4.2 |
| 路由库、状态库、CSS 框架、MSW、jest-dom、user-event | 均未安装 | 见 §5 缺口 |

### 1.2 可复用组件存在性核查（全仓 grep，含 backend/docs）

| 组件 | 是否已存在 | 核查结果 |
|---|---|---|
| EvidenceLink | **不存在** | 全仓仅任务卡文本命中（`docs/tasks/T40_frontend_shell.md:38`） |
| FreshnessBadge | **不存在** | 同上 |
| TaskStatus | **不存在** | 同上 |
| EmptyState | **不存在** | 同上 |
| ErrorPanel | **不存在** | 同上 |

结论：五个统一状态组件全部需要在 T40 从零实现，没有任何既有实现可复用；语义词汇应取自 `backend/src/ai_intel/domain/enums.py`（见 §3.3），不得另造状态字符串。相关命名命中 `DataMode`（`backend/src/ai_intel/infrastructure/settings.py:23`，`Literal["fixture","live"]`）是后端类型，不是前端组件。

### 1.3 既有测试

- `frontend/src/App.test.tsx`：唯一前端测试，断言「未连接」文案与无数字型假统计（正则 `\d+[\s]*(次|条|个|%)`）。可作为断言风格参照（`@testing-library/react` + `vitest` 显式导入，未用 jest-dom）。
- 仓库 `tests/`（根）只有 `tests/plan/test_verify_plan.py`（Python），与前端无关。
- **无任何 t40 或相邻前端测试**；`frontend/tests/t40_frontend_shell.test.tsx` 由任务卡明确声明为「需要本任务创建并实际执行的位置，不是现有测试证明」。

---

## 2. 权威测试 / lint / typecheck / build 命令

### 2.1 package.json scripts（前端权威入口，实测读取）

| 用途 | 命令（工作目录 `D:\dianzi\frontend`） | 实际展开 |
|---|---|---|
| 测试 | `npm run test` | `vitest run` |
| 指定文件测试 | `npm run test -- --run tests/t40_frontend_shell.test.tsx` | `vitest run --run tests/t40_frontend_shell.test.tsx`（任务卡 §6 主检查原样命令；位置过滤按路径子串匹配） |
| lint | `npm run lint` | `eslint .` |
| 类型检查 | `npm run typecheck` | `tsc --noEmit` |
| 构建 | `npm run build` | `tsc -b && vite build` |
| 开发/预览 | `npm run dev` / `npm run preview` | `vite` / `vite preview` |

环境约束（实测）：`engines.node` = `>=24.0.0 <25.0.0` + `.npmrc` `engine-strict=true` + `.nvmrc` `24`；本机 node v24.13.1 / npm 11.8.0 符合。typescript `~5.7.2`、vitest `^3.0.5`（CR-002 记录的主版本升级）、vite `^6.0.5`、react `^18.3.1`。

### 2.2 CI 与计划文档的相互印证

- `.github/workflows/ci.yml` frontend job：`npm ci` → `npm run lint` → `npm run typecheck` → `npm run test` → `npm run build`（Node 24）。与 §2.1 一致，CI 仅编排已实测检查。
- `docs/plan/06_testing_and_evaluation.md` §2 登记的前端命令合同：`npm run lint`、`npm run typecheck`、`npm run test -- --run`、`npm run build` —— 与 package.json 一致。
- `scripts/dev.py check --scope frontend` / `e2e`：**未建设**（`IMPLEMENTED_SCOPES = ("unit","integration","security")`，frontend scope 运行即 exit=3 `not_implemented`）。T40 主检查不得走 dev.py frontend scope，走 npm 原生命令。
- 历史实测（`reports/tasks/T40.md` 应引用新日志，不能引用 T02 的）：T02 最终态 install/lint/typecheck/test/build 全 exit=0、Vitest 1/1 通过（`reports/runs/t02_frontend_checks.log`）。T40 完成后须重新实测并留新日志。

**结论（权威命令表）**：`npm run lint`、`npm run typecheck`、`npm run test`（或指定文件变体）、`npm run build` 四条即 T40 验收命令组合；任务卡主检查是 `cd frontend && npm run test -- --run tests/t40_frontend_shell.test.tsx`。

---

## 3. 类型与 API 客户端现状

### 3.1 TypeScript 严格性（`frontend/tsconfig.json`，实测）

`strict: true` **已开启**，并额外开启：`noUncheckedIndexedAccess`、`noImplicitOverride`、`noUnusedLocals`、`noUnusedParameters`、`noFallthroughCasesInSwitch`、`isolatedModules`、`noEmit`、`types: []`（关闭隐式 @types 全局引入，T02 缺陷 3 修复产物）。target ES2022、moduleResolution bundler、jsx react-jsx。满足 AGENTS.md「TypeScript 开启 strict、不用 Any/cast」要求，T40 新代码会被上述全部约束检查。

**布局对应缺口**：`include: ["src", "vite.config.ts"]` —— **`frontend/tests/` 不在 typecheck/构建覆盖范围内**。任务卡测试位置 `frontend/tests/t40_frontend_shell.test.tsx` 将被 `vitest run` 收集（vitest 默认 include `**/*.{test,spec}.?(c|m)[jt]s?(x)`，默认排除 node_modules/dist），但 `npm run typecheck` 与 `npm run build` 的 `tsc` **不会检查它**。见 §5-G1。

### 3.2 类型来源：生成 vs 手写

- 前端当前**零自定义类型**（无 src/types、无 .d.ts、无接口定义）。
- 唯一机器生成的合同文件：`contracts/schemas/schema_bundle.json`（`schema_version: 1`，generator `ai_intel.domain.schema_export`，656 行，确定性输出）。内容为 Pydantic 导出的 JSON Schema：`SourceRecord`、`DocumentRecord`、`EvidenceRecord`、`ClaimRecord`、`AssessmentRecord` 五个记录类型。其 docstring 明示用途：「生成稳定合同文件供前端类型来源使用」。
- **前端无任何 codegen 工具链**（devDependencies 无 json-schema-to-typescript / openapi-typescript / orval / openapi 生成脚本）。任务卡 §4.2 的合同是「API 客户端从合同生成**或严格匹配类型**」——当前可走「严格匹配手写」路径，把 schema_bundle.json 与 `docs/plan/05_api_and_tool_contracts.md` 作为手写类型的比对基准。
- schema_bundle **未覆盖** T40 所需的：认证/会话 DTO（/auth/login、/auth/me、/auth/csrf 响应）、统一错误体（`error.code/message/retryable/details/trace_id`，05 §2）、健康探针、JobResponse/AnswerResponse。这些需手写类型并严格对照 05 §3/§4 表格字段。
- 权限词汇权威来源：`backend/src/ai_intel/domain/access.py` —— `Role` = viewer/analyst/tenant_admin/system_admin；权限串 read:asset、write:asset、read:public、manage:users、read:audit、manage:public_sources；`PERMISSION_VERSION = 1`。`Principal`(user_id, tenant_id, role) 在 `backend/src/ai_intel/api/authentication.py`。
- 状态词汇权威来源：`backend/src/ai_intel/domain/enums.py` —— `FreshnessStatus`(current/stale/unknown)、`JobStatus`(queued/running/retry_wait/waiting_approval/succeeded/partial/failed/cancelled)、`ConditionValue`(true/false/unknown/conflict)、`ToolStatus`(含 partial/not_configured/budget_exhausted/denied)、`DimensionStatus`、`AssessmentStatus`(四态)。05 §10 前端须展示 queued/running/partial/failed/stale/not_configured。`DataMode` = fixture|live（settings.py）。FreshnessBadge/TaskStatus 的取值必须落在上述集合，**不得把 stale/partial/unknown 渲染成正常态**（T40-C04）。

### 3.3 API 客户端现状：**不存在**

- 前端无 fetch 封装、无 base URL 配置、无错误体解码、无 CSRF 头注入。vite.config.ts 注释明确：「不配置任何真实 API 后端 API 由 T03+ 接入，当前前端显式呈现未连接状态」。
- 后端 HTTP 面（实测 `backend/src/ai_intel/api/app.py`）：**仅挂载 `/health/live`（200 live）与 `/health/ready`（503 not_ready）**。`authentication.py` 有完整领域级 `AuthenticationSessionService`（login/logout/validate_session/build_access_scope/validate_write_request、CSRF+Origin 校验、cookie 策略 HttpOnly+SameSite=Strict+prod Secure、登录限流），**但 `/auth/login|/auth/me|/auth/csrf|/auth/logout` 的 HTTP 路由尚未挂载**（全 backend grep 无 /auth 路由）。
- 含义（对 T40-C01/C05 关键）：登录/会话恢复的前端测试**只能在客户端边界 stub fetch（显式 fixture 标记）**，真实联调属 live=blocked（等 T35 API 挂载）；不得把 stub 通过当 live 证据。会话 token 由 HttpOnly Cookie 承载，前端代码永不见 session token；CSRF 值从登录响应或 GET /auth/csrf 取得、**仅内存使用**（05 §1），退出/登出时清除——这是 T40-C05「清除私有前端缓存」的合同依据。

---

## 4. T40 六案例落点建议（按现有布局）

### 4.1 测试文件与实际布局的对应关系

- 任务卡指定 **`frontend/tests/t40_frontend_shell.test.tsx`**，这是**待创建**位置，与现状唯一测试 `frontend/src/App.test.tsx`（src 内）**不同目录**。vitest 会自动收集 tests/ 下的文件（无需改 vite.config），但 `npm run typecheck`/`build` 不覆盖 tests/（§3.1）。
- 建议六个案例全部落在该单一文件（任务卡允许参数化但要求保留 case ID）：以 `describe("T40-C0x …")` 逐案例分组，断言可观察行为；负例不得只断「没有报错」；期望值来自 05 合同与 enums 词汇，不从被测组件实现反抄。
- 每个案例的 fetch 桩必须**显式标记 fixture 模式**（AGENTS.md §6：fixture 模式必须显式、隔离、有标记），并在断言中验证界面呈现 data_mode 标识（fixture/live 徽标）。

### 4.2 建议新增面（与任务卡目标产物一致，均在允许修改范围内）

```
frontend/src/
├── app/                    # 目标产物：工作台布局、路由视图切换（login/workbench）、
│   │                       # CurrentUserContext（用户/角色/权限/permission_version）、
│   │                       # 会话恢复（GET /auth/me）、ProtectedRoute、data_mode 横幅
│   └── …（App.tsx 可迁入或保持薄入口）
├── components/             # 目标产物：EvidenceLink、FreshnessBadge、TaskStatus、EmptyState、ErrorPanel
├── features/
│   └── auth/               # 登录表单、logout 动作、CSRF 内存持有、私有缓存清理
├── api/                    # 最小 fetch 客户端：错误体解码、CSRF 头、超时/断线分类
└── types/                  # 手写类型（严格匹配 05 合同 + schema_bundle 可导出记录）
frontend/tests/
└── t40_frontend_shell.test.tsx   # 六案例
```

### 4.3 案例 → 落点映射

| 案例 | 场景（任务卡 §5） | 建议测试落点（frontend/tests/t40_frontend_shell.test.tsx） | 依赖的实现落点 | 断言要点（期望值来源） |
|---|---|---|---|---|
| T40-C01 | 登录后加载工作台 | stub `/auth/login`→`/auth/me` 成功桩（fixture 标记），渲染 App | app/CurrentUserContext + features/auth + 工作台布局 | 显示真实 username/user_id/tenant/role 与权限集（Role 词汇取 access.py）；显示 data_mode 标识（fixture/live）。不得显示桩数据之外的统计 |
| T40-C02 | 未认证访问私有路由 | stub `/auth/me` → 401（统一错误体），从私有路由渲染 | app/ProtectedRoute + 会话恢复 | 转登录视图；DOM 中不残留任何私有对象标题/数量（05 §10「无权限不显示对象标题、数量」）；断言显式选择器为空而非仅「无报错」 |
| T40-C03 | API 断线 | stub fetch reject（TypeError: network） | api/ 客户端 + ErrorPanel + EmptyState 边界 | 明确错误文案 + 可聚焦的重试按钮；页面无假成功统计、无「暂无风险」类误导空态（05 §10） |
| T40-C04 | stale/partial/unknown | 直接渲染组件 props 组合（FreshnessStatus/JobStatus/DimensionStatus 全部取 enums 值） | components/FreshnessBadge + TaskStatus | 三态与 current/succeeded 的**文案+视觉**均不同；unknown ≠ false（ConditionValue 语义）；每态有文字标签 |
| T40-C05 | 刷新/退出 | ①重新挂载 App + `/auth/me` 成功桩模拟刷新恢复；②点退出后断言 | features/auth + api/（CSRF 内存）+ 缓存清理 | 刷新后会话恢复、用户上下文一致；退出后 `/auth/logout` 被调用、内存 CSRF 清除、DOM 无私有缓存内容、再访问私有路由回登录 |
| T40-C06 | 键盘访问按钮与表格 | fireEvent 键盘/焦点断言（无 user-event，见 §5-G4） | components/* + 工作台表格 | 操作元素为原生 `<button>`（或显式 role+tabIndex+onKeyDown）、有可访问名；表格 `<th scope>`；状态标签非仅靠颜色（文字/图标冗余编码，与 C04 同源组件） |

**与实际布局的对应关系总结**：任务卡的 `frontend/src/app/`、`frontend/src/components/` 在现状中是**空缺目录**（§1.1），六案例的实现载体全部是新建文件；唯一可复用的现状资产是 `App.tsx` 的「未连接」防假数据断言风格、`vite.config.ts` 的 jsdom 测试环境、以及 §3 的严格 tsconfig 与合同词汇（enums.py / 05 合同 / schema_bundle.json）。

---

## 5. 缺口与最小新增面

### 5.1 缺口清单（如实登记，不含未验证推断）

| # | 缺口 | 证据 | 影响 |
|---|---|---|---|
| G1 | `frontend/tests/` 不在 tsconfig `include` 内 | tsconfig.json include=["src","vite.config.ts"] | `npm run typecheck`/`build` 不检查测试文件类型；任务卡测试位置与 typecheck 覆盖错位。最小修法：include 增加 `"tests"`（属「相关最小迁移」，但 tsconfig.json 不在任务卡列明的修改清单内，实施时应在报告登记该边界事实） |
| G2 | 后端 `/auth/*` HTTP 路由未挂载 | app.py 仅 health 路由；backend grep 无 /auth 路由 | T40-C01/C05 只能 fixture stub + live=blocked；真实联调等 T35。**不得以 stub 通过冒充 live** |
| G3 | 无 API 客户端、无类型文件、无 codegen 工具链 | §3.2/§3.3 | 客户端与类型全为新增；手写类型需逐一对照 05 合同字段，禁止 Any/cast（tsconfig 已 strict，会被强制） |
| G4 | 无 @testing-library/jest-dom、user-event、MSW | package.json devDependencies | 用现有 `@testing-library/react` + vitest 内建 `vi.stubGlobal("fetch", …)` 即可覆盖 C01—C06 的 DOM/请求桩断言；键盘 Tab 真实焦点遍历 jsdom 不模拟，C06 用 fireEvent.keyDown + 语义结构断言（原生 button/th scope/可访问名/非颜色标签）并在报告如实说明该限制。**不建议为凑断言引入新测试依赖**；若确需 user-event，属新增依赖应登记 |
| G5 | 无路由库（react-router 等） | package.json dependencies 仅 react/react-dom | T40 只需 login/workbench 两视图：优先用 app/ 内最小受控视图状态，避免新增运行时依赖；若实施时决定引入 react-router-dom，属新增运行时依赖，按 AGENTS.md §2.5 应登记变更记录 |
| G6 | `scripts/dev.py` frontend/e2e scope 为 not_implemented（exit=3） | dev.py IMPLEMENTED_SCOPES | T40 检查走 npm 原生命令；dev.py 不在 T40 允许修改清单，接线留待后续任务并登记 |
| G7 | npm audit 未处置（T02 遗留） | T02 报告 §6.3 | T40 报告继续如实登记「未审计/有提示」，不得写「无漏洞」 |
| G8 | `tsconfig.tsbuildinfo` 被 git 跟踪（构建产物） | git ls-files frontend | 与前端功能无关的小瑕疵；建议归入 .gitignore 清理批，不属 T40 最小面 |
| G9 | e2e（frontend/e2e/）无 Playwright/任何 e2e 工具 | package.json 无 e2e 依赖 | 任务卡主检查是 vitest 单文件；e2e 目录空缺**不建空壳**，T40 验收不依赖 e2e |

### 5.2 最小新增面（建议，未实施）

1. **测试**：`frontend/tests/t40_frontend_shell.test.tsx`（六案例，case ID 保留，fixture 桩显式标记）。
2. **实现**：`src/app/`（布局+路由视图+CurrentUserContext+ProtectedRoute+会话恢复+data_mode 横幅）、`src/components/`（EvidenceLink、FreshnessBadge、TaskStatus、EmptyState、ErrorPanel 五件）、`src/features/auth/`（登录/登出/CSRF 内存/缓存清理）、`src/api/`（fetch 客户端+错误体解码）、`src/types/`（手写严格类型）。
3. **最小迁移**：tsconfig include 增加 `"tests"`（G1，需在任务报告登记为边界内最小迁移）；其余配置不动。
4. **不新增**：依赖（G4/G5 保持零新增为默认）、空目录、e2e 壳、mock 服务端实现。
5. **文档面**（实施时）：`reports/tasks/T40.md`（实测命令、退出码、测试数、日志路径、live=blocked 登记）；`progress/task_state.json` 与交接由主控更新。

### 5.3 验证状态预期口径

- unit（Vitest）：实施后可实测；fixture 桩测试通过 = 单元/合同级证据。
- live：**blocked**（G2，/auth 路由未挂载 + 无真实会话），不得标 passed。
- 命令口径：`cd frontend && npm run lint && npm run typecheck && npm run test && npm run build` 全绿 + 任务卡主检查单文件通过；日志落 `reports/runs/`，引用具体退出码与测试数。

---

## 附：本轮盘点动作记录（只读）

- 读取：frontend 全部非 node_modules 文件（14 个）、docs/tasks/T40_frontend_shell.md、docs/plan/05、docs/plan/06、docs/decisions/cr002、cr004、reports/tasks/T02.md、backend/src/ai_intel/api/{app,authentication}.py、domain/{enums,access,schema_export}.py、contracts/schemas/schema_bundle.json（头 40 行）、.github/workflows/ci.yml、scripts/dev.py、.gitignore、git 状态。
- grep：T40 全仓引用、五组件名全仓、/auth 路由全 backend。
- 未写入/未修改任何代码文件；仅写本报告 `reports/reviews/T40_frontend_prep.md`。未触碰 backend/、frontend/、contracts/、progress/。
