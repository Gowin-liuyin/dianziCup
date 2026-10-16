# CR-R18 · 默认公开问答生产入口

文档首次创建时间：2026-10-17T06:47:22.315+08:00
状态：approved_for_implementation；仅实现授权，独立审查和实际PG后才签切片。

依据已批准R18/CR-R09、公开v2及凭据预约变更，新增api/public_ask_routes.py的build_public_ask_router(service_provider,engine,settings)，复用build_question_service、parse_public_ask_request和GroundedQuestionService.ask。Root唯一负责App挂载和CORS Authorization，作者不改公共schema/迁移/认证模型/现服务。

同一当前credential解析支持cookie/Bearer，禁止重复/query/混合凭据；cookie写入保留原Origin+CSRF验证，Bearer不借cookie身份。短PG事务锁当前真实身份并create_actor_reference，后续scope_provider每次真实重验同凭据；ask传actor reference及原credential，沿已冻结服务的新预约/ask bucket原子性、锁后DBclock、重放免扣与最终围栏。模型IO不能跨route持有的锁事务，不保存raw token。

默认POST /ask保留公开JSON/1MiB/UUID/timestamp边界；缺幂等或畸形请求明确422、权限/撤销/限流与当前模型或DB缺失分类，错误不回显敏感内容。回答200必须真实shared service已出版结果，不能模板或把202当完成。调查/multiasset/multiturn/historical异步typed任务仍在Root后续范围，不解除当前服务限制伪成功。旧/questions继续兼容。过期answer对外稳定answer_failed，内部lease原因保留，错误码统一由Root现route修复和此新route映射。

新route须无配置失败、真实factory/cookie/Bearer、CSRF/重复header/幂等/ask额度重放/两owner/revocation/过期/current evidence/JSON引用输出测试。fixture只unit/contract，实际PG由Rootnonce窗；无新依赖。回滚卸载新route，历史答案/预约/APIkeys不删除。作者仅新增route直属tests和任务证据，不改Rootstate/App/合同/评分；独立新reviewer检查完整真实调用链。
