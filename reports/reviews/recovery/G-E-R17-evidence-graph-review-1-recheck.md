# G-E / R17 证据图前端 · 原 pointer Must 定向复核

What this change does: 修复在真实指针位置计算邻近曲线，重叠时展示明确的关系选择区，由用户确认方向和依据。原曲线、DTO、认证、原文hash路由和工作台样式保持；图中关系不再由最后绘制的透明路径默选。

**限定结论：原初审 Must 1 关闭，当前 pointer 修复切片 Ship。** 未发现新的 Must；不将完整 R17 / G-E 写成 accepted，不把隔离fixture算作后端/live。review SHA=`none`，未提交/未push；主控可以据此合入本pointer切片，真实后端和App接线仍是后续门。

## 冻结版本与审查边界

- 原被审材料：`370f8736f212adfc6ba05b0221bafa5061962a5c`，原独立初审为 `D:/wt/r17-graph-review1/reports/reviews/recovery/G-E-R17-evidence-graph-review-1.md`。原probe、negative JSON及原manifest只读复制，四项副本raw SHA256均与原文件一致；未修改旧89项raw。
- 新 reviewed material SHA：`65497b14cb5c24c6d780f675a70af3ee4019d8db`；tree：`39893dce7912f8206d50a79ae0139196efc02ed0`。
- 新 source SHA：`d6537678efe98c38e08b70960a7e5edaac02b108`；tree：`08249b02142cd085d4c4c801469edcea6d2b1649`。
- 独立目录：`D:/wt/r17-graph-recheck1`，分支 `codex/r17-evidence-graph-recheck1`，检查路径/分支未占用后从65497b1创建。没有在作者进行中目录核验通过，本reviewer未参与修复实现，未自行spawn。
- 按AGENTS读取执行图、R17卡、任务状态/交接，复用初审已读的T40/T41/T43、03/05/06合同、公APIv2与Ponytail5.2 review规则；新增CR-R17和作者fix1报告/manifest作为待核证据。authority文件hash列在自有audit，不据外部UI材料改变权限或业务合同。
- 仅修改本报告与 `reports/runs/recovery_r17_graph_review1_recheck_20261016/**`；现有源码/测试、App、全局CSS、API、认证、backend、lock/state/progress、作者raw未改。完整文件清单见自有manifest。

## 原 Must 1 的复验与根因闭合

原问题定位：`graph-explorer-view.tsx`的SVG曲线由index%4布线，后绘22px透明命中路径使鼠标点击“影响组件版本”曲线中点实际检视反向关系。新实现 `selectEdgeAtPointer` 使用实际screenCTM逆矩阵，把鼠标CSS坐标转到SVG；`findGraphEdgeCandidates`按曲线距离找最近/并列候选，不信任后绘DOM身份。44px non-scaling hit保持触控范围；并列关系以40/44px按钮明确确认，候选内容区260px有界。键盘与已有关系列表仍按选定关系ID操作；节点本体保持优先。

独立同坐标复验使用初审自行构造的同一六类DTO，**精确断言坐标仍为 `(407,682.671875)`**。原生 `page.mouse.click` 后，DOM target仍是“图关系6：组件版本关联事件”，但页面不再切到它，而保留节点检视并展示“选择此处的关系”。随后以实际候选按钮bounds再原生mouse确认“关系2：影响组件版本”；expected2/actual2相同，原文方向/依据属于关系2。完整输入、原坐标、DOM target、expected/actual在 `browser-independent-final/same-coordinate-confirmation.json`，确认前/后截图另存。没有用force、dispatchEvent或按DOM id给曲线发送点击来替代真实鼠标。

原2节点/1影响关系阳性对照继续用真实曲线中点Mouse，直接选中正确关系。独立390补充复验候选区button≥44px、260px上界、reset与pan清除旧候选、刷新403清除候选和旧图。最终这3项全部通过。原probe文件及原red不适配新交互流程的立即expect2仍保持原字节，不把历史失败改成skip/通过。

独立补充脚本初次adapt保留了旧“点击后立即出现关系检视”断言，因新授权chooser流程先等待确认而真实exit1，2pass/1fail；原脚本和日志完整保存。移除该先于chooser确认的陈旧断言、保留原坐标和expected关系2后再跑3/3通过。此处只调整reviewer自有probe，未修改作者测试/代码，也不是新的产品Must。

## 实际命令与检查（Asia/Shanghai +08:00）

完整argv、cwd、毫秒级start/end、exit code与ownership PID在本run `commands.jsonl`，stdout/stderr/JSON保持原字节；下表子集与总数不重复相加。

| 检查 | 实际命令 | 真实结果 |
|---|---|---|
| 离线依赖 | `node .../npm-cli.js ci --offline --ignore-scripts` | 04:34:01.360–04:34:06.999，exit0；此WT锁文件，Node24.13.1 |
| 前端回归 | `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<本run>/unit.json` | 04:34:37.611–04:35:10.478，exit0，405pass/0fail/0skip；graph子集53=原42+新几何11 |
| typecheck | `node node_modules/typescript/bin/tsc --noEmit` | 04:34:37.604–04:34:41.491，exit0 |
| lint | `node node_modules/eslint/bin/eslint.js .` | 04:34:37.713–04:34:45.368，exit0 |
| build类型 | `node node_modules/typescript/bin/tsc -b <本run>/build-tsconfig.json` | 04:35:26.601–04:35:29.360，exit0；继承原strict/include，仅自有incremental输出/@types路径，不改tracked tsbuildinfo |
| Vite production | `node node_modules/vite/bin/vite.js build --outDir <本run>/build --emptyOutDir` | 04:35:29.453–04:35:30.562，exit0；原App53modules，JS267.89kB/gzip82.20kB、CSS37.79kB/gzip7.76kB；未注册graph入口 |
| 全图浏览器回归 | `node node_modules/@playwright/test/cli.js test --config <本run>/playwright.config.mjs` | 04:34:53.895–04:35:14.170，exit0；18pass/0fail/0skip/0flaky，JSON duration19730.591ms，单msedge/1worker、自有25502 |
| 独立同坐标/阳性/390清除 | `node <本run>/browser-independent.mjs` | 最终04:38:01.680–04:38:05.472，exit0；3pass/0fail，Edge窗口2705ms；最初7.478秒尝试exit1的陈旧断言日志保留 |
| 自有CBM | 官方WSL portable `index_repository/get_graph_schema/get_architecture/trace_path` | 全部exit0；新cache/root/index绑定此WT frontend/src，403nodes/1458edges、partial0/unusable0、fast模式排除28测试；LoadedGraph11callee，selectEdgeAtPointer3callee含findGraphEdgeCandidates/distanceToSegment，与rg/源码交叉 |
| source/evidence audit | `python <本run>/audit.py` | 04:38:50.561–04:39:01.778，exit0；6源码/167作者证据逐hash核对，原probe4项raw一致；code/CR/report diff check exit0 |

18项Edge回归在本独立冻结WT实际重新执行了作者测试，无重用旧green日志：1366/390各6边×80/100/180%缩放及pan，附件实际各18次共36；30条平行/逆向/不同端点逐条原生Mouse共30；200nodes/400edges图原生坐标点击及候选确认精确edge UUID；Escape/首控件焦点/Enter、filter/zoom清除、节点Mouse与Space阳性、原文route、401/403/404/409/503、撤权、empty/partial/truncated、reduced-motion均通过。候选确认与曲线点击都用mouse坐标；DOM标识仅作结果断言。

单次合成密图观测：渲染369.4257ms、缩放+过滤434.1198ms；另一200/400真正pointer/chooser确认326.9805ms；30条点击循环2497.2869ms。raw附件已在audit提取并保留原browser JSON；不作正式时延/P95/live吞吐声明。

源/CR/报告定向diff check为0；全部材料diff check为2，保留原始red的两个error-context代码框、edge-red.stdout尾空格及其staged-all-diff-check.stdout复录，共4个证据文件。没有清理这些原raw以伪造pass，没有增加ignore。首个audit检查脚本误用manifest的非存在owned/artifacts键得到0条证据，未据此宣称核对通过；读取实际evidence键后167项核对通过。一次终端摘要打印遇Windows GBK不能编码“›”退出1，audit UTF8内容不受影响，改为ASCII JSON读取后核对；这不是业务测试失败。

## 有限范围、质量与状态

当前schema1客户端仅接受精确 `r10-graph-1.0.0 / r10-graph-1.1.0`。R10后端后续计划1.2尚未冻结，root需要后续metadata同步与对应合同/client回归；这不是本pointer Must再次开放的理由，也不能据本报告宣称真实1.2整合通过。App无GraphExplorerView import/caller，本次生产build继续是未注册图的原53module bundle；此事实经新CBM、rg和源码检查，没有拿旧索引当新证据。

实际查看本run同坐标确认前截图、1366/390选中截图与200/400图：候选清楚显示序号、关系类型、方向、完整端点、依据和ID；原检视在确认前没有变成反向关系；窄屏仅画布自身滚动，候选可滚动并有44px按钮。低亮动态背景沿用既有组件，reduced-motion由原e2e重新验证；真实hidden暂停没有验证。

| 维度 | 复核状态 | 限定范围 |
|---|---|---|
| unit | passed | 前端405（graph53）；非后端unit |
| contract | passed（限定） | schema1/精确1.0与1.1/既有DTO与几何输入，1.2未运行 |
| integration | not_run | 真实PG/API/生产App图入口整合 |
| security | passed（限定） | 原合成HTTP权限、撤回、迟到、错误私文/注入回归；真实后端跨租户not_run |
| frontend | passed（pointer切片） | type/lint/build/真实指针/窄屏与可读检视；不签完整R17 |
| e2e | passed（fixture） | 独立复跑18项+自有3项，全部显式隔离合成 |
| live | not_run / blocked_live | 后端/App接线与1.2后续门，未调用模型/来源/资产 |
| manual | not_run | reviewer截图目视已做；不替代人工签字/连续录像/hidden暂停 |

必要复杂度：沿用React/native SVG、现有auth/client/证据检视/状态组件，无新库；纯几何函数可单测，IO/会话与业务DTO保持原权威。最多400×128段仅在真实click处理，未变成pointermove热循环，也没有全能工具层。重叠必须由用户明确选择是CR-R17已授权的交互取舍；此修复足够局部，本轮没有可证实的复杂度删除建议。

D2/R17:T41限定证明原画布选择缺陷关闭并保持图/引用与键盘/窄屏流程；E1限定客户端严格边界和会话清除；F2只展示输入supported关系，不证明关系生成准确性、资产影响或来源真实性。未改金标/分母/阈值/公共业务合同/计划，完整R17/G-E与真人验收保持未完成。

## 进程、原字节与交接

25502初始无listener、独立probe每次先原生TCP bind验证空闲；Playwright reuseExistingServer=false，globalTimeout150s，全部命令窗口最长20.275s，单browser≤180s。其自有Vite PID31604、worker44524与runner48252取自raw stderr/command记录；自有Node/Vite-api PID48296/47536、Edge36756/39212及子进程由browser CDP和start/stop记录。`process-after.json`确认这些PID均退出且25502无listener；first running采样已晚于短run结束，因此记录空而非编造在途进程。所有浏览器close/server finally close或Playwright清理，不手动kill用户进程，不操作CNNVD IAB，没有model/source/秘密/第三方资产访问。

作者manifest在本CRLF检出WT的raw SHA256=`f467dd1cb074118b03dba98b1b857ec7bab3d0d4c02ce1db0fe3ec00c6eccb1f`；LF/Git blob SHA256=`5dbd71022d2197ec7f5aedc0229fec870f790a3773bd030c4bce7867b92055d6`，与交接所报本体一致。6源码的LF与d653 blob/material源码一致；167证据按文本LF或二进制raw核对；作者原raw与旧review原raw均未改。自有manifest包含本报告/脚本/原probe副本/日志/截图/构建证据的raw和LF，manifest本体hash另在 `artifact_manifest.sha256`，避免自引用。

Verdict: Ship，限d653当前pointer修复切片，原Must1=`closed`。建议root合入该切片后办理后续1.2 metadata同步、App注册和真实PG/API→图→原文→撤回链；新合同/真实live另跑。Not checked: 后端1.2/真实整合/live、生产graph bundle、完整R17/G-E、正式性能、人工验收与原生hidden暂停。
