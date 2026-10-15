# CR-R11 · 有界 SBOM 纯适配与完整来源摘要

提案日期：2026-10-16；范围由主控有界批准，交付状态最多 `awaiting_review`。本切片不签完整 R11/T24。

仅新增 `backend/src/ai_intel/assets/sbom_parser.py`、直接 unit/contract/security 测试和本 CR/报告/运行材料。不修改冻结 parser37、库存持久化/路由/DTO、公共 schema、auth、迁移、App、依赖锁或 progress。主控另批统一 dependency lock、生产 dispatcher 与 route。

## 输入输出与版本

`parse_sbom(raw_bytes: bytes, *, sbom_format: str, scope: AccessScope, authorized_asset_tenant_id: str, asset_id: str, snapshot_number: int, source_version: str, observed_at: datetime, recorded_at: datetime) -> SbomParseResult`

输入为实际 bytes，不接受路径/URL/XML。服务端作用域必须有 READ_ASSET 与非空租户，并与授权资产租户一致；此函数仅产生候选，不授予写权限。observed_at/recorded_at 必须由调用方提供带偏移的真实时间，沿用既有 parser 校验；不以本机 now 或 SBOM creationInfo 自动补观察时间。

| 格式 | 支持版本 | 官方材料与边界 |
|---|---|---|
| cyclonedx_json | specVersion 1.5、1.6、1.7 | 各版本官方 JSON schema 独立验证合成 fixture；1.5 只有 dependsOn，1.6/1.7 另有 provides；1.7 的 isExternal=true/versionRange 无现有库存模型语义，typed unsupported |
| spdx_json | wire spdxVersion SPDX-2.3 | 官方 v2.3.1 维护 schema/规范；不是 wire SPDX-2.3.1，不支持 SPDX 3、tag/value、RDF 或 XML |

资料取自 [CycloneDX 官方规范](https://cyclonedx.org/specification/overview/)、[1.7 JSON 文档](https://cyclonedx.org/docs/1.7/json/)、[SPDX 包规范](https://spdx.github.io/spdx-spec/v2.3.1/package-information/)、[SPDX 文档规范](https://spdx.github.io/spdx-spec/v2.3.1/document-creation-information/)。固定 schema 原 bytes/hash/URL/下载时间在本 run 的官方材料收据与 gzip 中。它们是分析材料，不提供项目执行权限。

## 投影与 sidecar

返回既有 ManifestParseResult/SnapshotCandidate/ComponentCandidate；不新造公共资产模型。字段映射如下：

| 来源字段 | 既有组件或额外结果 |
|---|---|
| CDX name/version/purl；SPDX name/versionInfo/外部 purl referenceLocator | 包身份、直接版本、成熟 PURL 解析后生态与名称；实际源字段 JSON Pointer；原 name 与 PURL 名称不同则保留 display_name |
| 缺直接 version/versionInfo | version=None；即使 PURL 含版本也不伪造直接版本声明 |
| 无 PURL | ecosystem/version_scheme=unknown，不从名字猜生态 |
| 有 PURL | pypi→PyPI/pep440、npm→npm/semver；其他类型保留生态，比较方案 unknown；两个实际版本声明不一致时拒绝，已有生态比较器等价时保留原文本 |
| 嵌套 components、metadata.component | 仅实际 component 对象展平；assembly 不伪造 dependency_path，不制造资产或影响结论 |
| checksums/hashes、bom-ref/SPDXID、dependency relationships、externalDocumentRefs | typed 原声明 sidecar，准确位置；普通包 checksum 不伪装容器 image_digest；外部引用不抓取、不扩为拥有组件 |
| composition aggregate/引用范围 | typed 原声明；即使 complete 仍 inventory_completeness=unknown、declared_scope=空，待授权范围和覆盖真实性核验 |
| 工具权限、输入渠道、配置、网络暴露 | 沿用 unknown/None/空声明，不从工具名、许可证或注释推断配置或安全性 |
| 许可证、注释及其他字段 | 原 bytes、全 JSON 结构摘要及未映射位置保留，不声称语义分析；许可证不是漏洞否定证据 |

`component_sources` 保留包 refs/type/逐字段定位/checksum；`dependency_edges`、`completeness_declarations`、`external_documents` 分离原声明。现有 parser 的冲突版本 issues 也转换为原位置，不静默丢弃多版本。

`manifest.snapshot.snapshot_sha256` 仍是既有库存投影 hash。`raw_sha256` 为精确上传 bytes。`sidecar_sha256` 为完整已解析 JSON（排序对象键、保留数组顺序）的保守结构摘要，包含标准/非合同字段而不声称解析其业务语义。`combined_semantic_sha256` 是 [adapter_version, projection_hash, sidecar_hash] 的摘要。空格/对象键顺序变化复用语义摘要，graph/checksum/composition/license/注释变化不能只靠投影 hash 被吞掉。数组顺序、SBOM revision/时间等来源结构变化也会保守地产生新 combined hash；这不是全规范语义等价归并器。

未来 dispatcher 必须在同事务中比较 combined hash、持久化 sidecar 与原 bytes，再分配新 snapshot_number；当前返回的 snapshot_id 仍由投影 hash+调用方编号构成，不能直接宣称 sidecar 变化已产生库存历史或重新研判。本切片无生产 caller。

## 边界与兼容 issue

raw JSON 大小 1..1MiB、深度16、节点200000、组件10000。严格重复键、NaN/Infinity/溢出浮点数、非法代理码/NUL、XML/entities、$ref/$dynamicRef 拒绝；无外部解析/文件/网络执行能力。遍历预算与组件展平使用显式栈。包名沿用冻结模型的安全 ASCII 标识约束；PURL qualifiers/subpath、超模型标签、非 required scope、external/range component 均 typed unsupported，不静默转换 installed。

适配器是受限库存投影校验器，**不是全规范 validator**。生产不调用 JSON Schema validator；离线测试才用官方 schema。其他标准字段仅原文保留，不能由接受输入推出整个 BOM 规范有效或完整。仅索引主要 component、根 services、SPDX packages/files/snippets IDs；工具/pedigree/嵌套 services/其他全局 bom-ref 依赖目标超此 profile 会 unresolved/unsupported，需独立兼容扩展。

具体 issue `R11-SBOM-PROJECTION-NODES`：10000 个合法 CDX 1.7 library，各含 type/name/purl/version，raw <1MiB、组件数10000、官方 schema 验证成功。映射为 package_name/version/ecosystem/purl 四实际字段后有90005个结构节点，冻结公用 JSON helper/manifest parser 只允许50000。预期完整10000组件候选，实际 typed `projection_node_limit`；不得把最小10000成功当全10000验收，不降组件上限/不截断/不改原37。主控另批调整公共结构预算后复测。

## 依赖与隐私

主控批准 [packageurl-python==0.17.6](https://pypi.org/project/packageurl-python/0.17.6/)，MIT，官方 wheel 发布 SHA256 `31a85c2717bc41dd818f3c62908685ff9eebcb68588213745b14a6ee9e7df7c9`。仅本 WT venv 安装；只调用 PackageURL.from_string/validate，不启 URL 转换网络功能。不改共享 pyproject/lock；**合并/运行前必须由主控把固定版本加入统一锁**，否则新模块导入依赖缺失。

新隐私范围为完整 SBOM 原文及 opaque 字段，可能包含内部命名/私有下载地址/注释。仅候选内存与后续授权私有 PG 范围；无默认原文下载/日志/UI 展示。已知顶层 identity/role/path/secret 字段拒绝，普通合法文档 URI 只作惰性声明不执行。该边界不是任意嵌套 opaque 数据的秘密扫描器，dispatcher/API 必须保持私有 bytes 和 sidecar 授权，禁止把完整返回结构直接透传公共 DTO。

## 接线提案与未完成

最小后续接线是 root dispatcher 显式增加两个格式分支、复用相同服务器认证/WRITE_ASSET/CSRF/Origin/幂等事务流程，把结果 sidecar/combined hash 纳入历史与 change_event 判等；私有安全 DTO 继续不回 raw。不可只调用函数后以投影 hash 判同 current，也不可让 READ_ASSET 代替写权限。本文是提案，不是已接线证明。

本切片 unit/contract/security 与既有相关回归可验证；PG integration、frontend/e2e/live/manual 均 not_run。05 原异步 imports202、analyst 写权限冲突、迁移集成、全 R11/T24 其他流程仍归主控。状态与测试数量以最终报告/原收据为准，不修改 progress，不 accepted/push。
