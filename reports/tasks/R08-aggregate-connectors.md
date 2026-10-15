# R08 · Hunter/Quake 受控聚合连接器独立包

状态：`awaiting_review`；本连接器包实现 `complete`。整 R08 仍需主控接线及独立审查，不能据本包签 `accepted`。

基线：`cb34097898b412390ee7e119d0d5c2c90d090673`。代码冻结：`8e150878a76e541e377b300f851d9c7caf919019`；分支 `codex/r08-aggregate-connectors`，worktree `D:/wt/r08-aggregate-connectors`。记录日期：2026-10-16，Asia/Shanghai；精确命令时间采用 UTC ISO 8601，见 [commands.jsonl](../runs/recovery_r08_aggregate_connectors_20261016/commands.jsonl)。未 push。

## 范围与依据

已读 AGENTS、00 执行索引、R08 恢复任务卡、T08/T19/T23、03/05/06 合同、04/07 引用材料、恢复计划 §6.3、相关状态与交接。基线 R08 状态为 pending/not_started。本包依主控明确授权先独立开发，R07 现有 `ExposureAggregateValue` 只读复用；公共 DTO、迁移、锁、FOFA、relay、模型、progress 未修改。

改动六个业务/测试文件：`backend/src/ai_intel/assets/aggregate_observations.py`、`hunter_aggregate.py`、`quake_aggregate.py`；`backend/tests/unit/test_r08_aggregate_connectors.py`、`contract/test_r08_aggregate_contract.py`、`security/test_r08_aggregate_boundary.py`。本报告及自有 run 是证据文件。

使用最新 Ponytail 5.2 full，复用标准库、现有严格 JSON 解析和 NetworkGateway，没有新增依赖、通用 BaseService 或第二套事实库。

## 官方接口核实与模板局限

公开资料操作共 **7 次**：Hunter 3 次、Quake 4 次；没有任何账户鉴权或搜索 API live 请求。Hunter 首次 web 抓取失败，其后浏览器读取官方语法查询页，并从实际菜单进入基础语法页；子任务浏览器不能设置 visible=true，因此页面以后台 tab 读取，未将可见窗口作为证据。菜单展开不计新资料页面。页面内部资源请求数量未单独采集，7 是主动资料检索/导航操作数。

| 来源 | 本轮核实的合同 | 未核实内容 |
|---|---|---|
| [Hunter 官方语法查询接口](https://hunter.qianxin.com/home/helpCenter?r=5-1-2) | GET `/openApi/search`；`api-key` query 认证；search 使用 RFC 4648 base64url；page/page_size 必填；code 数值 200 成功；总数为 `data.total`；fields 可选含 updated_at | 当前搜索额度扣费、最小 page_size 的实际执行、完整错误码映射、聚合观察时间 |
| [Hunter 官方基础语法](https://hunter.qianxin.com/home/helpCenter?r=8-1) | `app.name` 是组件名称匹配字段，区别于 banner/正文等宽泛文本字段 | Ollama/vLLM 是否为平台已登记的指纹名称、识别准确率 |
| [Quake 官方 quake_rs](https://github.com/360quake/quake_rs/blob/master/src/quake.rs) | 官方源码 348 行为 POST `/api/v3/search/quake_service`；1220–1226 行使用 X-QuakeToken；382–387 行 code 数值 0 成功；614–615 行搜索总数 `meta.pagination.total` | HTTP/JSON 完整权限与费用错误映射；官方聚合接口的 total 响应路径 |
| [Quake 官方语法资料](https://github.com/360quake/quake_rs/blob/master/src/gpt.rs) | `app` 用于产品，`service` 用于协议；因此不使用 service:Ollama/vLLM | Ollama/vLLM 指纹词项的有效性与实际匹配 |

Quake 子任务公开资料操作为一次官方域搜索、一次仓库页、一次 src 目录抓取失败、一次官方 codeload ZIP 在内存读取；未保存 ZIP、执行其代码或读取密钥。上述 master 文档的提交 SHA 没有采集，保留 unknown，不伪造文档版本。Hunter 页面所示更新时间为 2023/01/11；这是页内标记，不推断接口从未变化。

固定 `query_id=ollama/vllm`：Hunter 分别使用 `app.name="Ollama"`、`app.name="vLLM"`；Quake 分别使用 `app:"Ollama"`、`app:"vLLM"`。版本 `r08-product-name-1` 是本项目模板版本。名称匹配依照官方字段语法，产品指纹名仍待主控受控实测；不宣称已确认匹配准确率。

Hunter 固定 page=1/page_size=1/is_web=3/fields=updated_at，不扩大时间窗口。Quake 固定 start=0/size=1；仅用官方 search total，未猜测 aggregation total 路径。供应商搜索不可避免返回的明细只存在于网关内存和本次解析局部变量，白名单输出仅留下总数，不能进入 DB、日志、缓存、LLM 或错误信息。

## 输入、输出与调用方接线

真实入口为 `HunterAggregateConnector(api_key=SecretStr(...), dns_resolver="system"|"cloudflare_doh")` 和 `QuakeAggregateConnector(...)`，随后 `collect("ollama"|"vllm")`。密钥由可信调用方注入，本包不读取环境、DPAPI 或账户信息。缺 key 返回 not_configured，绝不默认 fixture 或假成功。显式 `fixture_gateway` 不得与凭据同时提供，使用 `is not None`，假值 fixture 不会落到网络路径。测试时才允许 retrieved_at 时钟覆盖，live 时间来自接收响应后的 UTC 时钟。

`AggregateObservation` 是本包内部严格冻结 DTO，extra=forbid；包含 schema_version、provider、query_id、query_version、retrieved_at、outcome、error_code、value、data_mode。成功才携带已有 `ExposureAggregateValue`，service_count 为 0..2^63-1 的严格整数、ttl_seconds=86400、observed_at=null、固定局限；不新增 vulnerable_estimate、IP、域名、端口、banner、原始 JSON、response headers、URL 或凭据字段。

| 行为 | outcome / error_code | 计数 |
|---|---|---|
| 有效总数，包括 0 | available / null | 保留真实整数 |
| 有效成功 envelope 缺失/null total | unknown / missing_total | value=null |
| HTTP 401/403 | unauthorized / provider_unauthorized | value=null |
| HTTP 429 | rate_limited / provider_rate_limited | value=null |
| HTTP 其他失败、供应商非成功 code、JSON/类型错误、网络失败 | failed / 固定分类码 | value=null |
| 缺少凭据 | not_configured / credential_missing | value=null |

输出验证器拒绝错配状态/错误码以及成功值的 provider/query/version/time 不一致。JSON 内未知供应商权限码不猜测、不按 message 关键词判定，保守 failed/provider_error；HTTP 权限拒绝已有独立状态。网络原异常、供应商 message、明细和 headers 不进入业务返回。调用只有一次，不重试、不以其他供应商或 0 降级。

真实网关使用固定 HTTPS origin、OriginCredentials、20 秒总预算、262144 字节 JSON 上限、单实例并发 1、0 重定向、严格 CA/SNI/IP 校验和已存凭据脱敏。每个 worker 应复用连接器实例，才能共享并发限制；上层全局配额与 job 预算仍由主控承担。本包不主动扫描、不运行 PoC。

`aggregate_freshness(value, now)` 在 retrieved_at+TTL 边界返回 stale 且保留历史计数；TTL 内缺平台 observed_at 时仍为 unknown。请求时间不冒充观察时间。已提供真实 observed_at 的其他可信值才可标 current；未来观察或早于获取时点的求值拒绝。

CBM 官方 0.11.0 先对基线 backend/src 索引并 trace 网关，再 rg 查所有调用方。src 初/终图为 1289 节点/6409 边；工具默认排除 assets，因此新增目录独立索引，最终 53 节点/160 边，两 collect 都指向本包类型/解析/判断函数。trace 的最初简写 function-not-found/exit1 已保留，完整限定名重试通过。src/graph 缺边不能证明没有调用，已有静态 rg 与实际 socket 检查交叉核实。独立 assets 缓存位于仓外 `/tmp/r08-aggregate-assets-cbm-20261016`，src 缓存同样仓外，不索引 reports、秘密或 holdout，不提交缓存或 ADR。

当前产品源码调用方尚没有 worker/API/PG/UI，只存在本包及直接测试。**主控需接线：**凭据/受控 DNS 配置、作业预算、PG 事实与失败状态、query version/TTL 缓存有效性、富化维度写入、详情展示与可见局限；仅序列化 AggregateObservation.value 作为现有曝光类型。fixture 必须隔离标识，不能进入 live 能力证明。失败记录不得抹掉此前可信历史统计。

## 真实验证

所有测试使用 `D:/dianzi/backend/.venv/Scripts/python.exe` 已有 Python 3.12 环境，并显式 `PYTHONPATH=D:/wt/r08-aggregate-connectors/backend/src`；未安装/更新依赖。cwd 为本 WT/backend，完整 argv、UTC 起止、退出码在 commands.jsonl；每项输出在同名 log。

| 验证 | 实际命令（python -m 前缀省略） | exit / 结果 | 日志 |
|---|---|---|---|
| 红例 | pytest tests/unit/test_r08_aggregate_connectors.py --no-cov -q | 2；1 collection error，模块尚未创建，不是环境故障 | unit_red.log |
| 新增 unit/contract/security 冻结检查 | pytest tests/unit/test_r08_aggregate_connectors.py tests/contract/test_r08_aggregate_contract.py tests/security/test_r08_aggregate_boundary.py --no-cov -q | 0；100 passed，0 failed/0 skipped | new_checks_freeze.log |
| 已有网关回归 | pytest tests/unit/test_r03_network_gateway.py tests/unit/test_r03_network_review_regressions.py tests/security/test_r03_network_transport.py tests/security/test_r05_http_post.py tests/security/test_r05_transport_timeouts.py tests/contract/test_t08_network_redirects.py --no-cov -q | 0；145 passed，0 failed/0 skipped | network_regression.log |
| R07 类型合同回归 | pytest tests/contract/test_r07_signal_schema_boundaries.py tests/contract/test_r07_signal_claim_values.py tests/unit/test_r07_enrichment_contracts.py --no-cov -q | 0；43 passed，0 failed/0 skipped | r07_contract_regression.log |
| Ruff | ruff check src/ai_intel/assets tests/unit/test_r08_aggregate_connectors.py tests/contract/test_r08_aggregate_contract.py tests/security/test_r08_aggregate_boundary.py | 0 | ruff_freeze.log |
| 格式 | ruff format --check 同上六文件 | 0，最终冻结版单独检查日志 | format_check_frozen.log |
| 类型 | mypy src/ai_intel/assets | 0，3 source files | mypy_freeze.log |

新增检查包括正常/0/缺 total/无权限/限流/坏 JSON/重复键/非有限数/错误标量、服务数≠漏洞数、私密字段 discard、历史/TTL、未知观察时间、错误码错配、精确固定请求、credential 边界、任意 query 拒绝、live 时间覆盖拒绝、假值 fixture、网络失败无零降级、真实 HTTP 序列化、0 重定向/大小/并发边界。socket 替身只是隔离 security 测试，**不是供应商 live**。

初期 mypy 的 106 条错误为 dict 展开类型不足，修为 TypedDict 后剩 1 条常量 Literal 类型，最终 0；Ruff 初期长度/导入/测试 mutable class 字段均已修复，无 ignore 新增。初期与迭代日志保留。定向 pytest 使用 --no-cov，未修改仓库 coverage 门槛，也未声称整仓覆盖率或全套默认 unit 已通过。

本包 unit/contract/security=passed；integration/live/frontend/e2e/manual=not_run。0 付费搜索、0 鉴权探测、0 模型调用；费用与实际未来额度消耗 unknown。已有账户200及权益事实属于主控此前独立证据，本包没有重复验证，也不将鉴权可用推断为搜索可用。

## 评分证据、偏差与下一步

R08 任务卡六项要求的离线边界证据对应上述 100 个测试；F2/P2/X1 仅证明受控模板、诚实状态与聚合输出约束。没有真实聚合、误匹配率、PG/API/UI 全链、持续运行或正式评分结果，不据代码存在宣称优秀档或整 T08/T19/T23 完成。

合同无公共语义/依赖/认证变动；内部包按主控文件所有权不改 progress。唯一归档增补是在主控明确允许下，自有 run/.gitattributes 对 *.log/*.diff 使用 -text -diff，并对 *.json 使用 -text whitespace=cr-at-eol，保存真实原始输出字节，不忽略业务检查。commands.jsonl 与 runner 源码采用 UTF-8 LF，使 Gitblob 与 manifest 原字节一致。

下一步建议：非作者审查固定代码 SHA；主控完成受控接线及明确四次预算的实际查询，先确认 page_size/size 和词项有效性，保存仅聚合脱敏元数据，再验证失败历史保护、PG 缓存 stale 与真实详情。若官方产品指纹名需改模板，升查询版本并记录实测依据；不能静默改含义复用旧缓存。
