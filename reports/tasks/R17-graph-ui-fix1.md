# R17 证据图指针选择 fix1

状态`awaiting_review`，本P2修复切片实现`complete`；完整R17/G-E仍`partial`，Must是否关闭由原非作者reviewer定向复核。基线/原被审对象`370f8736f212adfc6ba05b0221bafa5061962a5c`，原tree `ec464bf91b7c2806cb7b2fbbcd0a2529dffbd985`；当前代码freeze `d6537678efe98c38e08b70960a7e5edaac02b108`，tree `08249b02142cd085d4c4c801469edcea6d2b1649`。新WT `D:/wt/r17-graph-ui-fix1`，分支`codex/r17-evidence-graph-ui-fix1`。未修改原冻结WT/独立probe，未push/accepted/progress。

## 输入、根因与修改

已重新核对AGENTS、00执行图、R17/T41恢复卡及冻结合同、当前状态和交接，读取原独立初审与实际指针原始材料。Ponytail5.2 full保持现有native SVG/React；Diagnosing Bugs先真实mouse红再绿，未用DOM强制派发代替指针命中。无GLOSSARY/对应图ADR，新增授权UI决定见 [CR-R17](../../docs/decisions/CR-R17_graph_edge_selection.md)。本修复不改变DTO/schema1/精确规则1.0与1.1/业务关系语义。

原独立报告为`D:/wt/r17-graph-review1/reports/reviews/recovery/G-E-R17-evidence-graph-review-1.md`；其manifest本体SHA256实际核对为`812970796a9d0325ce1011876525b3aa5bfccbdda7454ff7101f430c9b21874e`。原`browser-pointer/pointer-negative.json`与`browser-pointer.mjs`只读并留副本，本fix没有覆盖其89项raw。原370的12个前端源码/测试Git LF blob另存`original_snapshot/frozen_source/`，原raw关键源码/测试和作者、reviewer manifest/JSON也留档；路径、blob与hash见`original_source_archive.json`和新manifest。

真实鼠标红测03项在04:02:59.864–04:03:09.821(+08:00) exit1：完整六类边2曲线点`(407,682.671875)`实际检视`component_version_vulnerability`；移去逆边同点实际`related_paper`；2节点/1影响关系鼠标阳性通过。因此是两个同根因失败+一个阳性，不是环境失败。已保存expected/actual、screen坐标、原始stdout/stderr、error-context与browser.red.json。

根因是后绘22px透明stroke接收点击后直接按其DOM身份选边，曲线本身重叠时覆盖用户看到的边；仅缩小hit或修四条曲线偏移不足以保护平行、多端点和密图。

共6文件代码/决定变更：graph-explorer-view.tsx、graph.css、新graph-edge-selection.ts及其专属unit、新r17_graph_edge_pointer_fixture.spec.ts、本CR。`createGraphEdgeCurve`沿用原曲线，预先128段有界近似；`findGraphEdgeCandidates`在CSS像素中计算最近曲线，不依赖后绘目标。44px non-scaling透明stroke保留触控范围；22px半径另留2px采样误差，最近距离4px内并列关系交给明确候选区。候选展示序号、类型、方向、完整端点、依据和ID，不默选另一条关系。

真实pointer在SVG capture处理，使用实际getScreenCTM逆矩阵转换，平移/滚动/缩放后仍从屏幕坐标定位。节点本体保留优先（80%缩放的可见主体仍超过44px目标）；与节点填充面重合的不可见边段不抢节点点击，完整关系可从其可见曲线段选择。候选区260px独立滚动、首控件焦点可见、Escape/取消回画布；节点/列表/键盘按ID直接选择，筛选/缩放/平移/重置清除旧候选。detail=0仅代表辅助技术/语义角色激活，实际pointer detail>0必须走几何路径；这些语义unit不计为Mouse证据。

App、shared API、backend、全局CSS、认证、锁、progress、既有tests/旧raw未改；动态背景原组件保持，reduced-motion与已有错误/撤权/原文hash路径保持。没有新增依赖、金标改写、分母/门槛调整或任意URL。真实后端整合仍由主控负责。

## 真实验证（Asia/Shanghai +08:00）

完整argv/cwd/毫秒级start/end/exit在`reports/runs/recovery_r17_graph_ui_fix1_20261016/commands.jsonl`，各stdout/stderr及JSON均保留。源码先1886冻结实现，再d653只补最大图指针测试，d653后重新实跑下面的最终回归/静态/构建/18项Edge；不拿旧试跑背书新增测试。

| 检查 | 实际结果 |
|---|---|
| `node node_modules/vitest/vitest.mjs run src/features/graph --reporter=json --outputFile=.../graph-unit.frozen.json` | exit0，53/53、0fail/skip（原42+新几何11）；最终全前端再次包含全部53 |
| `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=.../regression.release.json` | 04:19:03.587–04:19:36.772，exit0，405/405、0fail/skip；原394+新11，不与子集重复相加 |
| `tsc --noEmit` / `eslint .` / `tsc -b` / `vite build` | 04:19:36.854–04:19:45.015，均exit0；原App53modules，JS267.89kB/gzip82.20kB、CSS37.79kB/gzip7.76kB；App仍未注册图入口。tsbuildinfo生成副本存本run再恢复HEAD原blob |
| `node node_modules/@playwright/test/cli.js test --config <本run/playwright.release.config.mjs>` | 04:19:07.561–04:19:29.060，exit0，18pass、0fail/skip/flaky，20.961s<180s；原10+新8，真实本机Edge/msedge、1worker、专用Vite25501 |
| CBM portable actualcli索引/schema/architecture/trace，rg | 正确Ubuntu-22.04 root、独有cache及frontend/src root、persistence=false；实际exit0，最终403nodes/1458edges、partial0/unusable0，28测试按fast设计排除。TSX LoadedGraph追到曲线创建/候选判断，rg交叉真实pointer/角色激活路径；Git SHA/tree另记 |
| 原始备份/diff/hash/限定源码扫描 | original_source_archive记录12个原blob，新manifest核对当前6个变更文件的LF SHA256/Git blob；限定检查不充当全仓安全验收 |

源码/本CR/报告定向diff check实际exit0。全部staged材料检查exit2：两个red error-context代码框和edge-red.stdout保留了原始尾空格，不能为通过检查而改原始失败字节；自有生成config的末尾空行已清理，行为/参数不变，没有增加ignore。raw空白问题与产品/测试失败分开记录，新manifest同时保存raw和文本LF hash。

诊断过程完整保留：原red 2fail/1pass，第一版绿3/3；扩展17/17后补依据文本/截图冻结1886，再17/17；最终d653补200/400真实Mouse并18/18。所有失败与早期通过材料另名保存，未删除难例、改失败为skip或用force/dispatchEvent。初始状态读取误选不存在的recovery键，随后按实际recovery_tasks读取；这是预检命令错误，不记为业务测试失败。

最终mouse检查使用SVGPathElement实际getPointAtLength、getScreenCTM求屏幕坐标，然后`page.mouse.click`。六类完整图在1366/390及80%/100%/180%缩放和平移共36次边选择；另30条含平行/逆向/不同端点逐条30次；候选按钮同样取实际bounds以mouse确认并断言精确edge UUID，不只是locator把事件强行送到path。边段采样避开可见节点本体，保留真实节点Mouse阳性。候选焦点/Escape/Enter、筛选/zoom清除、44px non-scaling、页面无水平溢出及reduced-motion均自动检查；旧10项含原文路由、401/403/404/409/503、撤权、unknown/truncated和密图回归。

最大合成图最终单次观测：200/400渲染373.2405ms、缩放+过滤449.6842ms；另真正pointer/候选确认304.4474ms，expected edge`71000000-0000-4000-8000-000000002001`被精确选择，候选区≤260px。raw在browser.release.json附件。与其他后台检查有重叠，不作专用性能基线、P95、性能阈值或live吞吐结论。

作者实际查看最终desktop候选截图和390选中截图：逆向关系2/6方向可辨、ID/依据可读，旧检视没有自动变成6；窄屏图自己滚动，下面的关系列表和检视保持工作台风格。此观察不替代独立manual签字。

进程记录`process-before-frozen.json/process-after-release.json`：25501先查空，最终无listener；当前记录Vite PID41392、worker PID33460均已退出。每次独有webServer、reuseExistingServer=false、finally由Playwright清理，无手动kill/用户CNNVD tab操作；每个浏览器窗口均≤180s，未保存登录密码/trace/video。仅合成HTTP fixture，没有外部providers/模型/资产访问。

验证：unit/contract/security/frontend=`passed`仅所列前端检查与固定HTTP fixture；e2e=`passed`仅18项隔离Edge；真实PG/API integration=`not_run`，live=`not_run`，独立manual=`not_run`。D2/R17:T41限定证明该Mouse缺陷在作者反馈环内不再复现，E1保持输入/授权/清除和渲染边界；F2不证明新关系生成准确性。原整体R17/G-E和App接线缺口不提升。

下一步由原非作者reviewer从d653冻结及本manifest定向复验同一坐标、候选确认、六类/密图与原流程，然后由主控合并/接线。未检查真实后端/live、App注册后的生产bundle、完整R17、原生hidden暂停或独立人工验收；交点处需明确选一条关系是本CR记录的交互取舍。
