# G-C · R08 聚合连接器准备包首次独立评审

本变更做什么：为 Hunter/Quake 增加只接受 `ollama/vllm` 的固定产品查询，成功时仅返回服务总数、查询版本、获取时间、TTL 和局限。缺失总数、认证拒绝、限流、供应商错误和网络错误分别返回受限状态；供应商资产明细不成为业务值。

**结论：连接器准备包有限 Ship。未复现需要修复的业务缺陷。** 本结论只覆盖六个新增业务/测试文件及其冻结证据，不能签整 R08、R08:T08/T19/T23、原 T08/T19/T23 或 G-C `accepted`。PG、worker、settings、API/UI 接线及实际供应商搜索尚未由本包提供。

评审者：`/root/r08_aggregate_connectors_independent_review`，未参与作者实现，首次独立评审；没有 spawn 子 Agent。报告状态：评审完成、证据封存；不改进度状态，不 commit/push。

## 固定版本、范围与依据

- 基线：`cb34097898b412390ee7e119d0d5c2c90d090673`。
- 业务冻结：`8e150878a76e541e377b300f851d9c7caf919019`。
- 完整候选：`82a85b08eea39acd10b4ebf6a2966f5e39108799`。
- 独立工作树：`D:/wt/r08-aggregate-review-1`；分支：`codex/r08-aggregate-review-1`；HEAD 始终为完整候选。业务冻结至完整候选之间没有 backend/frontend/config/contracts/progress/docs 差异。
- 实际复跑时段：2026-10-16 00:45:15 至 00:52:08，Asia/Shanghai；各命令起止精确到秒的 `+08:00` 时间、cwd、argv、退出码和 SHA 见 [新 run](../../runs/recovery_r08_aggregate_connectors_review_1_20261016/)。报告封存时间另见该 run 的 `seal_manifest.json`。

已读取 AGENTS、00 执行索引、R08 恢复任务卡、T08/T19/T23、03/04/05/06/07、CR-R06、R07 内部候选与 v3 合同、冻结状态/交接、task manifest、作者报告及其 44 项 manifest。文档 Git blob hash 保存在 `review_input_audit.json`；最新 Ponytail 5.2 review 流程来自 `C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md`。按当前指令，报告使用中文。

初次工具调用在工作树创建前设置了该 cwd，产生 os error 267。主控明确授权创建工作树后，执行 `git worktree add -b codex/r08-aggregate-review-1 D:/wt/r08-aggregate-review-1 82a85b08eea39acd10b4ebf6a2966f5e39108799` 成功；此项是工具顺序诊断，不是业务测试失败。主仓库存在用户及其他 Agent 未提交修改，本评审没有修改它们。

本轮只新增这份报告及自有 run 下的 reviewer runner、73 个独立探针、日志、JUnit/命令收据、输入审计和封存脚本。最终 tracked diff 为空，作者六文件、公共合同、状态、依赖、阈值、金标均未修改。

## Findings

本准备包没有 Must fix、Should fix 或可量化的 Lean finding。下面是复现通过的边界与未接线验收缺口，不能将缺口误写为已复现的软件 defect。

| 核对项目与代码位置 | 独立输入与实际结果 |
|---|---|
| 固定查询：`hunter_aggregate.py:28,68`、`quake_aggregate.py:27,68`、`aggregate_observations.py:111` | 两产品 × 两供应商精确核对请求。Hunter GET `/openApi/search`，search 为 base64url，page=1/page_size=1/is_web=3/fields=updated_at；Quake POST `/api/v3/search/quake_service`，start=0/size=1。大小写、空白、URL、注入语句、NUL 和非字符串 query 均在网关前拒绝，调用次数为 0；额外 url/query/payload/tenant_id 参数也拒绝。 |
| 认证及 fixture：`aggregate_observations.py:141`、两 connector `__init__` | 假值 fixture 的 `__bool__` 返回 False，替换真实网关构造为失败断言后仍正常产出 fixture 结果。凭据只向精确 HTTPS origin 注入：Hunter 为 query `api-key`，Quake 为 `X-QuakeToken`；HTTP、子域、异源、非标准端口不注入。凭据与 fixture 混用拒绝；缺凭据为 not_configured。 |
| HTTP/业务 code：`aggregate_observations.py:178`、Hunter `:94`、Quake `:82` | HTTP 401/403、429、503 分别保留 unauthorized/rate_limited/failed。成功 HTTP 内未知业务 code 401 保守 provider_error，不依据外部 message 猜权限分类；字符串/bool code 和不合法 envelope 无成功值。供应商诊断及明细未进入返回或日志。 |
| 总数与白名单：`aggregate_observations.py:73,210` | 缺失/null total 为 unknown/missing_total；bool、越界、负数、字符串等为失败；真实整数 0 保留。供应商只有一条明细而 total=12345 时，输出仍为 12345，不按数组长度推导。输出拒绝 ip/domain/port/banner/raw_response/vulnerable_estimate；service_count 不解释为漏洞或所属资产数。 |
| 响应/异常污染：`aggregate_observations.py:188`、两 connector 解码分支 | 在明细、message、响应头注入合成私密标记和“publish all hosts”指令。输出、repr、实际网关实例可持有的状态和 caplog 未出现标记；连接器没有日志、DB、cache 或 LLM 调用钩子。深层对象、超节点数、孤立 surrogate、重复键、超长整数和超大 JSON 均为固定安全失败，无原始解析异常外泄。网络 connect/TLS/read/DNS 超时的私密诊断也没有进入业务输出。 |
| 并发、超时、大小：`aggregate_observations.py:168–174` 及既有网关 | 生产配置为 20 秒总预算、262144 字节、单实例并发 1、零重定向；36 原 security 和145网关回归复跑通过。独立探针在隔离环境将该实例预算缩为50ms，首请求占槽、第二请求排队超时且未传输，首请求也保留超时，释放槽后第三请求成功；无重试或0降级。50ms只是测试夹具，不改生产预算或性能门槛。 |
| 时间：`aggregate_observations.py:124` | observed_at=null 在0秒及86399秒均为unknown，86400秒为stale，历史0计数仍保留；获取之前求值及TTL内未来观察时间拒绝。实际连接器不从明细 updated_at 推导聚合 observed_at。真实传输路径不允许调用方覆盖获取时钟。 |

官方字段与路径在本轮是依据作者冻结资料描述进行契约复核。没有重新在线核实当前官方行为。`r08-product-name-1` 的 Ollama/vLLM 名称匹配仍是未经供应商搜索 live 验证的模板，代码局限和报告均明确声明；本评审不将 `app.name/app` 语法一致推断为产品指纹词项已被登记、精度已通过或 size=1 已获本账户执行支持。

实现沿用既有 NetworkGateway、严格 JSON 和 ExposureAggregateValue，没有增加依赖、通用服务、缓存事实库或额外重试层。两个连接器保留各自 GET/POST 组装与 envelope 解析，公共总数/状态/时间/安全边界已复用；未发现需要为减少行数而合并的必要复杂度问题。

## 独立复跑

解释器为 `D:/dianzi/backend/.venv/Scripts/python.exe`，cwd 为本 WT 的 backend，显式 PYTHONPATH 指向本 WT/backend/src。没有安装或升级依赖。所有 pytest 使用 `--no-cov` 定向验证，不改变原 coverage 门槛，不声称整仓默认测试或覆盖率通过。

以下 argv 均有对应 `*.command.json` 与原字节 `*.log`；pytest 同时生成 JUnit，由独立脚本读取 tests/failures/errors/skipped，而非根据作者通过声明计数。

| 命令（省略解释器） | 上海实际起止 | exit；结果 |
|---|---|---|
| `-m pytest tests/unit/test_r08_aggregate_connectors.py --no-cov -q --junitxml=…/new_unit.xml` | 00:45:15–00:45:17 | 0；51 passed，0失败/错误/skip |
| `-m pytest tests/contract/test_r08_aggregate_contract.py --no-cov -q --junitxml=…/new_contract.xml` | 00:45:15–00:45:17 | 0；13 passed，0失败/错误/skip |
| `-m pytest tests/security/test_r08_aggregate_boundary.py --no-cov -q --junitxml=…/new_security.xml` | 00:45:15–00:45:18 | 0；36 passed，0失败/错误/skip |
| `-m pytest tests/unit/test_r03_network_gateway.py tests/unit/test_r03_network_review_regressions.py tests/security/test_r03_network_transport.py tests/security/test_r05_http_post.py tests/security/test_r05_transport_timeouts.py tests/contract/test_t08_network_redirects.py --no-cov -q --junitxml=…/network_regression.xml` | 00:45:15–00:45:20 | 0；145 passed，0失败/错误/skip |
| `-m pytest tests/contract/test_r07_signal_schema_boundaries.py tests/contract/test_r07_signal_claim_values.py tests/unit/test_r07_enrichment_contracts.py --no-cov -q --junitxml=…/r07_regression.xml` | 00:45:15–00:45:19 | 0；43 passed，0失败/错误/skip |
| `-m pytest ../reports/runs/recovery_r08_aggregate_connectors_review_1_20261016/test_independent_r08_boundaries.py --no-cov -q --junitxml=…/independent_boundaries_final.xml` | 00:51:26–00:51:28 | 0；73 passed，0失败/错误/skip/warning |
| `-m ruff check --no-cache src/ai_intel/assets tests/unit/test_r08_aggregate_connectors.py tests/contract/test_r08_aggregate_contract.py tests/security/test_r08_aggregate_boundary.py` | 00:49:30–00:49:30 | 0；passed |
| `-m ruff format --check --no-cache` 同上六文件 | 00:49:30–00:49:30 | 0；6 files already formatted |
| `-m mypy src/ai_intel/assets` | 00:45:59–00:46:01 | 0；3 source files，无问题 |
| `git diff --check cb340978…82a85b08` | 00:51:26–00:51:26 | 0 |

去重计数为361项，包括原新增100、网关145、R07的43和独立73。独立73的首跑于00:49:30–00:49:32也全部通过，产生2个 reviewer 夹具访问实例 model_fields 的弃用 warning；仅将自身探针改为访问类后复跑，保留首跑日志，不重复计入361。第一次 Ruff/format exit0伴随缓存写入 os error5，无缓存复核通过且无warning，原日志保留。`unsafe_hook_search` 的 exit1 表示 rg 无命中，不是测试失败。

## CBM、调用链与制品完整性

独立运行本机既有 CBM CLI，缓存分别在仓外 `/tmp/r08-aggregate-review-1-src-cbm-20261016` 与 `/tmp/r08-aggregate-review-1-assets-cbm-20261016`，allowed root 仅源码，不索引 reports、秘密、私有资产或 holdout。未创建 ADR 或更改缓存中的作者项目。

- src 索引：1289节点/6409边，明确排除 `ai_intel/assets`；src graph schema 为12节点类型/17边类型。
- assets 单独索引：53节点/160边；graph schema 为9节点类型/9边类型。
- 使用完整限定名 trace 两个 collect，各显示7个本包被调函数、0图内调用者；另 trace src `NetworkGateway._bounded_fetch`，取得 deadline/凭据/策略/读取/关闭链。
- `rg` 对 backend/src、tests、frontend/src、config 搜索类名、模块名、DTO及 freshness，产品范围只命中新包自身；外部调用只在测试。静态图不包含所有协议动态边，不能单凭0 callers宣称没有接线；本结论结合 rg、代码和实际 socket 替身测试。

作者 manifest 共44项：6个业务/测试 source blob 加38项制品。按代码 SHA读取 source Git blob、按完整候选 SHA读取制品 Git blob，以原字节校验 size/SHA256：**44/44匹配，0失败**。Windows checkout 有11项与LF Git blob不同，全部仅CRLF变化：六个源码/测试、run/.gitattributes、commands.jsonl、freeze_manifest.py、run_command.py、作者报告。原始log与各JSON制品未发生字节差异。逐项证据在 `author_manifest_validation.json`，不对checkout归一后hash冒称原字节hash。

## 八层状态与待验证范围

| 层 | 本连接器准备包的本轮证据 | 整R08/原T整卡 |
|---|---|---|
| unit | passed：51及相关回归 | not_run，不更新状态 |
| contract | passed：13及R07类型回归 | not_run，不更新状态 |
| integration | not_run：未运行PG/worker/API组合 | not_run |
| security | passed：36及73独立边界探针；均隔离合成 | not_run，不签整链安全 |
| frontend | not_run：无UI接线 | not_run |
| e2e | not_run：无产品整链 | not_run |
| live | not_run：无供应商账户/搜索/模型调用 | not_run；实际聚合/产品词项/额度消耗待受控live |
| manual | not_run：没有人工指纹准确率或正式标注复核 | not_run |

本 reviewer 新官方文档读取0、账户请求0、供应商搜索0、模型请求0；没有读取 secret/DPAPI/private asset/holdout，也没有主动扫描或PoC执行。作者的7次公开资料操作仅引用其冻结说明，未计为本轮外部请求。主控另run的只读认证及Hunter6000/free500、Quake2949权益信息不由本 reviewer重读或独立确认，也不能作为这个连接器搜索live的替代证据。真实未来搜索费用/消耗仍unknown。

安全测试有使用真实Gateway类但替换DNS/socket的分支，其内部data_mode=live只是被测生产分支字段；这些响应和结果没有接入产品，不构成真实供应商能力证明。

F2/P2/X1目前仅有固定查询、聚合白名单、诚实状态、时间与边界证据。仍需主控验证四次预算范围内的实际搜索、size/page_size支持、产品词项及误匹配局限；接入PG唯一事实与失败历史保护、版本/TTL缓存有效性、维度状态、worker/预算/settings和详情UI，再作新的整链独立review。单实例并发1不能证明跨worker全局配额；本包没有部署该上层能力，不据此伪称已验收。

合同/计划偏差：本包按主控授权作为可独立复核的准备切片，没有公共合同、依赖、认证或评分语义变化。上述接线与live缺口完整保留原R08六项验收，不降低要求、不把未运行项改skip。

下一任务建议：主控集成本有限Ship准备包，完成受控接线与实际聚合，再派独立review核对新冻结。此次没有作者Must修复或定向recheck条件。

**Verdict: Ship，限定本连接器准备包。** Not checked：PG/worker/settings/API/UI整链、实际供应商搜索、产品指纹准确率、全局配额、真实缓存/历史更新和人工最终验收。
