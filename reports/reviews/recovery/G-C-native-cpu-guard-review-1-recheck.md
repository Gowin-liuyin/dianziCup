# G-C · R20 native CPU guard 审查1定向复核

What this change does: 修复增加一个匿名生命周期 Job；guardian 独占其最后句柄，worker 入 Job 后释放本地句柄，使 guardian 硬退出由内核联动终止 worker 树。原资源 Job、CPU 采样、两个父调用方和预算保持。

**Verdict: Ship，原 Must 1 关闭。** 结论只覆盖 native CPU guard 修复及本次已执行范围；没有签整张 R20、G-C 或后续运维阶段 `accepted`，没有修改公共状态。

## 版本、独立性与时钟

- 延续首轮独立 reviewer 身份，未参与修复。以 `git worktree add --detach D:/wt/native-cpu-guard-review-1-recheck 3c99f37ef1993ab677e0d21b9d080975524d44b4` 创建新的干净复核目录；创建后状态为空，没有在作者或旧994c活动目录测试。
- 产品代码 SHA：`852472810b20b113606a0275ae6861326d39ebe8`；材料冻结/复核 HEAD：`3c99f37ef1993ab677e0d21b9d080975524d44b4`。两者 `backend/src`/`backend/tests` diff 为空，命令 exit 0。
- 本次修复 merge-base：`994c381edd2c4f0743d9c76f83abefaf51359f14`；初始修复基线仍 `45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b`。Git 已实际核对。
- limiter Git blob：`36c7e90f3e1d5423f943f66b5573ba80563c9854`，工作文件 SHA-256：`63ba29abba39fdc915c46787aba8fe84bac1dbc747c2b1085ed9e89975f85756`。原故障测试 blob 仍 `fe78d248bcdcf617982551c9e68f8ae8c1023de0`。
- 主工作区作者报告 SHA-256 为所交 `446bc34049c2ba9e103f7abef33139cb634f6b388ff96729417e910aae0da64a`。复核 worktree 的报告 raw SHA 为 `cbe4f9aa2145908504c2df709a59ab0a45dbc87780d2705f5a36960f9d085c79`；CRLF→LF 后与作者值精确一致。
- 有独立 receipt 的检查开始 `2026-10-15T21:55:30.238889+08:00`，最后检查结束 `2026-10-15T22:03:32.880636+08:00`；产物冻结时刻另记 `artifact_manifest.json`。这些是检查与写作记录，不是连续压力运行时长。
- Windows 11 `10.0.26200`、CPython `3.12.13` AMD64。命令使用现有依赖解释器 `D:/dianzi/backend/.venv/Scripts/python.exe`，cwd/PYTHONPATH 是新复核目录；缓存位于独立 `D:/tmp/nativecpu-guard-review-1-recheck-20261015` 和 WSL workspace 外。

复读实际 AGENTS、执行图、R20 recovery 合同/状态、原报告及新 diff，并继续使用最新版 [ponytail-review SKILL.md](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)。原 T45/T49/T50/T51 合同与原卡完整验收沿用首轮已读内容；没有以本次修复消除整 R20 的其他前置或缺测。

## Must 1 的原输入与修复后结果

首轮问题是就绪后 `time.sleep(0.4); os._exit(99)` 使 guardian 无法执行 Python 异常清理，worker 两次用2.25 CPU秒并成功输出结果。复核逐字复用首轮独立 `probe_review_windows.py`，在新 worktree 源码上运行，保持 **1 CPU 秒 / 8 秒 outer wall / 100 MiB**。没有修改业务文件或原输入。

| 原最小故障输入 | 新实际 CPU | 新实际 wall | 退出/结果 | 生命周期 |
|---|---:|---:|---|---|
| `guard_abrupt_exit_0` | 0.484375 秒 | 0.629084100 秒 | worker exit0；只有 READY，**无 `WORK_COMPLETED_AFTER_BUDGET`** | worker/guardian句柄均signaled |
| `guard_abrupt_exit_1` | 0.484375 秒 | 0.603304600 秒 | worker exit0；只有 READY，**无成功完整结果** | worker/guardian句柄均signaled |

完整命令、真正 worker/guardian PID、所有采样、stdout/stderr、开始结束时间和结果分别保存在同名 JSON。CPU 来自真正 worker 的 `GetProcessTimes`，不是 venv 启动器。原失败门仍是1秒CPU，2.25秒热点成功输出未被放行；本机 kill-on-close 的 exit0不能单独等同成功。

### 两个父边界及匹配成功对照

独立 `check_parent_boundaries.py` 再执行4个检查，使用真实子进程和真实 multiprocessing `spawn`/Pipe；没有用作者日志推断，也没有用假连接替代传输。

| 检查 | 实际生产父边界行为 | wall |
|---|---|---:|
| PDF，guardian同一硬退出 | `unparseable`，notes=`invalid pdf parser output`，空stdout没有被当JSON成功 | 0.670895秒 |
| semantic，guardian同一硬退出 | `SemanticRuntimeError("local semantic worker exited without a result")`；Pipe EOF被拒绝 | 0.665153秒 |
| PDF，关闭故障注入，其他scaffold一致 | 接受非空、合法页JSON，`parsed`，实际block包含`BOUNDARY_CONTROL_TEXT` | 2.177617秒 |
| semantic，关闭故障注入 | 完整真实Pipe响应通过生产`embed_query`的维度及归一化校验，384维结果 | 2.258671秒 |

两组成功对照证明父检查能够接受合法完整结果，故障通过并非一律拒绝。此处仅是显式合成 worker 的协议边界检查，不计真实 PDF内容/模型推理 live 验收。原父预算仍是 PDF 512MiB/15CPU/20wall、semantic 2GiB/30CPU/总deadline≤30秒。

本检查stdout中的4份结果保存在 `parent_boundaries.log`，抽取到 `parent_boundary_results.json`。最初数据文件名与包装器命令receipt同名，包装器覆盖了该JSON；stdout原始结果完整保留，已仅修正自有harness输出文件名并从原stdout恢复数据。没有业务变更、失败改pass或增加测试数。

## 源码与句柄所有权核对

`process_limits.py:241–250` 创建并配置生命周期Job为kill-on-close；`:100–114` 以固定inherit列表传递其只查询句柄（`0x4`），target仍只有查询/同步/终止权限。Guardian在原资源Job内启动，此时worker尚未加入生命周期Job，因此guardian不在该嵌套Job内。

Guardian在`:28–35` 验证句柄、CPU计量和就绪。父内的临时继承副本在`:151–152` 关闭；worker在`:258` 加入生命周期Job，`:266–267` 的finally关闭本地生命周期句柄。初始化完成后最后生命周期句柄只在guardian；硬退出会由内核关闭它并终止worker及后续子进程，与worker的GIL无关。原资源Job句柄仍返回caller持有，worker退出关闭该句柄，反向清理guardian/conhost，未改变公共返回合同。

若guardian在ready与worker入Job之间死亡，worker仍持有自己的生命周期句柄；赋入之后finally关闭最后句柄会终止worker，不能让它返回不受监督结果。失败启动的guardian kill/wait、ready/target/临时Job句柄与本地Job句柄关闭路径已逐行追踪；既有就绪超时零句柄增量检查独立通过。

嵌套Job与默认子进程继承语义已按 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) 和 [AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject) 核对。未支持或赋入失败仍拒绝执行，没有静默降级为无监督模式。没有增加guardian线程、监护进程、网络或新依赖。

没有在复核parent额外持有Job句柄，以免改变kill-on-close；生命周期断言只持有实际进程句柄。其他已证实缺陷：无。

## 实际回归与命令

每条检查的完整argv、cwd、HEAD、limiter hash、+08开始结束、exit code和wall保存在同名JSON；输出保存在同名log，正式pytest数量以JUnit为准。

| 检查 | exit | 实际范围/结果 | 证据 |
|---|---:|---|---|
| `pytest tests/unit/test_r05_process_limits.py tests/unit/test_r20_native_cpu_guard.py --no-cov -v` | 0 | **32 passed，0 failed，0 skipped**；15.684秒JUnit，17.071767秒命令wall | `original_and_guard.*` |
| 逐字首轮独立 `probe_review_windows.py` | 0，诊断捕获 | 20次：4正常CPU、4guardian故障、2树生命周期、10短任务/开销；0 outer timeout | `windows_probe.*`、20份命名JSON、`probe_summary.json` |
| 自有父边界+配对成功对照 | 0 | 4/4断言通过，真正Popen/spawn，故障与正常结果区分 | `parent_boundaries.*`、`parent_boundary_results.json` |
| `measure_process_tree.py` | 0 | 4次短生命周期，全部exit0，所有观察进程最终结束 | `process_tree_measurement.*`、`process_tree_memory.json` |
| 相同scaffold的994c/852增量开销 | 0 | 3旧+3新，全部结果保留且观察进程结束 | `incremental_cost.*`、`incremental_cost/` |
| 默认 `pytest tests/unit` | 0 | **1054 passed，0 failed，0 skipped，1既有Starlette warning**；4489/6681=`67.19054033827271%`，默认60%门未改；53.105秒JUnit、55.430254秒命令wall | `full_unit.*`、`full_unit_coverage.json` |
| `ruff check src tests` / `ruff format --check src tests` | 0/0 | 全通过，197 files已格式化 | `ruff.*`、`format.*` |
| `mypy --platform win32 src` | 0 | 85 source files无问题 | `mypy.*` |
| 当前SHA CBM index/trace；`rg -n bound_process_resources backend/src` | 0/0/0 | src-only图与caller原文交叉核对 | `cbm_index.*`、`cbm_trace.*`、`rg_callers.*` |
| 产品代码与材料SHA等价；原caller/故障测试无diff；`git diff --check` | 0/0/0 | 原协议、预算及冻结代码保持 | `code_frozen_equality.*`、`caller_budget_equality.*`、`diff_check.*` |

以上32项与默认1054项重叠，不相加成独立案例数。专用进程检查为20+4父边界+4树测量+6增量成本=34次；不把它冒称成整个pytest只创建了34个进程。热点最大2个并发；普通双native线程/kernel IO、native持GIL空闲、短结果、内存拒绝、输入类型/范围、guard启动失败、实际caller和句柄清理均在真实针对回归中复跑。

正常CPU采样4次为1.03125–1.0625总CPU秒、1.142295–1.185696wall秒，以`0xC0000044`结束，guardian同步结束。名义50ms采样及OS调度/量化延后仍存在；没有改1秒预算或承诺硬实时1.000000秒。Guardian可捕获异常2次仍结束worker；worker崩溃及关闭Job各1次，guardian和新建benign sleep leaf均结束。新增永久硬退出案例另覆盖忙Python/native持GIL Sleep/PBKDF2，每例断言没有完整结果、CPU小于原1秒、worker/guardian/leaf均退出。

完整默认命令（cwd为新独立backend）：

```text
D:/dianzi/backend/.venv/Scripts/python.exe -B -m pytest tests/unit -o cache_dir=D:/tmp/nativecpu-guard-review-1-recheck-20261015/pytest-full-cache --basetemp=D:/tmp/nativecpu-guard-review-1-recheck-20261015/pytest-full-temp --junitxml=D:/wt/native-cpu-guard-review-1-recheck/reports/runs/recovery_native_cpu_guard_review_1_recheck_20261015/full_unit.xml --cov-report=json:D:/wt/native-cpu-guard-review-1-recheck/reports/runs/recovery_native_cpu_guard_review_1_recheck_20261015/full_unit_coverage.json
```

### 作者红记录与断言调整

保留并核对作者`green_regression.log`：3例在`assert worker.returncode != 0`失败，实际stdout/stderr均空、exit0；当前冻结测试保留无`UNSUPERVISED_RESULT`、树进程全部signaled、CPU<1秒等功能断言，并新增两个生产父边界。去掉此本机原生终止方式不满足的非0格式假设，**没有放行成功完整结果或放宽CPU/内存/wall门**；本次独立最小输入和父正负对照证实这一点。

作者`fault_parents.log`的NameError确为新harness错置assert引用未定义`result`，不是产品故障；失败日志仍在。只把相关测试放回正确作用域；本次两个冻结父案例及独立4检查均通过。没有删除难例、改skip或动计分分母。

## 索引、材料、成本及未检查项

官方WSL CLI 0.11.0索引当前材料SHA的`backend/src`，项目`nativecpu_review_3c99_src`，fast/persistence=false；1120nodes/5426edges，not_indexed/skipped/partial/unusable全0。未索引secret、holdout或作者报告。Trace两caller及实际helper；semantic局部import边仍heuristic 0.38，结合rg/源码核对，未单靠图作保证。

作者fix1 manifest **109条**逐条核对：24条raw hash差异全部为Windows checkout换行；规范化LF后109条均匹配，0内容不符。原作者日志只作历史说明，不作为本次复跑数量。5个测试生成的ignored pyc在绝对路径/非reparse检查后迁到独立tmp，见`cache_moves.json`；不删除源码，不修改主工作区现有用户diff。

相同scaffold每组n=3：旧994c guardian初始化wall中位 **61.3763ms**，新852为 **64.5283ms**。这个小样本差约+3.152ms，不是长期延迟保证；资源树测量与最后部分成本运行有短暂重叠，不作为受控性能基准。稳态guardian句柄 **125→126**，多一个生命周期Job查询句柄；worker完成设置后句柄观察均138，没有新增本地生命周期句柄残留。新guard一份退出交界采样得到0句柄，原始记录保留，未当稳态计数。

该组旧guardian private **6,545,408–6,610,944 bytes**，新 **6,541,312–6,590,464 bytes**；不据此声称节省。两次新完整进程树另看到guardian private最大6,582,272/6,664,192 bytes和各一个隐藏conhost，conhost private **1,187,840/1,171,456 bytes**、working set各7,929,856 bytes，所有观测进程退出。新增一个Job内核对象的精确内存、长期高并发峰值/吞吐、所有系统辅助成本仍`unknown`；不能把进程working set相加当物理内存或把100MiB当整个树总cap。

Not checked: Linux实际RLIMIT、其他Windows/非标准基础解释器布局、真实模型推理、>2热点worker压力、长运行/句柄压力、外部特权修改Job/句柄、完整R20 integration/live/manual/security/监控/恢复/CI/CD均`not_run`。任意grandchildren的总CPU仍不计入worker采样，本修改不提供任意不可信代码沙箱。没有secret/holdout读取、收费API、模型下载、第三方资产扫描、push或公共状态变更。

E1只登记本地可信worker的限额与生命周期缺陷闭合证据，P1只登记有限成本采样，均不换成整项评分或阶段通过。下一建议由主控按准确冻结SHA整合这一限定Ship，并保留整R20/G-C尚未完成的其他验收项。
