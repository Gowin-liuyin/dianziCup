# G-E · R18 MCP HTTP 独立审查 1

What this change does: 本变更把官方 MCP 2.3.0 Streamable HTTP 接到现有六工具 SDK，每个 HTTP 请求用自己的 Bearer 新建、鉴权并关闭异步 client。stdio 保留原构造器调用和默认 ask/check_stack 两工具，结果继续经过原严格 DTO 与完整 8,000 token / 1 MiB 预算。

首次写作：2026-10-17T06:54:37+08:00。审查人：`/root/r18_http_mcp_first_independent_review`，全新非作者；未参与业务实现。审查完成，建议仅本切片 Limited Ship；作者任务仍由 Root 登记，reviewer 没有修改状态或自行 accepted。整 R18/G-E 与真实 PG/live/client 产品验收没有随此报告通过。

## 冻结范围与依据

- Root 基线：`3fd9cd68f292afcd1b88ca55f218c4e869e8f706`，`D:/dianzi` 的用户未提交修改保持原样。
- 业务 source：`9fb558aaab4b1630eac62a88be7e2c5686243dab`；作者材料：`ccbbf3f5688bc57a81c881504a09ea5d18471387`。
- 自建独立分支 `codex/r18-http-mcp-review1`，worktree `D:/wt/r18-http-mcp-review1`，从材料提交冻结；没有审查作者继续移动的目录。
- source 相对基线仅四文件：`sdk/python/ai_intel_client/mcp_adapter.py`、新增 `http_transport.py`、新增 `sdk/python/tests/test_http_transport.py`、`sdk/python/README.md`。reviewer 只新增本报告和自己的 run/probe/封存文件，没有业务、合同、schema、原断言、阈值、锁文件、认证或状态修改，也没有 commit/push/发布。

已读本 WT AGENTS、execution map、`docs/plan/12_recovery_task_cards_20261014.md` 的 R18 卡与 manifest R18 能力依赖；Root 当前 progress/handoff；03/04/05/06/09 合同、T04/T32/T35/T51、CR-R04/09、R18 API Key/身份绑定/总 deadline/输出预算合同，以及 public_api_v2/extensions_v1 的六工具相关冻结定义。特别读取 Root 尚未提交的 `D:/dianzi/docs/decisions/CR-R18_http_mcp_transport.md`，SHA256 `f7fde964d529534eaf90d60e63719441bcc49acc88f431299a3c1730c7d94a4e`，与作者记录相同。

实际应用 [Ponytail Review 5.3.1](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.3.1/skills/ponytail-review/SKILL.md)，不是旧本地同名 skill。按 correct/safe/load/tested/fast/lean 顺序审查实际调用者、依赖、测试、README；假定可信配置的单进程 loopback ASGI 宿主、四个总请求槽，不把此版本视为已公开部署。

本机 Git `core.autocrlf=true`。fresh WT 的执行 checkout raw bytes 与提交 LF blob 不必逐字节相同；封存分别记录 raw SHA256、提交 SHA256、Git blob SHA，并用 `git hash-object --path` 精确比对冻结 source blob。四文件均匹配；没有把过滤后的 hash 冒充执行文件的 raw hash。见 [review_seal.json](../../runs/r18_http_mcp_review1_20261017/review_seal.json)。

## 真实调用链及检查结果

1. `http_transport.py:212–259` 的 `create_http_app` 只接受可信 constructor 配置，复用已有 base URL 校验；构造 `StreamableHTTPSessionManager(stateless=True,json_response=True)`，ASGI lifespan 进入 `manager.run()`。没有手写 JSON-RPC、OAuth token issuer、认证数据库或协议 session 真相。
2. `http_transport.py:127–162` 的入口把排队、body、鉴权和协议处理置于一个 finite deadline，外层总 limiter=4。容量 2 的 receive pump 只转送 ASGI 消息并监听 disconnect；JSON/版本/notification 仍由官方 SDK 处理。body 上限 1 MiB，并检查重复 Authorization/Host/Origin、精确 loopback Host/Origin/DNS rebinding。
3. `http_transport.py:164–209` 每请求 `DianziClient(self.base_url, credential)`，默认真实 `httpx.AsyncClient` 路径；`list_sources_async(limit=1)` 通过后，client 只写到拷贝的 request scope。initialize、list、notifications、GET/DELETE 同受入口鉴权。probe 额外消耗一次 read 配额，README 正确披露；不能称免费认证。401/403/429/503 safe code、网络、合同、deadline 分开，没有把下游错误变成空成功。
4. `mcp_adapter.py:169–174,239–287` 的可选 factory 从当前 official `Request` 取 client；缺 factory 的 HTTP 调用仍 not_configured，不能借固定 stdio 凭据。异步工具继续走旧 strict 输入、对应 native async 方法、总预算和 `_complete_result`。全仓 SDK `rg` 核对 stdio 与所有构造器调用者，旧前两实参及 `include_extended_tools=False` 保留。
5. `http_transport.py:203–209` 从该 scope 移除 client，在 shield 下限时关闭该 client；adapter 与 client 对超时/取消不返回伪成功。自有负例核对排队 deadline、半包 disconnect、legacy/modern 超时后释放 backend 不恢复 IO，lifespan 后无新增 pending asyncio task。实际 TCP 断连用例同时看到下游 peer EOF。
6. 已读取真实安装的 `mcp/server/streamable_http_manager.py`、`transport_security.py`、`_streamable_http_modern.py`、`streamable_http.py` 及官方 client 源码。manager 按 handshake-era / modern header 分流，legacy 请求关联 transport request，modern JSON 路径由 `serve_one` 接收 request context；新 pump 补上 modern JSON 路径缺少的 disconnect 监听。未据旧版本文档猜签名。安装版本：mcp/mcp-types 2.3.0、httpx 0.28.1、anyio 4.15.1、tiktoken 0.14.0；实际路径与官方源码 hash 在 seal 内。
7. 原完整结果 metadata、text、structuredContent、citations、未知/冲突与预算逻辑复用，原 8000±1 token、1 MiB 和 wire 回归通过；HTTP 新 schema/超预算检查通过。ask/check 下游 not_configured 与错误仍是 tool error，不是模板答案。没有任意 URL/shell/SQL 工具，没有借用户配置或共享 key 代取数据。

未发现可复现并需要列入 Must fix / Should fix 的问题。上述判断来自源码、CBM、独立原始日志和实际负例，不以作者“绿色”描述作为结论。

## 独立实测与资源

证据目录 [r18_http_mcp_review1_20261017](../../runs/r18_http_mcp_review1_20261017/)。所有复跑从独立 WT 执行，实际 cwd 为该 WT/backend；`*.command.json` 保留完整展开后的 argv/cwd/开始结束/exit/控制链/残留，`*.owned.json` 保留 Job 配置、用量、仪器来源与执行 SDK hash。薄 runner 复用 Root `batch13_checks_helper.py`、`batch13_process_metadata.py` 和冻结 fixed CORE `runtime_limits.py`，先加入 OwnedJob 再创建子进程。

普通组每组 60 秒、完整 Windows 控制链 ≤10、每进程 512 MiB / Job 1 GiB；Job read-back 验证 CPU_RATE=833，24 logical CPUs，约 1.9992 CPU。实际最大 Win 峰 8，最大 Job 峰 342405120 B，所有组 `remaining_owned_processes=[]`。`usage_after.active_processes=1` 是尚在写收据的 runner，未用它代替 children 退出检查。实际 PowerShell binary 路径见 `git_diff_check.json`，不把早期 requested shell alias 当作实测 binary。

普通解释器 `C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe` 加现锁 site-packages；native 组用现有 `D:/dianzi/backend/.venv/Scripts/python.exe`，确保 stdio 子进程正确加载 site/.pth。没有安装依赖、读取真实秘密、访问 PG/provider、运行 WSL 服务、真实来源/测绘或付费调用。APP_ENV=test / DATA_MODE=fixture；新 native 只开最多两个临时 loopback listener。

以下表内是 runner 子进程实际模块/参数；完整解释器 `-c site/runpy` 包装在各 command receipt 中。

| label / 实际命令 | 退出码与结果 |
|---|---|
| `http_final`: `pytest --no-cov ../sdk/python/tests/test_http_transport.py -q --junitxml=../reports/runs/r18_http_mcp_review1_20261017/http_final.xml` | 0；66 passed，0 fail/error/skip，2.30s |
| `regression_protocol`: `pytest --no-cov ../sdk/python/tests/test_mcp_adapter.py ../sdk/python/tests/test_mcp_output_security.py ../sdk/python/tests/test_wire_formats.py ../sdk/python/tests/test_output_budget.py ../sdk/python/tests/test_six_read_tools.py -k 'not subprocess and not real_ and not missing_stdio' -q --junitxml=../reports/runs/r18_http_mcp_review1_20261017/regression_protocol.xml` | 0；187 passed，8 deselected，0 skip，5.24s |
| `native_regression`: 同上述五文件，`-k 'subprocess or real_ or missing_stdio' -q --junitxml=../reports/runs/r18_http_mcp_review1_20261017/native_regression.xml` | 0；原 8 passed，187 deselected，0 skip，9.79s；原断言完整 |
| `independent_negatives`: `pytest --no-cov ../reports/runs/r18_http_mcp_review1_20261017/independent_http_probes.py -q --junitxml=../reports/runs/r18_http_mcp_review1_20261017/independent_negatives.xml` | 0；4 passed，0 fail/error/skip，1.29s |
| `native_http_final`: `pytest --no-cov ../reports/runs/r18_http_mcp_review1_20261017/native_http_probes.py -q --junitxml=../reports/runs/r18_http_mcp_review1_20261017/native_http_final.xml` | 0；2 passed，0 fail/error/skip，3.66s |
| `style_final`: `ruff check ../sdk/python/ai_intel_client/mcp_adapter.py ../sdk/python/ai_intel_client/http_transport.py ../sdk/python/tests/test_http_transport.py` | 0，All checks passed |
| `format_final`: `ruff format --check` 同三文件 | 0，3 files already formatted |
| `types_final`: `mypy ../sdk/python/ai_intel_client/mcp_adapter.py ../sdk/python/ai_intel_client/http_transport.py` | 0，2 source files 无问题 |
| `git diff --check 3fd9cd68 9fb558aa -- sdk/python` | 0，无 whitespace 错误 |

最终独立 XML 去重为 **66+187+8+4+2=267** 个不同节点，0 fail/error/skip；重复的 native_http 初跑不累计。原 native 8 产生 4 个 record_property/xunit2 warnings，新 native 2 产生 2 个同类 warnings；XML 仍保留实际属性，未改 JUnit/业务断言来消除它们。`--no-cov` 只作 SDK 限定回归，不称全仓覆盖率门通过。

原 native 8 真实证明 stdio 默认两工具、六工具 fixture discovery/call、ASCII stdout 纯协议、缺词表启动拒绝、GET 慢 headers/body 完整 deadline、执行中取消 peer EOF、stdio 取消及 owned handlers=0；不是作者排除八例后仍称“全部回归”。

新增 native 2 未 monkeypatch product client：**official mcp Client + httpx2 TCP → Uvicorn → create_http_app → DianziClient 默认真实 httpx TCP → 固定 fixture backend**。legacy 与 2026-07-28 均分别用 A/B synthetic Bearer，六工具列表及完整 list_sources wire 结果通过；未认证 HTTP 401 且下游调用 0。legacy 实际 10 次协议请求 / 9 probe+2正常读+1 held读；modern 实际 6 次协议请求 / 5 probe+2正常读+1 held读。真实 HTTP 断连取消 held 下游并观测 peer EOF；两 listener 关闭后 connect_ex 均拒绝、handlers=0、server task 收束、控制链 children=0。这是 network fixture integration，不是产品 PG/live 或 Codex/Claude 实测。

reviewer 自有仪器两次红均保留：`seal_review` exit1 是误把 Git CRLF checkout raw bytes 当 LF blob；修为精确 Git filtered blob 比对并记录两类 hash，`seal_review_fixed` exit0。`seal_review_final` exit1 是 Windows 默认 GBK 解码 UTF-8 CBM architecture 日志；只把仪器读取改为显式 UTF-8，`seal_review_final_utf8` exit0，4 file/267 distinct 验证通过。没有业务测试失败被改 skip，没有原 assert/分母/门槛变更。

## CBM 及其可证明范围

Root 独占授权后顺序执行，结束立即归还 WSL 窗：global `--help` 确认 v0.11.0；source-only SDK 8 文件索引，独立 project `dianzi-r18-http-review1-20261017`，cache `/tmp/dianzi-cbm-r18-http-review1-20261017`。`index_repository --repo-path /mnt/d/wt/r18-http-mcp-review1/sdk/python/ai_intel_client --name … --mode fast`、`get_architecture --project …`、`get_graph_schema --project …`、两个 `trace_path --direction both --depth 3 --format json` 均 exit0 且 isError=false。

结果 211 nodes / 896 edges；8 Python files，not_indexed/skipped/partial/unusable=0。transport trace 显示 create_http_app 连接 adapter/配置/transport；adapter trace 的四级调用者包含 HTTP constructor 与 stdio serve/main。嵌套工具 handler 及外部 SDK 动态调用边不完整，已用源码、全调用 rg 与实际官方客户端补证；零 callee/caller 不被解释成“没有调用”。

help 窗 06:50:30.555–06:50:33.209，index/architecture/schema/two-traces 窗 06:50:41.268–06:50:58.777（+08:00），每窗小于 60 秒。Windows 峰 7，加完整 guest 祖先至 PID1 和 tool 峰 6，保守相加 13≤16；birth-aware 祖先链保留，tool session 清理根只限自有 spawned session，shared init/PID1 从未作为 terminate 根。Windows children=0，guest owned tools=0。

Linux child affinity=[0,1]，guest RSS 采样峰 38539264 B；Go GOMEMLIMIT 只是软限制，RSS 只是采样，**没有宣称 guest 或完整 Win+guest 有 512 MiB / 1 GiB 内核硬内存限制**。Windows OwnedJob 的硬限制与 guest 仪器层级分开记录；见 `cbm_index.command.json`、`cbm_index.guest.json`、各 `cbm_*.raw.log` 与 seal。

## 未检查、偏差与后续

本片没有确认合同/计划偏差。OAuth issuer/client authorization flow 保持 not_configured，README 清楚说明；API Key Bearer、metadata 或 fixture 通过都不被当作 OAuth 已完成。

真实 backend/PG 撤销提交竞态、跨进程 read quota/权限、Codex/Claude/browser 接入、三类插件隔离、全 SDK/全仓 suite、package build/install、云 CI、正式性能与持续监测均 **not_run**。native TCP fixture 与 ASGI fixture 不填 live，也不签整 R18/T32/T35/T51/G-E。未知/fixture 当前性与后端 producer not_configured 均保持可见。

A1/E1/X1 证据仅限两个 transport 共用同一 SDK、逐请求身份生命周期、认证与输出失败保真、有限资源回归和可追溯日志。建议 Root 按冻结四文件集成后，另派新的非作者审查默认真实 backend/PG、OAuth/选定客户端和三插件切片；不要以本报告替代它们。

Verdict: **Limited Ship — 仅此 HTTP 逐请求身份切片。** 未发现须先修复的已证实问题；不改状态，不签 live/整卡/阶段。Not checked: 上述真实产品与完整验收项目。
