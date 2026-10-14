# R00 · 严格计划验证器工作包

首次创建时间：2026-10-14T21:07:40+08:00
本次写作开始时间：2026-10-14T21:41:05+08:00
本次写作结束时间：2026-10-14T21:41:05+08:00
最后更新时间：2026-10-14T21:41:05+08:00
证据截止时间：2026-10-14T21:41:05+08:00
任务状态：awaiting_review；实现状态：complete（仅本验证器工作包，不代表R00整卡或G-A通过）。
实现/修复Agent：r00_plan_validation；独立初审冻结d752fe0发现RV-02，定向修复仍awaiting_review。本文作者未担任独立reviewer；主控派原reviewer复核。
共享工作区：`D:\dianzi`；分支：`codex/full-delivery-recovery`。
代码版本：初轮历史快照基于b8199ce5，原delivery_snapshot.json保留；当前RV-02修复基于HEAD `d752fe0c8f14dd4c35b39863cfba0d1c902fffae` 的未提交diff，精确内容hash/diff见rv02_delivery_snapshot.json/rv02_changes.diff。未将基线HEAD冒充修复提交版本。
提交/push：本工作包未提交、未push、未签accepted。

## 1. 输入输出与改动范围

输入为官方评分追踪、原60任务manifest、恢复26执行节点/25聚合R卡、7阶段、能力切片、原任务合并验收、状态及证据引用。输出仍使用现有CLI：合法结构退出0并打印PLAN_OK，合同违反退出1并给出编号，重复键/错误JSON形状/不可读输入退出2并打印INPUT_ERROR。PLAN_OK只证明结构，不证明产品正确性、live、金标或独立审查内容真实。

仅修改`scripts/verify_plan.py`、`tests/plan/test_verify_plan.py`，新增`tests/plan/test_recovery_plan.py`与本报告/本工作包run目录。未修改manifest、state、产品业务、公共schema、依赖/锁、金标、计分门槛、旧baseline或用户文件。

## 2. 实际行为

- 标准库json的object_pairs_hook递归拒绝重复键，包括数组内历史对象；错误含实际文件路径。所有现有JSON入口和baseline读取共用严格解析。
- 恢复合同存在时验证26执行节点、25R卡状态、7阶段分区、T00–T59全映射、13要求与U01–U14覆盖、执行依赖和无环、切片ID/所有权/输出唯一划分、原最终依赖不减、原验收文件存在及合并规则、CR记录文件存在、变更生效审查引用。
- 切片执行依赖可由显式depends_on的传递前置满足。此规则允许早期能力切片推进，不要求包含后段的整T卡先验收；T卡最终accepted仍必须合并全部required_slices并满足原final_dependencies。
- 八层状态完整登记；passed的全部evidence路径须为存在的项目内文件。accepted另外需要完整实现、无failed/blocked、review_ref存在；原T卡的每个required_slice须独立accepted并有证据和审查引用。独立审查引用内容与评审者独立性由新reviewer核查，脚本不猜。
- 保持R22→R24-A→R23→R24-B，R24聚合accepted要求A/B均accepted；T59含A+B切片。依主控最新合并规则，T55/T56允许候选材料完整验收后由A切片完成，若B实质修改材料由主控重新审查对应版本，避免与T57前置互锁。
- independent_preparation采用当前manifest真实字段：id、work_package、after、requires_slices、allows、final_gate。验证唯一ID、存在且先于正式工作包的前置、切片在准备前置链内、允许范围与正式门文本非空；R24骨架对应R24-A正式节点。该校验不把独立准备升级为最终验收。
- recovery缺席时保留旧合同兼容检查。原16测试全部保留；测试副本额外复制恢复合同/证据/审查引用。子进程显式UTF-8避免Windows下中文错误输出被错误解码。

复用现有要求/评分/顺序/案例/基线哈希检查与依赖环检测，未新增依赖。新增恢复检查确实用于批准的能力切片、审查与状态安全边界，未重写产品框架。Ruff格式整理仅在分配的三个文件内，未新增全局忽略。

## 3. 问题与闭环

| 问题 | 输入/预期/实际与根因 | 影响 | 修复/复验与状态 |
|---|---|---|---|
| V-R00-01 | 初版16新场景，预期拒绝重复键、丢映射、非法依赖、partial accepted；旧脚本除正常结构外未能拦截15场景，json默认最后键覆盖。 | 恢复状态可伪通过，原T片段可误验收。 | 统一严格解析与恢复检查；24新场景+16旧回归40/40；本包实现修复，待独立review。 |
| V-R00-02 | 新旧首轮合跑发现原state真实重复note；旧16中14项因INPUT_ERROR先行失败。 | 无法把旧副本作为合法结构继续测试。 | 未在测试副本绕过或归一化；主控R00另包保留字节历史并重写无重复状态，随后37/37和40/40，日志保留。 |
| V-R00-03 | 静态检查最后补边界判断出现101字符长行，Ruff明确失败。 | 风格检查未过。 | 在允许文件运行formatter，复跑ruff/format/mypy均0，格式后的最终40/40，已修复待review。 |

问题发现/修复的实际执行时间分别见对应run JSON。各批失败日志保留，不覆盖，不将环境缺失记为业务失败。

## 4. 实际验证

下表命令分别在run JSON记载的真实工作目录执行（测试/CLI为D:\dianzi，Ruff/format/mypy为D:\dianzi\backend）。所有日期时间为Asia/Shanghai、+08:00。

| 命令 | 实际开始/结束 | 退出码 | 数量/结果 | 原始run索引（同目录日志） |
|---|---|---:|---|---|
| `python -m unittest discover -s tests/plan -p test_recovery_plan.py -v` | 2026-10-14T20:51:34+08:00 / 2026-10-14T20:51:37+08:00 | 1 | 16 项；1 通过、15 场景失败（重复键三个subtest使failure断言共17） | `red_run.json` |
| `python -m unittest discover -s tests/plan -p test_*plan.py -v` | 2026-10-14T20:55:53+08:00 / 2026-10-14T20:55:59+08:00 | 1 | 32 项；18 通过、14 失败，历史状态重复note阻止旧回归 | `green_run_01.json` |
| `python -m unittest discover -s tests/plan -p test_recovery_plan.py -v` | 2026-10-14T20:59:05+08:00 / 2026-10-14T20:59:09+08:00 | 0 | 21 项；21 通过、0 失败、0 skip | `green_recovery_run_02.json` |
| `python -m unittest discover -s tests/plan -p test_*plan.py -v` | 2026-10-14T21:01:07+08:00 / 2026-10-14T21:01:17+08:00 | 0 | 37 项；37 通过、0 失败、0 skip | `final_full_run_01.json` |
| `python -m unittest discover -s tests/plan -p test_*plan.py -v` | 2026-10-14T21:03:23+08:00 / 2026-10-14T21:03:34+08:00 | 0 | 40 项；40 通过、0 失败、0 skip | `final_full_run_02.json` |
| `python -m unittest discover -s tests/plan -p test_*plan.py -v` | 2026-10-14T21:04:42+08:00 / 2026-10-14T21:04:53+08:00 | 0 | 40 项；40 通过、0 失败、0 skip | `final_full_run_03.json` |
| `python scripts/verify_plan.py` | 2026-10-14T21:04:53+08:00 / 2026-10-14T21:04:53+08:00 | 0 | 结构校验PLAN_OK，非产品测试 | `repository_check_02.json` |
| `uv run ruff check ../scripts/verify_plan.py ../tests/plan/test_verify_plan.py ../tests/plan/test_recovery_plan.py` | 2026-10-14T21:04:40+08:00 / 2026-10-14T21:04:40+08:00 | 0 | 3 个文件；无诊断 | `ruff_final_02_run.json` |
| `uv run ruff format --check ../scripts/verify_plan.py ../tests/plan/test_verify_plan.py ../tests/plan/test_recovery_plan.py` | 2026-10-14T21:04:40+08:00 / 2026-10-14T21:04:40+08:00 | 0 | 3 个文件；格式一致 | `format_final_02_run.json` |
| `uv run mypy --follow-imports=skip ../scripts/verify_plan.py` | 2026-10-14T21:04:40+08:00 / 2026-10-14T21:04:40+08:00 | 0 | 1 个脚本；无类型错误 | `mypy_final_02_run.json` |

全部索引位于`reports/runs/recovery_r00_validator_20261014/`；最终完整测试日志为`final_full_tests_03.log`，CLI日志为`repository_check_02.log`。测试明确使用synthetic文档/状态，不是产品数据或金标，零网络、零付费模型调用。

验证状态：unit=passed；contract=passed（重用同一40项行为测试，不能相加成80项）；integration=not_run；security=not_run（产品安全未测，计划证据路径越界负例已在unit中）；frontend=not_run；e2e=not_run；live=not_run；manual=not_run。

## 5. 真实调用链与索引

已核实CLI `codebase-memory-mcp v0.11.0`真实存在并读help。首次索引与最终刷新使用独立project `dianzi-recovery-validator`、目录`/mnt/d/dianzi/scripts`，cache位于工作区外`/tmp/dianzi-cbm-recovery-validator-20261014`，不索引秘密、holdout或用户资料。原始结果见cbm_index_frozen.json、cbm_index_frozen_run.json、cbm_trace_load_json.json、cbm_schema.json、cbm_architecture.json；代码快照绑定见delivery_snapshot.json。

CBM inbound trace实际返回`load_json ← run_all_checks ← main ← verify_plan模块入口`（3层调用者）。源码/rg交叉核查全部读取入口：requirements、manifest、pilot_cases、state和可选baseline均通过load_json；run_all_checks实际接入check_recovery_manifest与check_task_state，没有仅被测试调用的验证能力。图仅覆盖scripts，不用于证明产品调用链；更广产品索引由主控承担。

## 6. 合同、评分与限制

没有本包自行引入新重大合同决策；按主控冻结schema实现R00校验。E1/D1/X1的计划完整性证据已增加，R00-C01/C02/C03/C05有结构证据；public schema正反样例、资源/费用授权清单、CR内容/迁移回滚和60卡切片语义覆盖由主控其他R00工作包及独立审查核对，本脚本不代签R00-C04/C06。

存在的文件只能说明证据引用可读，不能证明内容支持结论、reviewer独立性、命令真执行或八层产品验证真实。变更记录与任务映射的业务语义仍需要独立review及冻结baseline监督。产品integration/live/e2e未在本工作包执行，不据此称G-A通过。

下一步：主控提交冻结代码/合同快照，派新的独立reviewer复跑40项、实际manifest/state及关键负例，核查报告和CR内容，再决定R00状态；本工作包停在awaiting_review。

## 7. 文档修订记录

- 2026-10-14T21:07:40+08:00：r00_plan_validation首次创建，汇总实际红绿测试、静态检查、索引、重复字段纠偏依赖和未运行层。

## 8. RV-02 · R包验收遗漏能力切片的定向修复

本附录写作开始：2026-10-14T21:41:05+08:00；写作结束：2026-10-14T21:41:05+08:00。首次创建时间保持原值。本轮任务仍awaiting_review，未commit/push/登记accepted。

独立缺陷发现时间：2026-10-14T21:31:32+08:00（review原始accepted_r02_missing_slices.json）。发现者为主控派出的独立reviewer，冻结代码d752fe0c8f14dd4c35b39863cfba0d1c902fffae。输入：authority、R00/R01/R02均accepted/complete，八层passed且证据/审查文件真实存在，但110个原T切片仍pending。预期失败并指出缺失能力；实际旧validator退出0。根因：accepted R节点只核对依赖R包状态，未读取requires_slices与output_slices对应的原T.slice_acceptance，允许包级绿灯绕过能力级验收。影响R00及所有后续恢复包的依赖放行；属于阻断合同完整性缺陷。

本轮先在独立reviewer原临时副本只读复现，再新增7项行为测试。旧实现对4个消费/发布/R24切片负例退出0，其余新增证据/审查缺失负例、早期切片正例、R24部分聚合正例已有正确行为，全部保留。没有修改复现输入、manifest、state、评分门槛、金标或分母。

修复新增16行脚本：在accepted执行节点循环中分别遍历requires_slices/output_slices，通过capability_slices.original_task定位所属T的slice_acceptance，未accepted分别报STATE_RECOVERY_REQUIRED_SLICE/STATE_RECOVERY_OUTPUT_SLICE。原函数前半段已经对每个accepted T切片检查全部evidence为存在的项目内文件、review_ref有效存在；本修复复用该完整证据检查，避免另建验收真相或重复证据逻辑。R节点自身审查、完整实现、验证状态和包依赖检查继续保留。

不要求原T卡先accepted：正例中R00/R01/R02所需和输出切片均独立accepted、有真实可读合成测试证据，R20:T06仍pending，整张T06仍pending，validator退出0。此正例证明没有将T06后段安全增强反锁早期R02。R24-A/B同样从原T的A/B切片读验收，聚合R24继续由slices.A/B控制；A独立accepted、聚合partial/in_progress的正例退出0，A输出未验收和B消费A未验收都退出1。

修复代码编辑瞬间未单独打时标，历史未记录；实际修复在最终回归开始前已落地，执行时间如下。修复版本是未提交diff，hash见rv02_delivery_snapshot.json。问题状态：实现修复、自动复验通过、待独立reviewer复核；未写关闭时间或accepted。

| 命令 | 实际开始/结束（+08:00） | 退出码 | 实际结果 | run索引 |
|---|---|---:|---|---|
| `python scripts/verify_plan.py --root reports/runs/recovery_r00_review_1_20261014/temporary_copies/accepted_r02_missing_slices` | 2026-10-14T21:35:10+08:00 / 2026-10-14T21:35:11+08:00 | 0 | 独立review临时副本：错误返回PLAN_OK；缺陷复现 | `rv02_repro_before.json` |
| `python -m unittest discover -s tests/plan -p test_recovery_plan.py -v` | 2026-10-14T21:36:37+08:00 / 2026-10-14T21:36:45+08:00 | 1 | 31项，27过/4失败/0skip；4个新负例暴露RV-02 | `rv02_red_tests.json` |
| `python -m unittest discover -s tests/plan -p test_*.py -v` | 2026-10-14T21:37:35+08:00 / 2026-10-14T21:37:47+08:00 | 0 | 56项，56过/0失败/0skip；原16+恢复24+公共9+新增7全部保留 | `rv02_final_regression.json` |
| `python scripts/verify_plan.py --root reports/runs/recovery_r00_review_1_20261014/temporary_copies/accepted_r02_missing_slices` | 2026-10-14T21:38:30+08:00 / 2026-10-14T21:38:30+08:00 | 1 | 同一review临时副本：PLAN_INVALID，20项输入/输出切片未验收；预期退出1 | `rv02_repro_after.json` |
| `python scripts/verify_plan.py` | 2026-10-14T21:38:30+08:00 / 2026-10-14T21:38:30+08:00 | 0 | 当前真实manifest/state：PLAN_OK；退出0 | `rv02_repository_check.json` |
| `uv run ruff check ../scripts/verify_plan.py ../tests/plan/test_verify_plan.py ../tests/plan/test_recovery_plan.py` | 2026-10-14T21:38:27+08:00 / 2026-10-14T21:38:27+08:00 | 0 | 3文件，无诊断 | `rv02_ruff.json` |
| `uv run ruff format --check ../scripts/verify_plan.py ../tests/plan/test_verify_plan.py ../tests/plan/test_recovery_plan.py` | 2026-10-14T21:38:27+08:00 / 2026-10-14T21:38:27+08:00 | 0 | 3文件，格式一致 | `rv02_format.json` |
| `uv run mypy --follow-imports=skip ../scripts/verify_plan.py` | 2026-10-14T21:38:27+08:00 / 2026-10-14T21:38:28+08:00 | 0 | 1脚本，无类型错误 | `rv02_mypy.json` |
| `WSL codebase-memory-mcp v0.11.0 cli --json index_repository --repo-path /mnt/d/dianzi/scripts --name dianzi-recovery-validator --mode fast` | 2026-10-14T21:39:25+08:00 / 2026-10-14T21:39:32+08:00 | 0 | scripts安全窄索引刷新；cache工作区外 | `rv02_cbm_index_after_run.json` |

全部run索引/原始日志位于reports/runs/recovery_r00_validator_20261014/。最终回归stdout为rv02_final_regression.log，56项是49个既有+7新增，不能把多次复跑数量相加。复现后日志rv02_repro_after.log实际列出20项缺失切片，当前repo仍PLAN_OK，证明修复阻止错误accepted而不把当前awaiting_review误判失效。

CBM修改前refresh/inbound trace记录于rv02_cbm_index_before.json/rv02_cbm_trace.json，实际链为check_task_state←run_all_checks←main←模块入口；rg/源码交叉核查只此共享状态校验函数承担CLI验证。修改后独立窄索引刷新见rv02_cbm_index_after.json，对应精确代码hash见rv02_delivery_snapshot.json，cache未提交。

改动范围：scripts/verify_plan.py、tests/plan/test_recovery_plan.py、本报告与本run目录新增证据；tests/plan/test_verify_plan.py未修改，公共9项合同回归未改。复用标准库和已有slice证据检查，无新依赖。主控的.gitattributes/冻结字节纠偏与本修复分离，本文未代修或验收RV-01。

新限制：accepted R包必须在原T状态中具有可追溯的消费与发布切片验收，否则失败；独立准备和awaiting_review状态未被升级为accepted的强门，仍按既有合同调度。review_ref存在不证明评审者独立、内容支持或日志真执行，该语义核对仍由独立reviewer承担。产品integration/security/frontend/e2e/live/manual保持not_run，本修复没有产品live结果。

文档修订：2026-10-14T21:41:05+08:00，r00_plan_validation补RV-02复现、最小修复、56项回归和未提交hash，保留原首次创建时间、历史失败及原验证记录；结束时刻2026-10-14T21:41:05+08:00。
