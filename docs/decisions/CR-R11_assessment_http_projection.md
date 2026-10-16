# CR-R11 · 资产固定快照自查HTTP与工作台接入

文档首次创建时间：2026-10-16T20:02:55+08:00
本次写作开始时间：2026-10-16T20:02:55+08:00
状态：approved_for_implementation；在当前R11/R17有界完整授权内，awaiting新非作者验收。

输入：POST /v1/assessments（兼容挂载/api/v1），严格JSON最大4096bytes、重复键拒绝、extra forbid；asset_id/asset_snapshot_id UUID、rule_id复用现Label(1..200，不传任意SQL/URL)、rule_version strict int 1..2147483647。身份仅Cookie当前会话，不接tenant/user/role/permissions/cutoff/prepared。POST是写评估结果，须原Origin/CSRF及READ_ASSET，不新增WRITE_ASSET授予。服务调用现AssessmentService(engine, session_token|ActorReference, ContentStorage).prepare(asset_id,snapshot_id,rule_id,rule_version)→commit；其两事务中重新鉴权/当前来源/规则/资产快照与原CAS证明必须保留，规则未published/失效/冲突/缺证据均沿原四态，不在HTTP重算真值。

输出：新AssessmentResponse(schema_version=r11-assessment-http-1)，仅投影原AssessmentReceipt除prepared的字段：assessment_id,tenant_id,asset_id,asset_snapshot_id,event_id,rule_id,rule_version,knowledge_epoch,scope_epoch_map,rule_result,status,freshness,missing_requirements,conflicts,limitations,exposure_result,exploit_evidence_status,input_digest,created_at,reused。复用既有类型/enums；不回内部prepared整个资产/原文输入/actor/receipt目录，不暴露credential。GET /v1/assessments/{UUID}复用service.read重新鉴权+来源可见性；历史原结果不可覆盖，不把历史status叫当前安全。两路由Cache-Control:no-store/原problem_response固定错误，不回异常原值；未配置PG/存储503而非fixture成功；越租户/不可见资源uniform404，角色不足403，原证据完整性失效以既有明确error/partial语义处理，未知不得safe。

原幂等复用tenant/snapshot/rule/inputdigest/policy唯一键，重复HTTP不新增另套真值；无需新Idempotency-Key或任务表。同步单固定快照/单规则，避免发起未经范围授权的FOFA/任何外部扫描/模型。该切片未包括规则自动生成/九维全量、推荐撤回、所有资产批评估或正式live验收。兼容性/迁移：新增路由/DTO，无表、索引、依赖、原权限/公有DTO破坏；原AssessmentReceipt内部调用不改。回滚仅撤路由与UI入口，保留append-only结果/历史，不downgrade或删facts。原R11/T28及R17/T40等全部后续slice验收保持，评分/金标/分母不动。

所有权：Root App/settings/公共合同，backend唯一Agent仅assessment/http_contracts.py、assessment/http_routes.py和直属新tests；frontend唯一Agent仅new features/assessments组件/contracts/client/tests，旧WorkspaceApp接线由Root。界面复用当前黑客风tokens/既有组件和动态背景，表单真实API；明确四态/历史/unknown/加载/空/无权限/部分失败/旧快照、可打开正确event原文证据；不能前端mock成功或自算判定。

六层验收：schema正常/缺项/额外身份/重复key/oversize；真实认证PG prepare→commit→GET跨请求/重实例、来源撤销与tenant隔离、CSRF、同input幂等、四态与history；新非作者源码/CBMcaller与亲复PG关键负例，Root挂默认create_application后再独立API/browser e2e。单位fixtures只显式unit/contract，live/manual未跑保持not_run，不调用付费API。作者awaiting_review不push/accepted；后续新独审核合同才放行。

本次写作结束/最后更新时间：2026-10-16T20:02:55+08:00；修订人/root。
