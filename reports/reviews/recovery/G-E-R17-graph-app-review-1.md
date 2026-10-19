# R17 默认 App 图谱接线 · 新非作者初审 1

What this change does: 本批次把已审过的证据图组件接入默认工作台。已加载事件详情可进入 `#graph/{event_uuid}`，图中关系可经原文 GET 打开实际修订，刷新和返回保持对象标识；无事件的 `#graph` 给出可解释入口。schema1 精确增加规则 1.2，并保留历史 1.0/1.1 和未知版本拒绝。

Verdict: Ship. 仅批准本次默认 App 前端接线切片进入主控集成审议；没有发现 Must fix 或 Should fix。完整 R17 仍 partial，真实后端装配/API/PG integration、live 和完整人工验收为 not_run，不签 G-E、accepted 或评分项全部完成。

审查人是本批次全新非作者；独立工作树 `D:/wt/r17-graph-app-review1`，分支 `codex/r17-graph-app-review1`。未参与作者实现，未 spawn，未改业务、原测试、gold、状态、锁文件、公共 API 或后端，未 commit/push。仅新增本报告与 `reports/runs/recovery_r17_graph_app_review1_20261016/`，构建产生的本 WT tsbuildinfo 留存后恢复原 HEAD blob。根工作区与后端装配仍由主控持有。

## 固定对象与边界

- 代码：`baa9fa7e024981f8a5516bd840e49910ce7cd1f9`，tree `50e32e6bf86e558d4224e97784f1b942ae1b9a06`。
- 材料：`164cae93ac888180b056a4c694011402ee387383`，tree `207543edfa07f3c9885e6f0c4ecdc75f7560e34e`。作者 raw manifest 本体 SHA256 `7231a79cc2142172dd4c0339483b4100a89fa849ffc7444c2ed7b4c429b97a2b`。
- 合并基础 `b91856eccbba2f660aa434047fbc33ee771a7b7d` 已带原 SVG pointer 修复 `65497b14cb5c24c6d780f675a70af3ee4019d8db`；本审查未用其旧 Ship 代替新 App 检查。
- 后端只读 DTO/路由基准 `08b141bd437c1de70a8435a1f7f6c448a131ed0d`，`D:/wt/r10-graph-fix2` 两源码没有工作树差异，并以 `git show` 留存固定 blob。该后端另行独立复审中的状态不在此转为通过。

已读 AGENTS、00 执行图、12 恢复卡 R17、05 API、task_state 的 R17 partial 状态、CR-R17_graph_default_app、CR-R17_graph_edge_selection、作者 R17-graph-app/graph-ui-fix1/设计报告。使用新版 Ponytail 5.2 review；按团队授权浏览器的一次用户交互、最多 200 节点/400 边判断规模，没有把 fixture 小图当作后台吞吐测试。

生产改动恰为四文件：`frontend/src/App.tsx`、`frontend/src/app/workspace-navigation.ts`、`frontend/src/features/events/event-workspace.tsx`、`frontend/src/features/graph/graph-contracts.ts`。直属作者验证是 App/hash 新测试、graph-contracts 的 1.2 阳性与未知 1.3 负例，以及六场景 fixture e2e；原未知 schema/边规则负例仍存在。没有修改公共 schema、认证或指标分母，也没有 zip 两个证据版本数组。

## 实际调用链核对

默认 `main.tsx → App → AuthProvider → Workbench` 读取 hash。`readGraphSelection` 的完整锚点只接受一个 UUID，App 与 `readWorkspacePage` 是实际调用者；额外 query、URL、非法路径不触发图读取。`#graph` 无 ID 不请求业务图，只显示选择事件与情报列表入口。详情按钮位于 detail loaded 分支，路径使用经过事件服务标识一致性检查的事件 UUID。

图组件真实调用 `getEventGraph → fetchJson`，请求是 `GET /v1/events/{uuid}/graph?max_nodes=200&max_edges=400`；原客户端携带同源 Cookie、no-store、超时和 AbortSignal。App 上下文 key 包含 user、tenant、permission_version、data_mode、sessionGeneration；组件代次核验/取消阻止旧响应恢复，401 清除认证，403/404/409 清除已显示图。模式只取严格解析的认证响应，图 DTO 不自造 live 字段。

原文入口是 `#events/{event}/evidence/{span}`，实际请求仅 `GET /v1/evidence/{span}`；服务返回实际 revision 并展示。图的 `evidence_span_ids` 和 `source_revision_ids` 独立显示，未猜版本、未添加 revision HTTP query。本独立 fixture 还反转两条修订数组顺序、一条 span，仍打开服务给定的历史 revision。

规则类型与 runtime parser 都是精确 1.0/1.1/1.2 联合；schema2、未知快照 rule1.3、未知 edge rule1.3 均拒绝。后端固定 DTO 的 schema1/rule1.2、字段和限额一致。这是兼容边界核对，不是关系语义或引用支持准确率背书。

独立 CBM portable 索引只覆盖本 SHA 工作树 `frontend/src`，cache `/tmp/dianzi-cbm-r17-graph-app-review1-20261016`、persistence=false；404 nodes/1464 edges，partial0/unusable0，30 测试按 fast 设计排除。独立 schema、architecture、Workbench outbound depth3、readGraphSelection inbound、ruleVersion inbound 均实际成功。hash 入站覆盖 Workbench/readWorkspacePage/App，规则入站覆盖 edge/parseGraphSnapshot/getEventGraph/GraphRequest；两份 rg 输出交叉核对源码及被排除测试的调用者。没有索引 reports、秘密或 holdout。

## 真实命令与结果

全部以下时间为 2026-10-16、+08:00；完整 argv/cwd、原 stdout/stderr 在本 run `commands.jsonl` 与对应日志，最终 CBM 另有独立 `.command.json`。单元子集包含于全量，不能重复相加。

| 命令或检查 | 实际 start–end | exit 与数量 |
|---|---|---|
| `npm ci --offline --ignore-scripts --no-audit`，本 WT frontend | 05:14:56.419–05:15:01.264 | 0，299 包，原锁未改 |
| `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=../reports/runs/recovery_r17_graph_app_review1_20261016/regression.json` | 05:15:23.281–05:15:58.057 | 0，425/425，0 fail/skip；包含本图/App/hash 全部 73 项 |
| `node node_modules/typescript/bin/tsc --noEmit` | 05:15:41.127–05:15:44.186 | 0，strict 保持 |
| `node node_modules/eslint/bin/eslint.js .` | 05:15:44.429–05:15:51.240 | 0 |
| `node C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js run build` | 05:15:51.329–05:15:56.076 | 子命令 0，tsc -b/vite build 成功；首次日志打印器 GBK 编码错误另记下文 |
| `node node_modules/@playwright/test/cli.js test --config ../reports/runs/recovery_r17_graph_app_review1_20261016/playwright.review.config.mjs` | 05:16:39.969–05:16:54.383 | 0，真实 Edge 原六场景 6/6，0 fail/skip/flaky，专用 25619 |
| `node node_modules/@playwright/test/cli.js test --config ../reports/runs/recovery_r17_graph_app_review1_20261016/playwright.independent.config.mjs` | 05:18:23.910–05:18:29.612 | 0，独立 build preview 默认 App 两场景 2/2，0 fail/skip/flaky，25620 |
| 同两场景的资源生命周期复跑，由 `check_lifecycle.py` 监测自身进程树 | 05:19:56.012–05:20:02.663 | 0；仍 2/2，仅重复核验资源退出，不再加两项覆盖；最终完整 JSON 在 browser-independent.json |
| CBM index；最终 schema/architecture/Workbench trace | index 05:15:06.116–05:15:12.375；最终三读 05:22:17.000–05:22:32.937 | 各 0；metadata 与调用链见上述独立记录 |
| CBM hash/规则入站；rg 调用者与版本 | 入站 05:21:14.204–05:21:17.568；rg 05:17:41.239–05:17:41.276 和 05:21:14.347–05:21:14.394 | 各 0 |
| material-audit-final，固定 Git 身份/后端 DTO/路由只读；final-checks | 材料 05:19:45.862–05:20:00.882；保护核验 05:20:56.338–05:20:56.692 | 各 0；111 项原作者 raw、9 源码 Git、全部 LF 一致 |
| `git diff --check baa9fa7^ baa9fa7 -- frontend docs/decisions/CR-R17_graph_default_app.md` | 05:18:44.853–05:18:44.937 | 0 |
| `git diff --check baa9fa7 164cae9 -- reports/runs/recovery_r17_graph_app_20261016` | 05:18:45.022–05:18:45.136 | 2，原 raw 空白诊断保留；不改失败为通过 |

独立实际 bundle 为 59 modules，JS 290457 bytes，SHA256 `7111b25e33af72f6ed8479dad4d76d58b585860184c1c919d3c65b497049872f`；CSS 47593 bytes。含图标题、graph 读路径、过期文案、1.2 和 chooser 标记；10 个 fixture 账号/业务正文 marker 命中总数 0。不是旧未接线 App 的 53modules 构建。

六场景实跑覆盖桌面1366/390详情→图→真实鼠标 chooser→精确边 UUID→原文 GET→刷新→hash back→返回事件；loading、root-only unknown、truncated、409/重取；guest、403、401、logout 清除；legacy/非法租户 hash/未知认证模式/未来版本；旧租户晚到响应隔离。隔离路由与内容明确 Fixture，没有真实账号/API声明。

新增独立 case 使用 dist preview 的产品主路径，从详情按钮进入图，利用 SVG getPointAtLength/getScreenCTM 得到坐标后 `page.mouse.click`，候选按钮同样按真实 bounds 鼠标点击，精确选择 edge `71000000-0000-4000-8000-000000000011`。一 span/两 revision 顺序反转后原文 GET、实际 revision、refresh/back 成功；改成404重读后图场景、旧 inspector、chooser 与旧引文均 0，页面显示“事件不可访问”，未出现“暂无风险”或 Live。另 case 在构建 App 实测三种精确历史规则可读，未知 schema/快照规则/边规则都无旧图。

独立查看本次桌面和390截图：图/关系文字列表/原文链接及规则标识可读，390自身画布滚动，页面无水平溢出；桌面低亮动态背景与390 reduced-motion 均在实跑断言中通过。此项为有限 fixture 截图核查，完整R17人工操作验收仍 not_run。

## 原证据与 raw/Git 区分

author manifest 实际枚举 9 sourceGit + 102 materials = 111 项。作者原工作树 HEAD 正是 164cae9，111 项 raw SHA 全匹配；9 个源码固定 Git LF/blob 全匹配；独立 checkout 的 LF 匹配无差异。独立 checkout raw 有五项因 core.autocrlf 检出 CRLF 与作者 LF raw 不同：CR、e2e、App新测试、hash新测试、任务报告；详细 raw/Git/LF/crlf_count 全列于 material-audit.json，未把 LF 匹配声称 raw 匹配。

作者材料提交的属性仅新增 `reports/runs/recovery_r17_graph_app_20261016/** -text`。足以保全该 run 原始失败/log/PNG 字节，未扩大到源码、未设置 -diff 或关全局空白检查。本审查的 run 内 `.gitattributes` 也仅为该目录的 `* -text`，不改仓库根属性或源检查。

原先红完整保留：graph-contract/hash 29=20pass/9fail；App 11=3pass/8fail；首局部73=72pass/1fail的测试空元素误断言；首 typecheck exit2；首Edge6=2pass/4fail，次Edge6=5pass/1fail，最终6/6。均从 raw JSON/命令核验，不删除/skip/改 gold，原 raw diff exit2 仍可复现。

审查工具自身的限制也保留：首次 build 的实际子命令 exit0，但 Python打印器遇到 GBK不能输出“✓”退出1，stdout/stderr与真实子命令 receipt 已先落盘，随后仅改打印编码。少量预读误路径、一次默认GBK读JSON和一次 PowerShell引号预检错误不计业务失败。三条首次并行CBM的 Windows append 交错导致本审查 commands 第6行失效，原字节在 commands.initial.raw.jsonl、原CBM stdout/stderr不改；保留其余有效记录后将三读顺序实跑为 final，并新增每命令独立receipt，未编造丢失记录。资源复跑最终JSON覆盖本审查第一次独立JSON，第一次实际stdout/receipt仍保留；报告以最终完整JSON核对同两case，未额外计分。

进程核验：原六场景 node30444/worker46352、首次preview32088/worker42924均已退出；本次最终观测自身完整子进程树22个身份（含msedge/browser children）全退出，survivors0、25619/25620 listener0，见 process-lifecycle.json/final-checks.json。没有接入用户IAB/CNNVD标签，没有运行下载PoC、付费模型、第三方扫描或生产写操作。

本新报告与 `/dev/null` 的 no-index diff check 在05:24:18.654–05:24:18.709 exit1（新增文件有差异，stdout没有空白诊断，stderr仅LF/CRLF提示）；不把这个exit写成0。05:24:18.779–05:24:18.835实际 check-attr exit0确认审查run为text unset，两个被审源码的text/diff/whitespace均 unspecified，没有扩大豁免。

## 缺口、评分映射与下一步

本切片的 Must fix 为0，没有触发输入、错误行或最小修复需要提出；没有可证实的非阻断代码简化建议。未检查的真实后端接线、PG认证/快照事务竞态、关系支持准确率、外部live、持续运行、正式性能与完整R17/G-E验收应保持 not_run。前端有界独立审查可以成立，不能用本fixture替代这些验收。

覆盖证据只映射 D2/R17:T41 的默认图与原文互跳、错误与权限清除、窄屏操作，以及 E1 的本前端输入/会话边界。下一任务建议是主控结合后端08b正式复审结果，按其所有权接线默认后端App，再执行真实PG/API认证→详情→图→证据及撤权/过期联测。独立前端 Ship 不提升整卡、阶段门或分数。

本审查自己的 manifest、report SHA 见本 run `artifact_manifest.json`、`artifact_manifest.sha256`、`report.sha256`；不在报告内部嵌入会自循环的报告 SHA。根进度未写 accepted。

Not checked: 真实默认后端/API/PG integration 与 live、完整R17人工/阶段门、关系准确率和正式性能。
