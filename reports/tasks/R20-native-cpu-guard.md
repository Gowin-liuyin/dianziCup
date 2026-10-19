# R20-native-cpu-guard · Windows worker CPU 保障切片

最新交付为下文“独立审查1 Must1 修复”段；代码冻结 `852472810b20b113606a0275ae6861326d39ebe8`，状态仍为 `awaiting_review`。上轮实现和红/绿证据作为历史保留；本轮补上 guardian 就绪后硬退出的内核生命周期联动。没有自行验收 G-C 或完整 R20。

状态：`awaiting_review`；实现 complete；unit/代码检查 passed；integration/live/manual `not_run`。本切片没有自签 accepted，不代表 G-C 阶段或 R20 全链路安全、运维、恢复、CI/CD 验收。

## 结果与冻结版本

Windows 保留 Job 的单进程内存限额、原生 CPU 限额及 kill-on-close，并增加独立 stdlib 监护进程。它用真正 worker 的继承进程句柄读取所有线程累计的 user+kernel CPU，达到预算后调用 `TerminateProcess`。现有 `bound_process_resources(memory_bytes, cpu_seconds) -> int | None`、输入范围、原测试 8 秒/1 CPU 秒/100 MiB、PDF 512 MiB/15 CPU 秒、semantic 2 GiB/30 CPU 秒及两条父进程墙钟超时保持。

代码冻结：`36884c7860434314174adac92dda1947f4469a81`，基线 `45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b`，独立工作树 `D:/wt/native-cpu-guard`，分支 `codex/r20-native-cpu-guard-20261015`。`799fec8085d2b61270d737ccf51587fea8dc2fc0` 是业务实现提交，36884 仅修正新增测试的依赖环境启动方式。后续证据提交不改变这两份代码。

| 文件 | 改动 |
|---|---|
| `backend/src/ai_intel/infrastructure/process_limits.py` | Job CPU 兜底之外增加进程 CPU 监护、匿名事件就绪握手、句柄与失败路径清理；明确采样精度边界 |
| `backend/tests/unit/test_r20_native_cpu_guard.py` | 11 个直接案例：真实 GIL/native/双线程/kernel IO、native 空闲、短任务、启动失败、实际产品调用与生命周期、参数 envelope 校验 |
| 本报告与 `reports/runs/recovery_native_cpu_guard_20261015/` | 原始红/绿日志、JUnit、默认覆盖率、CPU/Job/资源采样、命令时间/退出码、冻结源码与哈希 |

没有改动原 `test_r05_process_limits.py`、两条生产 caller、认证、schema、迁移、依赖锁、指标、progress 或主工作区业务。原测试 Git blob 始终 `fe78d248bcdcf617982551c9e68f8ae8c1023de0`。limiter Git blob `076a89a5fb5ba0628d64e51d849071825f6e9fb3`，工作文件 SHA-256 `2e7a8d9d9cb45b556595507bf0aa87f86f10898c031c32f52c7f9a8759f36039`；新测试 blob `9be292bbfa4b085c4e2afe7d7a33d6812636b402`。详见 [delivery_summary.json](../runs/recovery_native_cpu_guard_20261015/delivery_summary.json)。

## 为什么需要独立监护

官方 Job 文档明确 PROCESS_TIME 约束用户态时间，并由系统周期检查。本机先前诊断已证实 1 秒设置读回正确，但 8 秒时 worker 仍活着、已用 7.703125 秒用户态 CPU，原未改测试也 TimeoutExpired。新基线业务修改前再次有限复现：4 次原 8 秒测试中 2 次 TimeoutExpired（8.016087/8.015431 秒），源码和原测试与旧诊断一致；新增 GIL 占有忙循环加强案例先真实失败。参见 [red_original.log](../runs/recovery_native_cpu_guard_20261015/red_original.log)、[red_gil.log](../runs/recovery_native_cpu_guard_20261015/red_gil.log)。驱动捕获异常并保存证据时可 exit 0，内部失败没有被改成通过。

[`GetProcessTimes`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) 提供进程全部线程的 user/kernel 累计时间，适合实际进程 CPU 预算；[`Job 基本限额`](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information) 仍作为原生兜底。监护进程独立于 worker 的 GIL，不需要工作负载主动让出线程。没有增加依赖、通用框架、配置开关或公共协议。

## 输入输出、调用方及生命周期

- 输入仍严格为原有整数范围，bool、浮点、零、负数和越界拒绝；Linux `RLIMIT_AS/RLIMIT_CPU` 实现路径保留。Windows 返回原 Job handle，正常 worker 应持有到进程退出。
- Guardian 由已安装的基础 CPython `sys.base_prefix/python.exe` 用 `-I -S` 启动，只执行固定代码；标准流为 DEVNULL，无可见窗口。环境仅转交 SYSTEMROOT/WINDIR，继承列表仅包含该 worker 的有限权限真实 process handle 与匿名 ready event，Job handle 不继承。该基础解释器路径不存在或不能启动时拒绝成功；没有另一套无界后备。
- [`DuplicateHandle`](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle) 将当前 worker 的 pseudo handle 转为可继承真实句柄，避免 venv 启动器计时与 PID 复用问题。Guardian 权限只有进程查询、终止和同步；不读取输入正文、模型缓存、秘密或业务数据。
- 设置 Job 内存/原生 CPU、分配当前 worker 后，Guardian 必须完成首次真实 CPU 查询并发出匿名事件；3 秒初始化等待失败即返回 OSError，不运行后续业务。就绪之后才启用 Job kill-on-close。失败 Guardian 被 kill/wait，ready/process/job setup handles 关闭。
- 正常完成后 worker 的最后 Job handle 关闭，会终止 Job 内 Guardian 与其系统辅助进程；Guardian 自身也等待 worker 退出。CPU 超限主动结束 worker，后续 Job 清理沿相同生命周期发生。Popen 对象在这个 disposable worker 内保留到退出；没有遗留外部服务或计划任务。
- PDF `_pdf_worker._bound_memory()` 与 semantic `_bound_worker_memory()` 均直接得到新路径，分别仍为 512 MiB/15 秒、2 GiB/30 秒。真实 helper 调用证明 Guardian 已启动，父测试持有 Guardian handle 验证 worker 正常退出后它已结束。父 PDF `communicate(timeout=20)` 与 semantic 总 deadline≤30 秒及 terminate/kill/join 逻辑未改。

先读取 AGENTS、执行图、测试/运维计划、R20/R05/T18 相关卡与状态/交接；使用新版 Ponytail full。CBM 沿用已实际查看的 0.11.0 CLI help，独立 fast/src-only 索引 `nativecpu_guard_45ee_src` 与 `nativecpu_guard_36884_src`，都在 WSL `/tmp/dianzi-nativecpu-guard-20261015`、persistence=false。修改后 1120 nodes/5426 edges，未索引/跳过/partial/unusable 均为 0；忽略三处编译缓存，不使用这些缓存作为源码。全 caller 以 CBM trace 加 rg/原文核实；局部 import 与 multiprocessing target 的图边不能单独作为完整调用链。见 `cbm_*_before.log`、`cbm_*_after.log`、`rg_callers_after.log`。

## 真实验证与保留失败

| 检查 | 结果 | 退出码/原始证据 |
|---|---|---|
| 修改前原测试 4 次 | 2 passed，2 TimeoutExpired，8 秒保持 | 捕获驱动 0；`red_original.json/.log` 与 attempts 1—4 |
| 修改前新增 GIL 强化案例 | 1 failed，3 秒到期 | 1；`red_gil.json/.log/.xml` |
| 初版直接回归 | 23 passed | 0；`green_initial.*` |
| 补真实 caller/启动错误 | 26 passed | 0；`green_lifecycle.*` |
| 就绪超时句柄检查初版 | 1 failed；首个 subprocess 运行时句柄增量被误归入 limiter | 1；`lifecycle_failure*` |
| 独立 stdlib 对照与重复失败启动 | 普通 subprocess 也 132→134；之后 3 次失败启动稳定134；自行创建3句柄均关闭、Guardian实际退出 | 0；`handle_control.*`、`diagnose_handles_repeat.*` |
| 校准独立 subprocess 初始化基准后的零增量断言 | 1 passed；原零增量门保持 | 0；`lifecycle_failure_fixed.*` |
| 完整 unit 首轮 | 1048 passed，1 failed；新 PDF lifecycle 测试错误使用没有 pypdf 的基础解释器 | 1；`unit_final.*`，失败未删除 |
| 修正为原依赖环境启动实际 caller | 2 passed；业务代码没有因这个测试错误变化 | 0；`product_caller_fix.*` |
| 冻结36884完整默认 unit | **1049 passed，0 failed，0 skipped，1 warning** | **0**；`unit_recheck.*` |
| 完整 Ruff / format | 全部通过，215 files formatted | 0；`ruff_code_frozen.*`、`format_code_frozen.*` |
| 完整 Windows mypy，src+既有脚本 | 87 source files passed，测试 harness 修正前后 limiter 哈希相同 | 0；`mypy_final.*` |
| Linux 平台静态检查 limiter | 1 source file passed | 0；`mypy_linux.*`，不计 Linux 运行验证 |
| 实际 CPU/Job 采样，顺序2次+并发2次 | 4 次无 timeout，全部 worker/job 已退出 | 0；`fixed_cpu.*`、`fixed_cpu_measurement.json` |
| 正常启动开销：3旧基线+3新路径 | 6 次正常完成，原始进程/内存/CPU保留 | 0；`overhead.*`、`overhead_measurement.json` |

冻结完整 unit 保留 pyproject 原 addopts，覆盖率门 **60%**，4478/6665 = **67.18679669917479%**，显示67.19%；命令实际 wall 52.809583 秒，pytest 50.10 秒。唯一 warning 是既有 Starlette TestClient 弃用提示。选择性红/调试检查显式 `--no-cov`，用于定位单个行为，不冒充默认门。既有相关 PDF、semantic、内存/恶意参数回归包含在完整 unit；没有删除或降级困难案例。

完整冻结命令（cwd `D:/wt/native-cpu-guard/backend`）：

```text
D:/dianzi/backend/.venv/Scripts/python.exe -B -m pytest tests/unit -o cache_dir=D:/tmp/nativecpu-guard-20261015/pytest-cache --basetemp=D:/tmp/nativecpu-guard-20261015/pytest-temp --junitxml=D:/wt/native-cpu-guard/reports/runs/recovery_native_cpu_guard_20261015/unit_recheck.xml --cov-report=json:D:/wt/native-cpu-guard/reports/runs/recovery_native_cpu_guard_20261015/unit_recheck_coverage.json
```

全部测试、质量和采样检查的 argv、UTC 开始/结束、退出码、当时 HEAD、limiter SHA-256、JUnit数量保存在同名 JSON 与 `delivery_summary.json`，不伪填未执行项。记录的检查命令累计 wall **221.033508 秒**，包括有限相位等待、红日志和两轮完整 unit；不是连续压力运行时长。专门 CPU 原样/采样组为修改前4次、修改后4次，后者最大2并发；正常开销组6次。其余真实 CPU、native/GIL、短任务和失败生命周期次数由对应 JUnit保留，不从结果中删除失败。

## CPU 实测、开销与边界

4 个真实忙循环在 worker 累计 user+kernel **1.015625—1.03125 秒**时退出，wall **1.307340—1.364104 秒**，exit `3221225540`（`0xC0000044`）。Job `terminated=0`，worker 用户态不足1秒而总 CPU已到预算，表明本组由新增的总 CPU监护终止。独立记录真正 worker、venv 启动器、Guardian与系统 conhost；Job整体 CPU包含辅助进程，不能误充 worker CPU。

正常 worker 的 limiter 启动 wall 中位：旧基线 **0.2756ms**，新路径 **84.0111ms**（n=3各组，新范围79.674—124.626ms）。新 worker 这段 CPU为0.015625—0.03125秒；Guardian在就绪采样时 user+kernel为0.046875—0.09375秒。Guardian private约 **6.22—6.26MiB**、working set约 **13.19—13.21MiB**；这些是调用就绪时的实测，不是持续高负载峰值或吞吐结论。[内存API](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo) 字段口径与原始数值保留。

限制与风险必须保留：

- 50ms是名义墙钟采样间隔。CPU计时量化、OS调度、多个 native 线程及异步进程终止均可带来延后；没有硬实时或严格1.000000秒精度保证。没有以增大旧8秒门掩盖它。
- 监护的是该 worker 的全部线程CPU；任意新增 grandchildren CPU不汇总到这个 worker计时，它们继承Job的原生单进程限制。当前两个 caller在工作负载内没有启动任意程序，PDF jbig2外部程序保持禁用；本切片不是可运行任意插件/PoC的沙箱。
- Job内存限制继续是每进程提交内存，Guardian及系统 conhost额外占用资源。记录到隐藏 conhost，额外系统进程的完整内存/费用/长期峰值为 **unknown**；没有宣称整组总内存受一个100MiB/2GiB总量cap控制。
- 当前 caller每个 disposable worker调用一次。正常 Job/Popen handle保留到worker退出；重复调用可产生多个Job/Guardian，不把这个启动器当长期worker管理框架。没有验证监护器被外部特权进程主动杀死时的强对抗保证，原生Job与父墙钟时限仍兜底。
- Windows11 build26200/CPython3.12.13本机验证；其他Windows版本与非标准基础解释器布局未运行。Linux实际RLIMIT验证 `not_run`，静态检查不能替代它。真实模型推理、全链路集成、持续运行、运维恢复与部署 `not_run`。

缓存统一位于 `D:/tmp/nativecpu-guard-20261015` 和独立 WSL tmp。首次Ruff默认缓存，以及既有PDF父环境过滤造成的三处编译缓存，在路径解析/非reparse核验后迁出自有工作树；没有改该生产父环境协议。见 `cache_moves.json`。未读秘密/holdout，未调用真实模型或付费API，业务测试无外部网络；资料查询只用上述官方Microsoft/Python文档。没有push或共享状态更新。

## 评分项、偏差与交接

E1：补齐可信 worker资源限制及时执行、启动失败拒绝工作、正常退出清理的本地证据。P1：增加实际CPU与初始化开销记录；不计成正式性能评分或持续运行达标。合同/计划偏差：无公共接口、依赖、指标分母变更；scope仅上述两份code和自有报告/日志。先前诊断记录24次/212.865秒保持历史，没有被覆盖。

下一步由主控另派新的非作者审查者，在本代码冻结SHA干净复现，重点检查进程句柄继承、GIL/native CPU、正常/失败生命周期、辅助进程与内存边界，以及原8秒测试和默认门。当前只交 `awaiting_review`；G-C/R20最终验收需后续全链路运维、安全和外部证据。

逐文件 SHA-256 见 runs目录 `artifact_hashes.json`；报告最终hash与证据提交SHA在交接消息给出，避免自引用hash。

## 独立审查1 Must1 修复（2026-10-15）

本轮输入是独立 [审查1](../reviews/recovery/G-C-native-cpu-guard-review-1.md)，原始 SHA-256 `29921e67545d14522323b3bad91c2d173f87a80c837406cdcdfbf70b09a9ccc5`。审查已确认 guardian 就绪后 `time.sleep(0.4); os._exit(99)` 能让原 worker 消耗 2.25 CPU 秒并输出成功结果。问题是一次就绪检查不能监督后续硬死亡；不是未取得就绪事件，也不是旧限额读回错误。

本轮基线 `994c381edd2c4f0743d9c76f83abefaf51359f14`；业务冻结 `852472810b20b113606a0275ae6861326d39ebe8`，独立工作树/分支沿用上述作者目录。只修改 limiter 和其直接测试，新增自有 `reports/runs/recovery_native_cpu_guard_fix1_20261015/` 并补本报告；没有改两条 caller、原测试、公共配置/状态或其他业务。limiter 新 blob `36c7e90f3e1d5423f943f66b5573ba80563c9854`、工作文件 SHA-256 `63ba29abba39fdc915c46787aba8fe84bac1dbc747c2b1085ed9e89975f85756`；测试新 blob `09a9e8bf4061025e254999eb3f103360433700b3`、工作 SHA-256 `64ddc00ea8aeb14ce142221d921a10578aee5448c96e60b80f30855bd73e03b9`。原测试 blob 仍为 `fe78d248bcdcf617982551c9e68f8ae8c1023de0`，与初始 1927 基线一致。

### 共同生命周期的最小实现

继续使用最新 [Ponytail full](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail/SKILL.md)。只加一个匿名原生 Job，启用 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`；不增加监护进程、线程或框架。原资源 Job 仍返回给 worker，保留内存、原生 CPU 与 worker 退出清树约束。

先启动 guardian，它继承原资源 Job，但还未进入新的生命周期 Job；通过固定 `handle_list` 向其转交生命周期 Job 的只查询句柄。guardian 验证句柄、CPU 计量和就绪事件后，worker 加入空的嵌套生命周期 Job，关闭自己所有生命周期 Job 句柄。此后 guardian 独占最后句柄。guardian 不可捕获退出会由内核关闭句柄，终止 worker 和它之后创建的子进程；worker 死亡又关闭原资源 Job 最后句柄，清理 guardian 及其原资源 Job 子进程。若 guardian 在就绪与入 Job 之间死亡，worker 关闭最后本地句柄仍会触发终止，不能返回未受监督的工作。启动失败仍清理实际 guardian 与 setup handles。guardian 可捕获异常及正常 CPU 超限路径仍调用原 `TerminateProcess(0xC0000044)`。

这依赖 Windows 8/Server 2012 起支持的嵌套 Job；不支持或无法入 Job 时拒绝初始化，不改平台或降级。内存仍按 Job 链中最严格的每进程限额执行；子进程默认继承 Job 链。依据为 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject) 和 [Job 基本限额](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)。没有把此联动解释成硬实时 CPU 精度或高权限强对抗沙箱。

### 先红、真实故障回归及父边界

原审查的完整最小脚本逐字复制到新 run 的 `probe_review_windows.py`，先只执行两次原样失败输入。`red_guard_abrupt_exit_0/1.json` 实测均 worker exit 0、CPU 2.25 秒、wall 2.310687/2.337071 秒且输出 `WORK_COMPLETED_AFTER_BUDGET`；1 CPU 秒、100 MiB、8 秒外层门保持。新增永久回归首先红：2 failed / 1 passed，忙 Python 和 GIL-held 原生 Sleep 返回结果，PBKDF2 那次被原 Job fallback 终止，不把偶然兜底当生命周期正确。

首次修复后的额外“必须非0退出码”断言三例仍红，原始 `green_regression.*` 保留。实际行为是 Windows kill-on-close 在本机返回 exit 0，却已终止 worker、没有输出结果；主控明确以父进程拒绝无完整结果为验收核心，不硬造非0码。永久回归改为验证无成功结果、三个实际进程句柄均退出，并读取真实 worker 的 user+kernel CPU **小于原1秒预算**；没有放行仍输出结果的情况，也没有扩大限额。修复后普通 CPU 超限仍返回 `0xC0000044`。

新增5个永久案例：就绪后硬退出的忙 Python/GIL-held 原生 Sleep/native CPU 三种 worker，各自创建 benign sleep leaf，断言 worker/guardian/leaf 均结束；PDF 真正子进程被同一故障终止后，生产父边界拒绝空 JSON；semantic 使用真正 multiprocessing spawn/Pipe，生产父边界把 EOF 转成 `SemanticRuntimeError("local semantic worker exited without a result")`。无模型、网络或付费调用。首次父回归 1 passed/1 failed 是新测试中一个错放的旧 assert 造成 NameError；只修测试位置，生产 limiter 不变，失败日志保留。两个真实父回归随后通过。父参数仍 PDF 512 MiB/15 CPU/20 wall，semantic 2 GiB/30 CPU/原总 deadline；两条生产 caller 无 diff。

同一个审查驱动修复后硬退出两次：worker CPU **0.453125/0.46875秒**，wall **0.567324/0.574713秒**，exit 0、无成功结果，worker 和 guardian 已退出；普通可捕获异常两次是 `0xC0000044`，CPU 0.515625/0.5 秒。正常 GIL/native/两worker并发共4次 CPU 1.03125—1.046875秒、wall 1.141262—1.193749秒、均 `0xC0000044`。另两次并发 guardian 死亡在 GIL-held Sleep 中验证 worker/guardian/leaf 全退出、无结果；worker `os._exit(77)`、显式关闭原 Job 及短任务的旧树清理路径也保留真实退出句柄证据。

### 冻结检查、命令和成本

全部 argv、cwd、HEAD、源文件 SHA-256、+08 开始/结束、退出码及 wall 保存为新 run 中同名 JSON/log；JUnit/XML、覆盖率 JSON 与进程采样不做口头计数。`fix_summary.json` 汇总实际记录。业务检查开始 `2026-10-15T21:36:58.673585+08:00`；冻结完整 unit 结束 `2026-10-15T21:46:15.883259+08:00`。汇总/报告写入时间不计为测试时间。

| 检查 | exit | 实际结果及证据 |
|---|---:|---|
| 原最小红 `python -B red_minimal.py` | 0，驱动捕获 | 2 次行为失败，上述 CPU/成功输出；`red_minimal.*` 和两份 red JSON |
| 永久故障回归首次红 `pytest test_r20_native_cpu_guard.py -k guard_hard_exit --no-cov -v` | 1 | 2 failed / 1 passed；`red_regression.*` |
| 首次额外非0码断言 | 1 | 3 failed，无结果但内核 exit0；`green_regression.*`，解释保留 |
| 原测试+直接回归 `pytest tests/unit/test_r05_process_limits.py tests/unit/test_r20_native_cpu_guard.py --no-cov -v` | 0 | 30 passed，13.83s；当时未加入两父边界案例，`green_behavior.*` |
| 两父边界 | 1→0 | 初版1 failed/1 passed（测试 NameError），修正2 passed；`fault_parents.*` / `fault_parents_fixed.*` |
| 原审查驱动 `python -B probe_review_windows.py` | 0 | 20 有界尝试：4 CPU、4监护故障、2树生命周期、10正常开销；0 timeout，逐份 JSON |
| 增量成本与并发 guardian 死亡 `python -B incremental_cost.py` | 0 | 6正常成本+2并发树故障；0 timeout、所有观测进程均退出 |
| 冻结默认 `pytest tests/unit`，保留默认60%门 | 0 | **1054 passed / 0 failed / 0 skipped**、1既有Starlette warning；53.25s pytest/55.963825s命令；`full_unit_frozen.*` |
| 冻结 Ruff check / format check `src tests` | 0/0 | 全 lint 通过、197 files formatted；`ruff_frozen.*` / `format_frozen.*` |
| 冻结 `mypy --platform win32 src` | 0 | 85 source files；`mypy_frozen.*` |
| 冻结 caller/原测试等价、rg、diff check | 0/0/0 | 不改caller/旧门、无空白错误；`caller_budget_equality.*`、`rg_callers.*`、`diff_check.*` |
| 当前冻结 CBM help/index/trace | 0/0/0 | 独立 src-only 1120 nodes/5426 edges，未索引/跳过/部分/不可用均0；`cbm_help.*`、`cbm_index_frozen.*`、`cbm_trace_frozen.*` |

完整默认命令：

```text
D:/dianzi/backend/.venv/Scripts/python.exe -B -m pytest tests/unit -o cache_dir=D:/tmp/nativecpu-guard-fix1-20261015/pytest-cache --basetemp=D:/tmp/nativecpu-guard-fix1-20261015/pytest-temp-full --junitxml=D:/wt/native-cpu-guard/reports/runs/recovery_native_cpu_guard_fix1_20261015/full_unit_frozen.xml --cov-report=json:D:/wt/native-cpu-guard/reports/runs/recovery_native_cpu_guard_fix1_20261015/full_unit_frozen_coverage.json
```

cwd 为 `D:/wt/native-cpu-guard/backend`，PYTHONPATH 指向本独立 worktree。覆盖率 **4489/6681 = 67.19054033827271%**；选择性诊断显式 `--no-cov`，没有冒充默认60%门。CBM 用现有 WSL portable `0.11.0`，先实际 help；冻结项目 `nativecpu_guard_8524728_src` 只索引 `backend/src`、persistence=false。trace 所有 caller 与 `rg` 原文交叉核实，semantic 局部导入边只有 heuristic confidence0.38，不单凭图作保证。索引/pytest/coverage/mypy/Ruff 缓存在 workspace 外；既有PDF父环境造成的5个 ignored pyc按受控绝对路径迁出，见 `cache_moves.json`。

专用采样总计 **30 次**（2红+20复验+8增量/并发），最大2个并发worker；累计各attempt wall **21.298144秒**、真实worker CPU **12.5秒**、0 outer timeout。此数不包含默认 unit 内的测试子进程，不能冒称所有测试总共只有30个进程。汇总前已记录命令累计 wall142.721251秒，包含红/失败/static/CBM/完整unit，不是连续压力时长。

与审查基线994c的相同guardian实现比较，每组n=3：就绪 wall中位旧 **70.9582ms**、新 **63.8970ms**；该小样本和不同import scaffold不能证明加速。guardian真实handle count旧125→新126（多1个只查询Job句柄）；guardian private旧6,529,024—6,557,696 bytes、新6,549,504—6,594,560 bytes，working set旧13,819,904—13,852,672、新13,848,576—13,893,632。一个新Job内核对象的精确内存、长期高并发峰值与吞吐成本 **unknown**。没有新进程/守护线程，worker完成setup后不保留新增生命周期Job句柄。原 guardian/conhost 固有成本保留上轮测量与限制，不将这些数字当整树100MiB cap。

### 本轮范围与后续复核

状态 `awaiting_review`，unit/静态 passed；本机 Windows11 build26200、CPython3.12.13。Linux运行、其他Windows版本、真实模型、integration/live/manual、长运行和完整R20运维 **not_run**。50ms采样、CPU量化与调度/异步退出延后限制不变；不声称精确hard CPU时刻。任意grandchildren CPU仍未纳入worker计量，原每进程Job限额与生命周期清树仍生效；新Job不是任意不可信扩展的沙箱。生命周期自动结束可能为exit0，调用方必须继续验证完整结果协议；两个既有产品父边界已验证，未来caller不得只看退出码。

本轮已验证隔离注入的guardian硬退出，取代上轮“未验证此死亡路径”的缺测描述；不据此声称抵御外部特权进程篡改句柄/Job。没有变更公共接口、依赖、阈值、计分分母或配置，未读secret/holdout，未push/accepted/改共享状态。E1补生命周期fail-closed真实证据、P1补实测增量开销；不计正式全链安全/运维评分。

交主控和原独立reviewer，在本业务冻结SHA的新干净工作树定向复核：同故障无完整结果及父空JSON/EOF拒绝、GIL/native/树/句柄、原8秒门及默认质量门。报告/证据新提交不再改业务；报告最终hash、证据SHA与新run逐文件manifest由交接给出。本切片不使G-C或整张R20 accepted。
