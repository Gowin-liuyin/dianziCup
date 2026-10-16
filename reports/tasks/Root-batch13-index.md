# Root-batch13-index · 只读工作区索引支持

任务状态：awaiting_review。索引支持产物已形成；本报告不是 frozen commit review，不签 accepted，也不提升 R07/R14/R16/R18 的实现或验收状态。首次读取 AGENTS、00 execution map、task_state 与交接；当前任务卡是主控本次有界只读派单，引用合同 CR-R14_shared_read_consumers、CR-R07_structured_fact_proof_bridge、CR-R16_completion_fanin、CR-R18_public_read_identity_bindings。Ponytail review 技能只读取作源码核查参考，没有执行完整审查或签 Ship。

## 1. 精确输入与修改范围

分支 codex/full-delivery-recovery；HEAD 9726363e0d9b33467ba40a06a8bde9548b46bccf 仅是背景。索引对象是主控已集成四包和 app GET mount 的未提交 Root 工作区，绝不将该 HEAD 写成当前实现版本。

冻结范围为 backend/src 与 backend/migrations 下全部 .py，共 224 个：193 source + 31 migrations。raw SHA256 清单在 source_before.json、source_after.json、source_delivery.json。排序后的 repo-relative POSIX path + NUL + lowercase raw SHA256 + LF，按 UTF-8 拼接再 SHA256：

`3df28309321d83b0c94e0cd13910ce88944d1e57dc97dd26ee2137ab39719370`

初冻 2026-10-17T02:14:06.166+08:00；复算 source_after=2026-10-17T02:17:22.346+08:00；交付复算 2026-10-17T02:19:09.320+08:00。三个文件列表与字节摘要完全相等，没有源码变化。新增写入只限本报告和 reports/runs/root_batch13_index_20261017。没有修改 code/progress/contracts/config、用户文件、Git index/commit/分支或执行 push。

输入：Root source/migration 原始字节及真实 CLI。输出：独立索引、schema/architecture/trace、源码调用方核查和进程证据。新增业务测试 0；只读任务没有运行 pytest、类型或代码风格回归。没有注册 MCP、安装依赖、启 Docker、调用付费 API或外部 live。

## 2. 独立索引结果

真实 portable CLI：/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp，--help 返回 0.11.0。先调用 index_repository，scope=/mnt/d/dianzi/backend/src，mode=full，name=root-batch13-20261017。CBM_CACHE_DIR=/tmp/dianzi-cbm-root-batch13-20261017，在工作区外，不复用旧 Root cache。

最终 index 返回 indexed：2924 nodes / 17369 edges / 193 Python files；not_indexed=0、skipped=0、parse_partial=0、parse_unusable=0。图中 46 Route 节点、663 Function、610 Method、645 Class；4204 CALLS、2205 IMPORTS。此数量描述索引结果，不是业务完成或覆盖率。migrations 被 hash 冻结但没有纳入 source 索引。__pycache__ 等 18 个目录排除；不索引 reports、测试、holdout、截图、附件、秘密或测试答案。

schema、architecture 和 trace 的原始 envelope 均保留，见 attempt3/*.stdout.log 和 supplement/*.stdout.log；原命令参数、+08 时间、退出码见 *.command.json / all_cli_commands.json。仅 graph edge 不能证明真实调用成立或不存在，以下结论全部与 Root source/rg 交叉核查。

## 3. 调用链与未接线边界

| 路径 | 图与源码交叉证据 | 当前结论 |
|---|---|---|
| create_application → build_public_extension_router | api/app.py:175–181 明确 include_router(/api/v1)，图为 1-hop lsp 0.97；public_router inbound 可追到 app | 四个 GET 已挂到 Root app |
| router → PublicExtensionReadService | public_extension_routes.py:106 构造；146/155/163/173 的固定 lambda 调四个方法；图 class 只有文件 heuristic caller，闭包调用并不完整 | 实际调用成立，不能因 class trace 无 callees 宣称未接线 |
| public tasks | public_extension_reads.py:800–804 明确抛 PublicReadUnavailable；routes.py:135–136 转 503 not_configured | task owner + typed result producer 仍缺，不能包装任意 PG job 成成功 |
| InvestigationWorkflowService.execute → build_investigation_graph → run_role | workflow_service.py:507–509 传 runtime.run_role；随后 graph.invoke 执行；run_role 图 callers=0 但此真实回调存在 | graph/role 实际入口接线，图缺 inbound 不代表没调用 |
| run_role → 当前共享读 consumers | Collector GetAdvisory 1112；Assessor GetInventory 1237；Reporter FindChanges 1373；tool 的 ToolGateway/PostgresReadToolAdapter 注入 878，read_adapters.py:594 dispatch | 共享公告/资产快照/变化读取成立；读取不是采集写入、最终研判或引文支持证明 |
| SourceEnricher / ENRICHER → bridge | workflow_service.py:1180 ENRICHER 仍只 KnowledgeReadService.event_detail，1197 为 enrichment_write_adapter_not_configured；source_report_node.py:14、source_report_reader.py:12 仅独立函数定义，全 backend/src rg 未见运行调用方 | StructuredFactProofReader 能独立读；build_source_report_reader/read_enrichment_source_reports 尚未接到默认调查角色。没有 source report 输出计数/QA prompt 完成证据 |
| worker → revalidation handlers | workers/runtime.py:170–177 在 cursor key configured 时注册；runtime_policy.py:614 返回两个固定 handler；图 consume_job → factory caller lsp 0.97 | revalidate_change/reassessment handler 有条件注册 |
| handler → final guard → complete_job | workers/executor.py:137 handler.handler；139 租约检查；140–141 completion_guard；142 complete_job；runtime_policy.py:575 guard_completion，597 guard_completed_fan_in，611 返回 DetachedJobHandler | 源码支持同一最终事务执行固定 guard；外部 IO 位于 detached handler，不据此宣称 PG/live 验收 |
| execute_owned_* 名称 | rg -n execute_owned backend/src 退出 1，符合预期 no-match；当前实际符号为 execute_job、nested reassess/plan_change/guard_completion | 没有猜造 execute_owned_*；按真实符号 trace |
| knowledge_change / graph_apply | retrieval/runtime_policy.py:96/128/135/176 只建 HybridIndexer handler，返回 partial/knowledge_change_other_consumers_pending；workers/runtime.py:179–181 只更新该 projection handlers；graph_projection.py:52/1069 定义 graph_apply/工厂但未注册到 consume_job 的 handler dict | knowledge_change 仍仅 hybrid；graph_apply 未注册。没有自动串联重判、推荐撤回或 graph 写入的证据 |

源码核查的精确 rg 命令、定位输出和退出码保存在 *.source.command.json / *.source.stdout.log / source_crosschecks.json。bridge 的未接线判断依据默认角色分支与全 source 调用方检索，不单独依赖 graph callers=0。未分析动态外部插件或 source 之外运行时注入。

## 4. 真实命令、错误与资源边界

保留两次报告侧 Windows wrapper 失败：attempt1 的预留 cap=6 过严触发 RuntimeError；attempt2 读取 Linux 正在发布的 active JSON 发生 JSONDecodeError。两次 Windows peak 未完整记录，不能算完整 cap 通过。对应 Linux 序列各 12 CLI 命令均退出 0，日志没有覆盖；attempt1_wrapper_failure.json / attempt2_wrapper_failure.json 明确记录限制，初次结束时间仅工具 wall time 上界估计，不冒充精确时间。

第三次完整受控序列：2026-10-17T02:15:50.913–02:16:20.241+08:00，exit 0，Windows 8 + WSL 8 = conservative 16/16；Linux 12/12 CLI 均 exit0。补充六个真实符号 trace：02:16:52.994–02:17:11.405+08:00，exit0，Windows8 + WSL5 = conservative13/16。Windows 使用 PID + birth UTC；Linux 使用 PID + birth ticks + pid namespace，以及明确不可读 namespace 的 SessionLeader/Relay ancestry。全链包含 PowerShell/conhost/两层 Python/wsl/wslhost 和 Linux SessionLeader/Relay/Python/CLI daemon/sh/git；不把其他 Agent、Docker、runc 或 PID1 计为自身。

退出前仅向经过 birth/namespace 匹配的自身 codebase-memory daemon 发 SIGTERM；没有杀其他 Agent 或服务。postexit_windows.json 与 postexit_linux.json 在 CLI 与 wrapper 退出后再次核 exact identities，Windows remaining0、Linux remaining0（后者审计26 identities）。Linux ancestor namespace 权限不可读原样保留，未伪造已读取。

日志 CLI 合计42次，累计 105.486s；单次最大 7.052s；另两次探索帮助 shell wall 上界5.537s，合计上界111.024s，低于180s CLI累计预算。每次 guard 为55s，低于单CLI60s。源码冻结到交付审计墙钟超过180s；如果主控“总180s”指整个分析墙钟而不是 CLI累计，则这一限时条件未满足，不能写成通过。最终成功资源证明不追溯修补两次失败采样的未知 Windows 峰值。

另保留只读探查的路径错误：曾查不存在的 ingestion/job_handlers.py、enrichment/service.py、investigation/tool_adapters.py、domain/agents.py，rg退出1/2；随后对实际文件完成上述保存核查。finalize_support.py 首次运行有 Python invalid escape SyntaxWarning，退出0，影响报告 helper，不影响业务或索引。未改 Root 旧日志。

## 5. 验证、偏差与交接

业务 unit/integration/live/manual 均 not_run，数量0；索引/tool执行与 hash稳定核对通过。外部 live 和 R07/R14/R16/R18 完整自动/人工验收保持原状态；本任务没有改状态文件。评分证据只支持工程调用路径与源码可追踪性，不新增准确率、性能、持续运行、模型成功或多跳成绩。

下一检查点可以引用本摘要、all_cli_commands.json、attempt3/supplement trace 及源码定位。主控若继续改 backend/src/migrations，必须重新冻结并刷新索引；本报告不为后续字节背书。继续工作应以目前真实未接线边界为依据，并使用各包原审查与真实组合回归。本子任务停止，不推送、不签验收、不创建递归 Agent。

## 附：全部 CLI 原命令与结果

下面42个记录按实际开始时间排序；全命令 JSON 含独立 cache、源树绑定、开始/结束与错误。所有 CLI exit0，两个 Windows wrapper exit1 单独保留，不能混写。

| 记录 | 开始 +08 | 结束 +08 | exit | 实际命令 |
|---|---|---|---|---|
| help.command.json | 2026-10-17T02:14:06.622+08:00 | 2026-10-17T02:14:06.659+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| index_help.command.json | 2026-10-17T02:14:06.667+08:00 | 2026-10-17T02:14:06.698+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help` |
| trace_help.command.json | 2026-10-17T02:14:06.706+08:00 | 2026-10-17T02:14:06.737+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli trace_path --help` |
| index.command.json | 2026-10-17T02:14:06.745+08:00 | 2026-10-17T02:14:13.798+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/dianzi/backend/src --mode full --name root-batch13-20261017` |
| schema.command.json | 2026-10-17T02:14:13.808+08:00 | 2026-10-17T02:14:16.748+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project root-batch13-20261017` |
| architecture.command.json | 2026-10-17T02:14:16.756+08:00 | 2026-10-17T02:14:19.687+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture --project root-batch13-20261017 --format json` |
| create_application.command.json | 2026-10-17T02:14:19.695+08:00 | 2026-10-17T02:14:22.607+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.app.create_application --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| public_router.command.json | 2026-10-17T02:14:22.615+08:00 | 2026-10-17T02:14:25.501+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_routes.build_public_extension_router --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| public_reads.command.json | 2026-10-17T02:14:25.508+08:00 | 2026-10-17T02:14:28.417+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_reads.PublicExtensionReadService --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| investigation_execute.command.json | 2026-10-17T02:14:28.457+08:00 | 2026-10-17T02:14:31.354+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service.InvestigationWorkflowService.execute --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| run_role.command.json | 2026-10-17T02:14:31.363+08:00 | 2026-10-17T02:14:34.255+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service._WorkflowRuntime.run_role --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| revalidation_handlers.command.json | 2026-10-17T02:14:34.264+08:00 | 2026-10-17T02:14:37.227+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.revalidation.runtime_policy.make_revalidation_job_handlers --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/help.command.json | 2026-10-17T02:15:18.093+08:00 | 2026-10-17T02:15:18.131+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| attempt2/index_help.command.json | 2026-10-17T02:15:18.139+08:00 | 2026-10-17T02:15:18.170+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help` |
| attempt2/trace_help.command.json | 2026-10-17T02:15:18.179+08:00 | 2026-10-17T02:15:18.208+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli trace_path --help` |
| attempt2/index.command.json | 2026-10-17T02:15:18.217+08:00 | 2026-10-17T02:15:23.155+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/dianzi/backend/src --mode full --name root-batch13-20261017` |
| attempt2/schema.command.json | 2026-10-17T02:15:23.166+08:00 | 2026-10-17T02:15:26.100+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project root-batch13-20261017` |
| attempt2/architecture.command.json | 2026-10-17T02:15:26.110+08:00 | 2026-10-17T02:15:29.014+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture --project root-batch13-20261017 --format json` |
| attempt2/create_application.command.json | 2026-10-17T02:15:29.023+08:00 | 2026-10-17T02:15:31.920+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.app.create_application --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/public_router.command.json | 2026-10-17T02:15:31.929+08:00 | 2026-10-17T02:15:34.832+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_routes.build_public_extension_router --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/public_reads.command.json | 2026-10-17T02:15:34.841+08:00 | 2026-10-17T02:15:37.779+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_reads.PublicExtensionReadService --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/investigation_execute.command.json | 2026-10-17T02:15:37.790+08:00 | 2026-10-17T02:15:41.126+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service.InvestigationWorkflowService.execute --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/run_role.command.json | 2026-10-17T02:15:41.135+08:00 | 2026-10-17T02:15:44.079+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service._WorkflowRuntime.run_role --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt2/revalidation_handlers.command.json | 2026-10-17T02:15:44.088+08:00 | 2026-10-17T02:15:46.995+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.revalidation.runtime_policy.make_revalidation_job_handlers --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/help.command.json | 2026-10-17T02:15:51.141+08:00 | 2026-10-17T02:15:51.182+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp --help` |
| attempt3/index_help.command.json | 2026-10-17T02:15:51.194+08:00 | 2026-10-17T02:15:51.228+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli index_repository --help` |
| attempt3/trace_help.command.json | 2026-10-17T02:15:51.238+08:00 | 2026-10-17T02:15:51.271+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli trace_path --help` |
| attempt3/index.command.json | 2026-10-17T02:15:51.282+08:00 | 2026-10-17T02:15:56.273+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/dianzi/backend/src --mode full --name root-batch13-20261017` |
| attempt3/schema.command.json | 2026-10-17T02:15:56.280+08:00 | 2026-10-17T02:15:59.174+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_graph_schema --project root-batch13-20261017` |
| attempt3/architecture.command.json | 2026-10-17T02:15:59.183+08:00 | 2026-10-17T02:16:02.071+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture --project root-batch13-20261017 --format json` |
| attempt3/create_application.command.json | 2026-10-17T02:16:02.079+08:00 | 2026-10-17T02:16:04.985+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.app.create_application --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/public_router.command.json | 2026-10-17T02:16:04.997+08:00 | 2026-10-17T02:16:07.943+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_routes.build_public_extension_router --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/public_reads.command.json | 2026-10-17T02:16:07.953+08:00 | 2026-10-17T02:16:10.881+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_reads.PublicExtensionReadService --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/investigation_execute.command.json | 2026-10-17T02:16:10.898+08:00 | 2026-10-17T02:16:13.916+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service.InvestigationWorkflowService.execute --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/run_role.command.json | 2026-10-17T02:16:13.925+08:00 | 2026-10-17T02:16:16.909+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.workflow_service._WorkflowRuntime.run_role --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| attempt3/revalidation_handlers.command.json | 2026-10-17T02:16:16.928+08:00 | 2026-10-17T02:16:19.849+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.revalidation.runtime_policy.make_revalidation_job_handlers --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/public_get_vuln.command.json | 2026-10-17T02:16:53.299+08:00 | 2026-10-17T02:16:56.433+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.api.public_extension_reads.PublicExtensionReadService.get_vuln --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/worker_execute.command.json | 2026-10-17T02:16:56.444+08:00 | 2026-10-17T02:16:59.343+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.workers.executor.execute_job --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/fan_in_guard.command.json | 2026-10-17T02:16:59.352+08:00 | 2026-10-17T02:17:02.241+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.revalidation.fan_in.guard_completed_fan_in --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/read_consumers.command.json | 2026-10-17T02:17:02.251+08:00 | 2026-10-17T02:17:05.148+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.read_adapters.PostgresReadToolAdapter.read_tool --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/source_report_node.command.json | 2026-10-17T02:17:05.159+08:00 | 2026-10-17T02:17:08.053+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.investigation.source_report_node.read_enrichment_source_reports --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
| supplement/structured_reader.command.json | 2026-10-17T02:17:08.063+08:00 | 2026-10-17T02:17:10.974+08:00 | 0 | `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project root-batch13-20261017 --function-name root-batch13-20261017.ai_intel.knowledge.structured_fact_proofs.StructuredFactProofReader.read --direction both --depth 3 --max-output-tokens 4000 --include-evidence true` |
