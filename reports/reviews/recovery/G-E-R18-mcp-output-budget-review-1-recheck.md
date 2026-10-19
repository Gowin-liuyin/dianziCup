# G-E / R18 · MCP 输出预算 Must1 定向复核

What this change does: 本次唯一业务修复在既有 MCP callback 的特定异常分支后增加两行 `except Exception`，用现有安全结果构造器返回 `backend_internal_error`。意外异常不再交给官方协议回显或异常日志；进程控制异常和取消仍保留原语义。

**评审结论：限定切片 Ship；原 Must1 closed。** 不写 accepted，不签整 R18、U13、G-E、完整 MCP 产品或完整 deadline。原失败报告与所有失败材料继续保留。

## 1. 固定目标与范围

复核工作树 `D:/wt/r18-mcp-output-budget-review1-fix1`，分支 `codex/r18-mcp-output-budget-review1-fix1`，从固定 material `260942efc77168683b2b978747a19c3c9fedce3e` 创建；material tree `b2444f8a03aadfef01e40a96eb79c2f60597b079`。审查 source `c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f`，source tree `9980da61338eb7b2b9202f98aa0c1055af1f9f70`。业务 diff 相对 `f246815bd678c624a11f784de5dc2b3c83981cde` 为 adapter +2/-0，无其它 SDK 业务变化。

作者报告 `R18-mcp-output-budget-fix1.md` raw SHA256 `7d31de97e01ea592740e2b9fc69a8021225a4fe641801e41d0fa42aa9fc6abd6`；76-member manifest raw SHA256 `3186563c35bff534b0e2b332148a58b0035d657d983677943291ce90a85121e6`。76项作者原始字节及其声明的 Git blob 模式均独立核验；原545项（368+91+86）及各原 manifest 逐raw复验未变。四个原SDK模块对 source `6d85742b0114cc5e304e88b2aa930755ccce9bc9` 仍相同。

`post_commit_blob_proof.json` raw SHA256 `661cde421a2e5d5208a56f693e3d7039831c3a11ed8b521130e19e39cc482b36` 仅只读附件，不把它冒作本 fresh checkout 的76个冻结材料成员或本人的复验。

本轮重新读取 AGENTS、执行索引、当前状态、R18及 T32/T35/T51合同；沿用 Ponytail5.2 评审规则。独立写入仅为本新报告和 `recovery_r18_mcp_output_budget_review1_fix1_20261016`，不改业务、原材料、progress、schema、锁、金标和阈值；无PG、真实秘密、付费调用、push、发布或递归spawn。

## 2. Must1 为什么关闭

原漏洞位于 `sdk/python/ai_intel_client/mcp_adapter.py:167–190` 的异常处理边界：公开SDK传输注入含 synthetic credential marker 的意外 RuntimeError 后，官方 legacy initialize 回显异常到wire并写stderr；modern discover虽然wire隐藏文本，stderr仍打印它。测试为明确故障注入，不代表正常内置 httpx 已自然泄露真实凭据。

新 `mcp_adapter.py:191–192` 的两行修复只在已知异常分类之后收口 `Exception`，返回既有 `_tool_error('backend_internal_error')`；无异常正文、repr、traceback或认证字段打印。没有吞成成功、空列表或伪默认结果，也没有重试。

原 reviewer same2及fixture逐字复制到自有run执行：probe raw SHA256 `ff45fa3f78dc3a6cd845f86a34abd68576e746e7458392001a233feb1630a4f3`；fixture `8c448aa919d723a1c0810ecc7cc3322f5665bde9931a1ac327d6d09a445a4d2e`。原输入 question=`explicit error injection`、mode=`library`，原安全断言不变：wire/stderr无marker且安全ToolError代码为 `backend_internal_error`。

独立真实官方 `ClientSession`→stdio subprocess 两协议均通过；实际输出保存在 `unexpected_handshake_wire.json` / `unexpected_modern_wire.json` 和对应stderr/observation。两边 stderr 空，marker flags均false，`isError=true`、固定代码，不再是旧协议code0/现代-32603的未知异常路径。正式 tiktoken0.14.0/o200k_base 对两份完整结果含serverInfo计数均60 tokens/229 UTF8B，profile=`r18-output-budget-1`。

新增三个unit故障注入覆盖 `KeyboardInterrupt`、`SystemExit`、`asyncio.CancelledError`：调用实际callback，在IO await seam抛真实对应异常类型，均继续向调用者传播。该测试未向OS发信号，不能冒作真实进程kill演练。原普通输入/API/transport/contract/native异常分类由原280回归复跑保持通过。

## 3. 独立执行结果

完整原296 distinct tests由本人亲跑：**296 passed、0failed/error/skip**，包含原280、原same2、取消2和正式协议12；另新增BaseException3通过，合计去重299 passed。重复检查不增加数量，作者的296声明未作为我的通过证据。

12个独立协议case仍逐字使用原 `test_independent_mcp.py` raw SHA `c29021042cbaf0e6b956cf7c0789519d527675151fbace493b86710a1f6c1659`；取消case原 `test_cancellation.py` SHA `c7ab01e0d116cd7c146cd872e7432b99ab9b8f170884b1b8656ae696a9009021`。真实官方ClientSession stdio、中文/emoji、unknown/完整support/citation、8000完整wire边界、原子单元超限诚实错误、现代HTTP拒绝共享凭据、Host/Origin和固定词表并发边界均保持通过。原296也包含 ASCII stdio、7999/8000/8001、原生panic和控制异常、缺/损cache无隐式下载、权限/限流及Cookie边界。

当前固定缓存只读：3613922B、SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`，无下载和字符估token。这个profile是协议预算，不是模型计费token。完整原生1MiB连续空白的历史实际panic证据保留；本次未改其loader/计数代码，没有把400k/500k空白称为panic。

新项目 CBM重新索引264 nodes/1275 edges，0跳过/0不可用解析；trace与全SDK/backend/scripts的rg核查仍指向 stdio main→serve_stdio→共享callback→固定SDK路由。现代 HTTP当前 app 只在测试组装、tools/call 明确not_configured，拒绝不是正常多租户接通。

## 4. 没有随修复放行的限制

原取消测试本轮再次实测：四个同步IO占槽时queued取消0后端调用；取消者未收到迟到成功，list_tools仍响应。已发出的同步IO thread继续等待，**没有实现强制终止**。

真实slowstream本轮 `question_timeout_seconds=0.1`、每块0.025秒的12块响应仍约0.313秒成功。它仍是单次HTTP IO timeout，完整排队/调用wallclock deadline未实现，不能冒作完整任务时间上限。主控另批修共享SDK/runtime；此结论只放行异常脱敏/既有预算切片。

真实PG请求级身份和撤销、六工具、公开新envelope/分页、包与插件、完整Codex/Claude外部客户端、产品live/完整性能仍未在本片接通。unit/contract/security本片passed；integration仅synthetic stdio/loopback/ASGI；frontend/e2e/live/manual not_run/blocked_live。A1/E1/X1仅保留已验证边界；不签整T32/T35/T51或正式评分。

## 5. 材料和仪器差异

作者保存的6个before_fix输出原raw未改：两stderr.log按exact_raw，四JSON按76 manifest明列GitLF（作者raw为CRLF）。本人首版audit错误地要求六个Git blob都等于raw而exit1；这不是业务或材料失败。按声明模式核验后exit0，并将六个作者raw逐字另存到自有 `*.raw`，封存为exact_raw，保留首失败日志。没有把JSON规范化后的Git字节叫原raw。

原fix1旧fixture仍使用支持的 `REVIEW_RUN_LABEL` 环境变量，设为自有run绝对前缀，把本次network receipt直接写到自有run；旧fixture源码/断言及原资料未改。新helper首次lint有路径长行及nested-with两个问题，已仅在新helper修复、保留原exit1。

CR-R18文字已在主根2026-10-16T10:23:55同步新831 schema SHA `4ccc4337586137a407359a1c4a59dc5d92081a2f4b50ee32cc53fac16095d50b`；本轮只读snapshot的raw SHA记录于 `material_observation.json`。预算合同和旧14defs不变，TaskDescriptor新UUID模式不影响本两个旧DTO工具。移动主根不是本次源码审查目标。

## 6. 实际命令与交接

所有下表命令的cwd均为 `D:/wt/r18-mcp-output-budget-review1-fix1`，时间是实际Asia/Shanghai +08:00；未保存的交互读取/逐次编辑时间不推算。SDK定向测试用 `-o addopts=`，未执行或降低原全仓coverage门。

下一任务建议：root可按此限定结论集成固定c691/2609；保留原失败和新绿色证据。整体deadline、执行中同步IO资源控制、真实HTTP身份/撤销及完整R18功能另批实现和独立审查，不把本次安全修复当作它们通过。

Verdict: Ship. 仅本修复与既有预算切片。

Not checked: 产品PG/live、完整deadline/强制终止IO、六工具/分页/安装和插件、真实完整外部客户端、整卡/阶段验收。


| 标签 | 实际argv | 开始/结束 +08 | exit | 日志 |
|---|---|---|---|---|
| cbm_index | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r18-mcp-output-budget-review1-fix1/sdk/python --name dianzi_r18_mcp_output_budget_review1_fix1_20261016 --mode fast | 2026-10-16T10:28:35+08:00 / 2026-10-16T10:28:42+08:00 | 0 | cbm_index.log |
| cbm_trace | wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project dianzi_r18_mcp_output_budget_review1_fix1_20261016 --function-name dianzi_r18_mcp_output_budget_review1_fix1_20261016.ai_intel_client.mcp_adapter.create_current_read_tool_server --direction both --depth 3 --max-output-tokens 2000 --format json | 2026-10-16T10:30:22+08:00 / 2026-10-16T10:30:26+08:00 | 0 | cbm_trace.log |
| complete_296 | D:\dianzi\backend\.venv\Scripts\python.exe -m pytest -q sdk/python/tests tests/plan/test_public_api_v2.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/test_unexpected_error_diagnosis.py reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/test_cancellation.py reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/test_independent_mcp.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/complete_296.xml | 2026-10-16T10:28:35+08:00 / 2026-10-16T10:29:06+08:00 | 0 | complete_296.log |
| full_callers | rg -n create_current_read_tool_server\|_tool_error\|Exception\|CancelledError\|streamable_http_app\|mcp_stdio sdk/python/ai_intel_client sdk/python/tests backend/src scripts --glob *.py | 2026-10-16T10:29:21+08:00 / 2026-10-16T10:29:21+08:00 | 0 | full_callers.log |
| helpers_final_format | D:\dianzi\backend\.venv\Scripts\ruff.exe format --check --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016 | 2026-10-16T10:34:06+08:00 / 2026-10-16T10:34:06+08:00 | 0 | helpers_final_format.log |
| helpers_final_lint | D:\dianzi\backend\.venv\Scripts\ruff.exe check --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016 | 2026-10-16T10:34:06+08:00 / 2026-10-16T10:34:06+08:00 | 0 | helpers_final_lint.log |
| helpers_lint | D:\dianzi\backend\.venv\Scripts\ruff.exe check --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016 | 2026-10-16T10:31:15+08:00 / 2026-10-16T10:31:15+08:00 | 1 | helpers_lint.log |
| helpers_lint_final | D:\dianzi\backend\.venv\Scripts\ruff.exe check --config backend/pyproject.toml reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016 | 2026-10-16T10:32:48+08:00 / 2026-10-16T10:32:48+08:00 | 0 | helpers_lint_final.log |
| materials | D:\dianzi\backend\.venv\Scripts\python.exe reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/audit_fix1.py | 2026-10-16T10:29:21+08:00 / 2026-10-16T10:29:27+08:00 | 1 | materials.log |
| materials_modes | D:\dianzi\backend\.venv\Scripts\python.exe reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/audit_fix1.py | 2026-10-16T10:30:22+08:00 / 2026-10-16T10:30:28+08:00 | 0 | materials_modes.log |
| process_control | D:\dianzi\backend\.venv\Scripts\python.exe -m pytest -q reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/test_process_control.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/process_control.xml | 2026-10-16T10:28:35+08:00 / 2026-10-16T10:28:38+08:00 | 0 | process_control.log |
| process_control_formatted | D:\dianzi\backend\.venv\Scripts\python.exe -m pytest -q reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/test_process_control.py -o addopts= --junitxml=reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/process_control_formatted.xml | 2026-10-16T10:32:48+08:00 / 2026-10-16T10:32:51+08:00 | 0 | process_control_formatted.log |
| product_format | D:\dianzi\backend\.venv\Scripts\ruff.exe format --check --config backend/pyproject.toml sdk/python/ai_intel_client | 2026-10-16T10:30:22+08:00 / 2026-10-16T10:30:22+08:00 | 0 | product_format.log |
| product_lint | D:\dianzi\backend\.venv\Scripts\ruff.exe check --config backend/pyproject.toml sdk/python/ai_intel_client | 2026-10-16T10:30:22+08:00 / 2026-10-16T10:30:22+08:00 | 0 | product_lint.log |
| safe_error_budget | D:\dianzi\backend\.venv\Scripts\python.exe reports/runs/recovery_r18_mcp_output_budget_review1_fix1_20261016/verify_result_budget.py | 2026-10-16T10:31:15+08:00 / 2026-10-16T10:31:16+08:00 | 0 | safe_error_budget.log |
| type | D:\dianzi\backend\.venv\Scripts\mypy.exe --strict sdk/python/ai_intel_client | 2026-10-16T10:29:21+08:00 / 2026-10-16T10:29:29+08:00 | 0 | type.log |

报告最终写作开始：2026-10-16T10:34:09+08:00；写作结束/更新时间/证据截止：2026-10-16T10:34:09+08:00。
交互读取及逐次编辑未逐次采集起止，未按mtime推算。
