# G-C · R20 native CPU guard 独立审查 1

What this change does: Windows disposable worker 仍使用原来的 Job 内存、原生 CPU 和进程树清理约束，另启动独立 CPython guardian，采样 worker 所有线程累计 user+kernel CPU。正常 guardian 能在 GIL 长时间占有及 native 热点中终止 worker；本次发现 guardian 就绪后的硬退出没有联动终止 worker。

**Verdict: Must fix 1 first.** 此结论仅覆盖提前独立的 R20 native CPU guard 修复，不验收整张 R20、G-C 或后续运维阶段。审查切片为 `needs_changes`；没有修改公共状态或写 `accepted`。

## 独立性、版本与范围

- 审查者未参与该实现。从冻结提交以 `git worktree add --detach D:/wt/native-cpu-guard-review-1 994c381edd2c4f0743d9c76f83abefaf51359f14` 创建独立目录，创建后 `git status --short` 为空；没有在作者活动目录执行测试。
- 审查 HEAD：`994c381edd2c4f0743d9c76f83abefaf51359f14`。冻结代码 SHA：`36884c7860434314174adac92dda1947f4469a81`。两者 `backend/src` 和 `backend/tests` 的 `git diff --exit-code` 为 0。
- 精确 merge-base：`45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b`，由 Git 核对。实际实现变更限于 `backend/src/ai_intel/infrastructure/process_limits.py` 和 `backend/tests/unit/test_r20_native_cpu_guard.py`，其余是作者报告/证据。
- limiter 工作文件 SHA-256：`2e7a8d9d9cb45b556595507bf0aa87f86f10898c031c32f52c7f9a8759f36039`；Git blob：`076a89a5fb5ba0628d64e51d849071825f6e9fb3`。原故障测试 blob：`fe78d248bcdcf617982551c9e68f8ae8c1023de0`，与基线相同。
- 已读实际 `AGENTS.md`、执行图、`contracts/task_manifest.json` 的 recovery R20、冻结状态、R20 作者报告、原 T45/T49/T50/T51 及其测试/运维/工作流合同。R20 原始完整前置、验收和 G-F 归属保留；本修复可独立检查的理由是只影响既有可信 worker 限额，不依赖尚未完成的全链路功能。
- 使用最新版 [ponytail-review SKILL.md](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，以源代码、调用者和真实行为确认发现；没有因风格偏好要求重构。
- 有独立命令 receipt 的执行开始：`2026-10-15T21:17:25.760281+08:00`；最后检查结束：`2026-10-15T21:25:32.801156+08:00`。最终报告与产物冻结时间另记在同目录 `artifact_manifest.json`，避免把写报告时间当测试时间。
- Windows 11 `10.0.26200`，CPython `3.12.13` AMD64。依赖解释器为 `D:/dianzi/backend/.venv/Scripts/python.exe`，但源码和测试 cwd/PYTHONPATH 来自上述独立 worktree。

只新增本报告和 `reports/runs/recovery_native_cpu_guard_review_1_20261015/`；无业务修复、合同/阈值/金标/分母修改，无 commit、push 或发布。主工作区已有未提交修改没有触碰。

## Must fix

### 1. Guardian 就绪后硬退出，worker 可超出 CPU 预算仍成功返回（P1）

**位置**：`backend/src/ai_intel/infrastructure/process_limits.py:120` 只在就绪时检查一次 `guard.poll()`；`:219–232` 后仅保留 Popen 和 worker 持有的 Job handle。`:45–51` 的异常清理依赖 guardian 仍能执行 Python 异常处理。

**职责与问题**：guardian 是此次补上及时总 CPU 约束的执行者。匿名事件握手之后，guardian 的不可捕获退出既不关闭 worker 持有的最后 Job handle，也没有被 worker 外部监督；因此内核不会仅因 guardian 死亡结束整个 Job。Python `except BaseException` 可以处理普通异常，不能处理进程硬退出、native 致命崩溃等路径。

**最小复现输入**：只在 disposable 测试子进程内替换模块中的固定 guardian 代码，在原 `ready_handle = 0` 后、监控循环前插入以下故障。没有修改冻结文件。

```python
import time, os
time.sleep(0.4)
os._exit(99)
```

worker 原样调用 `bound_process_resources(memory_bytes=100*1024**2, cpu_seconds=1)`，就绪后执行一个自限额的热点，避免无界占用：

```python
sys.setswitchinterval(60)
while time.process_time() < 2.25:
    pass
print('WORK_COMPLETED_AFTER_BUDGET', time.process_time(), flush=True)
```

驱动保持 **8 秒墙钟、1 CPU 秒、100 MiB**，观察真实 worker 的进程句柄与 `GetProcessTimes`，不把 venv 启动器 CPU 当 worker CPU。完整输入/argv、过程采样、stdout、退出码、开始结束时间见 `guard_abrupt_exit_0.json`、`guard_abrupt_exit_1.json` 和 `probe_review_windows.py`。

| 独立运行 | 实际 worker 结果 | 实际 worker 总 CPU | 实际 wall | 预期 |
|---|---|---:|---:|---|
| abrupt_exit_0 | exit 0，输出 `WORK_COMPLETED_AFTER_BUDGET 2.25` | 2.25 秒；user 0.984375 + kernel 1.265625 | 2.359480200 秒 | guardian 非正常退出后拒绝继续工作，不能成功返回超预算结果 |
| abrupt_exit_1 | exit 0，同样输出超预算结果 | 2.25 秒；user 0.953125 + kernel 1.296875 | 2.409814700 秒 | 同上 |

guardian 均已结束。两个观测确认的是**隔离硬退出故障下注入的 fail-closed 缺口**，不推断现实事故频率，不把它扩大为高权限攻击者强对抗承诺。原生 Job fallback 只约束 user-mode CPU，不能替代已丢失的总 CPU 监护；父墙钟超时也不会拒绝本例中及时返回的成功结果。[Microsoft Job 基本限额](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information)

**影响**：可信 worker 的 guardian 因致命错误或其他不可捕获原因死亡后，CPU 预算执行失效；即使父墙钟尚未到期，也能把本应被拒绝的超预算工作结果当成功返回。这违反本批明确检查的崩溃 fail-closed 范围。

**最小修复方向**：把 guardian 死亡与 worker/Job 终止建立 worker GIL 之外的联动。可由既有可信父进程监督 guardian 退出句柄并终止 worker，或用 guardian 独有的 kill-on-close 监督 Job 实现内核联动；保留现有资源 Job 返回接口、内存/CPU/墙钟预算与有限权限边界。仅在 worker 中增加 Python 线程轮询不能覆盖本修复针对的 GIL/native 热点。

**复验要求**：保留本次两份红 receipt；新增就绪后硬退出回归，确认结果不得成功返回，worker/guardian/子进程均结束且句柄清理。再跑普通 guardian 异常、native/GIL、短任务、内存、初始化失败与两个实际 caller，以及默认 unit/静态检查。此次没有修改业务，所以修复后的复验为 `not_run`。

对照：同一插入点改为 `raise RuntimeError(...)`，两次 worker 在 0.4375/0.5 总 CPU 秒、0.5664/0.5650 wall 秒以 `0xC0000044` 结束。说明当前可捕获异常路径有效，缺陷集中于 guardian 无法执行清理的死亡路径。

## 已核实的行为与合同

1. 原故障测试、原内存测试和新增 native/GIL/双线程/kernel IO/空闲/短任务/初始化失败/真实 caller/失败句柄测试合计 **27 passed，0 failed，0 skipped**。原故障测试保持 8 秒超时，CPU/内存仍为 1 秒/100 MiB。
2. 独立进程句柄采样另执行 GIL、PBKDF2 native 及两 worker 并发共 4 次。worker 总 CPU **1.015625–1.0625 秒**，wall **1.158364–1.186914 秒**，全部 `0xC0000044` 结束，guardian 也已结束；这里包含量化/调度延后，不能说严格 1.000000 秒。
3. guardian 可捕获异常 2 次联动终止；worker `os._exit(77)` 和显式关闭 Job 各 1 次，观察到 guardian 与新建 benign sleep leaf 的退出句柄全部 signaled。正常短任务 10 次（5 旧基线、5 新路径）均保留 `RESULT_OK`；另有 4 次短进程树/资源测量全部 exit 0、观测进程全部结束。
4. 就绪超时测试仍精确检查热身后的句柄数无增量及 child 已 reaped，独立复跑通过。正常 Job/Popen handle 的持有期仍是一次调用的 disposable worker 生命周期；没有把它宣称为长期多次调用的服务管理器。
5. 两个生产调用方和原测试相对 merge-base **无 diff**：PDF `_pdf_worker.py:23` 仍 512 MiB/15 CPU 秒，`pdf_text.py:56` 仍 `communicate(timeout=20)`；semantic `semantic.py:393` 仍 2 GiB/30 CPU 秒，`:181–190` 总 deadline 仍不超过 30 秒，`:241–289` 使用既有截止时间和 terminate/kill/join。语义 worker 的局部 import 由 `rg` 和原文确认。
6. guardian 用固定 `sys.base_prefix/python.exe -I -S -c`，有限 target handle 权限与单独 ready event，标准流为 DEVNULL、无可见窗口；仅转交 SYSTEMROOT/WINDIR，没有转交业务内容或秘密。没有新依赖、通用工具或可输入任意脚本的产品接口。
7. 保持单进程提交内存限额及进程树继承 Job；没有把 100 MiB 误述为整个树的总量 cap，也没有声称任意 grandchildren 的总 CPU 纳入 worker 的采样预算。当前两个 caller 不在工作负载中运行任意子程序，PDF 外部 JBIG2 保持禁用。

CPU 所有线程累计 user/kernel 字段含义已按官方 [`GetProcessTimes`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes) 核对。Job 最后句柄关闭结束关联进程的含义按 [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects) 核对；此次进程树断言使用真正进程句柄观察，没有在 parent 额外持有 Job handle，避免影响 kill-on-close。

## 来源索引与作者证据核对

实际运行 WSL 官方 CLI `codebase-memory-mcp 0.11.0`，先读取 CLI help。当前 SHA 的独立 `fast/src-only` 索引项目为 `nativecpu_review_994c_src`，repo path 指向审查 worktree 的 `backend/src`，persistence=false；1120 nodes、5426 edges，not_indexed/skipped/partial/unusable 均为 0。没有索引秘密、holdout、作者 reports 或整个仓库。

`trace_path(bound_process_resources, both, depth=4)` 显示两条 caller 及 `_pdf_worker.main`/`_semantic_worker`。图中的 semantic 局部导入边为 heuristic confidence 0.38，因此没有单凭图推断完整调用链；与 `rg_callers.log` 和原文交叉验证。索引缓存在 WSL 用户缓存中、workspace 外；Python/Ruff/mypy/pytest/coverage 的缓存位于 `D:/tmp/nativecpu-guard-review-1-20261015`。

作者 95 个 manifest 条目（94 个 runs 文件加报告；runs 另含 manifest 自身，共95文件）已逐文件核对。24 个 Windows checkout 原始哈希与作者值不同，全部是 CRLF→LF 规范化后精确匹配；无内容不符。两份核对 JSON 保留原始和规范化 hash，不把换行差异当篡改，也不将哈希核对计为独立重跑作者全部实验。作者历史红/绿日志仅作为线索，本报告的结论来自独立执行结果。

生产 PDF 父环境过滤不传递 `PYTHONDONTWRITEBYTECODE`，本次测试生成 5 个 ignored pyc。只把这次干净 worktree 中生成的 pyc 迁到上述独立 tmp；移前核对绝对路径位于 `backend/src`、无 reparse point、目标位于独立 cache 根，记录在 `cache_moves.json`。没有删除源码或用户文件。最终跟踪文件无改动。

## 实际检查、退出码与数量

全部 argv、cwd、+08 开始/结束、退出码、HEAD、limiter SHA-256 保存为同名 JSON，stdout/stderr 保存在同名 log。以下不把诊断驱动 exit 0 当全部行为通过。

| 检查及核心命令 | 退出码 | 范围/结果 | 证据 |
|---|---:|---|---|
| `pytest tests/unit/test_r05_process_limits.py tests/unit/test_r20_native_cpu_guard.py --no-cov -v` | 0 | 27 passed / 0 failed / 0 skipped；12.739 秒 pytest，14.1506 秒命令 wall | `original_and_guard.*` |
| `python -B probe_review_windows.py` | 0，诊断捕获 | 20 次：4 CPU、4 guardian 故障、2树生命周期、10开销；**2次硬退出后的超预算成功是缺陷**，0 outer timeout；15.3687秒命令 wall | `windows_probe.*`、20个命名 JSON、`probe_summary.json` |
| `python -B measure_process_tree.py` | 0 | 4 次 benign 短进程；全 exit 0，观测句柄全已退出 | `process_tree_measurement.*`、`process_tree_memory.json` |
| `pytest tests/unit`，保留 pyproject 默认 cov 和 60% 门 | 0 | **1049 passed / 0 failed / 0 skipped，1既有 Starlette warning**；4478/6665 = 67.18679669917479%；46.539 秒 JUnit，48.7868 秒命令 wall | `full_unit.*`、`full_unit_coverage.json` |
| `ruff check src tests` | 0 | 全 src/tests lint 通过 | `ruff.*` |
| `ruff format --check src tests` | 0 | 197 files already formatted | `format.*` |
| `mypy --platform win32 src` | 0 | 85 source files 无问题 | `mypy.*` |
| CBM 当前 SHA index / trace；`rg -n bound_process_resources backend/src` | 0 / 0 / 0 | src-only 图与实际调用者交叉核对 | `cbm_index.*`、`cbm_trace.*`、`rg_callers.*` |
| 冻结代码等价、caller/原测试基线等价、`git diff --check` | 0 / 0 / 0 | 未改变冻结业务或原预算 | `code_frozen_equality.*`、`caller_budget_equality.*`、`diff_check.*` |

完整命令示例（真实执行，独立 backend cwd）：

```text
D:/dianzi/backend/.venv/Scripts/python.exe -B -m pytest tests/unit -o cache_dir=D:/tmp/nativecpu-guard-review-1-20261015/pytest-full-cache --basetemp=D:/tmp/nativecpu-guard-review-1-20261015/pytest-full-temp --junitxml=D:/wt/native-cpu-guard-review-1/reports/runs/recovery_native_cpu_guard_review_1_20261015/full_unit.xml --cov-report=json:D:/wt/native-cpu-guard-review-1/reports/runs/recovery_native_cpu_guard_review_1_20261015/full_unit_coverage.json
```

早期一次路径检索对不存在的 `contracts/manifest.recovery.json` / `docs/plan/tasks` / `docs/contracts` 返回 1；随后按实际 `contracts/task_manifest.json` 的 recovery 字段和 `docs/tasks` 读取。此为检索命令路径错误，不是业务测试失败；没有据此虚构合同缺失。没有收费 API、下载模型、外部业务网络或扫描第三方资产。

## 独立资源开销与未检查项

5 次旧基线+5 次新路径的 limiter 调用 wall 中位分别 **1.282600 ms**、**65.371700 ms**，本组增量中位 **64.089100 ms**。这与作者 n=3 时约 +84ms 同为有限本机测量，不取其中更小值当性能保证。

新路径 5 个 guardian 的 live 采样 private 为 **6.254–6.273 MiB**，working set **13.207–13.219 MiB**；另外2个完整进程树测量的 guardian private为6.234/6.238 MiB。两次新路径各观察到一个隐藏 `conhost.exe`，private **1.1328125/1.140625 MiB**，working set **7.55859375 MiB**；baseline 两次未观察到此新 conhost。所有已观察句柄最终 signaled。

这些是单次短生命周期 live 采样的进程级成本，不是长期峰值、吞吐、整机物理内存增量或所有系统辅助成本。working set 有共享页，不能简单累加作物理内存；未观察到的系统外部资源、持续负载的全部 conhost 成本仍 `unknown`。原100MiB只是各受限进程的提交内存 cap，新增进程带来的总成本必须继续披露。

Not checked: guardian 硬退出的修复后行为 `not_run`；Linux 真正 RLIMIT、其他 Windows/非标准基础解释器布局、真实模型 native 推理、更多于2个热点 worker的负载、长期进程/句柄压力、全链路 integration/live/manual、安全/监控/备份恢复/CI/CD 的整 R20 验收均 `not_run`。此处没有把无外部凭据改为通过，也没有修改任何评分阈值或分母。

E1 证据限于本地可信 worker CPU/内存/正常及故障生命周期，且硬退出缺陷阻止本切片 Ship；P1 只保留有限采样与开销，不计正式性能成绩。下一项建议是由原作者最小修复发现1，冻结新代码，再进行独立定向复核。没有其他已证实缺陷或 Lean 删减建议。
