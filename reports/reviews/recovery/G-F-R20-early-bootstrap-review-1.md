# G-F / R20 · early bootstrap 独立 review 1

What this change does: Windows 的固定 PDF / semantic worker 先以 `-S` 等待私有 gate，父进程使用真实创建句柄安装原 Job、guardian 和额外 CPU 监督，再恢复 `site.main()`、venv、coverage 与业务入口。父在收到合法结果后仍检查最终监督错误，初始化、EOF、CPU 查询失败不会冒充成功。

**Verdict: Ship，严格限定于早期接管、真实 handle、失败拒绝及本次有限协议兼容改善。原严格累计 CPU 门仍 needs_changes / partial，不能签整 R20、G-F、原 T06/T40/T45/T49/T50/T51 或 E1/P1 达标。** 本报告完成、交主控登记；没有写 accepted、修改公共状态、提交或 push。

## 1. 冻结身份与独立性

审查者未参与实现。首次 shell 在现有 `D:/dianzi` 执行 `git worktree add -b codex/r20-early-review1 D:/wt/r20-early-review1 4ebfe9a7ae076f3c98d54d72f0b56188350b3efa`，exit0；初始工作树干净。业务 SHA **abc2c7b50e83c2681f28bbcf35d7f4d014cf096f**，材料 SHA **4ebfe9a7ae076f3c98d54d72f0b56188350b3efa**；这两版本的整个 backend src/tests、pyproject、锁文件无 diff。没有 spawn 或触碰作者、主控工作区的修改。

已读实际 AGENTS、执行图、恢复 R20、原 T06/T40、03/04/05/06/09 合同、冻结 state/交接、CR-R07/09 与 CR-R20、作者早期/bootstrap 和 startup 报告、原 native guard 两轮独立 review、CPU boundary 与固定 8a 诊断。按新版 [Ponytail review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md) 核查连接代码、实际 caller 和可观察行为。公共状态里的旧 pending 不被当成当前能力不存在，也不反推 accepted。

作者 manifest 的真实原字节 SHA256 **eb05f8b44d52fcb81fbc022d5565e3674f5ffc302c47b07ab5024ce780bccfe2**；**161/161** 条目的大小和 raw SHA 全匹配。Git OID 为 Git blob 身份，未当作 SHA256。`source_identity.json` 分别保存 checkout raw、代码 Git blob、材料 Git blob 的 SHA256 与 CRLF/LF 数量：例如 limiter checkout raw `edd2bcc3f1914226b4acd08a14028cc082c7881c81696959708f4347929307e5`，LF Git blob SHA256 `9b0fb1c7f54a621460e0e12c152c8ded433d7c518eb7c969b0a2ba0203636495`，差异只是换行。

独立 AST 对照 8a 基线确认：旧测试仅改变 `test_r04_real_parsing.py` 的协议/timeout 两函数、`test_r20_process_startup.py` 的环境函数，以及 `test_pdf_parent_rejects_result_missing_after_guard_hard_exit`。全部其他函数、case 数量、装饰器、模块 AST 相同；原四、初始耗尽、1/3/8 门、60% 门没有改动。生产修改仍仅四份白名单源文件，原 `_pdf_worker.py` 未改。

本 worktree 自有 `uv sync --locked --offline`，**04:59:31—04:59:38 +08，exit0**，CPython3.12.13 / Windows11 build26200；editable 安装指向本 backend。没有模型下载、费用、网络来源/PG调用、秘密/holdout或第三方资产动作。

## 2. Must fix：原严格 CPU 合同仍有实证失败

### 1. 早期接管后仍不能证明累计 kernel+user 严格小于 1 秒

**位置：**`backend/src/ai_intel/infrastructure/process_limits.py:347–357` 等待50ms后才读累计 CPU，达到预算才终止；`:365` 的终止不能撤回已经消费的 CPU。原直接 `-c` 测试仍在 site/coverage 后进入 `bound_process_resources`；其 `test_r20_native_cpu_guard.py:86/154` 原门保持。

**具体触发与问题：**本冻结新入口的正常 CPU 样本与 body READY 后0.4秒 guardian硬退出样本，都在真实 `GetProcessTimes` 下最终为 **1.03125 CPU秒**，严格 `<1` 为 false。两次都无完整结果，父记录 `worker CPU budget exhausted` 并清树；这是拒绝成功改善，不是硬界通过。原四仅一次复跑 **3 fail / 1 pass**：short 无 RESULT、exit0xC0000044、累计1.421875；Python fault累计1.25；native fault累计1.125；idle fault0.75通过。short这一次没有 guardian内部 last-error/首读记录，因此不强行归为 API错误或某个初始化分支。

**最小处理与复验：**保持该验收 needs_changes / partial 和所有红，不能将候选登记为严格 CPU 修复。技术后续须先给出能约束累计 kernel+user 的平台依据，再在已批固定入口接缝内验证；不能以更短采样、magic余量、扣启动CPU、重置baseline、扩大误差、改 `<1` 或重复碰绿替代证明。下一次有界复验应包含原四及本次 normal/body fault，保留默认coverage、真实CPU/退出句柄与失败日志；本 reviewer 已达12上限，不再运行。

**若跳过：**系统会把一个已复现超界的 sampled safeguard 当成严格 CPU 硬保证，原验收仍失败。该问题是已知合同未闭合，本报告没有另提计划外重写或将它伪装为新发现的特权攻击漏洞。

## 3. 真实入口与边界核查

- PDF：`catalog_pages._nist_document` / parser re-export → `parse_pdf_text_layer` → 固定 base Python `-S _worker_bootstrap.py pdf` → `_pdf_worker.main/_bound_memory` → pypdf → 私有stdin → JSON → 父结构/页码/文本/资源检查。容量2、32MiB、300页、100万字符、512MiB/15CPU、20秒communicate与环境白名单保持；真实官方4页、中文与精确page locator通过，无效PDF负例通过。spy全部操作委托真实Popen，记录创建handle、argv和环境键；PDF没有透传COV_CORE或无关环境。
- Semantic：`LocalSemanticModels` → `_run_worker`，spawn前建立≤30秒总deadline → 本地 `SpawnProcess/Popen` → 标准 preparation/reduction.dump → gate/site → 标准spawn_main → 真Pipe。父supervisor引用位于dump后，线程锁没有进入序列化；合法384维归一化**合成**结果通过，EOF拒绝。真实模型/第三方推理库反序列化与推理没有执行，模型固定revision/size/hash及数值边界由原纯回归检查，不能称live模型通过。
- 早期子只接受pdf/semantic白名单；父先设置原memory/CPU Job，启动guardian，分配exclusive kill-on-close lifetime Job，建立持真实handle副本的监督线程，再SetEvent。子复用原限额 envelope；无全局set_executable、无新业务真值、无任意URL/shell/SQL工具。
- `site.main()`恢复有真实行为证据：早期短任务与semantic合成worker的 `coverage.Coverage.current()` 活跃；pypdf从本venv成功导入并解析。没有另打印每个子进程的sys.prefix；不能据此声称其他解释器布局也支持。
- 监督读全部worker线程kernel+user，不扣启动。正常worker退出仍最终查询；已收到合法信封后close新发现的错误仍拒绝成功。独立零worker测试覆盖有效PDF输出遇最终监督失败，以及退出worker低于/等于/超预算和GetProcessTimes错误6。原真实invalid-handle注入也得到WinError6；这与正常观察器查询全部成功分开统计。
- lifetime最后句柄仍仅guardian持有，父监督不持有它。body fault的worker/leaf/guard全部结束；父错码、Pipe EOF和空输出不被当成功。Windows进程可能exit0仍无完整结果，父继续验证协议；semantic正常信封后父finally terminate造成exit65536，是已测清理行为，不等同协议失败。
- Linux原Popen/spawn/RLIMIT分支未改，Windows导入仅在其分支执行。这里只做源码核对；WSL用于CBM，不是Linux产品回归通过。

独立 CBM project `r20_early_bootstrap_review1_src_20261016`，索引本WT `backend/src`，**1425 nodes / 7193 edges**，not-indexed/skipped/partial/unusable全0，显式excluded `ai_intel/assets` 一目录。architecture/schema及limiter/PDF/semantic三个trace成功；没有复用作者索引或写ADR。动态spawn/局部import/测试seam由源码和全caller `rg` 再核对，不靠图推断。索引节点数与作者旧1409不同，未当成代码变动；上述Git整backend等价检查为空。

## 4. 实际命令与结果

完整argv/cwd/+08开始结束/exit在本run各 `*.command.json`；每个worker组另有原观察JSON、JUnit、coverage和stdout/stderr。解释器均是本WT `.venv/Scripts/python.exe`，pytest cwd是本WT backend。

| run / 上海时间到秒 | primary | 行为 / exit / coverage |
|---|---:|---|
| original_four 05:00:54—05:01:06 | 4 | 1 pass / 3 fail；exit1；1.59% <60 |
| product_pdf 05:01:37—05:01:50 | 2 | 2 pass；exit1仅局部coverage8.35% |
| semantic 05:02:09—05:02:15 | 2 | ok/EOF 2 pass；exit1仅局部coverage11.12% |
| early_short 05:02:37—05:02:43 | 1 | 1 pass、RESULT4999950000；exit1仅局部coverage8.82% |
| early_normal_cpu 05:02:46—05:02:51 | 1 | 严格CPU1 fail；exit1；coverage8.89% |
| body_python_fault 05:02:54—05:03:00 | 1 | 严格CPU1 fail；exit1；coverage8.84% |
| unready 05:03:23—05:03:27 | 1 | 无结果、两进程exit1并结束；自有句柄基线1 fail；未加载60门，不能计门通过 |
| pure 05:03:56—05:04:08 | 0 | 96 pass / 0 fail / 0 skip；exit1仅12.91% <60 |
| pure_config_recheck 05:04:51—05:05:04 | 0 | 同96 pass，显式 `-c backend/pyproject.toml`；exit1仅12.91% <60；属于重复调用 |

首个pure其实已正确读取backend默认配置；在读其日志前发起的显式config复验是重复检查，未加为独立案例。一次序列108个案例为 **102 pass / 6 fail / 0 skip**，其中5为严格CPU/原short失败，1为自有unready句柄断言失败。包括重复pure的实际调用为 **204次、198 pass / 6 fail / 0 skip**，不能称198个独立通过。完整pure及整体60%验收本review `not_run`。

static于05:04:46—05:04:47：Ruff/format **9文件exit0**，mypy win32 **4源exit0**，git diff-check exit0。零worker回归包含原启动、资源输入/envelope、semantic格式/模型身份、PDF协议/timeout/capacity、未知入口拒绝和最终监督失败边界。没有修改原阈值、金标、分母、skip或依赖。

## 5. 12个primary的真实计量与退出

CPU是该PID真实handle的最终GetProcessTimes；wall由Win32 creation/exit ticks相减。原四采用真实base worker，排除venv redirector；PID须连同run与creation ticks识别，不能把不同run复用PID合并。

| 样本 / PID | memory / CPU budget / 等待门 | kernel+user CPU秒 | 创建至退出wall秒 | exit |
|---|---|---:|---:|---:|
| 原short 37940 | 100MiB / 1 / 8s | 0.75+0.671875=1.421875 | 1.6030248 | 3221225540 |
| 原Python fault 43532 | 100MiB / 1 / 8s | 0.859375+0.390625=1.25 | 1.4974051 | 0 |
| 原idle fault 34420 | 100MiB / 1 / 8s | 0.5625+0.1875=0.75 | 1.3077825 | 0 |
| 原native fault 45404 | 100MiB / 1 / 8s | 0.46875+0.65625=1.125 | 1.2509027 | 0 |
| 真4页PDF 44864 | 512MiB / 15 / 父20s | 0.421875+0.359375=0.78125 | 0.8962819 | 0 |
| 真invalidPDF 44876 | 512MiB / 15 / 父20s | 0.234375+0.0625=0.296875 | 0.3521395 | 0 |
| semantic合成ok 41520 | 2GiB / 30 / 总30s | 0.3125+0.296875=0.609375 | 0.7408631 | 65536 |
| semantic合成EOF 29600 | 2GiB / 30 / 总30s | 0.46875+0.203125=0.671875 | 0.7292242 | 65536 |
| early短 3844 | 100MiB / 1 / 8s | 0.5625+0.234375=0.796875 | 0.8427377 | 0 |
| early正常CPU 14784 | 100MiB / 1 / 8s | 0.6875+0.34375=1.03125 | 1.0741536 | 3221225540 |
| body Python fault 43796 | 100MiB / 1 / 8s | 0.65625+0.375=1.03125 | 1.0948743 | 3221225540 |
| 未ready 42088 | 512MiB / 15 / gate与guard等待3000ms | 0.015625+0=0.015625 | 3.044031 | 1 |

**12/12，最后primary于05:03:27 +08退出，此后没有启动primary。** 含两次零worker命令在内共观察 **74个进程实例**，全signaled、0外层timeout、0discovery error，**15853次观察器采样CPU查询全部成功**。观察累计CPU73.0625秒含pytest controller/redirector/guardian/leaf/conhost，不能当12个worker CPU或持续运行时长；完整逐PID清单在 `execution_summary.json.owned_process_instances`。观察器原样继承已成熟诊断实现，只发现自有controller后代、核对creation并保留handle，未终止非自有进程。5ms发现可能漏掉极短helper，所以不是绝对完整全树或长期无泄漏证明。

作者24primary/132observed及原1.03125红已逐材料核验，属于作者不同运行，未与本review数量合并；作者一次原四4pass不消除本次3red或旧诊断red。

## 6. 缺测、疑虑与自有工具失败

**未ready句柄检查未证明。** 固定worker没有越gate运行，stdout空、worker/guard都结束；自有未预热baseline在显式关闭Popen owner后为169→177，断言失败。spy强保留Popen引用且communicate会建立reader线程，没有记录gc后的稳态handle归属，不能把+8定性为产品泄漏。该单文件absolute测试使pytest rootdir选择ROOT，未读取backend默认coverage，是review harness缺陷；原失败与缺门保留。预算已满，不偷偷补第13个worker；可靠预热/稳态句柄复验留下一有界批次。

工具失败原样保留：CBM `cli --json --help` 为unknown tool/exit1；architecture首次`--aspects '["all"]'`被当一个非法aspect/exit1，改为`all`的独立recheck exit0，未覆盖旧log。最初宽工具目录/组合阅读输出截断、`docs/contracts`与不存在的`07_security_privacy.md`/`cbm_architecture.command.json`路径错误、PowerShell传rg通配目录错误，均非业务检查。进入文件化runner前这些工具失败只有对话输出，摘录在 `prelog_tool_failures.md`，不伪造精确起止/原始完整日志。汇总首次KeyError误用owned顶层signaled，实际字段在final，旧执行源/原工具stderr保留；只修自有汇总，05:07:58 recheck exit0，0worker。

观察器原stdout/stderr在JSON中有效UTF8、无replacement字符。最初派生`.stdout.log`经Windows write_text发生回车展开；原文件不覆盖，`.raw.log`从JSON有效字符串逐字节恢复原CR/LF，manifest同时列两者，不把派生日志冒称原字节。run局部 `.gitattributes` 仅保留证据`-text`，log/xml `-diff`保护原失败栈空白；`.gitignore`仅本run `_cache/`与`_temp/` scratch，所有JSON/XML/coverage/错误源仍封存，不改全局检查。

Not checked: 原四之外的全部native/双线程/kernel IO/内存热点、其他early故障负载、初始exhausted/near真实复验、稳态/长期句柄、并发压力、其他Windows/解释器布局、Linux实际RLIMIT、Job accounting/ETW/硬调度界、真实模型重库/权重加载/推理、完整pure60门、PG/integration/live/manual、认证/跨租户/注入全链、监控/恢复/备份/CI/CD。原3秒CPU热点wall门保持，未把本次8秒故障选择称为该四热点全测。

## 7. 独立后续与交付

**R06来源批量与其他非CPU路径可在主控既有有界授权下安全独立继续。** 受控来源网关、非PDF解析/归一化、不可变原文/PG游标与outbox、重放幂等、权限及页面错误状态开发不依赖Windows `<1` 硬界结论；应保留真实环境/来源失败而非转假成功。使用PDF/semantic的批量或压力验收、依赖硬CPU证明的安全/性能/最终阶段不能借此放行。此结论不新增外部费用/扫描/部署授权，不宣告R06整卡或G-C/G-F通过。

E1仅新增可信固定worker早期资源/生命周期与失败拒绝证据；P1仅新增有限真实CPU/启动观测，严格门保留。没有公共合同或计划变更，review自有缺测如上。下一建议是主控登记限定安全改善Ship及严格CPU保留问题，并分配可靠handle/平台证明的最小独立复验；本review到此停止。

精确改动仅本报告和 `reports/runs/recovery_r20_early_bootstrap_review1_20261016/` 的证据文件，逐文件大小/raw SHA256/raw Git blob SHA1列 `artifact_manifest.json`，manifest自身hash列 `manifest_identity.json`。源、原tests、状态、合同、锁、阈值无修改。没有提交、push、accepted或公开发布。
