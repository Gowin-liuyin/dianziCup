# G-F · R20 固定 8a 的 Windows CPU / READY 根因诊断

What this change does: 本次不改业务，只在固定 8a 建立独立最小复现、记录真正 worker 的 Win32 返回值与 kernel/user CPU，并把四个失败拆成「READY 前预算已耗尽」和「READY 后 guardian 故障窗口」两类。**GetProcessTimes 失败没有在本次有效样本中出现；有些无结果是当前代码正确 fail closed，但启动接管太晚，仍无法满足原正常结果/严格 CPU 合同。**

任务状态：诊断产物 `awaiting_review / complete`；业务修复 `not_started`。原四节点本轮 **2 failed / 2 passed / 0 skipped**，R20 产品仍 `needs_changes`，不签整 R20、G-F、E1/P1 或任何阶段 passed/accepted。最后一个 worker 于 **2026-10-16T03:12:20.282402+08:00** 结束；达到 **20/20** 后停止采样。

## 1. 冻结、授权与写入范围

- 独有 worktree：`D:/wt/r20-8a-diag/codex/r20-8a-cpu-guard-diagnosis`；branch `codex/r20-8a-cpu-guard-diagnosis`；固定完整 SHA **`8a1b04d48346d8550f0326a77f003246a0ebbab5`**。
- limiter 工作文件 SHA256 `0e427be27ddce7ec2abb6ef183acb1df7008d112e0ea3a2b9b9ba9f86fe4dc56`；原 guard 测试 SHA256 `d36f79a39904c2f03fb11cae415835c79f45a07dde6c207fd04be95373167261`。全部源/测试/锁/公开 PDF 输入身份见 `execution_summary.json.identity.sources`。
- 仅读 AGENTS、执行图、R20 卡、task_manifest、固定 state/交接、T45/T48/T49/T50、04/06/09 合同、原 852 guard 报告/两轮 review、原 CPU/启动诊断、535 startup 作者报告与限定 review；使用 Ponytail 5.2.0 full/review。旧公共 state 的 `pending/not_started` 是冻结历史，不被当作当前产品无实现，也没有覆盖 root 正在更新的公共状态。
- 仅新增本报告及 `reports/runs/recovery_r20_8a_cpu_diagnosis_20261016/`；没有改业务、原测试、阈值、依赖、公共合同、状态、金标、skip 或分母，没有 spawn、提交、push、PG/network/model/provider/秘密/第三方资产/PoC 动作。
- 本 worktree 自有 `uv sync --locked --offline` exit 0，CPython 3.12.13 / Windows 11 build 26200。uv 已安装本项目 editable，实际 limiter `__file__` 指向本 worktree，`direct_url.json` 为本 backend / editable=true；不依赖另一 worktree 的 PYTHONPATH 来补子进程 import。环境日志为 `environment_uv.log`。第一次日志目录相对路径写错，在 uv 执行前失败；原工具错误保留在交付说明，没有把未执行的那次记成 sync 成功。

永久门保持：CPU 热点 **1.0 CPU / 3.0 wall**；原 worker **8 秒**；PDF **512MiB / 15CPU / 父 20wall**；semantic **2GiB / 30CPU / 总 deadline≤30 秒**；整体 coverage **60%**。本次不是严格 CPU 修复验收。

## 2. 原四红及本次最小复现

原集成日志经 rg 定位于独立 validator 的 `D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_full_pure_actual.stdout.log`、`backend_full_pure.xml`。其 **2489 passed / 11 failed / 10 deselected，77.22%** 中只有下表四个 R20 红项；另外七项已由 validator 的独立环境复核证明并得到 7 pass，不在本报告重分类或混计。

| 原测试 / 输入与预期 | 8a 原集成实际 | 本次真实复现 / 精确代码位置 | 根因确定性 |
|---|---|---|---|
| `test_short_cpu_task_keeps_its_result`：1CPU/100MiB 后 `sum(range(100_000))`；8 秒内 exit0、`RESULT 4999950000` | exit **3221225540 / 0xC0000044**，stdout/stderr 空；测试 `:86` | 未改原节点本次 pass，实际 worker 0.859375CPU。有效 coverage 仪器样本再次得相同退出码、无 RESULT：entry 0.984375、before-bound 1.0、guardian 首读 **1.015625**，未 SetEvent 即终止，终态 **1.03125**。limiter `:30–35/:51–58` | **确认该最小场景是预算耗尽 fail closed，非 API 读失败**；原集成那次未保存 guardian 内部诊断，逐次 API 原因仍 unknown，不能把本次分段冒称原次分段 |
| hard-exit `[python-gil-held]`：guard READY 后 0.4 秒 `_exit(99)`，worker 高 GIL 忙循环；应先输出 TREE、无完整结果、三进程退出且总CPU `<1` | TREE 为空，测试 `:143` | 原节点本次已输出 TREE、树退出，但 kernel **0.71875** + user **0.671875** = **1.390625**，在原 `:154` 红。受控同输入在 bound 前先用 1.0625CPU，首读1.078125、无 READY/TREE，终态1.09375，复现原空 TREE 的可达路径 | **确认早期耗尽可导致原空 TREE，确认当前原节点仍超总预算**；原次空 TREE 的具体 Win32/Job 分支无法回溯确证 |
| hard-exit `[native-gil-held-idle]`：同故障窗，`ctypes.PyDLL('kernel32').Sleep(2000)`；无结果、树退出、总CPU `<1` | kernel **0.578125** + user **0.421875** = **1.0**，测试 `:154` | 原节点本次0.890625CPU/pass；有效 coverage样本0.90625。受控近预算样本：首读/READY **0.984375**，leaf 创建后、Sleep 前 **1.0**，终态仍 **1.0**，原 `<1` 关系为 false；guard 实际 exit99、worker/leaf exit0且signaled | **确认空闲调用无需新增CPU也能红**，因为被断言的是从进程创建累计的总CPU；原次启动/leaf分段 unknown，不能说 Sleep 消耗了1秒 |
| hard-exit `[native-cpu]`：同故障窗、100M PBKDF2；总CPU `<1` | kernel **0.609375** + user **0.703125** = **1.3125**，测试 `:154` | 未改原节点再次红：kernel **0.375** + user **0.796875** = **1.171875**。有效 coverage仪器：READY **0.796875**，终态 kernel **0.40625** + user **0.796875** = **1.203125**；故障窗无 CPU 采样 | **确认 READY 后可超累计 kernel+user**，即使 user 尚 `<1`。不能归给正常50ms循环，因为该测试已绕过整个循环 |

原四节点的完整最小命令保存在 `original_four.json.argv`，实际已执行一次：

```powershell
cd D:/wt/r20-8a-diag/codex/r20-8a-cpu-guard-diagnosis/backend
& .venv/Scripts/python.exe -B -m pytest `
  tests/unit/test_r20_native_cpu_guard.py::test_short_cpu_task_keeps_its_result `
  'tests/unit/test_r20_native_cpu_guard.py::test_guard_hard_exit_after_readiness_terminates_worker_tree[python-gil-held]' `
  'tests/unit/test_r20_native_cpu_guard.py::test_guard_hard_exit_after_readiness_terminates_worker_tree[native-gil-held-idle]' `
  'tests/unit/test_r20_native_cpu_guard.py::test_guard_hard_exit_after_readiness_terminates_worker_tree[native-cpu]' `
  -v --junitxml=../reports/runs/recovery_r20_8a_cpu_diagnosis_20261016/original_four.xml `
  --cov-report=json:../reports/runs/recovery_r20_8a_cpu_diagnosis_20261016/original_four.coverage.json `
  -o cache_dir=../reports/runs/recovery_r20_8a_cpu_diagnosis_20261016/pytest_cache `
  --basetemp=../reports/runs/recovery_r20_8a_cpu_diagnosis_20261016/pytest_temp
```

该命令 **exit1**：2 行为红，另外局部 coverage **3.71% < 原60%** 门也失败，两个失败原因分别保留。没有使用 `--no-cov` 使其绿，也没有重复整仓 unit。诊断器 exit0 仅表示 raw 采集完成，不表示内部行为通过。

## 3. READY、Win32 返回值与终止路径

源码 `process_limits.py:233–241` 先设置原 process CPU/内存 Job、分配真正当前 worker，然后 `:243–269` 建 exclusive lifetime Job、启动 guardian、再把 worker 分配给 lifetime Job。guardian `-I -S`、基础 Python、SYSTEMROOT/WINDIR 白名单、独立 process handle；计时不是 Popen 的 venv redirector PID。`DuplicateHandle` 的目标权限、继承列表、事件及 Job 分配在有效仪器样本中均成功。

**1. 初始已耗尽不会 READY。** `coverage_valid_short` 中 `GetHandleInformation` success/error0，`GetProcessTimes` success/error0，读数 kernel5,000,000 + user5,156,250 ticks。随后 `TerminateProcess(target, 0xC0000044)` success/error0，没有 SetEvent；被捕获 stderr 为 `OSError: CPU budget exhausted before readiness`。产品 guardian stderr 原本 `DEVNULL`（`:134–135`），所以单凭旧 stdout空/退出码无法区分该原因与其他初始化失败。本次捕获使用独有诊断文件，未改生产日志或异常协议。

`controlled_initial_exhausted` 另观测首读1.078125CPU、GetProcessTimes成功/error0、无 SetEvent/TREE，worker实际退出码0xC0000044、guardian实际exit1。这是主动总预算拒绝，不能命名为 GetProcessTimes API 错误。所有 **8343** 个外部 CPU 查询记录均成功/error0；本次不存在可报告的真实 Win32 计时失败码。**原集成四次的内部 last-error 未记录，仍未知。**

**2. 原故障注入取消的是整个正常监督循环。** 原测试 `:98–113` 把 `"    while True:\n"` 前插入 `sleep(0.4); os._exit(99)`；guardian FIRST GetProcessTimes/SetEvent仍执行，但 `:39–50` 的 50ms wait、后续 CPU 查询、主动 TerminateProcess 全部不执行。有效 native样本的 guard 首读0.796875、SetEvent成功/error0、故障窗开始、约0.391秒后 `_exit`；没有第二次GetProcessTimes或主动TerminateProcess。native/Python样本跨此窗口继续消耗CPU。near-budget idle的实际guard exit99、worker/leaf exit0、所有句柄signaled，符合当前 last-lifetime-handle close 清树路径；不把 exit0当作完整结果成功。

**3. 原生 Job 设置与总CPU断言不是一套可替代的保障。** 此次 SetInformationJobObject success/error0，原 flags258、process_time10,000,000、memory104,857,600保持。原节点/native有效仪器中 user分别0.796875/0.796875，均低于1秒，而 kernel+user分别1.171875/1.203125已经超1。加上 guard 在故障窗完全不采样，已足以否定「这个兜底能保证原累计kernel+user `<1`」的主张。Windows Job PROCESS_TIME 的 user-only口径见既有独立诊断中的官方资料引用，本轮按零网络授权未重新访问网页；没有捕获 Job accounting readback、内核调度/ETW或某次原生Job终止事件，不能追加其内部周期的普遍结论。

**4. 普通50ms采样的严格上界仍未证明。** `normal_poll_coverage` 的 entry已有1.0625、首读1.09375即拒绝，未进入轮询。其名字不能被当成普通poll新证据。此前独立 startup review 的正常CPU四样本1.0–1.109375只作为历史观测，不冒充本轮复测。当前所有8343条kernel/user计时均为 **15.625ms 整倍数**；这是本机观测粒度，不是API100ns单位对应的精度保证，也不是硬件或调度的可证明最大延迟。不能把1.0改成`<=1`、加0.3125误差或预热/sleep等待碰绿。

## 4. coverage、仪器和负载对照

默认 pytest 的 `--cov=ai_intel` 由本项目 pyproject 提供；安装的 `pytest-cov.pth` 检测继承 COV_CORE_SOURCE，在 site初始化执行 `pytest_cov.embed.init()`。本地 `pytest_cov/engine.py:118–134` 构造COV_CORE_SOURCE/config/datafile；`embed.py:24–63` 在 `-c` 脚本前导入coverage并start。原 worker继承该环境，guardian自身 `-I -S`与环境白名单不继承coverage。此链路由安装文件/原默认命令和有效样本的 `Coverage.current()` 共同核对，没有用 import了coverage 就冒称 tracing已开启。

| 同一仪器代码、单worker顺序对照 | 有效coverage entry / READY / final CPU | 无coverage entry / READY / final CPU |
|---|---|---|
| short | 0.984375 / **未READY：首读1.015625** / 1.03125 | 0.09375 / 0.140625 / 0.15625，保留RESULT |
| Python hard-exit | 0.875 / 0.90625 / 1.328125 | 0.078125 / 0.125 / 0.515625 |
| native idle hard-exit | 0.875 / 0.90625 / 0.90625 | 0.0625 / 0.09375 / 0.109375 |
| native CPU hard-exit | 0.78125 / 0.796875 / 1.203125 | 0.078125 / 0.109375 / 0.515625 |

无coverage组是明确的单变量诊断对照，不计原默认门通过。有效coverage组明确 `coverage_active=true`，无coverage组false；两个组保持1CPU/100MiB、故障0.4秒及8秒外层不变，没有同时加人工背景负载。单worker已经复现超总CPU，故本次无需额外并行压力对照；未控制整台机器上其他任务，因此不能给无竞争/高并发性能结论。

instrumentation会增加ctypes/json导入、函数包装和日志成本，entry包含site、coverage、代码编译与仪器早期执行，**不能精确拆成纯coverage初始化耗时**。与未改原四节点分开保留；例如原short本次0.859375CPU/pass，而仪器short跨1秒。对照确认coverage启动路径显著占用预算，原红再次出现于未改Python/native节点；不能把instrumented绝对数值替成旧原红分段。

自有第一组四样本把COV_CORE_CONFIG误写成字面`os.devnull`，stderr ConfigError，旧字段仅检测模块导入而误写 `coverage_active=true`。**原记录没有改写**，执行版本为 `executed_diagnose_initial_bad_config.py`，summary把该组标为「只产生coverage导入成本，tracing未激活」。修正为实际平台os.pathsep并检查Coverage.current后，只执行新的有效组；四个错误样本仍计入20，不计有效coverage对照。另有三次CBM未带project前缀的qualified name查询失败，及一次WSL把regex `|`当shell管道导致exit127；所有command/log保留，随后实际search_graph返回的全名才trace成功。

## 5. 真实调用方与正常业务对照

官方 WSL Ubuntu-22.04/root portable CLI **0.11.0**，先实际help/schema，独有src index `r20_8a_diag_src_20261016`：**1409 nodes / 7128 edges**，not-indexed/skipped/partial/unusable均0；工具另外明确 **excluded `ai_intel/assets` 一目录**，不把这部分说成已索引。未采纳工具ADR写入建议。qualified limiter、PDF父、semantic worker trace成功，src之外tests/脚本只用rg/源码/AST，不伪称在图中。

两个直接caller仍为 `_pdf_worker._bound_memory`（`:18–20`）与 `semantic._bound_worker_memory`（`:389–393`）。semantic局部import边为heuristic0.38；`Process(target=_semantic_worker)`在图里没有普通caller边，已用 `semantic.py:242–247/308–334` 核对，不能用graph零caller说无人调用。

- PDF：`catalog_pages` NIST PDF分支 / parsers re-export → `pdf_text.parse_pdf_text_layer` → 固定模块Popen（`:44–54`）、容量2和白名单环境 → `_pdf_worker.main`先设512MiB/15CPU，再import pypdf（`:69–76`） → pages/notes JSON → 父20秒communicate、退出码/大小/结构/页号/文本校验（`pdf_text.py:56–93`）。生产PDF父不透传COV_CORE，而原直接 `-c` guard测试会继承，这是实际启动条件差异。
- 本轮 **真实生产父**读取官方四页PDF，结果 `parsed`、4blocks、原页号 `[1,2,3,4]`，exit0、outer wall1.266秒，实际PDF worker PID46220 **0.921875CPU**；全部7个观察进程结束。源码/原生产Popen未注入，输出不包含PDF正文。**没有在真实父内记录READY分段，不能虚构preREADY CPU。**
- semantic：LocalSemanticModels → `_run_worker`在spawn前建立≤30秒总deadline → 真spawn/Pipe → `_semantic_worker`先2GiB/30CPU，再模型校验及tokenizers/onnxruntime/numpy动态import → 信封/数值校验，EOF拒绝成功，finally有限terminate/kill/join。继承父coverage，所以还需要覆盖真实启动条件。
- **本轮没有新增semantic正对照worker**，20上限已到。先前非作者 `r20_startup_fix_review_1_20261016/semantic_coverage_recheck` 实测coverage活跃、entry0.515625、bound后0.53125、真实spawn/Pipe及384维**合成**合法信封；原真实模型/重库未运行。它只说明原30CPU协议能保持正常合成输入，不是本轮新测或真实模型能力。本轮不可据此关闭semantic真实正常推理与预算余量的验收。

## 6. Must fix 与最小下一方案

1. **启动预算在helper取得控制前被花掉。** What this is: 原 `sys.executable -c`先site/coverage，后import limiter；GetProcessTimes计累计CPU。Problem: 已达到1秒仍要求正常short结果，与后来才取得控制的安全拒绝无法同时由helper保证。Fix: root另派新作者，在已有PDF固定Popen和semantic固定spawn这两个真实接缝设计轻量、固定、白名单的早期bootstrap；先在真正worker执行site/coverage/重库之前取得process handle、Job与独立监督，再保留coverage对实际功能代码的执行。**不能仅给 `_start_windows_cpu_guard` 再加判断；不能回滚初始exhausted failclosed、重置baseline、减去启动CPU或清掉原默认coverage。** If we skip it: short/空TREE仍依赖启动CPU波动，任何后置判断都会在安全拒绝与正常结果之间继续碰撞。

2. **单个guardian故障窗没有累计总CPU保障。** What this is: READY后guard停止监督0.4秒，直到其退出才关闭Job清树。Problem: 有效READY可只剩0.09–0.20CPU；即使user<1，累计kernel+user仍超过1，idle创建leaf也能刚好到1。Fix: 新作者评估由现有父进程持有真正worker handle并在guardian故障期间继续监督的最小接缝，清树仍保留exclusive Job；将原4个边界放在该真实早期启动接缝复验。接口、测试入口或公共计量语义若要变动先交CR，不静默改原测试。If we skip it: failclosed清树能保证没有完整结果，却不能追回已消耗CPU，严格原1秒红不闭合。

**方案的可证边界：** 提前parent/轻量bootstrap和额外监督在Windows可实施，但本轮没有证明任何轮询/调度/异步TerminateProcess具有硬实时上界。因此不能写「改为1ms poll」或任意magic余量就保证所有情况下 `<1`。若实现者主张提前failclosed留余量，必须实测并记录同一合同下的startup CPU、最大在飞native线程数、计时量化和监督失效后的消费界；同时让正常四页PDF和semantic成功输入完成，不能把全部正常输入拒绝当安全通过。

对当前caller，PDF仍有原15CPU、semantic原30CPU，不得把一秒测试的固定0.4秒故障余量粗暴套成所有输入的新业务阈值；PDF成功样本0.921875CPU和既有semantic合成成功只给局部证据，真实semantic重库/推理成本还必须取得。保留原1/3/8以及60门，若当前一般用途Windows无法给kernel+user绝对硬界，root应提交**具体平台/合同不可证项**，而不是再派大补丁直到偶然绿。此处是未实施的最小设计方向，不是替代算法、合同批准或修复通过。

## 7. 下一作者/独立reviewer的最小回归命令

先复跑本报告原四节点（完整默认coverage，记录局部覆盖失败），再针对冻结新实现执行原guard+startup+R05限额文件的有限行为检查与真实PDF父四页节点；所有内层worker都计入下一轮独立资源上限。最终整体60门应由真正完整pure命令验证，不能把小范围覆盖不足改为skip/0门；本报告不再启动第21个worker。

```powershell
& .venv/Scripts/python.exe -B -m pytest tests/unit/test_r20_native_cpu_guard.py tests/unit/test_r20_process_startup.py tests/unit/test_r05_process_limits.py -v
& .venv/Scripts/python.exe -B -m pytest tests/unit/test_r04_real_parsing.py::test_official_four_pages_have_real_chinese_text_and_exact_page_locator -v
& .venv/Scripts/python.exe -B -m pytest tests/unit/test_r05_semantic.py tests/contract/test_r05_semantic_contract.py -v
```

其中semantic合同unit不能替真实模型成功输入；另需在授权模型/运行库可用时记录真实spawn、coverage、正常信封与EOF/故障拒绝。新边界需包含：preREADY已耗尽、readiness成功但余量极小、GetProcessTimes真正失败（明确last-error）、guardian硬退出、正常CPU、正常idle、短结果、两个产品成功/失败及整个树清理。阶段/安全/监控/恢复/CI仍按R20原卡验收，不以本局部代替。

## 8. 资源、实际命令与证据封存

| 实际采样命令（cwd独有backend） | primary样本 | +08开始—结束 | 结果/限制 |
|---|---:|---|---|
| `diagnose.py originals`，内部原四节点默认pytest | 4 | 03:08:45.784431—03:08:55.437078 | 2失败2通过；pytestexit1；原60覆盖门失败另记 |
| `diagnose.py coverage`，错误配置执行版本已归档 | 4 | 03:09:38.493475—03:09:43.110877 | ConfigError，不能当有效coverage；样本保留并计数 |
| `diagnose.py coverage_valid` | 4 | 03:10:15.527841—03:10:21.016864 | 活跃coverage分段；short无READY；Python/native严格总CPU红 |
| `diagnose.py no_coverage` | 4 | 03:10:31.669038—03:10:34.038051 | 显式诊断控制，未签默认门 |
| `remaining.py`：normal-poll命名但初始拒绝、初始耗尽、近预算idle、真实PDF父 | 4 | 03:12:14.964827—03:12:20.282402 | raw结果如上；没有普通poll成功测量；PDF正对照通过 |
| `summarize.py` / `validate_evidence.py` | 0 | 独立receipt | exit0；一致性检查通过，8343查询、输入hash/AST/限额/已知失败核对，不计产品unit通过 |

**实际20 primary，111个观察进程实例，已观察累计26.03125CPU秒，样本wall相加27.374秒，0 outer timeout，全部观察句柄最终signaled，0 discovery error。** 原pytest controller自己CPU已包括在观察树累计中；venv redirector/真正worker/guardian/benign leaf/隐藏conhost逐PID列在raw JSON。样本串行，单primary≤原8秒；原pytest controller总9.656秒是4个case加pytest开销，不冒称单worker超门。对原一次性leaf的10秒程序没有让其自然运行10秒，Job随guard退出及时结束。

Observer只用CreateToolhelp32Snapshot发现**自有root的后代**，OpenProcess后校验creation time并保留句柄；外层最多8秒（原4case controller30秒）仅能TerminateProcess这些已经验证的自有句柄。本轮未触发该外层清理，没有kill用户进程或全局WSL。查询5ms轮询可能遗漏在snapshot之间出生/退出的极短系统辅助进程；111/26.03125是观察总量，不是完整OS进程总数或绝对全树CPU证明。所有20primary和其guardian均有真实终态；不存在用wall推造CPU。

Observer的GetExitCodeProcess字段在最后4样本前追加；前16样本只有Popen root退出码、终态CPU/signaled和guard执行日志，不能补造各后代exit code。首16版按唯一已记录补丁反向重建于`observer_first16_reconstructed.py`，来源明确为重建，不冒称执行前已经封存的副本；该补丁只增加父observer查询，不改变worker/API仪器代码。一次自有inline汇总因PowerShell引号产生SyntaxError、未运行任何worker，之后文件化汇总成功；此失败不计产品或新增样本。

`artifact_manifest.json`列报告、执行版本、17份sample raw、原JUnit/coverage、API JSONL、command/log、CBM/rg/source identity与外部原证据hash。manifest本体不自包含，`manifest_identity.json`另存其SHA、字节数及+08封存时间；报告SHA也在manifest中。源/原测试/合同/状态/依赖的git diff为空，`git diff --check`通过；原日志未覆盖。

Verdict: **fix 1 and 2 first；本诊断不签Ship或阶段通过。** E1只新增真实限额/READY/清树诊断证据，P1只新增有限CPU/启动采样；R20本身的T45/T49/T50/T51与正式性能、部署、恢复验收继续保留。

Not checked: 原四红那一次的内部Win32 last-error/READY分段、真正GetProcessTimes失败注入、Job accounting query/ETW/硬件精确粒度、普通poll本轮新测、Linux/其他Windows、长期句柄/高并发、真实semantic重库/模型成功输入、完整pure/60门、完整integration/live/manual/安全/监控/备份恢复/CI、FOFA真正GIL超时原日志。没有外部在线或完整修复结果；到20后只封存与交接，下一措施由root交新作者。
