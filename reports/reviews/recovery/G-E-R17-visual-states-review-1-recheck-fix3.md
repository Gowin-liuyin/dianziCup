# G-E / R17 · 视觉与状态切片 fix3 定向独立复验

结论：本次 UI 源码切片 LimitedShip=true；未发现新增 Must fix，M01/M02/M03 原字节用例已通过，新65源码图与实际caller核查完成。CBM资源红原样保留，不能称全部工具/资源验证通过。整 R17 仍 partial，本报告不写 accepted，不更新公共状态、不 push。

## 固定范围与独立性

- 自己 worktree D:/wt/r17-fix3-review，分支 codex/r17-fix3-review，固定 material 434a7d8eafd77c07a09b7d21d0db514fda0cd957；唯一受测 source 6ed92b802a8126855dac3ce16d7c35e93305ff2b，父 material d4e678270eeaf74857886084460d854d4241ce04 / source 1a433f1305a11be25c93bcbeeb03eb4e5ca6cfd7。作者 WT D:/wt/r17-read404-fix3 只读。
- 产品差异仅 recommendation-workspace.tsx、新 recommendation-read404.test.tsx、经 Root 明确批准的 subscription-write404.test.tsx read 一分支期望。135 加 / 6 删；公开接口、后端、认证、合同、锁文件、金标、阈值、分母均无变更。source_diff.command/stdout 与 source_candidate.patch 留存逐行差异。source_fingerprints.json 同时给canonical Git blob及实际受测工作字节；新作者test在独审标准checkout为CRLF（working c183a3f8…），canonical仍2f726cdc…，只110个行结束差异，没有修改测试逻辑；原三oracle bytecopy不做此转换。
- 本审只写这个报告及 reports/runs/r17_fix3_review_20261017；没有业务代码修改。frontend/node_modules 与 ownrun/node_modules 是只读使用既有依赖的 junction，不提交；构建输出在独立 runtime cache。
- 已读本轮 AGENTS、00_execution_map、R17 恢复任务卡、05 API/故障合同、task_state.R17、黑客工作台设计与作者 fix3 报告；遵守用户当前定向复验授权。使用 Ponytail review 5.3.1：C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md，真实技能哈希见 review_scope.json。按正确性、安全、并发、测试、速度、必要性检查调用链；不报告无触发条件的风格意见。
- 并行辅助仅只读，不运行测试/CBM/浏览器。预期负载是单个已认证用户在当前浏览器会话按服务端分页读取本人目录；不从 fixture 外推吞吐或多租户产品验收。

## 三个原问题的复核

M01：所有订阅记录响应仍经 workspace:72 的同 ID 最高 version 入口；目录106、保存147、单条刷新153、toggle156及选择134/create145共同使用。订阅 GET404 的 epoch/catalog-controller:86–94/103–109/153保持，唯一 markSubscriptionUnavailable caller 是订阅实体 GET404；写失败不冒充实体不存在。原 a473 一例与 M02 五例全部通过。

M02：新 fix3 没有恢复 generic mutate 中全部写404清选中/草稿的旧特判。save/toggle/create/report 等写404保留相应订阅和输入，原 asset validation 404 → 可读订阅200/v1 → 草稿应保留的 0ff74 oracle 通过；同ID/version竞态的四个其它对抗例亦通过。

M03：workspace:95–100 仅按被拒核 recommendation_id 从当前已加载页过滤目标；不删除订阅Map，不改 selected，不重挂编辑器。其他推荐、订阅版本与用户草稿保留。全部目标过滤后167显示“当前页推荐暂不可读取”和当前不可读取边界，而不是成功空页/零风险。

workspace:141 只有 read:<id> 且 status404 进入该处理；95–97递增推荐 epoch 并取消在途列表。119–120成功与失败回调共同核 controller、epoch、当前会话；迟到200不能回填。显式fresh失败不清边界；fresh200恢复当前授权列表、清 read 错误和不可读取标记，不建立永久黑名单。134切到不同订阅清A标记，B503不承接A标记/内容；同ID仍保留边界直到fresh200。

授权依据仍是 05:21 的“不存在/不可见统一404”和145“不拿错误/空数组作暂无风险”；后端既有 mark_read→read_recommendation→history fence→read_evidence 的当前 revision/document/source 可见性组合不变。原 PG 合同同client/token改source可见性再拒核只是已读静态依据，本轮未运行PG或实际ACL更新handler，不声称真实跨租户泄漏/live撤权已验证。

correct M03 816f 原3例亲跑通过，包括401/403清私有DOM和草稿、same-target read404隐藏旧quote同时订阅GET200/v1。三轮原业务红不回写成绿：

| 原 oracle | SHA256 | 历史原结论 | fix3正式复验 |
| --- | --- | --- | --- |
| subscription_race.test.tsx | a47349fa55d437c2279daf67d1c8674fb21ba754503d78763937744e3d82c0dd | M01 1fail | 1pass |
| adversarial.test.tsx | 0ff74a7f356109c34a9992d940d1133f05ebc0daf75a75d5f2a95442334778d1 | M02 4pass/1fail | 5pass |
| access_failure.test.tsx | 816f03222445988c54b484c7adbcb68e192bcce3be19dbc47082d33d95b73303 | M03 corrected 2pass/1fail | 3pass |

以上从自己的原WT按字节复制，未改输入、断言、行结束符。oracle_provenance.json / historical_raw_provenance.json 记录原路径、size/hash；historical_m01/m02/m03 六类 raw 是原bytes副本，不加入本轮命令/方法数。错误 initial M03 URI 红件仍在原 faddb65 提交，corrected 红原件也保持。

## 获批的旧期望修订与独立负例

逐diff核：subscription-write404.test.tsx:92–96 只把 read 分支的“已读按钮仍显示可用”改为“目标按钮不可见+不可读取边界”；其他 save/toggle分支原断言保持。输入、方法、HTTP404、requests、writes1、subscriptionReads0 等全部保留；原七方法没有删除/skip。旧期望与 M03 当前证据拒核要求冲突，此修订有 Root 明确授权，不改gold/计分分母。

新作者三例覆盖 otherrec/draft保留、同act在途旧200拒绝与fresh404→fresh200、A→B503归属。其同act refresh/read 是fixture模拟并发，不描述成真人分离点击或真实浏览器证明；没有改作者测试。

新增自己的 fresh_failure 两例，分别404与503：先完成同目标read404并确认不可读取空状态，再显式刷新，等待第二个列表请求，确认推荐region处于loading，resolve该fresh响应并等待region本次alert后才断言quote隐藏、边界保留、订阅v1/草稿保留/单次write。避免作者fresh404断言可能先匹配旧写入错误的问题。它们验证可观察边界，不以源码实现生成期望。

## 真实命令与数量

真实 shell C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe，login=false；base Python C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe；node C:/Program Files/nodejs/node.exe。cwd D:/wt/r17-fix3-review/frontend。run_check.py / bounded_checks.execute 单窗45s/fullWindows10，串行、maxWorkers1、fileParallelismfalse、fixture环境，服务凭据从检查环境移除且不读其值。每条完整argv/clock/退出码见 ownrun 对应command.json，所有时钟真实 +08。

| 正式 label | 实际命令要点 | 开始–结束 +08 (2026-10-17) | 结果 | 完整Win峰/残留 |
| --- | --- | --- | --- | --- |
| oracles_threads | vitest run --config ownrun/oracles.config.mjs --pool=threads --maxWorkers=1 --reporter=verbose --reporter=json --outputFile=… | 05:13:04.506–05:13:07.833 | 3files / 原9pass / exit0 | 7/0 |
| recommendations_threads | vitest run src/features/recommendations --pool=threads --maxWorkers=1 双reporter/outputFile | 05:13:12.194–05:13:26.027 | 12files / 99pass / exit0 | 7/0 |
| fresh_failure | vitest run --config ownrun/fresh_failure.config.mjs --pool=threads --maxWorkers=1 双reporter/outputFile | 05:12:55.511–05:12:57.433 | 1file / 2pass / exit0 | 6/0 |
| types | typescript/bin/tsc --noEmit --incremental false | 05:13:49.709–05:13:54.935 | strict类型 exit0 | 4/0 |
| lint | eslint/bin/eslint.js src/features/recommendations | 05:13:55.588–05:13:58.895 | exit0 | 4/0 |
| build | vite/bin/vite.js build --outDir D:/dianzi-runtime-cache/r17-fix3-review-20261017/dist | 05:13:59.776–05:14:01.397 | exit0 | 6/0 |

110 distinct = 原9 + 推荐目录99 + 自己新增2，0fail/0skip。99=原96方法+新3，不把旧107/108/779、作者结果或本轮fork/threads重复相加。distinct_tests.json 用 relative file + fullName + 同文件同名出现序号去重，test_file_counts.json 给实际文件/方法数。types没有写incremental tsbuildinfo；own tsbuildinfo前后dc4119cf…全hash见review_scope.json；Root用户3c587文件未改。

## 原生资源终态与仪器失败

计数为真实采样的完整Windows控制树（pwsh、conhost、supervisor、工具及后代），未按核数猜budget；preexisting/control ancestry保护不盲kill。新增 native_process_handles 在运行中持有每个采样节点handle，用GetProcessTimes只核同birth身份；WaitForSingleObject(0)判断running/signaled，GetExitCodeProcess记录真正exit。不能仅凭birth仍可读推断alive/closed。正式threads、类型、lint、build所持有业务后代全部Wait0/signaled且exit0；各command的native_terminal_processes逐PID给证据，主Popen.wait与工具退出码也0。只对已采样拥有身份作断言，不虚构瞬间未采样进程或全宿主aggregate。

仪器红全部保留：

1. 首oracles断言9绿，但own helper在最终写receipt时NameError（native_terminal未初始化），outer exit1，无最终command收据；start/active/results/stdout/stderr、bounded_checks_initial.py与instrument_failure.txt保留。仅修自己helper，以oracles_corrected新label复跑。
2. 默认Vitest forks下oracles_corrected9绿/module99绿，主exit0；真实held worker nativeExitCode1且Wait0。installed Vitest4.1.11 ForkPoolWorker.stop:3166–3180确有fork.kill；将其关联解释标为基于本机源码的推断，不把所有后代写exit0。vitest_fork_stop.json保留代码片段/hash；原fork收据不改。为满足最终原生exit0边界，单workerthreads重跑同一oracle/模块，未改产品Vite/config或任何业务断言，数量不双算。
3. release_resources首扫描把当前正在执行的自身pwsh/Python/conhost算作应已结束，nativeWait258/exit259，exit1；第一次只排current ancestry仍漏同窗口conhost，exit1。两版helper/真实raw保留。最终显式记录正在运行的审计控制窗口完整同birth身份，免该窗口自证已结束的要求；这些进程仍计每run峰值，未裁预算。历史拥有身份以完整snapshot排除PID复用，现存同birth再真Wait/ExitCode核，access错误unresolved而非吞掉。not_present不会被赋予假exit0；业务后代的真实终态来自前述held收据。

## 新源码图与调用链

codebase-memory-mcp 工具本轮未注册，ALL_TOOLS实际发现为空，使用官方 WSL portable /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp。独立 CBM_CACHE_DIR=/tmp/dianzi-cbm-r17-fix3-review-20261017；只复制固定6ed的65公开生产TS/TSX/CSS，明确排除tests/fixture/synthetic/reports/answers/secrets/holdout。public source逐bytes manifest在cbm_public_source_manifest.json，旧fix2图只历史导航，不作为新代码证据。

本轮获Root专用独占授权后才开始；先真实 --help、cli index_repository --help、cli trace_path --help，确认官方0.11.0及真实参数schema，再index/full、新schema与两个helper trace。guest用明确/usr/bin/python3，Root已确认该解释器3.10；本轮guest wrapper仅json/os/signal/sys/time/pathlib，静态核兼容，无datetime.UTC；UTC birth helper只在已验证Windows3.12运行。没有重演R18解释器错误。

index真实成功815nodes/3417edges，not_indexed/skipped/partial/unusable全0，schema File65。markRecommendationUnavailable trace直接caller是mutate，其他saveDraft/toggle/generate/createSavedReport是两跳；图不表达status/read guard，逐rg workspace141核实仅read:<id>且404进入过滤，不将两跳caller说成所有写404均清空。markSubscriptionUnavailable trace直接refreshSubscription，另有self/AuthorizedWorkspace节点；self静态边不被当作已证递归，rg153确认实体GET404唯一真实directcaller。M01 useCallback响应入口仍以当前源码72/106/147/153/156及原字节竞态复验核实，不将旧图缺符号解释为未调用。

| CBM label | 实际 +08开始–结束（2026-10-17） | CLI child / outer wrapper | Win+guest combined峰 | 说明 |
| --- | --- | --- | --- | --- |
| cbm_help | 05:42:57.801–05:42:58.404 | 0 / 0 | 7 | 真实help通过 |
| cbm_index_help | 05:42:59.529–05:43:00.175 | 0 / 0 | 8 | 真实help通过 |
| cbm_trace_help | 05:43:01.046–05:43:01.670 | 0 / 0 | 8 | 真实help通过 |
| cbm_index | 05:43:02.491–05:43:11.494 | 0 / 1 | 12 | CLI成功，实际宿主迟退资源红保留 |
| cbm_schema | 05:44:08.031–05:44:08.328 | 124 / 124 | 32 | 原仪器误归属超限失败，未当作schema绿 |
| cbm_schema_corrected | 05:45:05.309–05:45:09.377 | 0 / 1 | 11 | CLI成功，实际宿主迟退资源红保留 |
| cbm_recommendation_trace | 05:45:19.842–05:45:23.410 | 0 / 1 | 11 | CLI成功，实际宿主迟退资源红保留 |
| cbm_subscription_trace | 05:45:24.025–05:45:27.677 | 0 / 1 | 11 | CLI成功，实际宿主迟退资源红保留 |

完整Windows树及guest actor→PID1祖先真实计数，sharedPID1计预算但不清理/不当temporary descendant root；所有临时owned后代及跨窗已见daemon持续按birth跟踪，不按核数猜预算。未起Docker/container，原继承helper将所有后来runc误认拥有进程的分支已删除；保留旧helper，真实own descendants全部保留，未裁自己预算。

本轮仪器/资源红分列，不冒充全绿：

- index CLI child0，但该run结尾wslhost/conhost真实held Wait258、GetExitCode259，outer1；所有schema/trace正式run也保留相应迟退红。GetProcessTimes能够读取不意味着还活着或已退出，真正状态逐native handle记录。
- 第一次cbm_late_host_recheck outer1的原结果实际Windows已0；当时口述“仍Windowsalive”错误，已即时向Root更正。真实失败来自release scanner把active.json中的sharedPID1写入owned known roots，误展开25共享guest；未动PG/Neo4j等业务服务。
- 随后原cbm_schema真实计量combined32>16，child/outer124且owned_process_limit_exceeded，原raw/污染provenance/旧helper保留。监督器按原budget同birth停止本窗Windows child；没有Linux全局kill。不是通过扩大cap或把32改为通过。
- Root只允许一次精确修共享PID1误root的provenance，随后schema+两trace单轮，禁止持续扩仪器/无限终态重跑。修复只用前三help/成功index的真实linux_seen及当前wrapper临时祖先重建known；PID1仍计fullcombined但不能派生wholeguest。原32 schema snapshot不参与真正owned roots集合，修正记录linux_ownership_repair.json可复核。修正schema/两traceCLI0、combined11≤16，原迟退outer1仍保留，不重复index/110业务。

唯一最终resource_final在2026-10-17T05:45:55.525+08：159 recordedWindows / 23 temporaryLinux，activeWindows0 / activeLinux0 / unresolved0 / nativeErrors0，reader child/outer0。sharedPID1保留，正在运行的最后审计行政控制身份单列并仍计该窗峰4；not_present不填假exit0。之前每次Wait258红保持，其末尾完整held退出未全部验证；最终拥有临时身份已不可见/复用或真Wait核消失，是最终资源释放证据。05:45:55终态后立即消息Root交回R07，不继续CBM/WSL；本轮实际工具窗约3分钟（含唯一归属修正及协调），每run真实≤60，最长9.003秒，未将整窗时长伪称预计20秒。


## 覆盖、未运行与交接

| 层 | 本轮状态与实际范围 |
| --- | --- |
| unit | passed，110 distinct隔离fixture；类型/lint/build通过 |
| contract | passed，推荐目录含20 schema合同、11客户端方法，404对象语义/版本/认证范围fixture；HTTP服务器合同未跑 |
| integration | not_run，无真实API/PG；不把React+stub fetch叫PG集成 |
| security | passed仅fixture权限/401/403/current-evidence404、迟到响应与范围核验；独立安全审计/live ACL变更not_run |
| frontend | passed仅组件/状态定向范围；此次无新视觉/浏览器证据 |
| e2e | not_run，无本轮Edge授权，未重跑11场景 |
| live / manual | not_run，模型/来源/真实PG/默认产品边界/连续业务操作未验收 |

原d7d3068视觉11Edge显式fixture与旧779回归只保留历史证据；此轮workspace没有改动ambient/CSS/调查入口/保存引用渲染，不把旧图/截图签成6ed新实时验收。原native hidden-page验证缺口保持；黑客风/动态背景用户要求仍由原已审样式实现，未被新修复移除。当前freshness与历史保存内容/当前有效性不混用，但整工作台评分项D2/F1/F2/F3仅有本切片fixture证据。

无新增Must/Should/Nice finding；M01/M02/M03关闭条件以本轮正式9例与相关caller检查为界。LimitedShip=true 只限固定6ed UI代码与这110个fixture/类型/源码caller范围；工具内容核查已取得，但CBM资源合规不能因最终释放0抹掉32超限/迟退红。Root已明确可限定集成此UI源码并公开资源红；不代表完整R17、真实默认产品或G-E阶段验收。Root后续只按固定8e4/591/1a/6ed前端ancestor整合，保留用户tsbuild3c587；真实PG/browser/live应另获资源窗验收。本人本地提交仅报告与ownrun，不accepted、不push。
