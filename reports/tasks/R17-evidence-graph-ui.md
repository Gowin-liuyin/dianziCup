# R17 证据图前端切片

状态：`awaiting_review`，本独立证据图切片实现 `complete`；完整 R17 为 `partial`。基线 `8a1b04d48346d8550f0326a77f003246a0ebbab5`，当前实现源码冻结 `b58aac48eee7e50264e3f51821c8057af36433d7`，独立工作树 `D:/wt/r17-graph-ui`，分支 `codex/r17-evidence-graph-ui`。未push、未自行accepted，主控唯一负责App/路由注册与阶段状态。

## 研究、输入输出与修改范围

实现前的实际官方产品研究、参考取舍与预定义回归见 [设计记录](R17-evidence-graph-design.md)。实际读OpenCTI与Graphistry官方文档；Neo4j直接页面不可达已明记。用户ui-design.md作为材料，Ponytail5.2 full与Industrial Brutalist的terminal/grid原则应用于当前暗绿工作台；无新增库/位图/全站重写。

仅新增 graph 模块9文件、graph专用 e2e 及HTML/React harness共3文件、独有设计/交付报告和run证据。GraphExplorerView导出路径 `frontend/src/features/graph/graph-explorer-view.tsx`。props为`eventId`、可选`onNavigateBack`、可选`dataMode=fixture|live|unknown`（默认unknown）；必须处于现有AuthProvider中。输入使用`GET /v1/events/{UUID}/graph?max_nodes=200&max_edges=400`的schema1冻结DTO；GraphSnapshot没有data_mode，不能自行默认live。

没有修改App、全局CSS、shared API、公共合同、package/lock、认证、后端、迁移、金标、指标分母、progress或用户当前工作树。生成的tsbuildinfo先存本run副本再恢复HEAD原始Git blob，当前工作树无该文件diff。初次离线安装使用本WT锁文件，最终另保存同命令完整日志；未下载依赖或改变版本。

## 可观察行为与调用者影响

严格读取schema/UUID、六类节点与六类关系、scope组合、精确规则版本1.0/1.1、支持证据/断言集合、端点完整性、去重身份、200/400及2000支持行限额、unknown/truncated/hash格式；非法协议、任意URL/标识注入、悬空/重复节点与无证据关系返回ApiProblem，不产生假成功。所有文本由React渲染；不会执行reason/label中的HTML。hash显示为服务返回的追溯标识，没有自称来源真实性核验。

图使用native SVG有界六列确定布局，缩放80%–180%、重置、四向平移、原生滚动、类型筛选和图/关系列表双向选择。图内短标签；完整标签、方向、reason、业务/规则版本、支持claim与所有原文span在检视区展开。200/400大图根节点400个关系的检视列表限制330px独立滚动；图和关系列表也有固定滚动边界。数量明确为当前视图/快照节点与关系，来源修订不是受影响资产。

证据链接复用既有`#events/{event}/evidence/{span}`路径，打开现有EventWorkspace的私有EvidenceInspector及真实getEvidence客户端。两个独立provenance数组未zip，未猜revision对应；证据读取后显示服务保存的原文修订与定位。每条引用均为固定UUID路由，不接受Graph DTO任意URL。

loading、仅根节点、unknown gap、truncated、401/403/404/409过期/503有明确文案；409/503可重新读取。刷新立即清除旧图，换事件/会话/权限代次重建上下文；迟到响应无法恢复旧内容，401使认证上下文失效。candidate/人工审核进度不在DTO里，页面明确说明当前只显示supported快照，未伪造全部审核完成。GraphGap仅接受冻结的两个reason；后端新增reason必须协商升级，当前会显示协议不匹配。

主控需要在shell注册GraphExplorerView与图入口，并从实际会话/运行配置传dataMode。普通Vite production build当前仍为原App的53modules，因为本包按所有权没有注册入口；它证明当前集成基线未破坏，graph代码同时经严格type/lint和受控Vite真实模块转换/EdgeHTTP fixture验证。注册后需复跑生产bundle与真实后端权限/撤回链路。

## 真实命令与结果（+08:00）

完整argv/cwd/秒级start/end/exit_code在本run `commands.jsonl`；stdout/stderr不改原始字节。run路径：`reports/runs/recovery_r17_evidence_graph_ui_20261016/`。

| 实际检查 | 退出码与实际结果 |
|---|---|
| `node node_modules/vitest/vitest.mjs run src/features/graph --reporter=json --outputFile=.../graph-unit-v1_1.json` | 03:38:58–03:39:02，exit0，42/42、0failed/0skip（20合同、9client、13组件/布局）；含精确1.1通过与未知1.2拒绝 |
| 最终`node node_modules/vitest/vitest.mjs run --maxWorkers=1 --no-file-parallelism --reporter=json --outputFile=.../regression-v1_1.json` | 03:39:02–03:39:26，exit0，394/394、0failed/0skip；包含原352与本42，不重复相加 |
| 最终`tsc --noEmit` / `eslint .` / `tsc -b` / `vite build` | 03:38:58–03:39:06，均exit0；53modules，JS267.89kB/gzip82.20kB，CSS37.79kB/gzip7.76kB；graph待主控注册入口 |
| `node node_modules/@playwright/test/cli.js test --config <本run/playwright.config.mjs>` | 03:39:19–03:39:28，exit0，真实本机Edge(msedge channel)10pass、0failed/skip/flaky，1worker，8.278s；全部graph HTTP fixture为规则1.1，独有Vite25488、单Edge，不操作用户CNNVD tab |
| CBM portable actualcli `index_repository/get_graph_schema/get_architecture/trace_path`与`rg` | 实际exit0；最终394nodes/1435edges，partial0/unusable0。27测试文件fast模式按设计排除；TSX GraphRequest追到getEventGraph、parseGraphSnapshot、fetchJson、Auth与展示函数（26callee），不是仅索引TS文件 |
| `npm ci --offline --ignore-scripts`、Node版本、diff/hash/限定扫描 | 实际命令与日志在run；Node24.13.1，本WT锁文件安装299包。后续seal记录raw/LF/Git blob并限定验证；不作为全仓秘密安全审计 |

首个预定义red测试于03:25:27–03:25:28 exit1：两个模块尚未实现，2suite导入失败、0业务测试实际执行。不是环境业务失败，也不是通过。03:29:06 typecheck exit2报两项未使用import，删除无用import后实际通过。初次浏览器10/10通过；作者查看200/400截图后发现侧栏需有界滚动，提交e70aa5f并补浏览器断言，旧1.0版本10项再次全通过。随后主控明确后端1.1语义修复，提交b58aac4只对精确规则元数据兼容1.0/1.1，schema1与gap两个reason不变；追加4项合同/client检查并将Edge HTTP fixture切至1.1。最终新冻结版本42/394/10均实跑通过，不拿e70旧测试背书新code。所有初次与最终JSON/截图/日志保留，不覆盖失败材料。

## 图像、边界、性能与评分证据

作者实际打开了1366、390与200/400截图以及390证据检视截图，最终1.1版截图另在`browser_artifacts_v1_1/`保存。六类形状和文字共同表达；桌面右侧检视、窄屏下方检视，画布独立水平/垂直滚动，页面宽度不溢出；按钮桌面≥40px/窄屏≥44px自动实测。Enter选择SVG关系/节点，原文引用键盘触发既有证据请求；reduced-motion下既有background animationName=none、图边transitionDuration=0s。没有重新实现动态背景。作者视觉检查不是独立manual验收签字。

最终1.1最大合成图单次UI测量：200nodes/400edges，导航至显示388.214ms，缩放与过滤完成238.487ms；fixture减少论文类型后160节点。raw测量在browser-v1_1.json的`synthetic-bounded-timing`附件。没有P95、正式性能门或真实后端吞吐声明，未模拟真实live数据。

进程前后检查记录`process-before.json/process-after.json/process-after-v1_1.json`：25488端口初始无listener、结束无listener；最终日志所记录Vite PID16584、worker PID11444结束后均不存在，旧1.0的PID10996/37412也在当次结束检查中不存在。Playwright自行清理所有权进程，没有手动kill用户进程。browser raw警告仅NO_COLOR/FORCE_COLOR与--trace-warnings提示。未保存登录密码、trace/video或对用户浏览器取截图。

验证状态：unit/contract/security/frontend=`passed`仅此切片和已有前端回归；e2e=`passed`仅显式隔离HTTP fixture→实际client→React→Edge链；真实PG/API integration=`not_run`，live=`not_run`，独立manual=`not_run`。后端仍有主控P1修复/复核任务，不能计为已接真情报。没有真实人工审核、asset影响判断、知识撤回/刷新live、持续运行或正式指标验收。

D2/R17:T41：限定证明图与证据互跳、长标签检视、部分未知继续操作、窄屏/键盘/错误/撤权清空。F2/R10：限定展示六类后端supported关系的依据，不证明本UI生成了关系或富化准确率。E1：限定同源固定路由、严格协议和渲染安全，不替代后端scope/事务/撤回检查。合同和计划未变更，不修改金标/分母/门槛。

下一步：主控安排未参与实现的新独立reviewer复核冻结源码与manifest；后端复核后注册App/路由，实际认证会话下跑事件→图→原文→撤权/修订，并在产物中确认fixture标识不进入生产行为。完整R17/G-E仍须其他业务工作台流程和真实验收。

`artifact_manifest.json`实际校验12个前端新增文件LF SHA256与b58aac4冻结Git blob一致，保存原始字节hash、LF hash和blob ID；自有run/报告证据另存raw/LF hash，实际数量见清单。限定credential-shaped literal扫描0、当前生产JS的4个独有fixture标记0、tsbuildinfo与HEAD blob一致；范围只覆盖该切片，不证明全仓没有秘密。manifest排除自身与seal的stdout/stderr以避免自引用；记录seal命令后再刷新封存，使commands.jsonl的hash包含该实际退出记录。源码/报告定向diff check及全部staged材料diff check均实际exit0，日志分别保存，不删改原始材料空白。

未检查：真实后端/live、主控App注册后的生产bundle、独立manual与整R17。风险：新增GraphGap reason/规则版本需要显式合同更新；当前图只覆盖接口给出的有界supported快照。
