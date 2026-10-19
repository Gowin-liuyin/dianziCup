# R07 原生原文 IO 根因诊断

诊断时间：2026-10-17（Asia/Shanghai）。任务状态：`awaiting_review`，诊断交接已形成；R07 产品仍 `needs_changes / partial`，不据本报告签 accepted、整卡或阶段。诊断只写本报告及 `reports/runs/r07_native_io_root_diagnosis_20261017/`，未改业务、progress、原阈值、PG 断言、oracle、秘密、依赖或 Git 历史，未 push。

## 版本、边界与依据

作者工作树 `D:/wt/r07-io-deadline`；基线 `8c48b61c02860166bdda0986e984058e8a824188`，冻结源码 `4d85343a6117f1be215313aacd4652a554e334e4`，材料提交 `5a7fdf22ab22968637f685025b285ff143bfd7bf`（parent 为该源码）。作者 `wip_source_manifest.json` 区分 CRLF 工作树原 bytes 与 Git blob；本诊断实际读取的 content_store / MinIO / worker 原 bytes SHA256 分别为 `2342823c…c5b2d` / `661ed3da…f06ab` / `5c69c724…6631f`，与 manifest 及 focused_final1 收据一致。共享 process_limits 未被作者修改，实际 SHA256 `0e427be27ddce7ec2abb6ef183acb1df7008d112e0ea3a2b9b9ba9f86fe4dc56`。

依据：AGENTS、执行地图、状态/交接、CR-R07_source_io_deadline、作者冻结报告/原始命令和 PID birth、Ponytail 5.3.1 review/full、diagnosing-bugs。当前目标是识别两次 Windows 进程超限及 stdin 截止时间机制，给最小修复路径；不执行69 PG、WSL/CBM、新来源、付费 API、模型、FOFA、前端或生产服务。团队槽位已满，尝试并行 stdin 子诊断未成功，故在本槽完成。

## 原触发与真实结果

原证据均在作者 `reports/runs/r07_source_io_deadline_20261017/`，未覆盖或重新解释为通过。

| 原运行 | 实际结果 | 能够说明什么 |
|---|---|---|
| focused_initial | 工具 exit1 / PowerShell 0xE9，原两 stdio 0字节，无 command receipt、PID birth、XML | `focused_initial.tool_result_transcript.json` 明确是人工转录，无法确认业务起止或进程峰值，不能由早期 cap12 通报推造原始收据 |
| focused_fix1 | cap10，exit124 / owned_process_limit_exceeded，峰12，剩余0，无XML | 控制链包含 venv shim；六控制进程、两个本轮 worker及各conhost、两个本轮guardian已经达到12 |
| focused_fix2 | cap10，exit0，旧源码hash绑定，峰8，剩余0 | 作者确认 slot 自始至终是2；一轮较小峰值不是稳定并发上界，也不能签后续 WIP |
| focused_final1 | cap10，exit124 / owned_process_limit_exceeded，峰11，剩余0，无XML | 已换实际 base interpreter；仍由本轮 worker/guardian/console 组合超限 |

focused_final1 的完整关系是 50796/pwsh、3136/conhost、18232/controller、43004/pytest 四个控制进程；54612 和27712 两个当前 IO worker；15448和55104分别为这两个 worker 的 conhost；49688和36236分别为当前 guardian；35280/conhost 的 parent 是36236，出生 `20:42:29.508916 UTC`，距 guardian 出生约29ms。这个额外进程属于**本轮 guardian**。原账本没有“上一 guard 尾部”证据，不能把它作为此次峰11的根因。

## 已亲复的两个根因

1. **隐藏 console 仍计入完整 Windows 进程树。** 冻结 content_store 第72行和共享 process_limits 第138行均用 `0x08000000 / CREATE_NO_WINDOW`。本机单 worker + 真实共享 guardian 的原生对照，实际出生四个子进程：worker、worker/conhost、guardian、guardian/conhost。对同一固定 harmless worker 和 guardian 使用 `0x8 / DETACHED_PROCESS`，只出生两个 Python，PIPE 返回固定 OK、returncode0；每段所有已观测出生身份均 join 后才进入下一段。在最终四控制进程的结构中，两 IO slot 的充分并发因此可能达到 `4 + 2×4 = 12`。原 threshold10 无需改变，slot2也不应降1。

   这是当前机器的实测因果对照；不能仅从旗标名称推断“没有 conhost”。微软说明 `CREATE_NO_WINDOW` 没有 console window，`DETACHED_PROCESS` 不继承父 console，但文档本身不承诺完整进程数量，数量结论来自本报告出生账本。[Microsoft Process Creation Flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags)

2. **Windows communicate 的同步 stdin 写不受 timeout join 控制。** 本机 Python3.12 `Lib/subprocess.py` 第1604–1622行先启动 stdout/stderr reader threads，然后调用 `_stdin_write`；第1143行同步 `stdin.write(input)`，之后 close/flush；第1628行才按剩余 endtime join reader。实际安全固定32768字节、child0.3秒不读stdin、timeout0.05秒，耗时 **0.328秒** 才抛 TimeoutExpired，证明 parent不能及时进入自己的 kill/finally。GetNamedPipeInfo 在该 fresh stdin pipe 上成功，两个 buffer 字段均实测4096字节。

   R07 parent 第78行直接 `communicate(request, timeout=remaining)`，对已编码 request 无父上限；local可信root、MinIO可信CA/SecretStr等可令JSON超过pipe容量。worker第55行先完整安装 guard，第56行才读stdin，第61行才启动 watchdog。worker的16384输入限制在消费端，不能限制父亲已经进入的同步写。Windows匿名pipe写入在buffer满时会等待读端释放空间；这与本机CPython源代码和原生最小用例一致。[Microsoft CreatePipe](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-createpipe)

   Root另批准≤6秒单case补充后，使用实际冻结R07 `_read_with_deadline` 与作者相同的 `os.environ.PYTHONPATH = frozen backend/src + 原 venv site-packages`，安全固定8365字节local私有JSON、绝对0.15秒deadline，实际 **0.656秒才返回OSError**。出生账本：worker49336于 `20:53:52.186346 UTC`，guardian51588于 `20:53:52.747897 UTC`；原父deadline早已到期，guardian仍随后出生，父被stdin消费前的启动链挡住。该入口的三个源文件原bytes hash与冻结manifest一致，故这次是源码入口的同机制亲复，不仅是stdlib演示。

## guardian 完成、结果与 owner 的边界

当前共享 guard 只有初始化 READY event，没有正常完成 ACK。guard第39行等 target process 的 handle；worker死亡后第58行关闭最后 lifetime Job handle，再退出。`bound_process_resources` 把 Popen 仅存于子进程自己的 `_WINDOWS_CPU_GUARDS`，返回的是整数 Job handle；worker `del resource_handle` 不会 CloseHandle，也不是 guardian join。R07 parent 只 kill/wait IO worker并关闭两条管道，之后无条件返还 semaphore。

因此 `worker.wait()完成`、`读取到业务结果`、`guardian已结束并关闭last handle` 是三个不同事件。本次两段正常对照在 worker退出快照中均没有活子进程；这是两次观察，不是已证明共享代码具有同步回收保证，也没有复现“上一guard尾部”导致原资源红。

不能让 guard在 worker仍活时先退出、再等业务结果：它持有 KILL_ON_CLOSE lifetime Job 的最后 handle，其死亡是原 native/GIL 崩溃围栏，可能立即杀 worker。所谓 held ACK 必须明确是谁持有哪个 handle、何时业务成功已被父接受、何时允许最后handle关闭；仅添加完成消息或提前 `guard.wait()` 可能形成环形等待，或把成功输出变成异常退出。推荐在现有固定 worker生命周期建立可验证的父 owner/guardian identity与剩余deadline内 join；不要为诊断建立通用进程平台。无可靠 owner 前不能声称所有资源已完整关闭。

另外，R07第98行 kill若失败，会跳过后续wait与stream close；第100–108行wait失败仍返还名额且可覆盖原Timeout/取消；Windows stdout reader可能仍持buffer锁，直接close并非有界清理证明。这些是源码已确认的失败路径，未在本窗口注入kill/wait错误。补充入口用例返回的OSError而非TimeoutError与清理覆盖主异常路径一致；按本窗口只class/elapsed/length/birth的输出约束未保存exception message，因此不把它具体断言为某个kill或wait分支。最小修需保留主异常、逐项收集清理失败、确认资源终态才返还capacity或明确保留失败owner；不能用50ms常量当作成功保证。

## 对 4096 + GetNamedPipeInfo + 先读 config 的判断

这条方案能够消除已证明的 stdin流量等待，前提必须同时成立：

- 在父端先校验**最终编码的 bytes 长度**，包括JSON转义、UTF-8和可能的协议前缀，不能用字符数、字段数或原字符串长度代替。
- 实际 pipe由本调用刚创建，父端是唯一writer，此前没有写任何前缀/握手；这样初始空闲容量等于容量，子读只能增加空闲。GetNamedPipeInfo 返回缓冲区容量，**不是当前空闲容量**，不能用于复用已写管道的即时free-space判断。[Microsoft GetNamedPipeInfo](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-getnamedpipeinfo)
- 正确查询写方向可用容量，值为0或API失败必须fail closed，不猜“所有Windows默认4096”；CreatePipe的size本身只是建议。实际本机查询成功且双字段4096只是当前硬件/创建路径证据。
- 长度不得超过被证明的fresh可用容量；保留现有BufferedWriter写/close语义，若改bufsize0或手写WriteFile，必须检查完整写入/短写与失败，不能默认一次write永远全写。[Microsoft WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile)
- worker把有界config读取放在native guard前，可去掉“等待guard ready才消费”的流量环；imports/Popen初始化仍会消耗预算，应继续使用原绝对deadline检查，不能重置五秒。父容量限制和实际pipe限制都要存在。

不需要为这个 bounded config 建一个无界stdin写线程；若最终必须用可取消的IO线程或overlapped IO，需同预算取消、join和真实终态，不能只让API提前返回而后台继续持凭据/IO。超过新内部配置上限要明确拒绝和安全错误，不把秘密放env、argv、错误日志或临时文件。4096是待唯一作者实现并回归的新内部限制，不能在旧WIP上冒称已修。

## 调用链与最小修复范围

已 rg核 `bound_process_resources / _start_windows_cpu_guard / _WINDOWS_CPU_GUARDS / read_verified / _read_with_deadline`，读真实调用方源码：

| 接线 | 影响及复验 |
|---|---|
| ContentStore + MinioContentStore →固定content worker →共享limits | 必需deadline分支；正常、missing、hash/size、取消、stdin超长、短deadline、并发2、完整worker/guardian终态 |
| StructuredFactProofReader →ContentStorage | 原同一绝对五秒、两PG事务间真实IDLE、末围栏身份/epoch/指纹；本诊断未签PG |
| VerifiedContentRecorder / FrozenVerifiedContent；enrichment inputs | 保留可选keyword协议/旧非deadline调用；不改reported/unknown/Strong/QA |
| PDF _bound_memory →共享limits；pdf_text父communicate(最高32MiB) | 改共享启动flag会触达；PDF也先guard后stdin，属于既有同类传输风险，不能在R07内静默扩大到PDF改写 |
| semantic _bound_worker_memory →共享limits；_run_worker父recv/finally terminate/join | 改flag需守原hard-exit/native-GIL和结果门；当前只joinsemantic worker，未提供guardianowner |

最小修复先改两个已经实测的启动flag（R07 worker及共享guardian），保持所有PIPE/DEVNULL、handle_list、KILL_ON_CLOSE、CPU/memory门与slot2；同时按上节完成config传输界限、清理owner/异常路径。共享limit策略触达PDF/semantic，应先由Root明确唯一ownership，不能让另一作者并改同一文件。不要降低并发、提高cap、延长deadline、删原PG/CPU oracle。

## 本轮执行与交付证据

实际原生命令：

```text
C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe D:/dianzi/reports/runs/r07_native_io_root_diagnosis_20261017/probe.py
```

cwd `D:/dianzi`。Root明确批准≤20秒/fullWin≤10专窗；复用原 `runtime_limits.py` 的原字节副本，SHA256 `6c60580d…d156`，仅本进程覆盖task constants为512MiB/process、1GiBJob、CPU_RATE833/24逻辑CPU约1.9992CPU、KILL_ON_CLOSE。实际 exit0、harness1.890秒、四assert场景、fullWin峰7、末remaining_owned0、Job active1为本监督器、aggregateCPU1.6875秒、peakJobMemory30466048字节；监督器随命令退出。每段出生身份join后下一段，没有常驻服务，窗口已向Root释放。

完整 argv/起止/exit 在 `native_probe.command.json`；结果、逐PID birth、峰值、终态、源文件hash在 `native_probe_result.json`；stdout/stderr原样保留。probe.py SHA256 `1f1129ce…ca45`；本机实际subprocess.py SHA256 `85d29b2b…f375`。本轮没有pytest/JUnit，不把4个原生assert场景报成产品测试数量，也不把fixture loopback或时间报成live/性能。

第四场景尝试固定8365字节配置、实际R07 helper、0.15秒deadline，观察0.156秒/TimeoutError且未观到guardian。该场景的父sys.path包含venv，但未显式给helper子进程同样os.environ.PYTHONPATH；**环境接线不充分，不能作冻结R07入口已同因果复现的证据**。原结果保留，前三场景（flags/CPython）不受它影响。不能用6ms边界偷换stdin根因。

补充实际命令为同一base Python运行 `D:/dianzi/reports/runs/r07_native_io_root_diagnosis_20261017/probe_source_followup.py`，cwd仍 `D:/dianzi`；Root另批≤6秒/fullWin10/同memory、CPU、KILL_ON_CLOSE单case窗。收据实际 `04:53:51.9579206–04:53:52.8673405+08:00` / exit0；结果0.656秒/OSError，fullWin峰7、remaining0，末Jobactive1仅监督器、CPU1.140625秒、peakJobMemory52449280字节。`native_source_followup.command.json`、`native_source_followup_result.json`及两个原stdio保存；新harness SHA256 `4fc27c9c79615229f5e0f6f524af6b479ed94d0163ca81fa96f1fe1edc03a18b`。监督器与实际worker/guardian均结束，第二窗口也已即时释放，未再试第三次。

原证据保留：作者两cap10红及0xE9、早期76/658绿、收集69 PG的范围均不变。本诊断未改原348/304/658、M02原byte/oracle、原CPU hard gate、SourceOrigin规则、URI/金标/计分分母。

## 状态、未检查与建议

原生机理诊断：flags、stdlib同步stdin及冻结R07实际stdin入口已亲复；产品unit/contract：当前WIP未闭合；integration/PG、actualMinIO/model/source/FOFA live、人工、前端、性能/持续运行均 `not_run`。未注入guardian held-exit、kill/wait/stream-close失败，未亲复所有共享caller或双slot新flags稳定上界。终态外部复核在 `native_probe_terminal.json` / `native_source_followup_terminal.json`，原生监督器及原账本所有PID均已不存在；没有用PID复用冒称原进程残留。

合同未偏离：没有改公开DTO/认证/迁移/依赖或已冻结验收条件；P1资源和deadline仍是待修事实。本报告只提供E1/A1/F3的可追溯诊断证据，不补产品分。下一步由唯一作者按Root批准范围最小修、完整冻结；非作者在cap10/原五秒/原CPU门亲复原并发、stdin、owner清理，再按原PG oracle核真实事务和末围栏，之后才滚动去重原回归。诊断到此有界交接，不启动新无限平台。
