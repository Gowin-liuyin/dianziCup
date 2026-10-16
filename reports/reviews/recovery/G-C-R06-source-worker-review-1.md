# G-C / R06 固定来源 normalizer + worker 组合独立初审

What this change does: 本批将七个新增固定公开来源的响应转为有原文、日期精度和证据位置的资料页，并接入既有 PG 任务/API。OSV 使用固定包 POST，AVID 使用目录/tree 与固定 blob 两阶段请求；原 NVD/vLLM 路径继续复用。仅审本冻结组合，不验收整 R06、G-C 或原 T 整卡。

结论：**Must fix（M1、M2）**。任务审查状态 `needs_changes`；没有写 `accepted`。作者回归数已被独立复跑确认，但新负例实际失败，不能据回归通过关闭缺陷。

## 冻结范围与环境

- 非作者 reviewer：`/root/r06_source_worker_combined_independent_review`，此前未参与本批实现；独立 WT `D:/wt/r06-source-worker-review-1`、分支 `codex/r06-source-worker-review-1`，创建时干净。
- 产品 diff 基线 `49ee33f6a95099be619a59ff47c621713a089137` → 代码 `52433474f66a900c56ee6d5478337b0ec83d6eda`；实际 checkout `b2bd53fd2320fc46f600ff0475298ec1b64b0172`。按仓库 checkout 过滤规则逐文件核对 524 的 Git 对象，实际运行字节 SHA256 另留各 run 与 `evidence_manifest.json`；官方 CAC -text fixture 另验证与 Git 原字节完全相同。未审主控活动 polling WT 或其后续提交。
- root normalizer 代码 `f0924a0b86e94629149bcbc73d0cdcfacefc2b2d`、精确保全 fixture `86e1fd504263844091a7c00415551ad3e8dc4a0c`；root 报告读自另 WT 的 `reports/tasks/R06-source-pages.md`，报告提交 `38496017e63fa5bd98352cc6065a1817c6d02cb0`，只作为线索。worker 报告 `02f834aec1bafe5ce63acae2c0d891f523be2444`，最终包装 b2bd。
- 产品文件：`backend/src/ai_intel/ingestion/catalog_pages.py`（全部 580 行）、`source_catalog.py`、`source_jobs.py`、`backend/src/ai_intel/infrastructure/models/json_output.py`、`backend/src/ai_intel/api/source_routes.py`；直接测试为两 unit、两 PG integration、`r06_source_worker_fixtures.py`，另有精确 CAC fixture 与其单文件 `.gitattributes`。准确 12 文件范围保存在 manifest。
- 已读实际 AGENTS、执行地图、R06 恢复卡、原 T08/T11–T16、03/04/05/07 合同、主库 0a 的 `CR-R06_source_collection_catalog.md`、CR-R04-R03 执行/游标、CR-R04-R04 持久化/来源任务/HTTP 提交、CR-R04-R06 资料读取合同及最新 ponytail-review 5.2.0。主库已有未提交状态/报告保留；没有修改其进度、锁、公共合同、金标或阈值。
- Windows / Python 3.12.13；在自有 backend 执行 `uv sync --offline --frozen --extra semantic`，安装锁定 92 包，未下载模型。该环境准备仅有实际工具输出，未补造秒级收据；正式检查均有独立 JSON 起止时间、argv、退出码、日志 hash 和产品 hash。
- 所有正式 run 工作目录 `D:/wt/r06-source-worker-review-1/backend`；本次正式测试证据窗口 `2026-10-15T21:32:56+08:00` 起，最终 probe 起止见 `independent_final_probes.json`。报告封存时间见 manifest 的 `frozen_at`（+08）。

## 已证实 Must fix

### M1 / P2：CAC 最后一条正文缺失仍被认定全文并推进游标

位置：`backend/src/ai_intel/ingestion/catalog_pages.py:489–495`、`:518`；实际提交路径 `source_jobs.py:453–516`。

这是什么：固定政策源应保存完整 24 条原文，结构改变或正文缺失应明确失败，不能显示为完整全文。

输入：保留官方 CAC fixture 其他字节与第二十四条 heading，只删除唯一的 `本办法自2023年8月15日起施行。`。独立保存输入 `cac_missing_last_body.input.html`，复现函数 `test_policy_with_last_heading_but_no_last_body_is_not_full_text` 与 `test_worker_does_not_commit_policy_when_last_article_body_is_missing`。

实际：normalizer 返回 `parse_status=parsed`、`content_coverage=full_text`，最后 heading 在、正文不在；PG worker 返回 `succeeded`，documents、document_revisions、source_cursors、source_page_receipts 各提交 1 行。预期：该固定完整性条件未满足，应 `SourceCatalogError` → `blocked/source_response_invalid`，本页资料/游标/回执不提交。纯与真 PG 原失败日志分别为 `independent_pure.log`、`independent_pg.log`；最终组合再次复现。

根因：代码只核 24 个 heading，并在全文任意位置搜“施行”。前言本来就有“现予公布，自2023年8月15日起施行”，因此替缺失的末条正文满足条件。最小修复：按每条 heading 的边界检查该条正文；末条要求在第二十四条之后存在完整末条正文，不能由前言满足。复验：原 fixture 应继续保留全部原文；本删除输入必须失败且 PG 不提交，另补正文位于下一块、内联标签与条款缺正文的边界。跳过修复会把缺正文修订作为全文当前资料对外显示。

### M2 / P2：OSV 新采集链把未知/非法时区及超支持精度转成确定时间

入口：新增 `catalog_pages.py:77–78`、`:360–386`；共同根因 `source_catalog.py:135–145` 与既有 `sources/osv.py:79–88`。下游 `api/document_read_service.py:196–197` 在非空 source_published_at 时默认给 `published_precision=instant`。

输入：在已录制 OSV 记录中只替换 published；完整 JSON 分别保存在 `osv_invalid_timestamp_1/2/3.input.json`。

| 原值 | 实际存储 UTC |
|---|---|
| `2026-10-15T01:02:03-00:00` | `2026-10-15T01:02:03+00:00` |
| `2026-10-15T01:02:03+00:99` | `2026-10-14T23:23:03+00:00` |
| `2026-10-15T01:02:03.1234567Z` | `2026-10-15T01:02:03.123456+00:00` |

实际：三例 normalizer 均接受；真 PG 三例均 `succeeded`、有确定 source_published_at 和完成游标。预期：非法 offset 分/秒与超当前存储支持精度不得静默归一/截断；`-00:00` 不能作为已知 UTC。此审查负例按既有 R04 拒绝策略期待 blocked 且无本页写入；若采用保留未知时间的合法策略，必须明确修订合同并保持 raw，不能返回 instant。未知不等于确定时间，错误时间不能进入正式时延统计。

根因：两处 `datetime.fromisoformat` 被当严格来源语法验证；该函数会宽松接受 offset 并截断小数。`_json_document` 为新路径调用原宽松 helper，将这个继承缺陷带进真实业务写入。最小修复：核对并复用项目已有严格时间规则，在共同边界验证日期/offset 字段/小数精度/未知 offset；同步 OSV 的 published、modified、withdrawn 校验。不能只在 worker 加特例。

caller 核对：`parse_source_timestamp` 的生产调用仅 `_json_document` 两处，其上游为 arXiv、RSS、release、OSV；OSV `_timestamp` 的生产调用为 `normalize_osv_record` 内 published/modified/withdrawn，后者唯一 src caller 是 `_osv_page`。完整 rg 原调用、model JSON 调用与测试调用见 `callers.log`；CBM trace 仅作辅助，嵌套 handler 用 rg/源码补足。复验需原三输入、新七路径、原 OSV ranges/关系/null 合同与原 NVD/vLLM 回归，不可把合法缺时间改成错误或从抓取时间补造。

## 独立命令与真实结果

统一 python `D:/wt/r06-source-worker-review-1/backend/.venv/Scripts/python.exe`；run 目录 `reports/runs/recovery_r06_source_worker_review_1_20261015/`。以下为核心 argv，收据包含绝对 JUnit/coverage/cache 路径与完整 argv；没有用作者日志替代自跑。

| run / +08 时间 | 核心命令 | exit / 实际结果 |
|---|---|---|
| pure_frozen / 21:32:56–21:34:49 | `python -m pytest tests/unit tests/contract tests/security -m 'not real_pg' -q --tb=short --junitxml=… --cov-report=json:…` | 0；1760 passed、10 deselected、0 skip；74.42% ≥ 原 60% |
| pg_frozen / 21:32:56–21:35:12 | `python -m pytest tests/integration/test_r06_source_worker_pg.py tests/integration/test_r06_source_worker_api_pg.py tests/integration/test_r04_source_jobs_pg.py --no-cov -q --tb=short --junitxml=…` | 0；91 passed、0 skip；新 worker 33、新 API 28 + 原 HTTP 11、原 worker 19 |
| independent_pure / 21:39:35–21:39:38 | `python -m pytest -c pyproject.toml <run>/test_independent_probes.py -m 'not real_pg' --no-cov -q --tb=short --junitxml=…` | 1；4 failed、10 passed、2 deselected、0 skip |
| independent_pg / 21:39:36–21:39:40 | 同独立 probes，`-m real_pg` | 1；1 failed、1 passed、14 deselected、0 skip |
| independent_pg_timestamp / 21:42:16–21:42:20 | 同独立 probes，`-k worker_does_not_commit_invalid_or_unknown_osv_source_timestamp` | 1；3 failed、16 deselected、0 skip |
| independent_final_probes / 见同名 JSON | 同最终冻结 probes 全 19 例、不使用 -m/-k | 1；8 failed、11 passed、0 skip；两组缺陷各在纯/PG 重现 |
| static_ruff / 21:39:35–21:39:36 | `python -m ruff check` 五产品文件 + 五直接测试/helper | 0 |
| static_format / 21:41:21–21:41:22 | `python -m ruff format --check` 同 10 文件 | 0；10 formatted |
| static_types / 21:41:21–21:41:31 | `python -m mypy src --cache-dir <run>/mypy_cache` | 0；92 source files |
| product_diff_check / 21:42:59 | `git diff 49ee33f6… 5243347… --check` | 0 |

PG 仅在进程内读取授权 WSL `…/runtime/test-services/connection.json`，替换为专库 `test_dianzi_r06_catalog_worker_20261015`，run ID `r06_catalog_worker_20261015`；每例新 UUID schema。未运行 umbrella fixture、未 downgrade、未碰受控观察库 `test_dianzi_r04_pipeline_20261015`。所有 PG runs `public_before=public_after={table_names:[]}`，迁移和清理只发生于本例 schema；日志与 argv 无 DSN/口令。

全套回归的已知 warning 是 Starlette/httpx 弃用。独立 run 外置 probes 导入 marked module 早于插件注册，另有真实 PytestUnknownMarkWarning；不是 skip、setup 错误或业务失败原因。CBM `cli schema trace_path` 实际不支持，exit1 记录保留为工具探索失败；后续正式 `trace_path` exit0，没有拿该失败当产品缺陷。

初次证据封存把 Windows checkout CRLF 与 Git blob LF 直接逐字节比较，在 `.gitattributes` 处断言失败；正式失败收据 `seal_raw_bytes_check` exit1 保留。修正为依据已有 Git checkout 过滤规则核对 blob，未改任何业务/属性；实际运行字节 hash 与官方 -text 原字节额外保存。此为 reviewer 封存工具错误，不计业务测试失败，也不把它当产品改动。

独立 CBM 0.11：WSL 官方 binary、独有 cache `/tmp/dianzi-cbm-r06-source-worker-review-1-20261015` 与项目 `r06-source-worker-review-1`，只索引本冻结 `backend/src`；92 文件、1233 nodes、6188 edges、0 skipped/partial。get_architecture、get_graph_schema、handler/catalog trace 与完整 rg caller 记录均在本 run；实际默认入口确认 runtime 固定注册 handler，未自动降级到 fixture。

## 本范围已确认与限制

九固定 key/八类别、OSV 固定 POST 包/MIME、GET 域/路径、无客户端任意 URL/body/租户、API 管理员/Origin/CSRF/提交时身份重查/双前缀/ID 重放冲突、原两来源回归均实际通过。AVID 目录只取 vulnerabilities 路径、树 pinned/失败回滚、blob base64/Git SHA1/文件 ID 校验和 12 秒共享 request deadline 经原回归核对；独立真实留档 tree hash与 40 条漏洞路径选择通过。

arXiv 依实际 start + 实际条数推进，论文实体/版本、仅摘要和 XML 深度/节点/DTD 边界经源码与纯回归核对；RSS 只称片段/metadata，不取正文或许可。OSV 独立范围、alias/related/upstream 原文、显式 null 记录拒绝、缺 vulns 的合法空结果与坏续页得到实际负例验证。release 未研判标记与无 Event/Claim 路径保持。新的事务写入、partial、7 秒续页、失败不推进游标/源历史、原二源19项与原 HTTP11项通过。

独立 NIST 实际留档 PDF（非 worker helper 的合成 PDF）sha256 `7576edb531d9848825814ee88e28b1795d3a84b435b4b797d3670eafdc4a89f1`：48 页文本坐标 1–48、原字节不变、January 2023 不造日/时区通过；缺页 partial 的原测试通过。官方 CAC 原 fixture hash `7fae988c064dde72c95e96e5727bf9abee4b3a5a1ea817606a9ca1f97ffac54b`、实际完整 24 条及末正文通过；M1 是额外结构缺正文输入，不能用完整原输入通过抵消。所有 HTML 仅解析为文本，未执行 scripts/PoC。

strict_json_object 模型默认仍 10000，仅 source 显式预算最多 50000，重复键/非有限数/Unicode/深度边界保留；独立上限正负例通过。原 response 与派生 payload 的 hash 没有混称：独立真 PG OSV 缩进原 response 与派生 member hash明确不同，两对象各自 read_verified，revision.source_response_hash 与 fetch_attempt 同指原 response；这一例真实通过。

没有新 live、模型、DPAPI、付费调用或外网请求。本报告的 recorded/synthetic 输入只能计 unit/contract 和 real-PG integration，不能计真实来源覆盖、延迟、连续运行、浏览器闭环或评分优秀；同一集成 SHA 的新七源 live/API/UI 尚待主控。跨 GitHub 来源共享 quota、后续 polling 调度、全文/图像语义完整性、正式参考分母和长期故障观察未重新验证，不能签整 R06/G-C。

未改业务、公共状态/锁/金标/阈值，未 push。失败日志的 `E     ` 尾空白原样保留；新增复现 HTML 也保留原脚本字节，仅删指定末条正文，没有全局 ignore。报告/证据冻结 hash在 `evidence_manifest.json`；本 reviewer 建议主控先修 M1/M2 并冻结新 SHA，原 reviewer 用同一负例定向复验，再做后续范围审查和限定 live。

Verdict: Must fix M1、M2。
