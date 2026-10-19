# G-F · R20 最小进程启动修复独立 review 1

What this change does: PDF worker 在成功安装原资源限额后才导入 pypdf；Windows guardian 在首次累计 kernel+user CPU 已达预算时拒绝发出就绪信号。两处改动均有独立边界复验，但只消除这两个具体启动缺陷，不能保证进程从 site 初始化起的总 CPU 严格小于 1 秒。

评审状态：独立 review 已完成，报告 `awaiting_review`，登记交主控；不写 `accepted`。**Verdict: Ship，限定于上述两处修复与五个新单元边界。整 R20、原 T45/T49/T50/T51、G-F、严格累计 CPU 硬上界均不通过本报告验收。** 未发现该最小 diff 的新增 Must fix / Should fix；原严格 CPU 问题继续保留。源代码、原测试、公共状态、合同和阈值零修改，无提交或 push。

## 冻结身份、范围与合同

新独立非作者 worktree：`D:/wt/r20-startup-review-1`，分支 `codex/r20-startup-review-1`。由 `D:/dianzi` 自行建立于完整冻结 `535c0a537bc24cb52c64511c72eeb4ea3ae5bc34`；业务版本 `41c61491b4429cc47dd970b201d9b2551cbb3a7f`，基线 `c3a2abc9a5246993eabb351d26cfeb51d0270b31`。主目录原未提交修改未触及，也没有 spawn 新 agent。

已读实际 AGENTS、执行图、恢复 R20、T45/T49/T50/T51、04/06/09 合同、冻结状态/交接、作者 `R20-process-startup-fix.md` 及独立原诊断 `D:/wt/r20-cpu-boundary-diagnosis/reports/tasks/R20-cpu-boundary-diagnosis.md`。使用当前 Ponytail 5.2 review 的真实 caller/负例方法。冻结公共 state 中 R20 仍为历史 `pending/not_started/not_run`；作者局部报告为 `awaiting_review`；本报告不据其较旧公共登记推断产品通过，也不覆盖主控工作目录的进度。

基线至业务版本只有两产品文件及 `test_r20_process_startup.py`，共 136 insertions / 3 deletions；业务版本至完整冻结仅材料变化。源身份与 Git blob 校验见 run 的 `execution_summary.json`。limiter 工作文件 SHA256 `0e427be27ddce7ec2abb6ef183acb1df7008d112e0ea3a2b9b9ba9f86fe4dc56`，PDF worker `24ea5c30a58eda43410700e5dd9396cecb6bc59b5da8e8d1c0a1c53041956c60`；原 guard 测试 `d36f79a39904c2f03fb11cae415835c79f45a07dde6c207fd04be95373167261`。新测试 checkout 与作者 LF 文件可能有换行差异，Git blob 已一致，不能用原始文件 SHA 的换行差异误判修改。

永久合同未改变：CPU 热点 1 秒 CPU / 3 秒 wall；原产品就绪 8 秒；PDF 512MiB / 15CPU / 20wall；semantic 2GiB / 30CPU / 总 deadline≤30 秒；整体覆盖门 60%。原测试和四个红例未删除、未改阈值、未 skip、未减去启动 CPU 或改计分分母。报告新增文件仅本 Markdown 和 `reports/runs/r20_startup_fix_review_1_20261016/` 的观测脚本、日志、receipt、JUnit、coverage 和封存索引。

## 独立调用链与实现审查

先独立使用 WSL CBM src-only index，再取得 schema 与三个 qualified trace，之后用 `rg` 搜全部 backend `src/tests` caller。project `r20_startup_review_1_src`，1253 nodes / 6259 edges，not-indexed/skipped/parse-partial/unusable 全 0；不复用作者 index，不采纳工具 ADR 建议。`bound_process_resources` 两个直接产品 caller 是 `_pdf_worker._bound_memory` 与 `semantic._bound_worker_memory`；动态局部导入与 multiprocessing target 另由源码/rg 核对，图不代替实际调用证据。

PDF 实际流：catalog 的 PDF 分支 / parser re-export → `parse_pdf_text_layer` → 固定 `sys.executable -m ai_intel.ingestion.parsing._pdf_worker` → `main/_bound_memory` → pypdf package 初始化 → 私有 stdin 内容解析 → pages/notes JSON → 父退出码、尺寸、JSON 类型、页号与文本校验。容量 2、环境白名单、20 秒 communicate、超时 kill/drain、拒绝空/异常输出保留。`extract_pages` 的直接函数接口仅有 worker 与测试 caller；直接测试接口没有变成对外任意读取工具。限额拒绝时返回明确 `pdf resource limit unavailable` 并不导入 pypdf；成功设限后的解析错误仍为 `invalid or resource-limited pdf`。不可用平台、资源初始化失败、进程失败和坏协议分别有负例，不伪造正常结果。

Guardian 首次 `GetProcessTimes` 仍读取进程从启动以来的累计 kernel+user，`>=` 原预算即走异常终止路径，发生在 `SetEvent` 前；等于预算与超预算两例均观察到 terminate、无 ready。现有 lifecycle handle、exclusive Job kill-on-close、有限失败清理继续保留。真实初始已耗尽样本确认无 READY、无结果且进程结束。正常采样仍是 50ms 后检查，首读/SetEvent/后续轮询间的调度窗口没有被本 diff 消除。

Semantic 实际流：`LocalSemanticModels` → `_run_worker`，spawn 前建立总 deadline → 固定 spawn/Pipe → `_semantic_worker` 先 `_bound_worker_memory` 后模型校验与动态库 → 信封和数值校验 → finally 有限 terminate/kill/join。EOF 被拒绝，资源初始化 OSError 对应 failed，缺模型/运行库对应 unavailable；没有把空值当成功。此次源码没有修改 semantic。实际控制样本以合成 artifact/inference 接缝运行原 `_semantic_worker`，在真实限额后才进入合成接缝，不能计为模型能力。

## 真正执行的检查

所有正式命令 cwd 为 `D:/wt/r20-startup-review-1/backend`，解释器 `D:/dianzi/backend/.venv/Scripts/python.exe`，PYTHONPATH 指向独立 worktree 的 `backend/src`。每条完整 argv、上海开始/结束到秒、exit、wall、日志哈希与实际 case ID 在同名 `*.receipt.json`，原始输出分 stdout/stderr 保存。没有运行整仓 pure、网络、PG、模型推理、下载、付费 API、秘密检查或第三方资产动作。

| receipt 前缀 / 实际命令范围 | 上海时间 +08 | exit | 实际结果 |
|---|---|---:|---|
| `startup_unit`：`pytest tests/unit/test_r20_process_startup.py tests/unit/test_r05_process_limits.py -k 'not real_native' --no-cov -v` | 00:58:33—00:58:35 | 0 | 19 passed，0 skipped；新 5 项 + 原输入/平台/限额 14 项；2 个 real_native 未在此选择 |
| `default_native`：原 hard-exit `[native-cpu]`，保留默认 addopts 与 coverage 60 门 | 00:58:44—00:58:48 | 1 | 原 case 1 passed；局部 coverage 1.74% < 60%，命令失败 |
| `original_boundaries`：guard 文件选 CPU 4、初始化失败、父 PDF 拒绝、真实 semantic EOF、产品启动 2、失败就绪清理、semantic 限额 | 00:59:43—00:59:54 | 0 | 11 passed，0 skipped，5 deselected；10 primary，其中 1 限额纯 unit 无 worker |
| `real_pdf_parent`：官方四页、中文、原页码与精确定位原节点 | 01:00:29—01:00:30 | 0 | 1 passed；真实固定产品 Popen、pypdf 与完整父入口 |
| `protocol_unit`：原 PDF 坏协议/20 秒超时清理；semantic 设限先行、错误与初始化失败清理 | 01:00:31—01:00:32 | 0 | 24 passed，0 skipped；显式合成边界，无 primary worker |
| `measured_boundaries`：初始 CPU 已耗尽、异步 stdin 的 PDF coverage | 01:01:43—01:01:52 | 1 | 2 primary；耗尽拒绝成功；PDF 四页输出成功，但自有 READY 前缀误读引发 KeyError，整个 harness 失败保留 |
| `semantic_coverage_only`：自有拆分脚本第一次 | 01:03:16—01:03:16 | 1 | 自有函数边界放错导致 NameError，尚未启动任何 worker，不能记业务失败或 worker 样本 |
| `semantic_coverage_recheck`：只执行未运行的 semantic 控制，不复跑前两个样本 | 01:03:44—01:03:45 | 0 | 1 primary；真实 spawn/Pipe、原 `_semantic_worker`、真实限额、coverage 活跃；合成 384 维结果 |
| `ruff_products` / `format_products` / `mypy_products`，win32 两产品文件及新测试静态范围 | 01:04:19—01:04:22 | 0 | Ruff、format 与指定产品 mypy 均通过 |
| `diff_check` | 01:04:22—01:04:22 | 0 | 无 whitespace 错误 |

实际 JUnit 合计 **56 passed / 0 failed / 0 error / 0 skip**，不是整仓验收：其中默认 coverage 命令仍 exit1，两次自有测量命令 exit1 也不算测试通过。原 guard 16 项中本轮只执行了选定 11 项及 default native 1 项，即 **12/16**，剩余 idle、short、另两个 hard-exit 节点未运行；不得引用作者 16 green 当本轮 16 全复跑。

作者冻结 `red_startup.xml` 仍是 4 tests / 4 failures / 0 errors / 0 skipped；其 import 前置两例和等于/超初始 CPU 两例的失败日志、GBK runner 问题与后来成功记录完整保留。作者的 5 新例、16 原 guard、1 真 PDF 与本轮是不同执行记录，不相加作为独立样本。本次局部 `--no-cov` 明确用于行为边界；完整默认 pure / 整体 60% 门 `not_run`，没有降低或移除覆盖门。

## 15 个 primary 样本与实际计量

`execution_summary.json` 列 command→primary 数量及实际 sample IDs；默认 native 1、选原 guard 10、真 PDF 父 1、耗尽/PDF coverage 2、semantic coverage 控制 1，共 **15**。所有 primary 串行、并发 1，达到上限后停止；guardian、leaf、Python venv redirector、就绪失败用例的纯 pass 预热另按实际进程计数，不能把 primary 数等同于系统进程总数。

这些含 worker 的命令累计 wall **27.110 秒**，低于 180 秒；查询到的 **63** 个后代进程累计 CPU **16.4375 秒**，低于本轮 45 秒预算，全部句柄最终 signaled。通过 root CreateProcess 同步留句柄及 10ms Toolhelp 后代查询记录 CPU；极短后代若在 snapshot 前退出可能漏计，因此该值是完整记录中已观察的累计值，不能宣称绝对完整全树 CPU 或通用性能上界。没有对 root 并发的其它任务计时或终止，不把本机竞争状态当无竞争性能基准。

| 具体样本 | 原始观测 | 结论边界 |
|---|---|---|
| default 原 native hard-exit | 实际 worker PID46248 总 CPU 0.96875，树结束，case 通过；未另取得就绪 CPU | 一次绿；不关闭原独立 1.328125 秒红记录 |
| 正常原 CPU 4 例 | GIL 1.03125、native 1.046875、双 native 线程 1.109375、kernel IO 1.0 CPU；原 3 秒 wall 断言均通过 | 当前采样仍可晚于名义 1 秒；不是严格累计 `<1` 的证明 |
| 初始预算已耗尽 | before-bound 1.109375 CPU，终态 worker 同为 1.109375 CPU；无 READY/结果、exit3221225540、观测树结束 | 首次 exhausted fail closed 生效；不能追回已花 CPU |
| PDF coverage 异步输入 | module 后 0.421875 CPU；bound 后 0.4375；重库后 6.84375；真实 JSON 四页、exit0、观测树结束 | pypdf 重初始化确在设限后；重库约 6.40625 CPU。自有 reader 计时断言失败，不能登记可信父 launch→READY 时长 |
| semantic coverage 合成正对照 | coverage_active=true；entry-after-site 0.515625 CPU、bound 后0.53125；真实2GiB/30CPU；0.672 wall；未 import tokenizers/numpy/onnxruntime | 补足 coverage 下 spawn/Pipe 与设限顺序控制；不替代真实运行库/模型覆盖启动、加载或推理 |

PDF 自有 reader 的错误与作者仪器缺口分别保留：作者先同步写 stdin，原 parent ready7.484不能代表 bootstrap 就绪；本轮改为独立 writer thread，但 reader 仅匹配 `READY ` 而子输出 `READY`，导致误写 `exited_before_ready=true`，随后 KeyError。原日志实际有 READY，因此该字段不能当产品未就绪。已更正自有下一轮 reader，**没有再次运行 PDF**；旧执行脚本保存为 `executed_measure_initial.py`，这条命令仍 exit1，无补造时长。冻结作者仪器缺口也不因本次补测自动消失。

## 封存核验与自有失败

独立 `frozen_gitblob_audit` 01:02:33—01:02:42 exit0：逐个读取完整冻结的 **85 artifact Git blob**，全部匹配；有 LF hash 的 artifact 均匹配；从实际 JSON 识别 **29 receipt**，完整 argv/exit 保留。manifest checkout SHA256 精确为 `d2520b0aef5fe79cec500de60c662e3e4aafe98324fcf0293e6f316bac85ec47`；Git 中 LF bytes SHA256 为 `9e80f3d3831605b02b7c446e5080afb6d9c3cee794a15cc7a637509def4f0ddf`，两者是换行形态不同。

原 GBK `red_startup.log` 没有 sha256_lf，checkout raw hash精确匹配 `1b336e...` 且 Git blob 为 `5cdc1e20...`；不能把其 raw hash直接当 LF hash。首次自有审计 KeyError、第二次错误比较造成断言失败均有 receipt/log 与执行脚本副本；没有修改作者 artifact 来修审计。自有初次汇总错误使用 `recovery` key产生 KeyError，随后仅改成实际 `recovery_tasks`，原失败保留。自有 semantic 拆分 NameError只在启动前发生，修正后只跑未执行的 semantic 样本。均不冒充产品测试失败、skip或通过。

本 review 自有 manifest 为 `review_artifact_manifest.json`，包括报告、执行版本、raw输出、JUnit、receipt、coverage、源身份与预算汇总。src/test/progress/contracts 与冻结一致；Git diff仅新增 reviewer报告与run。完整验收的前置缺口不在本次改动权限内。

## 保留问题与未检查范围

**原严格累计 CPU 1 秒故障未关闭。** 原独立诊断的默认 native 1.328125 >1 红记录依然有效；本轮正常样本和初始耗尽样本也明确不能支持绝对 1 秒硬界。首次预算检查只能阻止已经耗尽时继续；site/coverage先运行、GetProcessTimes与SetEvent间竞争、50ms后采样、guardian就绪后故障窗、Job user-only与kernel+user口径的区别仍存在。最小后续动作仍需由父在 site/重初始化前建立受控 bootstrap/监督接缝并明确平台可证保证，不重置 baseline、不加预算余量、不删除原断言。

Not checked: Linux实际 RLIMIT、其他 Windows版本、ETW/内核调度、绝对全树 CPU 上界、长期句柄/高并发、真实 semantic 重库与模型 coverage 启动/推理、完整默认 pure/60%门、完整 integration/live/manual、T45全链路权限/注入、T49告警、T50备份恢复、T51 CI/CD、FOFA真正 GIL 超时原日志与正式持续运行。模型和外部接口在此范围为 not_run；没有登记 online/live passed。

评分证据限定：E1仅新增真实 PDF设限顺序、guardian首次 exhausted拒绝、失败父协议/清树的局部证据；P1仅登记有限CPU/启动观测。不能由此签整E1/P1、整R20或阶段passed。下一任务建议：主控登记限定review结论，另行授权早期严格CPU接缝修复并安排新独立复验；本review到此停止。
