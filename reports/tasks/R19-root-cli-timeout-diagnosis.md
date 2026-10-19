# R19 Root CLI 超时独立诊断

任务状态 `awaiting_review`，本诊断实现 `complete`；不签 `accepted`，不修改整 R19/T46 的状态。诊断输入为 `codex/full-delivery-recovery@3fd9cd68f292afcd1b88ca55f218c4e869e8f706` 加 Root 已集成且未提交的 R19 三文件切片。源码冻结 `982532dd564f3eda5d85a6e252b2cf9ce16f98d1`、独审 `8f326cdceb3dd8b15d1eac45f82188df6bd1e1ae`。本轮仅写本报告和 `reports/runs/recovery_r19_root_cli_diagnosis_20261017/`，不改业务、原测试、oracle、状态、公共合同、依赖、认证、金标、阈值或分母，不提交/push。

已读 AGENTS、执行地图、R19 恢复卡、T46、评测合同、CR-R18 依赖登记、state/交接、冻结审查报告，以及 diagnosing-bugs 和 Ponytail 5.3.1 review。原 Root 已连续两次 60 秒超时，本轮不扩大补丁或重新运行完整失败组；先审原事实，再经 Root 明确批准进行一次 ≤20 秒合成 CLI 定位。用户 tsbuildinfo、push 台账、Root-batch13-index 和其他 Agent 的修改均不触碰。

## 结论与证据边界

**已证实的编排问题是把原来分别有界验证的两个 CLI class 合并进一条 60 秒命令。** 原独审的 `CliTests` 10 方法实际墙钟 51.682 秒，`CliRegistryRegressionTests` 5 方法实际墙钟 17.028 秒；两次独立启动的墙钟合计 68.710 秒，JUnit suite time 合计 63.871 秒。它们原本每组各自 ≤60 秒，不能把原限定通过误解为联合 15 方法也能在 60 秒内完成。该合计是历史观测，不是对当前 Root 联合耗时的精确预测；当前 Root 原联合命令已两次实际触发 deadline。

**重复冷启动的成本已在当前 Root 的单 CLI 中测到。** 原 15 方法的成功路径累计启动 34 个 Python、40 个 Git、1 个 cmd；不是 75 个同时进程。每个新的 Python CLI 顶层导入 jsonschema。当前单 CLI 的 cProfile 测得 jsonschema 累计 1.904542 秒、rfc3987_syntax 1.732828 秒、39 次 Lark 构造 1.684156 秒，其中 38 次 `make_syntax_validator` 累计 1.608712 秒。`protected_roots`（Git 注册表读取及逐根 resolve 合并）累计 0.598221 秒，`main` 累计 0.605729 秒，候选校验累计 0.002630 秒。profile 带额外开销，只证明此执行路径的相对成本与调用次数，不作为无仪器 CLI 的性能验收值。

没有证据要求修改原子 writer、降低格式校验、换依赖或扩大 timeout。当前 probe 未执行 export/write_new，不能凭它单独验收原子导出、并发或中断恢复。原 Root core 90 例的通过由既有完整 JUnit 证明，本轮没有重复这些例；crash 三方法和拆分后当前 Root CLI/registry 的完整验证由 Root 后续运行。

## 原失败与原独审的准确输入

Root 原收据目录：`reports/runs/recovery_reviewed_integration_20261016/`。

| 原命令标签 | 真实 +08 开始 → 结束 | child exit / 结果 | 完整 Windows 峰 / 残余 | Job CPU / peak memory |
|---|---|---|---|---|
| `reviewed_slices_batch15_unit_contract` | 04:52:35.254 → 04:53:35.335 | 124 / deadline_exceeded；无完整 XML，0 项计通过 | 10 / 0 | 86.3125 秒 / 357089280 bytes |
| `reviewed_slices_batch15_core_fix1` | 05:14:25.300 → 05:14:32.181 | 0；90 tests，fail/error/skip=0；pytest 输出 7.25 秒 | 6 / 0 | 9.6875 秒 / 209063936 bytes |
| `reviewed_slices_batch15_cli_fix1` | 05:17:44.633 → 05:18:44.699 | 124 / deadline_exceeded；无完整 XML，0 项计通过 | 10 / 0 | 86.359375 秒 / 311869440 bytes |

第一条实际选 R06 合同/单元及原 annotation 四文件，计划总 108 方法；stdout 是 99 个进度点。第二条失败只选 `../scripts/annotation/tests/test_prepare.py::CliTests` 和 `../scripts/annotation/tests/test_prepare_fix1.py::CliRegistryRegressionTests`，stdout 为 13 个进度点、stderr 空。两条失败的原 command/count/stdout/stderr 留存；不把点数计为最终通过数量，也不把没有 XML 的 0 errors 当成通过。

两条失败都用 base CPython：

```text
C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe
```

cwd 为 `D:/dianzi/backend`，`PYTHONPATH` 显式前置 `D:/dianzi/backend/.venv/Lib/site-packages` 与 Root/backend 的已有路径，`PYTHONNOUSERSITE=1`，`APP_ENV=test`、`DATA_MODE=fixture`。pytest argv 末尾为 `--no-cov -q --junitxml=<各自原路径>`；原 XML 路径未改写。Job 实际覆盖 supervisor 和其后代：512 MiB/process、1 GiB/job、CPU rate 833 / logical CPUs 24，约 1.9992 核；工具 pwsh/conhost 祖先单独采样，不能说整个控制链都在 Job 内。

原独审收据目录：`reports/runs/r19_annotation_tool_review1_20261017/`。其准确两条 argv（相同 base Python）为：

```text
python -m pytest scripts/annotation/tests/test_prepare.py::CliTests -q -o addopts= --junitxml=reports/runs/r19_annotation_tool_review1_20261017/security_cli.xml
python -m pytest scripts/annotation/tests/test_prepare_fix1.py::CliRegistryRegressionTests -q -o addopts= --junitxml=reports/runs/r19_annotation_tool_review1_20261017/security_registry.xml
```

cwd=`D:/wt/r19-annotation-tool-review-1`。第一条 03:38:59.612→03:39:51.294，exit0、10 tests、suite 48.942 秒、Win峰10；第二条 03:39:57.044→03:40:14.072，exit0、5 tests、suite 14.929 秒、Win峰7；两条失败/错误/跳过均0、残余0。这是读取的历史证据，不能宣称本诊断跑了15例。其 helper 未设置本次 Root 的 OwnedJob CPU/内存限制，不能据历史耗时推断两个环境严格同条件。

Root 与作者冻结的 Git blob 实际相等：prepare=`267b3adf2d1f9df883e5ae3538446a5a9f9f62ff`；原 test_prepare=`f1e48d26ce69335fe5092c0dbee6324e607c393b`；原 test_prepare_fix1=`54a851cdc1073e2db20d5069f7bb6b65adc8ac15`。Root prepare raw SHA256=`7db603b4cdbaccb85ab670f268c81e6a86aea76ba4c8a2e8c8fcc4864e2fcd05`，独审 WT raw 为 `20920148bf6197301a40e1a27125bd2e44ce09a3440ba712037ca0163d4f63eb`；Git 文本换行规范不同，不冒称 raw 一样。

## 源码、class 与 caller 链

已有独审 source snapshot 图为41 nodes/137 edges、72 CALLS；它只索引 prepare.py，不是全仓动态执行闭包。本轮读其原图材料并用实际源码/rg补核，没有新跑 WSL/CBM。

入口链是 Root runner → base Python pytest → unittest class → `sys.executable` 的新 base Python CLI → prepare 模块顶层 jsonschema import → `main` → `protected_roots` → strict JSON loader/schema/候选/标签检查 → 按 action 执行导出或显式扫描。普通 cli helper 的单次 timeout=30（test_prepare.py:396、test_prepare_fix1.py:196）；并发测试两次 Popen 后各 communicate(timeout=30)。所有单次都低于30秒也不保证整个class/双class低于60秒。

prepare.py:17 导入 jsonschema；已装 jsonschema/__init__.py:13 导入 `_format`，后者 :328 导入 rfc3987_syntax。`syntax_helpers.py:50` 建初始 Lark，:65–66 和顶层38次调用再建38个；probe 实际调用数39吻合。backend锁与已批准的 `jsonschema[format-nongpl]` 包含该链，候选schema仅用date-time format也要承担模块导入成本。没有读取或修改包环境、锁或运行任意下载代码。

prepare.py:326–350 每个 action 都同步执行 `git worktree list --porcelain -z` 并 resolve 注册根，main:504 无条件调用，没有扫 reports 内容。read_document:69 只懒导入 verify_plan.load_json，verify_plan 顶层只 stdlib；扫描 :478 的 rglob 只在 scan action 的显式小目录中执行。本轮单 validate 的 profile 显示没有调用 scan_leaks 或 write_new，Root 大报告树不是此执行路径的直接读取对象。注册根 resolve 的成本确实非零，尚无 Root/WT 同条件差分证据证明这是 Root 特有性能回退。

pytest unittest collector 使用 base `TestLoader.getTestCaseNames` 字母序；第二失败命令 class 顺序固定为 CliTests→Registry。前10方法属于CliTests，第11 alias、第12 missing Git、第13 new registered WT、第14 orphan export、第15 product root。正常非pdb路径的 unittest call 包括 tearDown 后才形成 passed report；13 dots不能定位为第13内部Git add/remove挂住，最多定位到其pytest teardown或第14开始附近。原收据没有逐项时刻，本轮不补造准确卡住函数。第14合法执行链在 `summarize→inspect_annotations` 拒绝孤儿裁决，未到write_new，因此不能把writer fsync/hardlink列为该方法的直接根因。

## 一次有界单 CLI 定位

先定义输入：从原 test_prepare.py 的 NOW/QUOTE/QUOTE_HASH 与 fixture_bundle AST 提取一个显式 synthetic/dev fixture；不导入测试/prepare来构造输入，不包含 annotations，不读取真实 human/holdout/secret/.env。预期：exit0、candidate_count1、synthetic1、awaiting_human_label1、human_gold_count0、formal status not_run/分子分母null。

Root 在 Source native scope 结束后明确给 heldACK，批准 ≤20 秒、fullWin10、512 MiB/process、1 GiB/job、rate833/24；只启动一个实际 CLI子进程。命令：

```text
& 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' -B 'D:/dianzi/reports/runs/recovery_r19_root_cli_diagnosis_20261017/diagnose_one_cli.py'
```

显式 shell=`C:/Program Files/PowerShell/7/pwsh.exe`、login=false；child准确argv含 `-B -X importtime -m cProfile -o <ownrun>/single_cli.pstats <Root>/scripts/annotation/prepare.py validate --input <ownrun>/synthetic_dev_input.json`，cwd=`D:/dianzi/backend`。所有凭据环境过滤沿Root既有fixture规则，未输出环境值；网络/PG/WSL/付费调用均0。

实际 2026-10-17T05:25:55.465→05:25:58.450+08，整个诊断主函数2.985秒，tool/child均exit0、上述输出断言吻合、source raw hashes前后稳定。Windows完整pwsh/conhost/supervisor/CLI/两个Git进程峰6≤10，residual0；Job CPU4.140625秒、peak126390272 bytes、退出前仅supervisor active1。preexisting conhost PID22960 / birth `2026-10-16T21:25:55.061128+00:00` 保留，本次没有触发kill。

完整命令/身份/内存CPU/输入与源码hash在 `single_cli.command.json`；stdout、importtime stderr、profile原件、selected profile summary、带时刻全树samples均在本ownrun。该执行是一个synthetic行为定位，不是一个新pytest方法，也不是完整timeout修复绿灯。正式业务unit/integration/live/manual本诊断均 `not_run`。

## 超时回收的独立缺口

原 shared helper :61 记录完整preexisting tree，但 :84–95 的超时kill只跳过supervisor与control pwsh。残余报告 :107又排除preexisting。因此同一个preexisting conhost可被kill选择，又不会出现在remaining_owned中；remaining0不证明控制台未受影响。

原两失败的具体控制身份：

| 原标签 | control pwsh | supervisor | preexisting conhost（原UTC birth） |
|---|---:|---:|---|
| unit_contract | 16100 | 21392 | PID60048 / `2026-10-16T20:52:34.802415+00:00` |
| cli_fix1 | 36852 | 51148 | PID22244 / `2026-10-16T21:17:44.190597+00:00` |

上述conhost各自属于原preexisting/峰值链，既不是supervisor也不是control，故匹配时会落入旧terminate选择分支。**原收据没有保存deadline最终tree、逐PID terminate尝试/返回或conhost退出码，本轮没有调用杀既有控制台的危险复现；无法证实那两次实际TerminateProcess是否成功，也不能把Root交接的0xE9症状直接归因为已证实误杀。** Root称原tool raw已保留，工具0xE9不在当前pytest stderr（其为空）；后续若要关闭归因，需要从raw及新harness明确记录选择/返回来核实，不能洗掉原失败。

## 最小修复建议与复验

只建议Root改自己的编排和回收；本诊断没有应用以下diff。

1. 将 runner `groups["cli"]` 留作 `CliTests` 一条，新增 `registry` 仅含 `CliRegistryRegressionTests`；保持core90、cli10、registry5、crash3，合计原108 distinct方法不变。各command仍60秒/fullWin10/512 MiB/1 GiB/2核，独立新前缀stdout/stderr/XML/counts，串行运行，不覆盖旧失败。新分组若仍超时保持真实失败，不能由本报告预先签通过。
2. 超时回收跳过exact preexisting PID+birth，继续完整计数；不要从峰值统计排除控制链以压cap。最小条件在旧skip后加：

```python
if preexisting.get(pid, {}).get("birth_utc") == item["birth_utc"]:
    continue
```

随后只对当前birth仍匹配的新增自身后代调用TerminateProcess；将当时tree、每次action/返回、控制对象preserved、finally残余写收据。既有控制台保留不影响Job对新增业务子进程的限制。此建议只修Root自有harness，不修改共享helper；若Root决定修改共享文件，须由Root拥有该写入和相关复验，本Agent不扩权限。
3. 先完成上述四组当前Root真实验证，再考虑是否确有产品CLI启动优化任务。此轮不移除FormatChecker、不关闭extras、不长期缓存worktree根表、不修改原测试或减少子进程行为；这些均超出诊断最小修复。

复验预期是四份完整JUnit分别90/10/5/3且fail/error/skip0，每份实际exit0且完整资源/残余检查通过，重复ID按原方法去重；不是把历史独审的15例与当前Root重复相加。Ruff/mypy/plan、实际产品integration、真实人工双标、正式冻结、Linux SIGKILL/断电恢复和最终性能均未由本诊断执行。公开短证据候选不等于人工金标，R19/T46整卡及阶段仍待完整验收。

## 偏差、评分证据与交接

本轮没有合同/计划/评分分母变更。诊断仪器cProfile/importtime故意增加开销，原始profile保留，不用仪器墙钟宣称无仪器性能达标；原Root进度点只能定位，不能计pass。原错误和0xE9交接保留，控制台kill归因的证据缺口明确列出。

D1/E1/X1证据限定为真实命令、冻结源码、失败/资源/调用链可追溯和最小编排修复建议；P2/P3/A1没有新评分，真人/金标0，没有正式评测。下一任务建议：Root唯一实现两个harness改动，按原class分组串行复验108例，并由新非作者审核新当前Root收据。本诊断到此停止，不续做业务或后续R任务。
