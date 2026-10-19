# CR-R14 · 九职责生产适配与调用方事务

文档首次创建时间：2026-10-17T13:41:23.022+08:00
本次写作开始时间：2026-10-17T13:41:23.022+08:00
状态：approved_for_implementation，独立review后按证据生效，不代表R14验收。

目的补已批准九职责当前adapter_gaps：collector/enricher/graph_writer/assessor/reporter调用现有真实来源任务、九维富化、PG图投影、四态资产规则和推荐报告服务；orchestrator/triage/QA/critic继续真实模型/共享gateway。复用既有operation账本/JobExecutionContext/可信actor/lease/budget，同Session一次业务写+operation receipt，不引第二事实源。

最小内部typed ProductionRoleAdapters接可信engine/content_store/enrichment_service与caller Session、ActorReference/AccessScope/已验证request、原budget/node key。允许唯一作者在assessment现有服务与graph_projection提取职责明确的caller-session transactional helper，共享业务体保留原有校验/锁/失败，旧Engine入口委托保兼容。只准必要seam，不万能Service、不复制算法。graph源码先精确qualified986b guard；无默认namespace/代际回退、不可全scope无界扫描。每次已有规则/来源最多固定cap，保Source-beforeEvent锁序，Sideeffect和账本同txn，unknown/reserved不重放新副作用。

原MAX23与原model/tool/output/deadline上限保持。来源只request evidenceRefs映射的已注册source及固定SourceKind，页数1；禁用户任意URL/SQL/shell。富化九维子job使用原独立Enrichment budget/policy且记录父子task/receipt与未知费用，父仅accepted_task/partial，不把下游call数藏成0费用，也不声称完成；缺APIactor兼容时明确blocked，不能伪session身份。资产只授权scope/request snapshot/≤8 currentpublished规则，缺规则/条件保持未知。报告须本人enabled subscription且asset范围精确当前request，真实R15 artifact/CAS和证据保存，缺配置partial。

无公开schema、迁移、依赖、评分/金标/分母变更。Root独占workers/runtime/App/Git；唯一集成人仅workflow_service/runtime、新窄adapter、assessment/graph_transaction helpers和直属tests。既有QA076/e310快照、generation helper、plugin生产账本eea必要依赖要逐raw/AST绑定并保护Root旧修复；不能整旧分支覆盖Root共享业务。无sideeffect时旧路径保持；回滚取消默认factory配置恢复明确not_configured，保留已accepted子任务/历史、不删除PG状态。

必要测试：每role真实service端口调用、权限/跨租户、无规则、异步accepted、预算、sourcecohort locks、reserved unknown/重放、账本与业务原子rollback、原caller兼容；真实PG/model/Neo4j/MinIO与APIworker接线按独立Resource gate，fixture不计live；6层not_run逐层保留。独立新reviewer审核冻结SHA和CR，主控方可记录limited切片资格。

本次写作结束时间：2026-10-17T13:41:23.023+08:00
