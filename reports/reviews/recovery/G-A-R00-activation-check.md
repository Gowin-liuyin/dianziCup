# G-A · R00 生效登记定向核对

首次创建、本次写作开始/结束、最后更新、证据截止：2026-10-14T22:38:09+08:00（Asia/Shanghai，+08:00）。
审查者：`/root/r00_independent_review`；范围：15d0272→69ecf16的登记/文档/日志，再定向核对69ecf16→f0b154e的13份文档/状态修订。
冻结目标：**69ecf16be7d95e839b18a4a40f03b3f9d86707f4**、**f0b154ee0e10100bc9a9d293ebeded13926d0a42**。
当前被核对tree：**43814fbde67e5c89267875b7b0776e5bf7451f00**。工作目录：`C:\Users\yinha\.codex\worktrees\recovery-r00-recheck-clean\dianzi`；两次安全切换前后均clean，HEAD精确匹配，不审主仓正在实施的API diff。

## 结论

**生效登记符合独立意见，定向核对通过。** 主控只登记R00及 `R00:T00/R00:T01/R00:T04` 三片accepted，九CR只批准准确落实；review_ref正确指向独立复核，reviewed_code_sha保持实际被审 **15d0272bd2a9e25d19397d8147e9c3cbe6016f9b**，没有把登记提交69ec/f0冒充实施被审版本。

原整T仍没有accepted，R01只是in_progress、implementation=not_started、八层not_run；后者记录的是冻结集成进度，不根据其他worktree在途代码提前签实现通过。R02–R24没有新增accepted，G-A仍未通过。没有误签未审产品能力，R01继续按已独立生效合同开发，不等待文档自SHA循环。

本核对不替代R01新初审或G-A新阶段review，也不改变[原R00定向复核](G-A-R00-review-1-recheck.md)的范围与未检查项。

## 差异与冻结内容

69ec共300个变动路径，主要为211份已指定review原始文件/显式synthetic输入，以及登记、文档与日志；没有backend/frontend/scripts/tests/fixtures/benchmarks/experiments/config/infra/CI业务改动。backend、frontend、scripts、tests、fixtures、config、infra的Git subtree ID与15d完全相同，原独立源码索引因源码未变继续有效，不为文档登记重建代码图。

manifest的实际JSON差异**只有** `recovery.authority.status/review_ref/reviewed_code_sha/activated_at` 四字段；审批指向已读独立报告与15d，时间2026-10-14T22:19:34+08:00。baseline差异**只有** `source_hashes.contracts/task_manifest.json`，新值 `eab9b195d09cbdc34fc930a896018e403c9b2e00d46a9f8ca97f41443c32ece9`。requirements与pilot_cases字节冻结值保持原样，新旧门槛、六不变量、case IDs和评分分母不变。

状态的差异局限于R00与三输出片的状态/证据/独立ref/被审SHA/时间、R01调度状态、恢复authority摘要和更新时间；原T状态与产品验证层没有改绿。当前结构检查实际验证全部accepted片的证据文件/review路径和R包输出一致性，不以“文件存在”替代独立报告的语义。

60原任务卡仅同步恢复附录标题为“已独立核验生效”，每张卡的原正文、原前置与C01–C06保持一致；独立逐卡比较60/60相同。00–06、11/12追加有日期的生效记录，并保留历史；九CR正文的建设决策、兼容/迁移/回滚/测试影响没有改动。新登记引用保留“原整T不自动通过、G-A未通过、人工金标/阶段门保留”，没有减掉余片或把资源smoke当应用集成。

69ec的300个新增/修改文件做了两类窄秘密模式检查（API key/private key），0匹配；未发现本次变更中的.env、KEYS-AND-USAGE或holdout路径，没有打开秘密库或输出匹配值。这是限定模式检查，不声称全面秘密/匿名保证。其报告和输入仍按原review场景标synthetic，不计产品验收或人工金标。

## 文档问题与已核对修订

69ec曾有下列具体同步问题，已向主控指出；f0修订后无需再阻断R01：

| 项目/位置 | 69ec实际问题 | f0核对结果 |
|---|---|---|
| CR-R01–09第3/4/7行 | 顶部仍awaiting_review、旧更新时间、独立审查尚未发生/review_ref=null，与已附生效记录相冲突 | 九单顶部全部accepted，保留首次20:52:23，更新时间22:31:09；reviewer、ref及被审15d准确，9/9确认 |
| progress/task_state.json:7 | execution_order_source仍写awaiting independent activation | 已明确independently activated R00，并保留原最终依赖，不改真实任务状态 |
| 恢复11:5、12:3 | 顶部仍将当前R00标awaiting_review/实施中 | 已改R00独立accepted/生效，12显示R01实施中；原带日期记录保留 |
| progress/context_handoff.md:3 | 指向R01-resources.md，但该资源报告不在69ec冻结树 | 已明确“主仓尚未并入本R00冻结树、随R01提交同步、资源smoke不签应用集成”，不再暗示可在本冻结快照据此复跑资源验收 |

69ec新增的规范文档/报告相对Markdown链接定向检查22项，22项目标存在；synthetic临时副本中的历史链接不当作规范交付入口。f0没有新增错误的Markdown目标，九CR的独立ref指向已经冻结的实际报告。

恢复11第5行仍有原初稿“未开始本方案的产品开发、未改写已有任务验收状态”一句。**本报告明确把它解释为制定方案时的历史描述**；当前事实以已登记authority、最新生效记录、state和R01调度为准，不使用旧初稿否定已经生效的合同。后续R01文档同步可在该句前加“初稿制定时”，这是非阻断说明，不要求新的R00批准或另一次文档自指审查。

f0实际仅修改9CR、恢复11/12、handoff、state共13路径；manifest及baseline字节与69ec完全相同，状态除执行入口说明外没有新增验收变更。没有纳入主仓在途API业务实现。

## 本轮实际验证

逐命令argv、真实cwd、时间到秒、退出码、stdout/stderr保存在 `reports/runs/recovery_r00_activation_check_20261014/` 的JSON及 `commands.json`，不是作者日志替代本轮结果。

| 检查 | 被审版本 | 真实结果 |
|---|---|---|
| HEAD/tree/status | 69ec、f0 | 各exit0，精确SHA，工作树clean |
| `git diff --check` 指定元数据/文档范围 | 15d→69ec | exit0 |
| `python scripts/verify_plan.py --baseline contracts/baselines/plan_baseline_recovery_r00.json` | 69ec | exit0，PLAN_OK，非产品测试 |
| WSL Linux Python执行同一baseline命令 | 69ec | exit0，PLAN_OK；原字节与Git/baseline匹配 |
| `git diff --check 69ec… f0…` | f0 | exit0 |
| 同一Windows baseline命令 | f0 | exit0，PLAN_OK；manifest/baseline未改变 |
| JSON字段级比较、accepted范围、60原卡正文、链接与9CR顶部 | 指定两个delta | 上述结果，明细 `activation_inventory.json`、`header_recheck_inventory.json` |

没有改动业务/校验器/测试输入，本轮没有再重复56项unittest或业务原始DSN测试。15d上的56/56及静态检查已经独立复跑并写在前报告；主控post登记56/56另有其自身记录，本轮不把它计为新的独立测试数量。产品unit/integration/security/frontend/e2e/live/manual没有本轮新验收，所有现存未通过/未运行/资源阻塞继续保留。

本reviewer只写本报告和专属日志，未改业务、真实state、CR、baseline、金标或阈值，未安装/迁移/清库/测试危险DSN，未读密钥值或holdout答案，未提交/push或向其他用户聊天发送消息。

**最终意见：69ec登记范围正确；f0已同步所指出的当前页头/状态/资源引用问题。R00与九CR的独立生效依据继续有效，原整T与G-A没有误签。继续R01实施，后续业务初审和阶段门仍用新的独立reviewer与冻结业务SHA。**
