# G-A / R01 · Vitest 安全升级候选独立审查 1

这次变更将前端直接开发依赖 Vitest 的声明 `^3.0.5`（旧锁实际为 `3.2.7`）固定到 `4.1.11`，并更新必要的传递依赖和锁文件缺项。审查结论为 **候选技术通过，可作为 CR-R10 的技术证据**；本审查不授权主版本变更生效，不将 R01、T02、T40 或 G-A 判为 accepted。Windows 默认 GBK 下的冻结质量入口仍有真实失败，详见问题 1。

审查人：`/root/r01_dependency_review`，未参与本批实现。审查仅写本报告及 `reports/runs/recovery_r01_dependency_review_1_20261015/`。无业务、HEAD、锁、金标、阈值、状态修改，无提交/push。候选工作树结束时保持同一 HEAD、同一 tree、干净状态。

## 冻结对象与范围

| 对象 | commit SHA | tree SHA |
|---|---|---|
| 审查候选 | `497740a771e7cb2d719ab22ebad34bd30539e20d` | `056245ba705d7df8822f74d8617db07e744029e5` |
| 比较基线 | `d0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120` | `bd45d960ee9e44b431f3ecf33d431936201691df` |
| 独立质量入口输入 | `4a17ca7b967a10d6077ba5219984a2d1a74cf320` | 只读取其 `scripts/dev.py` Git blob `2c8bf78453f842c809aac5989f76251507474776` |

候选路径：`C:\Users\yinha\.codex\worktrees\recovery-r01-vitest-candidate\dianzi`。已读候选 `AGENTS.md`、执行索引 00、恢复计划 11/12 的 R01/G-A、T02 卡及引用 02/06/08 合同、当前 task_state 的 T02/R01、作者 R01-vitest-candidate 报告。作者报告仅用于定位待核实证据，下面的安装、审计、测试和质量结果均独立执行。

使用最新插件 [Ponytail review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，按正确性、安全、测试、简洁性检查；中文及权限边界按用户任务要求。AGENTS §2.5 要求依赖主版本走变更单；已有 CR-R01–09 不含本次 3→4。CR-R10 明确授权仍是正式集成的前置。

精确差异保存在 [frozen_diff.patch](../../runs/recovery_r01_dependency_review_1_20261015/frozen_diff.patch) 和 [frozen_paths.txt](../../runs/recovery_r01_dependency_review_1_20261015/frozen_paths.txt)：总计 154 个文件，其中前端产品仅 2 个，另有 `.gitattributes` 和 151 个报告/运行证据文件。产品差异为 `package.json` 1 增/1 删、锁文件 207 增/320 删；没有前端业务、测试、Vite/TypeScript/ESLint 配置、认证、公共合同、后端、CI 或状态改动。`.gitattributes` 仅新增作者 run 的 `*.log -text -diff` 与 `*.raw.json -text`，未全局关闭源码 diff 或检查；其既有批准事实由主控负责核对，本次技术审查不代授权限。

| 候选工作树文件 | 实际 SHA256（CRLF checkout） |
|---|---|
| `frontend/package.json` | `c1de34b3d941f70526e256f58ee275bfa5eb16c993efd38a28427acce7573106` |
| `frontend/package-lock.json` | `79e4df46c6646ab2d878b8baeaa9985ab44a1c802a0f47c950ee1869a4cb8c61` |
| `frontend/vite.config.ts` | `8a6aeb592f95a9c471f1095c292a288c697d478c67aa457a73670597f68209ae` |

独立复跑从两个固定 SHA 的 Git blob 导出所有跟踪 frontend 文件到本审查 run 的 `candidate_replay/frontend` 和 `baseline_replay/frontend`，不复制 `.env`、KEYS、附件或 holdout。因此导出文件为 Git LF 字节，hash 与 Windows CRLF checkout 可不同；[inputs.json](../../runs/recovery_r01_dependency_review_1_20261015/inputs.json) 保留 Git 导出 hash，[independent_summary.json](../../runs/recovery_r01_dependency_review_1_20261015/independent_summary.json) 保留原工作树 hash，独立程序核对 CRLF→LF 后逐文件一致。只有副本生成物 `tsconfig.tsbuildinfo`、dist、node_modules 被构建/安装写入，原候选不受影响。

## 依赖、兼容与审计核对

独立实际环境为 Node `24.13.1`、npm `11.8.0`，证据辅助 Python `3.13.11`；这不是后端运行版本的验收。干净 `npm ci` 实际装入 299 包，退出 0；未见基线的 damaged lockfile 警告。仍出现已有 `whatwg-encoding`、ESLint deprecated 警告，未隐藏或把它们误称为新依赖安全漏洞。

独立 `npm ls --depth=0 --json` 对比全部 15 个直接包，唯一版本变化是 Vitest `3.2.7→4.1.11`。React/React DOM `18.3.1`、Vite `6.4.3`、TypeScript `5.7.3`、Playwright `1.64.1`、jsdom `25.0.1`、@types/node `24.19.2` 均保持；完整列表及传递版本差异在独立汇总。锁中 Vitest 系列同步至 4.1.11，chai/es-module-lexer/std-env/tinyexec/tinyrainbow 等随 upstream 依赖变化；tinypool、vite-node 被移除。Babel 部分同版本条目移动/去重，4 个已有空锁条目（`@types/babel__generator/template/traverse`、`@types/prop-types`）补齐，候选缺版本锁条目为 0。基线独立 `npm ci` 自身复现 damaged 警告，支持这部分修复属于必要锁修复，并非额外直接包升级。

独立读取公开 npm registry 的 4.1.11 字段：Node engine `^20.0.0 || ^22.0.0 || >=24.0.0`、Vite peer `^6.0.0 || ^7.0.0 || ^8.0.0`。实际 Node24/Vite6 满足；原 `.npmrc` 的 `engine-strict=true`、Node24 声明均未修改。官方 [v4 迁移说明](https://v4.vitest.dev/guide/migration.html)要求 Vite6/Node20 以上，移除 tinypool，并用 Vite module runner 取代 vite-node。当前配置没有 poolOptions/minWorkers/singleFork/singleThread、定制 runner 或 browser provider，无需为这些旧选项改代码。

独立真实解析的有效 runner 为 `jsdom`、`globals=false`、`pool=forks`、`isolate=true`、`maxWorkers=1`、`fileParallelism=false`；e2e 排除仍有效。[runner_config.stdout.log](../../runs/recovery_r01_dependency_review_1_20261015/runner_config.stdout.log) 保留结果。v4 的 upstream 默认 exclude 比 v3 少，当前有效排除为 node_modules、.git、e2e；本仓现有发现结果仍完全同 4 文件/30 用例。这是已核实的迁移限制，未来新增布局需要重测，不凭假设构造当前阻断问题。前端 coverage 仍未启用，未凭此宣称覆盖率达标。

独立基线 `npm audit --json` 退出 1，包记录为 `@vitest/mocker` moderate、tinypool critical、Vitest critical，汇总 1 moderate/2 critical/total3。候选完整 `npm audit --json` 退出 0，全部 severity=0、`vulnerabilities={}`，没有 omit-dev、allowlist、force、审计阈值调整。原始输出分别见 [baseline_audit.stdout.log](../../runs/recovery_r01_dependency_review_1_20261015/baseline_audit.stdout.log) 和 [candidate_audit.stdout.log](../../runs/recovery_r01_dependency_review_1_20261015/candidate_audit.stdout.log)。这是当时公开 npm 审计的实际结果，不等于依赖不存在未知漏洞。

官方 [Vitest 安全公告](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)将 4.1.11 列为 redirect mock 文件读取问题的修复版；独立锁中 mocker 确为该版本。两项 Tinypool 公告 [worker options](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3)、[run options](https://github.com/advisories/GHSA-85c8-ppgw-ccpr) 在旧审计中出现，候选已移除 tinypool。未运行任何公告 PoC；关闭漏洞的证据是版本/依赖存在性与实际审计。3 是 npm 受影响包记录数，不能宣传为 3 个互不相关漏洞。

## 原测试、真实复跑与质量入口

基线和候选 JSONReporter 均实际执行 30/30，4 文件、0 failed/0 pending/0 todo；独立程序对 `(相对文件路径, fullName)` 的完整多重集合逐项比较相同，包含参数化展开，未用通过数量代替 ID 一致性。分布为 shell 10、client 13、status 6、App 1；完整身份清单见独立汇总。所有前端测试/配置 Git blob 均与基线相同，T40-C01–C06、C05 的三个分例及其断言都保留。新增运行参数只设置 reporter/outputFile，没有降低门槛、删难题或改金标。

候选独立 JUnit 实际包含 30 个 `<testcase>`、0 failure/0 error/0 skipped，4 个 suite 的用例和也为 30；[candidate_junit.xml](../../runs/recovery_r01_dependency_review_1_20261015/candidate_junit.xml) 留档。实际导入固定质量 blob 的 `read_test_report` 返回 30/0/0/0，`_report_result` 返回 0，没有父子 suite 双计数。零文件负例 `npm run test -- __r01_independent_review_no_matching_case__` 实际退出 1，0 测试未被算成功。

候选本身未包含新质量入口；本次从质量 SHA 导出原 `scripts/dev.py`，与候选前端组合作为隔离副本复跑。其 LF 字节 SHA256 为 `bf4a7fc7a5490dac4d0ab4d6988d398efd762b5c316e53b1829fd0826deb44b7`（作者 checkout 的 CRLF hash 不同，Git blob 相同）。显式 UTF8 时实际依次执行 lint/typecheck/JUnit/test/build，入口最终输出 30/0/0/0、退出 0。此结论限定这组固定输入和编码环境，不声称原候选 HEAD 自带完整 R01 quality/infra。

下表所有时间为 2026-10-15 Asia/Shanghai 秒级实采。C=`candidate_replay/frontend`，B=`baseline_replay/frontend`，Q=`candidate_replay`；均位于本审查 run。每一行的同名 `.meta.json`、`.stdout.log`、`.stderr.log` 保存完整 argv、cwd、开始/结束、退出码与原字节日志。其它代码索引/版本/证据校验命令也逐条保存在 [commands.json](../../runs/recovery_r01_dependency_review_1_20261015/commands.json) 与 [actual_commands.md](../../runs/recovery_r01_dependency_review_1_20261015/actual_commands.md)。重复运行不累计为更多独立用例。

| run_id / 实际命令 | cwd | 开始—结束 | 退出码 | 数量与结果 |
|---|---|---|---:|---|
| candidate_ci / `npm.cmd ci` | C | 00:12:11—00:12:16 | 0 | 299 包，安装成功 |
| baseline_ci / `npm.cmd ci` | B | 00:12:41—00:12:47 | 0 | 308 包，damaged 警告保留 |
| candidate_audit / `npm.cmd audit --json` | C | 00:12:41—00:12:43 | 0 | 0 受影响包记录 |
| baseline_audit / `npm.cmd audit --json` | B | 00:13:08—00:13:11 | 1 | 3 受影响包记录，预期旧风险 |
| candidate_lint / `npm.cmd run lint` | C | 00:12:41—00:12:47 | 0 | 静态检查；测试数不适用 |
| candidate_typecheck / `npm.cmd run typecheck` | C | 00:12:41—00:12:43 | 0 | strict 保持；测试数不适用 |
| baseline_json / `npm.cmd run test -- --reporter=json --outputFile=<run>/baseline_vitest.json` | B | 00:13:08—00:13:14 | 0 | 30 pass、0 fail/skip/todo |
| candidate_junit / `npm.cmd run test -- --reporter=junit --outputFile=<run>/candidate_junit.xml` | C | 00:13:08—00:13:14 | 0 | 30 cases、0 fail/error/skip |
| candidate_json / `npm.cmd run test -- --reporter=json --outputFile=<run>/candidate_vitest.json` | C | 00:13:35—00:13:40 | 0 | 30 pass、同 30 ID |
| candidate_build / `npm.cmd run build` | C | 00:14:26—00:14:28 | 0 | 30 modules，构建成功 |
| quality_frontend_inherited / `python scripts/dev.py check --scope frontend --timeout-seconds 90` | Q | 00:14:55—00:15:06 | 1 | 构建 stdout 输出 GBK 编码失败；不算入口通过 |
| quality_frontend_utf8 / 同上，`PYTHONIOENCODING=utf-8` | Q | 00:15:15—00:15:25 | 0 | lint/typecheck/test/build 均真实执行；30/0/0/0 |
| no_test_negative / `npm.cmd run test -- __r01_independent_review_no_matching_case__` | C | 00:18:53—00:18:54 | 1 | 0 用例，正确失败 |
| rollback_pair_quality_utf8 / 固定质量 module 的 `run_scope_checks("frontend",90)`，UTF8 | baseline_replay | 00:18:53—00:19:05 | 0 | 旧依赖对再跑 lint/typecheck/test/build，30/0/0/0 |
| candidate_diff_check / `git diff --check <base> <candidate>` | 原候选 | 00:17:12—00:17:12 | 0 | 无 diff 空白错误 |

本审查证据核验助手首跑 `check_evidence` 于 00:17:23—00:17:24 退出 1：助手错误地假定旧锁所有包都有 version，遇到原空锁条目 KeyError。修正助手仅用于记录这类旧缺项，未动产品或断言期待；`check_evidence_recheck` 00:17:51—00:17:51 退出 0。两份失败/成功日志均保留；不将助手失败伪装为 30 业务测试失败。

## 已复现的问题与权限限制

1. **Windows 默认 GBK 在输出构建日志时使质量入口失败**（范围外质量 SHA 的 `scripts/dev.py:137`；调用位置 `:241`）。
   - 职责：该函数捕获真实工具输出，并把 stdout/stderr 转发给调用者。
   - 触发与结果：Windows 默认 GBK、未设置 PYTHONIOENCODING，执行 frontend scope 到 Vite 的 `✓ 30 modules transformed`；工具已经成功，但 `sys.stdout.write(stdout)` 抛 `UnicodeEncodeError`，入口退出 1，最终统计不输出。完整最小复现见 `quality_frontend_inherited.*`。
   - 最小修复：在已授权 R01 quality 变更内使入口自身输出流采用 UTF8，或把明确 UTF8 环境作为平台运行合同并在实际入口落实；仅给 child 设置 UTF8 无法解决 parent 输出。不要忽略编码错误或把退出码改成成功。
   - 不处理的影响：普通 Windows 自动入口仍会将构建成功报告为失败，R01 默认入口不能据本次 UTF8 复跑宣称无条件可用。本问题已在作者报告中记录，独立复现与其一致；它属于另一固定质量输入，不是此次 Vitest 两文件差异引入，不阻断本依赖候选的技术结论，整 R01 验收仍需质量修复/明确合同后重测。

无其他已确认的候选必须修复或简洁性问题。没有以未来目录、未知平台或纯猜测给出阻断发现。候选技术通过仍不代替 CR-R10：AGENTS §2.5、恢复 11/12 的变更规则与本任务授权范围要求用户明确批准新主版本后，主控才能集成生效；本报告不写 accepted、manifest 或进度。

## 回滚核对、索引与未检查项

作者回滚命令的范围正确：同时恢复基线的 `frontend/package.json` 与 `frontend/package-lock.json`，再 `npm ci`、再前端 scope；不能只改一份文件。两个固定 frontend 树除依赖对外逐文件一致，baseline_replay 就是该产品依赖对回滚后的精确输入。本次实际用旧依赖对干净安装、JSON 测试及 UTF8 quality scope 复跑，全部维持 30 用例，支持回滚路径可执行。未在原候选执行 `git restore` 或实际换 HEAD；回滚风险也独立重现为 old damaged 锁警告和 audit 3，不把回滚视为安全修复。若集成后已有用户改动，应先核对差异再使用范围明确的恢复命令，本次不授予后续覆盖权限。

代码索引实际执行 WSL `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --help`，随后 index/schema/trace 均退出 0；独立 cache 为仓库外 `/tmp/dianzi-cbm-r01-dependency-review-1-20261015`，project 为 `dianzi-r01-dependency-review-1`。仅索引候选 `frontend/src`，58 nodes/164 edges，fast 模式明确排除 3 个 src 测试，外部 tests 目录也不在索引根；未声称图覆盖全部用例。`getCurrentUser` trace 指向 AuthProvider/App 和 fetchJson/parseCurrentUser，与真实 `rg` caller 结果交叉一致；Vite 配置、所有 4 测试文件另外以 rg/逐文件源码读取核对。索引结果及 [source_crosscheck.stdout.log](../../runs/recovery_r01_dependency_review_1_20261015/source_crosscheck.stdout.log) 留档，未索引秘密、holdout、附件，未创建 ADR 或改写代码。

未检查：真实 API/PG/Redis、live 来源/模型、真实浏览器 e2e、人工验收、后端全量回归、覆盖率 provider、Linux/macOS/其它 Node/Vite 组合、未来新增测试布局；均 `not_run`，不能补为 passed。这里的 30 个前端测试使用明确合成 HTTP fixture，不能作为在线 API、模型问答或真实资产安全证据。没有付费调用、扫描第三方资产或运行外部 PoC。

评分证据仅支持 E1/R2 中固定依赖安装、前端回归/构建与可观察检查结果，不推出系统完整性或阶段门通过。下一步为主控据这些固定证据完成 CR-R10 的兼容/迁移/回滚说明、取得用户明确授权，再集成到新的统一冻结 SHA 并补独立检查；整 R01/G-A 的其它验收由对应审查负责。

Verdict：**候选技术通过；正式生效仍待 CR-R10，整 R01 不在本报告验收。**

## 本轮自有临时复验工作区回收（后续明确授权）

主控在完整安全扫描后明确授权回收本审查独占创建的 replay 工作区，不提交安装缓存或旧 fixture 源复制。2026-10-15 00:46:03—00:46:12（Asia/Shanghai）以原生 PowerShell `Remove-Item -LiteralPath ... -Recurse -Force` 精确删除以下两个绝对目录，退出 0：

- `D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\candidate_replay`：8666 文件，124393891 字节。
- `D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015\baseline_replay`：9012 文件，129250293 字节。

删除前核对 GetFullPath、Resolve-Path 及 run 根前缀一致，两个根和全部子项无 reparse point；`prepare_review.py` 初始导出在目标已存在时明确失败，原 prepare 日志证明这两个目录属于本轮新建副本，未含用户先前文件。其余内容只来自本轮 npm 安装/测试/构建和固定质量 module 导入。没有跨 shell 删除、触碰冻结 WT、其它 run 或用户文件。详细路径、归属、秒级时间和删除量见 [cleanup_replay_workspaces.ownership.json](../../runs/recovery_r01_dependency_review_1_20261015/cleanup_replay_workspaces.ownership.json)，实际执行 argv/退出码与日志见同名 `.meta.json`、`.stdout.log`、`.stderr.log`。

原 33 次命令 meta/stdout/stderr、commands.json、actual_commands.md、JSON/JUnit、输入 hash、独立汇总和 frozen diff 全部保留；清理前后逐个 SHA256 一致，清单见 [retained_artifacts.sha256.json](../../runs/recovery_r01_dependency_review_1_20261015/retained_artifacts.sha256.json)。原 commands.json 仍仅含原 33 次审查执行；新增 cleanup 独立登记，没有覆盖失败日志。清理后原候选仍为 `497740a771e7cb2d719ab22ebad34bd30539e20d` / tree `056245ba705d7df8822f74d8617db07e744029e5` 且干净。

本 run 不再有任何复制的前端 `.ts/.tsx` 文件或完整 fixture 源文件，额外独立输入样本保留数量为 0。源码本身可从 inputs.json 中的两个前端 SHA 与固定质量 Git blob 重建，无需将副本提交。保留的 `source_crosscheck.stdout.log` 是原始 rg 命令证据，可能含上述固定前端合成 fixture 的命中行，SHA256 为 `f4b971f171f409b391a0a60998e26cdd80a522b5c61f11d2509e80cc179f8fdb`；它不是新输入样本或真实秘密。JSON/JUnit 仅保留本轮实际测试身份和结果，完整 hash 在保留清单中。现有辅助脚本中依赖 replay 的复验步骤需先在新建临时位置从固定 Git 对象重建输入；原结果及日志不依赖工作区继续存在。
