# R17 · Root TypeScript 内存差异诊断

状态：`awaiting_review`；诊断实现 `complete`，产品实现未修改。Root完整类型检查仍保留两次 `failed`；本轮仅解析探针 `passed`，没有新增通过的业务测试。

本轮已读仓库AGENTS、执行索引、恢复R17任务卡、R17状态及最新交接，采用Ponytail 5.3.1 full。Root HEAD `3fd9cd68f292afcd1b88ca55f218c4e869e8f706`，分支 `codex/full-delivery-recovery`；固定UI源码 `6ed92b802a8126855dac3ce16d7c35e93305ff2b`；reviewer工作树HEAD `14605b9f6d7a9495415a71d1dee160504a91faea`。首次独立clock记录 `2026-10-16 22:22:44 UTC`，本轮证据探针发生于当地2026-10-17 06:26。

## 已确认的结论

Root和reviewer当前完整TypeScript输入相同。读取两边配置、解析全部root files及模块依赖后，各为156个root files、299个声明文件、455个总source files；455文件逐内容LF规范化SHA-256零差异。总解析文本10,880,706 bytes，其中非声明源码1,126,021 bytes。`src/tests/e2e`的154个TS/TSX文件及两个显式配置文件全部保留；没有删除难测用例或改变include。

两边`tsconfig.json`的规范化SHA为`fda2f7ff7d578e5f0547d2012d227641041046b4d7e08806f4347fae748eed8e`，package-lock为`99745a682ab890a86accdbb7a61564bf10744b6def66181573dc23475e0ab3cf`。reviewer `frontend/node_modules`是指向Root同目录的Junction；35个实际解析依赖包的版本、package.json SHA和realpath完全一致。关键实际版本：Node `v24.13.1`、TypeScript `5.7.3`、`@types/node 24.19.2`、`@types/react 18.3.31`、Vitest `4.1.11`、Playwright `1.64.1`。完整文件、resolved paths、包版本及SHA在ownrun `input_probe.json`。

配置没有`extends`或project references；`resolveJsonModule`未启用，实际解析JSON source files为0。原配置已有`strict:true`、`skipLibCheck:true`。本轮均未改变。reviewer argv额外`--incremental false`与Root未设置incremental在本配置中结果相同：本机官方TypeScript `_tsc.js:17951–17955`计算`!!(options.incremental || options.composite)`，两边为false；CLI `130606–130618`走普通`performCompilation`。Root旧tsbuildinfo含62个root entries，reviewer旧文件含4个，均不是此次普通tsc的增量输入。Root用户已有文件SHA始终为`3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d`。

Root两次红不能混写成同一种失败：

| 运行 | 实际argv | 原始结果与GC证据 |
| --- | --- | --- |
| `batch15_ui_types` | `node node_modules/typescript/bin/tsc --noEmit` | child/native exit134；`Zone Allocation failed - process out of memory`。最后Scavenge后heap使用328.5MB、heap总455.4MB；没有历史native memory peak，不能把heap数冒充process commit数。 |
| `batch15_ui_types_gc` | `node --max-old-space-size=256 node_modules/typescript/bin/tsc --noEmit` | child/native exit134；`Ineffective mark-compacts near heap limit ... JavaScript heap out of memory`。Mark-Compact后使用251.5MB、heap总259.6MB，说明256老生代设定已不够完成这次检查。 |
| reviewer `types` | `node .../typescript/bin/tsc --noEmit --incremental false` | child/native exit0，45秒/进程10采样监督；历史内存/CPU Job限额无证据，不可签成已在Root512MiB条件通过。 |

原日志均保持原字节，不把新的解析通过替代上述失败。

## 实际限制与前证边界

Root `reports/runs/recovery_reviewed_integration_20261016/check_batch15_frontend.py:18–25`实际加载R06候选`runtime_limits.py`并创建OwnedJob，随后执行reviewer的既有`bounded_checks.execute`。limiter代码先设置Job ExtendedLimits和CpuRate、Assign当前Python，再QueryInformationJobObject回读断言；后代继承。限制flags `0x2300`涵盖process memory、job memory、kill on Job close；CPU flags5为enable/hard cap。该Job没有affinity flag或affinity API。约2 CPU来自比例上限，不是固定两个CPU的affinity。进程10和wall60秒由原采样监督器控制，不能称为Job的native进程数/time限制。

两条历史UI收据没有保存实际numeric CPU rate、QueryJob限额或内存峰值；同批24logicalCPU/rate833只能作为历史推断。此次探针真实回读：process limit536,870,912 bytes、job limit1,073,741,824 bytes、flags8960=`0x2300`、CPU flags5/rate833、logicalCPU24，即约1.9992 CPU。

reviewer保存的`run_check.py:6,10`直接调用`bounded_checks.py:57,85`，仅Popen、wall45秒、完整Windows树cap10、held-handle终态；这些代码没有创建或查询内存/CPU Job。其外层shell是否继承别的Job以及具体限额，现存收据和报告不能证明。因而仅能确认runner缺少同限额设置证据，不能断言当时整个系统完全无Job，也不能把reviewer类型绿色当作与Root同512MiB条件的复验。

最小可证差异是Root明确加了512MiB/process Job，而reviewer前证没有对应限额证据；不是源码、类型依赖、resolveJsonModule或增量缓存差异。Root默认GC记录显示heap总量已经接近process预算，native/zone额外分配失败与此吻合；缺少初次native内存峰值，因果仍是强支持的解释，而非已经观测到确切512MiB提交量。256尝试又将失败转成JS老生代不足，两次红不支持继续盲降低老生代。

## 本轮唯一运行

Root明确批准一次≤15秒parseConfig/parseProgram、不typecheck、不emit探针。ownrun `run_probe.py`直接复用上述现成`bounded_checks`和同一limiter，未建立新监控框架、改产品配置或接触外部服务。实际命令：

```powershell
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' 'D:/dianzi/reports/runs/r17_root_types_memory_diagnosis_20261017/run_probe.py'
```

Python内部唯一Node命令：

```text
C:/Program Files/nodejs/node.exe --max-old-space-size=384 --max-semi-space-size=8 --expose-gc D:/dianzi/reports/runs/r17_root_types_memory_diagnosis_20261017/input_probe.cjs
```

真实开始06:26:19.918+08、结束06:26:22.665+08（2.747秒）；Node child exit0、held nativeWait0/signaled/native exit0、外层PowerShell exit0。完整Windows控制树峰4，owned后代剩余0。Job peak275,046,400 bytes，累计job CPU5.890625秒。取usage时active_processes=1是尚在执行的当前Python supervisor，并非残留Node。

Root解析后heapUsed198,464,800 / heapTotal216,424,448 bytes，reviewer解析后heapUsed199,623,504 / heapTotal218,599,424 bytes；释放program并GC后heapUsed分别25,939,096及24,367,008 bytes。这些只代表构造/丢弃语法program，不是语义类型检查的liveheap需求。该候选argv下观测heap_size_limit427,819,008 bytes（408MiB），原512MiB native预算保留。

原helper `execute()`返回布尔failure状态，因此ownrun `input_probe.native_limits.json`原始字段`exitCode:false`表示driver成功；实际整数child/native退出码0以`input_probe.command.json`为准，原收据不覆盖。

本轮应用unit/contract/integration/e2e/live/manual均`not_run`，新增业务通过数量0；静态输入比对与解析诊断通过。没有完整types复跑、PG、WSL、网络、付费调用、秘密读取、holdout读取、Git提交或push。

## 改动与最小复验建议

仅新增本报告及`reports/runs/r17_root_types_memory_diagnosis_20261017/`两个一次性探针源文件、实际start/active/command/stdout/stderr/native_limits/input JSON证据。没有改变frontend、node_modules、tsconfig、锁文件、ACL、状态文件或用户已有tsbuildinfo。初始准备时个别Windows rg通配路径、误路径读取和PowerShell管道语法命令exit1，随后用确定LiteralPath及官方API收敛；这些是只读检查仪器错误，没有算成业务失败或业务通过。

给Root的最小候选仅改运行argv，旧512MiB/1GiB/~2CPU/cap10/wall60限制保持：

```text
C:/Program Files/nodejs/node.exe --max-old-space-size=384 --max-semi-space-size=8 node_modules/typescript/bin/tsc --noEmit
```

Root已明确只在该不同内存布局候选下再进行一次完整类型检查。建议保留现有全部输入（本轮实际455个files），同时保存QueryJob限制、peak_process_memory/peak_job_memory及原生exit，用新label而不覆盖旧134；候选尚未在本报告中签完整types通过。若失败，保留新GC/Job peak并停止扩大补丁，由Root按实际缺口决策，不关strict、不再提高skipLibCheck、不排除测试、不抬512MiB阈值。

合同和计划偏差：无产品/公共合同变更；这是R17的工程诊断，不构成R17完整UI验收或G-E放行。D2/F1/F2/F3评分证据没有新增真实业务场景；仅给E1可复验工程限制留下实测证据。下一任务建议为Root授权的唯一候选类型复验及独立记录，完整工作台/浏览器/PG/live原缺口继续保留。

跳过完整类型/浏览器与外部集成测试；384/8候选对完整语义检查能否成功仍待Root唯一复验，reviewer历史资源可比性不能追认。
