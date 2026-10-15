# R11 / T27 条件 AST 与规则验证纯切片

状态：awaiting_review。纯切片 implementation=complete；R11/T27 整卡与 G-D 阶段验收仍未完成。本次是 root 批准的独立准备边界，不以尚未验收的 R10 图或 R11 生产资产迁移代替前置验证。代码版本：ddfbf8c631a7ea002865d6ae0c1385e63bd87674；基线：e310f7735bd499c4d9fbcefe8a644e2309a16a62；分支 codex/r11-condition-rules；工作目录 D:/wt/r11-condition-rules。报告生成时点 2026-10-16T05:53:12+08:00 之后，所有命令秒级时间见 raw receipts。

最终直属 136 测试通过；完整 unit 回归 2208 通过、6 失败。完整回归仍 failed，失败均在既有 R20 native CPU guard；两次完整回归在该模块失败后停止重复，不改其代码、资源门、断言或 skip。

## 改动与行为

仅新增 `assessment/conditions.py`、`assessment/rules.py`、直属 unit/contract/security 测试、[PG 接线提案](../../docs/decisions/CR-R11_condition_rules_proposal.md) 和本切片报告/日志。没有改共享 schema、version_ranges、资产 parser、认证、API/app/worker、迁移、依赖/锁、progress、金标、阈值或分母；没有 push。

覆盖 W06 全部八叶类型，all_of/any_of，根深度 1 的 8 层限制和 64 AST 节点限制。重复键/节点、循环/共享节点、空组合、任意 NOT、eval/shell/SQL/URL/表达式及越权字段拒绝。内部 schema 可独立生成，未改公共 schema。枚举复用现有 ConditionValue/RuleStatus/AssessmentStatus；当前实际公共目录没有 ConditionNode/PublishedRule 定义，见 schema inventory/search raw 文件。

纯求值只读现有 `AssetSnapshotResponse` 与已绑定 asset_snapshot_id 的 typed 支持事实；字段名复用 manifest_parser 的现行白名单。缺版本、缺配置、缺权限/输入/网络声明、未观察到组件、部分清单及不匹配的完整范围均不转 False；清单证明缺失需要指定 declared_scope 完整且精确匹配。重复资产字段与互斥版本保留冲突，固定快照并发重放一致。版本叶复用已审成熟引擎，不改 PyPI/npm 支持限制；Go/generic/Ollama 传播 unknown 与 unsupported_ecosystem。没有根据显示名推导身份、维护分支或回补修复。

source_fact 的模型假设/未核验/撤回/被替代状态不确认缓解；证据仍进入审计。disputed、互斥事实或已核验反驳保留 conflict。vendor 缓解描述本身不证明当前资产实施缓解，必须由调用者确认事实到固定资产快照的真实关联。所有组合完整评估所有孩子，非决定性冲突/引用不会被短路删除。

规则验证逐叶核对 exact digest 的支持记录、claim/origin/status、rule_kind、来源/source/doc/rev、证据 supports/validation、范围不扩大、必要条件支持和范围完整性。返回 eligibility/missing/conflict/pending_review 与版本化收据，不直接发布。新/未批准谓词、争议、模型假设、无必要条件支持、脱离来源链或私有输入进入 public 规则均阻止发布资格。生命周期复用 candidate/validated/published/retired；无真实 approver 时不造审批记录。PG 引文子串/真实文档版本/语义支持/实际 ACL 仍须事务查询验证，本纯切片不声称已做真实 PG ACL。

software_applicability、observed_path、research_prerequisites 分别求值。软件规则中的网络谓词不决定软件修复/安全，不能取得发布资格；observed_path 的 false 只表示已建模路径；论文前提匹配不表示执行成功。RuleEvaluation 总保留 rule_kind 限制。

## 历史冻结检查与原红（最终结果见以下封存节）

工作目录均为 `D:/wt/r11-condition-rules/backend`，每个完整 argv、秒级 +08 起止和 exit 见 [commands.json](../runs/recovery_r11_condition_rules_20261016/commands.json)。使用自有 .venv，`uv sync --frozen --offline --all-extras` exit 0；0 次产品/模型/测绘外网调用，没有读取 vault/holdout。

| 检查 | 真实命令核心 | 结果 | 原始文件 |
|---|---|---|---|
| unit | `uv run --frozen --offline --all-extras python -m pytest tests/unit/test_t27_condition_rules.py -v --override-ini addopts=` | 101 passed，0 fail/skip，exit 0；05:51:06–05:51:08+08 | unit_final.log/xml |
| contract | 同环境 `python -m pytest tests/contract/test_r11_condition_schema.py -v --override-ini addopts=` | 12 passed，0 fail/skip，exit 0；05:51:08–05:51:11+08 | contract_final.log/xml |
| security | 同环境 `python -m pytest tests/security/test_r11_condition_security.py -v --override-ini addopts=` | 22 passed，0 fail/skip，exit 0；05:51:11–05:51:12+08 | security_final.log/xml |
| 完整 unit 回归 | 同环境 `python -m pytest tests/unit -q`；未覆盖 addopts | **2212 passed / 1 failed / 0 skipped，exit 1**；73.95% 通过原 60% coverage 门，05:51:12–05:52:15+08 | full_unit_final.log/xml |
| 原失败定向复跑 | 同环境 `python -m pytest tests/unit/test_r20_native_cpu_guard.py::test_guard_hard_exit_after_readiness_terminates_worker_tree[native-cpu] -v --override-ini addopts=` | 1 passed，exit 0；05:53:09–05:53:12+08；不抵消完整回归失败 | native_guard_recheck.log/xml |
| 类型 | 同环境 `mypy src/ai_intel/assessment/conditions.py src/ai_intel/assessment/rules.py` | 2 文件，exit 0 | mypy_final.log |
| Ruff / 格式 | 同环境 `ruff check` / `ruff format --check`；两源文件及三测试文件 | 均 exit 0 | ruff_final.log / format_final.log |
| diff | `git diff --check` / `git diff --cached --check` | exit 0；Git LF→CRLF 提示不是错误 | 命令收据/交付核查 |

直属目标测试显式取消全仓 coverage addopts 以单独观察行为；完整 unit 回归保留原 addopts 和 60% 门，没有修改门槛或配置。T27 直属 135 个通过不能把完整回归本轮失败改为通过。

完整回归唯一失败来自既有 Windows CPU guard：`test_r20_native_cpu_guard.py:154` 原断言 `< 10000000`，实测 `5625000 + 4687500 = 10312500` 个 100ns 单位，即 1.03125 CPU 秒。没有修改该测试、1 秒门或 infrastructure。单独原样复跑成功只能证明存在波动，未证实根因已解决；交 root / R20 维护者核查。前三项直属测试与该模块没有调用依赖。

保留 initial_red.log（新增模块前 ModuleNotFoundError，记录命令 exit 2/1 collection error）、full_unit.log/xml（`uv ... pytest` 入口四个既有 tests.* 导入 collection error，exit 2）、mypy.log（新增审计路径 list/tuple 复用四错误，已重命名解决）。使用 `python -m pytest` 后原全仓路径复跑 2213 passed / 73.70% / exit 0（full_unit_recheck.log/xml）；此轮运行过程中仍补了一项 AST JSON 满容量校验，作为历史结果保留，最终冻结依据以上 final 文件。没有把环境缺失说成业务测试失败，也没有把原红删除或改 skip。

## T27-C01–C06 与评分证据

| 条款 | 可复跑行为证据 |
|---|---|
| C01/C02 | 32 个四态表组合；true AND unknown、false AND conflict、false OR unknown、true OR conflict；所有孩子、证据和非决定性冲突保留 |
| C03 | fixed 右开边界、无版本/非法版本、不完整清单/完整但其他 scope、Go/generic unsupported、同名异生态、重复组件版本 |
| C04 | 八叶内部 schema 往返；64 AST 节点满容量携版本字段；深度 8/9 与节点 64/65；注入、任意字段/URL、重复键/节点、循环与空组合拒绝 |
| C05 | 模型无必要条件支持、缺叶、脱离 source/doc/rev、无效/反驳引文、争议、未批准谓词、范围完整性证据和公私范围检查 |
| C06 | 同一软件受影响快照配网络不可达时软件仍 true，路径限定 false；research prerequisite true 有执行不成功限制；非 published/retired 不求值 |

支持 F2/F3/P2 的条件证据保持与已限定版本判断，A1 的确定性调用入口；不据此声称达到官方准确率/召回率/多跳/完整 Agent 评分。没有产品真人金标，更没有独立双人标注自签。

## 调用方、程序偏差与未验证项

首次修改前已完成 rg 的真实模块、schema 与 caller 检查；**CBM 首次索引发生在实现之后**，这是程序顺序偏差，未冒称修改前完成。原因是当时工具不在 tool catalog/Windows PATH；随后复用既有 WSL 0.11.0 binary 与独立 XDG cache 完成索引，没有联网安装或改 ACL。最终源码索引 05:51:31–05:51:37+08：1511 nodes / 7815 edges；assets 默认排除，另独立索引 198 / 823；schema、architecture 原文件和全部六入口 inbound/outbound trace 均保存。最终 13 条 CBM 命令 exit 0，至 05:52:18+08；见 audit_commands.json。没有调用方遗漏证据：evaluate_condition_tree 生产入边仅 evaluate_rule；evaluate_rule / validate_rule 入边均 0；version_assertion 入边新增 `_evaluate_leaf`。rg 再核验 API/worker/配置/export 没有既有接线，因此未宣称产品链已接。

经验检索的两个命中仅泛化 workflow/factory，未与此窄业务匹配，未照搬；复用来源以本仓 StrictRecord 模式、固定资产 DTO、版本引擎、strict_json_object 与 AccessScope 为准。

integration/PG、frontend、e2e、live、manual 全部 **not_run**。纯范围判断不代表真实 ACL；固定资产声明不代表真实网络探测；静态 source 引文收据不代表 PG 已重新核实；论文条件不代表 PoC 执行。3→5 产品真实真值、双人金标与争议裁决保持缺口。原 T27 发布持久化和 T28 快照/epoch 并发重校验、OpenVEX 仍需后续范围，0021 提案未实施。

下一建议：由全新非作者 reviewer 在独立 WT 复跑此代码和真实日志，核对 metadata→PG narrow IO；root 将 review 必修关闭后才可接 T28/0021，完整 unit 的 native CPU guard 失败由其所属切片调查。实现者没有 accepted、progress 更新、阶段放行或 push。


## 最终封存 · 2026-10-16T05:57:43+08:00

最终业务代码 ddfbf8c631a7ea002865d6ae0c1385e63bd87674。封存时补严验证收据不回退 published/retired 生命周期；新增 1 个回归案例。以下是该最终版本实际 replay，前面的 final/recheck 日志为原样历史材料，不能取代此节。

| 检查 | 实际 tests / failures / errors / skipped | exit | +08 起止 | 日志 |
|---|---|---|---|---|
| unit | 102 / 0 / 0 / 0 | 0 | 2026-10-16T05:55:17+08:00 → 2026-10-16T05:55:18+08:00 | replay_unit.log |
| contract | 12 / 0 / 0 / 0 | 0 | 2026-10-16T05:55:18+08:00 → 2026-10-16T05:55:22+08:00 | replay_contract.log |
| security | 22 / 0 / 0 / 0 | 0 | 2026-10-16T05:55:22+08:00 → 2026-10-16T05:55:24+08:00 | replay_security.log |
| full_unit | 2214 / 6 / 0 / 0 | 1 | 2026-10-16T05:55:24+08:00 → 2026-10-16T05:56:40+08:00 | replay_full_unit.log |
| mypy | 工具检查 | 0 | 2026-10-16T05:56:40+08:00 → 2026-10-16T05:56:41+08:00 | replay_mypy.log |
| ruff | 工具检查 | 0 | 2026-10-16T05:56:41+08:00 → 2026-10-16T05:56:41+08:00 | replay_ruff.log |
| format | 工具检查 | 0 | 2026-10-16T05:56:41+08:00 → 2026-10-16T05:56:41+08:00 | replay_format.log |

最终 CBM source 为 1511 nodes / 7815 edges，独立 assets 198 / 823；schema/architecture 与全新入口双向 trace 真实保留，audit_commands.json 为最终执行时点。历史 native CPU guard 的 1.03125 秒失败仍是已观察风险，定向成功和本节回归均不证明其根因已修复；本切片没有放宽或修改该边界。PG/frontend/e2e/live/manual 仍全部 not_run，整卡与阶段状态不变。

最终全仓失败 ID（原断言全部保留）：

- test_cpu_budget_stops_real_work_without_waiting_for_job_scan[python-gil-held]
- test_cpu_budget_stops_real_work_without_waiting_for_job_scan[kernel-io]
- test_idle_native_call_holding_gil_does_not_spend_cpu_budget
- test_short_cpu_task_keeps_its_result
- test_guard_hard_exit_after_readiness_terminates_worker_tree[python-gil-held]
- test_guard_hard_exit_after_readiness_terminates_worker_tree[native-cpu]
