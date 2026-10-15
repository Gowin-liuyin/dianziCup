# R11/T24 · 有界 SBOM 纯适配交接

状态：`awaiting_review`；本切片实现 `complete`，完整 R11/T24 仍 `partial`。独立审查由主控另派，本作者不签 accepted、不 push。日期 2026-10-16，所有收据时间为实际 Asia/Shanghai +08。

独立 WT `D:/wt/r11-sbom-adapters`、分支 `codex/r11-sbom-adapters`，基底 `e310f7735bd499c4d9fbcefe8a644e2309a16a62`。代码冻结 `658ffb19af3f50c3b8e157e4f270dece92589444`，只新增 [sbom_parser.py](../../backend/src/ai_intel/assets/sbom_parser.py)、[unit](../../backend/tests/unit/test_r11_sbom_parser.py)、[contract](../../backend/tests/contract/test_r11_sbom_contracts.py)、[security](../../backend/tests/security/test_r11_sbom_boundary.py) 四文件。材料为本报告、[CR](../../docs/decisions/CR-R11_sbom_adapters.md) 和 `reports/runs/recovery_r11_sbom_adapters_20261016`。未修改 inventory/router/parser/contracts/App/auth/locks/migrations/progress 或原测试。

## 实际能力与合同边界

签名及字段映射见 CR。实际 bytes→既有 ManifestParseResult/SnapshotCandidate/ComponentCandidate，支持 CycloneDX JSON 1.5/1.6/1.7、SPDX JSON wire SPDX-2.3（官方维护规范/schema v2.3.1）。不支持其他 wire 版本或 XML/tag-value/RDF；不返回空结果掩盖格式错误。规范依据为 [CDX 官方 overview](https://cyclonedx.org/specification/overview/)、[JSON 1.7](https://cyclonedx.org/docs/1.7/json/)、[SPDX package](https://spdx.github.io/spdx-spec/v2.3.1/package-information/)、[SPDX document](https://spdx.github.io/spdx-spec/v2.3.1/document-creation-information/)，原 schema 与许可证 bytes/hash 封存于本 run。

READ_ASSET/服务器非空租户/授权租户一致是候选解析前置；写库仍需现有 WRITE_ASSET 与 HTTP CSRF/Origin/auth lock/idempotency。真实观察时间由调用方提供，不从 now、SBOM 创建时间或包名推断。清单完整性始终 unknown，配置/权限/渠道/暴露不推断；complete composition 仅原声明 sidecar，缺组件不产生排除证据。

PURL 复用主控批准的 [packageurl-python 0.17.6](https://pypi.org/project/packageurl-python/0.17.6/)，再复用既有 PyPI/npm 版本比较器核对实际声明；缺直接版本不补，其他生态未知比较。qualifier/subpath、超既有包名/PURL 标签、非 required scope、external/versionRange 均 typed compatibility error，不伪装 installed。适配只展平实际 components/metadata.component；graph 不伪 path，checksum 不伪 image_digest，外部文档不变为拥有资产。

typed component-source、checksum、dependency-edge、completeness、external-document sidecars 含真实 JSON Pointer；中文、斜线/波浪号正确编码。原 parser 的冲突版本 issues 也回映原位置，保留双方版本。

三类 hash 明确分开：projection_hash 是现有 snapshot_sha256；raw_hash 为精确上传 bytes；sidecar_hash 为排序对象键但保留数组顺序的完整 JSON 结构摘要。combined hash 包含 adapter_version/projection_hash/sidecar_hash。graph/checksum/composition/注释改变时同投影但 combined 改变；只看现有 projection hash 仍会吞掉历史变化。**本轮无生产 dispatcher caller、无库存存储或重判接线**；函数候选 snapshot_id 仍由现有 projection hash+编号产生，主控后续必须按 combined 判等并持久化 sidecar/原文。

这是受限投影 validator，不是全规范 validator。生产无 JSON Schema 校验器或远程解析器；官方 schema 只在 offline fixture contract tests 中运行。工具/pedigree/嵌套 services 等其他全局 refs、完整许可/注释/未知配置业务语义超此 profile，保留 raw/结构摘要，不能声称分析完备。

## 真实测试与环境

own venv `D:/wt/r11-sbom-adapters/backend/.venv`，CPython3.12.13。`uv sync --frozen --offline --no-progress` exit0、80包；approved `uv pip install --python <own venv python> --index-url https://pypi.org/simple --no-deps packageurl-python==0.17.6` exit0，只本 WT，未改共享锁。运行版本 pytest8.4.2、Ruff0.16.9、mypy1.20.2、jsonschema4.26.0、packaging26.3、semver3.1.0，见 runtime_versions 收据。合并/运行前由主控统一锁固定 packageurl-python==0.17.6；缺此步骤新模块无法导入。

固定官方 wheel 实际下载 36776 bytes、SHA256 `31a85c2717bc41dd818f3c62908685ff9eebcb68588213745b14a6ee9e7df7c9` 与官方 PyPI发布值一致；MIT。只研究期官方公开资料下载，无 paid API、模型下载、FOFA、资产访问、PG端口/连接或秘密读取。未启 packageurl 的 URL 转换网络功能。

最终安装审核命令再执行exit0，真实+08起止/argv在dependency_install_verification；installed_code_proof逐一验证本venv 12个packageurl Python文件与官方wheel原bytes完全相同，未把只有包版本字符串当依赖完整性证明。

最终 [attempt_3 commands原bytes](../runs/recovery_r11_sbom_adapters_20261016/attempt_3/commands_final.json.gz) 按gzip封存，解压可读完整 argv/cwd、+08秒、exit、log、JUnit。测试 cwd 为 WT/backend；以下 `python` 均指本 WT venv。定向 `--no-cov` 不代表工程覆盖率门，不改 pyproject 门槛。

| 检查 | 实际命令核心 | exit / 数量 / pytest秒 |
|---|---|---|
| unit | `python -m pytest tests/unit/test_r11_sbom_parser.py --no-cov -q --junitxml=.../unit_final.xml` | 0；31 passed；0.716 |
| contract | `python -m pytest tests/contract/test_r11_sbom_contracts.py --no-cov -q --junitxml=.../contract_final.xml` | 0；16 passed；51.696（含完整官方schema 10000组件核验） |
| security | `python -m pytest tests/security/test_r11_sbom_boundary.py --no-cov -q --junitxml=.../security_final.xml` | 0；36 passed；0.158 |
| 原相关回归 | 4个manifest parser、3个version engine、access scope及3个inventory unit/contract/security文件 | 0；225 passed；2.035；2条原httpx/Starlette弃用 warning 保留 |
| 风格/格式 | `python -m ruff check` / `format --check` 新4文件 | 都0，4文件 |
| 类型 | `python -m mypy src/ai_intel` | 0，118源文件无问题 |
| Git | 冻结前 `git diff --cached --check` | 0，4新增源码/测试文件 |

最终 83 新用例 +225 原回归=308 个实际通过；每层0 failures/errors/skipped。重复复跑不累计分母。unit/contract/security 是三个层，不把 contract 中重复业务维度伪装新生产路径；合成/官方schema fixture 从未计 live。没有性能、准确率、真实资产完整性或持续运行结论。

六类必要行为分别为正常格式/版本与完整 DTO、缺版本/未知配置/完整性、PURL/多版本/checksum/ref冲突、malformed/duplicate键/XML/超界、权限/跨tenant/路径输入、原bytes/hash/定位/确定性与来源变化。1MiB精确边界、200000节点、深16、组件10000/10001 均有观察断言。

## 未关闭的 10000 兼容 issue

`R11-SBOM-PROJECTION-NODES` 在 CR 有具体预期/实际。合法 CDX1.7 10000组件原文 **797858 bytes**，SHA256 `5a524d5fdc2e9bebef8fafbaa1870080ffb7be896b561da3c11d35a611ffed4d`；完整官方 schema 测试通过，再转换 package_name/version/ecosystem/purl 四字段时 **90005** 节点，冻结 public strict JSON/manifest parser 的50000预算拒绝，adapter typed `projection_node_limit`。最小10000 case通过且无截断，但不代表高密度10000已满足。原 bytes 在 synthetic-dense-10000.json.gz，准确hash/结果在 synthetic_input_receipt；主控另批修公共 parser 预算后复跑，不能降低10000上限或改金标/skip。

## 红日志、调用链与封存

test_first_red 是新模块尚未存在时的1 collection error，非业务反例。unit_first24与combined_first60通过。分层 attempt_1 unit30/回归225通过，contract/security各1 collection error：新测试引用 sibling module 依赖同时先收集 unit；只改新测试 import 为 `tests.unit.test_r11_sbom_parser`，未改被测合同/输入/原测试。attempt_2 为30+16+36及225通过；最后补冲突 issues 原位置后 attempt_3 为31+16+36及225通过。Ruff首轮仅新文件风格错误日志保留，随后自动format并最终检查通过。

初次 Windows urllib官方下载 SSL EOF、exit1，改为固定官方 URL 的 WSL curl，无证书绕过；初次工具异常输出未落独立日志，不能声称逐字节封存。初次 venv/安装、初次 CBM 未逐条捕获起止时间；最终测试/CBM/规范下载/wheel收据有真实时间，不补造旧时间。

材料工具曾因默认 GBK 读 UTF8 脚本、重复 attempt目录保护、直接脚本 import tests失败、CBM参数 path/未知 trace工具/`aspects=["all"]`误当单词而失败；未影响业务测试。已改显式UTF8/新目录/仅harness测试根路径/真实help flags。capture第一次的 CBM architecture 错误 log保留，最终 CBM参数为 `--aspects all`。这类早期探索工具输出有部分仅在会话，不宣称完整命令时刻已追回。

材料脚本Ruff首检exit1（导入/长行和subprocess capture_output建议），format后仍2项；仅修材料脚本等价风格，最终Ruff与format --check都exit0、4脚本通过；两份失败日志与最终日志保留，未回写已执行测试的输入/时刻/结果。

初始 assets索引198/825。最终独立 CBM_CACHE_DIR=/tmp/dianzi-r11-sbom-cbm-final，CBM_ALLOWED_ROOT只限本WT/backend/src 或 assets；使用真实CLI help/index/schema/architecture/trace，最终 src **1678 nodes/8774 edges**，assets **232/1022**；not_indexed/skipped/partial/unusable全部0，仅 __pycache__排除。原 parser入向2个为inventory.import_manifest与parse_sbom；新parse_sbom生产入向0。全部 src/test caller经rg交叉核对；完整命令/+08时间在 evidence_commands。初次 XDG变量只记录已设事实，最终明确使用CBM实际cache变量，不把别项目列表当本WT覆盖。

artifact_manifest 以每个gzip bytes/SHA256和解压原bytes/SHA256、JUnit实际结果及冻结Git源码proof封存。raw logs/XML/txt/JSON/scripts本地保留；Git只提交其gzip原bytes，避免Windows换行清洁误记证据hash。manifest本体显式LF，报告与CR不是私有上传原文；6个原SBOM输入全部 explicit_synthetic_offline。官方schemas/许可证和wheel只为原研究材料，不计真实资产输入或外部live。

最终manifest 111份gzip artifact、4个代码Git blob proof，manifest原bytes SHA256 `0f9b2733b562e93d1d0403b1ee8ab6c1347025888df77af0f43aaa218c9275ce`。原bytes还原与每个实际Git blob在材料冻结时再次核对，不以本地LF/CRLF视图代替证据原文。

## 八层状态与下一批

unit/contract/security：passed；integration/PG、frontend、e2e、live、manual：not_run。本纯适配未用PG端口/独立库，未接生产App或API。原 parser CSV探索37/1历史未关闭；旧CPU失败/全suite未运行，不由本报告消除。

T24-C01–C06 原验收保留：C01有格式投影/原JSON与SPDX/CDX候选兼容证据，但JSON/CSV库存事务是此前独立切片；C02/C03本轮只有摘要/版本输入变化，PG幂等/历史不是此函数已接结果；C04直接证明unknown不排除；C05证明有界拒绝无候选部分成功；C06证明候选读取scope/租户/bytes边界，HTTP写权限仍由既有router与root后续接线核验。T24扩展步骤6获得有限版本纯适配函数，不能签全SBOM/API原协议或完整R11。

最小下一批为root统一固定依赖锁、明确格式dispatcher/route接受字段、combined/sidecar的PG保存及版本判等、修高密度10000公共结构预算，再跑真实库存事务/重放/并发/回滚和API权限。0018/0019迁移由唯一集成人处理；analyst写权限与05 imports202仍沿用原冲突记录，不在本切片grant/改验收。新reviewer应针对冻结code+material SHA重新运行，作者等待审查。

未检查：全规范语义/全部版本、生产dispatcher/PG/frontend/e2e/live/manual、全suite与旧失败；风险：缺统一依赖锁不能导入，projection-only判等会吞sidecar历史，合法高密度10000仍typed拒绝。
