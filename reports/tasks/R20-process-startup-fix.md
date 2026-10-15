# R20 · PDF 重依赖启动与 guardian 初始预算修复

状态：`awaiting_review`。本局部实现 `complete`；整 R20 仍 `partial/not_run`，本次不签原 T45/T49/T50/T51、阶段或严格 CPU 硬上界通过。新独立 reviewer 由主控安排，作者不自行 accepted、push 或写公共 progress。

## 冻结版本与范围

- worktree：`D:/wt/r20-process-startup-fix`；branch：`codex/r20-process-startup-fix`。
- 基线：`c3a2abc9a5246993eabb351d26cfeb51d0270b31`；业务 SHA：`41c61491b4429cc47dd970b201d9b2551cbb3a7f`。
- 产品 SHA-256：limiter `0e427be27ddce7ec2abb6ef183acb1df7008d112e0ea3a2b9b9ba9f86fe4dc56`；PDF worker `24ea5c30a58eda43410700e5dd9396cecb6bc59b5da8e8d1c0a1c53041956c60`。
- 仅产品改动 `backend/src/ai_intel/infrastructure/process_limits.py`、`backend/src/ai_intel/ingestion/parsing/_pdf_worker.py`；新增 `backend/tests/unit/test_r20_process_startup.py` 与本报告/自有 run。没有依赖、阈值、原断言、父调用、semantic、runtime、settings、API、锁、PG、来源采集或公共 progress 修改。
- 原 native guard 产品 `852472810b20b113606a0275ae6861326d39ebe8` 的这两个调用链在本基线相同；原诊断报告与 review 作为输入保留，不改写其结论。输入 hash 见 manifest。

已读 AGENTS、执行图、recovery R20 卡及 manifest、状态/交接、T45/T49/T50/T51 和其 `04/06/09` 计划合同，使用 Ponytail 5.2 full 与 diagnosing-bugs。R20 全验收仍须 R16–R18 能力与原卡前置，本次仅按主控明确的基础安全提前修复授权处理两个局部缺陷。当前 scope 无 GLOSSARY/ADR；CBM 输出的 ADR 建议没有作为执行指令。

## 实现与输入输出

PDF 的固定模块入口现在只先导入标准库及 limiter；`main()` 成功安装 512MiB/15CPU 限额之后才触发 pypdf package 导入。`extract_pages` 的直接测试接口保留，异常分类、页号/文本/notes JSON 与解析配置保持。限额初始化失败时仍输出明确 resource-unavailable 结果，并且不会导入 pypdf。父固定模块、白名单 environment、容量2、20秒 wall、空输出/退出码/JSON 校验保持。

Guardian 首次 `GetProcessTimes` 的累计 kernel+user 达到或超过原预算时，在 `SetEvent` 之前抛出异常；已有异常路径终止目标并关闭生命周期句柄。没有减去启动 CPU、重置 baseline、改变 50ms 轮询或新增预算余量。该修改只让首次读数已经耗尽时 fail closed，不能追回首次读取之前已用的 CPU，也不能保证读取与 SetEvent 之间没有调度延后。

永久预算保持：原 CPU 热点 **1秒 CPU / 3秒 wall**；原产品启动 **8秒**；PDF **512MiB / 15CPU / 20wall**；semantic **2GiB / 30CPU / 总deadline≤30秒**；原整体 coverage **60%**。未改 skip、金标、分母或任何原测试文件。

## 红例与真正执行的结果

新测试先于实现：原代码的 pypdf 导入前置2例和初始累计 CPU 等于/超预算仍就绪2例，**4 failed，exit1**。红例观察实际 import 事件及 guardian 源码的初始 accounting/SetEvent/terminate 行为，不是根据源码文本是否包含某行给期望值。guardian unit 使用显式合成 kernel 调用，不计真实 Windows 测量。

修复后同4断言通过；追加 PDF 父白名单负例。冻结代码后 **5 passed，exit0，0 skipped**。父白名单 unit 只注入显式 synthetic 环境标记，不打印或读取真实秘密。初始 runner 终端 GBK 输出有 UnicodeEncodeError；真正 pytest exit1、原始 log/JUnit/receipt 已完整保存，随后仅改自有 runner 的 stdout 编码。它没有把红例变成环境失败。

所有正式命令 cwd 均为新 worktree 的 `backend`，解释器为现有 `D:/dianzi/backend/.venv/Scripts/python.exe`，PYTHONPATH 为新 worktree `backend/src`。每个 `*.json` receipt 保存完整 argv、开始/结束UTC、退出码、wall和当时产品/test hash；数量以 JUnit 为准。

| 命令范围（完整 argv 见同名 receipt） | exit | 实际结果/限制 | 证据前缀 |
|---|---:|---|---|
| `pytest tests/unit/test_r20_process_startup.py --no-cov -v`，原代码 | 1 | 4 failed，0 skipped | `red_startup` |
| 新4例 + R05纯输入/保留 envelope，`-k 'not real_native' --no-cov` | 0 | 18 passed，2 deselected | `green_startup` |
| `pytest tests/unit/test_r20_native_cpu_guard.py --no-cov -v` | 0 | 原16项通过；15个 primary worker 场景 | `regression_guard` |
| 原 hard-exit `[python-gil-held]`，默认 coverage，未加 `--no-cov` | 1 | 1 case passed；**1.74% < 原60%覆盖门**，命令失败保留 | `native_default` |
| 原官方4页 PDF 父入口定位单例 `--no-cov` | 0 | 1 passed；真实 pypdf、真实固定Popen、中文/页号/证据定位成立 | `real_pdf_parent` |
| 自有 `measure_startup.py`，3个场景顺序 | 0 | 初始预算拒绝、覆盖模式PDF实际4页、真实spawn/Pipe语义协议正对照 | `measured_boundaries` |
| 追加白名单后纯输入/边界回归 | 0 | 19 passed，2 deselected | `unit_final` |
| 业务冻结后新文件 `--no-cov` | 0 | 5 passed；没有 worker | `frozen_boundaries` |
| 定向 Ruff / format / mypy win32 两产品文件 | 0 | 最终通过；初始格式失败保留 | `frozen_static` / `frozen_format_final` / `mypy` |
| CBM src独立index/schema/trace、rg caller核对、diff check | 0 | 1253 nodes / 6259 edges，解析遗漏全0 | `cbm_*` / `rg_*` / `diff_check` |

以上测试重叠，**不相加为独立案例数**。`--no-cov` 是明确的局部行为诊断入口，未登记整体覆盖通过。完整默认 unit/60% 门本轮 `not_run`；单节点默认 coverage 的 exit1 没有降为 skip 或删去。2个 R05真实内存/CPU节点本轮未在该命令运行，未冒充通过；本轮限定guard/启动场景见下表。

## 20个 primary worker 场景与计量

| 分组 | primary 数量 | 内容 |
|---|---:|---|
| 原 guard 专项 | 15 | CPU 4；idle 1；short 1；guardian硬退出3；初始化失败1；PDF父拒绝1；semantic真实spawn EOF拒绝1；PDF/semantic启动2；失败ready清理1 |
| 原 default coverage hard-exit | 1 | 原 python-gil-held 单节点，读真实 worker/guardian/leaf GetProcessTimes |
| 真正 PDF 产品父入口 | 1 | 官方4页 PDF，完整文本与定位检查 |
| 自有定向测量 | 3 | 初始已耗尽1；PDFcoverage实际4页1；semantic真实spawn/Pipe合成合法结果1 |
| **合计** | **20** | 到达上限后不再启动worker样本 |

这不是整个系统只创建20个进程：每个 Windows 限额场景还创建 guardian；硬退出案例创建 benign sleep leaf，失败ready案例含一个纯pass预热子进程。primary 场景串行、并发1；原 `native-two-threads` 保持其两个 native 热点线程。进程命令累计实际wall约31.60秒，低于240秒，但不是持续运行窗口。已观察的 raw CPU 数值列下方；未为原15例收集所有进程终态 GetProcessTimes，**不能据wall伪造整个20场景累计CPU或完整全树CPU硬保障**。本轮执行采用有限超时/原CPU限额，无额外长任务。

主控同时安排其他工作包静态/PG检查；本轮不控制整台机器竞争，不将数值称为无竞争性能基线。没有网络、PG操作、模型推理、模型下载、付费API、秘密读取或第三方资产扫描。

| 实际测量 | 准确数值/观察 | 能与不能支持的结论 |
|---|---|---|
| 原默认coverage hard-exit单节点 | ready worker kernel+user **0.546875CPU**；终态 **0.9375CPU**；worker/guardian/leaf均signaled；case通过 | 只是一轮绿；不能消除前独立诊断的**1.328125CPU > 原1秒**红记录 |
| 原1CPU预算，进入helper前已用1.109375CPU | 未READY、无结果；终态worker **1.125CPU**（kernel0.578125+user0.546875），guardian0.046875CPU；两进程结束 | 初始总CPU耗尽拒绝继续；也直接说明不能追溯保证总CPU<1秒 |
| PDF coverage实际4页 | 子进程 module import后0.53125CPU；bound后0.546875CPU；重库import后7.359375CPU；终态 **7.609375CPU**，guardian0.0625CPU；JSON4页、exit0、树结束 | 重库约6.8125CPU在限额后；总计算没有通过取消coverage减掉 |
| semantic真实spawn/Pipe正对照 | 384维规范化**合成结果**；约0.25wall；2GiB/30CPU；worker before-send0.1875CPU | 原生产父可收合法信封，与原真实EOF负例配对；不计真实模型语义能力 |

PDF 仪器限制：实际执行的 harness 在读就绪流前同步写 stdin；大于管道缓冲的 PDF 输入写入会等worker开始读stdin，因此 receipt 的 **parent ready 7.484秒、ready_cpu7.375秒不能解释为bootstrap就绪延迟/CPU**。真实子 `OBS` 时序显示 module import→bound→heavy import，entry→bound约0.079秒，但缺完整父launch→READY无阻塞时间，不能据此给新的启动wall成绩。原永久PDF启动8秒测试与真正PDF父20秒测试均通过，分别保留为独立行为证据。

已修自有下一轮 harness 为异步写 stdin，并记录 launch_monotonic；**新harness没有重跑，不给旧数据背书**。旧执行逻辑在 `executed_harness/`；一次格式化误及archive，仅依据已保存Ruff diff反向恢复两个文本的纯格式变化，并验证AST等价，记录 `executed_archive_restoration.json`。raw worker code本身也逐字保存在各场景JSON。早期GBK runner版本与后来UTF8 runner版本的差异明确保留在红日志/记录中，没有假称所有命令都是最终脚本执行。

Semantic源码核对：当前没有独立 `_semantic_worker.py`，实际函数位于 `infrastructure/models/semantic.py`。父固定 `spawn`、真实Pipe、在spawn前建立≤30秒总deadline；EOF与信封分别拒绝，finally有限terminate/kill/join。heavy tokenizers/onnxruntime/numpy仍在 `_bound_worker_memory` 后动态import。spawn继承调用父环境，包括父启用时的coverage；本次合成正对照 coverage_active=false，**没有完整semantic coverage真实启动/模型推理复验**，不以PDF测量代替。guardian自己的-I/-S基础Python与SYSTEMROOT/WINDIR白名单保持。

## 未闭合边界、最小后续措施与合同偏差

**原严格总CPU故障未关闭。** helper前的site/coverage启动没有现有业务函数控制；正常50ms采样及调度延迟不是硬实时保证，Windows Job user-only限额也不等于累计kernel+user。首次检查再早也不能独立消除guardian就绪后的0.4秒故障窗；前独立红例和本轮初始耗尽>1CPU实证均保留。没有通过重置baseline、放宽预算、换无coverage环境、删除断言或一次绿复跑宣称闭合。

最小下一措施是明确一个由父在任何site/重初始化前安装监督与资源限制的固定bootstrap接缝，且核对内核CPU与userCPU口径、句柄/进程树和原coverage启动方式。Windows若要求绝对1秒累计kernel+user硬界，需要平台可实施的早期监督/内核保障或重新澄清可证保证；不能仅以当前轮询实现承诺。该措施超出本轮最小两文件修复，不另建万能进程框架或静默改变合同。新独立review至少在冻结SHA复核上述局部修复及父正负边界，并用修正仪器保留原CPU/8秒/coverage门；完整R20验收条件继续阻塞其依赖。

本轮未验证Linux实际RLIMIT、其他Windows版本、完整CPU树/绝对上界、长期句柄/高并发、冷缓存热点、semantic coverage/真实模型、T45跨租户与注入、T49告警、T50备份恢复、T51完整CI/CD、integration/live/manual/完整pure与整体coverage60。模型/外部接口live在此范围为`not_run`，不伪装online。

E1只登记局部PDF设限顺序与guardian初始failclosed可追溯证据；P1只登记有限真实启动/CPU观测，不能登记整项达标或持续运行。没有公共合同/计划/评分门变更；自有harness测量缺口与完整门not_run如上公开。下一任务建议：主控安排全新非作者review，采纳限定结论后另行处理早期严格CPU接缝，保持原R20最终验收不缩减。

完整产物索引：`reports/runs/r20_process_startup_fix_20261016/artifact_manifest.json`；其中列本轮命令、20primary场景、raw计量、代码/输入hash、harness执行版本与限制。材料SHA由后续封存提交提供，产品与业务SHA保持相同。
