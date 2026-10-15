What this change does: 固定候选为事件列表、九维富化、断言历史与证据检视增加严格的 schema 2 客户端和可操作页面。会话代次隔离旧身份响应，同时集成 Vitest 4.1.11 的兼容安全修复；真实情报业务入口仍待接通。

本轮结论：**R04/R17 前端准备切片 needs_changes，implementation=partial**，须先修复下列 1、2。**CR-R10 的当前依赖组合技术核对 passed**：两份依赖文件与 497740a 必要候选逐字节相同，干净安装、完整 108 测试、隔离配置和本次 audit=0 有新的独立证据。此结论不签整 R04、R17、T40、T41、G-A、G-B 或阶段 push。

审查者 `/root/r04_frontend_independent_review` 未参与本批实现。开始 2026-10-15T12:03:05+08:00，固定树检查结束 12:12:52+08:00；报告随后落盘。固定候选 `0b983349e0468a4c75a1adf9f050ac3e7dd00686`，tree `9d9672945b5d4eb01661f315914c1e5b48113617`，差异基线 `3465b47ce618bed6fa45cfecccd88b2b595e04b9`，18 文件、1110 加行/330 删行。独立 WT `C:/Users/yinha/.codex/worktrees/recovery-r04-frontend-review/dianzi`，分支 `codex/recovery-r04-frontend-review`；初末 `git status --porcelain` 均为空。不追随 main 后续网络、PDF、任务执行改动。

已读 AGENTS、执行索引、恢复 R04/R17 卡、原 T40/T41、冻结 03/05/06、CR-R04 只读投影补充、CR-R10、root 当前 R17 准备报告、设计记录和 CR-R10 独立授权核对。采用指定新版 Ponytail Review 5.2，额外只读子审查由本审查者再次核实；最终问题以本轮浏览器证据为准。root 唯一负责全局状态和 Git 集成，本轮只写本报告及同名 run 目录，未改业务、原测试、金标、阈值、分母或 skip。

**Must fix**

1. **[P2] 事实引用没有携带已知历史版本**（`frontend/src/features/events/event-workspace.tsx:84`；相连校验 `frontend/src/api/knowledge-client.ts:35`）。
   - 职责：来源断言带 `source_revision_id`，引用应打开保存的原文版本；客户端已有 expectedRevision 校验。
   - 问题：claim 的链接仅为 `#events/{event}/evidence/{span}`，没有 `/revision/{source_revision_id}`。独立浏览器实际点击 claim A（`...0002`）的“原文片段 [1]”，同 span 响应返回 B（`...0004`），页面实际展示“错误版本B原文”；作为对照，维度 A 链接正常拒绝 B。不是只观察函数调用参数。
   - 最小修复：claim 的非 null `source_revision_id` 追加到 hash，复用现有校验；加入实际点击 claim 后错 revision 的回归。null 保持明确未知，不猜版本。
   - 不修影响：历史断言可能与另一修订的片段配对，失去冻结合同要求的版本一致性，现有维度测试无法覆盖这个入口。

2. **[P2] 新筛选失败后仍展示旧详情与证据**（`frontend/src/features/events/event-workspace.tsx:160`、`:175`）。
   - 职责：新的查询开始应清当前结果；权限或失败状态不得把旧结果继续当作本次取得。
   - 问题：提交仅替换 `filters`，selection 与两份详情资源保留。独立浏览器先打开旧事件和证据，再提交 `q=new-filter`，分别返回 403 和 503；列表变成“没有查看权限”/“依赖暂不可用”，但旧标题、旧 claim、blockquote 各仍为 1，且详情与证据没有重读。403 页面一面写“没有返回记录标题或数量”，下方仍出现旧对象标题。
   - 最小修复：提交筛选时清 selection 与对应 hash/证据，或以等价方式清整个当前选择；补 403/503 与 loading 期间旧详情不可见回归。不要改变业务过滤或把失败改成空列表。
   - 不修影响：用户在新查询失败/权限拒绝后继续看到旧上下文，既与文案矛盾，也无法确认这些内容当前仍获授权。隔离复现没有证明真实跨租户泄漏，不夸大为已发生泄密。

两项归因共用 `negative-browser.json` 的 5 个独立案例：2 passed、3 failed、0 skipped（错版本 1 例，筛选 403/503 2 例）；正常维度版本拒绝和证据 loading/503 不抢焦点均通过。浏览器负例退出 1 是真实业务断言失败，不是环境缺失。

已发现但不列本批新增阻断：旧 `fetchJson` 的非 JSON/空 body 401 会被包成 502 `invalid_response`，新工作区因此不会清身份；此行本批仅导出，且该响应不符 RFC9457。建议后续保留真实 HTTP 错误状态、固定公共错误文案，并补空 401/403/503 回归。request 参数 `cursor=""` 被省略不列明确缺陷：11:35 补充明确约束返回 `next_cursor`，当前 parser 已拒绝返回空 cursor，不能混同两者。

实际命令与结果如下；cwd 默认为独立 WT/frontend，命令由 main/run 中 `run_review.py` 用固定 SHA fence 执行，stdout/stderr 与秒级 command JSON 保留。

| 检查 | +08:00 起止 | 实际结果 | 证据 |
|---|---|---|---|
| `npm.cmd ci` | 12:03:56–12:04:01 | 子进程 exit0；299 包，审计 300 包 | `ci.command.json`、stdout/stderr |
| `node node_modules/vitest/vitest.mjs run --reporter=default --reporter=junit --outputFile.junit=.../test.xml` | 12:04:10–12:04:19 | 子进程 exit0；10 文件、108 passed、0 failure/error/skip | `test.command.json`、`test.xml`、stdout/stderr |
| `npm.cmd run lint` | 12:04:10–12:04:16 | exit0 | `lint.*` |
| `npm.cmd run typecheck` | 12:04:10–12:04:13 | exit0 | `typecheck.*` |
| `npm.cmd run build` | 12:04:32–12:04:36 | 子进程 exit0；36 模块构建成功 | `build.*` |
| `npm.cmd audit --json` | 12:04:10–12:04:12 | exit0；本锁文件时点漏洞记录 0 | `audit.*` |
| Playwright `r04_fixture_contract.spec.ts r17_skip_link.spec.ts --reporter=json --output=.../e2e-artifacts` | 12:04:52–12:04:59 | exit0；4 fixture + 2 匿名键盘，6 expected、0 skip/unexpected/flaky | `browser.*`、3 PNG |
| root 安全 runner，固定前/后端 0b983，`r01_auth.spec.ts`，端口 25305 | 12:06:50–12:06:57 | exit0；3 expected、0 skip/unexpected/flaky；独立核对 JSON、测试语义及 2 PNG | `real-api-auth.*`、`real-api-auth-artifacts/` |
| `node negative_browser.mjs`，端口 25304 | 12:09:03–12:09:08 | exit1；2 passed/3 failed、0 skip；全 `/v1` 隔离拦截 | `negative-browser.json`、3 PNG |
| Playwright `r17_hacker_workspace.spec.ts --grep "R17 dynamic background"` | 12:10:39–12:10:45 | exit0；1 expected、0 skip/unexpected/flaky | `background.*`、2 PNG、`background-observation.json` |
| CBM 官方 portable index/schema/trace | 12:06:22–26、12:09:02–09 | 各 exit0；独立 cache/index，只 frontend/src | `cbm_index.*`、`cbm_schema.*`、`cbm_trace.*` |
| `node runner_config.mjs` | 实际 `checked_at` 12:10:15 | exit0；forks、isolate=true、maxWorkers=1、fileParallelism=false、jsdom，e2e 排除 | `runner-config.json` |
| `python -X utf8 source_audit.py` | 实际收据时间见 JSON | exit0；13 原测试文件只有 App.test 新增两例，原内容保留；依赖对逐字节相同 | `source-audit.json`、`original-test-identity.diff` |

test/build 的审查包装器首次打印 Unicode 勾号时触发本机 GBK `UnicodeEncodeError`，包装器 exit1；实际 npm/Vitest 子进程早已 exit0，原 stdout、JUnit 和 child receipt 仍保留。修复仅是本 run 包装器 `sys.stdout.reconfigure(encoding="utf-8")`，没有重写产品输出或把失败检查改成通过。首负例启动手写了不存在的浏览器 exe 路径，12:08:40 exit1、0业务案例；改用已缓存 Playwright 默认解析后才取得上表 5 例。首 source audit 假定设计文档在候选 Git 树，实际仅 root 参考文件，exit128；去掉这项冻结树假定后完成，不将它算业务测试失败。辅助错误和检查边界见 `harness-notes.json`。

CR-R10 技术核对：原 471c547 的 13 测试源码文件中，12 个逐字节相同；App.test 仅增加两项 skip-link 用例，未删除原断言。当前完整 JUnit 列出 108 个具体身份，不用旧报告 30/64/106 数量代替。Vite/Playwright 配置相对差异基线未改，实际解析确认 runner 隔离与单 worker；React18/Vite6/TS5.7/Node24 要求保留。没有为通过审计执行 force audit、删除锁文件或升级产品栈。新的依赖安装/audit/log 只说明这个固定组合当前技术生效；不声称未来无漏洞或其他平台/coverage provider 通过。root 可据 CR-R10 独立授权核对登记该依赖技术结论，UI 两个缺陷独立待修。

本轮 CBM 先读取官方 portable `--help`，再使用 `CBM_CACHE_DIR=/tmp/dianzi-cbm-r04-frontend-review-1-20261015`、项目 `dianzi-r04-frontend-review-1`。fast index 得 151 nodes/505 edges，9 个测试文件按 fast-pattern 未入图；不是 0 测试/测试缺失，实际 Vitest 与 rg 补核。trace 为 Workbench→EventWorkspace→EvidenceInspector→getEvidence→fetchJson/parseEvidenceResponse；再以 rg、逐行源码及真实点击交叉检查，不能因图中无测试边就认定未覆盖。未索引秘密、附件、holdout 或运行证据。

视觉检查已实际通过 view_image 查看本轮 1366×900（full-page 1366×2206）与 390×844（full-page 390×3138）Fixture 截图、390×1406 的 503 截图、真实 auth 的 1280 与 390 截图，并以 original 详细查看手机和负例 PNG。桌面主表/证据侧栏有明确层次；手机长 UUID 换行，九维/失败 PoC/模型假设/未知历史时点可读，表格只在自身横滚，页面无整体宽度溢出。Fixture 在头部、列表、详情和证据中显著可见；产品源码没有 fixture fallback、伪造 CVE、外部统计或 Agent 进度。两处负例截图保留具体错版本和旧内容，不以正常截图掩盖。

本轮动态背景既有测试实际观察 transform 改变、布局 bounds 不变、pointer-events none、15 个背景元素及 reduced-motion 的 animationName=none。60 帧窗口约 1000ms，p95 16.70ms/max 16.80ms、0 observed long tasks，仅为本机短窗口粗观测，不是正式 P50/P95 产品性能或连续稳定保证。原生 hidden 暂停仍 manual 未证实，本轮没有重复无进展的 headless/最小化探针。

真实 auth 3 例由 root 的 DPAPI 安全 runner 调度，本审查者没有读取 DPAPI/.env/KEYS 或接收凭据；runner 元数据固定前/后 SHA 并检查 `artifact_secret_matches=[]`，trace/video/失败自动截图关闭。独立核对的真实语义包括 HttpOnly + SameSite Strict Cookie、无 local/sessionStorage token、重载恢复、POST logout 200 后重载匿名、键盘/390px、offline 健康失败及恢复；截图中的 worker/scheduler 显示待观测/过期，API-only 的缺口没有涂绿。本证据只覆盖真实认证与健康路径，不能证明事件 PG 投影、真实 NVD/厂商来源→页面或业务证据链。

`r17_hacker_workspace.spec.ts` 的另外两例未运行：认证后旧 Prepared 页描述已被新的 EventWorkspace 替换，其中“尚未取得事件查询结果……”仍是旧页面预期；静态确认应随真实业务接通更新其契约，而不是把未跑或过期预期写通过。本轮只真实运行并记录了该文件的动态背景 1 例。T41 指定最终来源页/六例、整 R04 两源/PG/业务浏览器与 R17 其余页面仍 not_run/blocked_live，不因为此准备切片或 Fixture 通过而豁免。官方 13 要求、U01–U14、原 60 T 卡与阶段检查点均未改变。

评分证据只登记 D2 的界面可操作性准备、E1 的当前前端安装/测试/构建与认证边界，以及 F1/F2/R1 的冻结投影显示/引用保护准备；不登记富化准确率、真实来源数、正式时效、问答/Agent/资产结果。本轮最终固定 WT clean，25304 无监听；只恢复自己 build 生成的 tracked `frontend/tsconfig.tsbuildinfo` 到固定 HEAD，未清用户文件、未提交、未 push。28000 的 root 受控 API 段由 root 所有，不由本审查者停止。

精确产物目录为 `reports/runs/recovery_r04_frontend_review_1_20261015/`。其中 `artifact-manifest.json` 列每个实际文件的相对路径、字节数和 SHA256；主要可复跑脚本为 `run_review.py`、`negative_browser.mjs`、`runner_config.mjs`、`source_audit.py`，固定初末收据 `review_start.json`/`review_end.json`；root 安全运行证据为 `real-api-auth.json`/`.command.json`/`.stderr.log`及 `real-api-auth-artifacts/`。正常截图在 `e2e-artifacts/`，负例在 `negative-artifacts/`，背景两帧在 `background-artifacts/`，逐个文件以 manifest 为准。

Verdict: fix 1 and 2 first. 下一步由实现者最小修复并冻结新的 SHA，保留本轮失败证据，交同一非作者定向复核；完整测试与空 HTTP 错误共享路径也应回归。Not checked: 真实情报端点/来源链、原生 hidden 暂停、正式性能和完整 R04/R17/G-A/G-B 验收。
