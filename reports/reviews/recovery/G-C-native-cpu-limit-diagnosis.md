# R20-diagnostic · Windows 原生 CPU 限额诊断

任务状态：`awaiting_review`。诊断产物 complete；业务实现没有修改；R20 整卡、G-C 阶段和问题修复均未验收。结论：应先修复 Windows CPU 终止保障，再把该负例作为稳定回归门。不能用本轮完整 unit 通过关闭已经复现的失败。

## 结论与证据强度

**确认：当前 Windows 实现虽成功设置 1 秒 PROCESS_TIME，却允许受限忙循环累计超过 7 秒用户态 CPU 仍未退出，随后与测试固定的 8 秒总时限相撞。** 这不是只能靠“并行时没有获得 1 秒 CPU”解释的故障：失败样本实际已获得 7.703125 秒用户态 CPU。没有提高 timeout、改测试断言、skip、改覆盖率门或修改业务代码。

1. 必须修复：`backend/src/ai_intel/infrastructure/process_limits.py:79`—89 只设置并分配 Job，未建立及时终止的额外保障。设置成功不能保证这个 1 秒负例在 8 秒内完成。受控样本 14 在 wall 8.011214 秒时，Job `user_seconds=7.703125`、`active=1`、`terminated=0`，启动器尚未退出；诊断器才执行到期清理。随后由 **未改动的原测试函数** 在样本 20 抛出同一 `TimeoutExpired`，wall 8.025709 秒，异常栈为原测试第 51 行和标准库 subprocess 第 1630 行；stdout 已含 `LIMIT_APPLIED`，stderr 为空。
2. 确认配置没有丢失：样本 13—16 由 `QueryInformationJobObject` 读回 `process_time_100ns=10000000`、flags `8450=0x2102`、memory `104857600`、EndOfJobTimeAction `0`；查询均成功。样本 14 的进程计时和 Job accounting 相互一致。不能把这个失败改写成限制函数未调用、CPU 不足、只有管道句柄迟迟不关闭，或 ctypes 参数未生效。
3. **推断而非已确认的内核根因：**原生终止常落在约 7 秒间隔，启动相位改变后出现接近 8 秒及超过 8 秒的结果，符合 Job 时间限额检查/终止有周期性延后的解释。未使用内核跟踪器，未取得该 Windows build 内部定时器证据；“固定每 7 秒检查”的普遍规则没有得到证明。旧两次失败没有 CPU/Job 原始采样，所以不能声称逐次证明了其全部内部过程。

主要原始证据：[样本14](../../runs/recovery_native_cpu_limit_diagnosis_20261015/attempt_14_settings_phase.json)、[未改原测试失败20](../../runs/recovery_native_cpu_limit_diagnosis_20261015/attempt_20_unmodified_test.json)、[逐次表](../../runs/recovery_native_cpu_limit_diagnosis_20261015/attempts.tsv)、[机器可读汇总](../../runs/recovery_native_cpu_limit_diagnosis_20261015/evidence_summary.json)。

## 基线、边界与调用链

- 冻结 SHA：`1927eeb00a7e0c1335f76340b0382f46102f08f2`；分支 `codex/recovery-native-cpu-limit-diagnosis-20261015`；独立工作树 `D:/wt/native-cpu-limit-diagnosis`。建立时 `git status --short` 空。主工作区既有未提交报告没有改动。
- 平台：Windows 11 `10.0.26200`，24 个逻辑 CPU；CPython 3.12.13、pytest 8.4.2。复用既有 `D:/wt/r06-feeds/backend/.venv/Scripts/python.exe`，用 `PYTHONPATH` 明确指向本诊断工作树 `backend/src`；没有安装依赖、下载模型或网络访问。
- 输入已读取 AGENTS、执行图、测试与运维计划、R20/R05 任务卡、状态及交接；新版 ponytail-review 已读取，用于核实真实调用者和最小修复建议。任务明确只诊断，覆盖原任务卡范围的写入限制；没有修改 progress、合同、依赖或盲测材料。
- Windows 虚拟环境启动器与真正执行 Python 的进程 PID 不同。样本 14 启动器 PID 6360 用户态 CPU 为 0，实际 worker PID 15896 用户态 CPU 7.703125 秒。所有 CPU 数字取实际 worker，而非只看 Popen 的启动器。
- limiter 两个生产调用者：PDF `_pdf_worker._bound_memory()`，512 MiB/15 CPU 秒；semantic `_bound_worker_memory()`，2 GiB/30 CPU 秒。前者由 `_pdf_worker.main()` 调用，父入口 `pdf_text.parse_pdf_text_layer()` 的 `communicate(timeout=20)`；后者由 `_semantic_worker()` 调用，父入口 `_run_worker()` 用 `multiprocessing.Process(target=...)`，总 deadline 最高 30 秒，并 terminate/kill/join 清理。两个入口另有墙钟时限，不等于本轮验证了 Windows 的 CPU 精确执行边界，也不把本次证据外推成真实模型/PDF 全链路结果。

已实际查看 `codebase-memory-mcp --help`、`cli index_repository --help` 与 `cli trace_path --help`，使用既有 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`。只复制冻结 `backend/src/ai_intel` 到 WSL `/tmp/dianzi-nativecpu-diagnostic-20261015/src`，fast 模式建立独立项目 `nativecpu_diagnostic_1927_src`，persistence=false；1085 nodes/5219 edges，未索引/跳过/partial/unusable 均为 0。索引与缓存均在工作区外。未执行工具输出提出的 ADR 写入建议。

CBM 的 limiter trace 找到两个直接调用者与其上游，semantic 局部 import 边置信度 0.38，且 `Process(target=...)` 不是普通函数调用边。因此逐一用 `rg` 与源文件核实，没有把图结果当作完整事实。参见 `cbm_limiter.log`、`cbm_pdf.log`、`cbm_semantic.log`、`rg_callers.log`；完整命令与退出码在 `audit_commands.json`（12 条，均 exit 0）。

## 已有失败证据

先用 rg 定位真实日志，而非根据目录名猜测。两组原失败/重跑：

| 记录 | 本地时间 | SHA | exit | 目标结果 |
|---|---|---|---:|---|
| r06-feeds `unit_final` | 18:19:54—18:20:31 | `7ed73540…` | 1 | TimeoutExpired 8s |
| r06-feeds `unit_recheck` | 18:23:57—18:24:29 | 同上 | 0 | 通过 |
| r06-feeds `fix1_green_combined` | 18:57:16—18:57:51 | `8e4d8a0a…` | 1 | TimeoutExpired 8s |
| r06-feeds `fix1_combined_recheck` | 19:00:11—19:00:46 | 同上 | 0 | 通过 |

日志根目录 `D:/wt/r06-feeds/reports/runs/recovery_r06_feed_parsers_20261015`。最初独立审查目录 `D:/dianzi/reports/runs/recovery_r06_feed_parsers_review_1_20261015` 也检索过，其独立组合 exit 1 不自动归为同一 CPU 失败。四组原命令、JUnit 中该测试的精确记录及日志/JUnit SHA-256 已保存在 `original_evidence.json`，未重写旧证据。

用 Git 对上述两个 SHA 与冻结 1927 核验：limiter blob 均为 `cb480569f0064a333a3ad7eeeae7534449d695c6`；原测试 blob 均为 `fe78d248bcdcf617982551c9e68f8ae8c1023de0`。本次观察不是通过修改该文件得到的。

## 有界实验与真实结果

23 次专门诊断，加完整 unit 中该目标 1 次，共 **24 次**，低于 30。专门诊断累计 167.682651 秒，含启动相位等待；完整 unit 命令 45.182113 秒；累计受控执行 **212.864764 秒**，低于 5 分钟。各命令实际 UTC 时间保存在逐次 JSON 和汇总中；这是各批执行耗时的总和，不把分析/阅读/报告的间隙计为连续压力运行。

| 尝试 | 负载/变化 | 次数 | 结果 | wall 秒 | worker 用户态 CPU 秒 |
|---|---|---:|---|---|---|
| 1—4 | 原样忙循环 payload | 4 | 均原生退出 | 3.614—7.015 | 3.266—6.891 |
| 5—8 | 同负载，增加 PID/Job handle 输出 | 4 | 均原生退出 | 6.994—7.071 | 6.391—6.797 |
| 9—12 | 同上，最多 4 个忙循环并发 | 4 | 均原生退出 | 6.869—7.055 | 6.594—6.688 |
| 13—16 | 读回 Job 配置；启动间隔 0/5.9/6.0/6.1 秒 | 4 | 14 到期仍存活；其余原生退出 | 6.596—8.024 | 6.406—7.703 |
| 17—20 | 调用原测试函数；间隔 0/5.9/5.9/5.9 秒 | 4 | 17—19 通过，20 TimeoutExpired | 1.082—8.026 | 本批未采样，避免伪填 |
| 21—23 | 同原函数；间隔 0/6.0/6.0 秒 | 3 | 均通过；22/23 为 7.981/7.987 秒 | 1.704—7.987 | 本批未采样 |
| unit | 默认完整 unit 门 | 1 目标尝试 | 1007 passed；目标 6.751 秒 | 命令 45.182 | 未采样 |

原生退出码均为 `3221225540`（`0xC0000044`）。样本 14 到期由诊断器清理后启动器 exit 1，Job 原生 terminated 计数仍 0；不能把它记成 native enforcement 成功。样本 20 则由原 `subprocess.run` 超时清理并抛出异常，完整 traceback 保留。

诊断最多 4 个受限 worker 同时执行（每个 100 MiB/1 CPU 秒配置，另有虚拟环境启动器），每次仍使用 8 秒 deadline；采样每约 0.2 秒记录真实进程 CPU、Job accounting、读管道线程状态和退出码。父诊断器到期仅清理本次创建的后代；超时样本原始日志没有删除。额外复制 Job handle 只用于 query；原样 payload 和未改测试函数也复现相关行为，不能将延后完全归给这个额外句柄。

原测试函数由 `runpy` 载入而不改写；仅包装 Popen 的构造调用以保留 PID 供收尾清理，参数和等待由原 `subprocess.run` 执行。该批不代替 pytest 门。随后完整 unit 保留 pyproject 默认 addopts，包括覆盖率门 60%，没有关闭或调低：1007 passed、0 failed、0 skipped、1 warning，覆盖率 66.60%，exit 0。warning 是既有 Starlette TestClient 弃用提示。

完整命令：

```text
cwd D:/wt/native-cpu-limit-diagnosis/backend
D:/wt/r06-feeds/backend/.venv/Scripts/python.exe -B -m pytest tests/unit -o cache_dir=D:/tmp/nativecpu-diagnostic-20261015/pytest-cache --basetemp=D:/tmp/nativecpu-diagnostic-20261015/pytest-temp --junitxml=D:/wt/native-cpu-limit-diagnosis/reports/runs/recovery_native_cpu_limit_diagnosis_20261015/unit.xml --cov-report=json:D:/wt/native-cpu-limit-diagnosis/reports/runs/recovery_native_cpu_limit_diagnosis_20261015/unit_coverage.json
```

`PYTHONPATH` 指向冻结 src；`PYTHONDONTWRITEBYTECODE=1`；coverage 与 pytest 临时缓存放在 `D:/tmp/nativecpu-diagnostic-20261015`。各诊断驱动命令、测量耗时和 exit 0 见 `evidence_summary.json.drivers`；驱动 exit 0 表示证据采集完成，**不表示其中的超时负例通过**。

## 最小复现与后续建议

在冻结工作树使用既有解释器设置上述 PYTHONPATH，然后运行：

```powershell
$env:PYTHONPATH='D:/wt/native-cpu-limit-diagnosis/backend/src'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'D:/wt/r06-feeds/backend/.venv/Scripts/python.exe' -B 'D:/wt/native-cpu-limit-diagnosis/reports/runs/recovery_native_cpu_limit_diagnosis_20261015/replay_unmodified_test.py'
```

默认最多 4 次、每次原测试保持 8 秒；一次完成后等 5.9 秒再启动下一次。本轮第 4 次复现同一 TimeoutExpired。也可先运行 `probe_native_cpu.py`（12 次，最多 4 worker 并发），再运行 `probe_phase.py`（4 次）取得 CPU/Job 对照。**相位方法是本机已成功的最小复现，不承诺每次或每个 Windows 版本都失败；复验仍须累计守住 30 次/5 分钟，不叠加无界重跑。**

最小建议：保留现有 8 秒负例、1 CPU 秒/100 MiB 与 Job 内存/退出清理设置，修补 Windows 实际 CPU 超限后的主动终止保障。优先评估由父进程按真正 worker 的 `GetProcessTimes` 监控并终止的最小实现；不要只监控 venv 启动器，也不要依赖可能被工作负载阻断的同线程协作。若调整公共 API/合同，先走变更记录；本报告没有替实现任务选定新合同。

复验必须同时证明：读回 CPU/内存配置仍正确；原测试与启动相位负例保留 8 秒且无 skip；接近阈值与超过阈值行为可观察；忙循环和实际调用者可清理；PDF 512 MiB/15 秒与 semantic 2 GiB/30 秒配置没有被改变；顺序及有界并发下不会遗留 worker/监护器。由另一名非作者复跑，保留失败和全部尝试；不能以“多跑几遍终于绿了”作为修复。

## 未检查、偏差与交接

- integration/live/manual：`not_run`；无真实模型/来源调用、无付费、无秘密/holdout 读取、无网络、无推送、无 accepted 登记。本次只为 E1/P1 的资源隔离与回归可靠性补证，不计成 R20 六项最终验收。
- Linux RLIMIT 路径只读代码，没有运行；不能由 Windows 结果推断其准确性。没有证明其他 Windows build 的检查周期，也没有恢复旧失败时的宿主并行进程快照。
- 没有新增或修改业务/原测试；诊断脚本仅存在本次 runs 目录，报告只存在指定 reviews 文件。未修改共享状态。完整 unit 与本次 CPU 负例之外的合同/集成/前端检查未运行。
- 下一任务：root 冻结本诊断证据后另派实现，再另派非作者审查。当前问题保持待修复，单次全 unit 绿灯只作为本次实际结果记录。

产物在独立工作树生成后复制到主工作区同名相对路径；逐文件 SHA-256 见 `artifact_hashes.json`。报告最终 SHA-256 由交接消息单独提供，避免自引用哈希。
