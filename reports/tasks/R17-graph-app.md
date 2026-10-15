# R17 默认工作台的事件证据图接线

本切片状态 `awaiting_review`、实现 `complete`；仅在 G-C 安全独立推进准备，不计 G-E 过门。完整 R17 仍 `partial`。unit/contract/frontend 检查 `passed`；browser integration `passed` 仅隔离 HTTP fixture；真实 PG/API integration、live、独立 manual 均 `not_run`，不签 accepted，不 push。

工作树 `D:/wt/r17-graph-app`，分支 `codex/r17-graph-app`，基线 `136fbaef337036d95229aa4976c1ba49b2e6b04c`。按主控授权以 `--no-ff` 合并原图 SVG 指针切片 `65497b14cb5c24c6d780f675a70af3ee4019d8db`，合并提交 `b91856eccbba2f660aa434047fbc33ee771a7b7d`，无冲突。当前代码冻结 `baa9fa7e024981f8a5516bd840e49910ce7cd1f9`，tree `50e32e6bf86e558d4224e97784f1b942ae1b9a06`。后续材料提交与代码提交区分，材料清单见本 run 的 `artifact_manifest.json` 和 `artifact_manifest.sha256`。

已核对 AGENTS、00 执行图、R17 恢复卡、05 API、现有 AuthProvider/hash 路由与 graph DTO、R17-graph-ui-fix1 和 CR-R17_graph_edge_selection。后端只读对照 `D:/wt/r10-graph-fix2` 固定 `08b141bd437c1de70a8435a1f7f6c448a131ed0d`，源码实际位置 `knowledge/evidence_graph.py` 与 `api/graph_routes.py`，schema1/规则 1.2；该后端仍待原 reviewer 复核，本文不以可读源码宣称 accepted 或真实服务通过。

## 修改、输入输出与范围

生产只改主控确认的四文件：`frontend/src/App.tsx` 注册图组件；`frontend/src/app/workspace-navigation.ts` 精确解析事件图 hash；`frontend/src/features/events/event-workspace.tsx` 仅在 detail loaded 时提供图入口；`frontend/src/features/graph/graph-contracts.ts` 精确增加 1.2 union。没有改 GraphExplorerView 几何选择、共享 schema、后端、认证、其他业务页面、锁文件、全局 CSS 或 progress。

直属验证文件：新 `frontend/src/App.graph.test.tsx`、`frontend/src/app/workspace-graph-navigation.test.ts`、`frontend/e2e/r17_graph_app_fixture.spec.ts`，以及 graph-contracts.test.ts 中新增 1.2 阳性、将未来版本负例更新为未知 1.3。旧负例保护仍在，未删除难例、改金标/分母或降门槛。决定见 `docs/decisions/CR-R17_graph_default_app.md`；自有材料范围是 `reports/runs/recovery_r17_graph_app_20261016/`、本报告。仅该 run 的 `.gitattributes -text` 规则保全 raw 字节，不忽略空白检查，不加入全局 ignores。

输入：团队认证上下文、事件 UUID 和服务端 schema1 快照。输出：`#graph/{event_uuid}` 的证据关系图；`#graph` 无事件时显示可解释入口；非法 URL、后缀、租户查询串和 UUID 均不发图请求。详情入口 → 图 → 同一事件/原文的浏览器 hash 返回和刷新均保持对象标识。

真实产品请求代码沿用默认 AuthProvider 与 fetchJson：`GET /v1/events/{event_uuid}/graph?max_nodes=200&max_edges=400`。前端不接受 URL/租户查询、不建立图缓存；App 会话 key 包含 user/tenant/permission_version/data_mode/sessionGeneration，图原组件捕获认证代次并取消旧请求。GraphSnapshot 没有模式字段，页面模式只取已校验认证响应，未确认时显示未知，不由 HTTP200/动画推断 Live。

图证据链接沿用 `#events/{event_uuid}/evidence/{span_uuid}`，实际 HTTP 只有 `GET /v1/evidence/{span_uuid}`。服务返回实际 revision 和定位；显式历史 hash 的 expectedRevisionId 仅做客户端一致性核验，不能自造 HTTP revision query。图 DTO 的证据/修订数组没有映射合同，测试使用一条 span 对两条 revision，未 zip 配对或猜测版本。

schema1 精确兼容 1.0/1.1/1.2；节点/边/证据/字段校验、有界200/400、未来未知 rule/edge version fail closed 均保留。1.2 当前元数据不代表关系生成准确率已通过。原图的真实 Mouse 候选选择、动态背景、reduced-motion 与文本关系列表复用。沿用深绿工业安全终端；Ponytail 5.2 full/review 自查沿 callers/输入/清除路径，没有新增框架或依赖。外部只参考 [Carbon 网络图](https://v10.carbondesignsystem.com/data-visualization/complex-charts/) 与 [可访问交互](https://www.carbondesignsystem.com/building-blocks/foundations/accessibility/developers)，网页作为参考数据。

## 实际验证与旧失败

完整 argv/cwd/真实毫秒级 start/end（+08:00）/exit 位于 `commands.jsonl`，各 stdout/stderr 和 JSON 独立命名。命令 cwd：前端测试/静态/build 为本 WT `frontend`；CBM/git/rg 为 WT 根。现有 Node24、原锁包离线 `npm ci --offline --ignore-scripts --no-audit` exit0；没有下载浏览器、调用模型、访问模型 vault 或创建真实用户账号。

| 检查与实际命令 | 真实结果 |
|---|---|
| `node node_modules/vitest/vitest.mjs run src/App.graph.test.tsx src/app/workspace-graph-navigation.test.ts src/features/graph --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=.../graph-app-unit.corrected.json` | 05:03:07.706–05:03:16.874，exit0，73/73、0fail/skip；其中新 App11、hash8、1.2版本1及原 graph53 |
| `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=.../regression.frozen.json` | 固定 baa9 后 05:07:48.995–05:08:19.544，exit0，425/425、0fail/skip；子集不重复相加 |
| `node node_modules/typescript/bin/tsc --noEmit`、`node node_modules/eslint/bin/eslint.js .`、`node node_modules/typescript/bin/tsc -b`、`node node_modules/vite/bin/vite.js build` | 最终 05:06:53.589–05:07:03.836，各 exit0。产品与最终 e2e 文件在之后代码提交中原字节不再修改 |
| `node node_modules/@playwright/test/cli.js test --config ../reports/runs/recovery_r17_graph_app_20261016/playwright.release.config.mjs` | 05:06:53.567–05:07:02.939，exit0，真实本机 Edge/msedge、1worker、6/6、0fail/skip/flaky；8.763288秒是此六 case 单次 duration，不是性能指标 |
| 默认 Vite build 与 `bundle-proof.json` | 实际59modules；JS290.46kB/gzip89.16kB、CSS47.59kB/gzip9.54kB。包含图标题、graph路径、409状态、1.2规则；合成业务正文及 fixture账号 marker 未入产品bundle，不沿用旧未接线53modules结论 |
| 官方 CBM portable 0.11.0 index/schema/architecture/trace + rg | 各成功命令 exit0；初403nodes/1458edges → 固定404/1464，partial0/unusable0。30测试文件按fast设计排除。独立 `/tmp/dianzi-cbm-r17-graph-app-20261016` cache、root仅本 WT frontend/src、persistence=false；不索引 reports/秘密/holdout、不提交cache |

真实六场景包含：1366/390 的默认 App 详情→图→原生 Mouse 曲线/候选按钮→精确 edge UUID→原文片段/实际 revision→刷新→hash back→返回事件；loading、root-only空支持关系和六项未知、truncated部分图、409清除与重取；guest不发业务请求、403清除、401失效、退出后返回图无旧数据；legacy入口、非法租户后缀、未知认证模式和未来图版本拒绝；旧 A 租户挂起响应在 B 会话恢复后不能覆盖 B 当前图。fixture路由限定前端e2e，认证/业务材料明确 Fixture，没有假 Live/静态成功。

原 Mouse 坐标来自 SVGPathElement.getPointAtLength/getScreenCTM，执行 `page.mouse.click`；候选按钮也以真实 boundingBox 点击，并断言 edge `71000000-0000-4000-8000-000000000011`。没有 force/dispatch 到遮挡 path。390 图与事件页均检查无页面水平溢出，图仅在自身画布滚动；动态图桌面 topology-drift、390 reduced-motion none 真实检查。作者查看最终桌面/390截图，图与关系文本、版本和原文入口可读；该观察不替代独立 manual。

全部先红与试跑材料保留原字节：合同/hash红29项20pass/9fail；App红11项3pass/8fail，缺入口与路由尚不存在；首局部73项72pass/1fail是本测试误用 getByText 断言空元素；首 typecheck exit2 为 Testing Library 的 ByRoleOptions 不支持 `exact`，修正测试后重跑成功。首 Edge 6项2pass/4fail：引用accessible name含空格、B节点标题两处匹配、仅改变hash没有重读认证；第二轮5pass/1fail是先从已有合法会话进入有效hash再reload导致请求总日志仍含合法旧请求。修正测试顺序为先重读未知认证再改hash，未改产品鉴权；第三轮原六case全部通过。第一、二轮fixture源码快照和 raw JSON/error-context/截图保存，不改 fail 为 skip。

少量预读命令试探了不存在的 `backend/src/ai_intel/graph` 路径、一次 PowerShell `.Substring` 语法错误、首次未引用 `HEAD^{tree}` 导致 Git 参数失败、首次端口输出误用 frontend 相对 reports 路径；随后使用实际 knowledge 路径/正确引用/绝对路径。它们是工具预检错误，不计业务测试失败；这些最早对话工具输出未逐条封存，因此不把它们算入 commands.jsonl 成功数量。

构建只改变本 WT 的 tsbuildinfo，生成副本存本 run 后恢复当前 HEAD 原 blob；D:/dianzi 主工作区用户 tsbuildinfo 与其他未提交文件未写入。专用25517由 Playwright启动/关闭，reuseExistingServer=false；`process-after-release.json` 实测 listener0，原 Vite24356、release Vite34124/worker19440均已退出，没有登录用户 IAB 或操作其标签。

源码/CR定向 diff check passed；全部 raw staged diff check 实际 exit2，包含保留的red error-context/stdout尾空格、schema输出空行与 CRLF 原日志字节。该材料空白问题与业务检查分开，未改字节或加 ignore 凑绿。manifest分别记录工作树 raw SHA256、LF文本 SHA256与 sourceGit 的 LF blob/代码SHA，sourceGit不冒充raw。生产bundle证据仅冻结内容hash，不提交dist或把build当live。

评分证据：D2/R17:T41 的默认前端图与引用互跳、错误/未知/过期/权限清除和窄屏操作；E1 是本前端输入与旧会话内容清除边界。未测新关系生成准确率、真实PG/API认证/快照竞态、外部live、完整R17、全量G-E或独立人工验收。无费用、模型、扫描或生产写操作。

下一步：主控交给新的独立 reviewer 固定 baa9、manifest及最终6case复核，再与已冻结后端装配真实PG/API联测；对应后端仍由原 reviewer 复核。真实联测未完成前不提升accepted/阶段门。
