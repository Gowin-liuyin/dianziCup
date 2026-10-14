# T01 验收检查表（实际执行记录）

执行时间：2026-09-30 20:33—20:45（本地时区）｜解释器：`E:\miniconda\python.exe`（Python 3.13.11，仅运行标准库脚本，不修改应用运行时 Python 3.12 合同）｜工作目录：`D:\dianzi`

主检查：`python scripts/verify_plan.py`（T01 建立，本次已实际运行）。正例针对真实合同；负例只改独立临时副本（tempfile），不修改正式合同、不动用同一份基线做“改目标又改基线”的自证。

## 最低验收案例（任务卡 §5）

| ID | 输入/场景 | 必须检查的结果 | 实际执行与观察 | 判定 | 证据 |
|---|---|---|---|---|---|
| T01-C01 | 完整评分表 | 初赛100、决赛100，11个决赛评分项全部映射 | 正例：`verify_plan.py --root D:\dianzi` → PLAN_OK（含 REQ_PRELIM_TOTAL/REQ_FINAL_TOTAL/REQ_FINAL_MISSING 检查）。官方PDF核对：`reports/runs/t01_pdftotext_extract.txt`（pdftotext 退出码 0）逐行比对评分表。负例：`test_prelim_total_mismatch_fails`（临时副本把 F1 初赛 15→14）→ 退出非零、报 REQ_PRELIM_TOTAL | 通过 | `reports/runs/t01_verify_plan.log`、`reports/runs/t01_unittest.log`、`reports/tasks/T01.md` §评分核对 |
| T01-C02 | 一条评分项没有任务 | 校验失败并指出编号 | `test_missing_requirement_task_mapping_fails`：临时副本清空 F3 的实现/验收映射 → 退出非零，输出含 “F3” 与 REQ_NO_IMPL_TASK/REQ_NO_ACCEPTANCE_TASK | 通过 | `reports/runs/t01_unittest.log` |
| T01-C03 | 任务依赖不存在或循环 | 校验失败而不是跳过 | `test_missing_dependency_fails`（T05→T99 不存在）→ 指出 T99；`test_dependency_cycle_fails`（T00→…→T59→T00 成环）→ 报 DEP_CYCLE 并给出环路径；`test_execution_order_violation_fails`（T18/T17 对调）→ 报 ORDER_RULE/DEP_ORDER | 通过 | 同上 |
| T01-C04 | 合成案例 | 标记、来源和预期字段完整且与真实事件分开 | 正例：20 个案例全部 `is_synthetic=true`、`SYN-` 前缀、`source_kind=synthetic`、含 input/expected_result/expected_basis/covers_*，不使用真实 CVE 编号，独立存放 `fixtures/synthetic/`。负例：`test_unmarked_synthetic_case_fails`（is_synthetic=false）→ 指出 SYN-REV-001；`test_missing_case_field_fails`（删 expected_basis）→ 指出案例与字段名 | 通过 | 同上；`fixtures/synthetic/pilot_cases.json` |
| T01-C05 | 有测试目标却没有结果 | 状态为 not_run 而非 passed | `test_passed_without_evidence_fails`（T01 标 unit=passed 但无证据）→ 报 EVIDENCE_MISSING 指出 T01；`test_unknown_verification_enum_fails`（verification.live=blocked_live）→ 报 STATE_ENUM 指出越界值。实际运行中该机制两次拦截本 Agent 自身（证据文件未落库前、映射不一致时），未静默通过。未来任务状态保持 pending/not_started、验证 not_run | 通过 | 同上；`progress/task_state.json` |
| T01-C06 | 改变官方门槛或删除困难案例 | 需要变更单且不能静默进入正式合同 | 基线另存 `contracts/baselines/plan_baseline_t01.json`（--write-baseline，先要求无校验失败）。负例分三次、各自独立临时副本、基线文件不随目标一起改：`test_baseline_detects_threshold_change`（F1 决赛 10→12）→ BASELINE_THRESHOLD_CHANGED 指出 F1；`test_baseline_detects_removed_case`（删 SYN-REV-001）→ BASELINE_CASE_DELETED；`test_baseline_detects_deleted_invariant`（删 INV-P3-no-5s-in-excellent）→ BASELINE_INV_DELETED。基线比对正例（未改动）→ PLAN_OK | 通过 | 同上；`contracts/baselines/plan_baseline_t01.json` |

## 测试汇总

| 项 | 值 |
|---|---|
| 命令 | `python -m unittest discover -s tests/plan -v`（cwd=`D:\dianzi`） |
| 解释器 | E:\miniconda\python.exe（Python 3.13.11） |
| 开始/结束 | 2026-09-30 20:38:53 / 20:39:12（首轮12例）；20:40 复跑13例 |
| 测试数 | 13（1 正例 + 12 负例/边界） |
| 失败/跳过 | 0 / 0 |
| 退出码 | 0 |
| 日志 | `reports/runs/t01_unittest.log` |

主检查命令（每条含工作目录、退出码、日志，见 `reports/tasks/T01.md` 命令表）：

1. `python scripts/verify_plan.py --root D:\dianzi`（修复双向映射13处不一致后 PLAN_OK，退出码 0）
2. `python scripts/verify_plan.py --root D:\dianzi --write-baseline contracts/baselines/plan_baseline_t01.json`（BASELINE_WRITTEN，退出码 0）
3. `python scripts/verify_plan.py --root D:\dianzi --baseline contracts/baselines/plan_baseline_t01.json`（本文件落库后 PLAN_OK，退出码 0）

## 边界与范围限制

- 本检查只证明计划合同的结构与规则被校验：不证明真实富化准确率、问答质量、租户隔离、FOFA 观察或监测性能通过；产品级验证属于 T45+ 的对应任务。
- 20 个合成案例的预期结果均为 Agent 起草的**待复核提案**（`review_state=待复核提案`），不是人工确认金标；人工核验前不得用于正式评分或盲测。
- 评分数字核对依据官方 PDF 文本提取与未修改的原始合同（`docs/plan/01_scope_and_scoring.md`）；脚本不能证明官方文本解释与人工裁决一定正确。
- 负例全部运行在临时目录；正式 `contracts/`、`fixtures/` 未被用于演示失败而改动。
- 尚无产品测试（backend/frontend 未创建）：unit 仅含计划校验器行为测试；integration/live = not_run。

## 结论

T01-C01—C06 全部有实际输入、可观察断言与日志；T01 自检通过，状态置 awaiting_review，等待独立评审（不自置 accepted）。
