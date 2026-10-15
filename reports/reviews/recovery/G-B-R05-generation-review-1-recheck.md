# G-B / R05 · 生成客户端独立定向复验 1

> 最新限定状态（2026-10-15T15:00:05+08:00）：31c2866 上两项 Must fix 已独立关闭。原8f6的两条deferred失败保留在下文；技术复验通过不代表产品live、接线或R05/G-B验收。

What this change does: 新补丁在拼请求前检查版本标识中的已知凭据，并沿 Pydantic 实际验证图检查嵌套对象的额外字段策略。本次从新的干净工作树复跑原失败探针，同时检查修复的递归、展示 hook 和延迟构建边界。

首次创建/本段写作结束：2026-10-15T14:55:50+08:00；实际审查计时 `2026-10-15T14:50:57+08:00` 起。审查者 `/root/r05_generation_independent_review`，未参与实现；状态 **needs_changes**：Must 1 已关闭，Must 2 的原触发已修复，但新确证的 `defer_build=True` 分支仍未关闭。没有 accepted、push、产品 live 或接线验收。

## 新固定版本与修改边界

- 被审集成提交 `8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce`，根 tree `1b9a94ac49b58ddd12debb40f173749dbd3110a7`。对应作者源码 `691a20db07d6594faf35c2cb1de738edcca6c617`；证据提交 `4311072d76d303730769b32eaaa33856a262d744` 不作为源码修改。
- 新独立分支 `codex/review-r05-generation-recheck-20261015`，干净工作树 `C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1-recheck/dianzi`。只审 `436455d → 新提交` 的 models 修复和直接回归；并复跑共享 POST/HTTP 安全路径。其他来源/分页/UI 变动不在此重新验收。
- 再核对 AGENTS、执行地图、恢复 R05、原引用合同、状态/交接与固定 diff；沿用初审已读新版 Ponytail 5.2 review 要求。未改业务、合同、状态、锁、金标、分母或阈值。
- 新独立 venv `C:/Users/yinha/.codex/review-r05-generation-1-recheck-runtime/.venv`，`uv sync --locked` 实际成功；每个 `COVERAGE_FILE` 位于该仓外 runtime，未使用原审查或主控的环境/覆盖率库。无 PostgreSQL、真实 key 或供应商请求。

## Must 关闭结果与剩余缺陷

**Must 1：关闭。** 原独立 v2 两个完整合成凭据版本字段失败例均转绿；额外独立 12 例覆盖两 provider × 三版本字段 × 完整/前后缀匹配。通过对 `require_strict_schema`、`encode_wire` 安装失败哨兵，证明实际在 schema、body 和网络前返回固定 `model_credential_in_input`；零请求、空 attempts，异常不含被测凭据。

**Must 2：原触发关闭，整体仍需修复。** 原 TypedDict/dataclass 显式 ignore 两例已转绿；额外独立容器、allow、默认继承、forbid、递归定义、实际严格解析、真实 JSON-schema hook 伪造 `additionalProperties=false` 都通过。

1. **延迟构建的验证图被静默跳过**（延续 Must 2，P2，`backend/src/ai_intel/infrastructure/models/generation.py:138`–`:170`）。
   - **职责：**调用前检查实际输入验证图，危险 schema 不得联网，也不能静默丢额外字段。
   - **触发：**可信 schema 使用 Pydantic 官方 `ConfigDict(defer_build=True)`。分别测试根 `extra='ignore'`，以及根 `extra='forbid'` 嵌套 `TypedDict(extra='ignore')`；生成调用前 `__pydantic_complete__` 明确为 False。
   - **实际结果：**`__pydantic_core_schema__` 尚是 `MockCoreSchema`，不是检查循环处理的 dict/list/tuple，因此整个预检被略过。后续 `model_json_schema()` 才构建实际验证图，两个响应含 `extra` 都实际生成 `succeeded`、字段被丢弃，两个 `pytest.raises` 均失败（DID NOT RAISE）。这不是任意自定义 validator 的信任问题，也不是 reviewer harness 错误。
   - **最小修复与复验：**先通过公开 `model_rebuild()` 确保实际验证图已建立，无法构建时安全拒绝，再检查 effective core graph；保留两个原字节独立 probe，另验证合法 deferred strict schema、递归 deferred schema 和已构建 schema 不回归。仅检查根 `model_config` 不能解决嵌套分支。
   - **不修影响：**同一个字段合同因 Pydantic 是否提前构建而改变，结构校验成功仍会静默丢模型新增字段。

探针 `reports/runs/recovery_r05_generation_review_1_recheck_20261015/test_deferred_core_schema.py` 与实际失败 receipt/log/XML 已在 `2026-10-15T14:53+08:00` 通知主控和原作者；本审查者未实现修复。

## 实际命令、起止和结果

所有命令 cwd 为上述新工作树 `backend`。完整 argv、环境说明和秒级时刻保存在同 label `.command.json`；原始 log/JUnit 同目录。表中省略号仅缩短排版，收据没有省略。

| label / 命令 | Asia/Shanghai 起止 | exit / 实际结果 |
|---|---|---|
| `original_independent_probe`：`uv run --locked pytest --no-cov …/test_generation_independent_boundaries_v2.py …/test_real_local_early_timeout.py -q --tb=short --junitxml=…` | 14:51:29–14:51:33 | 0；27 passed，0 failed/skip；包括原 v2 24 与真实本地 OS 早超时 3 |
| `original91_new43`：`uv run --locked pytest --no-cov tests/unit/test_r05_generation.py tests/unit/test_r05_generation_review_fixes.py tests/contract/test_r05_generation_wire.py tests/integration/test_r05_generation_http.py tests/contract/test_t18_model_clients.py -q --junitxml=…` | 14:51:29–14:51:40 | 0；134 passed，0 failed/skip；保留两 wire 本地 HTTP、原 T18 和修复回归 |
| `shared_post_timeout_r03`：`uv run --locked pytest --no-cov tests/security/test_r05_http_post.py tests/security/test_r05_transport_timeouts.py tests/security/test_r03_network_transport.py tests/contract/test_t08_network_redirects.py -q --junitxml=…` | 14:51:29–14:51:37 | 0；**115** passed，0 failed/skip；原 112 + Link guard 新 3，以实际 JUnit 为准，不写 114 |
| `unit_original_60`：`uv run --locked pytest tests/unit -q --cov-report=json:… --cov-report=xml:… --junitxml=…` | 14:51:29–14:52:08 | 0；**678** passed，0 failed/skip；1 条既有 TestClient deprecation warning；原 60% 门未改 |
| `independent_recheck_boundaries`：`uv run --locked pytest --no-cov …/test_independent_recheck_boundaries.py -q --tb=short --junitxml=…` | 14:52:40–14:52:42 | 0；35 passed；独立预编码哨兵、容器/allow/继承/forbid/递归、实际 schema hook 与严格 JSON 正负例 |
| `deferred_schema_probe`：`uv run --locked pytest --no-cov …/test_deferred_core_schema.py -q --tb=short --junitxml=…` | 14:53:15–14:53:17 | 1；**2 failed**，0 errors/skip，均为上述确证业务失败 |
| `static_ruff` / `static_format`：`uv run --locked ruff check src tests`、`ruff format --check src tests` | 14:53:55–14:53:55 | 均 0；Ruff 无发现，166 文件格式通过 |
| `static_mypy`：`uv run --locked mypy src` | 14:53:55–14:53:56 | 0；72 source files 无错误 |

集成提交的原始 unit 覆盖率：**3511/5421 = 64.76664821988562%**，1910 missing / 42 excluded。来自本次 `unit_original_60.coverage.json`；作者较小基线的 617 项 / 5364 分母不替代本次集成版本。额外来源测试增加单元数量不代表本审查重签来源业务。

原 v2 与本地 early-timeout 脚本按原字节复制，SHA256 分别为 `831cf259cabc44811e16780aff9f451ecb563fe8df3d50590f1201a579e3a684`、`9c7c714669d69903602c8f38890181adbb11f645fb9f4ff6bb9220ace4e540f2`；初审脚本和失败日志未覆盖。本次 35 例为新独立探针，并非仅复跑作者测试。

## 调用链、凭据与证据

CBM 0.11.0 新独立 cache `/tmp/dianzi-r05-gen-review-1-recheck-cbm-20261015` / project `r05_gen_review_1_recheck_20261015`，只索引新工作树 `backend/src`，fast / persistence=false：958 nodes / 4496 edges，72 Python 文件；parse partial/unusable/skipped 0，排除 11 个生成的 `__pycache__` 目录。schema、architecture、`trace_path(require_strict_schema,both,depth=3)` 原始结果保留；没有索引 holdout、秘密、报告或他人工作树。

`fixed_source_manifest.json` 保存 37 个固定源码/直接测试/合同文件的 captured SHA256、Git blob SHA1 和 Git blob 内容 SHA256；JUnit 逐 case 汇总及所有实际 receipt、日志、raw coverage 已保存。凭据形状扫描只针对固定审查文件和本轮证据，53 files、6 个命中均为显式合成 fixture/probe、0 未分类。真实产品凭据精确值/片段扫描 not_run，由主控在集成前另做，本审查者未读取真实 key。

**not_run / 未验收范围：**产品 API/worker/QA 接线、真实 PG 用量与外发授权集成、供应商 live、真实公网 DNS/CA/peer、embedding/rerank/pgvector、证据支持与唯一证据删除、浏览器问答、性能和持续运行。产品模型调用 0，费用 unknown。可信自定义 Python validator 自行改写输入属于业务代码信任边界，本轮不宣称能证明任意代码无损。

本轮无新服务/数据库资源；所有本地 socket/server/线程在 finally 中关闭/join，测试与静态进程已退出。新旧审查工作树干净固定，仓外 runtime/coverage 仅留复现文件。报告不改 progress，不自签整 T/R05/G-B。

Verdict: **fix Must 2 deferred-build branch first.** 修复后需在新的固定提交追加独立定向复验，保留本轮两条红色原始证据。

## 第二次固定补丁复验 · 2026-10-15T15:00:05+08:00

**最新限定结论：初审两项 Must fix（包含延迟构建分支）在 `31c2866ff19227e5f6ee24f1f966660c0d4ba383` 上独立关闭，本次生成客户端/共享 POST 技术复验通过。** 本文上方 `8f6bd9f` 的 needs_changes 与两条失败是历史证据，原字节保留；本结论不改 progress/accepted，不签整 R05、G-B、产品接线或供应商 live。

### 新固定对象和修复核对

- 新干净分支 `codex/review-r05-generation-deferred-20261015`；工作树 `C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1-deferred/dianzi`；HEAD `31c2866ff19227e5f6ee24f1f966660c0d4ba383`，根 tree `c0c4659b8c1c392eba67c22d15939bae6032bd36`。计时开始 `2026-10-15T14:56:59+08:00`。
- `8f6 → 31` 仅 generation 与直接回归两文件变动。审查确认预检先使用公开 `model_rebuild(raise_errors=False)` 建立实际验证图；无法构建/预期构建异常固定拒绝，然后沿相同有效 core graph 检查，未使用 JSON Schema 展示 hook 作为真实性依据。
- 新仓外 venv/coverage 根 `C:/Users/yinha/.codex/review-r05-generation-1-deferred-runtime/`；实际 `uv sync --locked` 成功。初审、8f 和 31 三个工作树/环境均隔离，测试未接触真实 key、数据库或供应商。

### 原失败与独立正负例

原 `test_deferred_core_schema.py` **未改字节**，根 ignore 与根 forbid+嵌套 ignore 两个原始红例均通过，零请求/空 attempts。此前原 v2 的凭据版本和 TypedDict/dataclass 四个原始失败也保持转绿。

本审查者新增独立 5 例，实际验证 deferred 默认继承的 dict/list/TypedDict 容器、deferred 递归 BaseModel 的完整严格 JSON 成功与额外字段失败、无法解析的 deferred 引用返回固定错误且不回显敏感型名。与原独立 24、第一轮新增 35、原 deferred 2、实际本地 OS 早超时 3 合并为 **69 个独立 probe**，全部通过。这里包含实际 JSON 解析正负例；不是只确认“schema 没报错”，也不是仅复跑作者测试。

### 本次真实复跑

完整 cwd/argv/秒级起止/exit 在 `reports/runs/recovery_r05_generation_review_1_recheck_20261015/candidate_31c2866/` 的同名 `.command.json`；各 log/JUnit 原样保存。输入 probe 仍位于上一段已封存的父 run，收据列出精确绝对路径。

| label / 命令范围 | Asia/Shanghai 起止 | exit / 实际结果 |
|---|---|---|
| `independent_all`：`uv run --locked pytest --no-cov` 原 v2、独立 35、原 deferred、真实 local-timeout 和新增 deferred positive 文件 | 14:57:45–14:57:50 | 0；69 passed，0 failed/error/skip |
| `original91_new51`：`uv run --locked pytest --no-cov` 原生成60、新修复51、wire18、本地HTTP7、原T18六 | 14:57:45–14:57:56 | 0；142 passed，0 failed/error/skip |
| `shared_post_timeout_r03`：原相同四文件 POST/TimeoutError/R03/T08 | 14:57:45–14:57:53 | 0；115 passed，0 failed/error/skip |
| `unit_original_60`：`uv run --locked pytest tests/unit -q --cov-report=json:… --cov-report=xml:… --junitxml=…` | 14:57:45–14:58:27 | 0；686 passed，0 failed/skip；1 条既有 TestClient deprecation warning |
| `static_ruff` / `static_format`：Ruff `src tests` 与 format `--check src tests` | 14:58:25–14:58:25 | 均 0；166 文件格式通过，lint 无发现 |
| `static_mypy`：`uv run --locked mypy src` | 14:58:25–14:58:26 | 0；72 source files，无错误 |

本次原始 unit 覆盖率 **3515/5426 = 64.78068558791006%**，1911 missing / 42 excluded，来自此候选自己的 `unit_original_60.coverage.json`；原 `--cov-fail-under=60` 未改，没有借用较早版本覆盖率或跳过失败。各组有重叠，不能将通过数量相加成独立业务样本数。

### 最终证据与未查项

`candidate_31c2866/fixed_source_manifest.json` 对 37 个固定文件重新记录 captured/Git blob 双摘要及 CRLF 差异，`junit_summary.json` 逐 case 留档。CBM 独立 cache `/tmp/dianzi-r05-gen-review-1-31-cbm-20261015`、project `r05_gen_review_1_31_20261015`，仍仅本工作树 `backend/src`：958 nodes/4496 edges，72 Python 文件，parse partial/unusable/skipped 0；schema/architecture/trace 原始查询保留。

此次候选凭据形状扫描 44 files、6 命中均显式合成 fixture/probe、0 未分类；真实产品 key 精确/片段扫描仍 not_run，由主控独立执行，不能把本审查形状扫描表述为持有真 key 的扫描。产品模型调用 0，费用 unknown。

**仍未验收：**产品 API/worker/QA、PG 用量和认证上下文外发许可、供应商 live、公网 DNS/CA/peer、embedding/rerank/pgvector、引文语义/删除唯一证据、问答浏览器闭环、性能和持续运行。可信自定义 Python validator 的任意改写仍是业务代码信任边界，不在本限定证明范围。

三个固定源码工作树均 clean；未创建服务或数据库。所有测试、静态与 CLI 子进程均结束，本地 fixture socket/server 关闭和线程 join 断言通过。仓外 venv/coverage 与 clean 工作树只保留可复现文件，没有等待中的任务、后台监测或付费调用。封存本报告与证据后释放当前审查槽。

Verdict: **Ship — 仅限上述固定生成客户端/共享 POST 技术范围。** 下一步由主控按既有授权执行有限供应商 live 和产品接线；此处不代签这些结果。

