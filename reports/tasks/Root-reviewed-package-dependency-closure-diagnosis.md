# Root · 已独审包依赖闭包根因诊断

任务编号：Root-reviewed-package-dependency-closure-diagnosis。状态：awaiting_review；诊断实现 complete；静态文件/版本核验 passed；本轮 unit/integration/live/manual 均 not_run。本报告不签 R06/R18 或阶段验收。

文档首次创建/本次写作开始时间：2026-10-16T18:40:06+08:00。固定 Root 对照：`d68b9c653aa8eced6eeb75b6d293617c6cce5094`；封存时实际 Root HEAD：`cb868896c944a45f5fc39fc3f0072743e291e7e6`。Root 在调查中从 d68 推进 cb868896；首版67项记录保留非原子观测说明，递归核验 2026-10-16T18:37:02.727134+08:00 → 2026-10-16T18:37:21.989720+08:00 的 cb868896 前后稳定。本诊断没有提交、stage、复制产品物料或修改业务文件。

## 结论与可复核根因

Root 集成器把“源码提交差异”当作完整可运行包，又把 import 存在核查当作依赖闭包。`reports/runs/recovery_reviewed_integration_20261016/integrate_reviewed_source_sdk_batch5.py:31` 只 `git diff-tree source`；35行强制 SourceProof 路径在 backend、SDK 路径在 sdk/python/tests。SourceProof 8355 只含三源码/测试文件，必要 archive 只在 material 5f8；即使检查74条内部 import 也不会读取 `Path.read_bytes()` 的目标。其 AST 只识别 ai_intel./ai_intel_client/r18_test_paths，而且没有递归核验目标内容、执行型 fixture、公共 JSON、外部词表或 lock 环境。

这是可复现的公共根因：R15 先漏 recommendation_contracts 后补 import；SourceProof 随后漏 material archive。目录类别只是存放位置，不能决定运行依赖；数据文件在 reports 中也可能是测试的直接输入。两次都不能靠删除案例、改 oracle 或重建合成答案修复。本次仅核既有冻结字节，没有创建或改造业务样本。

## 冻结包、证据范围与分类

- SourceProof source：`8355adbd9521e0dec99374b3bbb28bb6449e0fbc`；material/作者 clean HEAD：`5f8d644110ff2447ddc098c621375e0651ac2cf7`。固定8355下 hardcoded RUN/nvd-response.json 的 `git rev-parse --verify` 实际 exit128，属于预期“物料不在源码提交”存在性探针；material 中存在。
- SDK source：`02ce8d6b8072253c26a5df1a49e1b574f2668498`；material/作者 clean HEAD：`3db7b6cdf33ab1dc5d6c8801a54603b20137ada7`。16新增文件、原22基线SDK文件和五个合同/环境输入共43项逐核；Root 当前均存在，Git过滤 blob 全部等于 source/material。
- SourceProof 首版67项记录文件读取位置、物料类别、d68存在性与当前字节。递归补充83个必要内部模块/父初始化/执行中的local actor分支/0001–0030迁移，加 pyproject/uv.lock 共85哈希记录；author与Root无缺文件或 canonical 代码漂移。锁递归26个 distributions 的已安装 metadata 无缺失/版本漂移；这不是 ABI、导入运行或数据库扩展健康验证。
- 三个实际样本：RUN archive 4,332B 是20261014公开已记录NVD响应，vLLM 8,800B 和旧NVD API 3,106B 是20261015公开已记录响应。它们不是新 live、合成响应或盲测金标。两个 provenance sidecar 已存在且字节一致；旧 NVD API 是原R04回归输入，新 proof 测试直接读取 archive/vLLM。archive原始出处 `reports/runs/plan_audit_20261014/nvd-response.json` 字节相同，但原路径不能替代测试实际 hardcoded RUN 路径。
- SDK 的三新 fixture、两旧 fixture以及 inline fault/marker/token DI 都明确 synthetic；12个迁入测试与三 fixture 复用已审原断言，r18_test_paths只是路径/临时证据定位。旧3 sync/to_thread red oracle属于历史仪器材料，未删除或改变，也不是当前358的组成部分。

完整路径、Git blob、raw/canonical SHA256、consumer、缺失触发与材料分类在 `sourceproof_dependency_closure.json`、`sourceproof_recursive_closure.json`、`sdk_dependency_closure.json`；另用 `integration_provenance.json` 区分Root372补充合同输入。这四个JSON是完整逐路径清单，没有以图节点数或import条数替代文件核验。

## 必要输入与最小安全集成清单

SourceProof 从 d68 集成的最小增量是 source_documents.py、两份新测试，加 material 中原字节 RUN/nvd-response.json，合计四条；cb868896已完整收录，当前无需再次替换。保留既有vLLM/NVD API、provenance、运行源模块、全局 conftest、scripts/dev 和迁移链。全局 PG fixture 要求可信隔离 `DIANZI_TEST_RUN_ID=r06_source_event_proof_20261016` 及专用 loopback 测试库；本调查不读取 TEST_DATABASE_URL 值、不建库、不连接PG。0014 的 vector extension 安装/权限只列静态要求，没有冒称验证。

SDK 最小增量是以下16条冻结文件（当前已完整收录）：

- `sdk/python/tests/fixtures/close_fault_stdio_fixture.py`
- `sdk/python/tests/fixtures/native_stdio_fixture.py`
- `sdk/python/tests/fixtures/unexpected_error_stdio_fixture.py`
- `sdk/python/tests/r18_test_paths.py`
- `sdk/python/tests/test_cancellation.py`
- `sdk/python/tests/test_cli_fix1_regressions.py`
- `sdk/python/tests/test_close_fault_stdio.py`
- `sdk/python/tests/test_close_independent.py`
- `sdk/python/tests/test_close_reentry.py`
- `sdk/python/tests/test_independent_boundaries.py`
- `sdk/python/tests/test_independent_mcp.py`
- `sdk/python/tests/test_independent_native.py`
- `sdk/python/tests/test_independent_stdio_boundary.py`
- `sdk/python/tests/test_stdio_close_control.py`
- `sdk/python/tests/test_stdio_final_boundary.py`
- `sdk/python/tests/test_unexpected_error_diagnosis.py`

SDK还必须保留七个既有产品模块、其余15个基线测试/fixture、`tests/plan/test_public_api_v2.py`、`contracts/schemas/public_api_v2.json`、`public_api_v2_examples.json`、`backend/pyproject.toml`、`backend/uv.lock`。两个旧执行型fixture是 `sdk/python/tests/fixtures/mcp_stdio_server.py` 和 `mcp_native_deadline_stdio.py`。全部本地 import 目标存在；两公共JSON在收集/执行时被直接读取，v2 $ref 均为同文件内部引用，没有遗漏外部schema文件。

Root372入口额外需要 `backend/tests/contract/test_r18_public_extensions.py` 和 `contracts/schemas/public_api_extensions_v1.json`；这两项在 d68 已有且source/material/Root同blob，extensions 的14个 legacy defs与v2逐个语义相同。SDK自身没有 backend `ai_intel.*` 业务import；不能把这些纯schema测试说成REST/PG公开producer接线通过。

仓库外必须预备真实官方词表：`D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790`，3,613,922B，SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`，当前真实字节核验吻合。`output_budget.py:37–49` 要求 tiktoken==0.14.0/固定大小hash；`mcp_stdio.py:21` 从 DIANZI_MCP_ENCODING_CACHE_FILE 获取生产路径，缺失/损坏应 not_configured，禁止网络隐式下载。新旧SDK测试有固定宿主cache路径及子进程环境参数，安装库不自动准备词表。SDK_TEST_EVIDENCE_DIR/RUN是生成输出目录，默认唯一临时目录，不是需要复制的输入日志。

当前宿主 metadata：pytest8.4.2、MCP2.3.0、mcp-types2.3.0、httpx0.28.1、anyio4.15.1、tiktoken0.14.0、Pydantic2.13.5、jsonschema4.26.0、tzdata2026.4。固定 lock/pyproject是可复现安装依据；本轮没有安装、联网或重新初始化库。

## 关键字节与哈希

源码文本用Git过滤/canonicalLF比较，exact JSON样本用真实raw字节比较；作者CRLF源文本与Root LF raw SHA可能不同而同Git对象。v2原Git raw SHA `240eabf5...` 与合同记录的 canonical SHA `1c12e4de...` 是不同口径：实算 sort_keys=True/ensure_ascii=False/separators=(',', ':') 的compact UTF8 hash准确吻合合同，不是schema漂移。

| 必要路径 | 冻结Git blob | Git/canonicalLF或exact样本SHA256 | 字节 |
|---|---|---|---|
| `backend/src/ai_intel/ingestion/source_documents.py` | `614f5e2258b6d2d07143e6ec7c192eddec374f04` | `8e89a501f4afba59a8e7cee24ce9cb155e2edc8e75c12b09393ca23f4f8b7ea5` | 30769 |
| `backend/tests/unit/test_r06_source_excerpt_event_proof.py` | `aa7ae30c68d9b42ba36482f578afee9613222f40` | `7a4cbf4ebf008b8ca2df584bd407c22a44faa79b1ef913558ceb365057d4c3ef` | 7356 |
| `backend/tests/integration/test_r06_source_excerpt_event_proof_pg.py` | `3b14b3f60c3ae2f4def43b3da3a1e31bc624dbeb` | `be7eafb03406c7cee82d7576c7e3d593be502a516a45f86c6c41142768fb472c` | 15671 |
| `reports/runs/recovery_r06_source_excerpt_event_proof_20261016/nvd-response.json` | `212c03280e727ef2f7e6578acd56ccf5b6c8ae89` | `1bc5449375788cf417662cf3187bcd11c1484ed0b15026d4cf71760edd352c1f` | 4332 |
| `fixtures/recorded/vllm_vendor_20261015_public.json` | `7c4a826f72a67f4f69d4dd160c7de92b2b59d4e2` | `f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf` | 8800 |
| `fixtures/recorded/nvd_api_20261015_public.json` | `ffba95549db47eab529cebbb80a146b6309d5c56` | `c5cf6c0b00bc691dd97f1b8fd26504b7c104e047dfda0c278f54a6e70a66735a` | 3106 |
| `sdk/python/tests/fixtures/close_fault_stdio_fixture.py` | `fb8f8af7c9ec6196beef2b9b2fa0acfb6608915a` | `97d3d363f34922b47e2042cf5a1430fe664e953ad496ef1b5c3f2a334326dc6b` | 741 |
| `sdk/python/tests/fixtures/native_stdio_fixture.py` | `dd52a3ecbb05093ca43fcb87be132f73d4844f63` | `fd2e923a9227c9ee7fc0b05d2ac022ef1f9ed3a235f3406b1abfeddc03d19575` | 1293 |
| `sdk/python/tests/fixtures/unexpected_error_stdio_fixture.py` | `c312604dce5c7d6a877dbbccf900030f2e2e59bb` | `8c448aa919d723a1c0810ecc7cc3322f5665bde9931a1ac327d6d09a445a4d2e` | 1280 |
| `sdk/python/tests/r18_test_paths.py` | `b1eacf28c8ded86fd34818537f01c0feacad5ec2` | `a3d00776fe252d9136d258f42e0db9b530cdf8d3314edff6f35d333ba3e7146c` | 413 |
| `contracts/schemas/public_api_v2.json` | `9423eb93e42eb4a0beb1fc7e067df11358d8d931` | `240eabf5a810bade6f44b5731cee89ef57a4b313c6d76784bb897e8fefe45030` | 17683 |
| `contracts/schemas/public_api_v2_examples.json` | `bcf2077b56097959ff9b0545e8f8e3de324cf3b8` | `3b991bfc6610de89d62739965c556f60b0802ce8030e5abcdfc61c82234bfa70` | 1892 |

其余全部必要文件的完整hash见上述四个清单；不复制整个作者reports目录、不拷旧源码覆盖主分支、不重新生成fixture或修改oracle。

## 原测试事实与本轮命令

本诊断测试执行0；unit/integration/live/manual均not_run。下表是只读核原JUnit/receipt的历史事实，不能移作本诊断亲跑证据：

| 入口 | 真实时间+08/exit | 原结果与含义 |
|---|---|---|
| Root source_batch5 | 18:24:33–18:24:47 / 1 | 444 distinct：437pass/7failure，全为缺RUN archive的FileNotFoundError；业务断言前失败 |
| Root source_batch5_fix1 | 18:26:34–18:26:42 / 0 | 同444 distinct通过；原archive带入后，保留原red/XML |
| Root sdk_batch5 | 18:24:33–18:25:34 / 0 | 372 distinct=349 SDK+23 backend extensions；是不同于正式358的入口 |
| SDK独审 canonical | 17:02:39–17:03:31 / 0 | 358=349 SDK+9 tests/plan公共v2；另默认349重跑不增加分母，旧3 red保留 |
| SourceProof独审 | 原review receipt/summary | 469=405unit+44contract+2security+18integration；限定source8355新revision，历史独审PG不等于本轮PG |

原Root XML独立解析的(classname,name)去重与数量一致；原输入、阈值和分母没有改变。Root后来是否运行新的canonical入口，由主控自己的原receipt引用，本诊断不替其编造或回写时间。

本轮有持久实际+08/exit的主要命令如下；完整argv/cwd在各receipt，逐Git对象读取的实际命令/退出码在 sdk_command_index.json，SourceProof采集命令在两个SourceProof JSON。SDK主命令为 `D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_dependency_closure_diagnosis_20261016/diagnose_sdk_closure.py`；它执行Git/rg/AST/hash/metadata读取，没有导入业务或运行pytest。

| 收据 | 实际开始→结束+08 | exit |
|---|---|---|
| `sdk_diagnosis_receipt.json` | 2026-10-16T18:30:08.8360081+08:00 → 2026-10-16T18:30:32.5116495+08:00 | 0 |
| `integration_provenance_receipt.json` | 2026-10-16T18:32:29.5592721+08:00 → 2026-10-16T18:32:30.0818583+08:00 | 0 |
| `cbm_sdk_index_receipt.json` | 2026-10-16T18:33:19.9207188+08:00 → 2026-10-16T18:33:21.7317459+08:00 | 1 |
| `cbm_sdk_index_private_receipt.json` | 2026-10-16T18:33:35.2771403+08:00 → 2026-10-16T18:33:40.5744665+08:00 | 0 |
| `cbm_stdio_trace_receipt.json` | 2026-10-16T18:33:54.3068462+08:00 → 2026-10-16T18:33:58.4362897+08:00 | 0 |
| `cbm_budget_trace_receipt.json` | 2026-10-16T18:33:54.3068462+08:00 → 2026-10-16T18:34:01.9377176+08:00 | 0 |
| `cbm_sourceproof_index_receipt.json` | 2026-10-16T18:35:52.6979230+08:00 → 2026-10-16T18:35:59.5145315+08:00 | 0 |
| `cbm_sourceproof_trace_receipt.json` | 2026-10-16T18:36:16.0918916+08:00 → 2026-10-16T18:36:20.0119867+08:00 | 0 |

首次CBM用NTFS自有run目录cache失败exit1，原因secure cache-private需要私有目录；改用独立 `CBM_CACHE_DIR=/tmp/dianzi-dependency-closure-20261016-cbm` 后成功，原失败保存。SDK仅七产品源157nodes/600edges；SourceProof只ingestion源码398nodes/1862edges；均0skipped/partial/unusable。stdio、budget和persist_source_response trace均exit0，并与限定源码rg/AST交叉核验。图不含reports/secret/holdout/物料正文；budget图未连出文件读取边，不能据图证明文件闭包。

## 最小长期修复与未验范围

下个授权的Root集成任务应给每个已审包增加一份短的显式consumer清单：source/material两个SHA、实际测试argv、必需repo path+blob/raw SHA+consumer位置+recorded/synthetic/old-oracle分类、宿主输入版本/hash/大小及生成输出。集成器先核完整输入再应用源码差异，之后核带入物料与原Git字节；缺文件立即报真实缺口，允许逐条material输入进入，不用“reports全排除”过滤。原import核查保留但标为import层；递归源码/Path读取/subprocess参数/JSON refs/全局fixture由针对包的短清单补齐，无需新框架或扫描整个报告库。

当前两包字节闭包已存在，没有诊断发现的新增补丁。下一任务建议是主控复核该清单并沿原有正式入口引用新版本回归；此报告只awaiting_review，任务状态/progress未修改。评分证据仅E1/D1/X1的可复现集成、原oracle保护和真实问题定位；不增加来源live、模型问答、性能或完整R06/R18评分结论。

未验：业务运行imports/ABI、干净安装/跨平台CI、PG/vector扩展与权限、模型、外部来源/FOFA、网络live、前端/客户端、全仓回归/覆盖门、持续运行和人工/盲测。外部/模型/付费/PG调用0；没有读密钥、holdout、KEYS或环境秘密值。仅新增本报告及自有run诊断JSON/日志/helper/manifest；原业务、19集成WIP、测试oracle、schema、lock、作者物料和progress均未改。

本次写作结束/最后更新时间/证据截止：2026-10-16T18:40:06+08:00。
