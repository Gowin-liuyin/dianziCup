# G-E / R17 证据图前端切片 · 新独立初审

What this change does: 本切片新增 `GraphExplorerView(eventId,onNavigateBack?,dataMode?)`，在既有 AuthProvider 中读取固定同源、有界 graph DTO，并把六类节点、支持关系、缺口、版本与原文路由呈现给用户。作者明确未注册 App、未接真实后端；本审查只覆盖这份冻结前端，完整 R17 / G-E 不据此验收。

任务状态建议：`needs_changes`，Must 1 未关闭；不写 `accepted`，不改 progress/state/lock/合同/作者源码。本 reviewer 首次独立审查此切片，未参与实现、未自行 spawn；仅在指定独立工作树增加审查报告、自己的检查脚本和原始证据。未提交、未 push，review SHA=`none`。

## 冻结对象、前置与范围

- 基线：`8a1b04d48346d8550f0326a77f003246a0ebbab5`。
- reviewed SHA：`370f8736f212adfc6ba05b0221bafa5061962a5c`；tree：`ec464bf91b7c2806cb7b2fbbcd0a2529dffbd985`。
- 作者源码 freeze：`b58aac48eee7e50264e3f51821c8057af36433d7`。独立 WT：`D:/wt/r17-graph-review1`；分支：`codex/r17-evidence-graph-review1`，从 reviewed SHA 建立。未从作者正在变化的目录核验通过。
- 已读 AGENTS、00执行图、R17恢复卡、T40/T41/T43、03/05/06合同、公API v2、08/09、任务状态与交接、Ponytail 插件5.2.0的 `skills/ponytail-review/SKILL.md`。作者设计/交付报告和用户 `E:/wechatData/.../2026-10/ui-design.md` 只作待核证据/审美参考，没有将外部材料当项目指令。
- 冻结 WT 不含图后端。仅用 `git show 16803ce:backend/src/ai_intel/knowledge/evidence_graph.py` 对照1.0 DTO。主控确认1.1后端仍未冻结；本次1.1仅证明前端接受精确 `r10-graph-1.1.0` literal 的合成响应，不证明语义修复或 PG/API 整合。
- 输入：同源 `GET /v1/events/{UUID}/graph?max_nodes=200&max_edges=400`；schema1，精确规则1.0/1.1，无 `data_mode`。输出：图、检视、既有 `#events/{event}/evidence/{span}` 路由。浏览器夹具全部明确隔离合成；0外部模型/第三方资产/秘密访问。
- 本轮修改清单：本报告及 `reports/runs/recovery_r17_evidence_graph_review1_20261016/**`。源码、既有测试、公共合同、依赖锁、认证、状态、作者原始 raw 未改。文件逐项清单见独立 `artifact_manifest.json`。

## Must fix

1. **[P2] 多关系图里点击“影响组件版本”曲线会检视另一条关系** (`frontend/src/features/graph/graph-explorer-view.tsx:101`，同文件103/109；`frontend/src/features/graph/graph.css:50`)
   - **这是什么：** 画布使用每条边的 SVG 曲线和透明命中路径接收鼠标点击，再将该边放入“关系检视”。预期点击影响边后展示其影响关系、方向与支持证据。
   - **问题：** 现有曲线只以全局 `index % 4` 给四种下弯幅度；正常六类图中 index1的 `event→component_version` 与后绘制的 index5 `component_version→event` 中段重合，22px命中区覆盖前者。原生鼠标点影响曲线中点 `(407,682.671875)`，实际选中“图关系6：组件版本关联事件”，不是“图关系2：影响组件版本”。21点坐标核查还显示端部被节点透明矩形占据，中段被关系6占据；去掉反向边后同一中点被“关联论文”覆盖，说明不是单个 WebDriver 中心定位问题。键盘与关系列表可以正确选择，故只限定为画布指针操作缺陷。
   - **最小修复：** 在现有 SVG 布局中，按确定的端点对分配可区分的曲线偏移，并把反向边置于相反弯曲侧，避免可见边被其他命中路径整段盖住；保留原生 SVG 和既有列表，不增加图形库。增加真正 `page.mouse.click` 的六类图回归，不能用 `force`、`dispatchEvent` 或只按 Enter 代替。
   - **不修的结果：** 用户点击画布时核查的是另一条关系，容易把修复/论文/反向关联的依据当作本次想看的影响关系；图/检视联动的可观察行为不满足本切片声明。

**触发与证据：** `browser-pointer.mjs` 使用独立构造的合法六类 DTO，经实际 client→React→Edge；`browser-pointer/pointer-negative.json`保存完整输入、expected2/actual6、坐标和实际命中目标，截图 `browser-pointer/pointer-selects-wrong-edge-1366.png`。对应检查真实 exit1，1失败；同一脚本的2节点/1影响关系阳性对照真实鼠标点击通过，1通过。`browser-recheck/svg-hit-samples.json`与 `svg-without-reciprocal.json`记录几何取样。未给作者打补丁，未对同根因扩大业务修复；复验要求是在新冻结修复 SHA 上重跑这两个对照、六类图全部关系的指针/键盘选择、200/400及移动端。

## 实际检查与结果（全部 +08:00）

原始 stdout/stderr 与完整 argv/cwd/start/end/exit code/ownership PID 在本 run 的 `commands.jsonl`。以下数量不把子集与总数相加；浏览器多次诊断也不合成一个“全通过”的总数。

| 检查 | 实际命令（路径缩写只用于本表） | 起止 / exit / 真实数量 |
|---|---|---|
| 离线安装 | `node .../npm-cli.js ci --offline --ignore-scripts`，frontend cwd | 03:50:40.586–03:50:43.941，exit0；本 WT 锁定版本，Node24.13.1 |
| 前端回归 | `node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=<本run>/unit-regression.json` | 03:50:59.737–03:51:29.068，exit0，394通过/0失败/0skip；graph子集42=20合同+9client+13组件/布局，已包含在394中 |
| 类型 | `node node_modules/typescript/bin/tsc --noEmit` | 03:50:59.623–03:51:04.654，exit0 |
| lint | `node node_modules/eslint/bin/eslint.js .` | 03:50:59.763–03:51:08.145，exit0 |
| build类型 | `node node_modules/typescript/bin/tsc -b <本run>/build-tsconfig-final.json` | 03:55:21.942–03:55:24.237，exit0；继承原 tsconfig/include/strict，仅把 incremental产物与@types解析放在自有run，未触碰tracked tsbuildinfo |
| 生产构建 | `node node_modules/vite/bin/vite.js build --outDir <本run>/build --emptyOutDir` | 03:53:49.439–03:53:51.118，exit0，原App53modules；JS267.89kB/gzip82.20kB，CSS37.79kB/gzip7.76kB。此bundle尚不包含graph入口 |
| 自有CBM | 官方WSL portable `index_repository/get_graph_schema/get_architecture/trace_path`；`CBM_CACHE_DIR=/tmp/dianzi-cbm-r17-review1-20261016`，allowed root仅此WT frontend/src，persistence=false | 四命令exit0；394nodes/1435edges，partial0/unusable0，fast模式排除27测试文件；GraphRequest outbound26callee，与源码/rg交叉 |
| 主浏览器边界复验 | `node <本run>/browser-review.mjs`，本地25489，实际Edge | 03:57:19.334–03:57:40.066，exit1；19检查=17通过+2失败，两个失败为同一画布遮挡根因；浏览器窗口19.723s |
| 最小指针负/阳性对照 | `node <本run>/browser-pointer.mjs` | 03:59:15.937–03:59:18.604，exit1；2检查=1通过+1失败，expected影响边/actual反向关系；窗口1.784s |
| 源码/作者封存交叉 | `python <本run>/source-audit.py` | 04:02:23.441–04:02:33.819，exit0；最终显式UTF8；12源码LF/冻结blob/作者LF均一致，133作者artifact按文本LF或二进制raw核对；source diff check exit0 |

首轮浏览器13/16通过，3失败的自动中心点击日志完整保留。改为原生关系列表后，partial/注入操作通过；证据403初次断言用了共享客户端原文案，而实际 EventWorkspace 定制文案不同，调整为实际“证据检视/没有查看权限”可观察标题后通过。第二轮shutdown错误是审查脚本错误查找 esbuild 在顶层，而依赖实际位于vite/node_modules；它导致结果JSON尚未写出，raw stdout/stderr与截图保留，下一轮使用实际路径正常关闭。最终指针负例再使用真实曲线坐标证明产品缺陷，未把这些初期工具问题冒充业务缺陷，也未删失败记录。

最初将 `--tsBuildInfoFile`直接与`tsc -b`组合报TS5094，exit1；第一次自有扩展config报node类型解析路径缺失，exit1；修正自有config后上表最终构建类型通过。这两项仅是保持允许写入边界的检查配置问题。source-audit首次把二进制作者entry当作LF文本报KeyError，exit1；一次后续审计exit0但rg读取发生GBK解码警告，原日志保留，最终显式UTF8复验才作为封存依据。

## 合同、安全、可用性与评分证据

实际查看本 reviewer 的1366/390、密图200/400、390原文截图：暗绿终端网格沿用现有工作台，低亮拓扑背景可见；无页面横向溢出，图自身独立滚动。桌面可见button/link/summary/筛选label实测≥40px、390≥44px；此结论不把SVG边22px命中宽度算作44px控件。密图右侧节点关系列表有330px上界，图/关系列表有滚动界限；不宣称密图无重叠。

- 默认 `dataMode`不传时实际显示“数据模式未确认”，不显示live。AuthProvider缺失会抛既有明确异常；未重造认证。
- schema1、六类、严格字段集合、UUID、范围组合、节点/边上限、支撑ID数组、悬空/重复身份、精确1.0/1.1与拒绝1.2经既有42项及独立实际HTTP/browser复跑。1.0 DTO与冻结后端16803ce字段交叉；公API v2 Citation不被误当graph数组zip映射。
- 独立浏览器用2个source revision、3个span，选第3span；路由固定span UUID，证据API返回另一个revision72，页面显示真实返回revision72。未猜两个数组的对应关系，未提供任意URL读取。hash仅显示服务追溯标识，未把它当来源真实性验证。
- 401/403/404/409/503各自拒绝/过期/不可用语义，409/503可恢复；错误私有detail不呈现，失败不是零关系成功。仅事件、unknown gap、截断与部分gap仍可继续操作；没有“暂无风险”或人工审核完成伪结论。
- 刷新立刻清除旧图；新会话401撤回后，迟到旧图不能恢复。原文403没有blockquote，也不显示错误私有正文。这里只证明客户端隔离夹具行为，后端ACL/撤回事务未实测。
- 原文请求实际通过 EventWorkspace→私有EvidenceInspector→getEvidence；源码/rg确认App尚无GraphExplorerView import/caller，生产fixture四个独有标记扫描0。没有将53modules build冒称graph已集成。
- React文本渲染恶意label/reason，未生成img/onerror/onload；请求固定同源UUID路径，沿用fetchJson cookie/no-store/超时与Auth代次。没有关闭strict/lint或新增依赖。
- reduced-motion下实际background animationName=none、graph transition=0s；no-preference下背景transform前后变化。未把CSS动画当真实任务/业务进度；真实浏览器原生hidden窗口暂停未验证。
- 密图200nodes/400edges单次自有渲染532.2704ms/缩放与过滤292.4450ms，raw值见 `browser-recheck/browser-results.json` 的 `bounded-200-400-synthetic.detail`，只报这一次合成UI测量，不作正式时延、P95或真实吞吐证据。

| 验证维度 | 本切片结论 | 明确边界 |
|---|---|---|
| unit | passed | 394前端回归，含graph42；不是后端unit |
| contract | passed（限定） | 冻结1.0字段、前端1.0/1.1精确metadata与异常DTO；不签1.1后端语义 |
| integration | not_run | 真实PG/API图及App注册后整合未跑 |
| security | passed（限定） | 合成HTTP的拒权/撤回/迟到/注入/私有错误文本边界；后端跨租户与真实租户测试not_run |
| frontend | failed | 类型/lint/构建通过，Must1画布鼠标选择失败 |
| e2e | failed（fixture） | 实际Edge合成链17/19通过，最小鼠标对照1/2；真实后端e2e not_run |
| live | not_run / blocked_live | 1.1后端未冻结/未整合，未发外部调用 |
| manual | not_run | reviewer已做截图目视核查，但不等于真实人工验收/连续录屏/原生hidden暂停验证 |

D2/R17:T41：限定证明图/引用键盘路由、窄屏与长标签检视、部分失败继续操作；画布指针仍有Must。F2/R10：只展示后端DTO支持关系的依据，不证明生成准确性或资产影响。E1：客户端同源、输入校验与会话清除有独立证据；不替代后端ACL/事务/真实安全测试。无金标、分母、门槛、公共合同、计划语义改变。

## 必要复杂度、进程与封存

复用现有 AuthProvider、fetchJson、EmptyState/ErrorPanel、AmbientBackdrop、EvidenceInspector与UUID hash路由。URLSearchParams、Map/Set、React和native SVG足够处理200/400有界输入；没有引入布局库、万能服务或第二套业务状态。六列确定布局与本地严格DTO边界有实际职责，本轮没有可核实的冗余依赖/抽象删除建议；Must1应在现有绘线函数局部修复。

所有浏览器独立启动 actual Edge/msedge，单次窗口1.784s/19.723s/26.264s，均≤180s；另一次17秒尝试也在raw日志，不复用用户CNNVD IAB。自有Vite25489每次先用原生TCP bind验证空闲，server与browser起止/ownership PID在各browser-results；结束 `process-after.json` 记录端口无listener。初次node43440、最终6304/47324和相应Edge PID结束；历史35308后复查被系统复用于conhost，仅记录身份变化，未误杀它或用户进程。所有自有server由finally显式close、所有自有browser由close结束。没有会话外运行承诺。

独立 `source-audit.json` 保存12个新增源码的raw/LF SHA256、Git blob、冻结源码与材料提交一致性，以及133作者证据的原字节或LF核查。Windows检出CRLF使author manifest在此WT的raw SHA256为 `e1a90091c85cc7cac1716cf63ad281b7dbdb7fecb47842197b3334ad47f806e9`，其LF/Git blob SHA256为 `a3e8cc3cb0491c1b0c2f4c806b09dd2409764b814f4bf84b39906170d96ac71a`；未覆盖或重写作者原raw。自有 `artifact_manifest.json` 列出本报告/脚本/日志/截图/构建产物的raw及LF/blob核对范围，manifest本体SHA256单独写 `artifact_manifest.sha256`，避免自引用；最终交付提供本体hash。

Verdict: fix 1 first. 当前冻结切片 `needs_changes`；修复后从新冻结SHA复验，再由主控安排App/路由注册与真实后端证据图链。Not checked: 真实PG/API/live、生产graph入口bundle、完整R17/G-E、正式性能、人工标注/验收及原生hidden暂停。
