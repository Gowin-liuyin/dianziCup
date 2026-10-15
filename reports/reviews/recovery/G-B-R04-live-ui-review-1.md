# G-B · R04真实采集工作台独立浏览器审查 1

审查任务：R04:T40/T41 与 R17 已接线事件界面的有限切片。状态：**定向复核完成，Must 1 已在前端 d391f89 + 后端 7184 的实际组合中关闭**；本报告不登记任何整 R04、R17、T40、T41 或阶段 accepted。实现状态仍按原能力范围分别保留 partial。原 7184 结论 needs_changes 与失败证据保持可追溯。

本变更做什么：固定前端从真实认证会话读取持久化事件列表、九维状态、来源断言及历史证据，在黑底青绿工作台中支持检索、深链、刷新、窄屏和键盘操作。本次独立观察确认 vLLM 厂商公告与 NVD 记录实际进入浏览器；来源监测等其他工作区仍明确待接通。

**当前结论：真实列表→详情→证据→刷新路径已跑通；原 Must 1 已经新前端 d391f89 的 10 项真实定向检查关闭，没有新的 Must。先前 7184 上的 29 项主路径、10 项补测和 2 项历史未知日期检查保持原版本归属，不宣称在 d391 上重新全套执行。来源页、真实失败/过期维度、原生隐藏页暂停及完整业务体验仍不具备本轮验收证据。**

## 历史 Must fix（已定向关闭）

1. **面向人的时间直接显示 UTC 和微秒，未满足北京时间秒级合同**（`frontend/src/features/events/event-workspace.tsx:17–18`，调用见 `:87,119,170`）。
   - **职责：**SavedTime 将事件首次发现、原文源发布/源修订/首次观察/入库及定位核验时间显示给用户。主控于本审查后段补传此前分派漏写的用户当前明确要求：所有面向人的日期时间必须 Asia/Shanghai、精确到秒、ISO8601 带 `+08:00`；raw 工具日志可 UTC，但须标注。
   - **触发与实际：**固定 7184 API 返回 `2026-10-15T06:19:29.380687Z`，实际列表/metadata 显示原字符串，列表还在 `2026-10-` 后换行；vLLM 源发布时间直接显示 `2026-10-06T06:59:51Z`。证据见 `complement/list-viewport-1366.png`、`complement/evidence-viewport-1366.png` 及原 JSON，SavedTime 的 `<time>{value}</time>` 与实际 DOM 一致。
   - **预期：**上述首次观察应显示 `2026-10-15T14:19:29+08:00`，源发布显示 `2026-10-06T14:59:51+08:00`。按各字段自己的语义分别格式化，null 仍“未知 / 未留存”；`dateTime` 属性可保留原 API 值，不修改原文历史或 HTTP DTO。
   - **最小修复和复验：**主控 d391f89 加入共享显示格式化函数，由 SavedTime 与健康检查使用；显示秒级且固定上海偏移。两屏实际列表、vLLM metadata、NVD null 时间/刷新与布局的 10 项定向检查均通过，见文末追加记录。本 reviewer 未改业务。若未修复，用户会继续读到与合同不同的时区/精度，因此原 7184 仍保留 needs_changes 历史结论。

## 输入、范围与版本

- 审查者为新非作者 reviewer `/root/r04_live_ui_review`，未参与实现；未 spawn、未改产品业务、合同、进度、锁文件或服务。
- 实际产品源码固定 `7184dc63525ae3e8ea439ec64fc03dfaa629f7a8`，tree `ac9208e31abfb91deefe7959bcaecb3be3f3f2b7`；工作树 `C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi`，前后 `git status --porcelain` 均为空。没有 checkout、提交或 push。
- 实际 UI `http://127.0.0.1:25300`，API `http://127.0.0.1:28000`，浏览器响应 `schema_version=2`、`data_mode=live`。没有 route/fulfill、fixture 注入、响应替换、业务数据写入或另起 API/frontend。
- 浏览器和 HTTP 原始工具日志中的 Z/毫秒/微秒均作为 raw 时间留档，非人类 UI 格式合格证据；报告中的执行时点按 Asia/Shanghai 秒级 `+08:00`。Must 1 专门区分日志原值与产品人类展示。
- 已读根 AGENTS、执行地图、R04/R17 卡、T40/T41 原卡、只读投影合同、公共 API v2、交接与状态；采用新版 ponytail-review 的真实输入/边界/最小修复审查要求。`docs/design/recovery_hacker_workbench.md` 作为设计依据；旧 fixture/认证报告没有冒充本轮来源 live。
- 实际工具：Windows PowerShell/pwsh；Node `v24.13.1`，npm `11.8.0`；固定前端 `@playwright/test 1.64.1`，Chromium headless shell 1248。测试是 Playwright 浏览器 API + 独立 Node assert/expect 的检查点，不是项目全套 Playwright test suite。
- 输入/输出：真实 DPAPI 测试身份及现有 HTTP 服务→实际 DOM、HTTP 状态/业务 DTO、登录后 PNG 和脱敏 JSON。只新增本报告与 `reports/runs/recovery_r04_live_ui_review_1_20261015/`；没有改变 root 最新未提交修改。

## 实际执行与失败保留

所有浏览器子进程 cwd 为 `C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/frontend`。外层 PowerShell cwd 为 `D:/dianzi`。每份 command.json 保存真实命令、固定 SHA/tree、精确 +08 时点和退出码。

| Run | 外层实际命令 | 开始—结束（2026-10-15 +08:00） | 退出码 | 检查结果 |
|---|---|---|---:|---|
| 首轮 | `pwsh -NoProfile -File reports/runs/recovery_r04_live_ui_review_1_20261015/run_review.ps1` | 2026-10-15T14:24:37+08:00—2026-10-15T14:24:50+08:00 | 1 | 10 passed、1 failed、0 skipped；失败为 reviewer 错误假设 |
| 修正主路径 | 同上；当前 label=run2 | 2026-10-15T14:26:50+08:00—2026-10-15T14:27:05+08:00 | 0 | 29 passed、0 failed、0 skipped |
| 补测 | 同上追加 `-Label complement` | 2026-10-15T14:29:20+08:00—2026-10-15T14:29:28+08:00 | 0 | 10 passed、0 failed、0 skipped |
| 真实历史日期 | 同上追加 `-Label nvd_dates` | 2026-10-15T14:31:20+08:00—2026-10-15T14:31:28+08:00 | 0 | 2 passed、0 failed、0 skipped |

首轮以为 `product=vllm` 尚未支持并预期 422，真实返回 200；7184 已有基于保存 `affected_product` claim 的过滤，所以是测试输入假设错误，不是产品失败。保留首轮 stdout/receipt/PNG 与原 harness `live_browser_review_run1.mjs`；后续对产品筛选实际验证 200，并以非法时间输入验证真实 422。没有删失败、改业务或改通过门槛。

主路径“pagination to actual NVD evidence”检查现场第一页已含 NVD，循环未实际触发分页；它只计 NVD 详情/引文观察。独立 complement 明确点击一次 next_cursor 并确认 20→20、事件 ID 无交集，填补真实分页证据。

修正后合计 41 个 passed 检查点执行，包含重叠链路，不能称 41 个不同业务任务或全套回归通过。首轮 10 passed/1 failed 单独保留，不并入成功合计。本轮 unit、合同/后端集成套件和全套 lint/typecheck/build 未另运行，均 not_run；root 既有日志不当成本 reviewer 复跑。

独立 harness SHA-256：首轮 `11aa23fbc6d8d34aaa54245c9e2da1309e474762dfc64bc0c4a9b7a41ce50063`；run2 `620887e9ade232c8b63b149277d2711ffd1c13131ebededab614355eae602609`；complement `5f4f2099969a40572deaf8b76e454688a2825b005480a4f7f5daaa0684fded28`；nvd_dates `6451e1f5d530219b9de8bb7bda28d64353d4272f3fdb575378c9c2fccfa49343`。root 未提交 `frontend/e2e/r04_real_sources.spec.ts` 仅阅读、未运行，读时 hash `0004db3fbdcc01d95937a454a79cc24ea2f6839a74486d15eec995b61f320d9a`；该测试从匿名 `#events` 找不存在的登录表单，登录后的事件页又找退出按钮，不能直接作为本轮作者测试通过证据。真实产品导航为事件页→登录链接→会话页，再返回事件页；独立测试按此路径执行。

## 真实浏览器结果

| 可观察行为 | 1366×900 与 390×844 的实际结果 |
|---|---|
| 认证、模式、真实列表 | 匿名事件页无记录；通过实际登录链接进入会话页，POST login 200；进入事件页 GET 200，20 条、本页标签 Live，全部 title/source_count/freshness 与当前 HTTP DTO 逐行相同，没有总数或假图表 |
| vLLM 厂商公告 | 实际选中 `ea3eee85-aca6-5e90-8cd5-6b340397018f`，标题 MOSS-Audio processor cache；source_count=1，与 revision 中去重 source_id 一致；九维均未提供，全部呈现“未提供该维度”，事件时效未知 |
| NVD | 实际选中 `d11bb4a0-1d45-5d8d-b3a1-262c27132dc0` / CVE-2026-110719；详情九行，DTO 中 CVSS available/current、其余八维缺失。成功维度不冒充九维完成 |
| 原文版本与位置 | vLLM span `13a9dbee-7933-49b7-99f8-11be0ee65088`、revision `266e4626-fe50-4c33-a6f7-4c7a7192408e`、JSON `/description`、Unicode `[323,2323)`；blockquote 与 HTTP quote_text 相同；Enter 激活引用后实际焦点在证据 aside |
| 历史未知日期 | NVD span `762153e3-3565-4c60-9c08-68d744a984a0`、revision `002f4181-262f-4329-ba09-873a493486d5`、JSON `/cve/metrics/cvssMetricV40/0/source`、Unicode `[1385,1409)`；源发布和源修订为 null，DOM 均显示“未知 / 未留存”，没有拿采集日期填补 |
| 引用与支持边界 | 页面明确“引文存在 ≠ 内容支持”，来源断言按 DTO 显示 structured_source/原文明示及状态；第一条 NVD 引文是评分 authority 字段，仅确认片段定位，不把该片段单独当评分内容的充分支持审查 |
| 刷新 | vLLM 深链刷新产生新的 evidence GET 200，revision_id 与 quote_sha256 一致；没有存储状态复用或前端注入。固定后端 `knowledge_routes.py:66–69` 每次用 SQLAlchemy Session 创建 PG reader；本 reviewer 未另跑 SQL 逐行复核 |
| 搜索、空、分页 | 空查询实际 200/0，清旧详情/引文，明确“不代表没有相关风险”；产品过滤实际 200；非法 updated_after 实际 422 validation_error，显示错误与重新查询，未显示空成功；next_cursor 真正翻页后 20→20 无重复；第二页搜索 CVE-2026-86289 实际返回 1 条且无 cursor |
| 网络失败和重试 | 仅独立 Chromium context 置 offline，真实请求断网、界面错误及重试入口，旧列表清空，不变成 200 空；恢复 context 网络后重试真实 200/1。此为浏览器网络故障注入，不算供应商故障或 backend 503 实测 |
| 对象缺失与退出 | 真实不存在 UUID 返回 404，显示“记录不可访问”、旧 claims/evidence 清除；不是跨租户 ACL 试验。真实 logout 200，重新进入事件页无旧记录、模式回到登录后确认 |
| 动效与输入边界 | normal 的 computed transform 约 1.1 秒前后改变，topology-drift 22s、opacity .3；背景 pointer-events:none，实际按钮/引用可操作；reduced-motion 后 animationName=none 且两帧 transform 均 none |
| 窄屏、焦点、正文 | 两屏 document/body 宽度分别等于 1366/390；证据文本 Range 检查无越界；blockquote 14px；skip link 键盘 Enter 聚焦 main 且保持事件深链，2px 实际 focus outline。长英文原文、URL/UUID 和 metadata 可换行，桌面证据栏内滚动，移动单列 |

run2 HTTP 观察包含 login/logout 200 各 2，列表 200×10/422×2，事件详情 200×6、证据 200×6，匿名 me 401×2；response.fromServiceWorker 均 false。两屏 pageerror 均空。日志保留 React StrictMode/导航取消的 `net::ERR_ABORTED`，没有把请求取消写成供应商故障，也没有隐藏失败。精确每条请求见 run2/browser.stdout.json。

外部原网页单独验证：GitHub 实际打开上述公告 URL，HTTP 200，标题与 MOSS-Audio 公告一致，具体原文可达。NVD 两次实际导航均 HTTP 200、URL 规范化为小写，标题 `NVD - Home`；第二次额外等待 1.5 秒正文仍为空、CVE ID 不存在。NVD 只能记录**传输可达、具体原文内容 blocked_external_content**，不写网页内容打开成功。产品中的已保存证据仍可读取，外部结果不改变定位或支持结论。

## 截图检查、源码核对和剩余边界

审查者实际查看了 run2/full-page list/detail/evidence，以及 complement 的可读 viewport 截图和 nvd_dates 的 metadata 截图。黑炭色、青绿单主强调、细边框和高密度表格符合当前指令；拓扑在留白可见且正文面板不透明。截图均登录后，只截情报/证据/空/错误页，没有密码表单或会话身份面板。可读关键截图：

- `complement/list-viewport-1366.png`、`complement/list-viewport-390.png`
- `complement/evidence-viewport-1366.png`、`complement/evidence-viewport-390.png`
- `complement/offline-viewport-390.png`
- `nvd_dates/nvd-unknown-dates-viewport-1366.png`、`nvd_dates/nvd-unknown-dates-viewport-390.png`

源码与实际 DOM/HTTP 交叉：`frontend/src/features/events/event-workspace.tsx:17–22` 保存时间/时效、`:73–88` 九维/断言/修订、`:113–119` 引用焦点/文本/URI、`:158–176` 检索/本页数量/空与错误；`api/knowledge-client.ts:14–37` 实际只读端点及 ID/revision 核对；`api/knowledge-contracts.ts:51–59,88–97` 严格字段及 http(s)/无 userinfo URI；`styles.css:24–30,207–209,212–254` 背景、reduced-motion 和布局。rg 未发现产品 src 使用 localStorage/sessionStorage、innerHTML 或 browser route.fulfill；原文用 React 文本显示，不执行其中的命令或 PoC。没有用 CBM 建索引；本轮直接读取与 rg 已足以核对这个有限前端调用图。

未验收的实际边界：

1. 来源监测页 `CapabilityWorkspace` 仍 empty table + “本页能力待接通/待接通”，实际没有 source 状态/失败记录。真实 API/队列日志中的两个来源成功不等于此页已接线；T41 来源类别、增量能力、最近成功/失败/延迟和完整 R17 仍未完成。
2. 真实 failed/blocked/stale/not_found/not_applicable/conflict 维度、模型假设/争议/撤回、同事件多独立来源、不同历史修订切换未在本轮真实样本触发，live `not_run`。旧 fixture 结果只可作旧 fixture 回归证据，不补成本轮 live。
3. 原生后台/最小化引发的 document.hidden 暂停 `manual not_run`；没有改 document.hidden 或合成 visibilitychange 伪装验证。前轮相关环境缺口保持。
4. backend 503、会话中途401、真实跨租户/权限403、长任务/问答/资产/图谱/推荐/报告未运行；404 负例仅存在性，不签 ACL。
5. 双人金标、支持内容充分性、来源正确率、模型检索、FOFA、性能/吞吐/持续运行和正式 Linux 部署均未在本审查范围。Windows worker solo 缺 Celery native hardlimit，root 的 PG 35s watchdog/512MiB JobObject 是受控观测边界，不能写 Linux 正式部署 live 通过。

## 安全、运行资源与交付

凭据仅由 `run_review.ps1` 在内存解开已指定 DPAPI，再传子进程环境；没有 print/argv、产品模型/FOFA key 读取、storageState/cookie/CSRF 持久化。trace、video、自动失败截图均关闭；stdout/stderr 先在 Python 内存用实际身份全文及全部连续 8 字符片段脱敏，再写 JSON/log；所有 PNG/JSON/脚本/本报告和固定前端源码的最终扫描见 `credential_scan_final.json`，不保存扫描值。之前三份运行 scan manifest 均 0 命中。

使用 root 现有受控服务：API7184 段启动 2026-10-15T14:18:16+08:00、frontend7184 启动 2026-10-15T14:19:19+08:00，各最大 1800 秒；MinIO 既定截止 2026-10-15T15:17:25+08:00。读到的 root 第三采集段 2026-10-15T14:19:19+08:00—2026-10-15T14:22:20+08:00 结束快照为 55 events / 334 evidence，但这是 root 日志的该时点全库计数，UI 只展示当前本页 20，不据此发明总数、持续监测或两源之外全部接通。旧 Linux 出网失败和旧 vLLM 失败证据保留，不以新段抹去。

全部独立 browser/context 在 finally 关闭，测试身份正常退出，子进程环境 finally 清理；没有停止 root API/frontend/worker/MinIO，亦没有无限重启服务。审查输出只有本报告和指定 run 目录；未越过文件所有权。

评分证据仅限 D2（真实可操作界面及窄屏/键盘/动效）、F1（两源记录的实际显示）、F2/R1（维度缺失、历史位置/时间/引用边界）。不能外推完整评分项满足。

下一步建议：主控可据以下 d391 定向记录关闭 Must 1；真实事件链证据保持其原版本归属。完整来源页接线及后续富化/R17 依赖按原 DAG 继续，补上真实失败/过期等状态再独立审查。NVD 原网页内容需要来源可返回具体正文的环境，当前保存的证据 UI 无需为了外站空响应扩大补丁。

## 追加定向复核 · 前端 d391f89 + 后端 7184

主控冻结前端 `d391f89c65fb892b27b6a3b45cf0a06fea6032b0`，独立工作树 `C:/Users/yinha/.codex/worktrees/r04-ui-time-review/dianzi`；本 reviewer 通过 managed create_worktree 创建，不 checkout 或编辑原正运行 7184 工作树。版本和干净 git status 另存 `time_recheck/frozen_source.json`。新 UI 用独立 Vite `127.0.0.1:25305`，同源代理既有 `127.0.0.1:28000` / 后端源码 `7184dc63525ae3e8ea439ec64fc03dfaa629f7a8`；原 `25300` 仍是 7184，没有把它当新 UI。

真实命令：外层 cwd `D:/dianzi`，`pwsh -NoProfile -File reports/runs/recovery_r04_live_ui_review_1_20261015/time_recheck.ps1`；浏览器 cwd 为新工作树 `/frontend`，`node D:/dianzi/reports/runs/recovery_r04_live_ui_review_1_20261015/time_recheck.mjs`。执行 `2026-10-15T14:46:14+08:00`—`2026-10-15T14:46:20+08:00`，browser exit 0，10 passed / 0 failed / 0 skipped。后端到期前已跑完，无需重启 root 服务。证据见 `time_recheck/command.json`、`browser.stdout.json` 和 PNG。

定向检查每屏各 5 项：

1. 实际 Live 列表所有 `<time>` 文本匹配 `YYYY-MM-DDTHH:mm:ss+08:00`，并用独立 `Intl.DateTimeFormat(...timeZone:Asia/Shanghai...)` 校核；每行 `dateTime` 属性与该次 API 的 `first_seen_at` 原值逐个相同，保留 Z/微秒，不污染原始数据。
2. 列表 `white-space:nowrap`；两屏 document 宽度仍为 viewport。390px 表格自身 `scrollWidth>clientWidth`、overflow-x:auto，实际设置 scrollLeft 至右侧后可以看到时间列。截图实际查看，时间不再拆成两行。
3. 真实 vLLM evidence/revision 的源发布、源修订、首次观察、入库、定位核验各自读取自己的字段并转为上海秒级；源发布实为 `2026-10-06T14:59:51+08:00`，首次观察为 `2026-10-15T14:19:29+08:00`，未拿后者覆盖前者。原 `dateTime` 属性均不变。
4. 真实旧 NVD 的两个 null 源时间仍显示“未知 / 未留存”；新 UI 深链刷新再次真实 GET 200，revision 与引文保持正确，其余有值时间按合同格式显示。
5. 运行状态页的真实健康检查时间同样显示上海秒级，原属性仍是原始 UTC 时刻。

源码六文件 diff 直接复读：`formatShanghaiTimestamp` 是 4 行共享函数，SavedTime 及健康检查仅改变显示；未知时间分支、证据 ID/revision、查询/认证/持久化路径保持。作者 120 单元/类型/lint 证据仅作为作者结果读取，本 reviewer 没有重算为自己的通过数量；也未把作者 runner 的首轮 GBK 外层打印失败计成业务测试失败。

资源：自建 Node `--max-old-space-size=384`，浏览器命令 timeout 160s，外层记录总授权上限 600s、Vite 日志上限 4MiB；实际服务约 6 秒，日志远小于上限。Vite 进程在 finally 的 `2026-10-15T14:46:20+08:00` 终止，end.json 的 exit 1 是主动结束服务，不是 browser 失败。所有独立 browser/context 正常关闭，凭据清理；没有停止 root 后端、25300 或 worker。

运行隔离限制：为赶在既有后端到期前，新工作树 `node_modules` 使用 junction 复用 7184 依赖。Vite 日志显示重新优化依赖，因此共享的 ignored `node_modules/.vite` 缓存可能更新；没有修改产品源码，但不能宣称依赖缓存完全隔离。没有删除/回写共享缓存或重启原服务，已向主控披露。此限制不改变实际加载新 UI 后记录到的时间 DOM 结论。

本附录只关闭时间 Must；不重新签整 R04/R17，也不把原生 hidden、真实 stale/failed 等缺口变成通过。新的截图为 `time_recheck/time-list-{1366,390}.png`、`time-evidence-{1366,390}.png`、`time-null-{1366,390}.png`，均登录后、无密码页/trace/video/storageState；最终凭据扫描随附录更新。

清理：独立 Vite/browser 已停止；已对唯一自建 `r04-ui-time-review` 工作树调用 managed archive，工具首先返回 queued。随后 `2026-10-15T14:49:05+08:00` 的实际路径检查显示自有 checkout 已不存在、共享原依赖目标仍存在，记录在 `time_recheck/archive_request.json`；不以 queued 本身冒充完成。归档前 111 文件扫描（含新前端源码/报告/全部新截图）0 凭据命中，另存 `time_recheck/credential_scan_source.json`；归档后最终 90 文件扫描继续覆盖现存证据与报告，0 凭据命中、0 trace/video/storageState 文件。
