# batch22 目标2 · SourceEnricher（富化节点）输出 UTF-8 预算只读调研

文档首次创建时间：2026-10-25T04:48:02+08:00
本次写作开始时间：2026-10-25T04:48:02+08:00
最后更新时间：2026-10-25T04:48:02+08:00
调研性质：只读（未修改任何业务文件，未运行 pytest；git 仅只读命令）
工作分支：codex/full-delivery-recovery；HEAD 4c6ff75ac
授权依据：reports/tasks/Root-batch22-plan.md:11（只读调研；触公共合同 → 停该项 + 追记 OQ；可离线最小实现 → 实现 + 直属测试）

## 结论（先行）

**不可做（在当前授权下无"最小实现"）**：UTF-8 输出预算的"计量"已存在且被冻结测试钉定为正确 UTF-8 语义；唯一可新增的是"行为级预算约束"（裁剪/降级富化输出使其恰好落入预算），而该行为的反面（超预算整体拒绝、receipts 清空、结果公开为空）正是本区域专属冻结 oracle 钉住的 fail-closed 合同，且富化 receipt 输出是公开 API DTO（WorkflowResult → InvestigationResponse.result）的组成部分。任何实现路径都必须改冻结断言或公共 DTO → 变更单范围，按 batch22 计划自身条件应"当场停该项、追记 OQ"。

---

## 1. 对象定位与"输出预算"现状

### 1.1 "SourceEnricher" 实际指涉

仓库中不存在名为 `SourceEnricher` 的类（`grep -rin "sourceenricher|source_enricher" backend/src frontend/src` 零命中）。batch20 B5.3 / batch22 计划所称对象是调查工作流中的富化角色路径：

- `AgentRole.ENRICHER`：backend/src/ai_intel/investigation/capabilities.py
- 富化节点实现：backend/src/ai_intel/investigation/workflow_service.py:1311-1377（`run_role` 的 `elif role == AgentRole.ENRICHER:` 分支）
- 原始来源报告读取：backend/src/ai_intel/investigation/source_report_node.py:14-48（`read_enrichment_source_reports`，8 引用共享 5 秒 deadline）+ backend/src/ai_intel/enrichment/source_report_reader.py（`build_source_report_reader`，25 行薄工厂）
- 底层读模型：backend/src/ai_intel/knowledge/structured_fact_proofs.py:84-174（`StructuredFactProofRequest` / `SourceReportedFact` / `StructuredFactProofRead`）

注意区分：`enrichment/` 包另有独立的**输入侧**字节预算（backend/src/ai_intel/enrichment/inputs.py:26-27 `MAX_INPUT_BYTES=8MiB`、`MAX_DOCUMENT_BYTES=2MiB`，检查点 inputs.py:253-258；publication.py:342-343 复用同一错误码 `enrichment_input_byte_budget_exceeded`）——那是文档输入预算，与 B5.3 的"输出预算"无关。

### 1.2 当前输出预算机制（UTF-8 语义已实现）

工作流输出预算是一条**累计、按实际 UTF-8 字节计量、fail-closed 整体拒绝**的机制：

1. 计量函数 `_output_json_bytes`（workflow_service.py:139-145）：`json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False).encode("utf-8")` 的长度——**真实 UTF-8 字节数，中文按 3 字节计**，与 PostgreSQL JSONB 存储格式无关（docstring "Count the frozen UTF-8 representation"）。
2. 预算合同 `WorkflowBudget`（graph_contracts.py:58-67）：`max_output_bytes` 默认 262144，域 [1024, 1048576]；公开请求 DTO 字段。
3. 预留：`reserve`（workflow_service.py:827-895）逐操作累计校验（输入字节/输出字节/model/tool 次数/操作总数 `MAX_WORKFLOW_OPERATIONS`，workflow_service.py:136），每次预留至少 `OUTPUT_BUDGET_FAILURE_BYTES = _output_json_bytes({"error_code": OUTPUT_BUDGET_FAILURE})`（workflow_service.py:148, 845）。
4. 完成判定：`complete_operation`（workflow_service.py:897-943）按实际字节对剩余预算判定；超限 → 输出整体替换为 `{"error_code": "operation_output_budget_exhausted"}`、status="failed"（workflow_service.py:924-932），拒绝回执不可变、不可二次提交（workflow_service.py:913-919）。
5. 节点收口：`run_role` 末尾把含全部 receipts 的整个 state 作为节点回执再次过 `complete_operation`（workflow_service.py:1649-1653），预算失败即 `stop_reason=OUTPUT_BUDGET_FAILURE`（workflow_service.py:1623-1628）；图停止原因优先级含 OUTPUT_BUDGET_FAILURE（workflow_service.py:1607-1620；graph.py:15-49）。
6. 富化节点输出装配：workflow_service.py:1359 `source_reports = [json_object(report) for report in reports]` 全量装配后于 workflow_service.py:1368-1375 写入 `output["source_reports"] / source_report_read_status / source_report_reason / enrichment_write:"not_configured"`，字节约束完全委托给完成判定——这是设计而非遗漏：source_report_node.py:19-22 docstring 明文 "Empty references return no reports; the caller must record the evidence gap and **enforce receipt bytes**"。

### 1.3 "UTF-8 预算缺口"的准确含义

计量层不存在缺口：`_output_json_bytes` 已经是 UTF-8 正确计量，且被专名冻结测试 `test_frozen_encoding_counts_real_chinese_utf8_bytes`（backend/tests/unit/test_r14_source_report_output_budget.py:108-112）钉死（`{"值":"中文"}` 恰等于 UTF-8 字节数 22）。

真正的"缺口"只能在**行为层**表述：富化输出（source_reports）在完成判定前不做任何字节上界控制——单条报告的字符串内容没有字节上限（structured_fact_proofs.py:99 `primary_assertion_path` max_length=2000、:109/:145 `missing_requirements` 的 max_length 约束的是**元组项数**（32/64 项）而非字符串长度），大字符串（如 unit 测试构造的 `"中"*5000` ≈ 15000 UTF-8 字节，test_r14_source_report_output_budget.py:448）会把富化节点乃至整个工作流推入 `operation_output_budget_exhausted`，全部 receipts 丢弃、公开结果为空。"实现 UTF-8 输出预算" = 把这种"整体失败"改为"按 UTF-8 预算裁剪/降级富化输出"。这正是被冻结 oracle 禁止的方向（见 §3/§4）。

## 2. batch20 B5.2"触碰公共契约"的准确指涉

依据：reports/tasks/Root-batch20-summary.md:22（B5.2 记录）、:25（B5.3 跳过原因）、:54（计划偏差）。B5.2 的原始计划文件未入库（批次20 计划仅存在于会话，git 全历史检索 `B5.3` 仅命中 batch20/batch22 两份总结），可核对的事实链如下。

B5.2 的"公共契约"指三类，且都与富化节点路径纠缠：

1. **DTO 字段 + 类型域**：已发布读契约的 `DataMode = Literal["live","fixture"]`（如 WorkflowResult.data_mode，graph_contracts.py:98；EventListResponse/DocumentListResponse 的 data_mode 字段，test_read_source_mode_dto.py:165-169 钉死不可表示值直接 ValidationError）。改成 None→"unknown" 需要**拓宽**该 Literal——backend/tests/unit/test_read_source_mode_dto.py:1-11 模块 docstring 与 :172-181 的 strict xfail 明文记录这是"blocked pending a change order"。
2. **响应 schema（公开 API）**：`WorkflowResult`（graph_contracts.py:92-102，receipts 为 `tuple[RoleReceipt, ...]`、RoleReceipt.output 为 `dict[str, JsonValue]`，graph_contracts.py:83-89）经 `service.read_result` 直接进入公开 API 响应体 `InvestigationResponse.result`（backend/src/ai_intel/api/investigation_routes.py:69-80 字段声明、:300 装配点）。富化 receipt 的 output（source_reports 等）就在其中。
3. **行为合同（fail-closed oracle）**：现行"未知来源拒绝而非重标注"（503 fail-closed）与 2026-10-17 r06 诊断 oracle 及 r18 公开边界测试两个冻结 oracle 一致（batch20-summary:22；test_read_source_mode_dto.py:5-10）。

B5.2 与 B5.3 的区域纠缠点（B5.2 结论外推到 B5.3 的依据）：富化节点直接消费 B5.2 钉住的读服务与 data_mode 贯穿链——workflow_service.py:1312-1315 `KnowledgeReadService(session, scope, self.service.data_mode)`；workflow_service.py:1338-1344 `build_source_report_reader(..., self.service.data_mode)`；逐报告带 `data_mode: DataMode`（structured_fact_proofs.py:150），unit :329 断言 reader 工厂以 `"fixture"` 收参。即：富化输出预算若动 receipt 输出 schema，必然落在与 B5.2 同一条公开 DataMode/receipt 合同链上。batch20 的"相关区域触碰公共契约"是**区域级保守判断，经本轮逐点核实成立**。

## 3. 可做/不可做判定与依据

### 3.1 三条实现路径逐一否决

**路径 A：富化输出裁剪/降级（trim-to-fit）** —— 否决。
大报告超预算时不再整体拒绝而是裁剪进预算，将直接翻转冻结 oracle 的断言：
- backend/tests/unit/test_r14_source_report_output_budget.py:435-473 `test_large_source_report_never_enters_checkpoint_after_completion_rejection`：钉死 `captured[0] > 15000`（:469）、`state["stop_reason"] == OUTPUT_BUDGET_FAILURE and state["receipts"] == []`（:470）、checkpoint 不含大报告（:471-472）、`result.answer` 为空（:473）。裁剪后 receipts 非空、stop_reason 变化 → 断言失败。
- backend/tests/integration/test_r14_source_report_output_budget_pg.py:285-308 同名 PG 版：B2/B2b/B3 × 预算 1024 参数化，:302 `stop_reason == OUTPUT_BUDGET_FAILURE and receipts == []`、:303-305 checkpoint 无 source_reports、:306-308 公开结果 `result.answer is None and result.receipts == ()`。
改这些断言 = 改冻结 oracle = 变更单（AGENTS.md §6"禁止为了通过测试…删难题…"；batch22 计划 Root-batch22-plan.md:19"公共合同/金标/阈值/分母变更"不做）。

**路径 B：在 DTO 层加字符串字节上限（StructuredFactProofRead/SourceReportedFact）** —— 否决。
- 同一 unit 测试的大报告向量依赖无字节上限的字符串构造：test_r14_source_report_output_budget.py:445-451 `StructuredFactProofRead(..., missing_requirements=("中"*5000,))` 必须可构造，否则该冻结测试在构造处即失败。
- `StructuredFactProofRead` 是跨 r07/r14 链的公共读模型：unit 测试直接从 `test_r07_source_report_reader.read_case`、`test_r14_shared_read_consumers.consumer_fixture` 导入夹具（test_r14_source_report_output_budget.py:17-18, 55）；integration 侧 `seed_facts` 来自 test_r07_structured_fact_proofs_pg.py（test_r14_source_report_output_budget_pg.py:12）。改字段域 = 波及多文件冻结夹具与合同测试。

**路径 C：只改预算参数/默认值** —— 否决。
`WorkflowBudget.max_output_bytes` 是公开请求 DTO 域字段（graph_contracts.py:62），integration 测试以 `getattr(request, "param", 262144)` 锚定默认（test_r14_source_report_output_budget_pg.py:49）并以 1024 作参数化预算。动默认/上限属阈值变更。

**补充：任何会计语义变更都有版本栅栏**。改输出会计行为须同步 bump `OPERATION_OUTPUT_ACCOUNTING_VERSION`（workflow_service.py:135；装配点 :360-362；unit 钉定 :241, :272-275），其"配置变更 → 存量工作流 stale、不重放不改写历史"的栅栏行为本身被冻结（integration test_r14_source_report_output_budget_pg.py:247-282）。栅栏不是障碍，但 bump 是变更单级动作的设计触发器。

### 3.2 结论

**不可做**——但按 batch22 计划的两分支语义，这是"触合同停止"，不是"无事可做"：
- "计量"已存在且 UTF-8 正确（§1.2/§1.3），无最小补丁可写；
- "行为"实现（A/B/C 任一路径）必然修改冻结断言或公共 DTO/阈值 → 全部落入变更单范围（AGENTS.md §5/§6；Root-batch22-plan.md:11 的停止条件、:19 的明确不做清单）。

**停止点**：本项到此为止，不写任何业务代码。建议追记 OQ：登记"富化输出行为级 UTF-8 预算（trim-to-fit）"为待变更单事项，附本报告 §3.1 的三条否决路径与 §4 冻结清单作为变更单的必改面清单。

**若未来获批变更单，最小实现路径（供参考，非本轮执行）**：
1. 变更单明确行为语义（推荐：按 UTF-8 字节贪心裁剪 `source_reports` 内字符串/事实项，输出新增 `source_report_budget_status` 类标记键——新键而非改值，最小化 schema 面变化）；
2. bump `OPERATION_OUTPUT_ACCOUNTING_VERSION`（workflow_service.py:135）使存量工作流按冻结栅栏安全 stale；
3. 重钉 §4 清单中的 oracle 断言（这是唯一合法的断言修改方式）；
4. 直属测试设计：unit 侧复用 accounting_fixture/consumer_fixture（test_r14_source_report_output_budget.py:71-105）加"恰好落入预算/差一字节拒绝/裁剪后 checkpoint 与公开结果一致性"三组；integration 侧沿用 1024 预算参数化（test_r14_source_report_output_budget_pg.py:99, 143, 285）。

## 4. 相关既有测试的冻结语义（不可动清单）

| 文件:行 | 冻结内容 |
| --- | --- |
| backend/tests/unit/test_r14_source_report_output_budget.py:108-112 | `_output_json_bytes` 恒按真实 UTF-8 计数（含 NaN 拒绝），专名 "frozen encoding" |
| 同上 :115-128 | 完成判定按候选实际字节计数、保留他者 pending 预留、原始 dict 不被变异 |
| 同上 :131-152 | 实际字节取代原预留进入下次累计预算；小节点槽位不虚增预算 |
| 同上 :155-175 | 拒绝回执不可变、不可二次输出；成功回执不可被不同值覆盖 |
| 同上 :178-189 | 无失败容量时节点不得启动 IO |
| 同上 :192-217 | 被拒大节点不入返回值与 checkpoint（B2/B2b/B3 全策略） |
| 同上 :220-233, :476-552 | tool/model 完成拒绝路径同样不返回值（budget failure 传播） |
| 同上 :236-259, :570-576 | budget failure 恢复优先于 unknown 与旧 verified 状态，旧结果清空 |
| 同上 :263-287 | 默认装配钉定 `SOURCE_REPORT_CONSUMER_VERSION` / `OPERATION_OUTPUT_ACCOUNTING_VERSION` |
| 同上 :290-341 | 富化 receipt 形状钉定：reason_code ∈ {enrichment_write_adapter_not_configured, source_reports_partial, source_reports_not_found}、status="partial"、output 键集与事实字段（condition_value/freshness/claim_origin="structured_source"） |
| 同上 :344-380 | 8 引用共享单一 deadline、64 事实全保留 |
| 同上 :383-433 | 失败分类钉定：timeout→source_report_deadline_exhausted 且 source_reports==[]；epoch→WorkflowChangedError；空引用→source_report_references_missing 且零 IO |
| 同上 :435-473 | 大报告整体拒绝 oracle（本项最直接的禁行线） |
| 同上 :555-567 | `MAX_WORKFLOW_OPERATIONS` 第 24 行拒绝（operation_count_invalid） |
| 同上 :579-586 | 节点预留 deadline 与输出预算语义分离 |
| 同上 :589-617 | PG statement/lock timeout 与数据库失败分类分离 |
| backend/tests/integration/test_r14_source_report_output_budget_pg.py:63-96 | 真实 PG 富化输出形状 + 重放回执逐行等值 |
| 同上 :99-140 | 中文超预算失败保留预留、重放回执、output_bytes==OUTPUT_BUDGET_FAILURE_BYTES |
| 同上 :143-183 | 完成 actual 与 pending 预留共享同一累计预算；并发完成由工作流锁串行化 |
| 同上 :186-244 | 源 IO 前重校验 ACL/epoch/lease（变更即异常、行保持 reserved） |
| 同上 :247-282 | 配置版本变更 → stale、不重放、不改写历史 |
| 同上 :285-308 | 大报告不入 graph checkpoint 与公开结果（B2/B2b/B3 × 1024） |
| backend/tests/unit/test_read_source_mode_dto.py:1-11, 64-169, 172-181 | DataMode fail-closed oracle + strict xfail 变更单绊线（B5.2 产物） |

## 5. 调研过程记录（真实性）

- 方法：只读 grep/Read + `git log/show --stat` 只读命令；未修改业务文件；未运行 pytest（按授权只读）。
- 测试现状佐证（引用既有证据，未复跑）：unit 文件属 OQ-2 环境回归修复后 4 文件 165 passed 全绿（progress/OPEN_QUESTIONS.md:30、Root-batch20-summary.md:78）；PG 侧文件在 batch21 容器 integration 退出码 0（reports/runs/batch21_integration_unlocked/container_run_summary.txt:638, :874；inventory.md:70 记 7 例）。
- B5.2/B5.3 原始计划文本未入库：git 全历史 `-S "B5.3"` 检索仅命中 reports/tasks/Root-batch20-summary.md 与 Root-batch22-plan.md（提交 d21922041、4c6ff75ac），本调研以两份总结的记录为 B5.2 事实源。
- batch22 目标1 的 (d) 类甄别尚未产出报告（reports/runs/ 仅有 batch22_timeline.md），本文件与目标1 无重叠文件。

本次写作结束时间：2026-10-25T04:48:02+08:00；本文件为只读调研产物，不含任何实现与状态变更。
