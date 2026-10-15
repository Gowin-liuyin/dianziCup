# R04 / R06 / R17 · 固定来源与单页任务工作区

状态 `awaiting_review`；本前端实施切片已实现，整R04/R06/R17仍 `partial`。作者 hacker_frontend；非作者初审、真实管理员API/worker来源链仍待主控安排。不自行accepted、未push、未更新global progress或阶段文档。

独立WT `C:/Users/yinha/.codex/worktrees/source-job-workspace/dianzi`；分支 `codex/source-job-workspace`；基线 `31c2866ff19227e5f6ee24f1f966660c0d4ba383`。业务源码 `c9331835525d7470fdd022b1250b8a473ec1d95c`，e2e调用方适配 `73e729db82404268871ff058cd3dcfd6a31bb32f`，最终源码 `fccc0b918c58b18e66e8eb67cbfc8aadd4c1fb62`（lookup422提示与1负例）。证据为后续独立commit。

## 范围、研究与设计

已读AGENTS、00执行索引、R04/R06/R17任务卡、06测试合同、31c冻结CR-R04_source_jobs、实际source_routes.py、source_jobs.py、worker jobs.py、SQL job状态约束及当前auth/client/event模式；progress仅作索引，未把旧G-A/未完成live当通过。完整重新读取用户外部ui-design参考，仍仅作不可信设计参考：复用近黑层次、青绿强调、中文正文与monospace数据；不采用新增栈、参考写死来源/工具数、虚假监控数字或自动冲突裁决。

现有暗色token、布局、动态图层、AuthProvider与共享状态组件先审计后复用。设计为两栏完整工作区：左侧两固定源说明、窗口/采集流/页数提交与冻结请求；右侧单页任务查询、手动刷新和PG结果。1100px以下单列，390px长ID/键/说明可换行。保留现有动态背景，未改全局styles、auth/client、事件或公共模型。没有新依赖、路由库、配置或锁修改。

本轮仅新增sources feature、source客户端/DTO及直接测试，唯一App装配和App.test调用方；主控另明确授权旧 `r17_hacker_workspace.spec.ts` 的sources分支断言适配。无任意URL/凭据/租户输入；无GET source history可用，因此不显示历史列表、监控总数、整源在线或采集完成率。

## API与行为

- POST `/v1/sources/{kind}/collect`仅`nvd_ollama`与`vllm_vendor`；JSON恰好window_end、stream_kind、max_pages。UI显式默认live和5页，支持1–20；这不改变服务端backfill/20默认。窗口必须是过去、带时区ISO，不是上游快照/时间覆盖保证。
- 每轮首次有效提交生成ASCII有界幂等键；先冻结来源、原始body/window/key，再读CSRF。getCsrfToken返回后、POST之前复核sessionGeneration/isSessionCurrent、unmount与abort；同一操作使用提交前捕获的不可变JSON/键。未知提交结果可原样重试；编辑锁定，“开始新一轮”显式重开，下次有效提交才新键。202仅为PG受理。
- GET `/v1/jobs/{uuid}`仅手动查询/刷新，校验返回job_id匹配。空输入不能提交；非法UUID解释清楚并允许修改，且不发管理API。无自动poll、任务历史或取消/批准接口。
- 两接口恰好解析job_id/status/attempt_count/error_code/result_ref/created_at/finished_at；无data_mode字段。模式仅从当前user.data_mode显示Fixture/Live；不把成功响应当来源online。未知字段、非法时间/状态、原始错误文字或URL引用拒为合同错误。
- 九状态逐一对齐SQL和worker：queued/running/retry_wait/succeeded/partial/failed/blocked/cancelled/waiting_approval。succeeded显示“本页处理完成”，明确后续页仍可能运行；partial、blocked与failed各有不同中文说明。结果引用/错误码复用worker的安全正则，文本用React渲染，不显示payload或原始异常。
- 仅角色system_admin且tenant_id=null可操作；匿名、普通角色、带tenant系统管理员都不发管理/CSRF API。401清客户端身份、无自动me恢复循环；不宣称服务端撤销完成。切页/unmount与新身份会丢弃晚到200/401；并发双提交由同步inFlight围栏阻止。
- 所有人类时间用既有formatShanghaiTimestamp显示+08:00秒；time.datetime保留原始值，null未知，不推测历史。错误/404/503不回填旧任务，不当作空或完成。

## 文件与调用方

11代码/测试文件：`frontend/src/App.tsx`、`App.test.tsx`；新增 `api/source-client.ts`及测试、`api/source-contracts.ts`及测试；新增 `features/sources/source-workspace.tsx`及测试、局部`sources.css`；新增 `e2e/r17_source_jobs_fixture.spec.ts`；定向适配 `e2e/r17_hacker_workspace.spec.ts`。

App将sources从CapabilityWorkspace接到SourceWorkspace，沿用现有sessionScopeKey。复用fetchJson Cookie/no-store/超时/公开错误、getCsrfToken、AuthProvider代次动作、ErrorPanel/EmptyState、date-time、全局token；没有复制传输IO、改公共auth或另建缓存。旧导航e2e原本所有来源身份都期待“本页能力待接通”，现仅sources分支额外读同会话me且仅返回role/tenant判断：无租户system_admin断言表单可用，其他断言拒绝且无提交按钮；不触发实际collect，其他页面/阈值/skip原样。

CBM0.11.0仅索引frontend/src，独立cache `/tmp/dianzi-cbm-source-job-ui-20261015`、persistence=false；基线153nodes/510edges，最终188/645、partial0，fast模式按设计不索引13测试文件；未读秘密/holdout/reports。实际trace与rg核实App→SourceWorkspace→SourceAdminWorkspace/runRequest→collectSourcePage→getCsrfToken/fetchJson→parseSourceJob，以及getSourceJob只读链。回查worker validate_job_result_fields与job_runs SQL，未仅凭域enum猜状态。图不替代测试。

## 命令与真实结果

完整argv、+08:00秒级起止与退出码见 `reports/runs/recovery_r17_source_jobs_20261015/commands.jsonl`。npm命令cwd为此WT/frontend，CBM/git为WT根。Node24.13.1、原锁Vitest4.1.11/Vite6.4.3/Playwright1.64.1/现有Chromium156 revision1248；未下载或改依赖。原旧WT锁不符时拒绝复制（未安装或修改它）；随后只读复制与31c完全相同SHA256锁的D:/dianzi/frontend/node_modules到独立WT并排除.vite，robocopy正常exit1；没有junction或共享运行缓存。首次progress脚本键与06路径错误只影响只读定位，纠正为recovery_tasks与06_testing_and_evaluation后完成阅读，不算业务失败。

| 实际命令/label | 结果 |
|---|---|
| `npm run test -- --run src/api/source-contracts.test.ts src/api/source-client.test.ts`，source-contract-client-first | 15:07:07–10，exit0；32passed，后补2非法日期+1冻结body测试在完整回归执行 |
| source-component-first：sources组件与App | 15:08:48–53，exit1；26passed/1failed；非法响应被泛化为普通查询失败的UI提示，已修职责分支，原日志保留 |
| source-component-format-fix，同27 | 15:09:14–19，exit0；27passed/0skip |
| `npm run test -- --run`，source-full-tests（c933前） | 15:10:54–15:11:07，exit0；177passed、14files、0failed/skipped；基线120+新增57 |
| `npm run lint` / `npm run typecheck` / `npm run build` | exit0；build15:11:04–08，41modules，JS211.17kB/gzip66.94kB、CSS21.86kB/gzip5.32kB；不是性能达标声明；生成tsbuildinfo原字节恢复 |
| 73e旧导航适配后typecheck / fccc关联lint/typecheck | 均exit0；最后lint15:16:13–15、typecheck15:16:16–18 |
| fccc追加 `npm run test -- --run src/features/sources/source-workspace.test.tsx` | 15:16:13–15，exit0；22passed。比177全套多1本地UUID负例；不伪称最终178全套已跑 |
| `node node_modules/@playwright/test/cli.js test --reporter=json --output=<本包artifacts> r17_source_jobs_fixture.spec.ts`，source-fixture-browser-first（c933） | 15:11:48–15:12:16，exit1；2passed/2failed/0skip/flaky。精确getByLabel未匹配嵌套select标签文本；实际ARIA combobox名称正确，改用同名getByRole exact，不改产品/阈值/skip |
| 同4browser，source-fixture-browser-role-fix（73e） | 15:13:24–31，exit0；expected4/unexpected0/skipped0/flaky0 |
| 同4browser，source-fixture-browser-final（fccc） | 15:16:22–29，exit0；expected4/unexpected0/skipped0/flaky0；1366/390、网络未知同键重试、新轮新键、partial/blocked/succeeded、权限/迟到CSRF、401均过 |
| CBM最终index、submit/job trace；源码diffcheck | exit0；逐命令有log；源码图188/645 |
| 证据范围 `git diff --cached --check` | exit2：13原始日志EOF空行+12自动Playwright error-context尾空格，保留原始字节；源码/任务报告/证据脚本限定检查exit0，无ignore，不能把全证据范围记passed |

本包运行Node heap配置`--max-old-space-size=384`，Vitest worker1；此为配置不是RSS测量。fixture webServer独占25302且每轮少于30秒，总计远小于20min；API代理指向未启动的25303，所有/v1由测试白名单拦截，未启动API进程、未触root28000/25300、未请求公网源/产品keys/付费模型。结束监听0；本包日志/artifact小于4MiB，最终容量另在evidence-summary记录。

## 六层、视觉与未运行边界

| 层 | 状态 / 限定 |
|---|---|
| unit | passed：纯校验、UUID/时间、安全码、冻结请求、并发/会话围栏；属于完整/关联集合，不叠加计数 |
| contract | passed：实际7字段、SQL9状态、固定写入字段/页数、Cookie/CSRF/幂等；fixtures不等于真实API |
| integration | not_run：未自行运行真实PG API/worker；组件客户端fixture集成已过，不能替代PG |
| security | passed仅隔离：匿名/租户禁发，CSRF过期、await后generation/abort、旧200/401、原文错误注入/脱敏、双提交、同键重试；实际管理员CSRF链待root |
| frontend | passed：177全套+fccc追加22相关、lint/typecheck/build；最终整个178未再跑 |
| e2e | passed仅最终4显式fixture browser，首失败保留；授权旧导航分支仅类型/静态验证，真实账号导航未运行 |
| live | not_run/blocked：真实admin POST→PG→worker→固定公网来源→GET→browser由root随后受控验证；本作者调用public source/模型/费用均0 |
| manual | 已实际查看最终1366x900/390x900渲染截图；新非作者review待安排；原生隐藏页既有缺口不归本包重测 |

最终截图在 `fixture-final-artifacts` 两个PNG，数据模式、隔离账号/UUID及请求结果均为显式Fixture；1366两栏、390单列无全局横溢出，描述/元数据每行Range bounds断言通过。大屏/手机窗口与created/finished显示+08秒，datetime保留UTC。背景只复用既有已审实现，截图没有密码页、trace/video或产品秘密。日志内fixtureCSRF由随机数在内存产生，未把实际token纳入观察附件；附件仅布尔值与计数。

无公共合同或计划偏移。D2/F1/P1仅此固定源调度与真实状态工作区的实现证据；不是八类来源/九通道广度、整源完成、持续监控、时效指标、全任务树或整个工作台验收。后续依赖：主控安排冻结fccc的非作者审查，再用安全runner和隔离网络/有界公开请求复核真实无租户管理员接口链；不因本包fixture成功开启公网采集或把blocked_live改passed。
