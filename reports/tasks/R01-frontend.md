# R01 · 认证工作台前端切片

文档首次创建时间：历史未记录（2026-10-14T22:51:25+08:00是创建前实际时钟采样，不当作已知创建时刻）。
本次写作开始时间：2026-10-14T22:51:25+08:00；写作结束/最后更新时间：2026-10-15T00:17:46+08:00。
实际实施开始时间：2026-10-14T22:24:19+08:00；本轮代码编写结束：2026-10-14T22:54:41+08:00；真实e2e仍未开始。
状态：awaiting_review；实现状态：partial（当前前端代码已自检；真实 API 浏览器链尚未运行）。
实现 Agent：/root/r01_frontend；独立审查：尚未发生。
工作分支：codex/recovery-r01-frontend。
输入基线：69ecf16be7d95e839b18a4a40f03b3f9d86707f4。
已审代码 SHA：尚未发生；提交/推送：本包不自行 push。

## 1. 范围与实际行为

本包实现 R01:T40 的早期认证、运行状态与布局切片，不验收整 T40。T40 仍需 R04 实际证据业务与 R17 完整工作台。HTTP 合同来自主控冻结的 R01 报告：`/v1/auth/login|me|csrf|logout`、`/v1/health/live|ready`，Cookie credentials include、会话绑定 CSRF 内存、RFC9457 公开错误摘要。

以前 App 只有“未连接”骨架。现在页面实际调用 health/auth；登录后必须读取服务端 /me 身份、租户、四角色、权限、权限版本与 live/fixture 模式。原版刷新从 me→csrf 恢复（此双请求缺陷已由独立审查确认）；本次改用同一次 /me 身份与CSRF原子快照恢复，退出立即清除前端身份/权限及内存 CSRF；网络撤销失败明确写“未确认”，不能显示假成功。请求代次防止旧恢复响应重新填入已清除身份。用户名/密码表单提交后清除，未使用 localStorage/sessionStorage。

健康 503 的 not_ready/degraded 结果作为真实逐项探测呈现，不转换成空列表；网络/格式失败展示未知与重试。存活、依赖、数据模式分别显示，不以“live 模式”证明所有业务 live。未知、过期、部分、未配置与就绪均有文字区别。当前仅导航到实际运行状态/会话区域，不添加尚未接线的来源、问答入口。

## 2. 复用与必要新增

复用 React18、Vite6、浏览器 fetch/AbortController/HttpOnly Cookie、现有 Vitest/Testing Library。未增加 UI 框架、路由库、图标包、状态管理包或外部字体。新增严格 API 解析器、认证 context、三个实际使用的状态/错误/空态组件、可读中文布局 CSS、针对行为的测试与真实浏览器脚本；这些分别承接认证信任边界、刷新/退出竞态、实际错误交互和 T40 浏览器操作要求。

应用最新本机 Ponytail5.2.0 full 与工业 UI 技能中的 Swiss Print 方向。使用纸白、墨黑、警示红分隔、平面网格与可读中文，未采用技能中的随机遥测、装饰编号或商标字符。实际只读访问并观察 [GitHub Advisories](https://github.com/advisories) 与 [OSV](https://osv.dev/list) 的搜索/过滤与列表层级；学习其信息层级，不复制页面商标、漏洞数据或数量。访问为只读，没有向第三方提交项目材料。

## 3. 文件所有权与调用链

本包修改：`frontend/src/App.tsx`、`App.test.tsx`、`styles.css`、`api/client.ts`及测试、`app/auth-session.tsx`、`components/status.tsx`及测试、`frontend/tests/t40_frontend_shell.test.tsx`、`frontend/e2e/r01_auth.spec.ts`、`vite.config.ts`、`playwright.config.ts`、本报告及专属 runs。

主控唯一所有人：package.json/package-lock.json/tsconfig.json/index.html/后端/合同/状态/CI。主控为验证复制的依赖配置不纳入本 Agent commit。build 生成的既有跟踪 tsbuildinfo 不作为实现交付。

当前代码 CBM 独立 cache `/tmp/dianzi-cbm-r01-frontend-20261014`、project `dianzi-r01-frontend`，仅 frontend/src，刷新结果 66节点/197边、0未索引。`getCurrentUser ← AuthProvider ← App` 与 `getCurrentUser→fetchJson/parseCurrentUser→验证/公开错误` 有实际图证据；与 rg、main.tsx 的 createRoot→App 交叉核实。初始3文件索引10/13，App图无边但源码确实渲染，未以缺边宣称无入口。源码逐文件 SHA256 绑定见 [cbm_commands.json](../runs/recovery_r01_frontend_20261014/cbm_commands.json)，查询和 rg 原始日志同目录。不存在秘密/holdout/无关资料索引。

## 4. 验证与配置版本

每条命令的实际开始/结束时间、cwd、exit、依赖锁/配置 hash 见 [专属 run](../runs/recovery_r01_frontend_20261014/)。fixture 均显式命名、data_mode=fixture，与 e2e 脚本分开。API 客户端本身没有 fixture 分支。

| 验证 | 实际结果 | 证据/限制 |
|---|---|---|
| 先写的 T40 行为测试对旧 App | exit1；8/8真实失败 | initial_red.log/json；均缺少认证/状态交互，不是环境失败 |
| 初轮 frontend | exit1；20项18通过2失败 | test_1；两个 selector 错误，保留原失败，不 skip |
| 首轮冻结 frontend/unit | exit0；30/30、0失败/0skip、4文件 | test_5；10行为+13HTTP边界+6状态+1骨架回归，计数只相加一次 |
| 合同 | 13 HTTP 边界 fixture passed | 已计入30，不能额外重复计总数 |
| security | fixture安全行为 passed；真实权限/租户 integration not_run | CSRF头、无存储、错误文本、原型键、过期与旧响应负例，不证明 PG 服务权限 |
| npm run lint | exit0 | lint_5 |
| npm run typecheck | exit0，包含 src/tests/e2e/两配置 | typecheck_5；使用主控复制的候选依赖与tsconfig |
| npm run build | exit0；30模块、JS159.84kB/CSS8.66kB（gzip52.01/2.47） | build_4；构建大小不能当性能延迟 |
| npm ci --no-audit --no-fund | exit0，首次303包/主控候选308包 | 工具真实输出；起止未独立保存，明确历史未记录；npm提示lockfile warning待主控处理 |
| 浏览器只读负例 | 真实Vite→28002尚无API，ECONNREFUSED，页面未知/未登录/重试可见 | 2026-10-14T22:47:19+08:00实际观察；非认证成功/e2e验收，无密码输入 |
| 浏览器 e2e | not_run；3个真实脚本已编写；`npm run test:e2e -- --list` exit0仅发现3、执行0 | e2e_discovery；JSON listing把3记skipped，属于只列出未执行，绝非3通过；需独立API28002和预创建账号，脚本不route/mock、不skip、trace/video/失败自动截图off |
| live / manual | not_run | 无模型/来源/人工验收声明 |

实际候选依赖：Node24、Playwright1.64.1、@types/node24.19.2、React18、Vitest实际3.2.7、Vite实际6.4.3。锁 SHA256 `DBE6798B1130C291D11CE7C3E3B93D1B26710A2CB2841EF9EA9E223355FFD29C`；此主控候选锁/tsconfig尚未包含在本 Agent 业务冻结提交里，最终主控需合并后在一致候选 SHA 重跑。不能把本分支旧依赖 HEAD 当作上述全部验证对象。

## 5. 问题台账

| ID | 触发、预期与实际 | 根因/影响 | 修复与复验/状态 |
|---|---|---|---|
| FE-R01-01 | 旧 App 登录/刷新/退出/断线8场景，应可操作，实际仅骨架 | 未连接HTTP；阻断R01认证UI | 新共享客户端/context/UI，30fixture passed；真实e2e待API |
| FE-R01-02 | 初轮 heading名带隐藏点、degraded同文本两处，测试应正确定位，实际2失败 | 测试选择器错误，不是产品行为缺失 | 改为可访问名/复数匹配；test_2 exit0，未改金标/分母 |
| FE-R01-03 | import node:process，strict类型应通过，实际TS2307 | 原锁缺@types/node；Vite/Playwright配置依赖 | 主控锁并复制候选；typecheck_5 exit0，本Agent未自行改锁 |
| FE-R01-04 | 并行静态检查的Vitest，应有限执行，实际VirtualAlloc failed/exit1/0完成 | 默认worker与当前宿主并发负载；环境资源失败 | Vitest maxWorkers1/fileParallelism=false，test_5 30/30；原失败test_4保留 |
| FE-R01-05 | 外来错误码constructor/依赖名__proto__/未知状态，应普通数据，原Record查表可读取继承属性 | JavaScript原型查表边界；可能崩溃/错误显示 | Object.hasOwn与标准Object.fromEntries，三个针对性负例通过 |
| FE-R01-06 | 服务端 session_expired，应清私有身份并说明失效，最初统一401静默转登录 | 初始化未认证与失效语义未区分 | 保留expired公开说明，新增刷新清用户/租户/权限负例通过 |

复验日志各带实际发现/执行时间；编码历史首次发现瞬间未独立记录，不用文件mtime倒推。尚未关闭：主控依赖audit/lock警告处理、真实API认证e2e、R02持久化、R04/R17完整业务。没有发现金标/门槛差异，本包不改评分。

## 6. 浏览器真实运行契约与下一步

专用前端127.0.0.1:25173，严格端口，Playwright自行启停Vite，不复用用户开发服务。API_PROXY_TARGET默认127.0.0.1:28002（本worktree专用实例）；root演示28000需显式环境配置。后端允许Origin必须对应前端25173。e2e凭据仅受控环境 `DIANZI_E2E_USERNAME`/`DIANZI_E2E_PASSWORD`，不写日志、报告或提示词。只在认证后的测试工作台截图；密码输入不录制。

主控合并并冻结含正确依赖/后端/前端的候选→新未参与实现reviewer审查→真实API启动并运行三个浏览器流程→修复/复核。原T40的EvidenceLink/业务TaskStatus与实际来源/详情在R04/R17接真实数据后继续，本包不创建 unused 空组件凑整卡完成。

## 7. 修订记录

2026-10-14T22:51:25+08:00：/root/r01_frontend 首次记录当前代码、自检证据、真实未运行层、共享候选依赖范围和问题；尚未独立验收。

2026-10-14T22:56:18+08:00：补e2e listing只发现不执行的真实计数与未运行说明；验证25173没有本Agent遗留监听，临时只读浏览器已关闭。没有把listing skip改成验收通过。

2026-10-14T22:57:49+08:00：纠正首次创建时刻字段：此前误把创建前的时钟采样当作文件创建，现明确历史未记录，不从文件mtime推造；首次写作前采样与全部实际测试日志保留。

## 8. 独立审查后的原子会话定向修复

本次写作开始时间：2026-10-15T00:14:17+08:00；独立审查依据：G-A-R01-behavior-review-1，固定候选4a17ca7b967a10d6077ba5219984a2d1a74cf320。前端修复输入基线b07596cbe6082051bb55bac39f7b5df7020be68c，状态awaiting_review；未自行签accepted。主控提供兼容合同：/me保留原字段，增加同一session的csrf_token；后端由主控实现，本Agent未修改后端或公共合同。

### 真实问题、最小修复与限制

RV-03：A的/me返回后，其他标签登录B更换Cookie，旧/csrf取到B的nonce；页面显示A租户而用B nonce注销B。请求代次只能识别本组件请求，不能绑定不同HTTP响应。修复新增getSessionSnapshot，在单个/me响应内严格解析CurrentUser与非空CSRF，AuthProvider只把user放上下文、CSRF放ref。恢复没有/csrf fallback。登录后的确认也用同一snapshot，避免同用户被其他会话换Cookie时混用登录响应nonce。getCurrentUser/getCsrfToken仍保留现有辅助调用合同（client.test有直接调用），未删公共入口。

3个新增行为例先在旧实现真实3/3失败：跨用户Cookie切换导致B被注销；同用户换session后仍用旧nonce；缺失/me nonce却用第二请求fallback。修复后全部通过。跨用户例模拟/me读取A时的完整快照后Cookie已经B，验证发出的只能是A nonce、服务端拒绝当前B会话写入、B不被误注销、前端清除身份。单请求快照不能让任何时刻的显示自动感知其他标签后续变化；其保证是读取时身份/nonce一致，后续Cookie切换的写操作由服务端会话绑定CSRF拒绝。没有声称自动跨标签广播、真实资产跨租户读搜导出或真实浏览器已验收。

RV-05：client与直接相关T40测试的固定合成nonce被既有T06-C06扫描命中。已使用Node标准crypto.randomBytes(32)生成测试nonce并复用到输入/断言，没有拆字符串、改扫描、放宽正则或阈值。新的snapshot检查5种缺失/非法nonce，且不把CSRF暴露到公开user上下文。测试nonce不是模型/API/账号凭据，不读秘密库。

### 实际验证

| 命令与工作目录 | 结果 | 证据与边界 |
|---|---|---|
| frontend：npm run test -- --run src/app/auth-session.test.tsx，修复前 | exit1，3 failed，0skip | atomic_restore_red.log/json；有意义行为失败，不是import或资源错误 |
| frontend：npm run test，修复后 | exit0；39 passed/0failed/0skip、5文件 | atomic_test.log/json，保留原30＋新增9；19HTTP＋3快照＋10T40＋6状态＋1回归 |
| frontend：npm run lint / typecheck / build | 各exit0 | atomic_lint/typecheck/build.log/json；build30模块，JS159.78kB、gzip52.00；不是性能测量 |
| backend：原T06-C06定向scan（候选WT的Python环境，仅指向本WT源码） | exit1；1failed | atomic_secret_scan.log/json；未改scan标准，失败在旧caller日志复制了旧fixture字面量，而非新源码nonce。完整security未通过，待主控处理历史证据与scan冲突；保留失败 |
| CBM刷新+trace+rg | exit0；74节点/224边 | atomic_index_after/atomic_trace_after/atomic_rg_after；getSessionSnapshot←AuthProvider←App，旧辅助不再由AuthProvider调用，源码逐文件hash在atomic_index_after.json |

全部命令实际起止、cwd、exit、依赖锁hash由执行过程落盘；不根据mtime推造时间。依赖仍主控候选配置，本Agent未改package/lock/tsconfig/全局配置；本WT源码SHA与候选依赖hash分别报告。构建仅还原本次产生的既有tsbuildinfo，不覆盖主控复制配置。

各层：unit/frontend=passed（39fixture），contract=passed（19HTTP fixture且已包含于39），security=failed（定向原scan的历史证据命中；不是实密钥泄漏证据），integration/e2e/live/manual=not_run。本包未跑真实浏览器多标签/PG/外部模型来源；主控修后端并冻结一致候选后，仍需独立reviewer定向复核及浏览器验收。

### 当前证据冲突与下一步

recheck_rg_before.log保存修改前真实源码，含此前明确合成nonce赋值文本；原scan把历史rawlog文本再次当作当前凭据赋值，随后scan失败日志也回显该匹配。已向主控报告，未删除日志、改扩展名规避扫描、改扫描标准或把失败改skip。后续caller日志记录新动态nonce源码，没有原固定值。主控明确历史源码证据的保存/扫描规则后处理，不把39frontend通过替代安全门。

改动文件仅api/client.ts、app/auth-session.tsx、两者直接测试、tests/t40_frontend_shell.test.tsx、本报告与专属run。复用现有fetch/解析器/context和Node标准crypto，没有新依赖、通用框架或虚构节省数量。主控独立reviewer定向复核之后才能集成/登记通过。
2026-10-15T00:14:17+08:00：追加RV-03/RV-05定向修复、39测试证据和历史rawlog扫描仍失败的边界；保留原报告/失败记录，未改评分或扫描标准。

2026-10-15T00:17:46+08:00：主控要求保留原始历史log、不再重复执行C06。已枚举原两个正则在专属run的全部命中，synthetic_occurrences.json包含2文件/7实际行/11重叠pattern命中/0未分类，以及完整路径、原始字节SHA256、行号、data_mode=fixture、b07596c源码blob和源行。主控与非作者reviewer核对局部hash分类后再修安全根因；本Agent未更改原日志、全局scan规则或验收状态。
