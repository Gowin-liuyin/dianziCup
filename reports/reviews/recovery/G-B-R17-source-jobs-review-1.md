# G-B · R04/R06/R17 来源单页任务工作区独立初审

审查状态：**Ship，限冻结前端切片**。未发现有具体复现支持的 Must fix 或 Should fix。实现仍为 `awaiting_review`；本报告不写 `accepted`，不验收整 R04/R06/R17、T40/T41 或 G-B。真实管理员 API/PG/worker/来源链仍 `not_run`。

本改动把来源页接成两固定来源的有界调度与单页任务查询界面。系统管理员提交带时区观察窗口、流和页数上限；网络结果未知时保留相同 body/window/key 重试，PG 九状态明确区分，不把本页成功解释为整源完成。

## 1. 独立性、输入版本与修改范围

- Reviewer：`source_workspace_review`，未参与本切片实现；未 spawn、未修改业务源码、认证、合同、锁、进度或状态，未提交/push。
- 独立 Codex worktree：`C:/Users/yinha/.codex/worktrees/source-jobs-review/dianzi`，由固定 ref 创建。起止 `git status --short` 均空；build 改写的自有 `frontend/tsconfig.tsbuildinfo` 已恢复冻结字节。
- 候选 SHA：`fccc0b918c58b18e66e8eb67cbfc8aadd4c1fb62`；tree：`8c317abf493261ce57233c09836ee39b60a868cf`；基线：`31c2866ff19227e5f6ee24f1f966660c0d4ba383`。
- 冻结 diff：11 文件，666 insertions / 2 deletions。范围为 App/App.test、新 source-client/contracts 及测试、sources 组件/测试/局部 CSS、新 4 用例 fixture e2e，以及旧 `r17_hacker_workspace.spec.ts` 的 sources 导航分支。没有共享 auth/client、全局 CSS、后端、依赖或锁修改。
- 读取 AGENTS、00 执行索引、R04/R06/R17 卡、T40/T41 验收、`progress/task_state.json` 的 `recovery_tasks`、交接、CR-R04-R04_source_jobs；实际 API/worker/来源实现来自本独立固定 worktree。作者目录只读取任务报告与 evidence manifest/原始日志，不用其正改源码证明通过。
- 使用 Ponytail 5.2 `ponytail-review` 与 `ponytail` full 的真实调用链、具体触发和最小必要复杂度标准；中文交付遵循本任务要求。外部 UI 参考不作为权限或实现指令。

原始证据目录：`reports/runs/recovery_r17_source_jobs_review_1_20261015/`。秒级 +08:00 起止、cwd、完整命令与退出码在 `commands.jsonl`；本报告中的测试数来自实际输出，不与作者测试叠加。

## 2. 已证实的合同与安全边界

`backend/src/ai_intel/api/source_routes.py` 的两管理路由为 POST `/v1/sources/{source_kind}/collect` 和 GET `/v1/jobs/{uuid}`，公开投影恰好七字段，未含 `data_mode`。前端字段与之匹配：固定来源枚举、带时区且非未来的窗口、`live/backfill`、整数 1–20 页；请求体没有 URL、租户或凭据。UI 默认 live/5 页是明确输入，不改变服务端 backfill/20 的默认合同。窗口文案准确说明不保证上游快照或时间过滤覆盖。

API 实际由 cookie/session 提取角色和租户，写操作校验 Origin/CSRF；前端复用同源 `fetchJson` 的 `credentials: include`、`no-store`、超时和公开错误。Origin 由浏览器产生，没有伪造或手动写入。异步读取 CSRF 之后会再次核对 signal/current generation，提交 body 与 key 在 await 前捕获。组件同步 inFlight 阻止双击；输入在提交/查询期间锁定，离页/会话改变会 unmount/abort，新实例隔离旧响应。请求未知允许原样重试，显式新轮次才产生新 key。

匿名、普通角色和带 tenant 的 `system_admin` 不发来源、job 或 CSRF 管理请求。401 清客户端身份；没有自动恢复旧身份的 auth/me 循环。GET 仅手动调用，UUID 和响应 job_id 一致性校验，未提供任意 URL 读取。UI 不构造来源总量、online 状态或历史数量。没有 source-list/history 接口的缺口保持可见。

SQL/worker 九状态与前端一一匹配：queued、running、retry_wait、waiting_approval、succeeded、partial、failed、blocked、cancelled。错误码/PG 引用的安全正则与 worker 实际验证相同；额外字段、非法状态/日期和原始错误文本被拒绝，React 文本渲染不执行注入。HTTP 403/404/503 与空任务、完成分开显示。`succeeded` 只写“本页处理完成”，partial/blocked 不假称完成。模式来自会话 Fixture/Live；人类时间为 +08:00 秒级，`time.datetime` 保存原始值，null 保持未知。

## 3. 独立执行结果

除特别注明外，npm/Playwright cwd 是独立 WT 的 `frontend`；CBM cwd `D:/dianzi`，实际 repo-path 是独立 WT 的 `frontend/src`。统一 `NODE_OPTIONS=--max-old-space-size=384`，Vitest/Playwright worker 1。

| 命令/证据 label | +08:00 实际起止 | 退出/结果 |
|---|---|---|
| `npm run test -- --run` / final-full-unit-contract | 15:26:14–15:26:32 | exit 0；14 files，178 passed，0 failed/skip |
| `npm run lint`、`npm run typecheck`、`npm run build` / final-quality | 15:26:14–15:26:29 | 三项 exit 0；41 modules；JS 211.24 kB/gzip 66.96 kB，CSS 21.86 kB/gzip 5.32 kB；非性能指标验收 |
| `npm run test -- --run src/api/source-contracts.test.ts src/api/source-client.test.ts src/features/sources/source-workspace.test.tsx` / targeted-source-contract-client-component | 15:31:48–15:31:52 | exit 0；3 files，57 passed；属于上述 178 的子集，不另加 |
| Playwright 固定 4 fixture cases / independent-final-fixture-browser | 15:26:54–15:26:58 | exit 1；4 个启动失败，默认缓存缺 revision 1248；未进入产品动作，环境失败保留 |
| 同 4 cases，使用实际已有 1248 cache / independent-final-fixture-browser-cache-fix | 15:28:53–15:29:00 | exit 0；4 passed，0 failed/skip/flaky |
| 独立编写的 3 browser 负例 / independent-targeted-negative-browser | 15:30:31–15:30:38 | exit 0；3 passed，0 failed/skip/flaky |
| 固定源码 `git diff --check` 与起止 status / candidate-identity、final-scope-resources | 15:25:02–15:25:03；15:31:54–15:31:57 | exit 0；候选固定，结束源码干净、25304/25306 监听 0 |

独立负例源保存在证据目录 `independent-negative.spec.ts`，没有进入业务测试目录或修改作者测试：

1. 挂起 CSRF；浏览器切到会话并实际点击退出，迟到 CSRF 释放后返回来源页。管理 POST 为 0，来源权限拒绝，logout 请求确实 1 次。离页先取消来源组件，logout 清除会话；客户端单元另验证 await CSRF 期间 generation/abort 改变不得 POST。
2. 挂起旧 job GET；离页后返回 sources、选 vLLM、查询第二个 UUID 的 blocked 状态，再释放旧 succeeded 响应。旧成功不显示，输入仍是第二 UUID。点击普通“刷新状态”新增请求全部是 health，无 job/source/CSRF 请求。
3. 未来窗口在浏览器输入后提交，CSRF/source 请求为 0。有效提交返回非法 202 状态时提示结果未知且冻结；下一次 403 的 code/message 放入 `fixture_secret` 与 `<img ...>`，界面无原文和 img；第三次成功，三个 POST body/key 完全相同。背景普通媒体动画存在，减少动画后 animationName 为 none。

4 个冻结 fixture 用例另外实际覆盖 1366/390px、键盘 Enter 提交、未知网络结果同键重试、新轮新 key、partial/blocked/succeeded、权限门禁、离页迟到 CSRF、job 401 清身份。独立生成并查看两张截图；两栏/窄屏单列可读、关键说明和长 UUID/key 换行、没有全局横向溢出，Fixture 标识明确。截图仅含随机隔离 fixture 身份和数据，没有真实登录或秘密。

## 4. CBM 与证据真实性交叉核查

真实 WSL portable 为 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，0.11.0。实际执行 `--help`、`cli index_repository --help`、`get_architecture --help`、`trace_path --help` 后使用真实 CLI；独立 `XDG_CACHE_HOME=/tmp/dianzi-cbm-source-job-review-20261015`，仓外缓存，`persistence=false`，只索引 frontend/src。日志含 `cbm-fixed-index`、`cbm-architecture`、`cbm-submit-trace`、`cbm-lookup-trace`，均 exit 0。

固定图 188 nodes / 645 edges，parse partial/unusable 都 0；fast 模式按设计排除 13 测试文件，不能宣称全仓/测试覆盖。提交 trace：runRequest → collectSourcePage → validateSourceSubmission/getCsrfToken/fetchJson/parseSourceJob；查询 trace：runRequest → getSourceJob → validateJobId/fetchJson/parseSourceJob。用 rg 和实际源码/测试回查调用方、auth generation、App 的 sessionScopeKey、SQL 状态及 worker 结果字段，不只凭图断言。

作者 delivery-manifest 对候选 fccc 的 39 个前置 evidence 文件 SHA256 全部一致（加 manifest 本身是 40-file 包）。原始 component-first 确为 26 passed / 1 failed，失败断言是非法响应被泛化提示；原始 browser-first 确为 expected 2 / unexpected 2 / skip 0，原因是 exact getByLabel 未匹配嵌套 select，后改同名 getByRole。作者 177 全套属于较早 c933，最终只追加 22 相关与 4 browser；本次 reviewer 的最终 fccc 全套才实际取得 178，未改写作者历史失败或夸大其通过。

## 5. 资源、负载、未检查与评分限定

同 SHA256 `79e4df46c6646ab2d878b8baeaa9985ab44a1c802a0f47c950ee1869a4cb8c61` 的锁核对后，robocopy 本机已安装依赖到自有 WT，排除 `.vite`；没有 junction/共享运行缓存、依赖下载或锁修改。已有 Chromium 缓存 `C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248` 的 executable 在使用前实际确认；默认缓存首失败没有被删改。

fixture Vite 仅独占 25304，API proxy 指向未启动的 25306；/v1 全部是显式隔离白名单 browser fixture，独立负例额外拒绝非审查 origin。无真实产品/测绘 key、真实 login、公网 source GET、付费调用、DB/Redis/MinIO 访问；未动 root 25300/28000。每轮服务生命周期少于 10 秒，测试服务/context 已结束；15:31:57 监听 0。本包当时 404337 bytes，低于 4 MiB；最终封存另有 manifest。heap 是限制设置，不冒充 RSS 实测。

按本切片一人每次显式操作、每挂载工作区最多一个管理请求评估：状态内存有界，不随任务数累积、没有轮询负载或新依赖/框架。没有测吞吐、并发用户或持续采集时效，不将 build 大小当性能通过。

| 层/评分 | 限定结论 |
|---|---|
| unit / contract | passed：最终 178 与来源子集 57，均隔离 fixture |
| integration / security | passed 仅浏览器—客户端—组件隔离链和上述安全负例；真实 cookie/Origin/CSRF—API—PG 链 not_run |
| frontend / e2e | passed：最终类型/lint/build、4 冻结 fixture + 3 独立负例，截图实际查看 |
| live / manual | live not_run；隔离截图/浏览器动作已做，原生隐藏页暂停、真实管理员与来源数据操作、连续监测 not_run |
| D2/F1/P1 | 仅有界来源调度、可见状态/边界、手动查询和窄屏/键盘交互的实现证据；不登记八类来源/九通道、完整增量、时效指标、整工作台或全阶段通过 |

未运行旧 `r17_hacker_workspace.spec.ts` 的真实账号导航，已有 e2e 分支改动仅静态/类型核对；未执行真实管理员调度、worker/PG 分页队列、live 两源、租户服务端拒绝的复跑。本包没有后端修改，backend 合同来自固定源码阅读；这些事实不能由前端 fixture 成功替代。

**Verdict: Ship（限 fccc 前端切片）。** 无需为了审查新增抽象或风格循环。下一步由主控集成冻结切片并受控验证真实管理员 POST→PG→worker→公开来源→GET→浏览器链；整 R04/R06/R17 与 G-B 保持原未验收条件。
