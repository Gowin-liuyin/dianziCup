# Root-batch14-index · 固定48源码只读索引支持

任务状态：awaiting_review；索引支持产物已形成，不签 accepted，不替代 mode/budget/pool 新独审或业务验收。只写本报告与 ownrun。没有改业务、状态、配置、Git index/commit/push，没有访问 PG/服务/模型/秘密或索引测试答案。

## 固定输入、范围与真实执行

固定 HEAD：48f96b5ba35d19f5e26868a2bccd5b124afb2bd0（parent bc089809）。开始/结束 git status 与 git diff --exit-code 的 backend/src、backend/migrations 范围无修改；用户 frontend tsbuild 不进入此范围。raw tree 冻结225个 .py：194 source、31 migrations；初冻 2026-10-17T03:59:15.430+08:00，结束复算 2026-10-17T04:00:29.857+08:00；前后完全一致=True。

`693a9769c52d0757347b6fd3537dec61667fbb6d2e671f87b262f368371e6eec`

摘要定义仍为 UTF-8、按 repo-relative POSIX path 排序的 path + NUL + raw SHA256 + LF，再 SHA256。完整清单 source_before.json/source_after.json。该原始字节树绑定本索引，不拿 bc089809 的图审新 source。

官方 portable CLI=/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp；实际 index_repository --help 本轮再次调用并保存，只有 full/moderate/fast/cross-repo-intelligence，没有 incremental。新独立 CBM_CACHE_DIR=/tmp/dianzi-cbm-root-batch14-20261017、project=root-batch14-20261017。full 索引仅 /mnt/d/dianzi/backend/src；migrations只冻 hash，不入图；排除18个缓存目录；没有索引 secrets、holdout、截图、附件、reports、测试或测试答案。

结果：2944 nodes/17472 edges，194 Python source files，not_indexed=0、skipped=0、parse_partial=0、parse_unusable=0。真实 schema 原件 schema.stdout.log；未调用新版 get_architecture，architecture=not_run，不复用旧图数量。

序列 2026-10-17T03:59:15.839+08:00–2026-10-17T04:00:03.369+08:00，47.532s，exit0，9条串行CLI（help/full/schema/六trace），低于60s序列上限；单次最大 11.277s；Linux内部55s总deadline。完整 own Windows8+Linux8=16/16；包括两层Python、conhost、wsl/wslhost、SessionLeader、Relay、CLI daemon、sh/git，没有过滤relay来满足cap。Windows PID+birth UTC；Linux PID+birth ticks+namespace，祖先 namespace PermissionError 原样保存。仅 SIGTERM 精确匹配的自身CLI daemon，未采用其他Agent/Docker/runc/PID1。没有在此CBM序列同时启动第二个native shell。序列退出后交回Root的CBM独占slot；postexit exact identities Windows remaining0、Linux postexit exit0，原件postexit_windows.json/postexit_linux.json。Root其他reviewer随后独立任务不计为本任务所有。

## 图与源码交叉定位

| 链路 | 冻结48源码与图证据 | 实际边界 |
|---|---|---|
| shared mode → document/knowledge/public API | knowledge/revision_mode.py:13/29 的 classify_stored_revision_mode/homogeneous_revision_mode；mode_callers.source.stdout.log 覆盖document_read_service:157、knowledge_read_service:165、public_extension_reads:120；trace homogeneous 有29 inbound、3 outbound | trusted-source-runtime-v1 的live/fixture可读；无policy的legacy fixture保留，untrusted live/缺标记拒绝；最多2000；mixed拒绝；空响应仅描述运行时mode |
| document/knowledge routes | document_routes.py:71、knowledge_routes.py:69 显式 require_expected_mode=False，服务仍homogeneous；public projection/proof保留True默认 | doc/knowledge API按存储源mode报告，不把全局配置覆盖真实源；混合/缺失仍拒绝；public consumer严格与预期mode匹配 |
| mode → R07 structured proof | structured_fact_proofs.py:835/888 在两次事务捕获/锁后分别 homogeneous_revision_mode；StructuredFactProofReader.read trace58 outbound/6 inbound | 原文IO前后都核存储mode；原fact支持/ACL/锁/版本路径复用，不把“来源报告”升级成最终资产事实 |
| SourceReport默认工厂 → ENRICHER | api/investigation_routes.py:242/294 与 workers/investigation.py:169 经 investigation/runtime.py:47/56 将 build_content_storage(settings) 注入 InvestigationWorkflowService；workflow_service.py:358/360/387 保存consumer版本；1338 build_source_report_reader，1346 read_enrichment_source_reports；source_reader trace inbound1/outbound1 | 与batch13不同，本固定48默认角色已调用bridge。无store明确not_configured；无refs明确not_found；5s与剩余deadline共享；changed变stale，timeout/57014/55P03为partial，其余DB错误不吞 |
| SourceReport输出 → workflow预算 | workflow_service.py:1370写入RoleReceipt.output；1637/1649节点完成存全state；897 complete_operation按_output_json_bytes核实际字节、替换预留而非累计双计；920剩余扣其他完整/预留输出；超额存固定OUTPUT_BUDGET_FAILURE | 成功role输出与source_reports受节点实际字节总预算；未运行真实PG/并发/大输出测试，不能计通过 |
| budget/恢复版本 | workflow_service.py:388 envelope operation_output_accounting_version；671–675配置核版本；751 restore_node_state从PG failed receipt/job error恢复stop；829 operation_output_bytes reserved读原预留、complete算output_json；1156 run_role恢复优先，1625/1649传播失败 | 不改历史原预留列；同一JSON/status完成幂等，不同回执拒绝；恢复不重放未知模型/工具。图restore inbound4/outbound9，run_role inbound0是回调缺边，不否认build_investigation_graph(runtime.run_role)真实绑定 |
| Engine/pool/finally | api/app.py:73–81 lifespan finally关闭Redis cache后engine.dispose；workers/investigation.py:174–175 dispose；infrastructure/database.py:38–40 pool_size5/max_overflow5/pool_timeout固定设置 | 只是源码释放/有限池定位；没有新PG/泄漏或异常复跑。Redis cache.close先于engine.dispose，其异常是否保证后者执行，本任务未验证，不宣称所有finally异常路径已通过 |
| Neo4j可选配置 → 默认注册 | infrastructure/settings.py:47–49三可选字段、81–112成组/URI/凭证校验；infrastructure/neo4j_projection.py:126存在store；graph_projection.py:1069存在JobHandler工厂；workers/runtime.py:178仅build_projection_job_handlers；retrieval/runtime_policy.py:96/128/135/176仅hybrid/partial | 48新增graph可选settings，不等于默认Neo4j factory或graph_apply注册已完成；knowledge_change仍other_consumers_pending；GRAPH_WRITER仍partial/graph_projection_adapter_not_configured |

调用图只是索引辅助。create_application trace80 outbound/2 inbound，role/source factory/proof实际调用有源码和rg定位；class、闭包、回调图无edge不能单独证明没有调用。Graph factory注册的否定依据固定consume_job handler字典与projection factory源码，不依据旧bc图。

trace_summary.json记录六图完整计数/eq/no cursor/isError=false；深度3是查询边界，不宣称全运行时动态调用覆盖。模式标记生成、UI/SDK/live、SourceReport QA语义支持、budget真实PG/并发重放、pool资源测试、本轮architecture均not_run。索引和源码核对不添加准确率、多跳、持续运行或产线成绩。

## 命令、错误与交接

显式 shell=C:/Program Files/PowerShell/7/pwsh.exe、login=false；本轮没有空输出挂起或重复开shell。索引使用现成birth-aware native helper复制到本ownrun；未安装或扩业务框架。source rg原件为 mode_callers、workflow_budget、default_engine、graph_config、factory_pool、default_budget_exact.source.*。曾误查不存在 investigation/http_routes.py，rg退出2；实际工厂是 investigation/runtime.py，已有源码与caller定位，原错误不冒充业务失败。各CLI原件及实际+08时间/exit在all_cli_commands.json与*.command.json；以下9条全部exit0。

业务测试数量0，unit/integration/live/manual均not_run；不修改progress，也不签accepted。评分证据仅为工程路径/原始版本可追踪性。Root新mode/budget/pool reviewer可用225 raw tree与独立cache做定位；后续源码若变化须另冻/刷新，不继承此图结论。

| 实际CLI命令 | 开始 +08 | 结束 +08 | exit |
|---|---|---|---|
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help` | 2026-10-17T03:59:16.501+08:00 | 2026-10-17T03:59:16.571+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/dianzi/backend/src --mode full --name root-batch14-20261017` | 2026-10-17T03:59:16.586+08:00 | 2026-10-17T03:59:27.863+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project root-batch14-20261017` | 2026-10-17T03:59:27.949+08:00 | 2026-10-17T03:59:34.493+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.knowledge.revision_mode.homogeneous_revision_mode --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:34.507+08:00 | 2026-10-17T03:59:39.613+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.investigation.workflow_service._WorkflowRuntime.run_role --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:39.625+08:00 | 2026-10-17T03:59:45.489+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.investigation.workflow_service._WorkflowRuntime.restore_node_state --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:45.533+08:00 | 2026-10-17T03:59:51.092+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.enrichment.source_report_reader.build_source_report_reader --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:51.103+08:00 | 2026-10-17T03:59:54.425+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.knowledge.structured_fact_proofs.StructuredFactProofReader.read --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:54.439+08:00 | 2026-10-17T03:59:59.006+08:00 | 0 |
| `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch14-20261017 --function-name root-batch14-20261017.ai_intel.api.app.create_application --direction both --depth 3 --max-output-tokens 5000 --include-evidence true` | 2026-10-17T03:59:59.027+08:00 | 2026-10-17T04:00:02.930+08:00 | 0 |
