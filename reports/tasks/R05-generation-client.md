# R05 · 两种真实生成wire客户端工作包

文档首次创建时间：2026-10-15T14:11:15+08:00
本次写作开始时间：2026-10-15T14:09:09+08:00
本次写作结束时间/最后更新时间/证据截止时间：2026-10-15T14:20:31+08:00
作者：/root/r04_knowledge_api（本轮工作包R05-generation-client）
基线：08c4471fd74e882cbbfabf81f890d98f1d7a782d
分支：codex/recovery-r05-generation-client
当前已测集成冻结：4e47a93db8e3039b87755b3d8108963969978361（本包3695c5b + 主控07f5d85的cherry-pick）；backend/src tree=d9b30d9e93395fb3e031691551c8dc5265121bd5
状态：awaiting_review；本工作包实现complete，所列隔离自动验证passed，未独立验收，整R05仍partial。
unit/contract/integration/security：最终所列隔离范围passed；历史失败保留；frontend/e2e/live/manual：not_run。
独立review：主控将派新非作者；未accepted，未push。

## 1. 授权范围与冻结接口

读取当前AGENTS、00执行地图、R05、05模型/外部访问合同、CR-R04-R05_model_post、新Ponytail 5.2 full与OpenAI Docs。主控批准的小接口在2026-10-15T13:42:53+08:00系统时钟登记；消息实际发送秒未单独记载，不倒推。4个固定官方provider目标、2个wire，不允许请求体修改provider/path；Native OpenAI/Anthropic只从可信构造配置approved_model取得，当前无用户产品凭据，本包未配置或试用。DeepSeek仅允许deepseek-flash。

`GenerationRequest`分别承载可信system_text、question、带明确边界的evidence_texts、prompt/schema/model版本、整次max_output_tokens及至多一次格式修复开关。UTF8/NUL/长度/类型严格校验；请求model_version必须等于可信配置。`generate(request,response_schema,content_is_private,egress_granted)`返回经过严格Pydantic验证的`TypedGenerationResult[T]`及每次`AttemptMetadata`；私有外发拒绝在拼body/联网前。业务调用者仍须从认证与PG来源范围取得私有属性/外发许可，不能从客户端body自报；本接口不推断内容天然公开。

response_schema的根与嵌套BaseModel都必须extra=forbid；实际model_validate_json(strict=True)。保存prompt/schema/实际request body/response body SHA256、provider、请求/返回模型、已知finish reason、provider调用ID、起止UTC时点、完整完成耗时、input/output/cache read/cache creation/total token（缺失None）、费用unknown。不保存headers、输入/输出正文或key到元数据；响应ID/模型与文本含已知凭据时拒绝，错误消息固定。格式修复有独立实际prompt/body hash，不能给修复输入套用原prompt摘要。

## 2. 实现与复用

产品/测试6文件：`infrastructure/models/clients.py`直接兼容调整；新增`generation.py`、`json_output.py`、`tests/unit/test_r05_generation.py`、`tests/contract/test_r05_generation_wire.py`、`tests/integration/test_r05_generation_http.py`。没有修改schema、迁移、lock、settings/app/runtime、progress、原金标/分母/阈值。

复用已批准共享`NetworkGateway.post_json`、精确OriginCredentials/SecretStr、固定peer/TLS/SSRF/POST无redirect、绝对RequestDeadline和已有egress policy；复用标准库JSON/hashlib/threading/perf_counter及已锁Pydantic。没有新增SDK依赖、通用provider框架、自动工具执行或fixture后备。新代码必要性：旧clients.py仅验证器和FixtureProvider，无真实IO；本客户端确实通过共享网关发有界POST并读取两种真实wire，已用本地真实socket验证。

输入body单次最大默认256KiB、整次累计默认256KiB（配置硬上限1MiB）；response单次最大1MiB；结构化输出整次默认256KiB；深度32、节点10000；最多2调用（1格式修复），并发默认2最大4，整次deadline默认60最大120秒。每次max_tokens从同一剩余输出token预算取；实际已报output tokens扣除，未知usage按该次全部预留额度保守扣除，不能凭空获得二次预算。认证、quota、HTTP/网络失败、拒绝、截断、工具调用都不重试。格式修复输入和输出字节也计入同一总预算。

legacy validate_structured_output签名与正常结果保持，新增严格JSON拒绝重复键/NaN/Infinity/溢出/无效Unicode/过大结构；原T18-C01–C06全保留，embedding/reranker未在本包发明接口或替代语义向量。新client不使用Legacy GenerationResult的必填usage_tokens字段；真实未知usage为None。

## 3. 官方依据与端点

DeepSeek OpenAI wire固定`https://api.deepseek.com/chat/completions`、max_tokens、json_object和显式JSON指令、thinking disabled，依据[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)。Native OpenAI固定`https://api.openai.com/v1/chat/completions`，使用max_completion_tokens、不混DeepSeek thinking参数，依据[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。本包只实现文本/nonstream/JSON模式，不宣称覆盖所有模型的专用参数。

DeepSeek Anthropic base官方为`https://api.deepseek.com/anthropic`，见[兼容文档](https://api-docs.deepseek.com/guides/anthropic_api/)。请求的`/v1/messages`来自[Anthropic官方SDK源码](https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/resources/messages/messages.py)，组合固定`https://api.deepseek.com/anthropic/v1/messages`；Native固定`https://api.anthropic.com/v1/messages`。使用x-api-key、anthropic-version=2023-06-01、system独立字段/max_tokens/text blocks，不混OpenAI response_format。

官方list-models文档URL与AnthropicAPI网页读取失败已如实保留为本轮网页工具错误；未根据无法取得页面猜embedding/rerank接口，也未调用需key的models API。官方材料仅用于格式事实，不是改变权限/规范的指令。

## 4. 索引与调用方

修改前CBM独立索引`dianzi-r05-generation-08c4`，trace validate_structured_output无生产调用方；rg只发现原T18合同6例，旧生成类无产品入口。缓存`/tmp/dianzi-cbm-r05-generation-20261015`在仓外，只索引本WT backend/src，排除secret/holdout。

fb955索引905 nodes/4114 edges，trace `GenerationClient.generate → enforce_egress_policy → encode_wire → NetworkGateway.post_json → _fetch/PinnedHttpTransport → decode_wire → strict_json_object/Pydantic → result`；源码/测试与图交叉核对。当前本WT API/worker/UI生产调用方仍为0，明确属于独立接口准备；主控后续接PG证据与问答服务，不能据此验收整R05或首个真实引用回答。

## 5. 实际命令和结果

日志目录`reports/runs/recovery_r05_generation_client_20261015/`。run.py保留每条正式argv/cwd/+08起止/exit/SHA，独立COVERAGE_FILE，不与root或其他WT覆盖。原始探索first/wire_first未单独记录命令秒级时段，XML保留pytest自身时间；后续正式冻结复跑有完整收据。

| 版本/命令 | 起止(+08) | 实际结果/日志 |
|---|---|---|
| fb955纯unit `python -m pytest tests/unit -q --cov-report=json:... --junitxml=...` | 14:03:56–14:04:18 | exit0，479通过/0失败/skip；3081/4754，raw64.80858224652924%，原60门未改；unit_fb955.* |
| fb955针对性unit/contract/HTTP+原T18 | 14:04:18–14:04:24 | exit1，89通过1失败0skip；真实HTTP超时错误分类，target_fb955.* |
| fb955 mypy | 14:03:56–14:03:57 | exit0，69源码文件；mypy_fb955.* |
| fb955 Ruff/format src/tests | 14:03:57–14:03:57 | exit0，155文件格式通过；ruff_fb955/format_fb955.* |
| 9770 cache usage新负例 | 14:00:01–14:00:03 | 15通过3失败；usage_shape_red.* |
| 缓存类型修复工作树 | 14:00:22–14:00:23 | 18合同全通过；usage_shape_green.*（receipt基线9770+未提交修复；随后999提交） |
| 999完整时间定向修复工作树 | 14:02:44–14:02:46 | 2通过；clock_metric_green.*，随后fb955提交 |
| 已知refusal finish reason修复工作树 | 14:09:07–14:09:09 | 1通过；refusal_finish_metadata.*，随后3695提交 |

已通过的新unit边界：两wire正常、native参数区别、未知usage None、各HTTP错误单次、网络失败无retry、拒绝/截断/工具、坏JSON/额外字段/错误类型/重复键/非有限值、一次repair共享deadline和剩余tokens、二次坏输出无第三次、输入/output bytes/output token/总input修复预算、credential输入/回显、私有外发、UTF8/NUL/布尔类型、嵌套extra禁止、schema模型一致、并发等待有界、原legacy正常/负例、完整完成耗时（perf_counter）。

真实HTTP集成每次使用http.client和NetworkGateway.post_json，实际localhost临时socket/HTTPServer；fixture只将DNS返回登记的合成公共IP并替换PinnedConnection.connect路由到loopback。固定生产HTTPS URL/Host/path/header/body仍按真实codec生成；测试不证明真实生产CA/peer/DNS，不能计为DeepSeek live。正常两wire、401/429/503、302不跟随/不给其他origin发key/body、0.2秒服务延迟+0.05总预算是7例；服务器finally shutdown/server_close/thread.join，无新后台服务。未使用真实keys、未读取.env/KEYS、paid/model live调用0，实际费用unknown。

## 6. 问题台账

| ID | 实际触发/预期/结果 | 根因、处理与状态 |
|---|---|---|
| GEN-01 | usage.prompt_tokens_details=[]/false/0应拒绝，却转成空object；3负例实际失败 | `value or {}`误吞false形状；仅None视未知，999b修复，18合同green；已修复 |
| GEN-02 | sleep30ms的完整耗时一次仅记录15ms，不能下调30阈值 | Windows3.12 monotonic实际GetTickCount64/15.625ms分辨率；10探针未再次重现15ms，留真实样本；elapsed用perf_counter，deadline保持网关同一monotonic时基，fb955；定向2pass，已修复/待独立复核 |
| GEN-03 | 本地真实HTTP延迟0.2s、deadline0.05s，有时得到network_failure，预期timeout | 共享PinnedHttpTransport把socket TimeoutError落在OSError通用路径，deadline标记/粗时钟存在竞态；root是唯一owner，作者未在client猜测。target_fb955真实1fail；随后主控07f5d85/本WT4e47a93共同根因修复，最终91+4复验通过；历史失败保留 |
| GEN-04 | 超时fixture服务端向已关闭socket写入WinError10053 | 仅fixture把已关闭的Aborted与BrokenPipe/Reset同处理，20e2提交；未skip测试，不吞产品IO错误 |
| GEN-05 | Python runner以UTF8解码但子进程/终端GBK导致错误输出出现replacement且打印失败 | 设置child PYTHONUTF8与stdout UTF8；保留target_fb955.log/XML/receipt，pytest真实1fail未被覆盖；证据脚本修复 |
| GEN-06 | 显式OpenAI refusal在stop下拒绝，但meta未保留已知stop | 在安全失败对象保留已知reason，3695，定向1pass；无改变拒绝策略 |
| GEN-STYLE | 初版Ruff过长/unused及2长JSON fixture literals | 保留初轮静态日志；只格式、拆同字节literal与unused名称，最终fb955全src/tests exit0；不改gold/指标 |

## 7. 结论与下一步

完成所需最小真实联网客户端、严格两wire和预算/元数据接口。共享HTTP超时根因关闭前不声称本批全通过；最终修复复验见第8节；独立review仍须固定新候选，尤其不能拿479全绿掩盖真实HTTP负例。后续root接真实DeepSeek两wire最小live，保存实际耗时/usage/fee未知与PG引用；embedding/reranker/检索/首回答/浏览器仍待R05其他切片，不能将mock或本地HTTP算这些效果。

源码提交顺序：9770b29 → 999b5a7 → fb95577 → 20e2d48 → 3695c5b。原normal legacy调用兼容；旧生产调用者无，新增生产装配由root唯一负责。测试/扫描/文档不进入accepted或progress；作者交付后释放槽给新独立审查。

首次修订记录：2026-10-15T14:11:15+08:00，真实记录当前冻结、自检及已知共享阻断；后续修复和独立结果追加，不改首次创建时间、不删除失败。


## 8. 主控共同根因修复与最终冻结复验

2026-10-15T14:15:59+08:00：主控07f5d85明确将request/body读取/DNS的TimeoutError转换NetworkTimeoutError，保留其他网络异常的deadline检查；作者只cherry-pick为4e47a93，不在client猜测或下调超时断言。GEN-03已修复并在组合源码复验，原两次1失败日志/XML保留。GEN-04 fixture不对已关闭连接继续日志噪声，产品IO仍按共享层明确分类。当前等待新的独立review，作者未自签。

| 最终组合冻结4e47a93 | 实际+08起止 | 结果/证据 |
|---|---|---|
| 全纯unit（独立COVERAGE_FILE） | 14:12:05–14:12:25 | exit0，480/480，0失败/skip；3082/4760=64.74789915966386%；unit_transport_fixed.* |
| 新unit60+新contract18+真实本地HTTP7+原T18合同6 | 14:12:26–14:12:32 | exit0，91/91，0失败/skip；target_transport_fixed.* |
| 共享transport4定向security负例 | 14:14:39–14:14:40 | exit0，4/4；transport_security_combined.* |
| mypy69源码 | 14:12:05–14:12:06 | exit0；mypy_transport_fixed.* |
| 全Ruff/format src/tests | 14:12:06–14:12:07 | 两项exit0，156文件；ruff_transport_fixed/format_transport_fixed.* |

最新CBM仅本WT backend/src：905 nodes/4119 edges，project dianzi-r05-generation-transport-fixed，仍无产品API/worker调用方；这一限制不因接口准备green改变。root无需重复pick本包4e47a93（已有07f5d85），只按此前5条本包源码提交顺序集成；证据提交SHA另由交付消息给出。

本包所有测试进程已退出，本地fixture HTTPServer关闭/线程join断言通过；未创建长期服务、数据库、队列或持久端口，private key读取0/model paid calls0。正式模型接通、真实CA/DNS/live、浏览器及人工语义评估仍未运行，整R05不可accepted。

修订记录：2026-10-15T14:15:59+08:00，补共享根因修复、最终480/91/4及原始覆盖率；保留首次创建时间与旧失败事实。


修订记录：2026-10-15T14:18:22+08:00，统一最新问题状态与最终复验；证据staged diff check=2仅保留失败traceback/XML空白分隔行末空白，不改日志字节。evidence_index每项提供captured_sha256/captured_size_bytes及Git blob SHA256/bytes；静态扫描仅检查长sk-token形状，没有读取实际产品keys，真实凭据全文/片段扫描由主控集成时执行，本报告不把静态零命中叫真实秘密全扫描。


修订记录：2026-10-15T14:20:31+08:00，封存后仅将5个本包生成coverage SQLite缓存经绝对路径白名单核对移动至仓外C:/Users/yinha/.codex/tmp/dianzi-r05-generation-client-20261015/coverage，保留hash和实际移动收据coverage_cache_move.json；未递归清理/移动，也未动用户或他Agent文件。后续runner默认在此仓外缓存路径使用独立COVERAGE_FILE；既有命令收据中的旧位置是当次实际捕获位置，原raw coverage JSON/XML/log没有改变。

## 10. 独立审查两项Must的修复批次

本节首次写作时间：由本节末实际写作收据登记；历史首次创建时间保持不变。主控在本轮授权仅修两个已确证缺陷，作者仍为/root/r04_knowledge_api；独立审查者/root/r05_generation_independent_review未参与实现。状态awaiting_review，整R05仍partial，未push/未accepted。本节取代前文当前状态指向，前文各时点和失败原样保留。

修复基线322b51ac2835fcd7a5597317cc2f843dc3e97812；隔离worktree `C:/Users/yinha/.codex/worktrees/recovery-r05-generation-review-fixes/dianzi`，分支codex/r05-generation-review-fixes。源码冻结691a20db07d6594faf35c2cb1de738edcca6c617，backend/src tree=9eb16e6f6c3992b7465476e29d3c873cf7f9c6db。仅修改generation.py，新增直接单元测试test_r05_generation_review_fixes.py；没有修改共享network、schema、锁、settings、认证、公开API、进度、金标或阈值。本节和本包run目录为单独证据提交。

### 10.1 复现、根因、修复与复用

| 问题 | 确证输入/实际结果 | 根因及实际修复 | 自检/独立状态 |
|---|---|---|---|
| R05-M1，安全阻断 | reviewer的合成客户端凭据放进prompt_version或schema_version，满足pattern，调用成功后元数据包含凭据 | body已有已知凭据检查，但两个标识不在body；现在在编码、schema处理及联网前检查request的model/prompt/schema全部公开版本标识，复用已有known-credential子串规则和固定model_credential_in_input，异常attempts为空 | 原probe两例失败保留；18个新两wire×三字段×原样/前缀/后缀负例检查零编码/零网络/零元数据凭据；独立复核待审查者登记 |
| R05-M2，合同阻断 | 根BaseModel extra forbid，但嵌套TypedDict或stdlib dataclass显式ConfigDict(extra=ignore)，输出嵌套extra被丢弃后成功 | 旧遍历只识别BaseModel与typing参数，未取得子类型有效配置；改为检查已锁Pydantic实际core validation graph的model/dataclass/typed-dict配置和fields显式override，包含容器、union、definitions/递归引用，metadata/config展示/serialization支路不作为验证节点扫描 | 原probe两例失败保留；16个ignore/allow覆盖直接/list/mapping/union配置拒绝为零网络；8个有效默认继承/显式forbid正负输出与1个递归模型通过；独立复核待登记 |

原审查probe的v2更正过harness，作者直接只读复跑原文件，在322基线实际4 failed/20 passed，不把v1 harness错误列为业务缺陷。v2原字节复制至本run/reviewer_probe_v2.py，hash与原文件一致，便于提交后独立复跑；未改审查者源文件。修复后同24项全部通过。所有凭据均为显式synthetic fixture值；没有读取实际产品key。

复用已锁Pydantic2.13.5/pydantic-core2.46.5生成的有效验证配置，使用标准库dict/list/tuple/集合迭代，不新增反射框架、依赖或provider能力。根据[官方core schema定义](https://pydantic.dev/docs/validation/dev/api/pydantic-core/pydantic_core_schema/)，结合锁版本schema_probe实际输出核对extra_behavior/extra_fields_behavior；默认TypedDict和stdlib dataclass在严格父配置下实际继承forbid，合规正例保留，没有将默认继承本身误报。自由键的有类型dict映射继续有效，映射值中的对象仍递归检查。必要新增代码弥补元数据旁路和类型遍历缺口；不是扩大模型公共接口。Pydantic升级需复跑这些合同，任意自定义validator执行逻辑不在本批授权输入范围，response_schema仍由可信业务代码提供。

### 10.2 调用方、索引与入口

本批先读AGENTS、00执行地图、R05、T18及其02/05/07合同、实际CR-R04-R05_model_post、新Ponytail5.2 full/review、状态/交接。仓内未发现名为CR-R14的文件，已向主控报告；两项修复严格落实现有extra forbid与秘密保护合同，无新增合同差异。

主控随后确认CR-R14为派发口误，正确合同就是CR-R04-R05_model_post，无需新的合同文件或授权。派发消息确认为本批记录依据，消息发送秒没有独立日志，不补造。

CBM0.11.0独立项目r05_review_fixes_322b51a在本WT backend/src索引953nodes/4509edges；冻结后独立项目r05_review_fixes_691a20d刷新953nodes/4507edges、72文件，cache只在/tmp/dianzi-cbm-r05-review-fixes-20261015，不含holdout/秘密。architecture/schema/trace、源码及rg调用方交叉核对：require_strict_schema唯一调用者GenerationClient.generate；完整路径为可信业务调用→私有外发许可→请求/版本/有效schema→两wire encode→NetworkGateway.post_json→固定origin HTTP→严格JSON/schema→安全metadata→返回。当前源码依然没有产品API/worker调用入口，仅unit/contract/本机HTTP调用，不能拿索引没有边单独当未接线证据；rg和源码一致支持这一限制。调用签名、异常固定码和正常返回未改变；新增阻断作用于原本不合合同的输入/schema。

cbm_frozen_generate首次用简名GenerationClient.generate返回function not found，exit1原样保存；根据图返回的完整qualified name重查exit0，28出向/0入向，非业务测试失败。

### 10.3 冻结版本实际验证

本轮所有命令cwd为上述WT/backend；完整argv、+08开始/结束秒、退出码、code_sha在同名receipt.json，原始日志/XML/coverage保存在 `reports/runs/recovery_r05_generation_review_fixes_20261015/`。本机Windows CPython3.12.13，68个锁包独立uv sync；没有修改其他Agent虚拟环境。`-o addopts=`只用于显式隔离target，完整unit原始默认coverage60门完整运行，不更改分母或skip。

| 冻结检查 | 上海时间2026-10-15 | 实际结果/证据 |
|---|---|---|
| 原始unit全门 | 14:46:51–14:47:18 | exit0，617 passed，0 failed/skip，1依赖弃用warning；unit_frozen.log/xml；raw3449/5364=64.29903057419835%，coverage JSON保留42现有excluded lines，未改覆盖配置 |
| 定向完整行为 | 14:46:51–14:46:59 | exit0，162 passed，0 failed/skip；target_frozen.log/xml；103 generation unit + 24既有wire/T18 contract + 7真实本机HTTP + 4共享timeout security + 24审查v2 |
| mypy src | 14:46:51–14:46:52 | exit0，72源码；mypy_frozen.* |
| Ruff src/tests | 14:46:51–14:46:52 | exit0；ruff_frozen.* |
| format check src/tests | 14:46:51–14:46:52 | exit0，166文件；format_frozen.* |
| schema展示hook/serializer定向负例 | 14:49:43–14:49:44 | exit0，4 passed；schema_presentation_frozen.*；只增加run内可复现probe，691a20业务源码未变 |

原始失败保留：14:43:54–14:43:57的independent_red=exit1/4failed20passed；首次ruff=exit1/4格式问题（行长/导入），仅两拥有文件修复后通过，不隐藏日志。完整unit唯一warning来自Starlette测试客户端弃用httpx提示，未新增依赖解决与本批无关的弃用，留给依赖维护触发时处理。

unit/contract/security：本表范围passed；integration：仅真实本机HTTP传输7例passed（隔离DNS/loopback socket，不证明供应商TLS/网络）；PG/Redis/OpenSearch/向量/图/产品API集成not_run；frontend/e2e/live/manual均not_run，供应商实际调用0、费用unknown，真实语义/引用回答未证明。未开启fixture后备；未付费、未扫描资产、未执行PoC。pytest HTTP fixture退出关闭server并join线程；本轮没有长期服务、数据库或持久端口。

六类范围与评分：这里只支持T18-C01/C02/C05的生成边界，F2/F3/A1/E1代码准备；embedding、rerank、PG任务链、真实模型接入、端到端引用回答仍由主控后续批次完成，不签整T18/T20/T30/T31/T43，不声称G-B通过。修复后定向独立审查依据由/root/r05_generation_independent_review输出中文报告；作者只登记awaiting_review。

额外4例实际证明：TypedDict/dataclass的json_schema_extra把additionalProperties伪成false仍被有效ignore配置拒绝；BaseModel的真实__get_pydantic_json_schema__ hook同样不能使ignore过关；custom model_serializer不能绕过额外输入拒绝。明确边界：schema类必须为可信业务代码，任意before/plain validator可自行运行Python和预先删除输入，本客户端不承诺证明任意用户代码的无损性，也不接受外部提供schema类；serialization不是输入验证器。该边界已直接通知独立reviewer，不以展示hook测试替代任意代码安全保证。


本修复批次写作收据：2026-10-15T14:50:17+08:00，追加本节实际写作结束/最后更新时间/证据截止；本节首字写作开始秒未独立记载，写历史未记录，不根据文件mtime推断。前文首次创建时间保持。本节仅awaiting_review，独立复验结果另由审查者登记。

封存检查补记：staged_diff_check在2026-10-15T14:50:40+08:00实际git exit2，原因仅为CBM原输出/原review probe尾部空行，以及故障traceback/XML原字节空白行；原始证据不裁切、不换全局attributes。业务源码/直接测试提交前diff check为exit0。evidence_index逐条并列captured SHA256/bytes与Git blob SHA256/bytes，保留换行转换差异；静态长sk-token形状扫描不是实际凭据全文/片段检查，后者由主控集成负责。未创建或遗留长期服务资源。
