# CR-R11 · 私有资产持久化与独立HTTP入口

提案时间：2026-10-16，状态：主控批准有界实现，0018生产迁移由主控冻结。本切片实现完成最多 awaiting_review，不能签整R11/T24。

授权范围为新资产专用models/service/contracts/router和直接测试。不改public schema、角色权限、现有parser、应用接线、富化模块、迁移、锁文件或progress。

## 表与一致性

SQLAlchemy metadata 提案在 `backend/src/ai_intel/assets/inventory_models.py`，复用现有knowledge metadata，但测试仅显式create这三个新表。基底真实前向升级到0016；不将create_tables算为生产迁移成功。

| 表 | 列/键与约束 |
|---|---|
| assets | asset_id TEXT PK；tenant_id/display_name TEXT非空且长度有界；criticality默认unknown、active默认true；current_snapshot_id；created_at/updated_at timestamptz；unique(asset_id,tenant_id)；tenant/created_at/asset_id分页索引 |
| asset_snapshots | snapshot_id TEXT PK；asset_id/tenant_id；snapshot_number正整数，unique(asset_id,tenant_id,snapshot_number)；previous_snapshot_id；manifest_sha256/raw_input_sha256固定64hex；schema_version/parser_version/source_kind/source_version；完整canonical_payload JSONB对象；私有raw_input BYTEA 1..1048576；observed_at/recorded_at；actor_user_id FK users，无cascade；unique(asset_id,tenant_id,snapshot_id)；tenant/asset/number倒序索引 |
| asset_import_receipts | 联合PK(tenant_id,actor_user_id,request_route,idempotency_key)；actor FK users无cascade；route固定asset-imports/asset-snapshots；request_sha256；asset_id/snapshot_id；created_at；联合FK(asset_id,tenant_id,snapshot_id)确保跨租户引用失败 |

snapshot→asset、previous→snapshot、asset current→snapshot均为包含asset/tenant的联合FK。current FK deferrable initially deferred；事务内创建asset再创建snapshot最后设current。延迟constraint trigger要求成功commit时current非空。snapshot BEFORE UPDATE OR DELETE触发器拒绝历史修改。

全历史不按manifest hash唯一：A→B→A追加新版本，保留前驱。重复当前canonicalhash复用当前snapshot，写请求receipt但无change/epoch/job/outbox变化。请求同key同正文/参数返回原snapshot；即使已产生更新版本，重放不恢复旧current。不同正文或任一影响结果参数409。

锁序为事务内认证会话/用户共享锁→tenant请求advisory→asset advisory→assets FOR UPDATE→knowledge-publication advisory/scope epoch。所有事实、current、receipt、既有change_events/job_runs/outbox_events/publication_receipts同Session事务提交；复用save_change_publication，不进行外部IO或内部commit。

## 方法合同与HTTP边界

`InventoryService(session, scope).import_manifest(raw_bytes, *, manifest_format, display_name, source_version, observed_at, idempotency_key, asset_id=None, csv_column_mapping=None, request_route='asset-imports') -> AssetImportResponse`

`read_asset(asset_id)`、`get_snapshot(asset_id,snapshot_id)`、`list_assets(limit=20,cursor=None,product='')`、`list_snapshots(asset_id,limit=20,cursor=None)`只读私有租户范围。

`build_inventory_router(service_provider,engine)`可在隔离FastAPI直挂：POST asset-snapshots JSON；POST asset-imports受控二进制JSON/CSV上传；GET assets、asset current、history和指定snapshot。工厂复用AuthenticationSessionService的CSRF/Origin与lock_authenticated_scope，不接受body tenant/role/server file path。写必须WRITE_ASSET与非空tenant，读必须READ_ASSET与非空tenant；无权限先403，不可见和不存在统一404。POST idempotency-key必需。大小1MiB；解析器实际上限10MiB/10000组件，当前切片不替换解析算法。

03 AssetSnapshot字段完整映射到独立AssetSnapshotResponse（含组件生态/版本/摘要、字段定位、完整性/声明范围及未知配置）。配置缺失与None保持unknown；不把缺组件当否定。公开`contracts/schemas/public_api_v2.json`当前没有AssetSnapshot定义，只有Component/StackCheck等对象；独立DTO不冒称既有public v2 AssetSnapshot已满足。Component可无损选择component_id/ecosystem/package_name/version/purl五公开字段，其余完整字段保留在私有DTO与PG。

05旧REST表写analyst；真实ROLE_PERMISSIONS analyst只有READ_ASSET。此次按WRITE_ASSET拒绝analyst，权限兼容决策留主控，不静默grant。POST imports当前同步解析返回201，05旧表异步202属于未完成接线/任务协议，不声称原API完全满足。

## 私有原文与剩余范围

raw_input与raw hash由服务端计算，仅入私有PG，GET不返回raw、内部存储路径或连接信息，不默认提供原文件下载。测试原文均显式synthetic fixture；报告仅记录长度/hash/断言，不存实际私有清单。parser按既有合同拒绝未支持字段名，保留其已支持未知值及原bytes；不为了保留额外秘密字段改parser。

原parser探索38例37通过/1 CSV引号方言失败保持原历史。CycloneDX/SPDX adapter、生产0018迁移/API app接线、前端/e2e/live/manual、真实资产完整性核验和3→5产品真值均未由本切片完成。原T24 C01–C06全部保留，不更改金标/阈值/分母。
