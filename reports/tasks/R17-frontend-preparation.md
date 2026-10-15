# R17 前端准备切片

状态：`awaiting_review`；整R17实现 `partial`。本准备切片的auth/health、导航、黑客风与动态背景已实现；完整业务和原生隐藏页人工验证缺口保留。作者 hacker_frontend；Asia/Shanghai。基线 `b099483b4f2be3d21b3fd3e7e4327912ba75cae2`，源码第一冻结 `fa5787409da358ea95dbb35acfbd3a96c1fa2371`，动效修复冻结 `00a5c990c22c6bf1e1d572fe358b086baf02d66b`。独立WT `C:/Users/yinha/.codex/worktrees/recovery-hacker-ui/dianzi`，分支 `codex/recovery-hacker-ui`；未push。

## 目标、范围与实现

真实调研→设计→实现已按顺序完成。读取AGENTS、00/11/12（R04/R17）、03/05/06、public_api_v2及原T20/T30/T31/T40/T41/T42/T43验收；读取外部ui-design参考并记录取舍。详细调研和信息架构见 `docs/design/recovery_hacker_workbench.md`。

复用既有React/CSS、AuthProvider、API客户端、StatusBadge/ErrorPanel/EmptyState；没有新UI库、router、主版本、锁、公共合同或鉴权改动。第一冻结8文件：`frontend/src/App.tsx`、`App.test.tsx`、`components/status.tsx`、`styles.css`、`app/workspace-navigation.ts`与测试、`features/preparation/capability-workspace.tsx`、`frontend/e2e/r17_hacker_workspace.spec.ts`。

近黑绿青研究工作台、10核心导航、hash恢复、未知页面返回；保留运行概览/登录/真实健康状态的原行为。来源/事件/证据等未冻结DTO前仅展示已知能力缺口与信息结构，不发送猜测请求，不注入样本/统计。查询禁用且说明原因；图谱/问答/资产/任务/变化/报告都有具体依赖和核查上下文。unknown、partial、stale、未配置、待接通、待人工分别有中文状态。

用户动态背景要求在第一冻结后到达，第二冻结已实现AmbientBackdrop与2单测、动态browser用例；不把第一冻结称已含动态背景。低对比SVG拓扑与光域缓慢漂移，15装饰DOM、非业务进度、pointer-events:none/aria-hidden/reduced-motion停；document.hidden监听暂停。移动端所有准备页的缺口说明移出横滚table，新增Range每行 bounds断言。

## 实际命令与结果

实际命令、起止时间（秒+08:00）、退出码和原始日志见 `reports/runs/recovery_hacker_ui_20261015/commands.jsonl`，npm-ci另有JSON。

| 命令 | 结果 | 范围 |
|---|---|---|
| `npm ci` | exit0；原锁安装；报告3项既存依赖漏洞（1moderate/2critical） | 未升级；Vitest4主版本变更CR-R10仍由主控协调 |
| `npm run test -- --run` | 子进程exit0；60 passed/0 failed/0 skipped；6files | 42原回归+18新增；fixture组件不算live |
| `npm run lint` | exit0 | 全前端现范围 |
| `npm run typecheck` | exit0 | TS strict |
| `npm run build` | exit0；32modules；JS 172.63kB/gzip56.08kB，CSS14.09kB/gzip3.79kB | 编译不等于可用性 |
| CBM narrow indexes/traces | exit0 | frontend/src及backend/src/ai_intel/api，独立cache，不含秘密/holdout/reports |
| `git diff --check` | exit0 | 已冻结8文件 |
| 第一冻结5 real browser | 10:31:54–10:32:11+08:00；exit0；expected5/failed0/skipped0/flaky0 | 前端fa57874、真实PG默认API4bab166；trace/video/自动输入截图off；artifact secret scan0 |
| 动效冻结`npm run test -- --run` | exit0；62 passed/0 failed/0 skipped，7files | 原42+20新增；新增hidden事件组件单测不算原生隐藏页实测 |
| 动效lint/typecheck/build | 均exit0；33modules，JS173.86kB/gzip56.57kB，CSS15.39kB/gzip4.20kB | 无新依赖；生成tsbuildinfo恢复 |
| 第二冻结6 real browser | 10:41:47–10:42:02+08:00；exit0；expected6/failed0/skipped0/flaky0 | 前端00a5c99、后端4bab166；原3auth+2研究导航+动态/粗性能；artifact secret scan0 |
| 原生隐藏页探针 | 成功执行但visibility仍visible，实际隐藏验证blocked | headless1248及已安装Edge155专用headed；记录0未伪造hidden通过 |
| `git diff b099483 HEAD --check`完整证据范围 | exit2；6份npm原始日志末尾空行告警 | 原始日志保持字节，不改数据或加全局ignore；`full-evidence-diff-check.log` |
| 同命令限定源码/测试/设计/任务报告 | exit0 | `source-document-diff-check.log`；排除原始记录的范围明确，不把全范围写passed |

证据辅助问题：首次安装日志路径以frontend为cwd误建空目录，重定向失败，npm尚未执行；纠正根路径后真实npm ci通过，错误空目录已删除。首次证据runner在GBK终端打印✓发生UnicodeEncodeError（runner退出1），其子进程测试exit0与60测试日志已保存；随后runner stdout改UTF-8。独立visibility探针最初默认browser cache缺失，随后环境变量在ESM静态import后设置仍失败；改为import前注入已有非secret缓存路径通过。headed缓存只装headless，因此首headed缺执行文件；改用已经安装的Edge，不下载。成功探针仍未取得真实hidden，全部日志保留，不当作通过。build修改了生成tsconfig.tsbuildinfo，已逐字节恢复基线，未提交越界生成文件。

## 六层与外部/人工状态

| 层 | 当前状态 | 证明边界 |
|---|---|---|
| unit | passed | 16导航边界+2背景生命周期；无需真实网络 |
| contract | passed（既有回归） | 19 API客户端合同；没有新业务DTO已接通声明 |
| integration | passed（本切片范围） | 真实PG默认API经过browser登录/重载/退出与health；未改后端，不重复冒称PG事务全套 |
| security | passed（本切片范围） | 同会话快照/身份清除/秘密内存/旧请求；真实Cookie/CSRF/撤销与artifact secret0；无新token保存 |
| frontend | passed | 62fixture测试及lint/typecheck/build；与unit/contract/security有重叠，不相加伪造总数 |
| e2e | passed（本切片范围） | 先固定5，新增改动后固定6；无skip/flaky，非业务来源闭环 |
| live | passed仅auth/health；业务blocked | 真实PG认证与health观察；来源/模型/FOFA业务仍blocked_live |
| manual | blocked（原生隐藏页）；视觉检查已执行 | 作者与主控实际查看1280/390；作者CUA实际渲染；独立UI验收仍由新非作者完成 |

## 合同/计划偏差、评分证据和下一步

R17提前仅做独立UI准备；R04–R16业务接口前置仍阻塞整R17。schema_version冻结为数值2，草案中的字符串1.0已被主控纠正，未落业务代码。主控已冻结`docs/decisions/CR-R04-R04_read_api_projection.md`与`backend/src/ai_intel/api/knowledge_contracts.py`，作者直接完整读取；source_count/freshness/display_value、九维与null历史时间按该规则下一切片对接。外部参考的冲突取T1、9类别/写死工具数、3D及UI新栈不采纳。

D2：真实调研、中文研究界面、导航/状态与固定六browser；F1/F2/F3仅页面结构准备，无新业务能力或指标验收。实际截图见run内`e2e-dynamic-artifacts`：runtime1280、events1280、events390、ambient-frame-a/b（截图不含输入密码），`ambient-observation.json`保留真实计算状态和60帧粗测：约999.9ms/p95约16.70ms/max约16.80ms/0 observed long tasks/主内容bounds不变。该1秒粗测不替代正式性能。第一版本390说明裁切已修并在新截图和Range负例通过。下一切片：新独立UI审查→按冻结列表/detail/evidence DTO并行实现R04页面链。无需重新批准普通实现；未经独立review不accepted。

未检查：真实来源/模型/资产/图谱/任务/推荐/报告完整业务、正式评测、持续运行、独立review；原生hidden页面暂停仍待可产生真实visibilitychange的浏览器环境，不改测试分母补足。风险：准备页面不是完整平台；既存依赖漏洞由CR-R10处理，未用主版本升级回避。临时Vite25300 session46219已主动停止，确认无25300 listener；专用浏览器关闭；未操作其他API/worker/daemon。

## R04 前端只读切片独立交付

状态仍 `awaiting_review`；整R04/R17均 `partial`，无作者accepted。源码基于cafbe，在原WT的独立分支 `codex/recovery-r04-ui`：业务 `2363fc4389ee80500a06bd73b7e37f9e374a9458` → 测试观察修正 `6e42c9242e8af067ee14e39c585e801220ab0dd7` → 最终源码 `471c54760e8fe016fcd26aca89d17a334d7b0303`。未push。单独skip-link修复bb3a/90da在另一WT供非作者审查，未静默混入本源码；主控集成需叠加已审修复。

直接读取主控 `099c5b1af4cea9df9f6c72894ee36782b7f4c8c3` 冻结投影；c41b5a8只补pure unit不改接口。三条GET接线代码齐备：事件列表筛选/opaque分页、九维详情/断言状态/历史修订、指定版本证据检视。严格schema2与字段/状态校验；available无citation、URI不安全、版本不匹配、错误负载均作为合同错误。没有新增依赖/主版本/锁、没有后端/公共schema修改，也无运行时fixture入口。

列页200空、404未接通、403无权限、503失败、422 unsupported_filter分别解释，不默认绿/空或伪造CVE/总数。维度缺失、模型假设、时效过期、历史时间/URI缺失均可见。桌面侧栏sticky、手机单列；引用取得后焦点与视口定位证据，instant不平滑；加载/错误不抢焦点。原文用React文本，没有HTML注入。

主控明确授权必要AuthContext内部动作：新增sessionGeneration、isSessionCurrent、expireSession。请求开始generation不匹配就丢弃晚到200/401；组件key含user/tenant/permission/data_mode/generation以清私有数据。当前业务401直接清客户端身份和内存CSRF，给重登入口；不重取me制造循环，不声称服务端Cookie已撤销。旧logout晚到不会恢复/清掉新身份；logout失败仍保留撤销未确认。新增6auth测试内含3fence回归；事件UI覆盖旧会话200/401迟到与当前401。

### 文件清单与调用方影响

15源码/测试文件：`frontend/src/App.tsx`；`api/client.ts`（仅导出现有fetchJson）；新增`api/knowledge-client.ts`与测试、`api/knowledge-contracts.ts`与测试；`app/auth-session.tsx`与测试；`app/workspace-navigation.ts`与测试；`components/status.tsx`；新增`features/events/event-workspace.tsx`与测试；`styles.css`；新增`frontend/e2e/r04_fixture_contract.spec.ts`。完整逐文件LF哈希绑定在run内 `r04-evidence-summary.json`。

复用fetchJson的Cookie/no-store/timeout/公开错误清洗、既有AuthProvider、StatusBadge/ErrorPanel/EmptyState、React/CSS和hash导航。必要新增仅三GET的类型与边界解析、事件组件和生命周期fence；未造通用repository/router/design-library。客户端增导出的fetchJson是唯一传输IO，不复制timeout逻辑。AuthContext新增内部字段会影响其调用方，原登录/退出和运行状态回归在最终源码全套106测试中保留。

CBM0.11.0重新索引仅frontend/src，独立cache `/tmp/dianzi-cbm-r04-ui-20261015`、persistencefalse，151nodes/505edges，partial0；fast模式按设计未索引9测试文件，未读秘密/holdout/reports。trace+源码rg交叉核实：App→Workbench→EventWorkspace→getEventList→fetchJson/parseEventListResponse；EvidenceInspector→getEvidence→fetchJson/parseEvidenceResponse。新增AuthContext在事件调用处捕获generation；公共API模型只读对照。源码图不能替代测试。

### 真实命令、失败和复跑

完整argv与Asia/Shanghai秒级起止/退出码在commands.jsonl；均使用原锁Node24.13.1/Vite6.4.3/Vitest3.2.7/Playwright1.64.1、已有Chromium156 headless revision1248，无下载。固定frontend25302由主控授权独占，25300/25303不触碰。

| 实际命令与源码 | 实际结果 |
|---|---|
| `npm run test -- --run`，2363前完整检查 | 11:31:09–11:31:20，exit0；106passed/0failed/0skipped、10files |
| `npm run lint` / `npm run typecheck` / `npm run build` | exit0；最后471对应lint11:36:51–53、typecheck11:37:16–19、build11:36:57–11:37:00 |
| `npm run test -- --run src/features/events/event-workspace.test.tsx`，471引用修复前检查 | exit0；13passed，含真实DOM焦点断言 |
| `npm run test -- --run`，最终471全回归 | 11:39:22–11:39:32，exit0；106passed/0failed/0skipped，10files |
| `node node_modules/@playwright/test/cli.js test --reporter=json --output=<隔离证据目录> r04_fixture_contract.spec.ts`，2363 | 11:32:41–48，exit1；3passed/1failed/0skip/flaky；错误预期启动me次数1，StrictMode实际2，首失败完整保存 |
| 同4browser，6e42新label | 11:34:00–08，exit0；expected4/unexpected0/skipped0/flaky0；延迟401后对比初始/结束me2→2、events2→2，要求仍是无恢复循环 |
| 同4browser，最终471新label | 11:37:24–31，exit0；expected4/unexpected0/skipped0/flaky0；1366x900/390x844引文focus/viewport、无整体横溢出、文字每行Range、delayed503、401全部通过 |
| CBM source-only index + list/evidence trace | exit0；日志各自固定label |
| `r04_evidence_summary.py` | exit0；15源码文件逐字节LF核对冻结SHA，3browser批次保留；R04日志四类credential-shaped pattern命中0；这不是root的known-secret片段扫描 |
| `git diff --cached --check`证据范围 / 源码与文档范围 | 证据exit2：14原始日志EOF空行与6Playwright自动error-context空行尾空格；原始字节保留。限定源码/设计/任务报告exit0，不加ignore，不声称证据全范围passed |

401首次失败不是业务通过，不删/skip，也不覆盖旧记录。修正用delayed401在起始快照之后比较数量，不把StrictMode双effect当额外401循环；最终attachment保留完整计数。所有fixture请求由e2e进程拦截并严格白名单路径，不访问真实账号/来源；截图可见“合成 / Fixture”与隔离标题，不计真实数据。没有输入密码页面截图、trace或video。实际查看第一轮和最终1366/390渲染截图；最终路径在run的 `r04-fixture-focus-final-artifacts`，另有503手机图。测试不填充产品mock；真实API失败按其状态展示。

### 本批六层与外部缺口

| 层 | 状态与边界 |
|---|---|
| unit | passed：generation/导航边界/Unicode等；属于106集合，不能叠加重复计分 |
| contract | passed：18 DTO +9 transport隔离回归；主控确认next_cursor非null必须非空并安排模型min_length1小补记，前端未改公共合同 |
| integration | passed仅fixture客户端→React组件；真实PG/持久化R04读链not_run |
| security | passed仅本批隔离fence/错误/文本渲染/URI回归；新AuthContext扩展还需受控真实会话复核，不外推旧00a实测 |
| frontend | passed：最终106与lint/typecheck/build；36modules，JS196.51kB/gzip62.67kB、CSS19.08kB/gzip4.88kB；不是性能达标声明 |
| e2e | passed仅4隔离fixture browser；首失败仍保留；R04真实API browser not_run |
| live | blocked：主控业务路由/真实事件/版本/证据链尚未接通；不把fixture当live |
| manual | 1366/390截图作者实际查看；独立review待主控安排；此前原生hidden页缺口仍blocked |

下一受控真实依赖：GET事件列表按冻结cursor/q/risk/updated_after返回有效投影，product不支持422；GET可见事件详情与该citation历史版本证据；真实会话权限401/403/404与503正确返回。root接通后安全runner注入已有隔离账号，源码固定复核，新label保留日志。来源数据的真实支持、PoC/模型/FOFA、多跳问答、图谱/任务/资产/报告、正式评测和持续运行不在本批通过范围。R04准备不是整平台交付；待审状态不代替最终验收。


## 独立评审 P2 修复：skip link 保留当前工作区

新非作者评审实证：00a5c99在`#events`聚焦skip link按Enter会改为`#main-content`，路由解析误回runtime。既有六browser只在默认runtime检查skip，因此未覆盖此边界。修复单独WT `C:/Users/yinha/.codex/worktrees/hacker-ui-skip-fix/dianzi`，从cafbe证据基线建`codex/recovery-ui-skip-link`，不重置或混入仍在开发的R04 App/client改动。

代码冻结 `bb3a3b3d4b3f40c88633adba1ae131db03bb2480`：仅App skip link阻止锚点默认导航并focus主内容；App新增event/source两组件断言；新增`frontend/e2e/r17_skip_link.spec.ts`两匿名真实键盘回归。没有路由依赖、鉴权或公共合同变化。

实际日志：`skip-component-test`64 passed/0 failed/0 skipped（原62+2），lint/typecheck/build均exit0。首匿名browser在25300被strictPort阻止，exit1、expected0，为端口被独立reviewer使用的环境阻塞，未启动或停止reviewer进程；该日志完整保留。主控分配25302后，对同固定bb3a版本在11:11:10–11:11:15+08:00实际执行2browser，exit0、expected2/skipped0/unexpected0/flaky0：event/source路由不变、main被focus、h1不变、随后Tab可到刷新按钮。仅GET同源真实PG默认API28000，无账号和POST，不需Origin写白名单；无trace/video/自动截图。

六层范围：unit/frontend=64测试passed；contract/security=既有原样19客户端/认证回归passed，无新权限变化；integration/e2e=本匿名键盘路径2browser passed；live=仅真实authme/health入口被浏览器使用，不是R04业务；manual=原生hidden缺口仍blocked，P2等待原非作者定向复核。整个R17仍partial，作者仅awaiting_review，不accepted。

`npm ci`退出0并报告已有3依赖漏洞及lockfile reify warning；锁文件未变化，不执行force fix。实际版本仍原锁。新固定输入和source-only CBM索引记录见skip前缀日志；缓存不含报告/秘密/holdout。25302 runner自动退出后释放端口；未操作其他daemon。下一步：原reviewer定向复跑并由主控登记，R04活动分支随后单独合并这3文件补丁，保留其业务未冻结diff。


## 2026-10-15T12:00:19+08:00 · 主控证据集成记录

R04与skip作者从同一基线并行追加报告/commands，cherry-pick产生这两处文档冲突，主控保留两段历史并按真实started_at合并JSONL索引。原作者文件字节完整保存在本run author_frozen/，原manifest仍对应其冻结作者SHA/原文件，不能冒称其hash验证这个合并副本。ui_evidence_merge_receipt.json逐项记录源Git blob内容hash和当前合并hash。没有改任何产品源码或原命令/计数/失败，当前R04界面108集成回归及独立review状态另见其新冻结证据。
