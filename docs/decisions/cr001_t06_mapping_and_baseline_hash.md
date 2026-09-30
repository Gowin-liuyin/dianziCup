# CR-001 · T06 评分映射修正与基线 source_hashes 比对（FIX-T01）

状态：proposed（变更单待人工确认；下述修复由 FIX-T01 修复指令授权并于 2026-09-30 实施完毕，本单不追认任何未授权范围）
提出者/日期：FIX-T01 修复者 Agent（非 T01 原实现者、非 R-T01 审查者）/ 2026-09-30
关联任务：T01 修复（附录见 `reports/tasks/T01.md`）；缺陷来源 `reports/reviews/R-T01.md`（P-1、P-2、负例 N10）与 `reports/reviews/R-T01_runs.log` [6][8]
性质：公共合同变更（映射修正）+ 校验器行为增强。**不是**分值/门槛/分母/不变量/案例 ID/金标变更。

## 原合同与问题

### P-1：F1↔T06 双向映射残留（必须修复）

- 事实：`contracts/task_manifest.json` 中 `T06` 的 `requirements` 为 ["F1","F3","E1","X1"]，且 `contracts/requirements.json` 中 F1 的 `implementation_tasks` 含 "T06"（双向映射）。
- 权威来源（两条一致，均不含 F1）：
  - `docs/plan/00_execution_map.md` §8 任务表第 76 行：`| `T06` | 用户认证、租户权限与审计基础 | T05 | E1、F3、X1 |`
  - `docs/tasks/T06_authentication_and_scope.md` 任务卡头部第 4 行：`阶段：G1｜前置：T05｜评分/要求：E1、F3、X1`
- 依据次序：执行索引规定 manifest 与任务卡不一致时以任务卡为准并报告；`task_manifest.json` 自带 note 亦要求「manifest与任务卡不一致时停止并报告」。
- 证据：R-T01 §4/§10 P-1、`reports/reviews/R-T01_runs.log` [6]（60 卡对比，1 处不一致：T06）；`reports/tasks/T01.md` 原称「60 任务映射一致」不成立（见修复附录更正）。

### P-2：`compare_baseline` 不比对已冻结的 source_hashes（同批修复）

- 事实：基线 `contracts/baselines/plan_baseline_t01.json` 冻结了 `source_hashes`（三个合同文件 SHA-256），但 `scripts/verify_plan.py` 的 `compare_baseline` 只比对 `thresholds` / `contract_invariants` / `frozen_case_ids`，从不比对 `source_hashes`。
- 后果（R-T01 负例 N10 实测）：同 ID 篡改 `SYN-REV-001.expected_result` 内容（案例集合不变）后 `--baseline` 仍 exit 0 / PLAN_OK；同理修改 `task_manifest.json` 也逃逸。案例内容与任务映射改动落在「防静默篡改」范围之外。

## 最小变更与备选

### 逐项旧 → 新

| # | 文件（位置） | 旧值 | 新值 |
|---|---|---|---|
| 1 | `contracts/task_manifest.json`（T06 行，原第 32 行 `requirements`） | ["F1", "F3", "E1", "X1"] | ["E1", "F3", "X1"] |
| 2 | `contracts/requirements.json`（F1 条目 `implementation_tasks`，原第 31 行） | ["T01","T04","T05","T06","T07","T08","T09","T10","T11","T12","T13","T14","T15","T16","T17","T35","T36","T37","T40","T41","T44"]（21 项） | 同左仅移除 "T06"，余 20 项逐一保持不动 |
| 3 | `scripts/verify_plan.py`（P-2） | `compare_baseline` 不比对 source_hashes | 新增 `check_source_hashes(baseline, contract_paths)`：对 `baseline["source_hashes"]` 每个相对路径重算当前文件 SHA-256 并比对；不一致输出 `BASELINE_SOURCE_HASH_CHANGED: <path> <旧哈希> -> <新哈希>，需变更单`；缺失条目或文件不可读输出 `BASELINE_SOURCE_HASH_MISSING`。`compare_baseline` 签名最小扩展 `contract_paths: dict[str, Path]`，入口先执行该检查；`run_all_checks` 调用处传入 `contract_paths`。标准库、小函数、docstring 风格（AGENTS.md §4）。 |
| 4 | `tests/plan/test_verify_plan.py` | 13 个测试 | 追加 3 个测试（13→16）：`test_baseline_detects_case_content_change_with_same_id`（复现 N10）、`test_baseline_detects_task_manifest_change`、`test_baseline_passes_on_unchanged_copy`。原 13 个测试与断言未删改、未放宽。 |
| 5 | `contracts/baselines/plan_baseline_t01.json` | source_hashes 旧三值 | 经 `--write-baseline` 刷新为新三值（见下表）；其余五项未变（见下证明） |

未改动：其余 59 张任务卡的映射、任何任务的 `requirements`（除 T06 外）、F1 的 `acceptance_tasks`（["T52","T54","T58"] 不含 T06，无需改）、全部分值/门槛/不变量/案例/`fixtures/synthetic/pilot_cases.json` 文件本体、`progress/`、`reports/reviews/`、`docs/plan/`、`docs/tasks/`、`AGENTS.md`。

### 备选与未采用原因

- 备选 A：保留 F1↔T06 映射、先走变更记录论证其成立——未采用：任务卡与 §8 两条权威来源均不含 F1，映射无来源支撑；执行索引规定以任务卡为准。
- 备选 B：删除基线 `source_hashes` 字段并在 purpose 明示冻结范围——未采用：会削弱防静默篡改能力，且 R-T01 P-2 首选修复即为真正比对 source_hashes。

### 基线 source_hashes 旧 → 新（三值）

| 相对路径 | 旧 SHA-256（R-T01 与本次刷新前实测一致） | 新 SHA-256 |
|---|---|---|
| `contracts/requirements.json` | 2411f1a4c31c1a78b4011f3e59019412e4ff26b9d52e40e6ebda6fe0159168b9 | 8757ddc0db3cb219403037f21f7dbe1667e58b91d7be84724b41334ce871ca97 |
| `contracts/task_manifest.json` | 0cb8275e9d1913f293a167e1b8ce3eb1337b6382c36564c8b7f087ab725e6e22 | cfdc74b188c0ff1e30b975f883847db20bbb15e815880bb6d1a404c678256b99 |
| `fixtures/synthetic/pilot_cases.json` | 8686ba8db7793e5ac59cab339e61ea8b0bfd4e85ecd65e9f657c2d4ade0b990d | 8686ba8db7793e5ac59cab339e61ea8b0bfd4e85ecd65e9f657c2d4ade0b990d（不变，冻结案例文件未改） |

### thresholds / contract_invariants / frozen_case_ids 未变的证明

方法：`--write-baseline` 前（21:29:1x—21:29:3x）与后（21:35:33.268—21:35:33.268）分别对基线各顶层键做规范 JSON 序列化（`json.dumps(..., ensure_ascii=False, sort_keys=True)`）后取 SHA-256，逐项比对。旧值于刷新前实测留存，新值为刷新后实测；脚本只读（`reports/runs/fix_t01_verify_plan.log` [2][4]，退出码 0）。

| 顶层键 | 刷新前 SHA-256 | 刷新后 SHA-256 | 判定 |
|---|---|---|---|
| thresholds | 7b5dfcca7e61f7e22976c9111f006f3213a1f4929298fa72f28d9d7a39d0f1bd | 同左 | UNCHANGED（逐字节） |
| contract_invariants | 143ce95ac8fba749227d4a3b5d64d6b133c1aa55fd42901cc2822a1ad57812b4 | 同左 | UNCHANGED（逐字节） |
| frozen_case_ids | 644a41a6379bf878b61836d47a227f0fce0a1faab736c9898b83407817919b03 | 同左 | UNCHANGED（逐字节） |
| source_hashes | f2951ac17440c6a3c3183752bcb1d9eec799a93211c6390a5996dc8f87ef3b84 | 14134e4128822d8048b8a3df72cf97e4185a4c7ab8a65c60c9b0b777763188a4 | CHANGED（预期，见上表） |
| purpose | 462c11c664351f4881448f5c11b83e2fb4db6dc2001c8fe70baf421dea408021 | 同左 | UNCHANGED（逐字节） |
| schema_version | 6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b | 同左 | UNCHANGED（逐字节） |

结论：`--write-baseline` 仅更新 `source_hashes`，thresholds / contract_invariants / frozen_case_ids 三项（及 purpose、schema_version）逐字节未变，无越界改写；顶层键集合仍为 6 项，无新增/删除键。

## 影响

- 评分要求：F1 的实现任务清单由 21 项减为 20 项（虚增项移除），不改任何分值、档位、门槛、分母；F1 证据链（T52/T54/T58 验收）不变。
- 合同与任务依赖：T06 的 `depends_on`（T05）、stage（G1）、title 均未动；其余 59 卡映射未动。
- 校验器：`--baseline` 模式新增一类可拦截违规（同 ID 内容篡改、任务映射改动）；`--write-baseline` 语义不变；退出码合同 0/1/2 不变。
- 测试与金标：新增 2 负例 + 1 正例，只在临时目录副本操作；20 个合成案例内容、ID、review_state 未动（哈希不变即证据），其「待复核提案」状态不变。
- 安全/费用/数据：无 API、无凭据、无外部访问、无依赖安装；不涉及用户数据与迁移。
- 任务依赖：T58 逐项证据审计的追踪链恢复与冻结来源一致；R-T01 P-1/P-2 具备闭环条件。

## 验证与回滚

复跑命令与结果（工作目录 `D:\dianzi`，解释器 `E:\miniconda\python.exe` Python 3.13.11，仅标准库；完整日志 `reports/runs/fix_t01_verify_plan.log`、`fix_t01_unittest.log`、`fix_t01_crosscheck.log`）：

| # | 命令 | 开始—结束（2026-09-30） | 退出码 | 结果 |
|---|---|---|---|---|
| 1 | `E:\miniconda\python.exe scripts/verify_plan.py --root D:\dianzi`（修复后、刷新前） | 21:29:09.146—21:29:09.213 | 0 | PLAN_OK |
| 2 | `E:\miniconda\python.exe scripts/verify_plan.py --root D:\dianzi --write-baseline contracts/baselines/plan_baseline_t01.json` | 21:29:38.765—21:29:38.920 | 0 | BASELINE_WRITTEN |
| 3 | `E:\miniconda\python.exe scripts/verify_plan.py --root D:\dianzi --baseline contracts/baselines/plan_baseline_t01.json` | 21:30:08.243—21:30:08.393 | 0 | PLAN_OK（必须项） |
| 4 | `E:\miniconda\python.exe -m unittest discover -s tests/plan -v` | 21:30:17.008—21:30:19.005 | 0 | Ran 16 tests；16 通过 / 0 失败 / 0 跳过 |
| 5 | 三方映射只读核对（`python -c` 内联脚本，正文见日志） | 21:34:42.853—21:34:42.859 | 0 | cards=60 / section8=60 / manifest=60，DIFF_COUNT = 0 |

负例回归（新增，全部在临时目录副本；正式 contracts/、fixtures/、baseline 未被负例改动）：

- 同 ID 篡改 `SYN-REV-001.expected_result` + `--baseline` → 非零退出，`BASELINE_SOURCE_HASH_CHANGED: fixtures/synthetic/pilot_cases.json`（R-T01 N10 修复前逃逸，修复后拦截；并断言不含 `BASELINE_CASE_DELETED`，证明拦截来自内容哈希比对）。
- 篡改 `contracts/task_manifest.json` 的 T06 requirements + `--baseline` → 非零退出，`BASELINE_SOURCE_HASH_CHANGED: contracts/task_manifest.json`。
- 未改动副本 + `--baseline` → exit 0 / PLAN_OK（正例）。

回滚：如需撤销，按本单「逐项旧 → 新」表反向恢复两处合同映射与 `verify_plan.py`/`test_verify_plan.py` 的新增部分，再以 `--write-baseline` 重刷基线（source_hashes 将回到旧三值）。回滚不涉及数据迁移。

## 批准记录

- 待人工确认：本单是否接受「以任务卡与 §8 为准删除 F1↔T06 映射」及「基线 source_hashes 纳入比对」两项公共合同变更。
- 修复行为本身由 FIX-T01 修复指令（2026-09-30）授权实施；本单不伪造任何批准。人工金标审批（20 个合成案例复核）仍为未完成项，与本单无关。
