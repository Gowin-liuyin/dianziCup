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

## 独立评审 P2 修复：skip link 保留当前工作区

新非作者评审实证：00a5c99在`#events`聚焦skip link按Enter会改为`#main-content`，路由解析误回runtime。既有六browser只在默认runtime检查skip，因此未覆盖此边界。修复单独WT `C:/Users/yinha/.codex/worktrees/hacker-ui-skip-fix/dianzi`，从cafbe证据基线建`codex/recovery-ui-skip-link`，不重置或混入仍在开发的R04 App/client改动。

代码冻结 `bb3a3b3d4b3f40c88633adba1ae131db03bb2480`：仅App skip link阻止锚点默认导航并focus主内容；App新增event/source两组件断言；新增`frontend/e2e/r17_skip_link.spec.ts`两匿名真实键盘回归。没有路由依赖、鉴权或公共合同变化。

实际日志：`skip-component-test`64 passed/0 failed/0 skipped（原62+2），lint/typecheck/build均exit0。首匿名browser在25300被strictPort阻止，exit1、expected0，为端口被独立reviewer使用的环境阻塞，未启动或停止reviewer进程；该日志完整保留。主控分配25302后，对同固定bb3a版本在11:11:10–11:11:15+08:00实际执行2browser，exit0、expected2/skipped0/unexpected0/flaky0：event/source路由不变、main被focus、h1不变、随后Tab可到刷新按钮。仅GET同源真实PG默认API28000，无账号和POST，不需Origin写白名单；无trace/video/自动截图。

六层范围：unit/frontend=64测试passed；contract/security=既有原样19客户端/认证回归passed，无新权限变化；integration/e2e=本匿名键盘路径2browser passed；live=仅真实authme/health入口被浏览器使用，不是R04业务；manual=原生hidden缺口仍blocked，P2等待原非作者定向复核。整个R17仍partial，作者仅awaiting_review，不accepted。

`npm ci`退出0并报告已有3依赖漏洞及lockfile reify warning；锁文件未变化，不执行force fix。实际版本仍原锁。新固定输入和source-only CBM索引记录见skip前缀日志；缓存不含报告/秘密/holdout。25302 runner自动退出后释放端口；未操作其他daemon。下一步：原reviewer定向复跑并由主控登记，R04活动分支随后单独合并这3文件补丁，保留其业务未冻结diff。
