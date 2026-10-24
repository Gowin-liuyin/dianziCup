# 独立审查（非作者）：batch19/20/21 checkpoint 定向复核与 R06 verification.unit 改判建议（R-C）

- 审查人：R-C（batch21 指派独立审查人，非被审提交的作者，未参与 batch19/20/21 任何提交）
- 审查时刻（真实时间戳）：2026-10-25T03:54:33+0800
- 文档首次创建时间：2026-10-25T03:54:33+08:00
- 最后更新时间：2026-10-25T03:54:33+08:00
- 审查方式：仅 git 只读命令（log/show/diff/status/rev-parse）与文件读取；未运行任何测试；未修改本报告以外的任何文件（progress/、reports/ 其他文件均未动）。
- 审查快照基线：HEAD = 70cb41d565f182735d475dbdb7fdb373bc9ee4f9（分支 codex/full-delivery-recovery，领先 origin 9 个提交）。

## 1. 审查范围

批次 checkpoint 提交共 13 个（均经 `git show --stat` 逐个核对）：

| 批次 | 提交 | 时间（+08） |
| --- | --- | --- |
| batch19 | e61556a22 | 2026-10-24 01:32:46 |
| batch20 | 999af01b0 | 2026-10-24 02:22:56 |
| batch20 | d21922041 | 2026-10-24 02:34:04 |
| batch20 | 6c9bb455c | 2026-10-24 11:26:14 |
| batch21 | e5832ed92（C0） | 2026-10-24 22:53:07 |
| batch21 | 6795db3e6（C1） | 2026-10-24 23:34:59 |
| batch21 | 13a580e23（C3） | 2026-10-24 23:35:11 |
| batch21 | b4407f833（C2 prep） | 2026-10-24 23:35:19 |
| batch21 | ee283de3e（C5 groundwork） | 2026-10-24 23:52:36 |
| batch21 | ff9109a43（C2 harness） | 2026-10-25 01:49:11 |
| batch21 | b467cd69c（R10） | 2026-10-25 03:13:50 |
| batch21 | cce9e1d90（R19） | 2026-10-25 03:41:59 |
| batch21 | 70cb41d56（R21） | 2026-10-25 03:45:50 |

ae6f623d1（2026-10-19）为批次19 前的现场捕获，不计入批次 checkpoint。origin/codex/full-delivery-recovery 位于 6c9bb455c，本地领先的 9 个提交全部为 batch21。

## 2. 逐 checkpoint 内容与叙述一致性

- **e61556a22（batch19）**：55 文件。`backend/src/ai_intel/fixtures/main_path_story.py`（535 行）、3 个新单测、`scripts/migrate.py`、`scripts/load_main_path_story.py`、前端 tasks 工作区与富化动作、恢复切片 `tests/r07_input_audit_helpers.py`（162 行）、story_fixture_20261023 证据链（含定向单测 79 通过的 backend_targeted_tests*.txt）。与 `reports/tasks/Root-batch19-runnable-assembly.md` 及 batch20 报告"改动文件"节对 e61556a22 的描述一致。
- **999af01b0（batch20 中间）**：13 文件。`test_r06_revision_mode_reads.py` +19 行（r06 适配，见 §4）、路由清单合同测试（181 行）、DTO 钉住测试（181 行）、`scripts/smoke_main_path.py`（575 行）、OPEN_QUESTIONS.md 建立、基线证据（full_suite.txt 2788 行，含 r06 两红 FAILED 行 2747-2748）。与 batch20 报告"改动文件"第 2 条逐项吻合。
- **d21922041（batch20 报告落盘）**：Root-batch20-summary.md 建立（70 行）、task_state/context_handoff 更新、质量门证据（backend_gates.txt 含 35 failed 勘误注记）、smoke_guard 证据。一致。
- **6c9bb455c（batch20 续推轮）**：`content_store.py` +20（OQ-2 方案 b 的 `_content_read_child_python_paths()`）、OPEN_QUESTIONS OQ-1/OQ-3 状态更新、54 条分类提案 JSON（3954 行）、smoke_real_run 证据、报告补记。与补记第 1-4 点一致。**注意：OQ-2 正文未同步闭环，见 §5。**
- **e5832ed92（C0）**：仅 `reports/runs/batch21_timeline.md` 22 行，符合"本批未改任何业务文件"。
- **6795db3e6（C1）**：单容器冒烟 attempt2-7 证据 21 文件、`scripts/dev_single_container.py`、`smoke_main_path.py` 修复（diff 已核对：`normalize_database_url` 返回 URL 对象替代 `str(url.set(...))`，与提交消息及 timeline"str(URL) 密码掩码"根因叙述一致）。
- **13a580e23（C3）**：R20 扩展（`fixtures/synthetic/security/r20_registry_extension_batch21.zip` 1.57MB、registration_proposal.json 54 条全哈希登记、CR-R20）、codec -2 oracle（`test_r07_single_model_dimension_contract.py` 2 行）、迁移 head 0031（3 个测试文件断言位更新）、red_zero 复跑证据、CR-migration。与 timeline C3.1-C3.3 一致；timeline"提交：6795db3e6（C1）、13a580e23（C3）、b4407f833（C2 准备）"与实际吻合。
- **b4407f833（C2 prep）**：`scripts/dev_integration_container.py`（229 行）、9 处跨目录裸导入修复、r12 切片 helpers 恢复、分组计划。与 timeline C2 准备叙述一致。
- **ee283de3e（C5 groundwork）**：CR-R10（39 行）、producer 盘点报告（169 行）、OQ-4、前端质量门证据。与 timeline C6/C5.2 一致。
- **ff9109a43（C2 harness）**：146 文件（49300 行，绝大部分为逐文件 pf 证据）、`dev_integration_container.py` 重写（+167）、两处新暴露的 0019 head 守卫更新（`test_r11_r08_forward_migration_boundaries.py`、`r07_idempotency_scope_helpers.py`，与 timeline C2 甄别第 2 点一致）、run1-run6 证据。
- **b467cd69c（R10）**：`neo4j_projection.py` +457、`default_graph_runtime.py` +238、r10/r16 注册测试、证据 `host_unit_rerun.txt`（171 passed, exit 0）+ `host_registration_final2.txt`（5 passed, exit 0）。与 timeline"171+5 tests green"一致。
- **cce9e1d90（R19）**：manifest 双产物（1384/1267 行）、schema（88 行）、annotation 装配/种子脚本与 10 个测试。与 timeline C5.3 一致（0 gold 表述与 manifest 内容核对无矛盾）。
- **70cb41d56（R21）**：evaluation 包 8 模块、`test_t47_baselines_and_ablation.py`（747 行；test_run_log.txt = 19 passed, exit 0）、7 份实验配置（B1/B4 以 not_implemented/not_reproduced 如实命名）、run_eval.py、seam B0 证据（exit_code=0）。与 timeline C5.4 一致。

结论：13 个 checkpoint 的提交内容与其时间线/报告叙述一致，未发现"提交含未叙述改动"或"叙述声称但提交缺失"的情况。

## 3. batch21 提交合规抽查（逐文件 add / tsbuildinfo / 秘密）

- **tsconfig.tsbuildinfo**：对 9 个 batch21 提交逐个 `git show --name-only` 过滤，零命中；batch19-21 全区间 `git log --name-only` 亦零命中。`frontend/tsconfig.tsbuildinfo` 当前在树未被修改（timeline C6 记录的 build 触碰后 `git checkout --` 还原事件与当前状态一致）。
- **秘密字面量**：对 batch19-21 全部新增行做高置信模式扫描（PEM 私钥/AKIA/sk-/ghp_/xox）零命中；赋值形态命中 2 处均为测试哑值（`analyst_password="unused"`、`csrf_token="verify-unused"`）。R20 扩展 proposal 与分类记录仅含 value_sha256/raw_sha256 哈希与合成值登记（`verified_synthetic_fixture`/`recorded_synthetic_evidence` 类别带证据链），无明文秘密；`unzip -l` 证实扩展 zip 为哈希命名 .bin 合成束。冒烟证据文件无带口令连接串（仅 `password authentication failed` 诊断行）。`scripts/smoke_main_path.py` 的修复方向（保留 URL 对象避免 `str(URL)` 掩码）本身即为防泄漏修复。
- **逐文件 add**：staging 过程无法从 git 历史直接证明，只能验证其声称的排除效果——当前未跟踪/未提交内容（`.zcode/`、`reports/reviews/batch21/`、`reports/runs/eval_20261025T034524329399+0800-B0/`、`backend_full_final.txt`、`full_suite_after_c3.txt`、`batch21_r19_r21_research/`）均未出现在任何提交中；146 文件大提交 ff9109a43 的文件清单与 harness/证据叙述逐类对应，无杂散文件。**间接验证通过。**
- **提交内 eval 目录说明**：70cb41d56 内 `reports/runs/batch21_r21_implementation/runs/eval_*/records.jsonl,run_summary.json` 是 R21 seam 检查的有意留痕，与根级未跟踪的 `eval_20261025T034524329399+0800-B0/`（seam_check_b0_v2.txt 所指 receipt_dir）不是同一批文件，不构成泄漏。

### 3.1 当前工作树状态（如实记录，截至 2026-10-25T03:54+08:00）

- 113 个已跟踪修改文件：`docs/decisions/CR-R07_*`、`CR-R20_*`（增补）、`progress/OPEN_QUESTIONS.md`（+8 行 OQ-5）、`reports/runs/batch21_timeline.md`（+18 行：C2 定稿/R10/C5 完成记录）、`batch21_integration_unlocked/` 下 100+ pf 证据（run6 后更新）、`batch21_red_zero/c31_r20_t06_t02_rerun3.txt`。
- 未跟踪：`.zcode/`、`reports/reviews/batch21/`（本报告）、`reports/runs/batch21_quality_gates/backend_full_final.txt`、`reports/runs/batch21_r19_r21_research/`、`reports/runs/batch21_red_zero/full_suite_after_c3.txt`、`reports/runs/eval_20261025T034524329399+0800-B0/`。
- **并发写入观察**：本审查首次 `git status`（03:46:00）不含 `progress/OPEN_QUESTIONS.md`；该文件与 timeline 的 mtime 为 03:46:18（首查之后 18 秒），即存在收尾/并发写入。本审查结论以 03:54 快照为准。`progress/task_state.json` 未被修改（mtime 2026-10-24 11:25:44 = 最后提交 6c9bb455c），即 **batch21 的 R10/R19/R21 尚未登记进 task_state，状态同步待收口**。

## 4. R06 verification.unit 改判建议（独立成节）

### 4.1 可执行判断

**建议：R06 `verification.unit` 由 failed 改判为 passed（仅 unit 维度）；R06 整卡维持 `needs_changes`（implementation=partial）。本建议不等于 accepted，不构成任何整卡或阶段验收。**

改判落地的前提动作：Root 按下方复核命令复跑确认（本审查受任务约束未运行测试，改判依据为已落盘的两次独立复跑记录与冻结材料零改动实证），并在 task_state 的 R06 history 追加改判事件与依据引用，不回写任何历史条目。

### 4.2 依据链（全部经本审查逐项实证）

1. **unit=failed 的成因唯一指向 2 个 r06 revision-mode 红**：`reports/runs/batch20_offline_baseline/red_inventory.md` 第 97-107、193-219 行给出完整根因链——10-17 冻结诊断早于 `business_version` 合同字段，`knowledge_read_service.py:444` 读取 `int(row["business_version"])` 时 stand-in 行缺键；`full_suite.txt` 2747-2748 行记录两红为 `[fixture-event_detail]`、`[live-event_detail]`。红清单 19 项最终余量（16 codec + 2 迁移 head + 1 t06）无一属于 R06。
2. **修复为纯测试层适配，oracle 未动**：999af01b0 对 `backend/tests/unit/test_r06_revision_mode_reads.py` 的 diff 共 +19 行——`_rows_carry_contract_business_version` 补常量 `business_version=1`（docstring 明示 "Frozen diagnostic predates business_version; supply the constant without new truth"），经 `monkeypatch.setattr(original, "sql_result", _adapted_sql_result)` 在测试函数内注入，24 条冻结 oracle 断言与 `test_required_revision_mode_truthfulness` 调用一字未改；与该文件既有的 `OriginalProjectionFixtures` 适配先例同构。符合"fixture 模式显式、隔离、有标记"与"冻结材料变动走变更单"（未触碰冻结材料，无需变更单）。
3. **冻结 oracle 零改动实证**：`git log --follow -- reports/runs/r06_revision_mode_read_fix_20261017/` 仅 48f96b5ba（2026-10-17）一次提交；`git diff 48f96b5ba HEAD --stat -- reports/runs/r06_revision_mode_read_fix_20261017/` 为空。`git log --follow -- backend/tests/unit/test_r06_revision_mode_reads.py` 仅 48f96b5ba（创建）与 999af01b0（适配）两次。
4. **修复后两次独立落盘复跑**：
   - batch20 B6 全量复跑：35 failed（40→35，backend_gates.txt 勘误注记明列 r06×2 在清零之列）+ 定向全文件 38 passed（red_inventory.md:289、Root-batch20-summary.md 测试表"r06 revision-mode 全文件 | 38 passed（2 红清零）"；测试用例数独立核算 24+2+2+2+1+1+2+2+1+1=38，数目自洽）。
   - batch21 C3.4 全量复跑（`reports/runs/batch21_red_zero/full_suite_after_c3.txt`，2026-10-25T01:3x）：**6080 passed / 0 failed / 1 xfailed / 83 errors**；`grep r06_revision_mode` 在该日志零命中（无失败、无 error），83 个 errors 为隔离 PG fixture 设计内 blocked，与 r06 无关。该文件属 tests/unit 收集范围，必然在执行集合内。
5. **标准符合性**：AGENTS.md §3"评审人依据日志与复跑结果确认"——上述两次落盘复跑即日志依据；batch20 报告"下一任务建议"第 3 点正是请求评审复跑后改判。本审查完成日志级复核；复跑命令留给 Root 落地前执行。

### 4.3 整卡维持 needs_changes 的依据

- `implementation=partial`；`verification.contract/integration/e2e/live` 全部 `not_run`。
- R06 live 面（6 小时采集、浏览器采集、FOFA 授权资产范围）未运行且资源窗未授权——按 AGENTS.md §3，"外部 live 阻塞不能在最终验收中视为通过"。
- batch21 C2 (d) 类登记 r06 局部 integration 失败待逐条甄别（OQ-5，约 30 例 r04/r05/r06/r07 局部），属 integration 维度后续工作。
- 故 unit 改判 passed **不升级** R06 整卡状态，也不解锁任何阶段门。

### 4.4 复核命令（Root 或后续评审人执行后落地改判）

```bash
# 1) 冻结 oracle 零改动（期望：无输出）
git diff 48f96b5ba HEAD --stat -- reports/runs/r06_revision_mode_read_fix_20261017/
# 2) 测试文件历史仅两次提交（期望：48f96b5ba、999af01b0）
git log --follow --oneline -- backend/tests/unit/test_r06_revision_mode_reads.py
# 3) 定向复跑（期望：38 passed, exit 0）
cd backend && uv run python -m pytest tests/unit/test_r06_revision_mode_reads.py -q
# 4) 全量证据交叉核对（期望：0）
grep -c "FAILED tests/unit/test_r06_revision_mode" reports/runs/batch21_red_zero/full_suite_after_c3.txt
```

### 4.5 引用勘误（不影响证据成立）

任务书称"batch20 报告续推轮补记第 1、3 点声明 r06 revision-mode 测试层适配后 38 passed"。实际该声明位于报告**主文**："实现内容与关键甄别"第 3 点、"真实测试命令与结果"表（r06 revision-mode 全文件 38 passed）、"合同与计划偏差"节与"下一任务建议"第 3 点；补记第 1、3 点分别对应 OQ-2 修复与 OQ-1 定案，不含 r06 内容。报告自身自洽，此为引用方偏差，记录备查。

## 5. OQ-1..4（含 OQ-5）与报告叙述一致性

- **OQ-1：一致，无过期表述。** 两段状态更新（10-24 11:1x WSL2 数据面故障定案；批次21 C1 单容器回环路线真实解决）与 batch20 补记第 3 点、timeline C1（attempt7 pass）、attempt7 证据吻合；宿主侧修复明确保留为用户事项，未把环境修复冒充软件修复。
- **OQ-2：过期，需修正。** 正文仍停留"具体缺口：需要评审决定修复方向 (a)/(b)"，无闭环状态更新；而 batch20 补记第 1 点已宣布按方案 (b) 修复完成（`content_store.py` `_content_read_child_python_paths()`，4 文件 165 passed），代码确在 6c9bb455c 提交（本审查已核对 diff）。6c9bb455c 只更新了 OQ-1/OQ-3，漏更 OQ-2。
- **OQ-3：部分过期，需修正。** 11:3x"一次修正"状态更新本身与补记第 2 点一致（回退至 136、提案材料存档——材料确在 6c9bb455c 提交）；但"影响：t06 维持唯一历史红（19 failed 最终余量）"与"最小所需输入：评审/下一批次按 R20 程序落地"已被 batch21 C3.1 超越（136→190 落地、c31_rerun3 303 passed、t06 清零、C3.4 全量 0 failed），缺闭环状态更新。
- **OQ-4：一致。** 与 ee283de3e 提交、`Root-batch21-public-producer-inventory.md`、timeline C5.2 吻合（503 桩被冻结测试钉住、真实 producer 零装配、需变更单改语义）。
- **OQ-5（工作树未提交新增）：内容一致但时间戳不实。** 内容与 timeline C5 收口/R21 实现报告一致；但"记录时间：2026-10-25T07:0x+08:00"晚于最后提交 70cb41d56（03:45:50）与本审查墙钟（03:5x），不可能成立。同类问题：timeline"R10 默认图消费者……2026-10-25T06:0x"晚于对应提交 b467cd69c（03:13:50）；timeline 头部"最后更新时间：2026-10-24T22:55:00"未随后续追加内容更新。三处均需在落地前更正为真实时间。

## 6. 需修正事项与观察项清单

需修正（3 条）：

1. **OQ-2 补闭环状态更新**：正文与补记第 1 点/已提交代码矛盾（过期表述）。
2. **OQ-3 补闭环状态更新**：19 failed 余量与"待落地"表述已被 batch21 C3 清零/落地（过期表述）。
3. **时间戳不实更正**：OQ-5 记录时间 07:0x、timeline R10 条目 06:0x、timeline 头部最后更新时间未更新——三处与 git 提交时间及墙钟矛盾。

观察项（不计需修正，供 Root 收口参考）：

4. batch21 收口未完成：R10/R19/R21 未入 `progress/task_state.json`；timeline/OQ-5/pf 证据/CR 增补尚未提交；03:46:18 存在并发写入痕迹（本审查快照与该写入相差秒级，已如实记录）。
5. batch20 报告引用位置勘误（§4.5）：属任务书引用偏差，报告自身自洽，不构成仓库缺陷。

## 7. 审查结论

- batch19/20/21 全部 13 个 checkpoint：提交内容与叙述一致；batch21 合规抽查（无 tsbuildinfo、无秘密字面量、无未跟踪目录泄漏）通过；"逐文件 add"以排除效果间接验证通过。
- R06：建议 `verification.unit` 改判 passed（限 unit 维度，落地前按 §4.4 复核），整卡维持 `needs_changes`；**本建议不等于 accepted**。
- OQ：OQ-1/OQ-4 一致；OQ-2/OQ-3 过期需补闭环；OQ-5 及 timeline 存在三处不实时间戳需更正。

（R-C，2026-10-25T03:54:33+08:00）
