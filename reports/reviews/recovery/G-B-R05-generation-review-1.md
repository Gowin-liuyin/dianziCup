# G-B / R05 · 生成客户端与共享 POST 独立技术初审

What this change does: 本补丁为四个固定官方目标实现 OpenAI/Anthropic 两种结构化生成协议，共用受控 JSON POST、严格输出解析和整次预算。它尚未接入产品 API、worker、检索或问答页面。

首次创建/初审写作结束：2026-10-15T14:41:46+08:00；审查者 `/root/r05_generation_independent_review`，未参与实现。审查执行开始 `2026-10-15T14:31:32+08:00`，各命令实际秒级起止见收据。初审状态 **needs_changes**：两项确证 Must fix，已逐项通知主控与原作者；没有自行更改任务状态、合同或业务代码。后续定向复验必须另列新固定版本，不能覆盖本节失败结果。

## 固定对象、依据和边界

- 固定提交 `436455d0dedd7b125740b0d0a823a9563755e8a5`，根 tree `202f93dd517cf1e884d78a3a10a783d1ca12ed05`。
- 干净独立分支 `codex/review-r05-generation-20261015`；工作树 `C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-1/dianzi`。未在主控正在变化的源码目录审查；初始和封存源码工作树 `git status --porcelain` 均为空。
- 读取 AGENTS、00 执行地图、恢复 R05 卡、原 T18/T20/T30/T31/T43、所引架构/数据/流程/API/测试/资源/交付合同、任务状态和交接、`CR-R04-R05_model_post.md`；按新版 Ponytail 5.2 `ponytail-review` 沿调用链审查。调用权限来自本次明确授权，外部内容不作为权限指令。
- 核心范围：`infrastructure/models/{generation,json_output,clients}.py`，共享 `network.py` JSON POST 和 `http_transport.py` 的单次 POST / TimeoutError 分类，以及直接测试和调用边界。未扩大到来源 writer、分页修复或其他正在实现的模块。
- 只新增本报告与 `reports/runs/recovery_r05_generation_review_1_20261015/` 证据。没有改金标、分母、阈值、依赖、认证、合同、progress 或业务源码；未提交、push、付费调用或读取真实产品凭据。

## Must fix

1. **版本元数据可带出已知完整凭据**（P1，`backend/src/ai_intel/infrastructure/models/generation.py:393`、`:459`）。
   - **职责：**生成客户端检查输入与上游响应中的已知凭据，并返回可公开留档的调用元数据。
   - **问题：**`prompt_version`、`schema_version` 不进入请求 body，因而绕过仅检查 body 的凭据检查；之后原样进入 `AttemptMetadata`。使用现有显式 fixture 的合成 key 分别作为这两个版本字段，均完成一次调用，`asdict(metadata)` 含完整合成 key。不是读取真实 key 或推测未来接线；24 项独立 v2 probe 中这两项实测失败。
   - **最小修复与复验：**在拼 body、联网和记录轨迹前，对所有将进入元数据的请求标识检查已知凭据；固定错误码，不能把秘密带入异常。分别复跑两版本字段，要求零网络、零泄漏；同时保留正常版本和上游 id/model 反射回归。
   - **不修影响：**一旦调用方把凭据误装配到版本字符串，受控结果与报告接口仍会公开它，违反秘密不能进入报告的边界。

2. **显式宽松的嵌套对象能绕过严格 schema 检查**（P2，`backend/src/ai_intel/infrastructure/models/generation.py:135`–`:148`）。
   - **职责：**调用前保证根和嵌套结构不静默接受额外字段。
   - **问题：**检查仅遍历 `BaseModel` 及 typing 参数；嵌套 `TypedDict` 或 dataclass 的独立配置没有检查。根 `BaseModel(extra='forbid')` 的 `nested` 子类型若显式 `__pydantic_config__=ConfigDict(extra='ignore')`，响应 `{"nested":{"required":1,"extra":"silently dropped"}}` 两种都一次调用 `succeeded`，并丢弃 `extra`。默认未覆盖配置的子类型会继承 forbid，不属于此缺陷。
   - **最小修复与复验：**拒绝这些宽松嵌套对象，或检查最终 JSON Schema 中含 `$defs`/`$ref` 的所有对象的额外属性规则。复跑 TypedDict/dataclass 的显式 ignore/allow 与合法 forbid，证明危险 schema 在网络前被拒绝，合法 schema 的实际额外字段也会失败。
   - **不修影响：**“结构校验成功”与严格字段合同不一致，未来抽取候选可能静默丢弃模型新增字段。

两项在 `2026-10-15T14:36`–`14:37+08:00` 已附触发条件、定位和影响通知主控，原作者收到独立 v2 probe 的精确路径后修复；本审查者未实现补丁。

## 独立验证与原始结果

所有 pytest/static 命令 cwd 为上述工作树的 `backend`；Windows 11 / Python 3.12.13 / uv 0.10.9 / Pydantic 2.13.5。独立 venv `C:/Users/yinha/.codex/review-r05-generation-1-runtime/.venv`，`UV_PROJECT_ENVIRONMENT` 与每个 `COVERAGE_FILE` 位于仓外，不使用主控 `.venv`、覆盖率库或数据库。初始 `uv sync --locked` 实际成功；未创建 PostgreSQL 资源。

| 收据 label / 实际命令 | Asia/Shanghai 起止 | exit / 实际结果 |
|---|---|---|
| `target91`：`uv run --locked pytest --no-cov tests/unit/test_r05_generation.py tests/contract/test_r05_generation_wire.py tests/integration/test_r05_generation_http.py tests/contract/test_t18_model_clients.py -q --junitxml=…` | 14:33:39–14:33:48 | 0；91 passed，0 failed/skip。组成：新 unit 60 + wire contract 18 + 本地 HTTP 7 + 原 T18 6 |
| `unit_original_60`：`uv run --locked pytest tests/unit -q --cov-report=json:… --cov-report=xml:… --junitxml=…` | 14:34:17–14:34:51 | 0；574 passed，0 failed/skip，1 条上游 TestClient deprecation warning；原 `--cov-fail-under=60` 未覆盖 |
| `shared_post_timeout_r03`：误写不存在的 `tests/contract/test_t08_fetch_gateway.py` | 14:34:17–14:34:19 | 4；0 tests，环境/命令路径错误，保留日志，不计业务失败或通过 |
| `shared_post_timeout_r03_actual`：`uv run --locked pytest --no-cov tests/security/test_r05_http_post.py tests/security/test_r05_transport_timeouts.py tests/security/test_r03_network_transport.py tests/contract/test_t08_network_redirects.py -q --junitxml=…` | 14:35:07–14:35:11 | 0；112 passed，0 failed/skip，包括 POST 20 与 TimeoutError 4 负例 |
| `static_ruff` / `static_format`：`uv run --locked ruff check …`、`ruff format --check …` | 14:35:07–08 / 14:35:32–33 | 均 0；11 个直接相关文件格式通过，Ruff 无发现 |
| `static_mypy`：`uv run --locked mypy src` | 14:35:32–14:35:33 | 0；72 source files，无类型错误 |
| `independent_boundary_first`：`uv run --locked pytest --no-cov …/test_generation_independent_boundaries.py -q --tb=short --junitxml=…` | 14:36:29–14:36:30 | 1；20 passed / 4 failed。2 项版本凭据泄漏；另外 2 项是 reviewer harness 在 except 外引用已释放变量的 UnboundLocalError，不能算业务失败 |
| `nested_shape_inspect`：`uv run --locked python …/check_nested_schema.py` | 14:36:57–14:36:58 | 0；默认 TypedDict/dataclass 继承根 forbid，额外字段实际被拒绝，缩小缺陷条件 |
| `independent_boundary_v2`：`uv run --locked pytest --no-cov …/test_generation_independent_boundaries_v2.py -q --tb=short --junitxml=…` | 14:37:35–14:37:37 | 1；20 passed / 4 failed，均为上述两 Must 各两分例；保留首次脚本/日志，另建 v2，不覆盖历史 |
| `real_local_early_timeout`：`uv run --locked pytest --no-cov …/test_real_local_early_timeout.py -q --tb=short --junitxml=…` | 14:38:57–14:38:58 | 0；3 passed；实际本地 HTTP header/body/TLS handshake 由 OS 触发 25ms socket TimeoutError，而绝对 deadline 仍在未来 3 秒，均准确返回 NetworkTimeoutError |

完整 argv、cwd、环境隔离说明、起止与 exit 均在同名 `.command.json`，实际日志与 JUnit 同目录；表中省略号只为排版，收据没有省略。重复测试不能相加冒充独立样本数。

原始 unit 覆盖率：**3442 / 5356 = 64.26437640029873%**（1914 missing，42 excluded），来自 `unit_original_60.coverage.json`，XML 亦保留。分母来自固定集成提交，包含其他已集成源码，比作者较小工作树的 4760 大；没有删模块或降低原 60% 门。

复核的可观察边界包括 UTF-8/NUL/字节与结构限额、私有内容在 schema/body/network 前阻断、两种 wire 固定 path/Host/header/token 参数、精确 body 摘要、截断/拒绝/工具输出不执行、最多一次格式修复、修复共享输入/输出/calls/deadline、未知 usage 为 None/费用 unknown、网络/认证/quota 不自动重试。四个上游 id/model 完整 key 反射负例通过；模型/请求异常字符串不回显被测敏感输入。cache usage 错类型、元数据实际时点/耗时与 body hash 的已有及独立直接测试通过。

POST 与原 GET 共用 DNS 解析/固定 IP/peer/SNI/CA 校验、响应上限和并发/deadline；已有 socket fixture 对这些路径验证，真实本地测试仅覆盖明确列出的 HTTP/OS timeout 行为。本地 HTTP 的 DNS/TLS 路由替换是显式隔离 fixture，不能据此证明官方 DNS、真实公网 CA 或产品凭据可用。

## 调用链、配置和未查项

CBM 0.11.0 未注册为可用 MCP，使用已指定 portable CLI。先读取 help/schema，首次 schema 漏 project 的 error 原样保留；随后仅索引本审查工作树 `backend/src`，独立 `XDG_CACHE_HOME=/tmp/dianzi-r05-gen-review-1-cbm-20261015`，project `r05_gen_review_1_20261015`，fast / persistence=false：72 Python 文件、953 nodes / 4470 edges，parse partial/unusable/skipped 均 0。未索引 holdout、秘密、报告或他人源码。

`get_architecture` 和 `trace_path(generate,both,depth=3)` 显示 28 callees / 0 callers；保存 schema/architecture/trace 原始结果。`rg` 独立补查 `GenerationClient|generate_structured|validate_structured_output|ENDPOINTS|approved_model|deepseek` 的 source/config/exports；配置仍为 not_configured，产品 API/worker/QA 无装配调用。这一事实不是生成客户端可以被当作整 R05 完成的依据。

**not_run：**产品 API/worker/QA 接线、PostgreSQL 用量/任务写入、产品认证上下文外发授权集成、供应商 live、真实公网 DNS/CA/peer、真实 embedding/rerank/pgvector、引文语义和唯一证据删除、问答/浏览器端到端、性能与持续运行。没有访问真实 key；产品模型调用 **0**，实际费用 **unknown**。未查项不能记为 passed，也不签整 T18/T20/T30/T31/T43、R05 或 G-B。

## 凭据扫描、文件证据与资源

`fixed_source_manifest.json` 保存 36 个固定源码/直接测试/合同文件的 captured SHA256、Git blob SHA1、Git blob 内容 SHA256、长度及 captured 与 Git bytes 是否相同；CRLF 差异显式区分。`junit_summary.json` 保存实际 testcase 名与失败/错误/跳过数，便于独立复跑。

`artifact_shape_scan.json` 对这次固定代码/直接测试及本审查证据做仓库原两种凭据形状扫描：初次 58 files、补充调用链/环境收据后 63 files，6 个命中均来自显式合成 fixture/probe，0 未分类；只输出位置与摘要。真实产品凭据精确值/片段扫描 **not_run**，审查者未持有或读取它们，不能把形状扫描写成真实凭据零泄漏保证。两项失败日志包含的完整值仅为公开测试合成凭据，专用于复现 Must 1。

所有本地 HTTPServer/socket 与线程在 finally 中关闭/join，相关断言通过；所有测试/静态子进程已结束，无长期服务或数据库资源。独立工作树/venv/CBM 项目暂保留给新冻结补丁的定向复验；完成后仅释放自己资源，不清理主控或其他 Agent 的目录。

Verdict: **fix 1 and 2 first.** 这是生成客户端/共享 POST 的限定技术初审，不是功能、live 或阶段验收。下一步由原作者提供固定补丁，再由本审查者独立复跑失败探针及受影响回归；主控在 Must 关闭后另行执行获准的有限供应商调用和产品接线。


## 独立定向复验登记 · 2026-10-15T14:55:50+08:00

新固定8f6bd9f的原24独立probe与真实本地超时3通过；Must 1关闭、Must 2原触发已修，但defer_build=True延迟构建分支新增确证2失败，整体仍needs_changes。详见 [复验报告](G-B-R05-generation-review-1-recheck.md)。初审436的原始失败/manifest保留，不覆盖或倒推新结论。


## 第二次独立复验登记 · 2026-10-15T15:00:05+08:00

31c2866固定补丁的69独立probe、142模型回归、115共享网络、686纯unit及静态检查通过；两Must（含8f6新增deferred分支）限定关闭。完整固定SHA/tree、命令/秒级时刻/rawcov及未验收项见 [复验报告末段](G-B-R05-generation-review-1-recheck.md)。未签产品live、接线或整R05/G-B，不覆盖任何历史失败。

