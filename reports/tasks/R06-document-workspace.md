# R06 / R17 资料工作台前端切片

状态：awaiting_review；implementation=complete（仅此前端切片）；unit=passed、contract=passed、frontend=passed、e2e=passed（显式隔离 fixture）；integration/live=not_run（待主控真实 API 接通与复跑）；manual=passed（本机生成截图视觉审查，非最终人工验收）。整 R06/R09/R17 仍 partial，不签 accepted。

作者：r06_document_workspace。工作树 D:/dianzi-worktrees/r06-document-workspace，分支 codex/r06-document-workspace，基线 1ca2ea34c224e23776431fa6eac5fe6549d8c65f。没有提交后端、锁文件、共享 schema、progress 或主树未提交日志；没有 push。

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

默认browser首跑exit1，3项均缺 Chromium headless1248执行文件，保留e2e_missing_browser_report.json/e2e_first.log，不算业务失败/skip。改用本机Edge后首轮1过2失败；e2e_edge_first_report.json、e2e_edge_first_artifacts/、e2e_edge.log保留。1366 exact-label缺陷用显式 aria-label 修复；夹具换状态需reload而非同页hash，修正后四项全跑通过，没有删题/降门槛。测试日志目录第一次相对路径建错导致npm未执行，随后重建正确日志根并记录实际运行；误建空目录与junction已核对完整绝对路径后删除，未操作目标 node_modules 内容。

测试覆盖：strict schema字段/枚举/数量/日期精度/恶意URL，GET输入过滤与ID验证，跨文档/版本/模式响应，非前进offset，分页、空、403/404/503、metadata无正文、HTML/script注入文本、401清身份和退出后的晚到响应。浏览器1366×900及390×900键盘Enter/Space、focus、Range x坐标、页面scrollWidth、reduced-motion=none及装饰pointer-events:none有实际断言。

截图实际已查看（合成 Fixture，不计live）：

- e2e_artifacts/r06_document_workspace_fix-d2f71-ry-evidence-keyboard-layout/document-isolated-fixture-1366.png。
- e2e_artifacts/r06_document_workspace_fix-76e0f-ry-evidence-keyboard-layout/document-isolated-fixture-390.png。

## 未执行、评分证据与交接

真实 PostgreSQL 资料 GET、真实来源→资料→browser 链路由主控集成后运行，本工作树未访问真实凭据/数据，不声称live通过。资料切片不能代替R09机制知识卡、R16更新重判或整R17验收。历史切换会重新读取历史列表第一页，当前检视修订仍保留并可继续加载更多；不声称列表已完整。资料仅支持标题关键词，不声称正文语义检索。

F1/R1：资料分类与明确正文覆盖/日期精度；F2/F3：指定revision原文与永久定位核查入口；D2：中文列表/详情/历史/窄屏/键盘/错误状态；E1：统一认证、严格投影、不执行原文、无产品fixture成功。均为本切片代码/隔离证据，不上推全部评分项通过。

建议下一步：主控集成源码冻结后，使用专用真实PG/API会话复跑资料列表→历史→证据与权限负例，再交独立审查；progress由主控登记 awaiting_review。未经独立复跑，不accepted、不跨阶段。
