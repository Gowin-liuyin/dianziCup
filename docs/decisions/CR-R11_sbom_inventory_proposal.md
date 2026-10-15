# CR-R11 · SBOM库存接线与合法10000组件容量

日期：2026-10-16；主控有界批准；实现者最多 `awaiting_review`，不修改 progress，不 push，不自签 accepted。

## 冻结边界

复用 `parse_sbom` 的 CycloneDX JSON 1.5/1.6/1.7、SPDX JSON wire SPDX-2.3 profile，显式 `manifest_format=cyclonedx_json/spdx_json`；JSON/CSV 两格式与旧快照、列表、导入响应字段保持兼容。HTTP二进制原文仍1..1048576字节，认证租户、WRITE_ASSET、Origin/CSRF、幂等键与同事务发布沿用现有入口。无文件路径、任意URL、外部文档抓取、模型、付费调用或PoC执行。

## 容量修复

共享模型 `strict_json_object` 的最大50000节点保持不变。它不允许传入更大参数，因此在 `manifest_parser._json_rows` 使用标准库 `json.loads(object_pairs_hook, parse_constant)` 加局部有界遍历，保留重复键、非有限数、溢出float、UTF-8、非法代理码、NUL、深度16与10000组件检查。解析器本来10MiB的内存输入边界不变；库存入口及SBOM原文仍1MiB。

数学预算包含对象键和值，不仅数组件。顶层有8个允许字段，根+键值容器为 `1+2×8=17`；每组件最多8字段以及64个dependency_path项，`1+2×8+64=81`；declared_scope/tool_permissions各64个项共128；configuration/input_channels/network_exposure最多4/3/2字段共18个键值节点。总上界为 `17+10000×81+128+18=810163`。有效库存对象均在此上界以内；SBOM自身原JSON节点200000与深度16仍不变。其投影自动通过既有 `MAX_JSON_NODES` 引用取得新预算，无需修改已审 `sbom_parser`。非法未知字段不会因此获得业务支持。

原合法dense10000未通过是 typed `projection_node_limit` 能力缺口。主控批准仅把原两个旧缺口证明测试改为完整10000成功断言，原组件内容、固定官方schema与fixture字节不变；保留旧日志及首红。新增两字段、多字段、SPDX容量和严格非法边界断言，不降低组件数量、删除难例、修改金标或改变评分分母。

## 历史与判等

新独立 `asset_snapshot_sbom_sidecars` 表由主控冻结DDL，不改既有 ASSET_TABLES。字段：snapshot_id主键，asset_id/tenant_id，adapter_version，spec_version，sidecar_sha256，combined_semantic_sha256，canonical_payload JSONB。三列外键 `(asset_id,tenant_id,snapshot_id)` 指向既有快照同租户唯一约束；hash/租户/版本长度检查；UPDATE/DELETE不可变。唯一原文仍存既有 `asset_snapshots.raw_input` BYTEA，其大小/hash与原始上传一致。

canonical_payload保存本次已解析typed component sources、checksum、ref、dependency edges、composition declarations、external document及未映射字段定位，附快照认证身份、格式/版本和原文/投影/全JSON/组合摘要。不保存第二份raw，也不把opaque值写入响应。历史GET直接读取已冻结payload，不以新parser重解析旧原文。opaque字段的准确原值由不可变raw和全JSON结构摘要保留。

同current复用比较：SBOM用 `combined_semantic_sha256`；旧JSON/CSV用原投影hash。跨格式产生新快照。graph/checksum/composition/opaque变化即使投影相同也产生新编号、历史/current与change/epoch/outbox；空格和对象键顺序等combined相同变化可复用。幂等请求仍包含精确raw hash，原请求重放返回原快照且不能恢复旧current。A→B→A产生3个历史快照。

旧 `AssetSnapshotResponse.snapshot_sha256` 和数据库 `manifest_sha256` 保持投影语义。outbox旧 `manifest_sha256` 也保持投影语义；仅SBOM新增 `combined_semantic_sha256` 和 `sidecar_sha256`，供消费者区分完整来源变化。普通包checksum不转为image_digest，图不转为dependency_path，composition complete不转为安装范围完整。

## 私有读取与兼容

新增独立 `GET /assets/{asset_id}/snapshots/{snapshot_id}/sbom`，READ_ASSET、非空认证tenant、同事务当前scope核查；不可见/不存在/非SBOM统一404。返回专用typed DTO，不向旧snapshot DTO加extra。原文、内部路径、连接串、opaque值均不返回。规范内external URI仅惰性声明，不执行。DTO身份来自服务器候选，输入不能自报租户。

旧GET/POST/分页/role行为不扩大权限。现有analyst无WRITE_ASSET仍拒绝；原05异步202与当前同步201差异保持明确，未借此次改成新任务协议。API app装配与0022生产迁移归主控独占。

## 迁移、回滚与验证影响

生产迁移0022由主控编写；本切片真实PG测试使用专用测试库前向0019，再准确声明独立sidecar表测试创建，不能将其当生产迁移证据。既有PG回归若fixture只允许0018，另建专用前向0018测试库并保留原fixture约束。

回滚入口必须先停用新格式及sidecar读取，连同dispatcher/DTO/服务/本容量修复回退；保留SBOM历史和原文，禁止删表、原文或修改current。已存在SBOM快照不能在旧版本上以投影hash进行新导入判等；回滚后需保持新格式写禁用，或重新上线这次冻结实现。依赖packageurl-python0.17.6已有主控锁，不新增依赖。

unit/contract/realPG/security/frontend/e2e按实际运行记录；纯synthetic测试不计产品live。整个R11/T24/T28、真实资产完整性人工核验、真实SBOM产品live、研判/规则/OpenVEX与最终评分不由本切片完成。所有通过数量、未运行和外部阻塞以最终报告及run原日志为准。
