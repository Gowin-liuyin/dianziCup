# 批次21 C5.3 · R19 标注工具与开发集基础设施 —— 实现方案（只读调研产物）

- 调研时间：2026-10-25T00:40:28+08:00 开始，本方案落盘 2026-10-25T00:43:09+08:00
- 仓库：D:\dianzi，分支 codex/full-delivery-recovery，HEAD `ee283de3e`；工作区含 batch21 既有未提交改动（docs/decisions 三份 CR、reports/runs 多目录、scripts/dev_integration_container.py 等），本次调研未触碰
- 方法：只读 grep/read/ls/python -c 检查 JSON；未运行 pytest，未改任何业务文件，未做改变 git 状态的操作
- 本文允许写：仅本文件（reports/runs/batch21_r19_r21_research/r19_plan.md）；配对文件 r21_plan.md 同目录

---

## 1. 权威输入与任务卡摘录

| 依据 | 位置 | 关键条款 |
|---|---|---|
| 阶段 G-F | docs/plan/00_execution_map.md:155 | `G-F = R19 → R20 → R21`；:160 "R19工具/候选在R04真实闭环独立通过后，正式冻结依赖完整覆盖+双人核验" |
| R19 恢复卡 | docs/plan/12_recovery_task_cards_20261014.md:213-221 | 输入→输出："真实原文及家族/时间分组 → 版本化dev/holdout、双人核验记录、裁决与冻结manifest"（:217）；"无人工复核仅能标awaiting_human_label"（:219）；核验①事件家族不跨split②holdout不入检索/提示③双人独立与裁决可追溯④缺项不从分母消失⑤修订金标需变更理由⑥许可/hash/时间快照齐全（:220）；"候选题数量不等于金标题数量"（:221） |
| T46 原卡 | docs/tasks/T46_benchmark_dataset.md | 修改边界：`benchmarks/`、`scripts/annotation/`、`contracts/schemas/`、`reports/acceptance/`、`reports/tasks/`（:22）；目标产物：`benchmarks/manifests/`、`scripts/annotation/`、`reports/acceptance/dataset.md`、`reports/tasks/T46.md`（:26）；实施 6 步（:32-42，含 :36 dev/demo/holdout 划分、:42 "人工未完成时输出待标注清单，不宣称已有金标"）；最低验收 C01–C06（:50-55） |
| T01 既有授权面 | reports/tasks/T01.md:10 | T01 卡曾允许 `benchmarks/dev/`、`fixtures/synthetic/`；现 repo 无 benchmarks/dev/ 目录 |
| 数据集合同 | docs/plan/06_testing_and_evaluation.md:37-51 | 规模区间先"20—30起事件和20题验证标注规则"（:39）；字段组织 `case_id, event_family_id, data_kind, split, source_refs, source_snapshot_time, input_refs, expected_claims, expected_status, annotators, adjudication, license`（:41）；开发示例只用 dev/demo、holdout 答案隔离（:43）；同事件译文/转载/修订/派生题整体分组（:45）；"没有人工可用时完成标注工具和候选集，状态awaiting_human_label，不宣称金标已完成"（:51） |
| 硬约束 | 用户本批指令 + AGENTS.md §6 | 不产出任何金标；没有人工标注就如实保持 0 gold；工具就绪本身如实记录 |

## 2. 现状盘点（全部 file:line 实证）

### 2.1 标注工具切片已存在且为 awaiting_review（未 accepted）

- CLI `scripts/annotation/prepare.py`（570 行，docstring 即"never freezes gold labels"，prepare.py:1）。四个 action `validate/import/export/scan`（prepare.py:491）。
- 候选校验 `validate_candidates`（prepare.py:112-194）：重复 case 拒绝（:121-123）；synthetic 必须 `source_kind=="fixture"` 且 URI `urn:synthetic:`、real 必须 https 公开来源（:136-149）；证据 quote_sha256/offset/locator/来源关联校验（:151-175）；家族/alias/document_id/URI 同一键域跨 split 拒绝 `FAMILY_SPLIT_LEAK`（:186-189）；`candidate_sha256` 绑定（:190-193）。
- 标注状态机 `inspect_annotations`（prepare.py:197-295）：四状态 awaiting_human_label / awaiting_adjudication / awaiting_identity_verification / ready_for_manual_review（:201-206）；恰好两位标注人（:250-251）；裁决/身份记录 hash 绑定与第三人约束（:263-284）；修订链 revision+previous_sha256+change_reason（:228-239）。上限即 ready_for_manual_review，永远不判金标。
- 汇总 `summarize`（prepare.py:307-323）：`human_gold_count: 0` 硬编码（:317）；`formal_evaluation: {status: "not_run", numerator: null, denominator: null}`（:318-322）。
- holdout/标签隔离：标注与 holdout 输入/输出强制仓外 `require_external`（prepare.py:353-357），读取 git worktree 注册表判定仓内根（:326-350）；holdout 或带 annotations 的输入必须仓外（:507-509）；标签只能 annotation 目的导出，拒绝 prompt/index/image/fixture（:537-538）；holdout 只能 annotation 导出（:541-542）；泄漏扫描 `scan_leaks`（:441-486）只扫操作者选定公开树、命中不打印答案（:446, :485-486）。
- 原子独占写 `write_new`（prepare.py:393-438）：目标存在拒绝、pending 文件、fsync。
- Schema `benchmarks/schemas/candidate_case_v1.json`：split 枚举 dev/demo/holdout（:38）；data_kind 枚举 real/synthetic/redacted/replay（:38）；`label_status` 常量 `awaiting_human_label`（:52）；label 结构 expected_claims/expected_conditions/expected_status 仅存在于 annotation_bundle（:62-67）；annotation_bundle 含 data_mode human/fixture、双人记录、裁决、身份核验（:68-85）。
- 真实候选 manifest `benchmarks/manifests/r19_public_dev_candidate_v1.json`：1 个 real/dev 候选（vLLM GHSA-6cxc-2vcg-w5qc 包名短证据），`label_status: "awaiting_human_label"`（:66），license unknown/redistribution unverified（:35-41），limitations 明示 0 人工标签（:61-65）。
- 测试：`scripts/annotation/tests/` 四文件共 2813 行（test_prepare.py 655、test_prepare_fix1.py 358、test_crash_recovery.py 426、test_fd_metadata_error.py 177）；历史实跑 27+13=40 tests exit 0（reports/tasks/R19-preparation.md:44、reports/tasks/R19-preparation-fix1.md 命令表）。
- Runbook `docs/runbooks/annotation_preparation.md`：人工最短核验清单、仓外目录合同、scan 用法、"只有 unknown/conflict 等短状态仍需人工检查"的边界声明。
- 历史报告：reports/tasks/R19-preparation.md（状态 awaiting_review）、R19-preparation-fix1.md（三个审查阻断修复）、R19-root-cli-timeout-diagnosis.md（CLI 冷启动成本：jsonschema/rfc3987/lark 导入 1.6-1.9s 量级，测试组须拆分不合并进 60s deadline）。
- 该切片在主库的状态：主库含 prepare.py+schema+manifest+tests（本次 ls 实证）；批次时间线未登记其 accepted，主状态仍 partial。

### 2.2 存储：无任何标注/开发集 DB 表

- backend/migrations/versions/ 共 32 个迁移（0001–0031），grep `annotation|benchmark|dev_set` 仅命中 `from __future__ import annotations`，0 张业务表。标注记录按设计放仓外受控文件（runbook、prepare.py:353-357），PostgreSQL 只做产品事实权威（AGENTS.md §5）。开发集装配物同理为版本化 JSON 文件，不建第二套任务真相。

### 2.3 可作 dev-set 种子的现有数据

| 种子 | 位置 | 形状差距 |
|---|---|---|
| 1 个 real/dev 候选 | benchmarks/manifests/r19_public_dev_candidate_v1.json | 已符合 candidate_case_v1，可直接作装配输入 |
| 20 个合成案例 | fixtures/synthetic/pilot_cases.json（20 cases，如 SYN-REV-001） | T01 时代形状：`data_kind:"revision"` 等旧值域、`expected_result`/`expected_basis`/`review_state:"待复核提案"`；无 event_family_id/source_refs/evidence span；**不符合 candidate_case_v1** |
| 规划区间 | docs/plan/06_testing_and_evaluation.md:39 | "先用20—30起事件和20题验证标注规则"，20 个合成种子正落在验证规模；150 起/200 题是资源规划非官方要求 |

关键事实：pilot_cases 的 `expected_result` 是规则推导的"待复核提案"（pilot_cases.json `review_state` 字段），**不是金标**；适配时绝不能转成任何 label 字段。

### 2.4 缺口清单（C5.3 需补的"开发集基础设施"）

1. 无 dev-set 级 manifest：bundle（candidate_case_v1 bundle）→ 版本化开发集的装配物（计数、hash、0 gold 声明、种子溯源）不存在。
2. 无 synthetic 种子适配器：pilot_cases.json 无法通过现有 `validate_candidates`（需 event_family_id/source_refs/evidence≥1，schema :34-53）。
3. 无装配 CLI 与跨 bundle 家族隔离校验（现有 validate_candidates 是单 bundle 检查，prepare.py:112；跨 bundle 的 FAMILY_SPLIT_LEAK 需装配层合并后复检）。
4. （人工侧，非本批）真实双人标注、裁决、身份核验、真实 holdout 集、冻结签字——仓外人工事项。

## 3. 最小实现路径（步骤 A–E，全部离线可完成，不产金标）

设计总原则：
- **不修改**已 awaiting_review 的 prepare.py 既有逻辑与已冻结 candidate_case_v1 schema，避免重开审查面；新逻辑全部放新文件，函数级复用 `from scripts.annotation.prepare import ...`（prepare.py 自身已把 ROOT 插入 sys.path，prepare.py:19-20，同包导入成立）。
- 新 schema 是 R19 本地装配格式，先例：R19-preparation.md:9 "新增 schema 是 R19 本地候选准备格式，未改冻结公共合同"。T46 原卡虽允许 contracts/schemas/（T46:22），最小路径不碰公共合同目录。
- 每步先定输入输出与负例，再实现；测试独立成文件（吸取 R19-root-cli-timeout-diagnosis 的分组教训）。

### 步骤 A · dev-set manifest schema（新文件 `benchmarks/schemas/dev_set_manifest_v1.json`）

字段（对齐 06_testing:41 的字段组织意图，全部为候选级、无 expected_*）：
- `schema_version: const 1`；`dev_set_id`；`assembled_at`（+08:00 秒级，复用 candidate_case_v1 的 time 定义模式，schema:8）。
- `source_bundles[]`：每项 `{path(仓内相对), candidate_sha256, case_count, data_kind_counts}` —— 溯源到已校验 bundle 的 hash。
- `cases[]`：内嵌候选 case（逐项符合 candidate_case_v1 的 candidate_case 定义，schema 引用其 $defs）或仅 `minItems 1`（种子非空：1 real + 20 synthetic）。
- `counts`：`by_data_kind`（real/synthetic/redacted/replay 分列）、`by_split`（dev/demo 分列）——synthetic 与 real 分开计数（T46-C03，T46:52）。
- `label_status_counts`：恒全 `awaiting_human_label`（C5.3 批内无标签输入）。
- `gold` 块（0 gold 的机读表达）：`{human_gold_count: const 0, gold_status: const "none_no_human_labels", formal_evaluation: {status: const "not_run", numerator: null, denominator: null}}` —— 与 prepare.py:317-322 同构。
- `dev_set_sha256`：绑定 cases+counts payload（digest 规则与 prepare.py:61-66 一致）。
- `scale_statement`：固定字符串声明"候选/种子规模，awaiting_human_label，非正式指标，不是金标"。

### 步骤 B · synthetic 种子适配器（新文件 `scripts/annotation/build_synthetic_seed.py`）

- 输入：`fixtures/synthetic/pilot_cases.json`（只读）。
- 映射：全部 `data_kind: "synthetic"`（旧值域 revision 等降级写入 limitations 文本保留可追溯）；`source_kind: "fixture"` + `uri: "urn:synthetic:<case_id>"`（满足 prepare.py:136-140）；`event_family_id` 由 case 前缀推导稳定家族（修订/派生题同家族同 split，满足 T46-C01）；evidence span 取 synthetic 输入 JSON 规范化文本的精确子串，quote_sha256/offset/locator_kind=json_pointer 全部可离线计算（schema :22-30 必填项）。
- `candidate_origin: "model_assisted"`（沿用 R19-preparation.md:61 的明示先例）；`candidate_task` 只写场景任务（scenario 字段），**不复制 expected_result/expected_basis 值**；limitations 指回 pilot_cases.json 原 case_id，声明"T01 时代预期提案存在且仅待人工复核参照，不是金标，模型不充当唯一出题人与裁判"（T46:34"不默认模型即真值"）。
- 输出：`benchmarks/manifests/r19_synthetic_dev_seed_v1.json`（独占新建，复用 prepare.write_new 原子写）。
- 产物必须能通过现有 `prepare.py validate --input ...` exit 0——这是最硬的互操作回归。

### 步骤 C · 装配 CLI（新文件 `scripts/annotation/assemble_dev_set.py`）

- 输入：`--bundle`（可多次）已校验 candidate bundle + `--output` dev-set manifest 路径。
- 行为：
  1. 逐 bundle 跑 `prepare.validate_candidates`（复用，不重写）；
  2. 合并全部 cases 后做**跨 bundle** 家族/alias/document_id/URI 键域 split 一致性复检（现 validate_candidates 的 split_by_identity 是单次调用内积累，跨 bundle 需装配层重跑同规则）；
  3. 拒绝 `split=="holdout"` 的 bundle 输入——holdout 永不进仓内 dev-set manifest（T46:36、06_testing:43 隔离意图；holdout 候选继续走 prepare.py 仓外通道）；
  4. 拒绝任何 `label_status != "awaiting_human_label"` 的 case（金标不进装配物）；
  5. 生成 counts/label_status_counts/gold 块，写 dev_set_sha256，原子独占输出（复用 write_new）；
  6. stdout 只打印计数与状态（对齐 prepare.py:552 的无泄漏输出风格）。
- 可选 `--scan-root`：装配后对 dev-set 内容跑 `scan_leaks` 复用（防种子文案意外携带 holdout 家族字符串）。

### 步骤 D · 直属测试（新文件 `scripts/annotation/tests/test_dev_set_assembly.py`）

unittest 显式 synthetic fixture（同目录先例风格），预计 <20s 单组可完成：

| # | 用例 | 断言 |
|---|---|---|
| 1 | 1 real bundle + 1 synthetic seed 合法装配 | exit 0；counts real=1/synthetic=20 分列；label_status_counts 全 awaiting；gold.human_gold_count==0；formal_evaluation.status=="not_run" |
| 2 | 跨 bundle FAMILY_SPLIT_LEAK：synthetic 案例的 family alias 改为 real bundle 的来源 URI/家族 | exit 2，固定错误码，输出不创建 |
| 3 | 手改临时副本 gold.human_gold_count=1 | schema/校验拒绝（负例只改临时副本） |
| 4 | 混入 label_status 非 awaiting 的 case | 拒绝 |
| 5 | bundle 被篡改但 candidate_sha256 未更新 | 拒绝（CANDIDATE_HASH_MISMATCH 传递） |
| 6 | holdout split 的 bundle 作输入 | 拒绝 |
| 7 | 同输入两次装配 | dev_set_sha256 确定（装配无随机，无随机种子需求） |
| 8 | 重复 case_id / 空输入 / 输出已存在 | 分别拒绝 |
| 9 | synthetic seed 产物通过 prepare.py validate | exit 0（互操作） |
| 10 | 缺 license/snapshot 的构造 case 进装配 | 拒绝（T46-C05 传递） |

运行命令（与既有 40 例分组，不合并进同一条 60s deadline，R19-root-cli-timeout-diagnosis 结论）：
`python -m unittest discover -s scripts/annotation/tests -p "test_dev_set_assembly.py" -v`（宿主 `.venv`）。

### 步骤 E · 文档与记录

- `docs/runbooks/annotation_preparation.md` 追加"开发集装配"节（命令、0 gold 声明、holdout 不进装配、种子溯源）。
- `reports/acceptance/dataset.md` 按 T46:26 建立骨架：如实记录"工具就绪、装配物 1 real + 20 synthetic 种子、0 gold、0 真人标签、正式指标 not_run"。
- 任务报告 + progress 状态按 AGENTS §3（awaiting_review，不自行 accepted）。

## 4. "0 gold" 的表达方式汇总（多层一致）

| 层 | 机制 | 证据 |
|---|---|---|
| schema | `label_status` 常量 awaiting_human_label，候选 schema 无 expected_* 字段 | benchmarks/schemas/candidate_case_v1.json:34-53（:52） |
| 工具 | summarize `human_gold_count: 0` + `formal_evaluation not_run/null` | scripts/annotation/prepare.py:317-322 |
| 装配（本批新增） | dev_set manifest `gold` 块三常量 + 装配器拒绝带标签 case + 测试 1/3 断言 | 本方案步骤 A/C/D |
| 标注记录 | 人工标签走仓外 annotation_bundle，工具上限 ready_for_manual_review | prepare.py:197-295、runbook |
| 状态 | T46 pending、整 R19 partial 不改绿；报告写"工具就绪"非"金标就绪" | AGENTS.md §3、progress/task_state.json T46 |

## 5. T46-C01–C06 验收映射（本批可达性）

| ID | 要求（T46:50-55） | 现状 | 本批动作 | 本批可达 |
|---|---|---|---|---|
| C01 | 同事件多语言/修订/题目同 split | prepare.py:186-189 + fix1 扩展测试 | 装配层跨 bundle 复检 + 测试 2 | 是（fixture 级行为） |
| C02 | 双人标签不一致进裁决 | inspect_annotations awaiting_adjudication（prepare.py:285-288）+ synthetic 双填表测试已有 | 无新增 | 工具行为是；**真人验收不可达**（见 §6） |
| C03 | 合成与真实 data_kind/来源分离 | SYNTHETIC_PROVENANCE_REQUIRED（prepare.py:136-140） | 装配 counts 分列 + 测试 1 | 是 |
| C04 | holdout 入 prompt/镜像 → 泄漏检查失败 | scan_leaks + LABEL/HOLDOUT_EXPORT_REFUSED（prepare.py:537-542） | 装配器拒绝 holdout 输入 + 可选复扫 | 是（局部扫描边界如实声明，runbook 已有） |
| C05 | 缺来源/许可/观察时间 → 校验失败或显式 unknown | schema required + provenance/time 校验 | 测试 10 传递 | 是 |
| C06 | 人工未完成 → awaiting_human_label，不生成实测准确率 | summarize（prepare.py:317-322） | gold 块继承 + 测试 1 | 是 |

## 6. 本批不可达成的验收（如实入 OQ 的内容）

1. **真实双人独立标注、分歧裁决与身份核验**（T46-C02 的真人半边、R19 卡"双人核验记录、裁决"12_recovery:217）：需要两名真实标注人、第三裁决人、身份核验证据；本批无该输入。工具侧（含 fixture 模式状态机）已就绪并被 40 例覆盖。最小所需输入：负责人登记的两位标注人身份与独立提交安排、仓外标注目录、利益冲突核查。
2. **冻结 manifest 与签字**（R19 卡"冻结manifest"、:221"独立复核和冻结签字"）：冻结以完整覆盖+双人核验为前置（00_execution_map.md:160）；0 gold 下只能冻结"候选集 awaiting_human_label"，不能冻结金标集，且签字属独立审查者。本批不产冻结 manifest。
3. **真实规模扩展**（06:39 规划区间）：真实候选扩充依赖 R07–R16 能力输出与真实采集；本批只有 1 real + 20 synthetic 种子，如实记录规模。
4. **实际镜像/索引输入的泄漏检查**：现有 scan 只查显式公开树不解压镜像（runbook 末节）；正式冻结前的镜像/索引审计不在本批。

## 7. 本批不做清单

- 不修改 `scripts/annotation/prepare.py` 既有 570 行与 `benchmarks/schemas/candidate_case_v1.json`（只新增文件）。
- 不新建任何 DB 表/迁移（标注与开发集保持版本化文件；PG 不建第二套真相）。
- 不产出任何金标、不把 pilot_cases 的 expected_result 提案转为标签或任务答案。
- 不触碰 `contracts/schemas/` 公共合同、backend、认证、指标分母/阈值。
- 不读取、不创建真实 holdout 与真实答案目录。
- 不做真实标注、裁决、身份核验、冻结签字（OQ 记录）。
- 不运行 pytest 之外的探索性执行；批内实现时只跑新增测试组 + 既有 annotation 组 + 计划回归。

## 8. 依赖与交接

- C5.3 产物（dev-set manifest，0 gold）是 C5.4 评测 harness 的输入；两步可在同批顺序执行，harness 在无 dev-set 时须显式 blocked 而非空跑（对齐 r21_plan.md §3.1）。
- 最小交付一句话：**在不动已审切片与公共合同的前提下，新增 dev-set manifest schema + synthetic 种子适配 + 装配 CLI + 直属测试，交付"工具就绪、1 real + 20 synthetic 种子、0 gold"的版本化开发集基础设施；真实双人标注/裁决/冻结本批不可达，如实入 OQ。**

---

- 文档首次创建时间：2026-10-25T00:43:09+08:00
- 最后更新时间：2026-10-25T00:43:09+08:00
- 调研开始时间戳：2026-10-25T00:40:28+08:00（date +%Y-%m-%dT%H:%M:%S%z 原始输出 2026-10-25T00:40:28+0800）
