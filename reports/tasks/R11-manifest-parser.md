# R11 / T24 · 清单到资产快照候选的独立准备切片

记录时间：2026-10-16T02:00:39.369+08:00。切片状态：`awaiting_review`；实现状态：`complete`（仅本报告边界）；unit、contract、security：`passed`。integration、frontend、e2e、live、manual：`not_run`。整R11/T24仍`partial`，G-D正式门尚未通过，无push、无accepted、无资产导入成功声明。

基线：`349c5e3ec27196257b98cdfcb63c75fb50157978`。代码冻结：`e91db79889972c24a209997b4dcec5731d0c809f`。独立分支：`codex/r11-manifest-parser`；工作树：`D:/dianzi-wt-r11-manifest-parser`。材料提交随后独立冻结，`evidence_manifest.json`保留代码与日志的长度、SHA256及版本。

## 真实前置与边界冻结

已读AGENTS、00执行索引、12恢复R11、T24/T29、03/04/05合同、progress状态与交接。指定基线的`domain/records.py`和`domain/values.py`没有Asset、AssetSnapshot或Component类型；全源码和测试rg没有其调用方。03 §3.7只有文档字段，公开v2 JSON Schema的Component子集也不能替代资产领域类型。主控明确批准仅在`assets/manifest_parser.py`新增内部SnapshotCandidate/ComponentCandidate；不修改公共领域/schema，不冒充PG权威快照。

既有`domain/access.py:32`的ANALYST仅有READ_ASSET/READ_PUBLIC；05合同第42行却将POST `/asset-snapshots`写为analyst。该权限冲突交主控后续正式接线处理，本片复用READ_ASSET和`enforce_visible`做纯计算可见范围验证，未修改角色表，读权限不代表写入/导入权限。目标asset_id的PG归属查询仍需调用方在认证事务中完成；本函数仅信任外部已认证的tenant/资产归属上下文。

输入：严格bytes、明确format、现有AccessScope、外部授权asset tenant、UUID asset_id、正snapshot_number、明确source_version、带时区observed_at/recorded_at。输出：不可变tuple组成的内部候选、原字节/source SHA256、source版本、parser版本、组件冲突定位。缺版本为None、缺生态为unknown；未知生态的version_scheme为unknown。PyPI/npm的scheme只按明确生态声明为pep440/semver；此模块不解析、比较或证明精确版本有效性。

首期格式为`json_manifest_v1`（`format_version=1`）及`csv_components_v1`。JSON字段与候选范围见代码常量；CSV必须显式将语义组件字段映射到真实列名，拒绝未映射/重复/缺失列。CSV仅承载组件列，配置、声明范围及完整性缺失保持unknown；不声称CSV配置导入已实现。CycloneDX、SPDX、XML、requirements.txt均返回unsupported_format，不建占位适配器。T24步骤6的SBOM扩展仍未完成。

上限：10,485,760 bytes、10,000组件、JSON深度16、JSON节点50,000、单字符串4096、范围/权限/依赖路径列表64项。节点上限也是独立边界，富字段JSON可能先达到节点上限；不是对所有10,000条富字段清单均可解析的承诺。复用既有strict_json_object的重复键、UTF-8、非有限数、NUL检查，之后施加本片更窄深度/字段边界。没有新增依赖。

configuration只支持model_name、provider_name、trust_remote_code、authentication_required；input_channels只支持public_api、uploaded_documents、retrieved_web_content；network_exposure只支持public_endpoint、outbound_network_allowed。字段缺失与显式None均保留未知，显式空tool_permissions与未知None分开。声明不会授予工具或网络能力，清单声明完整也不自动证明真实完整性。

内部UUID、package_name、display_name、purl分别保存。purl只保留不含qualifier/subpath的受限来源标签，不作完整PURL规范校验，不验证其包名与显式包身份一致，也不从中填生态/版本；后续匹配必须用明确生态与package_name，不能把该标签当已验证身份。没有生态归一、安装、shell、eval、URL抓取、文件读取、外部资产扫描。

## 改动文件与实现

- `backend/src/ai_intel/assets/manifest_parser.py`：输入边界、JSON/CSV解析、组件/配置候选、字段来源、保守冲突提示与确定性快照hash/ID。
- `backend/tests/unit/test_r11_manifest_parser.py`：正常、未知、部分、配置差异、冲突、格式、权限、版本变化、重复及并发回放。
- `backend/tests/contract/test_r11_manifest_candidate.py`：03内部候选字段、认证身份、source/version/hash、UTC时间及不可变结构。
- `backend/tests/security/test_r11_manifest_parser_boundary.py`：身份伪造、秘密字段、命令/install脚本、symlink字段、路径遍历、文件Path对象、URL、XXE、禁IO配对、字节/组件/深度/字符串边界。
- 本报告和`reports/runs/recovery_r11_manifest_parser_20261016/`：真实命令、原始日志、JUnit、CBM、无损原失败归档与哈希清单。
- `.gitattributes`：只追加本次唯一run目录的`-text`与原始日志空白属性，防Git改写证据字节；原Move-Item失败stderr有PowerShell原始尾空白，另对该唯一文件追加`-diff`保留原始字节，避免将证据当代码修剪。未扩大至其他目录。该配置文件本身按Git常规CRLF→LF归一，manifest另列其Git blob与工作副本hash；run原始材料不归一。

本片没有修改assessment/version_ranges、hunter/quake/fofa/aggregate、domain/schema、迁移、依赖/lock、配置、API、worker、frontend或progress。当前唯一源码调用入口是测试；主控后续负责PG/REST/UI接线，候选模块没有内存数据库或另一套业务真相。

## 真实执行与结果

工作目录均为本工作树`backend`；实际解释器为既有`D:/dianzi/backend/.venv/Scripts/python.exe`，PYTHONPATH指向本工作树`backend/src`。没有修改共享venv/lock。每条命令的完整参数、开始/结束（+08:00）、退出码、代码SHA及原始stdout/stderr在同名JSON/log；下面使用`python`作该已记录绝对解释器的简称。

| 证据 | 实际命令核心 | 退出码 / 结果 |
|---|---|---|
| red | `python -m pytest tests/unit/test_r11_manifest_parser.py --no-cov -q` | 2；模块尚未存在，0执行，collection error；不是环境缺失或业务失败 |
| green_initial | 同上 | 0；31 passed |
| mypy_initial | `python -m mypy src/ai_intel/assets/manifest_parser.py` | 1；完整性Literal类型1 error，已修复 |
| green_boundary | 三个新测试文件，`--no-cov -q` | 1；62 passed、1 failed、2 errors，见下述仪器纠正 |
| green_boundary_fix | 三个新文件，`--no-cov -q --junitxml=...` | 0；64 passed |
| pre_freeze_boundary | 三个新文件，`--no-cov -q` | 0；补并发后65 passed |
| fixed_boundary | 三个新文件，`--no-cov -q --junitxml=...` | 0；代码e91db79，32 unit + 1 contract + 32 security = 65 passed，0 failed/skip |
| fixed_related_regression | t04_domain_contracts、t06_access_scope_boundaries、t18_model_clients、r08_aggregate_connectors、r13_fofa_relay，`--no-cov -q --junitxml=...` | 0；代码e91db79，112 passed，0 failed/skip |
| fixed_mypy | `python -m mypy src/ai_intel` | 0；100源文件通过 |
| fixed_ruff | `python -m ruff check` 本片源码及三个测试文件 | 0；通过 |
| fixed_format | `python -m ruff format --check` 同四文件 | 0；4文件格式通过 |

`--no-cov`明确用于独立解析与相关回归，不代表全工程覆盖率检查或降低正式覆盖门槛。integration/frontend/e2e/live/manual未运行；T24原集成入口尚不存在，未调用或编造集成数量。

原green_boundary的1失败是证据测试误要求repr里连合法Component属性名package_name都不能出现。真实原字节已由source_bytes repr=False隐藏；修正为原JSON字符串及source_bytes=不能出现在repr。不能由此声称序列化/导出安全已验收：`dataclasses.asdict(ManifestParseResult)`确实含原source_bytes，合同测试明确断言这一保留行为；`asdict(snapshot)`不含原字节。没有公开导出接口，后续必须受控处理ParseResult。

另外2 errors分别是同一超10MiB bytes参数的setup/teardown：pytest自动测试ID超过Windows环境变量32767字符限制，尚未进入解析业务断言。仅增加显式ID empty/above-byte-limit，原bytes表达式及10MiB门不变。没有改金标、阈值、评分分母或删除难例。

原失败stdout为41,951,937 bytes。Git保存无损gzip（44,590 bytes）和`original_failure_archive.json`，原字节SHA256为`3cccbce776d43c2fb1910a851859ae70de0d3290a387efbd870814e78d8b0323`，解压长度/hash逐一相同。仓外原始日志位于`D:/dianzi-local-evidence/recovery_r11_manifest_parser_20261016/green_boundary.stdout.log`。

材料首次`git diff --cached --check`exit2，定位到原Move-Item失败stderr第7行尾空白及EOF空行；源码冻结diff check为0。保留原日志字节并用上述唯一`-diff`证据属性后再检查，不以修改日志隐藏原始失败。此临时stage诊断只保留recorded_at，未记录精确开始/结束；不编造该时长。

首次单文件Move-Item因本片此前Get-Content巨行读取占用而exit1。主控授权后，逐PID复核CommandLine、CreationDate、ParentProcessId并只停止本片36188/35712/20308/46396（各stop exit0）；没有按进程名批量kill或停止WSL/数据库。35712挂起命令中后续Ruff未执行，记not_run；质量结论来自另行实际执行的固定SHA检查。重试单文件native Move-Item前验证绝对源/目标目录及原hash/size，移动后逐hash/size相同，exit0。完整识别/停止/移动证据保留。这是日志查看仪器故障，不是解析性能结论。

## CBM与调用方影响

官方portable codebase-memory-mcp 0.11.0真实help/schema已核实，独立XDG缓存`/tmp/dianzi-r11-manifest-parser-cbm`，只索引本WT源码。初始backend/src图1292节点/6424边，工具默认排除了`ai_intel/assets`，报告不把该图说成覆盖资产代码。补建assets目录图107节点/390边，5个源码文件，parse_partial/unusable与not_indexed为0；冻结代码的schema/index/trace日志齐全。

真实AccessScope.enforce_visible入向15调用方保持原样；新parse_manifest在资产图产品入向0、出向21（含解析与候选构造）。源码rg补足跨图导入：本片只复用AccessScope/READ_ASSET与strict_json_object，未改其调用方行为。`rg_callers.log`与各CBM日志保存定位范围，不用旧accepted状态替代源码证据。

## 原案例与评分证据边界

| 原要求 | 本片证据 | 未完成部分 |
|---|---|---|
| T24-C01 合法JSON/CSV规范一致 | 相同组件业务内容的snapshot hash/ID一致，原bytes/hash/定位分开 | REST/PG导入未接 |
| T24-C02 重复导入幂等 | 纯候选重复/16次并发回放确定性 | PG幂等、变更事件与不重复提醒未验证 |
| T24-C03 版本变化 | 新旧候选值与ID/hash不同、旧对象不可变 | 历史持久化/current指针未实现 |
| T24-C04 完整性未知 | partial/unknown保持，不填默认配置或缺组件排除事实 | 规则研判/排除证据链未实现 |
| T24-C05 超行/非法CSV | 正常10,000与超限10,001组件、非法列/格式行定位，不返回部分结果 | 异步上传/错误展示未接 |
| T24-C06 越租户/私有路径 | 认证scope先拒绝越租户；Path、symlink字段/路径遍历及未知字段拒绝 | asset_id的PG租户归属仍由后续服务查询 |
| R11 缺版本/生态/部分/配置冲突 | 真实可解析的本地JSON/CSV候选；未知保留、配置值分离、多版本冲突保留所有字段位置 | 四态规则、3→5可靠产品真值、提交校验、OpenVEX与界面未实现 |

F2/F3/P2只登记候选输入质量与追溯的局部代码证据；无准确率、性能、评分或真实资产授权结论。所有fixtures显式合成且隔离于unit/contract/security。FOFA授权资产范围仍未取得，不把fixture租户或模拟配置说成用户授权资产；G-D正式门和T29导出限制未闭合。

## 下一步交接

由新的非作者reviewer审固定e91db79及材料manifest，复跑65新增与112相关回归、质量和压缩证据；通过本片review不代表整R11/T24/G-D通过。主控后续在获准正式阶段内解决写权限合同冲突，接PG权威快照/认证事务、资产归属、幂等和历史API、规则/版本模块与UI，再按原六项集成验收完成T24。SBOM扩展需选定规范版本与受支持子集后独立核验。
