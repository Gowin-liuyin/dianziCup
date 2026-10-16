# CR-R18 · 后台任务身份引用与锁后过期

文档首次创建时间：2026-10-16T12:25:25+08:00
本次写作开始时间：2026-10-16T12:25:25+08:00
状态：approved_for_implementation；独立审查待执行。

落实已批准认证/后台恢复边界：任务、检查点、模型与工具台账不保存raw session/API token。复用现有auth_sessions/api_keys/users/job_runs；没有实际新事实就不建表，原0028 Actor表预留撤销。R14应用两表迁移改用0028；0027仍R15。不得创建空迁移或另一身份真相。

唯一指定集成人 /root/r18_async_actor_reference_seam_implementation 修改api/auth_state.py的lock_authenticated_scope及必要类型import，新增api/actor_references.py与直接测试。旧str仍仅cookie；新增明确内部ActorReference分支，不将APIkey解释为cookie、不接HTTP/body参考。create_actor_reference由服务端在同事务已认证SessionCredential/ApiKeyCredential构建，严格记录credential kind、owner/tenant/role、frozen effective permissions、既有permission version或明确derived digest、resource、credential/server issuance，以及session_hash或key_id/version；无rawtoken/SecretStr序列化。内部可信PG decoder与公开请求schema分开，reference是locator/context，不能单独作为bearer capability。

后台每次锁住credential+users后重验owner/tenant/role、当前权限、resource、issuance、版本、expiry/revoked；锁等待用可信aware server now加真实monotonic elapsed再验，不用请求时间/全局monkeypatch。角色和tenant变化包括升权均fail closed；权限取冻结与当前交集，不扩大。同步修复旧cookie在等待锁后可过期的同根因，原红/微秒边界记录保留。

锁顺序credential+users→job/workflow owner→业务资源，与现有enqueue一致，不反序等待。job_runs只有tenant没有owner，单tenant不足；R14 owner必须来自同事务锁住的investigation_workflows；R15来自subscription/generation复合owner。不能信任body或调用者自报owner。实际绑定服务同PG锁查job_id/tenant并与受信owner记录核对，public接口不暴露reference构造或解析。

兼容：旧cookie函数名/str参数路径及旧服务语义保留，全部直接调用与两跳类型消费者需核查（冻结312958业务src有16次直接调用/11文件；CBM两跳35包括file/heuristic，不能称直接35），不自行批量扩大constructor；APIkey管理、公用路由及worker挂载另root集成，不以内部模块宣称接通。迁移无需新增身份表；回滚关闭新reference入口保留既有事实，不存回raw凭据。测试覆盖两个租户/用户、引用伪造、jobowner不同、锁后expiry/撤销/角色变化、权限交集、key版本/resource、重启恢复与秘密不序列化。unit/contract、安全/真实PG分别记录；frontend/e2e/live未跑写not_run。

本次写作结束时间：2026-10-16T12:28:28+08:00
最后更新时间：2026-10-16T13:13:42+08:00

修订记录：2026-10-16T13:13:42+08:00，依据独立src/AST/图核对纠正直接调用计数口径；worker旧锁序接线仍待短事务执行端口。
