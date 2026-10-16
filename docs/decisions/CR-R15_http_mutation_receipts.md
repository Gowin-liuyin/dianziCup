# CR-R15 · HTTP 写入收据与既有服务的同事务端口

文档首次创建时间：2026-10-16T14:57:02+08:00
本次写作开始时间：2026-10-16T14:57:02+08:00
状态：approved_for_implementation；属于已授权R15/R17/T39/05幂等要求的必要接线，非整卡验收。

问题：已冻结持久服务5e2d3cbc每次create_subscription生成新UUID；POST generate使用服务器当前截止时刻。前端按原05发送Idempotency-Key，但没有PG请求收据时网络重放可生成多个订阅/生成结果。不能以当前四表内部去重代替HTTP幂等。

新增明确的recommendation_mutation_receipts表，迁移编号0029由root唯一管理，0027四表/触发器不改。收据按当前认证tenant/user、固定操作、服务器目标定位符、幂等key SHA256唯一；输入canonical SHA256、响应严格JSON及其SHA、创建时间只来自服务器，不保存raw key/token/外部凭据。key按现有05长度边界严格校验；同key/同输入重放不产生第二效果，同key/异输入409。POST要求key，PATCH既有version CAS继续保留且可同样支持key，不能重放旧CAS绕过新权限。

批准最小同事务端口：仅在请求内部把现有RecommendationService的业务写入与receipt共用同一个显式SQLAlchemy Session/transaction；普通既有调用仍自行管理短事务。可以抽取职责明确的内部transaction helper或具体写入函数，不能复制整服务、嵌套commit、建万能repository。服务器wrapper锁当前身份/owner后用PG唯一插入冲突等待与收据围栏，所有效果+完成receipt原子提交；失败回滚两者。已完成收据不可覆盖/删除；若采用reserved占位只能同事务完成，不提交空成功，独立review检查并发/fault。

重放先重新验证当前身份、本人subscription、来源与asset权限及当前历史可读性，不直接返回已撤销的缓存证据。current overlay按现有service读取，不用原HTTP响应替代当前授权；保持不可变历史输入、材料hash、截止和首次写入结果locator。schema响应字段、路径、分页、错误码与CR-R15_public_workbench_contract不变；输入仍不收owner/tenant/PreparedGeneration。只新增新API/router/internalreceipt与直属tests，root负责App挂载/0029/全局锁与状态。

兼容：新增router/v1与alias/api/v1，cookie Origin/CSRF/READ_PUBLIC+asset额外权限不削减。旧四表和service直接调用不变；只服务器可信Session可注入，无请求体/SDK字段。回滚关闭新router保留历史和收据，禁止自动downgrade。原05金标、评分分母、阈值和live原则无变化。

测试影响：严格payload/schema/duplicate keys/未知字段/true-as-int/权限；同key同输入/异输入、两owner同key隔离、并发只一效果、失效CSRF/凭据/撤权、insert后崩溃两者rollback、replay current overlay、订阅停用历史、报告原文和hash；真实0027→0029升级/原表sentinel/PG/API/浏览器由各层实际运行记录，fixture不计live。全部业务新源码须新非作者初审，root登记前不accepted。

本次写作结束时间：2026-10-16T14:57:02+08:00
最后更新时间：2026-10-16T14:57:02+08:00
