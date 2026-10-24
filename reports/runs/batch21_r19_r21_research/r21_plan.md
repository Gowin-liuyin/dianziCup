# 批次21 C5.4 · R21 评测框架骨架 —— 实现方案（只读调研产物）

- 调研时间：2026-10-25T00:40:28+08:00 开始，本方案落盘 2026-10-25T00:45:00+08:00
- 仓库：D:\dianzi，分支 codex/full-delivery-recovery，HEAD `ee283de3e`；本次调研只读，未运行 pytest，未改业务文件
- 配对文件：r19_plan.md 同目录（R19 dev-set 装配是本 harness 的设计输入）

---

## 1. 权威输入与任务卡摘录

| 依据 | 位置 | 关键条款 |
|---|---|---|
| R21 恢复卡 | docs/plan/12_recovery_task_cards_20261014.md:233-241 | 前置"R14–R20，开发集与评测工具可用"（:236）；输入→输出"同数据/模型/工具/预算配置 → 可复跑基线、消融、延迟和错误分析"（:237）；改动边界 `experiments/`、性能脚本、相关最小优化，"不得改holdout答案、阈值或分母凑结果"（:238）；实施"B0/B1/B2/B2b/B3/B5；B4只有实际复现才登记"（:239）；测试①同任务资源可比②关闭单个机制的消融可复跑③完整时延含排队/失败④引用和准确率不因优化退化⑤负结果与旧索引不走错误缓存⑥每个指标有分子分母、原始记录和运行配置（:240）；"未复现外部方案标未复现，不能预填提升百分比"（:241） |
| T47 原卡 | docs/tasks/T47_baselines_and_ablation.md | 允许修改：`experiments/`、`backend/src/ai_intel/evaluation/`、`scripts/`、`backend/tests/unit/`（:23）；目标产物：`experiments/configs/`、`backend/src/ai_intel/evaluation/`、`reports/tasks/T47.md`（:27）；**测试位置合同：`backend/tests/unit/test_t47_baselines_and_ablation.py`**（:29）；实施 6 步：CaseRunner/ResultRecord 记录模型/提示词/数据/权限/预算/缓存/硬件/代码 hash（:33）、B0–B5 配置（:34）、消融开关且"生产不暴露危险安全开关"（:35）、B4 外部参照未复现如实登记（:39）、报告正确率/完成率/未知率/时延/调用量/费用（:41）、冻结后配对实验+多次随机运行（:43）；验收 C01–C06（:51-56） |
| T48（R21 另一切片） | docs/tasks/T48_performance_benchmarks.md | 修改边界 `scripts/benchmarks/`、`experiments/`、integration 测试（:23）；本批骨架只保留记录字段，不做压测 |
| 基线与消融合同 | docs/plan/06_testing_and_evaluation.md:103-127 | B0 强检索：同资料+精确检索+BM25+向量+重排（:105）；B1 单Agent（:107）；B2 固定四角色（:109）；B2b 固定九职责（:111，CR-R01）；B3 我们的缺口调度，只改变调度策略（:113）；B4 公开实现，无法部署写未复现（:115）；B5 全量重算：变化任务正确性参照（:117）；消融分别关闭条件保留、证据校验、冲突处理、scope watch、动态调度（:119）；对照统一模型/输入快照/工具返回/权限/预算/缓存/硬件（:121）；按事件家族聚类 bootstrap、冻结后再跑 holdout（:125） |
| 硬约束 | 用户本批指令 + AGENTS.md §6 | 骨架=对 fixture 数据真实可执行；一切输出显式标注 fixture-scale，不得写成正式指标；0 gold ⇒ 准确率如实不可算 |

## 2. 现状盘点（全部 file:line 实证）

### 2.1 缺失（grep/ls 实证）

- 无 `backend/src/ai_intel/evaluation/`：backend/src/ai_intel/ 目录清单为 answering/api/assessment/assets/domain/enrichment/fixtures/infrastructure/ingestion/investigation/knowledge/recommendations/retrieval/revalidation/workers，无 evaluation。
- 无 `experiments/`（仓库根 ls 无此目录）、无 `scripts/benchmarks/`（scripts/ 清单无此子目录）。
- **B1 单Agent 无实现**：全 backend/src grep `"B1"` 0 命中；Strategy 联合类型只有 B2/B2b/B3（investigation/graph_contracts.py:26）。

### 2.2 既有可复用件（基线映射表）

| 基线 | 现有代码 | file:line | 骨架状态 |
|---|---|---|---|
| B0 强检索 | HybridRetriever（BM25+向量 RRF 融合）+ 重排 | backend/src/ai_intel/retrieval/hybrid.py:347（类）、:96（reciprocal_rank_fusion）、:360（retrieve）；重排协议 retrieval/service.py:47、调用 :293-305 | available；真跑需 PG（hybrid 是 SQL 检索）+ 语义模型（显式 fixture 模型已存在，backend/tests/r12_hybrid_fixtures.py:44-58 FixtureSemanticModels：固定 384 维向量与逆序 rerank，注释明示"never semantic recall quality"） |
| B1 单Agent | 无 | 全 src grep 0 命中 | not_implemented 登记（不虚设、不加 Strategy 枚举值，见 §6 风险 1） |
| B2 固定四角色 | build_investigation_graph("B2") 用 B2_ROLE_MAP 分组 | backend/src/ai_intel/investigation/graph.py:59-96（:67-69 取 B2_ROLE_MAP）；B2_ROLE_MAP=planner+intelligence_agent 等四组，backend/src/ai_intel/investigation/capabilities.py:212-217 | available |
| B2b 固定九职责 | 默认策略，九角色逐段 | graph_contracts.py:37 `strategy: Strategy = "B2b"`；AgentRole 九角色 capabilities.py:12-21；graph.py:69 else 分支逐角色 | available |
| B3 缺口调度 | 同图只换 planner 候选选择 | graph.py:64 docstring "Strategies share executors and budgets; B3 changes only the planner's candidate choice"；Strategy 含 "B3" graph_contracts.py:26 | available |
| B4 外部参照 | 无复现记录 | 无 | not_reproduced 登记（T47:39、06:115"不能冒充官方实跑"） |
| B5 全量重算 | RevalidationService（增量重判侧已有） | backend/src/ai_intel/revalidation/service.py:65（类）、:88（plan_change，冻结页+显式 partial 计划）、:199（reassess） | partial；"全量参照"=同快照对全部评估重算的 config 轴，行为验证需 DB，本批仅 config+记录 |

### 2.3 运行时与数据面（fixture 真跑的依托）

- QA 入口：`GroundedQuestionService.ask(payload, scope_provider, ...)`（backend/src/ai_intel/answering/service.py:309-317），构造注入 `data_mode: DataMode = "live"`（:299）；DataMode=Literal["live","fixture"]（api/knowledge_contracts.py:15、infrastructure/settings.py:27，settings 默认 live :40）。
- 证据校验：validate_citations（answering/grounding.py:122）、validate_support_verdicts（:174）、generate_grounded_answer（:196）。
- 模型客户端：`GenerationClient`（infrastructure/models/generation.py:326-350，provider/model 白名单校验 :338-343）；`FixtureProvider` 固定答案、fingerprint=sha256(prompt)[:12] 确定性（infrastructure/models/clients.py:155-164）；`ModelNotConfiguredError`（clients.py:20）；`ProductionFixtureForbidden` + `assert_runtime_allows_fixture_provider`（clients.py:24, :131）——fixture provider 严禁 production，harness 必须传测试环境名；`describe_model_capability`（clients.py:145）可用于如实登记模型未配置。
- fixture 数据：`load_main_path_story(engine, store, *, data_mode, ...)`（backend/src/ai_intel/fixtures/main_path_story.py:291-304），fixture 模式门 require_fixture_mode（:129）；冒烟脚本同路（scripts/smoke_main_path.py:456 `data_mode=fixture`、:479）。
- 测试先例：t 卡命名 unit 测试已存在（backend/tests/unit/test_t02_project_skeleton.py、test_t17_relevance_and_event_linking.py 等；integration 有 test_t30_hybrid_retrieval.py）——`test_t47_baselines_and_ablation.py` 命名符合既有约定。
- R19 输入面：dev-set manifest（r19_plan.md 步骤 A–C 产物）0 gold——**accuracy 分子不可得**；C5.4 骨架不得在无金标时输出准确率数字。

## 3. 骨架设计

### 3.1 输入

1. **dev-set/金标**：读 R19 dev-set manifest（benchmarks/manifests/，候选级 0 gold）；manifest 缺失或为空时 harness 明确 `blocked_input_missing` 退出，不空跑、不伪造 case 集合（对齐 06_testing:21"不能打印PASS"精神）。
2. **实验配置** `experiments/configs/<baseline_id>.json`：`baseline_id`（B0/B1/B2/B2b/B3/B5/B4_ref）、`strategy`（B2/B2b/B3 或 null）、`ablation`（§3.4）、`data_mode: "fixture"`（**本批常量**）、`data_ref`（dev-set manifest 相对路径 + 期望 sha256）、`model_config`（provider/approved_model 名与凭据的**环境变量名**，不存值）、`budget`（max_model_calls/max_tool_calls/费用上限=0）、`seed`（确定性种子记录位）、`hardware_note`、`code_ref`（期望 HEAD）。
3. schema 校验失败/未知字段拒绝（对齐 prepare.py 风格）。

### 3.2 ResultRecord（统一记录，T47:33）

每 case × 每 baseline 一条，字段全部显式：

- 标识：`run_id`、`case_id`、`baseline_id`、`strategy`、`ablation_flags`（快照）。
- 可比性字段（T47-C01）：`data_sha256`、`config_sha256`、`code_sha256`（git rev-parse HEAD + dirty 标志）、`model_provider`/`model_name`（非密）、`budget`、`seed`、`hardware_note`、`started_at/ended_at`（+08:00）。
- 行为结果：`status`（completed/partial/failed/blocked_model_missing/not_applicable）、`tool_calls`、`model_calls`、`latency_ms`（完整墙钟，含排队/失败，对齐 06:83"不能删去慢请求"）、`error_code`。
- 指标：一律 `{numerator, denominator, status}` 三元组。`accuracy/critical_claim_accuracy/evidence_support`：dev-set 0 gold ⇒ `status="not_computable_no_gold", numerator=null, denominator=case_count`；`completion_rate/unknown_rate/timeout_rate`：fixture 真跑可算但必须带 scale 标注。
- **scale 标注**：`scale: "fixture"`、`data_mode: "fixture"`、`disclaimer: "fixture-scale 非正式指标"` 固定字段。

### 3.3 基线注册

- 骨架提供 runner 协议 `CaseRunner.run(record_input) -> ResultRecord`（纯接口，backend/src/ai_intel/evaluation/runners.py）。
- B2/B2b/B3：adapter 调 `build_investigation_graph(strategy, ...)`（graph.py:59）——本批 unit 层用显式 stub executor 驱动记录结构；真实图执行（fixture DB）列为可选 integration 步骤（§4 步骤 E）。
- B0：adapter 接口面向 `HybridRetriever.retrieve`（hybrid.py:360）；unit 层同上 stub；真跑属 integration/容器路线。
- B1：注册表条目 `status="not_implemented"`，产出 record `status="blocked_baseline_missing"`，**不生成任何指标**（T47-C02 的诚实版）。
- B4：注册表条目 `status="not_reproduced"`，无数字（T47:39）。
- B5：config 定义"同快照全量重算"轴，记录 `status="declared_behavior_pending_db"`。

### 3.4 消融开关（T47:35、06:119）

- `AblationFlags`：`condition_retention / evidence_check / conflict_handling / scope_watch / dynamic_dispatch` 全 bool，default 全 on，显式记录进 config 与每条 record。
- 本批真实生效的轴：**策略轴**（B2/B2b/B3 已是现成代码开关，graph.py:67-69）；其余五轴 `declared_not_wired`（default=on 时记录与现行为一致；置 off 时 record 标 `ablation_status="switch_declared_mechanism_not_wired"`，不产出"消融效果"数字）。
- 开关只存在于 evaluation 层配置；**不改生产模块**（T47:35"生产不暴露危险安全开关"）。

### 3.5 复跑机制（T47:43）

- 运行收据落 `reports/runs/eval_<run_id>/`：每 record 一行 JSON + run 汇总（命令、cwd、起止、退出码、case 计数、失败/skip 分列——对齐 06:68 记录要求）。
- 复跑 = 同 config_sha256+data_sha256+code_sha256 再执行；`experiments/compare_runs.py` 输出字段级 diff；FixtureProvider 确定性（clients.py:163）保证 fixture 路线可复现；真实模型路线本批不存在（费用上限=0）。
- 多次随机运行：seed 记录位已备；fixture 路线 seed 变化不影响确定性 provider，如实记录。

### 3.6 fixture-scale 强制标注（本批硬约束）

- writer 层（evaluation/writers.py）：record 缺 `scale="fixture"` 或缺 disclaimer 拒绝落盘（exit 非零 + 固定错误码）。
- 真实模型结果通道：需要 `scale="live"` + 显式授权环境变量门；本批无授权，通道存在但恒拒绝（`live_results_forbidden_budget_zero`），防止未来静默混写（T47-C03：fixture 结果不混入真实效果报告）。

## 4. 最小实现路径（步骤 A–E）

- **A · evaluation 包骨架**（backend/src/ai_intel/evaluation/）：`records.py`（ResultRecord dataclass/pydantic + hash 规则）、`configs.py`（config schema 校验）、`registry.py`（B0–B5/B4_ref 状态表，含 not_implemented/not_reproduced 如实条目）、`runners.py`（CaseRunner 协议 + B2/B2b/B3/B0 stub adapters）、`metrics.py`（三元组指标与 not_computable_no_gold 语义）、`writers.py`（fixture-scale 强制 + 收据落盘）、`replay.py`（复跑比较）。全部纯函数/协议，无 DB、无网络依赖（unit 层合同：06_testing:9）。
- **B · 配置**（experiments/configs/）：`b0_retrieval.json`、`b2_four_roles.json`、`b2b_nine_roles.json`、`b3_gap_scheduling.json`、`b5_full_recompute.json` 五份可执行配置 + `b1_single_agent.not_implemented.json`、`b4_external.not_reproduced.json` 两份如实登记。
- **C · CLI**（experiments/run_eval.py）：读 config → registry 校验 → 逐 case 产出 record → writer 落收据；退出码合同仿 scripts/dev.py:4-12（0 通过/1 失败/2 参数错误/3 未建设/4 资源阻塞）。
- **D · 直属测试**（backend/tests/unit/test_t47_baselines_and_ablation.py，T47:29 指定位置）：§5 全部用例真实执行。
- **E ·（可选，不阻塞骨架）** integration 冒烟：隔离 PG + FixtureSemanticModels（tests/r12_hybrid_fixtures.py:44）+ main_path_story fixture（main_path_story.py:291）真跑 B0 检索与 B2b 图一遍，产出带 fixture-scale 的收据——若批内时间不够，记 OQ 转 C5.4 后续轮，骨架验收不依赖它。

## 5. 直属测试设计（T47-C01–C06 → 骨架级断言）

| ID | 输入/场景（T47:51-56） | 骨架级可观察断言 | 本批可达 |
|---|---|---|---|
| C01 | 同 case 运行 B0/B1/B2/B3，输入和预算等可比字段一致 | B0/B2/B2b/B3 stub runner 产出的 record 中 data_sha256/config_sha256/seed/budget/model 字段相同，仅 baseline_id/strategy 不同；B1 返回 blocked_baseline_missing 且无指标字段值 | 是（stub 级；真实同资源可比需模型/PG，OQ） |
| C02 | 外部方案不支持某类任务 → N/A 而非算错拉低对手 | not_applicable record 不进该基线 accuracy 分母，但保留在覆盖矩阵输出中（逐 case 可见） | 是 |
| C03 | fixture 结果不混入真实效果报告 | 全部落盘 record scale="fixture"+disclaimer；writer 拒绝缺标注 record；live 通道预算=0 恒拒绝且错误码固定 | 是 |
| C04 | 关闭 scope watch → 变化测试应能发现漏新增命中 | 骨架级：flag 进 config+record、default on、off 时 ablation_status="switch_declared_mechanism_not_wired"；行为级证明（真测漏新增命中）需 revalidation+fixture PG → 本批 not_run，记 OQ/可选步骤 E | 骨架是；行为级否 |
| C05 | 省工具但拒答增多 → 完成率/未知率同时体现 | metrics 模块对同一 run 同时输出 completion_rate 与 unknown_rate 两字段；writer 拒绝仅含其一的"提升声明"结构；两指标 denominator=case_count 不删失败 case | 是 |
| C06 | 缺模型或外部部署失败 → 明确阻塞/未复现，不生成比较数字 | GenerationClient 未配置（对齐 ModelNotConfiguredError 语义，clients.py:20）→ record status=blocked_model_missing、指标全 null、run 汇总无跨基线比较数字 | 是 |

命令（T47:63 工程合同的骨架兑现）：`cd backend && uv run pytest tests/unit/test_t47_baselines_and_ablation.py -v`。

## 6. 触碰公共合同/金标的风险点

1. **Strategy Literal 扩展**：给 `Strategy = Literal["B2","B2b","B3"]`（graph_contracts.py:26）加 "B1" 即改动调查图合同类型面，影响 workflow_service 校验与既有测试 → 本批不做；B1 以注册表 not_implemented 表达。
2. **消融开关下沉生产代码**：改 answering/grounding/retrieval 内部加开关即生产语义变更+危险开关暴露 → 本批只在 evaluation 层声明（T47:35），行为接线留正式 R21 轮并走变更单。
3. **指标分母**：任何"缺金标/失败 case 从分母消失"都违反 AGENTS §6 与 T47-C05；writer/metrics 固定 denominator=case_count、失败单列 status。
4. **金标边界**：harness 只读 R19 候选级 manifest（0 gold）；不读 holdout（holdout 仍在仓外，prepare.py:353-357 合同）；不把 FixtureProvider 固定答案当效果；accuracy 恒 not_computable_no_gold。
5. **FixtureProvider 生产禁令**：harness 必须 `assert_runtime_allows_fixture_provider`（clients.py:131,155-164）传测试环境名，防止 fixture 答案进入 live 数据模式。
6. **数据模式**：config `data_mode` 常量 fixture；live 通道需独立授权门（本批恒拒绝）；与 settings.py:40 默认 live 的产品侧互不影响。
7. **报告语义**：run 汇总页眉固定"fixture-scale，非正式指标，不是官方评分材料"；不预填提升百分比（T47:241、06:127）。

## 7. 本批不做清单

- 不实现 B1 单 Agent、不扩 Strategy 枚举、不登记 B4 复现。
- 不做 T48 性能压测（scripts/benchmarks/ 不建；ResultRecord 只留 latency/调用数字段）。
- 不跑真实模型、不产生任何 API 费用（budget=0；缺凭据走 blocked_model_missing）。
- 不改 holdout 答案、阈值、分母；不产正式指标报告；不做正式冻结后的配对实验（T47:43 的前置"配置和金标冻结"不存在——0 gold）。
- 不改生产模块（answering/retrieval/investigation/revalidation 零 diff）；公共合同（contracts/schemas/、api schema）零 diff。
- 不做真实 PG/容器的 B0/B5 行为验证（可选步骤 E 或 OQ）；unit 测试不依赖 DB。

## 8. 与 R19/C5.3 的接口与依赖

- 输入：C5.3 dev-set manifest（r19_plan.md 步骤 A–C）。若 C5.3 未落地，C5.4 的 config `data_ref` 可暂指向既有候选 manifest benchmarks/manifests/r19_public_dev_candidate_v1.json（1 real case，0 gold）——harness 仍真实可跑（stub runner 出 record），规模如实为 1 case fixture-scale。
- 交接：C5.4 骨架 + not_implemented/not_reproduced 登记是正式 R21（B1/B4/真实模型/行为级消融/家族聚类 bootstrap，06:125）的前置壳；正式轮需模型授权与冻结 dev-set，均不在本批。

最小交付一句话：**新增 backend/src/ai_intel/evaluation/ 骨架（ResultRecord/配置/基线注册/指标三元组/fixture-scale 强制 writer/复跑比较）+ experiments/configs 五配置两如实登记 + run_eval CLI + T47 指定 unit 测试，对 fixture 数据真实跑通并全部显式标注 fixture-scale；B1/B4/真实模型/行为级消融/正式指标本批不可达，如实登记 not_implemented/not_reproduced/not_run。**

---

- 文档首次创建时间：2026-10-25T00:45:00+08:00
- 最后更新时间：2026-10-25T00:45:00+08:00
- 调研开始时间戳：2026-10-25T00:40:28+08:00（date +%Y-%m-%dT%H:%M:%S%z 原始输出 2026-10-25T00:40:28+0800）
