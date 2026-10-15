# R05 引用问答内核交付

状态：`awaiting_review`。本工作包实现 `complete`，仅指公开来源回答内核；整张 R05、T31 和 R12 的最终验收范围未缩减，未自行签 `accepted`。

最新候选：独立初审在下述 `c1804d0` 发现一个 scope 误拒 Must；修复业务冻结为 `b1511145d4e6c15c5b1f6595bb7c776781ecf2ab`，仍 `awaiting_review`，详见文末“独立初审 Must 1 修复”。前面的首次交付、失败与覆盖率记录保留为历史，不代替新版本的独立复核。

起点：`afe490ce15e567bf916d2e7b970354ddff3e193e`。业务代码先冻结为 `c1804d0a38cd4e451b801f1ec88df9c3c47629e0`，本报告与日志在后续独立提交中引用该 SHA。分支 `codex/r05-grounded-answer-core`，独立 worktree `C:/Users/yinha/.codex/worktrees/r05-grounded-answer-core/dianzi`。主仓已有未提交修改保持原样；没有 push。

## 范围与调用合同

新增五个业务/测试文件：

- `backend/src/ai_intel/answering/__init__.py`
- `backend/src/ai_intel/answering/contracts.py`
- `backend/src/ai_intel/answering/grounding.py`
- `backend/tests/unit/test_r05_grounded_answer.py`
- `backend/tests/contract/test_r05_grounded_answer_contract.py`

公共接口：`generate_grounded_answer(client: GenerationClient, question: str, evidence: tuple[CitationProjection, ...]) -> GroundedAnswerDraft`。调用者可以从 `answering.contracts` 导入 `AnswerClaim`、`GroundedAnswerDraft` 和 `GroundedAnswerFailure`。结果只包含 `answer_text/claims/citations/limitations/attempts`；没有新建 API 响应、持久化记录、模型网络客户端或 fixture 后备。

调用方在调用前与返回前重新鉴权、核验公开可见性及 epoch，并注入每次 `total_timeout_seconds <= 30` 的生产 `GenerationClient`。输入最多 20 个唯一 evidence ID，问题最多 4096 Unicode 字符，总输入文本最多 65536 UTF-8 字节。重复 ID 明确失败，不覆盖。输入投影及输出均检查非空、长度、NUL、UTF-8；模型输出限制最多 20 个 claim/citation、单项正文与引文最多 2048 字符。

首次生成与独立证据支持核验均使用递归 `extra=forbid` 的严格 schema、`allow_format_repair=False`，最多两次远程调用，输出 token 上限分别 4096 和 2048。外层 65 秒期限在调用前后核验，真实网络期限由现有网关和每次最多 30 秒的客户端控制。出现格式错、提供者错、支持失败、超时即安全失败；不会为了 repair 产生第三次调用。失败异常仅包含固定 `code` 与所有已经发生的 `AttemptMetadata`，费用未知保持 `unknown`。

模型仅选择输入 evidence ID 和 exact 单行 quote 子串；不允许模型重建 revision、URL 或 locator。程序保留原投影元数据，不标准化 CRLF、空白、标点或 Unicode 来伪造一致。事实至少一个支持 ID；数字和版本使用独立 token 边界比对，避免 `1.2.30` 支持 `1.2.3`。否定/未知检查使用完整输入片段，防止从“不受影响”裁出“受影响”绕过检查。

第二次调用获得所有原始证据、已选引文及服务器分配的 claim 编号，独立检查语义支持、主体、限定条件、冲突、数字和状态。verdict 必须恰好覆盖全部编号一次；缺失、重复、额外编号、布尔编号、`unsupported/unknown` 和失败检查字段均拒绝。项目建议也必须经过核验，并与来源事实分别标识。正文只由验证通过的 claims 编排；不接收额外自由正文或模型生成的 limitations，避免未验证事实夹带。

此切片没有 Assessment/规则执行器输入，`rule_result` 以 `answer_rule_result_unavailable` 失败，已向主控确认。私有资产、历史查询、多轮会话、检索、数据库、API 和 UI 接线归主控或 R12；没有伪造多轮能力。

## 真实检查结果

命令工作目录均为上述 worktree 的 `backend`，最终使用本 worktree 经 `uv sync --frozen` 创建的独立 `.venv`。以下时间为 2026-10-15、UTC+08:00。原始命令、开始/结束、退出码保存在对应 JSON 中，JUnit 保留每个案例结果。

| 检查 | 开始—结束 | 退出码 | 结果及日志 |
|---|---|---:|---|
| R05 unit/contract | 16:15:27.800—16:15:32.791 | 0 | 77 unit + 22 contract = 99 passed；本模块覆盖率 96.52%，门槛仍为 60%；[grounded_isolated.log](../runs/recovery_r05_grounded_answer_core_20261015/grounded_isolated.log) |
| R05 离线安全负例子集 | 16:14:20.798—16:14:23.193 | 0 | 23 passed、54 deselected；这是显式 R05 攻击边界子集，不计为全系统安全验收；[security_final.log](../runs/recovery_r05_grounded_answer_core_20261015/security_final.log) |
| T18/生成客户端相关回归 | 16:15:59.785—16:16:07.774 | 0 | 111 unit + 24 contract + 7 本机 socket = 142 passed；[t18_regression.log](../runs/recovery_r05_grounded_answer_core_20261015/t18_regression.log) |
| 扩大 unit/contract 回归 | 16:15:27.801—16:16:06.876 | 1 | 970 passed、1 error、1 warning；整库覆盖 70.75% 达到 60%，既有 T07 PG 合同缺隔离测试配置；[unit_contract_isolated.log](../runs/recovery_r05_grounded_answer_core_20261015/unit_contract_isolated.log) |
| mypy 全源码 | 16:15:27.854—16:15:29.018 内 | 0 | 75 source files，无问题；[mypy_final.log](../runs/recovery_r05_grounded_answer_core_20261015/mypy_final.log) |
| Ruff / format | 同上 | 0 / 0 | 五个新增文件通过；[ruff_final.log](../runs/recovery_r05_grounded_answer_core_20261015/ruff_final.log)、[format_final.log](../runs/recovery_r05_grounded_answer_core_20261015/format_final.log) |

实际最终命令：

```text
uv run --frozen pytest tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py --cov-reset --cov=ai_intel.answering -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/grounded_isolated.xml
uv run --frozen pytest tests/unit/test_r05_grounded_answer.py -k security --no-cov -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/security_final.xml
uv run --frozen pytest tests/unit/test_r05_generation.py tests/unit/test_r05_generation_review_fixes.py tests/contract/test_t18_model_clients.py tests/contract/test_r05_generation_wire.py tests/integration/test_r05_generation_http.py --no-cov -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/t18_regression.xml
uv run --frozen pytest tests/unit tests/contract -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/unit_contract_isolated.xml
uv run --frozen mypy src
uv run --frozen ruff check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
uv run --frozen ruff format --check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
```

最终两条 coverage 命令分别设置 `COVERAGE_FILE=../reports/runs/recovery_r05_grounded_answer_core_20261015/.coverage.grounded_isolated` 和 `.coverage.unit_contract_isolated`。没有修改配置、阈值、金标、分母或失败用例。本任务 coverage 用 `--cov-reset` 明确限定新增模块；扩大回归另保留冻结全库 `--cov=ai_intel --cov-fail-under=60`，未被任务模块范围替代。

业务代码提交的 `git diff --cached --check` 为 0。证据提交的相同命令报告七处 pytest 原始失败日志/JUnit 自带行尾空白；这些原始输出保持未改写，没有把该检查记录为通过。报告本身的本地链接检查通过。

覆盖正例、无证据、删唯一证据、输入类型/大小、重复 evidence、伪造 span、错误版本与数字、明确否定/未知、冲突核验失败、引文 CR/LF/CRLF/Unicode 边界、建议夹带事实、额外字段、空/重复/遗漏/编造 verdict、第三次调用防护、提供者网络失败/超时与 attempts 保留。测试使用明确合成证据和隔离网关替身；没有真实产品模型调用，不能把这些断言计为问答准确率或模型 live。

## 失败、阻塞和过程记录

扩大回归唯一 error：`tests/contract/test_t07_jobs_outbox.py::test_transient_failure_parks_in_retry_wait_then_retries_exactly_once`，fixture 报 `blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier`。没有注入或猜测隔离 PostgreSQL 连接信息，没有改成 skip。最小所需资源为项目隔离规范允许的 run ID 与测试 PostgreSQL 环境；此既有资源缺口不影响新增纯内核用例。

初次开发检查出现前置类型注解的 NameError，导致两项 collection errors，随后加 `from __future__ import annotations` 修正；未把它归为环境缺失。首次保存的定向运行 88 passed、1 failed：测试在构造 `CitationProjection` 时已被 Pydantic 拦截不合法 UTF-8，未进入内核；测试改为通过 `model_copy` 构造受损投影，验证内核再次拒绝。后续 89 条以及最终新增边界后的 99 条通过。失败日志 [targeted_01.log](../runs/recovery_r05_grounded_answer_core_20261015/targeted_01.log) 保留。

第一次扩大回归共享主仓 `.venv` 的 editable 路径，覆盖源同时包含主仓和 worktree，输出 49.00%，未达 60%，保留 [unit_contract.log](../runs/recovery_r05_grounded_answer_core_20261015/unit_contract.log)，不作为最终代码覆盖证据。改用本 worktree 独立冻结环境后，一次并行测试又争写 `.coverage`，出现 `no such table: line_bits`；[unit_contract_own_env.log](../runs/recovery_r05_grounded_answer_core_20261015/unit_contract_own_env.log) 与该次 `grounded_final` 覆盖率不采信。最后使用两个独立 coverage 数据文件复跑，产生上表结果，没有扩大业务补丁或放宽门槛。

首次业务修改前使用官方 CBM CLI 0.11.0：WSL 可执行路径 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，独立 `CBM_CACHE_DIR=/tmp/r05-grounded-answer-core-cbm`。实际核对 `--help`、`index_repository --help`、`get_graph_schema --help`、`search_graph --help` 与 `trace_path --help`，对 worktree `backend/src` 执行 `index_repository --mode full --persistence false --name r05-grounded-answer-core`，958 nodes、4533 edges、零未索引/跳过/partial/unusable；[cbm_index.log](../runs/recovery_r05_grounded_answer_core_20261015/cbm_index.log)。schema 实际返回 Class/Method/Function/CALLS/IMPORTS 等图类型。短名称 trace 初次 `function not found` 保留，随后使用精确限定名 `r05-grounded-answer-core.ai_intel.infrastructure.models.generation.GenerationClient.generate`，得到 27 个调用节点、0 个生产调用者；[cbm_trace.log](../runs/recovery_r05_grounded_answer_core_20261015/cbm_trace.log)、[cbm_generate.log](../runs/recovery_r05_grounded_answer_core_20261015/cbm_generate.log)。已通过 `rg` 与 `generation.py`/`knowledge_contracts.py` 源码交叉核验。

## 八层验证及评分证据

| 层 | 本切片状态 | 解释 |
|---|---|---|
| unit | passed | 新内核 77 条及相关回归通过 |
| contract | passed（本切片） | 新 schema/API shape 22 条通过；扩大合同中的既有 T07 资源 error 保持 blocked |
| integration | not_run（问答产品链路） | PG/API 尚未接线；已有客户端 7 条本机 socket 回归通过，不冒充问答集成 |
| security | passed（离线边界子集） | 23 条明确负例；ACL/租户/epoch 全链路由主控接线后验收 |
| frontend | not_run | 不在此工作包文件边界 |
| e2e | not_run | 未接网页/数据库链路 |
| live | not_run | 本 Agent 实际产品外部调用 0；未读取凭据或调用付费模型，不用替身充 live |
| manual | not_run | 无人工金标或人工支持复核 |

F3/R1 证据：已验证 claims、来源修订/位置/URI、否定未知保留、引用存在与语义支持两道检查。P3 只有有界调用与可复跑内核，没有完整响应性能、多跳准确率或 ≤5 秒证明。模型支持核验是辅助检查，不能当成人工金标、事实真实性或正确率证明；保守词表可能拒绝包含多个不同事实/状态的较长片段，复杂语义仍需独立评测。

合同/计划偏差：没有修改公共 schema、依赖主版本/锁、全局设置、认证、迁移、progress、金标或评分分母。原 T31-C02 多轮与 C06 会话权限、R12 的混合检索/必要多跳/历史/资产最终范围保留，未在此切片声称实现。

下一建议：主控集成代码 SHA 与报告证据，另派非作者进行独立复核；随后在已授权生产客户端和公开有效证据上接 PG/API/UI，补真实两调用回答、失败映射、调用前后鉴权/epoch 检查和 e2e。不要把本内核自检状态直接登记为整卡或阶段 accepted。

## 独立初审 Must 1 修复 · 2026-10-15

原独立初审：`D:/dianzi/reports/reviews/recovery/G-B-R05-grounded-answer-review-1.md`，固定业务 `c1804d0`，结论 `needs_changes`。独立探针 `D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/test_independent_grounded_probes.py` 的四个正常输入确证：产品 A 已修复/受影响/不受影响，产品 B 另有未知或否定时，整个 quote 的状态词会在第一调用后误拒 A，第二核验没有机会执行。

本轮在原独立 WT、父提交 `90f0c98` 先原样重放四例，业务未改时得到 **4 failed、24 deselected、exit 1**，16:34:53.409—16:34:54.925 UTC+08；[red_probe.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/red_probe.log)、JUnit/JSON 同目录。不是环境缺失，不改原输入或删 B 的未知。

修复只改 `grounding.py` 和直接 `test_r05_grounded_answer.py`，冻结业务 `b1511145d4e6c15c5b1f6595bb7c776781ecf2ab`，立即交主控和原 reviewer，之后只写此报告/证据。公共函数、结果字段、schema、锁、预算、认证、数据库、API、progress、阈值、金标、分母均未修改；没有 push、spawn 或签 accepted。

本地未知/否定校验收窄为：去掉明确状态标记后，完整来源命题与 claim 的其余文字必须相同，才据此阻止字面同命题状态变化。不同对象、额外谓词、条件、句子或改述不能凭任意词命中强制传播状态，均进入本来就必须执行的独立支持核验。它不是实体解析器，不新增猜测分句/主体的规则。本地数字/版本、精确 quote、支持 ID、结构与调用上限检查继续执行；同命题“不受影响→受影响”“未确认→未受影响”“未观察到→观察到”仍在第一调用后拒绝。

核验仍取得全部原始 quote，包括未被选入答案的产品 B 状态、同对象其他条件和冲突。提示词明确以**同主体、谓词、适用范围和时间**检查相反/未知信息，防止裁剪否定和跨对象借支持；不同对象/谓词的信息不强制传播。prompt 版本更新为 `r05-grounded-answer-2`，输出 schema 版本未变。第二 verdict `unsupported/unknown` 或状态检查失败仍安全失败，保留两次 attempts；没有重写或第三调用。

原 99 个业务案例保持输入和接受/拒绝结果。其中“修复版本未知→已完成修复”和“No evidence of exploitation→Exploitation has occurred”属于语义改述，不能用不同文字证明同一命题，本轮保留这两个负例，增加明确 `unsupported/states_preserved=false` 核验响应，断言 **2 calls/2 attempts/安全拒绝**；其余原样断言保留，没有 skip 或降低拒绝要求。新增 14 例：四个原正常探针、同句多对象/不同谓词四例、同主体未知/范围省略/跨对象借引文/否定裁剪五例、注入且拒绝第三调用一例。

| 本轮检查 | 开始—结束 UTC+08 | exit | 真实结果 |
|---|---|---:|---|
| 原 99 + 新 14 内核 unit/contract | 16:42:10.968—16:42:15.466 | 0 | **113 passed**：91 unit、22 contract；模块 coverage **96.63%**，原门仍 60；[grounded.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/grounded.log) |
| reviewer 原文件完整重放 | 16:43:13.380—16:43:15.710 | 0 | **28 passed**，四个原正常误拒输入转为两次核验后返回；这是作者重放，不代替独立复核；[independent.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/independent.log) |
| 安全边界子集 | 16:43:13.320—16:43:16.324 | 0 | **29 passed、62 deselected**，包含原 23；[security.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/security.log) |
| T18/生成必要回归 | 16:43:13.321—16:43:22.763 | 0 | **142 passed**，111 unit/24 contract/7 本机 socket；[t18.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/t18.log) |
| 完整 unit，冻结整库门 | 16:43:13.365—16:43:42.776 | 0 | **777 passed、1 warning**；3714/5634 = **65.92%** 达到原 60；[full_unit.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/full_unit.log) |
| mypy/Ruff/format | 16:44:04.462—16:44:05.611 | 0/0/0 | 全 75 source files 类型通过，五个内核/直接测试文件代码与格式通过；[static.json](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/static.json) |

各行完整 executable 参数、cwd、时间和退出码见同目录对应 JSON；JUnit、独立 `.coverage.grounded`/`.coverage.unit` 保留，不共用 coverage 文件。实际命令是在本 WT `backend` 执行以下 pytest 文件参数与原始表中的 JUnit 路径：

```text
uv run --frozen pytest tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py --cov-reset --cov=ai_intel.answering -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/grounded.xml
uv run --frozen pytest D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/test_independent_grounded_probes.py --no-cov -q --tb=short --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/independent.xml
uv run --frozen pytest tests/unit/test_r05_grounded_answer.py -k security --no-cov -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/security.xml
uv run --frozen pytest tests/unit/test_r05_generation.py tests/unit/test_r05_generation_review_fixes.py tests/contract/test_t18_model_clients.py tests/contract/test_r05_generation_wire.py tests/integration/test_r05_generation_http.py --no-cov -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/t18.xml
uv run --frozen pytest tests/unit -q --junitxml=../reports/runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/full_unit.xml
```

本轮改业务前复用已核对 help/schema 的官方 CBM CLI 与独立 cache，重新索引该 WT `backend/src`、追踪 `validate_citations`，992 nodes/4687 edges，未索引/skip/partial/unusable 均 0；[cbm_before_fix.log](../runs/recovery_r05_grounded_answer_core_20261015/scope_fix_1/cbm_before_fix.log)。源码/`rg` 交叉后仅收窄原状态分支，未变外部调用点或客户端。

八层状态仍限本内核：unit/contract/离线 security `passed`；问答 PG/API integration、frontend、e2e、live、manual `not_run`。既有 T07 隔离 PG error 保留原日志与阻塞，本轮按主控要求不为无关测试扩迁移或造 fixture。真实产品外部调用仍 0，费用 unknown。模型语义核验不是人工金标或准确率证明，提示词范围检查的真实模型效果仍需 live/人工配对，不能把作者重放 28 passed 当独立 reviewer 已批准。

下一步：原非作者 reviewer 在 `b151114` 上定向重放四个正常输入、同对象未知/否定/范围与注入配对，并检查两调用上限；主控依据新 reviewer 结论决定集成。该修复候选只交 `awaiting_review`，不扩大原 R05/R12 完成范围。
