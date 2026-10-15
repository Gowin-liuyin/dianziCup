# R06 · 九固定来源 worker 接线

状态：`awaiting_review`；限定实现 `complete`。本报告只登记 source worker/API collection 接线与离线/隔离 PG 验证，不验收整张 R06 或 G-C；frontend/e2e/live/manual 均 `not_run`，未出网调用来源、模型或付费 API，未读 DPAPI，未 push。

## 基线、边界与调用方

独立工作树 `D:/wt/r06-worker-wiring`，分支 `codex/r06-worker-wiring`，基线 `86e1fd504263844091a7c00415551ad3e8dc4a0c`；代码冻结 `52433474f66a900c56ee6d5478337b0ec83d6eda`。主控 frozen normalizer 的前置代码位于该基线，主控补充证据 `38496017e63fa5bd98352cc6065a1817c6d02cb0` 无本包业务差异；其独立审查仍由后续新 reviewer 与本包组合执行。

产品只改 `backend/src/ai_intel/ingestion/source_jobs.py`、`backend/src/ai_intel/api/source_routes.py`。新增直接测试为 `backend/tests/unit/test_r06_source_worker.py`、`backend/tests/integration/test_r06_source_worker_pg.py`、`backend/tests/integration/test_r06_source_worker_api_pg.py`，共用显式 fixture helper 为 `backend/tests/r06_source_worker_fixtures.py`。其余改动只在本报告和 `reports/runs/recovery_r06_source_worker_20261015/`。没有修改 source_catalog/catalog_pages/catalog_documents、公共 schema、迁移、锁文件、配置、progress、前端或既有测试文件。

调用方包括 worker runtime 的既有 `build_source_page_handler` 注册、collection API 的 `SourcePageRequest` 构造和旧来源测试。handler 新增可选测试 `poster` 注入，默认实际 POST 走现有 `NetworkGateway.post_json`；无 fixture 自动后备。API source path 的 Literal 从统一 catalog 导入并扩到九固定键，已有 Cookie/CSRF/管理员/提交时身份重查、请求 body、双路由前缀、幂等范围及 problem 行为保持。frontend 尚未接新来源按钮，属于主控后续范围。

## 实现与事务不变量

九键为 nvd_ollama、vllm_vendor、osv_ollama、avid_community、ollama_releases、trailofbits_blog、arxiv_security、nist_ai_rmf、cac_generative_ai。既有 `ensure_source_registration` 已由 catalog 派生九源，直接复用；实际 PG 证明九唯一身份、八类别，无新注册仓库或内存游标。

旧 NVD/vLLM 仍使用原 fixed URL adapter、`persist_source_response` 和原 continuation 解析。新七源使用 frozen `build_catalog_request`/`normalize_catalog_page` 与 `persist_catalog_documents`；OSV 为固定包的 JSON POST，正文只能由 server builder 生成。每源 gateway 的固定 domain/content-type allowlist、响应大小、TLS/DNS、禁止 redirect、错误分类继续由现有 NetworkGateway 实现。新资料只是可追溯文档/证据，不凭资料类别创建 Event/Claim 或资产影响结论。

AVID 初始目录请求后先选择固定 tree/blob；第二次 GET 仅由已验证 blob SHA 重建 URL，不跟 url/download_url。页面输入 cursor 只能空或 tree_sha/record_offset，blob_sha 只用于第二阶段 server builder。每页最多两请求，共用一个 12 秒 `RequestDeadline`；真实 gateway 收到相同 deadline，测试明确证明第二请求剩余预算不能重置。目录空结果只留原始响应与完成回执，不伪造文档。

所有成功原始响应使用 `register_response_content` 保存真实字节/hash，并以 `record_fetch_attempt` + response_content_hash/final_url 留在 PG。AVID tree 与 blob envelope 都有独立原始响应记录，资料 revision 的 source_response_hash 锚定最后 blob envelope，decoded Git blob payload 由 frozen normalizer 校验 SHA1、再由资料 writer 保存实际 payload/hash；未仅存派生 JSON。NIST PDF/RSS/Atom/政策 HTML 的原始 upstream bytes 同样保留，资料内嵌摘要/字段不冒充抓取全文。

原文/资料、evidence、scope epoch、cursor/page receipt、continuation job/outbox 与终态仍在原 `execute_job` 的同一 PG 事务。存储、整页写入、cursor commit 或 continuation enqueue 任一失败全部回滚，不留部分资料或推进游标。每任务 remaining_pages 仍 1..20、max_attempts 仍 3；7 秒来源间隔、Retry-After/配额期限、partial 及停止后恢复逻辑不变。没有增加跨来源 GitHub 共享配额账本；AVID 两请求属于本包明确授权的固定范围，后续 live 共享配额/预算由主控另行约束，不能把每源间隔声称为全局 quota。

## 红例、修复与验收证据

`red_source_keys` 真实 7 failed/2 passed：原 worker Literal 只允许两键。初步接线后 new/old unit 聚焦 `initial_green` 243 passed；新 source/transport unit `catalog_transport` 57 passed，包括七源类型/固定方法、OSV POST、AVID 两阶段共享 deadline、坏 cursor/URL/type、429 与未知 key/API auth。

`pg_initial` 为 3 failed/20 passed，完整红日志保留。两个是新 fixture 的明确修正：录制 NVD 页仍有下一页，因此 max_pages=1 应 partial；AVID 按 frozen normalizer 倒序选择，第二条 synthetic path 最初错误占了首位。未改原 fixture/金标/验收门槛，只修正新测试对真实分页输入的解释及 synthetic tree 构造。

坏 XML 的失败不能靠吞异常解决。首次针对原始 ParseError 的猜测没有改善该例（`pg_recheck` 1 failed/23 passed），立即以 `malformed_xml_root_cause` 留最小复现并检查实际 parser：它将 ParseError 包装为 RuntimeError 派生的 AcademicContractError。最终只把已存在的 Academic/Feed/OSV/Repository 四类合同异常明确映射为 `source_response_invalid`，移除无效的 ParseError 补丁，没有 catch-all 或改 normalizer。七源坏页 PG 检查全部 blocked、无原文/游标部分写入。

`pg_catalog_errors` 33 passed：九 source 注册、旧两源与新七源 raw 内容/hash/evidence 精确子串与坐标、状态/游标；存储/资料/cursor/continuation 失败回滚；每源坏页；AVID blob 完整性与第二请求限流；OSV POST continuation/partial/重复修订复用及新 handler 恢复；AVID pinned tree 重启成功及坏 blob 保留此前状态；有效空页；source 身份冲突拒绝发送请求。

`api_pg_initial` 25 passed：九键 admin collection/alias replay/body conflict、CSRF/Origin/role 拒绝、任意 URL/cursor/tenant/max_pages 拒绝、并发幂等及提交时认证变化。新 API 文件另外引用原 HTTP 幂等测试函数对象，使用本专库 fixture 复跑其全部原断言，不修改原测试；`pg_legacy_http` 11 passed/28 deselected。既有 `test_r04_source_jobs_pg.py` 直接在专库显式执行，前一组合 `pg_full_related` 77 passed。最终冻结组合新增读取任务的三类跨租户角色拒绝，并包含全部原 HTTP 11 例和旧 source-job 19 例，最终结果以 `pg_frozen.json/xml/log` 为准。

## 环境、命令与结果

本工作树独立执行 `uv sync --frozen --extra semantic`，Python 3.12.13，92 packages，无修改 lock/no model download。所有 run_check 执行 cwd 均 `D:/wt/r06-worker-wiring/backend`，argv/开始结束秒级 +08 时间/exit/code SHA/product hashes 记录在同名 JSON；日志为实际输出，失败日志不覆盖。纯测试删除 TEST_DATABASE_URL/TEST_REDIS_URL/DIANZI_TEST_RUN_ID 环境输入，PG 只在显式文件命令注入授权专库 URL。

新专库 `test_dianzi_r06_catalog_worker_20261015` 从授权 WSL `.../runtime/test-services/connection.json` 进程内读取连接并创建，未打印/持久化 DSN/口令。每例新 UUID schema，migration schema-only、alembic_version 的 pg_namespace 属自有 schema；finally 只 drop 本例 schema。未使用旧 GA/生产/此前 R05 专库。所有 PG runs 的 public table counts 前后相同且始终空，没有在 public 迁移或写业务表。vector extension 的 public 类型由原 0014 迁移要求安装，非另一套业务真相。

| Run | 实际核心 argv（完整路径见 JSON） | 结果 |
|---|---|---|
| red_source_keys | `python -m pytest tests/unit/test_r06_source_worker.py::test_all_registered_source_keys_are_valid_worker_inputs --no-cov -q --tb=short --junitxml=...` | exit 1；7 failed/2 passed |
| catalog_transport | `python -m pytest tests/unit/test_r06_source_worker.py --no-cov -q --tb=short --junitxml=...` | exit 0；57 passed |
| allocate_database | `python .../prepare_database.py` | exit 0；created=true，public=[] |
| pg_catalog_errors | `python -m pytest tests/integration/test_r06_source_worker_pg.py --no-cov -q --tb=short --junitxml=...` | exit 0；33 passed，28.88s |
| api_pg_initial | `python -m pytest tests/integration/test_r06_source_worker_api_pg.py --no-cov -q --tb=short --junitxml=...` | exit 0；25 passed，21.60s |
| pg_full_related | 两个新 PG 文件与 `test_r04_source_jobs_pg.py`，`--no-cov -q --tb=short --junitxml=...` | exit 0；77 passed，96.81s |
| pg_legacy_http | 新 API PG 文件 `-k legacy --no-cov -q --tb=short --junitxml=...` | exit 0；11 passed/28 deselected，12.17s |
| pg_frozen | 两个新 PG 文件与原 source-job 文件，`--no-cov -q --tb=short --junitxml=...`，code 5243347 | exit 0；91 passed，105.10s；无 skip |
| pure_all | `python -m pytest tests/unit tests/contract tests/security -m 'not real_pg' -q --tb=short --junitxml=...` | exit 0；1760 passed/10 deselected，75.80s；74.42% ≥ 原 60% |
| pure_frozen | 同全纯范围及原覆盖率门，code 5243347 | exit 0；1760 passed/10 deselected，77.97s；74.42% ≥ 60% |
| final_ruff / final_format | ruff check / format --check 两产品文件与四新测试/helper文件 | exit 0；6 files formatted |
| mypy_final_candidate | `python -m mypy src` | exit 0；92 source files 无问题 |

CBM 0.11 独立 `backend/src` 索引/handler trace 及源码 rg caller evidence 在本 run 目录；没有索引秘密或 holdout。日志仅有已知 Starlette/httpx deprecation warning，不把 warning/fixture 当 live。初次日志目录不存在导致命令未执行的启动错误不计业务红例；建立自有 runner 后才封存 red_source_keys。Ruff 初始格式/导入问题经格式化与最终 checks 解决，没有忽略规则。

冻结代码的 `git diff 86e1fd504263844091a7c00415551ad3e8dc4a0c 52433474f66a900c56ee6d5478337b0ec83d6eda --check` 为 exit 0。包含报告证据的 `git diff 86e1fd504263844091a7c00415551ad3e8dc4a0c 02f834aec1bafe5ce63acae2c0d891f523be2444 --check` 为 exit 1：原始 `pg_initial.log/xml` 六处和 `pg_recheck.log/xml` 两处 pytest 失败输出 `E     ` 带尾随空格。八处均仅属于封存红日志；保留实际失败输出，没有改写日志或新增忽略规则。

## 限制、评分与交接

本包支持 E1 原子任务/恢复/权限、F1 八类别九通道的代码接线与可追溯原文输入、P1 有界分页/退避的工程证据；离线测试与录制输入不计真实来源覆盖、实时延迟、持续运行、准确率或性能达标。NIST 测试 PDF 是明确 synthetic text-layer fixture，不冒称真实 48 页 NIST live。资料元数据/原始时间精度保持 frozen normalizer 语义，法律适用性、资产影响与知识卡不由本接线自动推断。

跨来源共享 GitHub quota、实际来源采集、实时数据/API/UI、长期稳定性和完整 R06/R09/R17 验收留给主控，frontend/e2e/live/manual not_run。当前代码只能进入 awaiting_review；由全新 reviewer 在 root normalizer + worker 集成候选上复跑并审查，不由实现者 self-accept。下一建议是主控整合本代码提交，结合其 normalizer 证据安排独立审查后，再按剩余真实预算执行限定 live。
