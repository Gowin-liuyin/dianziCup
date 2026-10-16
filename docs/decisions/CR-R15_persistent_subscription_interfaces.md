# CR-R15 · 订阅、推荐与报告持久化接口

文档首次创建时间：2026-10-16T12:25:25+08:00
本次写作开始时间：2026-10-16T12:25:25+08:00
状态：approved_for_implementation；内部服务本批实现，公开适配与独立验收待执行。

依据数据合同3.11及R15/T39/T43，不修改原验收。冻结内部四模块 recommendations/service.py、persistence_models.py、service_contracts.py、candidate_loader.py；复用已独立审查的纯规则、AssessmentService、KnowledgeReadService、EvidenceGraphReadService 和 ContentStorage。现有合同没有定义公共 SubscriptionSpec/ReportJob JSON schema；不得编造“既有schema”。先实现内部DTO，主控另作带版本公开扩展。公共 minimum_priority 将显式映射内部 maximum_priority_bucket（0最高、3最低），不能反转过滤意义。

迁移0027仅主控写。四表：r15_subscriptions 保存 id、tenant、user、version、enabled、spec JSON/hash、创建/更新时间，UNIQUE(id,tenant,user)，owner/created不可变，编辑CAS version；r15_generations 保存订阅/owner复合FK、subversion、cutoff、input hash、policy version、scope epochs、result JSON/hash、created，幂等 UNIQUE(sub,subversion,input hash,policy version)，追加不可变；r15_recommendations 保存订阅/owner复合FK、generation、event、material_version、payload/hash、created、read_at及当前状态/理由/检查时刻，UNIQUE(sub,event,material_version)，仅read/current overlay可变；r15_reports 保存订阅/owner、generation、day/week、cutoff/generated、payload/hash及current overlay，UNIQUE(generation,frequency,cutoff)，历史payload不可变。generation另有UNIQUE(id,subscription_id,tenant_id,user_id)，两输出表以同owner复合FK引用，拒绝跨owner generation。

用户/tenant来自当次认证，不从请求体取。prepare与commit重验同owner、订阅version/config hash、输入版本、epoch、来源/证据ACL、asset snapshot及角色；退订阻止新提醒但保留历史。旧generation不得覆盖较新的overlay。历史payload按严格canonical JSON真实bytes/hash验证，当前overlay与历史结论分开。

候选用实际已验证 affects_component_version/mapped_atlas typed关系、当前证据和研判收据；ContentStorage.read_verified校验实际原文/响应bytes，不以引文存在证明内容支持。material version包含相关事实/规则/资产/收据，排除读取时钟及无关globalepoch；generation input仍含所需epoch。每次输入最多2000事件、候选最多200，partial continuation显式。报告以冻结cutoff的日/周窗口生成，来源修订时刻与首次实质观察时刻分开。

允许同Session调用AssessmentService._read_result(session,scope,row)作为本批内部端口，保留其asset/current snapshot、rule/source ACL、内容及freshness校验；不得嵌套read()事务或复制研判真相。锁顺序复用现有actor→subscription→assets→source/document/revision→publication→claim/graph→epoch/final read；不持claim锁等publication。对外worker以后用server ActorReference，不保存raw凭据。

兼容性：新增内部持久服务，不改已审纯规则、四态或旧API。前向0027补约束/索引/不可变guard，保留旧数据。回滚关闭新handler/路由，保留历史；不自动downgrade。必要测试：两用户两租户、版本CAS、退订/角色/来源/资产并发、重放幂等、旧任务不能覆盖新结果、原文hash失败、报告历史/current区分、实际PG重启和浏览器完整操作。纯policy Ship不等于R15/T39完成；最终还依赖R16撤回重判及公开接口/UI。无自动外部消息发送。

本次写作结束时间：2026-10-16T12:28:28+08:00
最后更新时间：2026-10-16T12:28:28+08:00
