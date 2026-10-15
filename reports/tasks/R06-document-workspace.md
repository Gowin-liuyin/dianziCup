# R06 / R17 资料工作台前端切片

状态：awaiting_review；implementation=complete（仅此前端切片）；unit=passed、contract=passed、frontend=passed、e2e=passed（显式隔离 fixture）；integration/live=not_run（待主控真实 API 接通与复跑）；manual=passed（本机生成截图视觉审查，非最终人工验收）。整 R06/R09/R17 仍 partial，不签 accepted。

作者：r06_document_workspace。工作树 D:/dianzi-worktrees/r06-document-workspace，分支 codex/r06-document-workspace，基线 1ca2ea34c224e23776431fa6eac5fe6549d8c65f。没有提交后端、锁文件、共享 schema、progress 或主树未提交日志；没有 push。

源码冻结：aa17db32c314555363bb4bca3105c2b434939b29。source_freeze.json 记录该commit所改源码/设计的 Git blob、实际工作树SHA256与字节数；后续元数据提交不改源码。主控可 cherry-pick 此源码提交及紧随元数据提交，不需复制整个工作树。

## 实现和调用方

新增研究导航「资料库」，已有登录/来源/问答及 hash 深链保留。资料标题关键词、六类文档/八来源类别筛选、opaque cursor 下一页与回首页；列表仅显示本页数量。详情读取所选版本标题、四来源时间、日期精度、许可、覆盖范围与 source_notes。版本历史分页可加载后续版本；正文使用原 EvidenceResponse，后续证据请求固定首次响应 revision_id，去重/归属/模式/不前进游标异常拒绝，换版本卸载旧正文。

标题、原文、许可、来源说明均 React text；仅被冻结并严格校验的 canonical_uri / license_uri 出站链接（HTTPS、无 userinfo/fragment/敏感 query），不显示或执行任意 metadata 链接。没有任意 URL 读取、写操作、付费任务、模型调用或产品 fixture fallback。当前/历史、全文/摘要/片段/metadata/unknown 与解析状态分别展示；没有证据不标确认风险。

复用 fetchJson（Cookie include / no-store / timeout / 原problem）、AuthProvider sessionGeneration/isSessionCurrent/expireSession、formatShanghaiTimestamp、原 EvidenceResponse parser 与统一 ErrorPanel/EmptyState/StatusBadge。最小必要新增为 document-contracts、document-client、资料工作区/局部CSS、导航深链与对应隔离测试；未加框架或依赖。CBM baseline src-only 独立cache图232节点/822边，fetchJson入站21调用方、readWorkspacePage入站2调用方，rg复核 App/导航/capability类型调用处；日志 cbm_fetch_callers.json / cbm_navigation_callers.json。CBM初次schema无project报错后已读取项目schema，未索引秘密/holdout。

改动文件：

- frontend/src/App.tsx；frontend/src/app/workspace-navigation.ts 与 .test.ts；frontend/src/features/preparation/capability-workspace.tsx（排除documents类型）。
- frontend/src/api/document-contracts.ts 与 .test.ts；frontend/src/api/document-client.ts 与 .test.ts。
- frontend/src/features/documents/document-workspace.tsx 与 .test.tsx；documents.css。
- frontend/tests/document-fixture.ts（仅测试）；frontend/e2e/r06_document_workspace_fixture.spec.ts；frontend/playwright.documents.config.ts。
- docs/design/recovery/r06_document_workspace.md；本报告；reports/runs/recovery_r06_document_workspace_20261015/。

冻结输入：合同文档 0b9cd13013ac2020c15e077b12016c630eeb3667、实际 Pydantic 225c0fcd501d85d355513a44308083407b18bb2a；直接读取主控工作树，未整体 cherry-pick 后端。日期精度、字段上限与安全URL均逐项对齐。没有公共合同、权限、指标分母、计划或评分阈值变更。

## 真实检查

工作目录 frontend；Node v24.13.1、npm11.8.0；复用主树已安装 node_modules 的本地 junction（未改依赖）。绝对日志根：D:/dianzi-worktrees/r06-document-workspace/reports/runs/recovery_r06_document_workspace_20261015/，每条命令起止与退出码在 commands.jsonl。

| 命令 | 实际结果 | 日志 |
|---|---|---|
| npm test -- --reporter=json --outputFile=../reports/runs/recovery_r06_document_workspace_20261015/initial_contract_tests.json src/api/document-contracts.test.ts | exit1，模块尚未实现；环境可运行，非业务失败 | initial_contract_tests.json/.log |
| npm test -- --reporter=json --outputFile=../reports/runs/recovery_r06_document_workspace_20261015/unit_delivery.json | 295/295，20文件，0失败/skip；包含既有auth/source/question回归 | unit_delivery.json/.log |
| npm run lint | 最终exit0；首次exit1为测试未用参数，修复后重跑 | lint.log、lint_recheck.log、lint_delivery.log |
| npm run typecheck | 最终exit0；首次exit2，record返回类型未narrow，修为type guard后重跑 | typecheck_initial.log、typecheck.log、typecheck_delivery.log |
| npm run build | exit0，tsc -b和Vite成功，无依赖变动 | build.log、build_delivery.log |
| DIANZI_E2E_FRONTEND_URL=http://127.0.0.1:25376 node node_modules/@playwright/test/cli.js test --config=playwright.documents.config.ts | Edge 4/4，0失败/skip/flaky；服务由Playwright独占启动/关闭；所有/v1请求测试内显式拦截 | e2e_report.json、e2e_delivery.log |

主要最终时间窗（+08:00）：unit 19:39:21.8776787–19:39:47.4573030；lint/typecheck/build顺序执行19:39:21.8040969–19:39:37.6152329；browser19:39:21.8882061–19:39:33.1334992。此前 unit_frozen/e2e_frozen 等中间记录仍保留。截图最终版本已重新实际查看，四来源时间全部可见。

冻结源码/设计/任务报告的 `git diff --check aa17db32^ aa17db32 -- frontend docs/design/recovery/r06_document_workspace.md reports/tasks/R06-document-workspace.md` 实际exit0，见source_diff_check.log。若对整个证据包检查，原生 Playwright 失败日志与error-context.md含trailing whitespace，因此整包check会非零；原日志不清洗、不改工具输出，未添加忽略规则。生成的tsconfig.tsbuildinfo已恢复基线字节，编译产物不进入源码差异。

默认browser首跑exit1，3项均缺 Chromium headless1248执行文件，保留e2e_missing_browser_report.json/e2e_first.log，不算业务失败/skip。改用本机Edge后首轮1过2失败；e2e_edge_first_report.json、e2e_edge_first_artifacts/、e2e_edge.log保留。1366 exact-label缺陷用显式 aria-label 修复；夹具换状态需reload而非同页hash，修正后四项全跑通过，没有删题/降门槛。测试日志目录第一次相对路径建错导致npm未执行，随后重建正确日志根并记录实际运行；误建空目录与junction已核对完整绝对路径后删除，未操作目标 node_modules 内容。

测试覆盖：strict schema字段/枚举/数量/日期精度/恶意URL，GET输入过滤与ID验证，跨文档/版本/模式响应，非前进offset，分页、空、403/404/503、metadata无正文、HTML/script注入文本、401清身份和退出后的晚到响应。浏览器1366×900及390×900键盘Enter/Space、focus、Range x坐标、页面scrollWidth、reduced-motion=none及装饰pointer-events:none有实际断言。

截图实际已查看（合成 Fixture，不计live）：

- e2e_artifacts/r06_document_workspace_fix-d2f71-ry-evidence-keyboard-layout/document-isolated-fixture-1366.png。
- e2e_artifacts/r06_document_workspace_fix-76e0f-ry-evidence-keyboard-layout/document-isolated-fixture-390.png。

## 未执行、评分证据与交接

真实 PostgreSQL 资料 GET、真实来源→资料→browser 链路由主控集成后运行，本工作树未访问真实凭据/数据，不声称live通过。资料切片不能代替R09机制知识卡、R16更新重判或整R17验收。历史切换会重新读取历史列表第一页，当前检视修订仍保留并可继续加载更多；不声称列表已完整。资料仅支持标题关键词，不声称正文语义检索。

F1/R1：资料分类与明确正文覆盖/日期精度；F2/F3：指定revision原文与永久定位核查入口；D2：中文列表/详情/历史/窄屏/键盘/错误状态；E1：统一认证、严格投影、不执行原文、无产品fixture成功。均为本切片代码/隔离证据，不上推全部评分项通过。

建议下一步：主控集成源码冻结后，使用专用真实PG/API会话复跑资料列表→历史→证据与权限负例，再交独立审查；progress由主控登记 awaiting_review。未经独立复跑，不accepted、不跨阶段。

## 独立初审两项 Must 修复（2026-10-15 第二轮）

第二轮源码冻结：e492a8fb6b58465c60cf3b355caacbd077483967，基于475f71e48f93e9888dfcf09954a7ce13e590add5。两个改动源码的Git blob / SHA256 / 字节数与检查计数见review_fix_1_source_freeze.json。第二轮源码/设计/报告`git diff --check`实际exit0。此处补元数据不改源码。

状态仍 awaiting_review，待原独立 reviewer 定向复核；本文作者复跑独立用例不等于独立验收。原 aa17db32/475f71e 冻结、原295/4browser和全部失败报告均保留。

初审确认：①已取得正文后历史分页403/404只隐藏history，旧正文仍展示；②初始当前地址在证据分页期间变历史，当前链接仍为相同hash，点击没有新GET。根因是detail/history只有各自错误状态，以及hash被用作唯一重读触发。

修复范围仅 `frontend/src/features/documents/document-workspace.tsx`、新增 `document-recovery.test.tsx`、本报告/设计及自有run日志。detail与history共享资料读取代次和AbortController集合：任一403/404先提升代次并取消全部读取，再清detail/evidence/history、加载/partial错误状态；父工作区清列表快照并提升独立list代次，晚到成功不能恢复标题/数量/正文。503后续页保持已取得的部分内容和未完整说明，未改为权限丢失。当前链接显式取消旧请求、重挂检视区、reset所选revision/正文/历史分页并重新GET不带revision_id的当前版本；同hash也执行读取。普通临时详情失败仍重试原已选版本。

先固定读取独立测试，输入SHA256见review_fix_1_inputs.json：review.test.ts=aa85efb493e10b02beb0f8037581cb1426d02c6e8e175b14cb9914b70a314749；review.browser.spec.ts=e79bc1c9034770e4cfd30b81598d390eb910bd67875b086adad84c426cbae13e。原样复制到自有run目录；只调整自用config的include/testMatch/cwd/loopback端口/输出目录，测试断言与fixture字节不改。独立 reviewer 原目录未写入。

红→绿真实结果：

| 自用命令 / 用例 | 修复前 | 末版 | 日志前缀（同run目录） |
|---|---|---|---|
| `node node_modules/vitest/vitest.mjs run --config=../reports/runs/recovery_r06_document_workspace_20261015/review_fix_1.vitest.config.ts --reporter=json --outputFile=...` | exit1，36中34过2失败 | exit0，36/36，0skip | review_fix_1_unit_red / unit_final |
| `node node_modules/@playwright/test/cli.js test --config=../reports/runs/recovery_r06_document_workspace_20261015/review_fix_1.playwright.config.ts`，独占25377 Edge | exit1，6中3过3失败 | exit0，6/6，0skip/flaky | review_fix_1_browser_red / browser_final |
| `npm test -- ... src/features/documents/document-recovery.test.tsx`，新增永久回归 | exit1，4中1过3失败 | exit0，4/4 | review_fix_1_regression_red / regression_green |
| `npm test -- --reporter=json --outputFile=../reports/runs/recovery_r06_document_workspace_20261015/review_fix_1_full_unit_delivery.json` | 原295测试保留 | exit0，299/299，21文件0skip | review_fix_1_full_unit_delivery |
| `npm run lint` / `npm run typecheck` / `npm run build` | 首轮lint有2 ref-cleanup warning（exit0） | 捕获effect局部Set后全exit0，0warning | review_fix_1_lint/typecheck/build_delivery |
| 原 `playwright.documents.config.ts`，独占25376 Edge | 原四项不删改 | exit0，4/4，0skip/flaky | review_fix_1_original_browser_delivery |

每条完整参数/真实起止/exit见追加commands.jsonl；上表`...`仅为报告省略日志输出参数，不是未执行命令。原样copies与红绿JSON/失败message均保留。新增永久回归包含403/404后已在途证据晚到、catalog/title/history清空，503部分保留及同hash当前新GET。六browser也覆盖新版本后旧证据丢弃、退出→重新登录→刷新时旧会话晚到结果不复活、390长title/license/notes/raw日期注入与动效开关。未伪造live或将失败改skip。

末版真实时间窗（+08:00）：独立36unit20:04:54.6298737–20:04:56.7733704；独立6browser20:04:54.6298737–20:05:02.0550406；原4browser20:05:39.8184006–20:05:48.1506510；lint/typecheck/build20:05:39.8711446–20:05:50.2211009；299unit20:05:39.8711118–20:05:59.9377796。CBM本次新增src索引后的DocumentInspector入站确认DocumentWorkspace（1跳）与App.Workbench（2跳），均lsp0.95，rg调用日志复核；此前baseline图保留，不把图当测试通过。原独立assert文件copies末次hash仍一致，见review_fix_1_copy_hashes.json。

实际查看修复截图：history-403-stale.png中资料列表已清除且检视区仅有无权限；current-link-stale.png中已出现新当前revision3/原文，无旧版正文。文件名来自原独立测试，不代表修复后仍stale。截图在review_fix_1_browser_artifacts/。源码/文档diff检查仅排除原生日志，不清洗原工具输出；末版源冻结随后登记。下一步由原独立reviewer对新SHA复核，真实资料API/browser依旧由主控接续，不自行accepted。

## 定向复核 Must 3 修复（第三轮，基线 ef3a058）

第三轮源码冻结：2f5c7ef225ce2d29da2438a4d5caa51cdc6a9231，基于ef3a0583179a27ccdaca05b771afccc90429dc35；四个frontend改动的Git blob/SHA256/字节及结果在review_fix_2_source_freeze.json，源码/人工文档diff check exit0。其后仅补元数据，代码不变。

原独立复核已关闭 Must 1/2，并在直接deep-link列表先403、detail/history在途200的相邻路径确认Must 3。作者读取主控原报告并复现，不改独立测试或已关闭结论。状态awaiting_review，仍待同一独立reviewer复核。

最小修复把原Inspector的generation与AbortController集合提升至资料工作区单个私有READ_PUBLIC读取scope，list/detail/history共同使用；无新全局state/框架/公共合同。list403或401同步提高scope代次并取消全部资料请求、清selection且卸载旧Inspector状态；401继续清会话。详情/历史403/404仍按原修复清缓存，晚到list也被scope/目录代次挡住。503及列表404待接通保持各自查询失败语义，不统一清空或伪造零结果。搜索、下一页、回第一页、重试统一经queryDocuments取消旧scope再清检视/换过滤，补回第一页原来未清Inspector的相邻路径。

改动仅document-workspace.tsx、永久document-scope.test.tsx、永久r06_document_scope_fixture.spec.ts、原专用Playwright config的testMatch（原4保留，新增4），以及自有报告/设计/run。无backend、认证/DTO、锁、progress、金标、分母变更，无push/accepted。

独立新输入已固定hash：catalog_privacy.test.ts=e1df2ef900bf6a277b381b0781d56359259d670a5906a88b3761d7a434a763ab；catalog_privacy.browser.spec.ts=092bedcad878acbe66428c6a8ab2e5851318c573b40e8b5a54c0b3ce3bc1734b；七竞态recheck.race.test.ts=c77c4767106618dc02198a0fc82c9ad3095456f688ac1168ee976e7811b52fb1。自用copy字节原样，config仅更换include/cwd/loopback端口/输出，见review_fix_2_inputs.json。原独立目录未写。

| 实际检查（完整命令/时间/exit在commands.jsonl） | 结果 | 文件前缀 |
|---|---|---|
| 独立catalog原样单元 | 修前exit1，1红；修后exit0，1/1 | review_fix_2_catalog_red / catalog_green |
| 永久scope单元 | 修前6中4过2红（初轮403与回第一页取消）；修后6/6，另含原4修复回归合跑10/10 | review_fix_2_scope_red / scope_green |
| 原样相邻七竞态 / 原36单元 | exit0，7/7及36/36，0skip | review_fix_2_race_green / original_unit |
| 全前端npm test JSON | exit0，305/305，22文件0skip（原299保留+6） | review_fix_2_full_unit |
| lint / typecheck / build | 全exit0，lint0warning | review_fix_2_lint / typecheck / build |
| 原4+永久scope4 Edge，独占25376 | exit0，8/8，0skip/flaky | review_fix_2_browser_delivery |
| 原样独立6 Edge，独占25377 | exit0，6/6，0skip/flaky | review_fix_2_original_browser |

永久Edge直接验证：403/401错误出现后待完成两类请求实际requestfailed取消，释放全部barrier并等实际已启动handler完成，再断言标题/正文/source链接/历史控件为0；分页同样覆盖。503对照保留查询失败与合法已取得详情，绝不显示零记录。实际查看catalog-403-scope-cleared.png，右侧已卸载成通用核查提示，左侧无记录标题/数量。每轮的截图与原失败日志均保留，不宣称live。

独立新browser probe在release后先要求漏洞原文toBeVisible，再要求count0：修前可复现泄漏，正确修后原文永不出现，因此原样修后在toBeVisible前置超时。已向主控逐条报告，主控明确认可保留该仪器失败而用有效unit与永久Edge检查；不改原文件、不断言为产品仍失败，也不声称该probe绿色。原样前后exit1及JSON均保留在review_fix_2_browser_red.json / browser_raw_after_fix.json，原reviewer需修其probe再复核。

作者永久Edge首轮把StrictMode的实际4个handler硬写成2，造成4红；改为核对实际started/settled数量后保留原红日志。第二轮有403业务红、分页fixture按次数允许首页导致StrictMode误拒绝的仪器红；改为按有无cursor识别真正分页请求，0skip，最终4/4。没有降低权限取消或不可见断言，也未改独立断言；原scope_browser_red、red_valid及两套artifacts完整保留。

真实时间窗（+08:00）：质量/305unit20:31:13.1192399–20:31:42.3322160；8Edge20:31:13.1892050–20:31:23.7955812；原独立6Edge20:33:53.9562902–20:34:00.1714983。来源实际PG/API/browser/live仍not_run。主控用新源码和元数据提交交原reviewer复核，本作者不accepted、结束此修复切片。
