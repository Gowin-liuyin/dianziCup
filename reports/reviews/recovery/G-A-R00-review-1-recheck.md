# G-A · R00 独立初审 1 的定向复核

首次创建、本次写作开始/结束、最后更新、证据截止：2026-10-14T22:16:46+08:00（Asia/Shanghai，+08:00）。
实际复跑记时：2026-10-14T22:04:38+08:00至2026-10-14T22:12:48+08:00；此前切换与阅读未另行打时标，不补造时间。
独立reviewer：`/root/r00_independent_review`，未参与修复实现。
被审SHA：**15d0272bd2a9e25d19397d8147e9c3cbe6016f9b**；tree：**a637b17bbab71c8ccdc38525d1db607b403a88c3**。
原初审SHA：d752fe0c8f14dd4c35b39863cfba0d1c902fffae；原意见：[G-A-R00-review-1.md](G-A-R00-review-1.md)，其原始失败意见及日志保留。

## 结论

**RV-01、RV-02已在冻结15d0272上独立复核关闭。R00本卡及R00:T00、R00:T01、R00:T04三个输出切片在R00规定范围内可以独立accepted，九份CR准确落实授权的核验通过，可由主控据本报告登记生效。** 本reviewer没有修改任何状态或CR审批字段，也没有自行commit/push。

这个判断只接受合同合并、状态纠偏、执行映射、冻结可复跑和本卡公共schema。它不自动接受原T00/T01/T04整卡；T01的R19、T04的R02/R18等余片和原最终前置/六验收仍按原合同核查。**整个G-A未通过**，R01–R03真实API/认证/PG/worker、重启、事务/并发等尚需完成并由新的阶段reviewer验收。

## RV-01 · 字节冻结复核

新.gitattributes精确将requirements、manifest、pilot_cases设为 `-text`，前两份仅局部允许既有CR-at-EOL；原字节哈希与新/旧baseline没有通过改值“补绿”。独立比较三JSON与d752的解析内容完全相同；九CR、状态文件、两baseline、公共schema、旧原始state和NVD响应的Git字节均未改。

先在原审查目录确认clean，从d752安全切到15d0272。该**复用旧工作树**虽然HEAD正确、Git status仍clean，但不变blob的fixture保留了旧CRLF物化，Windows/WSL基线最初均exit1。Git restore及checkout-index --force同样未实际重写它；所有失败日志保留。没有再扩大修复，没有重写baseline或案例业务值。这说明旧checkout的字节残留不能仅凭status判断，**不代表新候选checkout仍有同一缺陷**。

随后独立创建新的managed worktree，operation `06ddaa68-2faf-4558-9749-6667c36c28de` 完成并附属本主任务：
`C:\Users\yinha\.codex\worktrees\recovery-r00-recheck-clean\dianzi`。
该目录HEAD/tree精确匹配上述候选，`core.autocrlf=true`、status为空，**未手动处理任何内容**，Windows及WSL Python的指定baseline均exit0。三个文件的baseline、Git blob、Windows实际字节和WSL sha256sum完全一致：

| 冻结输入 | 精确SHA-256 |
|---|---|
| contracts/requirements.json | fd83695b9935cd6addf3f4430a5a63cb8e6ac8e27c1d52df88f230a305d54b4f |
| contracts/task_manifest.json | 85c21c0ffd912080275d44fe741c41921fcfbe72b3886884db7e96b0b1c37cfb |
| fixtures/synthetic/pilot_cases.json | 8686ba8db7793e5ac59cab339e61ea8b0bfd4e85ecd65e9f657c2d4ade0b990d |

另用Git checkout-index向全新前缀自动物化三输入，也精确匹配这些hash。证据为 `fresh_integrity.json`、`fresh_baseline_windows.json/stdout.log`、`fresh_baseline_wsl.json/stdout.log`、`fresh_wsl_source_hashes.stdout.log` 和 `materialization_integrity.json`。旧目录1907ff53…与相应exit1记录保留；后续工作直接从最终冻结SHA新建干净worktree，复用旧目录时先核实字节并仅恢复已确认无用户改动的冻结路径，不清理用户文件。

## RV-02 · 消费与输出切片门复核

修复只在共享 `check_task_state` 的accepted R节点循环内新增requires_slices/output_slices检查，以capability_slices.original_task定位原T的slice_acceptance。原有逐accepted切片的证据文件与review_ref检查继续复用，没有另一份状态真相或整T先accepted的新门。关键代码为冻结 `scripts/verify_plan.py:720`–`735`。

独立复验原初审的**同一all-slices-pending恶意构造**，不改变它的输入或评分合同：新CLI exit1，实际列20项 `STATE_RECOVERY_REQUIRED_SLICE/STATE_RECOVERY_OUTPUT_SLICE`，覆盖R00三输出、R01输入/输出和R02输入/输出。旧脚本曾exit0；如今实际拒绝，日志在 `all_pending_negative.*`。

再使用真实冻结manifest构造显式synthetic正例：R00/R01/R02所需及输出切片独立accepted、有合成证据/review文件，**整张T06仍pending、R20:T06仍pending**，CLI exit0。它证明早期能力可以推进，不会被后段整T反锁。把R01:T06证据与review移除后exit1，分别报EVIDENCE_MISSING和STATE_REVIEW_MISSING；正例输入在专用synthetic目录，没有更新真实state，不能计为产品通过。实际日志在 `needed_slice_positive.*`、`accepted_slice_missing_evidence.*`，输入与冻结绑定在 `recheck_integrity.json`。

新增7项作者回归由本reviewer重新执行，涉及输入/输出切片、证据/审查缺失、早期整T pending合法例、R24-A/B及聚合partial。原49项完整保留，本次56项均真实通过，无失败/skip。R24-A后整R24保持partial的正例仍过，A输出与B消费候选未验收的负例仍被拒绝；没有改变R24-A→R23→R24-B顺序。

## 范围与九CR核验

九CR与初审已读取版本逐字节相同，第一次逐单中文意见继续有效：九职责与四/九角色基线，PG权威及可重建向量/图/对象投影，八类与通道及时效口径，公共schema适配/异步/四态/大小上限，来源冲突与撤回，公网聚合与FOFA授权资产双链，切片执行/原卡最终验收/独立review与阶段push，冻结评测/双人金标/holdout，共享认证/MCP/插件边界均准确落实用户批准的CR-R01–09；每单兼容、迁移、回滚、任务/测试影响完整，产品实施结果仍留对应后卡。

requirements/manifest本次仅为既有冻结原字节落盘，解析内容与初审相同；60原任务、110切片、26节点、13要求、U01–U14、原最终前置与360原C验收没有削减。原state仍24 needs_changes/36 pending/0 accepted，八层纠偏和旧历史保留；此复核不把旧记录重新变绿。新旧baseline阈值、六不变量与case IDs继续原样，未读取holdout答案。

| 可独立验收的R00输出 | 实际接受内容 | 保留限制 |
|---|---|---|
| R00:T00 | 当前真实基线、既有实现缺口、资源/费用/凭据/资产/发布授权类别、事实诚实与历史保留的审计切片 | 不认证账号有效性或实际产品live，不据此自动签原T00全部C项 |
| R00:T01 | 13要求/评分/原任务映射、110切片合并规则、重复键严格解析、八层证据状态、旧字节历史、冻结基线与能力依赖校验 | R19人工标注/盲测余片仍未完成，文件存在不证明引用内容或review独立 |
| R00:T04 | 公共八对象适配合同、完成/任务联合、四态/no_match未知、200同步与10MiB/10000独立异步上传、禁止自报tenant等静态边界 | R02内部领域持久化、R18运行适配/协议/SDK/实际客户端仍未完成；格式合法不等于引文支持 |

R00六项验收在本卡范围已有证据：100/100分、13要求/14U、60T归属、公有schema正负、旧accepted纠偏与冻结/依赖校验、授权类别分别登记。本独立复核补闭了初审阻断，主控可引用被审SHA和本报告登记R00及三个输出切片；不能把“R00 accepted”作为所有原T或整个阶段通过的替代。

## 实际命令与结果

逐命令完整argv、cwd、真实时间到秒、退出码及stdout/stderr均在同run目录JSON；汇总为 `commands.json`。本次新的通过记录，不复用作者PASS。本表缩写的冻结绝对路径可由argv复跑。

| 命令/观察 | cwd | 退出码/数量 |
|---|---|---|
| `python -m unittest discover -s tests/plan -v` | 原审查worktree，HEAD=15d0272 | 0；56 tests、56通过/0失败/0skip（47计划+9公共合同，不重复相加） |
| 指定 `verify_plan.py --baseline …recovery_r00.json` Windows / WSL | **新干净managed worktree** | 0 / 0；PLAN_OK，仅合同结构 |
| 原all-pending副本 `verify_plan.py --root …accepted_r02_missing_slices` | 原审查worktree，HEAD=15d0272 | 1；20项拒绝，符合预期 |
| 独立需要切片accepted、整T pending正例 | 同上 | 0；合法早期能力放行 |
| 已accepted切片去证据/review负例 | 同上 | 1；2项拒绝，符合预期 |
| `uv run --locked --offline --no-sync ruff check <冻结scripts/verify_plan.py> <冻结tests/plan>` | D:\dianzi\backend已有uv环境 | 0；4文件，无诊断 |
| 同环境 `ruff format --check` / `mypy --follow-imports=skip <冻结verify_plan.py>` | 同上 | 0 / 0；4格式文件 / 1源文件 |
| `git diff --check d752fe0… 15d0272… -- .gitattributes contracts scripts tests/plan docs progress` | 原审查worktree | 0；本次代码/合同差异无whitespace错误 |
| 旧checkout基线与局部物化尝试 | 原审查worktree | 基线保持1，真实失败日志不覆盖；最终通过依据来自自动正确的fresh目录 |

本次未安装依赖、未修改锁文件。Ruff/mypy使用已有宿主工具但目标源码为冻结绝对路径；新旧审查目录的scripts/backend/src全部逐字节相同。WSL检查是Linux Python访问新managed checkout，未冒充完整Linux产品部署或真实数据库验收。

## 索引、未检查项与交付

实际刷新codebase-memory-mcp 0.11.0独立窄索引，新cache `/tmp/dianzi-cbm-r00-review1-recheck-20261014`，name `dianzi-r00-recheck1-scripts-15d0272` / `dianzi-r00-recheck1-backend-15d0272`，仅scripts与backend/src；不含秘密、holdout、附件或提交的临时测试副本。`check_task_state/load_json ← run_all_checks ← main ← CLI入口` 的新trace与源码/rg交叉一致，修复门位于真实CLI共享路径。索引源hash绑定在 `recheck_integrity.json`，与最终fresh源码完全相同，未拿旧图审新代码。

未检查：产品PG/队列/权限/事务/并发/重启、模型/测绘真实live、前端业务/e2e、MCP客户端、正式评测、人工金标、持续运行、报告/PPT渲染。它们integration/security/frontend/e2e/live/manual仍not_run或原任务资源阻塞；R00通过不清除后卡缺口。默认API/PDF/NVD/cursor/模型等既有产品缺口初审已复现，本次生产源未变，未反复全仓重审，也未将环境不可达当软件修复。

本reviewer只写本复核报告、run日志和显式synthetic临时输出；执行的是已授权安全checkout/新managed worktree及只读检查，没有实现业务修复、改state/CR/金标/阈值/分母、读密钥值/秘密库/holdout答案、调用付费API、提交或push。旧工作树、初审失败及本次旧物化失败均保留，新worktree留供复跑。

评分证据仅为E1/D1/X1的计划/状态完整性和可追溯独立验收；其他要求保留映射，不产生正式评分或性能数字。

**Verdict：R00及三个R00输出切片可以按本意见accepted；CR准确落实可生效。原整T不自动accepted，G-A尚未通过。下一步继续R01–R03的真实运行链，阶段门另派未参与实现的新reviewer。**
