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

## 独立审查privacy修复补充（主控批准）

独立审查真实PG18自有探针15通过、3失败证明：SPDX spdxDocument的数据库连接URI、file URI、HTTPS userinfo URI原样出sidecarGET，违反上文不返回内部路径/连接串合同。新最小pure红3例同样复现，不修改已审pure parser/原输入/原review探针。修复是安全展示投影；不是拒绝或删掉原声明以改事实。

新sidecar公开响应统一schema `r11-sbom-sidecar-2`，document_uri为str或None；新增typed redactions，每项source_field_locator、固定reason=unsafe_uri_or_path、replacement_ref为None或精确redacted-ref:64hex。内部校验接受历史schema1（redactions缺失按空），先核scope/adapter/spec/raw/projection/sidecar/combined绑定，再投影；不更新旧payload，不取原raw重新解析。新schema2只信完整typed载荷中确切位置、固定reason与实际alias同时匹配的标记；重复/多余/伪标记或未处理危险值返回503，不单凭保留前缀信任。

URI仅离线判断，无DNS/HTTP：优先无credential、无query/fragment的HTTP(S)，authority百分号/反斜杠/控制、明确localhost/internal host及非global IP均不展示；路径编码中的URI/控制也不展示。必要UUID/CDX规范URN及安全opaque引用可保留。其他URI/path被标明展示限制。CDX组件ref、edge两端、composition三组引用统一sha256 opaque alias，同原值保拓扑。客户端原值恰为生成前缀也按原值再次hash，不与真实危险引用生成的alias合并；schema2再次投影仅通过严格服务器标记保持幂等。原id/checksum仍保留，声明完整性仍unknown。

进一步实际probe确认PURL的编码version可携credential URI（qualifier/subpath原profile仍拒绝）；因此主控批准仅SBOM source_kind的公共snapshot purl只读隐藏为已有nullable None，覆盖POST新导入、幂等重放、指定/current/asset-list/history读取。私有canonical候选、component identity、raw/hash不变，JSON/CSV及旧DTO字段不变。sidecar从同次冻结snapshot payload标出该purl源位置，不读取raw或重跑parser。URI/path样式的未知JSONPointer键同样使用稳定安全locator占位；普通业务name/display或自由文字不使用万能secret黑名单。

迁移：无表/DDL或批量回填；兼容schema1和schema2私有payload读取。新声明及旧原文均保持不可变；raw/fullJSON/combined/projection摘要不因展示限制改变。回滚须保留此安全view或停用SBOM/sidecar展示，不能重新上线会透传旧私有URI的旧读取。验证增加原3URI、编码PURL、URI键、private IP/query、schema1历史、schema2幂等、碰撞、伪metadata、analyst/ACL、raw/hash/replay/history和日志否定；保留原411分母和新独立审查，不改评分/阈值。生产0022、正式app、SBOM frontend/browser/live/manual仍独立待验。

## 同批定向复核的编码与重复定位遗漏（主控批准）

原reviewer在742冻结版本发现3个真实新失败：未知字段键的URI经过5层或8层percent编码后，四轮解码残余编码被误当普通定位符公开；schema2两条edge共享同一source定位，首条匹配alias已使用标记后，第二条改成安全外观的不同值仍200。b4已有None URI必须有精确标记的校验保留。作者先记录这3条最小unit红及新9条PG中的7红/2绿，再修展示层，不改原探针/已审parser或来源语义。

解码仍最多四轮，每轮验证percent escape完整语法并用标准库严格UTF-8；非法编码或四轮后仍有percent编码一律不可展示，不无限解码、不只增加轮数。未知键占位hash使用JSONPointer反转义后的原字段字节，不以不同编码最终解出的相同URI合并位置。控制码/歧义编码同样给固定typed定位占位；普通合法Unicode键与业务名称保留。历史schema1通过同边界，已冻结schema2精确旧marker保持二次投影幂等，原raw/fullJSON/combined/projection摘要均不变。

每次公开引用遇到typed replacement定位时都要求实际值与固定reason、完整alias精确匹配，先拒绝错值再作安全URI判断；同一原定位的每次引用值也须一致。合法重复同值保持可读和原拓扑，错值固定503，不由“此marker曾使用一次”免检。

无新DTO字段、数据库迁移或回填；旧JSON/CSV不变。回滚仍须保留安全view或停用SBOM展示，不能恢复泄漏。新独立26条unit与9条真实PG覆盖四轮边界、5/8/12/64层、非法/截断percent、非法UTF-8/代理码/控制、合法Unicode、原键占位碰撞、schema1/2重复同值与错值；原411、前一轮33/22与原独审探针分别保留分母，不累加重复通过数。精确起止、红绿及未运行项见修复报告。
