# G-D · R11/T24 SBOM adapters 独立审查 1

What this change does: 本改动把受限版本的 CycloneDX/SPDX JSON 原字节转换成既有库存候选，同时保留实际字段位置、checksum、依赖关系、完整性声明和全 JSON 结构摘要。它不写资产事实、不授予导入写权限，也没有生产接线。

结论：**Verdict: Ship.** 仅限本报告列出的 pure adapters profile 加唯一依赖 checkpoint。没有发现本有界切片内需要阻止合入的 Must fix；未签完整 R11、T24、G-D 或最终 SBOM/10000容量验收。公共 parser 容量缺口、库存历史接线与其他原红项继续保留。作者 `awaiting_review` 不是本 reviewer 的结论依据；本 reviewer 不修改 `accepted` 或 progress，由主控按此范围登记。

报告实际写入时间：2026-10-16T06:05:17+08:00（Asia/Shanghai）。非作者 reviewer：`/root/r11_sbom_first_independent_review`。分支 `codex/r11-sbom-review1`，独立 WT `D:/wt/r11-sbom-review1`；没有修改作者 WT 或主仓业务树、没有 push。`review_commit=null`：本审查报告及 run 尚未提交，不能把依赖 cherry-pick commit 当作 review commit。

## 冻结边界与精确文件

集成基底：`e310f7735bd499c4d9fbcefe8a644e2309a16a62`。作者代码：`658ffb19af3f50c3b8e157e4f270dece92589444`。作者材料：`f6acedcd2b004671c317f55dd058f46e5e517de9`。

业务/原测试审查只包含四个新增文件：

- `backend/src/ai_intel/assets/sbom_parser.py`
- `backend/tests/unit/test_r11_sbom_parser.py`
- `backend/tests/contract/test_r11_sbom_contracts.py`
- `backend/tests/security/test_r11_sbom_boundary.py`

作者材料为 `docs/decisions/CR-R11_sbom_adapters.md`、`reports/tasks/R11-sbom-adapters.md`、原 run 的 manifest 与 111 gzip；精确逐文件清单在 `frozen_material_verification.json`。除本WT被授权的venv与工具缓存外，审查产物只写本报告和 `reports/runs/recovery_r11_sbom_review1_20261016/`；版本化变更仅有被明确授权的唯一 dependency cherry-pick。

主控追加授权的 dependency `48b56033cf5daf3ce8cfaa710c0acbda7cc2356e` 在本 WT 为 `bea469e5140a25877b076dee770db04fd944e2c7`；确切只变 `backend/pyproject.toml`、`backend/uv.lock`、`docs/decisions/CR-R11_R07_parser_dependencies.md`，逐 Git LF bytes 完全等于 root 该三文件。后半轮组合验证基于 `f6acedc + 48b5603`，没有包含 root 其他内容。

读取了仓库 AGENTS、`00_execution_map`、恢复 11/12 的 R11、真实 `docs/tasks/T24_asset_inventory.md`、数据/算法/测试合同、冻结 progress/交接、作者 CR/报告，以及实际安装的 ponytail 5.2.0 review SKILL。原 T24 六验收、原前置、容量阈值及金标没有减少。冻结 progress 的旧 pending 状态仅是该基底历史索引，本报告不代替最新主控登记。

## 审查范围、调用链与原声明

CBM 优先执行：src 索引 1458 nodes/7535 edges，但默认排除了 `ai_intel/assets`；随后显式 assets 索引 232 nodes/1018 edges。两者 not_indexed/skipped/partial/unusable 都为 0。分别取得 get_graph_schema/get_architecture 与 assets trace，完整参数、实际秒和 raw MCP 输出在 `cbm_*.command.json` / `.log`；CBM cache 为 `/tmp/dianzi-r11-sbom-review1-cbm`，allowed root 仅本 WT 相应源码目录。静态索引不是运行证明。

`source_callers.log` 全 src/tests `rg` 与 CBM 交叉确认：`parse_sbom` 生产调用者 **0**；`parse_manifest` 的入向是 `InventoryService.import_manifest` 和本新 adapter。inventory 现有两次调用在 `inventory.py:151/242`，current 判同在 `inventory.py:225` 只比较 projection hash；它们仍只接原 manifest，因此本轮没有 sidecar 历史、PG 写入或重判事实。未来 dispatcher 必须同事务保存 raw/sidecar、比较 combined hash并分配新编号，保留 WRITE_ASSET、HTTP Origin/CSRF/幂等流程；接线需要新的独立 review。

支持精确限定为 `cyclonedx_json` 1.5/1.6/1.7 和 `spdx_json` wire `SPDX-2.3`。SPDX v2.3.1 是维护规范/schema版本，不能把 wire 宣称为 SPDX-2.3.1，也不含 SPDX3、XML/RDF/tag-value。生产是受限投影 validator；没有运行全 schema validator。工具/pedigree/嵌套 services 的全局 refs、完整配置/许可语义等不由接受输入得到支持结论。

原始来源和候选分离：组件 ID 与 purl/display name/source ref 分开；普通 hashes/checksums只进 typed sidecar，没有变成容器 image_digest；dependsOn/provides/relationships不制造 dependency_path；外部 ref 不抓取、不增加已拥有组件。未知直接 version、生态/比较方案、完整性、配置、权限、渠道和暴露保留未知，complete composition也不支持缺组件的否定。PURL含版本不补直接version。实际解析库的规范化适用于 pypi 名称与 npm namespace；合法 qualifier/subpath、Unicode身份超过现有 ASCII 模型、非 required scope/external/versionRange显式 typed 拒绝。

READ_ASSET + 服务端 tenant scope + 已授权资产tenant一致先于解析；analyst有READ而无WRITE仍仅能构造候选，未变成已入库或已确认事实。没有创建 confirmed/installed/current研判记录。作用域来自认证上下文的上游责任不能由纯函数在本轮替代；函数不证明 asset_id 真实存在或源声明真实。

## 真实复跑

独立 CPython3.12.13，初始 `uv sync --frozen --offline --no-progress` 安装80包；批准的 packageurl-python0.17.6只安装本WT。唯一锁 cherry-pick 后再次 frozen/offline sync，新增PyYAML/stub；packageurl版本保持不变。pytest8.4.2、Ruff0.16.9、mypy1.20.2、jsonschema4.26.0、packaging26.3、semver3.1.0。精确完整 argv 保存在每个 `.command.json`，下附主要 argv；时间是实际观察，未补造初次工具探索时刻。

所有 pytest cwd 为 `D:/wt/r11-sbom-review1/backend`。计数列为 tests / failures / errors / skipped；JUnit时间为pytest层时间，起止包含进程启动，不互相冒充。

| 命令名 | Asia/Shanghai 实际秒 | exit | tests / fail / error / skip | JUnit秒 | 日志 |
|---|---|---:|---|---:|---|
| unit | 2026-10-16T05:55:26+08:00 → 2026-10-16T05:55:31+08:00 | 0 | 31 / 0 / 0 / 0 | 0.922 | `unit.log` / `unit.xml` |
| contract | 2026-10-16T05:55:26+08:00 → 2026-10-16T05:56:38+08:00 | 0 | 16 / 0 / 0 / 0 | 67.386 | `contract.log` / `contract.xml` |
| security | 2026-10-16T05:55:26+08:00 → 2026-10-16T05:55:30+08:00 | 0 | 36 / 0 / 0 / 0 | 0.269 | `security.log` / `security.xml` |
| regression | 2026-10-16T05:57:01+08:00 → 2026-10-16T05:57:08+08:00 | 0 | 225 / 0 / 0 / 0 | 3.803 | `regression.log` / `regression.xml` |
| independent_probes | 2026-10-16T05:58:07+08:00 → 2026-10-16T05:58:11+08:00 | 1 | 43 / 1 / 0 / 0 | 2.096 | `independent_probes.log` / `independent_probes.xml` |
| independent_probes_recheck | 2026-10-16T05:59:16+08:00 → 2026-10-16T05:59:20+08:00 | 0 | 43 / 0 / 0 / 0 | 2.197 | `independent_probes_recheck.log` / `independent_probes_recheck.xml` |
| combined_dependency_regression | 2026-10-16T06:00:21+08:00 → 2026-10-16T06:01:30+08:00 | 0 | 308 / 0 / 0 / 0 | 65.126 | `combined_dependency_regression.log` / `combined_dependency_regression.xml` |

原冻结31unit+16contract+36security+225regression=308个独立通过，重复组合复跑仍为308，不能累加为616。组合版本再次308 passed、0fail/error/skip、2条原Starlette/httpx弃用warning保留；补充自有43probe通过，去重后本轮351个可观察断言用例。自有probe位于run，未改作者或冻结原tests；没有把资源观察5进程凑成pytest通过数。定向 `--no-cov` 不代表项目覆盖率门或全suite通过，原阈值没有变。

43独立probe包括：三个CDX版本官方fixture；SPDX真正的Draft201909Validator方言；嵌套/转义重复键；NaN/-Infinity/溢出；key/value非法surrogate与合法代理对；NUL/$dynamicRef；精确1MiB/+1、depth16/17、raw nodes200000/200001；purl qualifier/subpath与私有URI惰性标签、npm %40namespace、pypi Foo_Bar规范化、Unicode显示名与超模型身份；缺直接版本；READ/跨tenant拒绝先于malformed；非required/external/range拒绝；完整性/配置仍unknown；edge/hash/license/comment/opaque变化时projection不变、sidecar/combined必须变化，snapshot_id仍相同（证明它没有自动持久化历史）；对象键顺序/空格不改combined。

静态与材料检查：

| 命令名 | 实际 cwd | Asia/Shanghai 实际秒 | exit | 日志 |
|---|---|---|---:|---|
| uv_sync | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:54:10+08:00 → 2026-10-16T05:54:17+08:00 | 0 | `uv_sync.log` |
| dependency_install | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:54:37+08:00 → 2026-10-16T05:54:38+08:00 | 0 | `dependency_install.log` |
| ruff | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:56:33+08:00 → 2026-10-16T05:56:33+08:00 | 0 | `ruff.log` |
| format | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:56:33+08:00 → 2026-10-16T05:56:33+08:00 | 0 | `format.log` |
| mypy | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:56:33+08:00 → 2026-10-16T05:56:47+08:00 | 0 | `mypy.log` |
| dependency_cherry_pick | `D:/wt/r11-sbom-review1` | 2026-10-16T05:58:27+08:00 → 2026-10-16T05:58:27+08:00 | 0 | `dependency_cherry_pick.log` |
| dependency_sync | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:59:10+08:00 → 2026-10-16T05:59:13+08:00 | 0 | `dependency_sync.log` |
| combined_mypy | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T06:00:21+08:00 → 2026-10-16T06:00:23+08:00 | 0 | `combined_mypy.log` |
| format_no_cache | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T06:00:21+08:00 → 2026-10-16T06:00:22+08:00 | 0 | `format_no_cache.log` |
| frozen_materials | `D:/wt/r11-sbom-review1` | 2026-10-16T05:56:13+08:00 → 2026-10-16T05:56:25+08:00 | 0 | `frozen_materials.log` |
| resource_probe | `D:/wt/r11-sbom-review1/backend` | 2026-10-16T05:59:52+08:00 → 2026-10-16T05:59:55+08:00 | 0 | `resource_probe.log` |
| dependency_verification | `D:/wt/r11-sbom-review1` | 2026-10-16T06:01:16+08:00 → 2026-10-16T06:01:18+08:00 | 0 | `dependency_verification.log` |
| source_callers | `D:/wt/r11-sbom-review1` | 2026-10-16T06:01:16+08:00 → 2026-10-16T06:01:16+08:00 | 0 | `source_callers.log` |
| official_sources | `D:/wt/r11-sbom-review1` | 2026-10-16T06:01:49+08:00 → 2026-10-16T06:01:53+08:00 | 0 | `official_sources.log` |
| frozen_diff_check | `D:/wt/r11-sbom-review1` | 2026-10-16T06:01:16+08:00 → 2026-10-16T06:01:17+08:00 | 0 | `frozen_diff_check.log` |

Ruff check四新增文件、format四文件、mypy118源文件均通过；组合锁后mypy仍118文件通过。首次并行ruff/format的format exit0但有cache写入拒绝warning，原日志保留；后用同规则 `format --check --no-cache` 四文件通过，没有禁用风格规则或修改业务代码。`git diff --check`涵盖基底到组合HEAD，exit0。

## 官方 bytes、Git LF 与依赖完整性

独立重新从固定官方 CycloneDX/specification 1.5/1.6/1.7、spdx/spdx-spec v2.3.1 URL下载四schema，分别164769/252625/315607/47602 bytes，**全部与冻结gzip解压raw逐字节相同**，未禁用TLS、未抓任意文档链接。官方PyPI0.17.6metadata也逐字节吻合冻结材料。下载实际命令/秒、原bytes与hash在 `official_source_verification.json` / `official_independent/`。schema只是输入验证材料，不是改仓权限指令。SPDX原contract统一用了Draft7，本review另按实际`$schema`选Draft201909Validator并验证fixture；没有观察到此冻结schema使用会造成此次fixture差异的2019专有规则，因此不把一个方言标记差异虚构成业务反例。

四schema raw SHA256：

- CDX1.5：`067f7824b08653839ea050ae9e09ca48375eadc2652b0e2a299476e7db90335b`
- CDX1.6：`3e92dddbc30cf7f6a02b80f0942b1a4cfd4fb1c26f1dfc4310afa9d613cafb93`
- CDX1.7：`df472ef4aaf593904c479293723a1a5c191d6672715c93b3c0b5c318f3914221`
- SPDX维护schema：`4126dc29f15e92feec92e9622f4939131ad58b125d6f578aa93e980a6e6f3212`

111/111 gzip的Git bytes、本地gzip bytes、长度/SHA256、解压raw长度/SHA256全部吻合；各作者JUnit计数/time也逐一核对原XML，包括失败/collection error材料。四代码 `git show 658ffb1:path` 与 `f6a:path` 相同，`git hash-object --path`与冻结blob ID相同、LF bytes/SHA256与作者proof相同。官方wheel36776 bytes，SHA256 `31a85c2717bc41dd818f3c62908685ff9eebcb68588213745b14a6ee9e7df7c9`，MIT；本venv 12个packageurl `.py`逐字节等于该wheel，而不只比较版本字符串。

作者manifest的**Git LF原bytes**SHA256 `0f9b2733b562e93d1d0403b1ee8ab6c1347025888df77af0f43aaa218c9275ce`；本地CRLF视图 `5472959600582830c9c88f504101694ed0733b7669b7be82e2623403b1eb89ce`，不能替代前者。锁Git LF SHA256 `8dadd7cb420236fd2532667ac23c7451b2d35b2b2098f9f4e07e8e74ccd8a74d`，工作视图另hash；93原包版本全部未变，新增purl0.17.6与types-pyyaml6.0.12.20260906后95包。PyYAML6.0.3仅从semantic间接升为直接。Package URL库在新代码实际用于解析/strict validate，必要且没有自制PURL库；PyYAML和Apache-2.0 stub属于另一已授权R07用途，这里只核对共享锁/许可证/类型环境，没有为R07业务验收签字。

## 保留缺口与真实容量观察

已知兼容issue `R11-SBOM-PROJECTION-NODES` 仍存在，位置 `sbom_parser.py:794–800`、原 `manifest_parser.py:23/251`（公共预算50000）。触发输入为官方schema有效CDX1.7 10000个type/name/purl/version，原797858 bytes，raw SHA256 `5a524d5fdc2e9bebef8fafbaa1870080ffb7be896b561da3c11d35a611ffed4d`；原来源未到1MiB且未超10000组件，投影却90005节点，实际typed `projection_node_limit`、没有部分成功或截断。较窄反例10000个type/name/version只有478962 bytes，投影50005节点，也typed拒绝；同根因也作用于name/versionInfo的SPDX投影。不能对外称所有10000规模输入已支持。

此不是本review静默接受完整容量；它已在冻结CR/作者报告显式列为待主控另批公共parser预算修改，本切片明确禁止改原parser37、锁阈值/公共结构预算。因此它保留为**完整容量与后续生产接线验收阻塞**，在本受限pure adapter审查里不转成“新Must但无人修”。最小修复应是单独批准协调公共strict JSON与manifest预算、保持真实边界不截断，再重跑官方有效dense10000与既有225回归；不是降组件上限、删难例或改金标。该缺口影响T24扩展完整容量，不授权本review修它。

五个隔离Windows进程观察（没有负载SLA/内存门槛，不可称性能验收）：name-only10000原408962 bytes→10000候选，0.244s/峰值Working Set59678720 bytes；dense10000→typed拒绝，0.217s/51171328 bytes；two-field10000→typed拒绝，0.099s/49020928 bytes；raw200000节点→空候选但完整raw保留，0.069s/52400128 bytes；200001节点→typed拒绝，0.081s/52297728 bytes。每子进程实际argv、cwd、秒、exit和原输入gzip/hash在`resource_observations.json`及`resource-*`。这些只说明此次受限输入观察，不是并发/持续运行/正式性能结果。

没有新的切片内Must fix；没有通过推测增加缺陷。未被抽查的全规范字段业务语义属于未验证范围。R11其他规则/研判/OpenVEX与T24整卡依然partial，不能由本Ship消除。

## 红日志与未运行项

作者原test-first module缺失、首次contract/security sibling import collection error、Ruff首检等失败日志均在111gzip内保留并已核hash；它们不作为本轮通过数量。作者初次工具探索未记录时刻仍未记录，不能补写。旧CSV探索37/1、旧CPU失败/全suite未跑和imports202/analyst写权限/迁移冲突延续原记录，本review未复现或关闭它们。

本review的第一次43自有probe为42passed/1failed：所造SPDX10000带可选filesAnalyzed=false原文1138071 bytes，违反探针前提“小于1MiB”，尚未调用业务函数。只去掉该可选字段让该自造输入进入预算；没有修改被测原tests、原阈值或预期typed节点错误。首红log/XML/receipt原bytes保留，之后43/43通过。尝试复制首红脚本时用了backend下错误相对路径而未复制成功；该shell工具输出只在会话，不声称原首红脚本已封存。首红log含实际构造表达式与1138071实数，最终脚本另封存，不把最终脚本冒充首红脚本。

原format cache warning保留，重跑无cache规则成功。web读取CDX1.7文档超过工具内容上限；不把该读失败当业务失败，已独立下载固定官方schema并证明原bytes一致。SPDX包文档read成功，只有材料作用；本轮官方公开资料可达并非产品live。

unit/contract/security：passed（限定此切片）。integration/真实PG、frontend、e2e、产品live、manual/人工真实性核验：**not_run**。没有PG端口/临时库、FOFA/模型/第三方资产请求、PoC执行、秘密读取、公开发布、全suite覆盖率/准确率或持续运行结论。资料下载不冒充SBOM生产live。

## 原T24案例与评分项证据

| 原案例 | 本slice实际证据及限制 |
|---|---|
| C01 合法JSON/CSV一致 | SBOM→既有DTO投影与限版本官方schemafixture已测；原JSON/CSV相关回归通过，但新SBOM库存事务未接，不能签C01整项 |
| C02 重复导入幂等 | 函数确定性/组合hash与key order已测；PG幂等、重复提醒与import receipt未由本轮验证 |
| C03 版本改动新旧并存 | 直接版本/原位置与source/combined摘要已测；库存历史与current/outbox未接 |
| C04 不完整不排除 | unknown/空declared_scope、缺版本、complete仅sidecar有直接断言；没有输出安全否定 |
| C05 超界非法拒绝 | 1MiB/depth/node/components与malformed typed拒绝、不返回部分成功有证据；高密度10000明确未满足；CSV探索历史不删除 |
| C06 跨tenant/私有路径 | READ scope/tenant先检、非bytes路径typed拒绝；新的HTTP写授权/CSRF/Origin/PG边界未接 |

F2：有限版本组件身份、直接版本、字段位置与原声明的安全投影证据。F3：资产相关未知信息保留，不声称问答或四态研判端到端。P2：这只是功能/边界断言，没有准确率、召回率或冻结盲测分母。E1/D1：独立锁环境、真实质量命令、Git/LF/raw材料追溯；不代表全工程/评分项验收。

下一批建议：主控登记本有界pure profile独立Ship和48b5603组合证据；公共容量预算另批修复；之后明确dispatcher/API格式与private DTO、combined/sidecar历史事务、重放/并发/回滚，再由新的独立reviewer签生产接线切片。T24原六验收和完整R11/G-D仍需后续合并验收。

最终报告/run raw bytes冻结收据在 `review_seal_receipt.json`，其中whole-report真实SHA256、Git filtered blob、run manifest hash和每文件raw/gzip hash逐一核验。`review_commit`保持null；没有凭空的bodyhash或未提交review SHA。

## 主要实际 argv 附录

### unit

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "tests/unit/test_r11_sbom_parser.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/unit.xml"
]
```

### contract

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "tests/contract/test_r11_sbom_contracts.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/contract.xml"
]
```

### security

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "tests/security/test_r11_sbom_boundary.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/security.xml"
]
```

### regression

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "tests/unit/test_r11_manifest_parser.py",
  "tests/unit/test_r11_manifest_parser_identity_time.py",
  "tests/contract/test_r11_manifest_candidate.py",
  "tests/security/test_r11_manifest_parser_boundary.py",
  "tests/unit/test_t26_version_engine.py",
  "tests/contract/test_r11_version_ranges_contract.py",
  "tests/security/test_r11_version_ranges_security.py",
  "tests/unit/test_t06_access_scope_boundaries.py",
  "tests/unit/test_r11_inventory.py",
  "tests/contract/test_r11_inventory_contracts.py",
  "tests/security/test_r11_inventory_boundary.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/regression.xml"
]
```

### independent_probes_recheck

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "../reports/runs/recovery_r11_sbom_review1_20261016/test_independent_probes.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/independent_probes_recheck.xml"
]
```

### combined_dependency_regression

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "pytest",
  "tests/unit/test_r11_sbom_parser.py",
  "tests/contract/test_r11_sbom_contracts.py",
  "tests/security/test_r11_sbom_boundary.py",
  "tests/unit/test_r11_manifest_parser.py",
  "tests/unit/test_r11_manifest_parser_identity_time.py",
  "tests/contract/test_r11_manifest_candidate.py",
  "tests/security/test_r11_manifest_parser_boundary.py",
  "tests/unit/test_t26_version_engine.py",
  "tests/contract/test_r11_version_ranges_contract.py",
  "tests/security/test_r11_version_ranges_security.py",
  "tests/unit/test_t06_access_scope_boundaries.py",
  "tests/unit/test_r11_inventory.py",
  "tests/contract/test_r11_inventory_contracts.py",
  "tests/security/test_r11_inventory_boundary.py",
  "--no-cov",
  "-q",
  "--junitxml=D:/wt/r11-sbom-review1/reports/runs/recovery_r11_sbom_review1_20261016/combined_dependency_regression.xml"
]
```

### ruff

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "ruff",
  "check",
  "src/ai_intel/assets/sbom_parser.py",
  "tests/unit/test_r11_sbom_parser.py",
  "tests/contract/test_r11_sbom_contracts.py",
  "tests/security/test_r11_sbom_boundary.py"
]
```

### format_no_cache

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "ruff",
  "format",
  "--check",
  "--no-cache",
  "src/ai_intel/assets/sbom_parser.py",
  "tests/unit/test_r11_sbom_parser.py",
  "tests/contract/test_r11_sbom_contracts.py",
  "tests/security/test_r11_sbom_boundary.py"
]
```

### combined_mypy

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "-m",
  "mypy",
  "src/ai_intel"
]
```

### uv_sync

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "uv",
  "sync",
  "--frozen",
  "--offline",
  "--no-progress"
]
```

### dependency_install

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "uv",
  "pip",
  "install",
  "--python",
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "--index-url",
  "https://pypi.org/simple",
  "--no-deps",
  "packageurl-python==0.17.6"
]
```

### dependency_cherry_pick

实际 cwd：`D:/wt/r11-sbom-review1`；完整 argv：

```json
[
  "git",
  "cherry-pick",
  "48b56033cf5daf3ce8cfaa710c0acbda7cc2356e"
]
```

### dependency_sync

实际 cwd：`D:/wt/r11-sbom-review1/backend`；完整 argv：

```json
[
  "uv",
  "sync",
  "--frozen",
  "--offline",
  "--no-progress"
]
```

### official_sources

实际 cwd：`D:/wt/r11-sbom-review1`；完整 argv：

```json
[
  "D:/wt/r11-sbom-review1/backend/.venv/Scripts/python.exe",
  "reports/runs/recovery_r11_sbom_review1_20261016/verify_official_sources.py"
]
```


Not checked: 完整R11/T24/G-D、公共容量修复、全schema语义/所有版本、PG/前端/e2e/live/manual、全suite、旧失败闭合、原声明真实性与最终评分。Verdict: Ship（仅列明切片）。
