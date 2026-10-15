# R17 事件详情 UI 切片

状态：`awaiting_review`；本当前 API 详情展示切片实现 `complete`，整 R17 `partial`。基线 `c3a2abc9a5246993eabb351d26cfeb51d0270b31`，源码冻结 `c5ad9de9d31a28f927d45dcbd4589fa840a9101f`，独立工作树 `D:/wt/r17-event-detail-ui`，分支 `codex/r17-event-detail-ui`。仅事件目录、直接测试和本报告/run；不修改共享 API、App、全局 CSS、背景、状态、依赖或后端。未 push，未自行 accepted。

## 调研与设计决定（实现前）

已读 AGENTS、00 execution map、R17/T41、U02/U08、03/04 与 CR-R04 冻结只读投影、当前状态与交接。复用 `docs/design/recovery_hacker_workbench.md` 已有 Elastic Timeline/Wazuh 调研；本轮真实重读 [Elastic 告警详情官方文档](https://www.elastic.co/docs/solutions/security/detect-and-alert/view-detection-alert-details)，关注关键字段、概要/字段阅读结构、相关证据互跳和保留列表上下文。外部 ui-design 只作为参考；其自动按等级裁决冲突、假 9/9 富化时间线、替换九维和演示值均不采用。

设计阅读：面向情报研判人员的证据工作台，黑绿/低亮拓扑语言，使用现有 React/native CSS。DESIGN_VARIANCE=3、MOTION_INTENSITY=2（详情自身无持续动画）、VISUAL_DENSITY=7；沿用现有 5px 面板和 4px 控件圆角与颜色变量。design-taste 明确不适用于密集产品页，本轮只取审计、排版、状态、对比与响应式规则，不套营销 hero/图片/组件库；Ponytail 5.2 full 不增加依赖。

输入为当前 schema2 的 EventDetailResponse/EvidenceResponse；输出是事件上下文、九维状态与关联断言值、来源断言、原文修订与固定版本引用。API 未提供独立维度数值、人工确认任务、合并/重判事件、差异比较或文档全文入口；这些能力不猜测、不生成假状态。保留全部九维，包括未提供/未发现/不适用/冲突/受阻/失败/待处理；引用存在不自动成为支持关系。

计划改 `frontend/src/features/events/event-workspace.tsx`、新增私有展示组件/样式与直接单测，新增自有 fixture e2e。回归定义：关联 claim 值动态展示；冲突双方和撤回/过期状态保留；null 时间不补值；旧修订引用保持 revision 深链；403/503 和加载不泄露旧内容；390/1366 键盘与长文本可用。复用既有认证/会话代次隔离和 client。

## 改动文件与行为

源码冻结仅 8 文件：事件 `event-workspace.tsx`、`event-workspace.test.tsx`；新增 `event-detail-view.tsx`、`event-display.tsx`、`events.css`、`event-detail-view.test.tsx`、`event-detail.fixture.ts`；新增 `frontend/e2e/r17_event_detail_fixture.spec.ts`。其余是本报告与 `reports/runs/recovery_r17_event_detail_ui_20261016/` 自有证据。

详情先显示事件类型、保存状态、可见来源数、首次发现、过期/未知时效与 Fixture/Live 模式；标识在原生 disclosure 中完整保留。阅读按钮用 instant 焦点/滚动进入九维、事实、原文修订，不改事件 URL；成功打开详情后定位其标题，loading/error 不抢焦点。证据成功取得仍定位侧栏，390px 单列。

九维来自冻结 enum，值严格按响应中的 claim_ids 映射 display_value，不从 quote/predicate 推算值。available 无关联值、关联断言缺失、未提供维度各有明确说明；七状态和 freshness 使用文字与颜色。冲突双方、来源方法、supported/disputed/unverified/withdrawn/superseded 保留；完整中文条件不截断。观测时间和来源版本为 null 时可展开核查未知，无假进度或自动裁决。

修订按服务返回顺序保留文档/来源标识、各自修订号、解析状态、四个时间；只有服务 event.latest_revision_id 匹配项标“事件指向的最新修订”，不把其他文档自动判为旧版本。每项修订汇聚已返回的引用链接，证据 deep link 带 revision_id；外部 URL 标为留存地址并提醒可能已更新，保存片段仍可读。Evidence nullable 页码/JSON 位置显示“未提供 / 未留存”，不将未知混作不适用。

沿用现有原生 CSS/共享认证与 API client。新样式仅限定 events，主色和背景沿用现有变量；新内容无持续动画。移动 disclosure/引用触达至少 44px，焦点框青绿，reduced-motion 禁用详情过渡。完整产品所有动态背景证明仍引用既有证据，本切片只复核 reduced-motion 下 animationName=none。

两个旧单测调整为在修订 article 内精确断言四个未知时间、在 blockquote 内核查已取得证据；新增可折叠摘录和维度时间后，原先全页文本计数不再代表该业务对象。未修改金标、阈值、分母、skip 或原验收条件。

## 真实命令与结果

所有固定 check argv、cwd、秒级起止（Asia/Shanghai）、exit_code 在 run 的 `commands.jsonl`；对应 stdout/stderr 原始日志保留。使用 Node24.13.1、已安装同锁依赖（工作树 node_modules 连接到 root 的现有目录），不安装或改变依赖。测试和浏览器均单 worker；Vite 专用 loopback 25317 启动/结束，最后检查无 listener。

| 实际命令 | 结果与范围 |
|---|---|
| `npm run test -- --run src/features/events/event-detail-view.test.tsx src/features/events/event-workspace.test.tsx --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<events-tests.json>` | 00:33:14–00:33:21，exit0，30/30，0failed/0skip（14 新增与 16 既有），随后最终全套包含这些测试 |
| `npm run test -- --run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<regression-tests.json>` | 00:39:54–00:40:17，exit0，352/352，0failed/0skip；new14，不重复相加成 382 |
| `npm run typecheck` / `npm run lint` / `npm run build` | 最终 00:40:17–00:40:26 均 exit0；53modules，JS267.89kB/gzip82.20kB，CSS37.74kB/gzip7.76kB。生成 tsbuildinfo 恢复基线，不入提交 |
| `node node_modules/@playwright/test/cli.js test --config <本run/playwright.config.mjs>` | 最终 00:40:56–00:41:01，exit0，7pass/0fail/0skip/0flaky；本切片3与既有R04 fixture4；所有 /v1/** 白名单隔离拦截，不访问真实登录或后端 |
| CBM index/schema/architecture/search/trace + `rg` | 最终 index/trace exit0，331nodes/1200edges，partial0/unusable0，24测试文件按 fast 设计不索引；仅此 WT frontend/src，独立 WSL cache、persistencefalse，不提交 cache |
| `git diff --check` 和源码 `git diff --cached --check` | exit0；全证据 staged 检查 exit2，原始 browser.stdout/error-context 及工具日志有尾空格/末尾空行，详见 `staged-evidence-diff-check.log`。不修改原始字节、不加 ignore；限定源码/报告/runner 检查另记 exit0 |

CBM 通过 schema/search 核实完整 qualified_name，trace 当前 EventDetail→getEventDetail→fetchJson/parseEventDetailResponse 与 EventDetailView/各私有展示函数；rg 对照 evidence 调用和固定 revision 校验。源码图不替代业务测试。

首轮浏览器 00:35:58–00:36:03 exit1，0pass/3fail：fixture 白名单漏配 App 的 health 请求。`browser.initial.json`、`browser.stdout.log`、`browser_artifacts_initial/` 留存；加入明确合成 health 路由后原 3 项在 00:36:34–00:36:39 全通过，扩入原 4 项后最终 7 项通过。最初 evidence runner 的终端 GBK 无法打印 Unicode 抛错，但子进程真实 exit1 已写 commands/log，随后 stdout/stderr 改 UTF-8；不把该异常包装为业务通过。

CBM 最初默认 WSL 发行版/PATH 没有可执行文件，工具输出“env: codebase-memory-mcp: No such file or directory”；该次退出码未单独持久化。第二次重定向误用了 frontend 相对 reports 路径，命令未执行，打印的旧 LASTEXITCODE 不能证明索引成功。后续主控给出固定 Ubuntu-22.04/portable binary，run 以正确绝对位置记录实际成功 index/schema/architecture/trace。以上均非业务测试失败，也不隐瞒为通过。

## 截图、边界与评分证据

作者实际查看最终 `browser_artifacts/` 内 1366x900 详情 viewport、390x844 详情 viewport/历史证据/局部503，以及完整页结构。桌面上下文和首个真实投影值在可读范围；窄屏标题/时间/ID/中文条件换行，无整页横溢出。自动检查 Range 文本每行的 viewport 边界、详情/阅读位置/引用键盘焦点、历史深链刷新恢复与 reduced-motion。没有截图密码输入、trace 或 video；全部画面有显式合成模式。

unit/frontend：passed（352 中的限定证据）；contract：passed 仅原 strict schema/client 回归；integration/e2e：passed 仅隔离 HTTP fixture→真实 client→React→Chromium 的 UI 链；live/真实 PG/API/真实富化：`not_run`；manual：作者限定视觉检查 passed，非独立验收。未测真实人工复核、合并/重判历史、完整 v3 值投影、正式时效/性能、真实供应商、原生隐藏页面暂停与连续运行。

D2/U02/T41：限定证明九维完整呈现、状态/缺值可辨、原文引用固定版本、未知时间不补值、部分失败继续阅读、长条件/键盘/窄屏。F2：仅展示后端保存的值与支撑状态，不证明本切片新产生富化结果或准确率。U08：仅已保存的修订与旧引用可查，不证明旧命中/新命中/旧空结果重判。合同/计划无变更；当前 schema2 尚缺的新业务能力显式保留，完整 R17/G-E 不据此验收。

下一步：主控对冻结源码安排新独立 review；在当前真实服务/授权会话下复跑详情→修订→证据，并将后续已批准公共投影接入。源码/材料只本地冻结供检查，根状态与阶段更新由主控负责。

未检查：本切片真实后端/live 与完整 v3/人工确认/合并重判；风险是 schema2 能展示的信息有限，页面无数据替代路径。既有动态背景的原生 hidden 验证缺口不由这些 fixture 浏览器消除。

制品清单 `artifact_manifest.json` 校验 8 个源码文件的 LF SHA256 与冻结 Git blob 一致；证据记录原始字节及可读 UTF-8 的 LF SHA256。限定 credential-shaped literal 扫描 0、生成生产 JS 中 4 个本测试独有标题/谓词/错误/quote 标记为 0；这不是全仓安全扫描，也不证明未知秘密不存在。
