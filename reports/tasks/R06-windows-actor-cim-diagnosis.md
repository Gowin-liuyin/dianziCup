# R06 · 冻结 Windows actor 的 CIM 三秒超时独立诊断

本报告首次落盘：2026-10-17T05:40:20.6919081+08:00（文件 CreationTime 实测）；静态准备时钟05:34:45.6402409+08:00，两者不混写。诊断状态：已完成有界诊断、待 Root 审阅；R06 原 `needs_changes / partial` 与所有阶段状态不改，不写 accepted。

本轮证实当前宿主上的 CIM 可以返回本父子的身份，但冻结 `WindowsOwnedActor` 的整机快照在原三秒门内两次失败。空命令能完成，bundled PowerShell 的同一整机查询也超时；Root随后批准的全量三字段投影与全量名称投影仍均超时。因此不能把问题只归为错误 PowerShell 路径、CIM 完全不可用或一次冷启动。现有证据不能确定 CPU 竞争、CIM 提供程序初始化、整机枚举和序列化各自的耗时；不猜唯一环境根因，也不把未经验证的替代实现写成修复。

## 范围、版本与前置

已读 AGENTS、执行图、R06 报告/状态、`CR-R06_failed_bootstrap_control_recovery.md` 与固定独审详案；使用 Ponytail 5.3.1 review，另派只读子审追踪所有共享调用方。Root 起始 HEAD `3fd9cd68f292afcd1b88ca55f218c4e869e8f706`，branch `codex/full-delivery-recovery`；既有业务、文档、状态和用户未提交内容均未动。

固定来源为 Product `912d8b381eaab9260ead30d68f49b88fa8078384`、CORE `2ee7f509727e9fe37f31bba671083ac4aa07c123`、OPS `f75b0ccf3d2ea51fb6083c47cd1078e82b64a816`、材料 `95e45f388f413fc62d2de6217185b9e17e5592bd`、独审封存 `f497d499c02c44d3e38a3f5d4f89fc7650e90aca`。读取 `D:/wt/r06-bcr1f2` 的固定公开 scope；20 文件运行前/后逐项 raw SHA 均匹配。actor 为 9461 字节，SHA256 `d7472af2a53b4f126448cb2a5999de12fa80dabd000670fdf4c81ca8efd9dabc`，与实际 candidate/core 原字节一致。

当前 CR 只允许 `configuration.prepare_launch` 与 `controlled_supervise.main` 两处生命周期变化，另外十八文件仍必须冻结。独审 136 个不同 JUnit case 为 135 passed、1 原 immutable-freeze failed，仅限定两处离线功能 Ship；本轮没有重跑这些用例或改其状态。新 scope 图为 303 nodes / 1420 edges、partial1；NTFS 完整资源预算与 coverage 未通过，只用于定位，未重跑 CBM 或以图替代 native。

本轮新增仅本报告及 `reports/runs/r06_windows_actor_cim_diagnosis_20261017/` 的自有仪器/证据。没有 Source、产品 API、PG、Redis、MinIO、WSL、真实模型或付费请求；没有读取 `.env`、秘密、附件、盲测或 DPAPI。CIM 输出只保留 PID、PPID、创建时间；报告没有整机快照或用户命令行。

## 原红为何不能当作九秒 CIM

独审原 `native_identity` 为 05:23:38.811476–05:23:48.119361+08:00，9.297 秒、exit1；wrong birth 与 foreign Job 先拒绝，wrong ancestry 才进入固定 CIM，真实 `TimeoutExpired(3)`。正确 parent/membership 与 exit23 当时未运行，不能继承旧 b7 native 成功。

原仪器在 `with Popen(sleep9)` 内触发异常，`Popen.__exit__` 会等待那个 dummy 自然退出；实际 Python 3.12 标准库源码 `subprocess.py:1092–1126` 确认该等待。另 `subprocess.run:548–568` 在创建进程后才把 timeout 交给 `communicate`，Windows 超时后会 kill 并回收输出。故三秒是原通信 timeout，不保证包括 CreateProcess 与退出回收的总墙钟恰为三秒；本轮没有调这个门。

原收据只证明完整 Windows 峰8/Linux0、held child ACKtrue、remaining0，以及原固定 CIM 超时。它没有落盘的单 dummy birth 与原未运行第二子进程，不予补造。

## 本轮真实命令、时间和资源

Root 明确批准单一最多20秒窗口，内部16秒动态截止，下一 CIM 前剩余少于3.25秒记 not_run；R07 两个 Windows native 窗已释放。批准原文对应事实落在 `root_window_ack.json`。本轮没有在 ACK 前运行 native。

实际入口：显式存在的 bundled shell `C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe`、`login=false`，再运行：

```text
C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe -B D:/dianzi/reports/runs/r06_windows_actor_cim_diagnosis_20261017/run_owned_diagnosis.py native_cim_probe -B D:/dianzi/reports/runs/r06_windows_actor_cim_diagnosis_20261017/cim_probe.py
```

完整 child argv、原始 stdout/stderr hash 和真实收据在自有 run；重复 `-B` 原样保留，不计作业务变化。native 起止 **05:37:56.725415–05:38:12.042079+08:00**，wall **15.328 秒**、outer **exit1**。无 traceback、stdout/stderr 为空；逐项结果即时写入 `probe_incremental.json`。exit1 保留了身份未知与内部终态计数红，不改为 success。

查询实际硬值：active10、512MiB/process、1GiB/Job、24 logical CPU、rate833，核上界1.9992，KILL_ON_CLOSE=true。完整 Windows 峰 **8/10**，本轮 Linux0，sampling errors0；外层 Job CPU9.859375秒、peak memory118267904字节，结束时 active1仅执行器，held probe ACKtrue、remaining_owned0。CPU均值不是瞬时限流或宿主竞争排除证据；该内存峰也不证明 CIM provider 的宿主内存情况。

| 项目 | 实际 +08 起止 / wall | 真实结果 |
|---|---|---|
| wrong birth，原 frozen ctor |05:37:56.898307–56.899305 /计时分辨率0.000s|拒绝 `owned actor creation changed`；dummy仍alive；未发信号 |
| foreign Job，原 frozen ctor |05:37:56.899305–56.899305 /0.000s|拒绝 `actual actor is outside owned Job`；dummy仍alive；未发信号 |
| 首次 wrong ancestry，原 frozen 整机 CIM |05:37:56.900309–05:38:00.043158 /3.140s|`TimeoutExpired`，身份 unknown，未执行到 ancestry 判断 |
| 系统 PowerShell no-op |05:38:00.044158–01.905274 /1.860s|exit0；child CPU0.3125s；held ACKtrue |
| 正确 parent/membership，原 frozen 整机 CIM |05:38:01.906273–05.445085 /3.547s|`TimeoutExpired`，身份 unknown；不能计正确身份接受通过 |
| 系统 PowerShell，仅本父子 CIM filter |05:38:05.446086–08.390756 /2.937s|exit0；child CPU0.78125s；恰2行，PPID关系正确；held ACKtrue |
| bundled pwsh，同一原整机 CIM脚本 |05:38:08.391761–11.425549 /3.031s|硬3秒后timeout、kill退出1；child CPU0.5s；held ACKtrue；stdout0字节 |
| 系统 PowerShell再次整机 warm命令 |未运行|剩余不足3.25秒，明确 not_run |

前两项墙钟0是 Python 3.12 本机 monotonic 的记录分辨率，不是零资源开销。所谓首次/cold仅指本仪器首次整机 CIM；没有重启宿主、清缓存或证明 CIM provider 冷态。targeted在前面多次查询之后执行，不能从单次结果断言过滤必然解决或改变正式行为。

系统 no-op 和 targeted 子进程的 held `QueryFullProcessImageNameW` 实际为 `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`，采用与冻结函数相同的 `-NoProfile -Command`、creationflags0；系统文件版本10.0.26100.8875。bundled 子进程的 held image确为上列缓存路径，文件版本7.6.5.500。`C:/Program Files/PowerShell/7/pwsh.exe` 实际不存在；旧 shell映射不能视作文件存在或合法 child spawn证据。本轮没有通过改 PATH、flags 或原 source把 bundled shell作为修复安装。

## 自有身份、关闭与计数红

probe真实 PID15048，parent48684，kernel creation ticks134366602767361714；sleep dummy PID60016、parent15048、ticks134366602768838661。targeted CIM只保存两行：15048的created=`2026-10-16T21:37:56.7361710Z`，60016的created=`2026-10-16T21:37:56.8838660Z`，其 PPID=15048。原 actor仍因其自己的整机查询失败而未接受该身份；这些诊断字段不充当产品 actor receipt。

cleanup前重新核对 dummy GetProcessTimes birth和自有 Job membership，再仅使用自己持有的 handle结束 dummy。其真实exit1、held Wait ACKtrue。随后第二 dummy PID43004、ticks134366602914407721，真实exit23、held Wait ACKtrue、退出后 birth未变；两 dummy顺序，不对用户进程发信号。

第二 dummy退出确认后的立即 inner Job查询仍为 **active2**，CPU2.984375秒、peak memory102969344字节，仪器据此exit1；不能猜第二个对象是何进程，也不删除这一红。外层 held probe退出后查询为active1、remaining0，说明最终自有 Job资源已经退出。另一个只读 postexit核查对6个自有已记录PID逐项确认 absent、same-generation alive/unknown均0；20冻结文件after SHA全部匹配。不能把此最终关闭事实改写成 inner即时终态通过，也不声称这些dummy等于真实Source actor。

没有运行 pytest、unit/contract/产品integration、完整类型/风格或旧/new freeze回归；业务测试新增0。本轮4个实际身份分支中2个拒绝通过、2个身份unknown；3个独立命令中2个exit0、1个timeout，另1命令not_run。exit23与held关闭分别列证，不拼成完整native pass数量。

有限文件检查另列：对本报告/两个仪器执行 `git -c core.whitespace=cr-at-eol diff --no-index --check -- empty_for_diff_check.txt <exact_file>`，三个实际exit1，属于新文件与空文件的内容差异；输出只有LF/CRLF转换warning或空，没有whitespace错误，不能写成tracked完整diff检查exit0。首次PowerShell数组拼接生成错误短路径，初记录保留；第二次命令有ParserError，未执行任何文件操作；最后改为三个精确绝对路径检查，收据为 `own_source_diff_check_corrected.json`。初次寻找仪器误读不存在的run_checks.py也是静态工具定位错误，shell非终止诊断exit0；随后读取真实run_owned.py，不把它算业务测试失败。

## 共同调用方与最小后续动作

`windows_actor.py:16–25` 的共同函数同时供 ctor注册`:79`、kill前`:136`与kill后`:172`使用；不是两个新授权函数各自独立的缺陷。外部路径包括：

- `controlled_supervise.py:342` 注册worker/beat，异常路径`:530–582`记录失败并关闭自有Job；`stop_controller.py:85/90`使用 actor tree关闭，成功后才写后代退出证明。
- `guardian.py:76`注册Source；ctor失败走`:133–143`的 Job关闭和launcher等待，仍须真实ACK，不能由静态 finally推定成功。
- `configuration.py:948–950`在旧运行归档前检查旧PID/后代；`stop_owned.py:144`在写stop请求前检查身份。
- `stop_owned.py:158–169`另有一条独立 PowerShell/CIM进程名称查询，同硬3秒；它不经过共享函数。本轮未运行该路径，不能承诺只修shared就解决完整停止入口。

当前环境的最小已证结论是：CIM可用，但当前冻结整机查询方式与三秒门的实机组合不满足注册要求；bundled替换和单次预热都未证明可解决。父子kernel birth与Job拒绝边界未被放宽。没有证据指向 Product业务、API依赖、原worker readiness或原六小时中断的唯一原因。

首次交付后Root只批准一次全量投影对照，实际结果见下一节；原全量、三字段全量及二字段名称全量均失败，没有保持原门的一行属性投影修复证据。遵从Root明确的停止条件，不追加扫描、重试、第三个诊断窗或扩大仪器；最小下一步由Root另行精确授权native快照候选并交独立审查，不由本报告自行改十八冻结文件。

如果必须修改source第三文件，先创建Root新的精确CR，列明 `windows_actor.process_tree`/必要导入、精确COREpin与binding/raw manifest；新冻结登记三个允许变化控制文件、其余十七不变，旧18same Oracle/原native红全部保留。任何 kernel快照替代必须独立验证未知/权限/消失/PID复用、父子generation、Job membership与关闭前后后代覆盖，不能跳过无法读取的对象后伪造完整树。独立名称CIM若也要改，需另列 `stop_owned.main` 查询段授权，不用caller补丁绕freeze。

随后复核原 wrong birth/foreign Job/wrong ancestry/正确parent、已退出actor、真实exit23、正常stop ACK、强制Job收尾和后代确认。Root的新kernel closure audit、安装、fresh七门、真实Source/PG/MinIO/worker readiness、首轮采集、21600秒同版本观察及最终关闭仍 not_run/原failed，不由本诊断放行。18原文件、阈值、累计预算、ledger42/450、评分与状态均未改，未commit/push。

证据入口：`static_facts.json`、`root_window_ack.json`、`native_cim_probe.command.json`、`probe_incremental.json`、`postexit_and_source_freeze.json`，以及下节的独立投影收据。本报告只提供E1控制运行故障定位证据，F1/P1/R06/G-C继续保留真实运行缺口。下一任务建议为Root的精确native快照CR；不扩控制工程。

## 接续：一次全量属性投影对照，仍 failed

本次准备时钟 **2026-10-17T05:43:37.3965332+08:00**，Root HEAD仍3fd9、R06仍needs_changes/partial，原两函数CR未变化。静态子审确认 `-Property` 只选择读取字段；候选未增加Filter、KeyOnly或目标PID条件，保留全量 `Win32_Process` 与原ordered JSON。两次时刻不同的全量查询可能遇到进程出生/退出，不能仅据PID集差异判断投影漏项。

没有在R17 CBM占用窗口时运行。Root在其done且终态0后明确批准单16秒窗、内部11秒动态截止，每个CIM仍硬3秒、各一次，不循环。三条命令在自有 `cim_projection_probe.py` 顺序执行：

```text
Get-CimInstance Win32_Process | ForEach-Object { [ordered]@{pid=$_.ProcessId;parent=$_.ParentProcessId;created=$_.CreationDate.ToUniversalTime().ToString('o')} } | ConvertTo-Json -Compress
Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId,CreationDate | ForEach-Object { [ordered]@{pid=$_.ProcessId;parent=$_.ParentProcessId;created=$_.CreationDate.ToUniversalTime().ToString('o')} } | ConvertTo-Json -Compress
Get-CimInstance Win32_Process -Property ProcessId,Name | ForEach-Object { [ordered]@{pid=$_.ProcessId;name=$_.Name} } | ConvertTo-Json -Compress
```

入口使用同一真实bundled工具shell、login=false与base Python3.12：

```text
C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe -B D:/dianzi/reports/runs/r06_windows_actor_cim_diagnosis_20261017/run_projection_owned.py native_cim_projection D:/dianzi/reports/runs/r06_windows_actor_cim_diagnosis_20261017/cim_projection_probe.py
```

实际窗口 **05:46:27.164115–05:46:37.328829+08:00，10.157秒、outer exit1**。独立序列无dummy、无Source服务、无retry、无额外扫描；完整Windows峰 **6/10**、Linux自有0、sampling errors0、资源failure=null。硬值仍512MiB/process、1GiB/Job、833×24（1.9992核上界）、active10/KILL_ON_CLOSE；外层Job CPU6.3125秒、peakmemory106328064字节、最终active1，held probe ACKtrue、remaining_owned0。inner最终active1、CPU1.8125秒、peakmemory91709440字节。已向Root交回资源窗口。

| 全量命令 | 实际 +08 起止 / 总wall | CreateProcess / 通信与回收wall | 结果与CPU |
|---|---|---|---|
| 原三字段JSON、默认全属性读取 |05:46:27.336685–30.374512 /3.032s|0.016 /3.016s|timeout、exit1、CPU0.578125s、stdout0 |
| 显式三字段Property、原JSON |05:46:30.375825–34.238204 /3.859s|0.015 /3.844s|timeout、exit1、CPU0.59375s；回收stdout29794字节，仅保存hash与长度 |
| 显式PID/Name Property、原名称JSON |05:46:34.239203–37.275743 /3.031s|0.000 /3.031s|timeout、exit1、CPU0.46875s、stdout0 |

三者 held QueryFullProcessImageNameW均为系统 `C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe`，flags仍 `-NoProfile -Command`、creationflags0。对应子进程实际 PID/birth为30708/134366607873425023、41316/134366607903782117、22440/134366607942414106，三者held Wait ACK均true；probe为PID21988/parent47764/birth134366607871743852。

三字段投影的29794字节是在TimeoutExpired之后kill/communicate回收的输出；本轮没有保存整机stdout或解析它为快照，更没有以“已有输出”绕过三秒门。三个status均timeout，集合覆盖、ordered JSON完整性与产品身份接受在此窗均unknown，不声明投影成功或快于原路径。查询从创建到回收的墙钟可以超过通信timeout，规则与第一窗相同。

actor运行后原字节仍SHA `d7472af2a53b4f126448cb2a5999de12fa80dabd000670fdf4c81ca8efd9dabc`；两处控制函数、其余18冻结、状态、预算、账本和评分均未改。新增仅自有projection仪器及 `projection_root_window_ack.json`、`native_cim_projection.command.json`、`projection_incremental.json`、stdout/stderr hash证据。此追加没有运行pytest、业务unit/contract/integration、完整质量门或CBM，也没有commit/push。

**接续结论：三条全量CIM各一次均failed，保持字段语义的Property优化不能据本证据放行。** Root可据真实红开启精确native快照替换CR；共享tree和停止入口独立names必须同时列清验收影响。未知读取、权限/消失、PID generation、Job membership、父子关系、关闭前后后代与held退出ACK依然必须fail closed。本agent按本次有界指令到此停止，不实现替代算法，不扩诊断框架。
