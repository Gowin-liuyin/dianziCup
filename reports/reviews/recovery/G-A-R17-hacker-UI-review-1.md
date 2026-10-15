What this change does: 此次变更把现有认证与健康页面改为近黑绿青研究工作台，加入十个核心导航、准确的待接通页面，以及缓慢漂移的 SVG/CSS 背景。真实业务接线仍只有 auth/health；情报、来源、图谱、问答、资产、任务、推荐与报告是明确标识的准备布局。

# G-A / R17 黑客风 UI 准备切片独立初审

任务状态：`needs_changes`，发现 1 项实证 P2。本报告只覆盖 R01 UI 延续与 R17 准备切片，不签整 R17、整 T40–T44 或 G-A，不修改任何 accepted 状态。审查者 `/root/hacker_ui_independent_review` 未参与本实现。

审查开始 `2026-10-15T10:55:51+08:00`；报告结束时间见文末。固定审查工作树 `C:/Users/yinha/.codex/worktrees/recovery-hacker-ui-review/dianzi`；初始 `git status --short` 空。基线 `b099483b4f2be3d21b3fd3e7e4327912ba75cae2`；源码提交 `fa5787409da358ea95dbb35acfbd3a96c1fa2371` → `00a5c990c22c6bf1e1d572fe358b086baf02d66b`；被审源码 tree `e8c9534a7ec2c8b6e2689e958be548b3102eb695`。作者证据另从 `cafbe7f7c451479ce38b0674de0cf71aa44154b2` 读取，仅用于定位，未将作者日志当作独立复跑。未审作者活动 R04 分支。

实际真实 API 版本为 `4bab166d675602f8e553c8f6c1c97c74e020dd85`，地址 `http://127.0.0.1:28000`，运行段 `r02_default_4bab`；它不是本报告写作时主仓 HEAD。真实浏览器记录仅属于该段，未拼接持续稳定窗口。

## Must fix

1. **[P2] 研究页的“跳到主要内容”把用户带回运行概览**（`frontend/src/App.tsx:156`，相关 `App.tsx:141` 与 `frontend/src/app/workspace-navigation.ts:23`）

   - **职责与输入：**skip link 应让键盘用户跳过导航并聚焦当前页主内容。独立 Chromium 1248 中打开 `/#events`，等待“情报工作区”，聚焦“跳到主要内容”，按 Enter。
   - **期望与实际：**期望保留“情报工作区”并聚焦 `#main-content`。实际 hash 变成 `#main-content`、h1 变成 `运行概览_`；`main_focused=true`。链接修改 hash 触发 `hashchange`，而导航解析器把 `main-content` 映射成 `runtime`。这不是焦点风格偏好，而是可复现的错误导航。
   - **影响：**使用这个无障碍入口的用户会离开当前情报/来源/问答等研究页。未来接入业务后，还会丢失当前页面上下文。现有真实键盘测试只在默认运行页点击 skip，因此不能检出该分支；新增 N08 实际失败，未改期望或分母。
   - **最小修复与复验：**保留链接可访问性，点击时阻止 hash 路由变化并聚焦主区，或使用等价的保留当前页方案。无需新 router 或依赖。补充 events/source 非默认页的键盘回归，断言页标题、URL 页身份与主区焦点；原 62 组件及 6 真实浏览器回归必须保留。证据：`independent_negative_second_report.json` 的 N08 与 `skip_link_observation`。

Verdict: fix 1 first. 本固定版本 UI 准备切片为 `needs_changes`；修复后由本 reviewer 定向复核新固定 tree。整阶段仍需新的阶段 reviewer。

## 授权、合同与范围

已读取固定树 AGENTS、00/03/05/06/11/12，R04/R17、CR-R04、CR-R04-R02、progress/task_state 与交接，以及原 T40/T41/T42/T43 六项验收。采用 Ponytail 5.2.0 review skill，按真实调用及具体输入判断问题，没有要求美学偏好或换栈。

本轮实际看过作者证据提交中的设计与任务报告，也完整读取外部 `ui-design.md`，但没有采用其自动按等级抹冲突、9 来源分类、固定 7 工具替代 registry 或 Next/新 UI 栈建议。冻结八类别、证据历史、四态研判、权限和未知语义保持。作者引用的 [Elastic Timeline](https://www.elastic.co/docs/solutions/security/investigate/timeline)、[Elastic 告警详情](https://www.elastic.co/docs/solutions/security/detect-and-alert/view-detection-alert-details)、[Wazuh 导航](https://documentation.wazuh.com/current/user-manual/wazuh-dashboard/navigating-the-wazuh-dashboard.html)本轮也独立打开成功；查询、表格、上下文与导航分组依据相符。本次未独立重放作者每一步研究操作或将证据提交时间当作调研发生时间。

本轮只新增指定 review 报告及 `reports/runs/recovery_hacker_ui_review_1_20261015/**`；无业务实现、合同、依赖锁、认证、数据库、后台 runtime、金标或评分分母改动，无 commit/push。`npm run build` 修改了已跟踪生成物 `frontend/tsconfig.tsbuildinfo`；审查者用 `git show HEAD:frontend/tsconfig.tsbuildinfo` 原始 bytes 恢复，哈希记录于 `generated_restore.json`，随后固定工作树状态为空。未删除任何缓存。

## 实际复跑

证据根目录为 `D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015`，各命令 JSON 记录 cwd、完整参数与秒级 +08 时间。表中前端 cwd 为固定树 `/frontend`；CBM 命令按对应记录在 `D:/dianzi` 或固定树根执行。

| 命令 / 证据 | +08:00 开始–结束 | exit / 数量 / 实际结果 |
|---|---|---|
| `npm.cmd ci`；`npm_ci.*` | 10:57:31–10:58:06 | 0；按原锁安装 308 packages。审查未升级；安装提示既有 1 moderate/2 critical，CR-R10 未在本切片批准或关闭 |
| `npm.cmd run lint`；`lint.*` | 10:59:21–10:59:27 | 0 |
| `npm.cmd run typecheck`；`typecheck.*` | 10:59:27–10:59:29 | 0 |
| `npm.cmd run test`；`test.*` | 10:59:29–10:59:37 | 0；7 files，62 passed；0 failed/skip |
| `npm.cmd run build`；`build.*` | 10:59:37–10:59:40 | 0；固定源码成功构建，不据此判产品完成 |
| 固定原 `r01_auth.spec.ts` + `r17_hacker_workspace.spec.ts`；`node node_modules/@playwright/test/cli.js test --reporter=json --output=<本run>/e2e-review-artifacts r01_auth.spec.ts r17_hacker_workspace.spec.ts` | 11:02:03–11:02:16 | 0；expected 6、skipped 0、unexpected 0、flaky 0、errors 0；实际六例见 `e2e-real-api-review.json` |
| 独立 `node <本run>/independent-negative-browser.mjs`，首轮 7 项显式合成 HTTP 边界 | 11:04:56–11:05:05 | 0；7 passed/0 failed/0 skipped；首轮 stdout/command 保留。新增 N08 后脚本的 JSON 固定输出名被第二轮写入，首轮完整 JSON 未单独保存，未声称它仍存在 |
| 同 runner 新增 N08；`independent_negative_second.*`、`independent_negative_second_report.json` | 11:05:57–11:06:06 | 1；7 passed/1 failed/0 skipped；失败是实证 skip 导航问题，不是环境缺失 |
| `git diff --check b099483b 00a5c99 -- frontend/src frontend/e2e`；`source_diff_check.*` | 11:07:10–11:07:10 | 0；仅源码/测试范围。作者原始 npm 日志 EOF 告警不更改、不全局忽略、不把全证据 diff 声称 passed |
| `git diff --check b099483b cafbe7f7`；`author_full_evidence_diff_check.*` | 对应 command JSON | 2；独立确认六份作者 npm 原始日志 EOF 空行警告，原字节保留。与源码范围 exit0 分别记录 |

原 42 组件回归完整保留：client 19、auth snapshot 3、T40 11、status 8、原 App 1；新 App 2、导航 16、背景 2 合计增加 20。`preserved_regression.diff` 为空，认证实现、client、这些回归、原 3 real browser、package 与 lock 在本变更范围未改；无 skip/todo 搜索命中。各层测试有重叠，不把 62+6+8 加成独立业务覆盖数量。

真实六例由审查者选定固定 WT、原文件和新证据目录，主控只负责在独立 runner 子进程安全注入 DPAPI 凭据。审查者未读取 DPAPI、未接收/输出账号密码、未依赖作者旧 e2e JSON；已独立解析此次原始 JSON，核对六个标题、预期状态、retry=0、errors=[]、截图与动效附件。trace/video/自动截图 off。主控对本次 artifact 使用实际秘密集合扫描结果为空（`e2e-real-api-review.command.json`）；这是主控安全扫描证据，不冒称 reviewer 已读取秘密自行比较。截图均在输入清空且认证后保存；动效用例的匿名截图无输入秘密。

## 独立负例与安全观察

负例 runner 在真正的浏览器中操作本固定前端，但通过 `page.route` 注入明确 `data_mode=fixture` 的 HTTP 边界，没有真实账号、Cookie、业务对象或第三方访问；不计 live。其 synthetic HTTP 状态与网络失败仅检验客户端/UI 的行为。

| ID | 输入与观察 | 结果 |
|---|---|---|
| N01 | authenticated fixture → logout 网络 abort | 身份/权限立即消失、可重新登录；明确“服务端会话撤销尚未确认”；local/sessionStorage 均 0 |
| N02 | 已认证 → reload `/auth/me` 返回 401 session_expired | 显示过期提示，不保留旧身份或权限 |
| N03 | constructor、__proto__、带 tenant query、javascript:、子路径 hash | 均显示工作区不存在；只出现 auth/me 与两个 health 请求，未触发任意 URL/业务读取 |
| N04 | 390px 的 events/sources/graph/questions/assets/tasks/changes/reports | 8 页每一行待接通说明均位于 viewport；整体无横溢出；13px、21.45px 行高；表头仅表格自身滚动 |
| N05 | readiness 请求网络 abort | 清晰错误和重试、无“全部依赖就绪”；未用空列表代替失败 |
| N06 | 实际 CSS 动画，随后 reduced motion | transform 与实际截图 bytes 变化；主内容 bounds 不变；pointer-events none，面板 rgb(16,25,28) 不透明；reduce 后两张隔 1 秒截图完全相同 |
| N07 | login user A → me snapshot user B | invalid_response，未展示权限，密码输入已清空 |
| N08 | events 页键盘 skip-to-main | 失败；焦点到主区但页面转 runtime，见 Must fix 1 |

同会话身份/CSRF读取的正负例仍通过：真实 Cookie HttpOnly/Strict、登录/重载/撤销；组件检查 me 原子 snapshot、同用户 Cookie 替换时使用当前 snapshot nonce、不同 Cookie 不撤销新身份、缺 CSRF snapshot 不回退第二请求。源码 `getSessionSnapshot` 单次 `/v1/auth/me`、CSRF 仅 ref 内存；`fetchJson` credentials/include、no-store、超时与错误清理；request generation 阻止旧请求恢复清除身份。未发现新增 secret 存储、innerHTML/eval、任意 URL、shell、SQL、攻击入口或新业务真值计算。

当前没有私有业务结果缓存、也没有可见的其他租户对象请求；上述检查不能替代未来 T41/T42/T43 对真实对象读/搜/导出的跨租户测试。跨身份 snapshot 拒绝是客户端边界证据，不能外推所有租户授权已通过。

## UI、背景与可用性

审查者实际打开本次独立 real run 的 1280 runtime 与 390 events PNG：中文字形可读、待接通长说明完整换行、无随机指标或成功进度。Live 来自真实认证返回，旁边明示“模式与业务验证状态分别呈现”；待接通页仍保留 warning 文字，不将 Live 解释为来源/模型/检索完成。

源码背景只有 15 个装饰子元素，SVG transform 与光域缓慢运动；fixed/pointer-events none/aria-hidden、业务面板不透明，无遮挡或布局抖动。审查者独立 N06 的像素变化证据与 reduced 截图相同证据支持“动态真正可见/可停止”；真实六例中附件也为 topology-drift running，reduce 后 animationName=none。真实 run 60 帧约 1000ms、帧间 p95 16.70ms、max 16.80ms、0 observed longtask，只是该设备该短窗粗观察，不是正式产品 P95、吞吐或持续性能保证。

CSS 主文、次文、accent、warning、error 对 opaque panel 的相对亮度对比分别约 15.03、7.70、11.38、10.05、8.01（`color_contrast.json`）；此计算只涵盖实际主题色表，未声称逐元素完整 WCAG 审计。准备表格禁用控件没有虚构可操作能力。状态以中文文本与颜色共同表示；unknown/partial/stale/pending/waiting_approval 等 labels 存在，但真实长任务和全部状态流尚未运行。

`AmbientBackdrop` 在 mount 注册 visibilitychange，cleanup 移除同一监听；CSS data-paused=true 暂停三种动画，组件两个生命周期案例通过。**原生 hidden 暂停仍未证实**：本轮未把人工派发 visibility 或属性伪造当 live，也未重复作者已无进展的 headless/headed/minimize 探针。当前观察 document.hidden=false、visibility=visible；这证明 visible 状态，不证明真实后台暂停。保留 manual 缺口；在能产生原生 hidden 的受控浏览器环境，需观察 animationPlayState paused、transform 停止并恢复，无需扩大组件框架。

## CBM 与源码对齐

使用 WSL Ubuntu-22.04 官方 portable `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` v0.11.0，先实际读 `--help` 与 index/search/schema/trace help。唯一 allowed root 是固定树 `frontend/src`；独立 cache `/tmp/dianzi-cbm-hacker-ui-review1-20261015` 在仓库外，persistence=false。没有索引秘密、holdout、reports；fast 模式主动排除 6 个 test 文件，测试另由源码和执行核对。

| 操作 | +08 起止 | 结果 |
|---|---|---|
| index fast, name=hacker-ui-review1 | 11:00:06–11:00:12 | exit0；79 nodes/218 edges，skipped0、partial0、unusable0 |
| get_graph_schema | 11:00:57–11:01:01 | exit0；实际 CALLS 70、CALL_REFERENCE 1、IMPORTS 29 等 schema |
| search_graph 首次带未安全跨 WSL 引号的 `|` 参数 | 11:01:44–11:01:48 | exit127；bash 把正则当管道，stderr 原样保留；工具调用错误不是源码缺入口 |
| search_graph Function 全表 | 对应 `cbm_functions.command.json` | exit0；35 functions，取实际 project-prefixed qualified name；无边不推断无调用 |
| AuthProvider outbound trace | 11:04:18–11:04:22 | exit0；到 getSessionSnapshot/loginSession/logoutSession/publicProblem/fetchJson 等 11 callee |
| getSessionSnapshot outbound trace | 11:04:22–11:04:26 | exit0；7 callee，含 fetchJson/parseCurrentUser；与 client.ts:120–125 的单次 auth/me 对齐 |
| Workbench outbound trace | 11:04:26–11:04:29 | exit0；23 callee，含 getLiveness/getReadiness/导航/背景/准备布局 |

改用实际 JSON args-file 后 trace 不猜参数。`rg` 对齐 client.ts:121/134/141/146/151 的固定端点和 App/auth-session 实际调用，识别 UI → AuthProvider → client → fetch 与 UI → health 路径。源码索引不是安全/行为验收的替代。

## 原验收保留与未检查

T40 C01/C02/C03/C05 在此次真实 auth/health 六例和独立负例有相应证据；C04 只有 status labels/fixture 状态覆盖，未代表未来完整业务流；C06 因研究页 skip 缺陷未通过。原 T41 C01–C06 的真实多源归并、维度、revision 引用、未知发布日期与对象权限均未跑；只验证布局长说明。原 T42 C01–C06、T43 C01–C06 的真实资产/规则、旧结论、导出、问答、长任务、订阅与越权业务均 `not_run/blocked_business`，没有靠 placeholder 关闭条件。

R17①仅 auth/health 与导航准备页通过；②正确版本引用、③长任务恢复/取消/重试未实现；④仅已知待接通与健康失败；⑤已有 390/全导航键盘覆盖但 skip 失败；⑥当前无 mock 成功/无新增秘密持久化，未来真实对象跨租户仍待。R04 原⑥登录到真实证据流程未运行。F1/F2/F3 只登记信息结构准备，不登记业务得分；D2 有本切片操作/截图证据，不代表完整演示、连续录像或答辩通过。原生 hidden、正式性能、来源/模型/FOFA、人工金标、连续采集与完整产品状态未检查。

安装报告的既有依赖漏洞仍由 CR-R10 与主控协调；本 UI diff 未更换依赖，无相关批准或风险关闭声明。未发现必须增加的框架、深层抽象或新组件库，Lean 不另报行数。

## 操作异常与交接

后台 `Start-Process -WindowStyle Hidden` Vite 启动被自动审批拒绝，返回确切原因仅为 `blocked by policy`，没有更详细安全条款；未重复同一后台方式。之后用受控前台 exec 会话、25300 strictPort 启动，安全方式不同；凭据 runner 前已验证 listener 为 reviewer 自启 node/Vite并交回端口。证据 `vite_handoff.json`、`approval_rejection.json`。只操作本人 Vite，未操作 root API/数据库/容器/worker/scheduler。

下一步是作者修复 Must fix 1，冻结最小 diff，由本 reviewer 保留原负例并定向复核；完整 R17 在业务前置齐全后另验收。本报告没有授予 push/部署/清缓存或自动 accepted 权限。

本人 25300 Vite 最终于 `2026-10-15T11:11:52+08:00` 停止，验证 listener_after_stop=false（`vite_final_stop.json`）；关闭了本负例脚本全部 browser contexts/browser，未操作其他进程。固定工作树 HEAD/tree 不变，status 空。准备的 `real-playwright.config.mjs`、`safe-reporter.mjs` 未执行，不计任何测试；实际 real 六例使用原仓配置和主控安全 helper。

报告结束：2026-10-15T11:12:34.7900103+08:00。artifact 清单见本 run `artifact_manifest.json`；缓存只登记保留，不删除。
