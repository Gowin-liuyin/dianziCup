# G-A · R00 能力切片与原任务合并验收分析

文档首次创建时间：2026-10-14T20:58:51+08:00
本次写作开始时间：2026-10-14T20:58:51+08:00
本次写作结束时间：2026-10-14T20:58:51+08:00
最后更新时间：2026-10-14T20:58:51+08:00
本报告证据截止时间：2026-10-14T20:58:51+08:00
读卡分析开始时间：历史未记录；不能由文件mtime推断。
结构复验时间：2026-10-14T20:56:22+08:00
分析基线：`main@8e265dc039a67319140f003f6a070ea714bf7bef`
报告生成时工作分支/HEAD：`codex/full-delivery-recovery@b8199ce5dd0a7920ce5770e4f580fe23e0fe9f6b`
分析Agent：`/root/recovery_mapping_audit`
任务状态：`awaiting_review`；本报告不是冻结独立review，不签accepted。
实现状态：本分析产物complete；业务实现/验证未执行。

## 1. 结论与交付范围

恢复卡覆盖索引没有遗漏原T00–T59。已生成110个可核验能力切片、26个恢复执行节点（R24拆A/B）和60项原卡聚合条件，完整保留原360项实施步骤、360个C01–C06验收案例及卡文件hash。原T卡前置用于整卡最终独立验收，恢复执行使用前置能力切片，不将后段整卡状态倒灌为早期执行前置。

结构分析核验13个要求ID、U01–U14责任映射及初/决赛100/100分。它证明计划结构覆盖，不证明业务运行、官方档位达标或产品可用。

交付JSON：[`mapping_analysis.json`](../../runs/recovery_mapping_20261014/mapping_analysis.json)。可供主控增量写入manifest的部分为`recovery`，原tasks/stages/execution_order保留历史。`original_contract_snapshot`保留原实施步骤、验收案例、引用合同与hash；不是新的弱化验收合同。完整实际结构复验命令、开始/结束与输出见[`structural_check.json`](../../runs/recovery_mapping_20261014/structural_check.json)。

仅读AGENTS、11/12恢复文档、00/01执行与评分、requirements/task_manifest/task_state、60张T卡、审计/交接/阻塞及相关数据/算法/API/评测条款，源码rg核对旧审计位置。未读取附件秘密、.env、holdout答案或第三方用户资料。读取最新版插件Ponytail 5.2.0及review正文，复用原合同和Python标准库分析，不增加依赖。

## 2. 必须统一的计划差异

| 编号 | 具体输入/条款 | 当前结果与影响 | 最小处理 |
|---|---|---|---|
| M-01 | `progress/task_state.json:68` T18重复`note` | 常规JSON解析覆盖历史审查说明；本分工解析实证两值均存在 | 主控严格拒绝重复键，追加历史纠偏；恢复两个note为有序历史/独立执行顺序说明 |
| M-02 | 11 §9写R19在G-B后，12写R04后 | 模型live阻塞时不应阻止安全独立的工具/候选准备 | 用户当前授权为R04真实链路后可准备，完整R07–R16覆盖与人工标签后才正式冻结 |
| M-03 | 00/manifest原60卡串行与恢复主线 | T06/R20或T04/R18整卡后置会阻断R03，T17模型前置会阻断R04 | CR-R07声明本批执行权威为恢复能力DAG；旧顺序保留历史与原最终前置，不静默改原验收 |
| M-04 | R卡正文“原任务”头部与末尾覆盖索引 | 13个R卡头部少列T切片，按头部调度会遗漏 | 按下一表同步正文、切片/聚合manifest和执行地图；不删末尾条目 |
| M-05 | T55/T56如果强制要求R24-B再accepted | T57要求T55/T56，R24-B又等R23:T57，形成最终验收互锁 | T55/T56在R24-A完整满足原卡并由新reviewer独立试部署/材料检查；T59候选A+最终B；R23后材料改版须定向复核 |

| R卡 | 覆盖索引中存在但正文头部漏列的原T卡 |
|---|---|
| R00 | T04 |
| R02 | T04 |
| R06 | T08 |
| R07 | T13、T41 |
| R09 | T09 |
| R10 | T41 |
| R11 | T11、T42 |
| R13 | T42 |
| R14 | T43 |
| R16 | T28、T39、T44 |
| R18 | T04 |
| R19 | T01 |
| R20 | T03、T06、T07、T44 |

CR-R01–R09建设方向已由用户授权。本分析只提出映射与兼容/顺序修正，正式变更生效仍须主控记录迁移/回滚/测试影响，并交新独立reviewer核对授权落实；本报告不能替代该冻结review。

## 3. 恢复执行DAG与切片前置

每个requires_slices都存在且生产节点在消费者之前；未以整卡accepted替代能力证据。下表外部前置是开发/验收真实需要的能力，不代表这些能力当前已通过。包内T顺序仍保留必要业务先后。

| 节点 / 阶段 | 包前置 | 必须读取的前置切片 | 依赖理由 |
|---|---|---|---|
| R00 / G-A | 无 | 无 | 合同与现状审计无产品前置，批准建设决策仍须落实CR并独立审查。 |
| R01 / G-A | R00 | R00:T00、R00:T01、R00:T04 | 只依赖R00冻结的运行/认证/基础设施合同；路由装配与依赖ready不等待R02完整仓储。 |
| R02 / G-A | R01 | R01:T02、R01:T03、R01:T06、R00:T04 | 需要实际PG与类型合同；实现会话/事实/断言/关系仓储和事务结构，不要求模型抽取或关系推理先完成。 |
| R03 / G-A | R02 | R02:T05、R02:T06、R00:T04、R01:T03 | 需要PG事实事务、认证范围、网关DTO与实际Redis；T07/T08/T16在包内按任务/outbox→网关→游标装配，不能等待R20整卡安全。 |
| R04 / G-B | R03 | R03:T07、R03:T08、R03:T16、R02:T05、R02:T17、R01:T40、R00:T04 | 需要网关、持久化原文/游标、确定性事件仓储和登录外壳；归并初版用强标识，模型缺失保留uncertain，不以真实模型后置卡住第一链。 |
| R05 / G-B | R04 | R04:T09、R04:T10、R04:T40、R04:T41、R02:T06、R02:T21 | 需要真实可定位证据、范围化事实读取和鉴权；完成生成/embedding/rerank与初始QA，不等后段全文图谱/调查。 |
| R06 / G-C | R04 | R04:T09、R04:T10、R04:T12、R03:T08、R03:T16、R02:T05 | 来源连接器只依赖解析/网关/游标/PG；R05模型live缺失不阻断独立来源适配，不能由此宣称G-B通过。 |
| R07 / G-C | R02、R05、R06 | R02:T19、R02:T21、R05:T18、R05:T20、R06:T11、R06:T13、R06:T14、R06:T15 | 九维业务需要真实模型/结构化来源/账本；暴露先冻结接口状态合同，R08的实际聚合尚未通过时不可涂绿。 |
| R08 / G-C | R03、R07 | R03:T08、R07:T19、R07:T23 | 公网聚合依赖受控网关与R07暴露合同，供应商文档/账号/模板为外部前置；不依赖FOFA私有资产。 |
| R09 / G-C | R04、R05、R06、R07 | R04:T09、R05:T18、R06:T14、R06:T15、R07:T22、R02:T21 | 知识卡需要原文解析、来源、抽取合同与模型支持；R04后可独立整理原文候选，正式问答证据仍依赖R05/R07。 |
| R10 / G-C | R07、R09 | R02:T17、R02:T21、R07:T20、R07:T22、R07:T23、R09:T14、R09:T15、R09:T22 | 六类关系需要断言事务、模型抽取及资料卡；Neo4j仅投影，图谱落后仍回查PG当前性和权限。 |
| R11 / G-D | R02、R07、R10 | R02:T05、R02:T06、R07:T19、R07:T20、R10:T21、R06:T11、R03:T07 | 资产/版本/条件依赖成熟版本输入、事实发布与任务状态；包内按T24/T26→T27→T28→T29，不等T28在R16的未来重判切片。 |
| R12 / G-D | R05、R09、R10、R11 | R05:T18、R05:T30、R05:T31、R09:T22、R10:T21、R10:T22、R11:T27、R11:T28、R11:T29、R02:T06 | 混合多跳QA依赖真实模型、知识卡、已核验关系、资产规则；R05初始检索不等于完整T30/T31。 |
| R13 / G-D | R03、R11 | R03:T08、R03:T07、R11:T24、R11:T28、R02:T06 | 授权观察依赖授权资产快照和网关；授权资产范围与FOFA账号字段是外部前置，空结果不作排除证据。 |
| R14 / G-D | R03、R05、R10、R11、R12、R13 | R03:T07、R05:T18、R10:T21、R11:T28、R12:T30、R12:T31、R13:T25 | 调查需要可用工具的schema、权限、预算、业务结果与PG任务恢复；R13 live阻塞可开发非FOFA分支，相关工具必须not_configured/partial且正式全验收不越过。 |
| R15 / G-E | R11、R12、R14 | R11:T28、R12:T31、R14:T34、R14:T35 | 推荐依赖资产研判、引用QA与调查输出；初版以有效快照排序和去重，R16提供未来撤回/双时间切片，不反向要求T38整卡先通过。 |
| R16 / G-E | R02、R03、R11、R12、R15 | R02:T05、R02:T21、R03:T07、R11:T24、R11:T28、R12:T31、R15:T39 | 变化处理需要已保存答案/研判/推荐与事实事务；旧命中、新命中、空结果、撤回和历史均需覆盖。 |
| R17 / G-E | R04、R05、R06、R07、R08、R09、R10、R11、R12、R13、R14、R15、R16 | R04:T40、R04:T41、R07:T41、R10:T41、R11:T42、R13:T42、R12:T43、R14:T43、R15:T43、R16:T39、R16:T44 | 各页面只消费对应已验证业务切片；可按页面渐进实现，完整包验收等R04–R16对应接口及变化结果。 |
| R18 / G-E | R00、R11、R12、R14、R15、R17 | R00:T04、R11:T24、R11:T28、R11:T29、R12:T35、R14:T32、R14:T35、R15:T39、R17:T40、R17:T43 | 协议统一必须调用已测业务和鉴权，不在适配器复制真值；公共schema以R00合同为准，完整客户端/插件验收后置。 |
| R19 / G-F | R07、R08、R09、R10、R11、R12、R13、R14、R15、R16 | R00:T01、R00:T04、R04:T09、R04:T10、R07:T19、R10:T21、R11:T28、R12:T31、R14:T34、R15:T39、R16:T37 | 准备工具R04后可独立开始；正式冻结需要九维/关系/资产/QA/调查/推荐/重判完整覆盖与双人独立标签裁决，不能只冻结易例。 |
| R20 / G-F | R16、R17、R18 | R01:T03、R02:T06、R03:T07、R06:T16、R06:T49、R16:T37、R16:T38、R16:T39、R17:T43、R17:T44、R18:T32、R18:T35、R18:T51 | 基础监控R01起接入；全安全/恢复/CI验收需要更新、完整UI和公开协议/插件攻击面；T51性能检查可先接可运行开发检查，正式最终制品与R21性能结果保持版本关联。 |
| R21 / G-F | R14、R15、R16、R17、R18、R19、R20 | R14:T34、R16:T37、R19:T46、R18:T35、R17:T43、R20:T45、R20:T50 | 同条件实验需要完整能力、开发集/评测工具、安全恢复基线；性能修复导致代码变化须重新冻版本及相关回归。 |
| R22 / G-G | R19、R20、R21 | R19:T46、R20:T45、R20:T49、R20:T50、R20:T51、R21:T47、R21:T48、R17:T41、R17:T42、R17:T43、R17:T44 | 正式评测与全链路验收依赖人工冻结、工程安全和可比基线；早期观测按各代码版本分段记录不能拼成最终版本持续窗口。 |
| R24-A / G-G | R22 | R22:T52、R22:T53、R22:T54、R18:T51、R21:T47、R21:T48 | 需要正式评测和实际运行证据形成候选报告/演示/清单；候选材料为R23输入，不能声称整张R24/T55/T56/T59完成。 本片须完整满足T55/T56原检查并独立核验；候选制品清单为准备artifact，不提前完成T59。 |
| R23 / G-G | R22、R24-A | R22:T52、R22:T53、R22:T54、R20:T51、R24-A:T55、R24-A:T56、R24-A:T59 | 从候选材料和冻结产品独立干净环境复现及逐项审计；使用R24-A而非最终R24，避免循环。 |
| R24-B / G-G | R23 | R23:T57、R23:T58、R24-A:T55、R24-A:T56、R24-A:T59 | 必须消费R23复现/逐项审查结果后修订及冻结；最终T59的T58前置在这里闭合。 若R23后实质修改T55/T56材料，记录新版本与相关复核，撤回旧签字适用性；无必要修改不制造额外固定能力切片。 |

R24是聚合工作包，不加入26节点执行DAG：R22→R24-A→R23→R24-B。R24-A产生可复现候选材料；整张R24仍partial/in_progress。T55步骤6“独立按文档试部署”必须在A由新的独立reviewer真实完成，不能以R23未来会做替代；R23仍负责完整干净环境复现。T55/T56候选材料经R23实质修改后，旧版本验收不为新版背书。

关键包内顺序：R03为任务/outbox→受控网关→游标；R04为真实解析/归一→强标识事件归并→API/UI；R11为T24/T26→T27→T28→T29；R14为T32→T33→T34→T35。模型相关模糊分类未接通时保留uncertain，不能输出确认；持久化结构可以先实现，不伪造模型结果。

## 4. 可安全提前的准备与阻塞传播

| 准备项 | 开始条件 | 允许部分 | 仍须满足的正式门 |
|---|---|---|---|
| R19-tools-candidates | R04及对应切片证据 | 标注工具、证据包、真实候选集；不读取holdout答案。 | R07–R16完整覆盖、双人独立核验和裁决、隔离冻结manifest。 |
| R20-basic-observability | R01及对应切片证据 | 运行标识、结构化脱敏日志、依赖健康、隔离/指标骨架；后续每链逐项接入。 | R16–R18完整功能上的安全/监控/恢复/CI实际故障与攻击验收。 |
| R22-early-observation | R04及对应切片证据 | 从首条真实采集链记录代码版本/配置/开始结束/中断/参考集合；按版本独立统计。 | R19冻结+R20/R21通过，冻结代码连续窗口和正式测评。 |
| R24-document-skeleton | R00及对应切片证据 | 报告/演示/交付清单骨架与许可清单，不填尚未取得的结果。 | R22→R24-A→R23→R24-B。 |
| R06-source-adapters-while-model-blocked | R04及对应切片证据 | 真实独立来源适配；不把R05/G-B模型live阻塞改为通过。 | 来源逐项live与G-C检查，G-B依旧保留阻塞。 |

R05模型live缺失不阻止R06来源适配或R19准备，但G-B真实问答仍blocked。R08公网聚合与R13授权FOFA是两条独立链，账号/字段/资产授权不足只阻止对应live；UI可以明确展示blocked/unknown，但不能把展示错误状态当供应商接通。R14非FOFA工具可以独立开发/复验，必须记录R13阻塞传播，完整正式Agent/资产live不能穿过。R20原T51依赖T48性能结果，故R20可先完成CI工程切片，原T51完整验收还必须等待R21:T48共同完成；不得在G-F早期将原T51整卡accepted。

原卡“前置”和切片前置分工明确：recovery.work_packages描述允许执行的能力边界；original_task_aggregation.final_dependencies保留原前置和它们的全部切片，仅用于整卡最终接受。JSON同时给直接切片最早阶段和包含原前置后的最早最终验收阶段，不能从R01完成推出T02整卡已最终验收。

## 5. 60张原T卡合并验收表

每行全部required_slices、原前置、原实施步骤与C01–C06、引用合同和独立review必须共同满足。模型/live/人工标签未证明时保持对应blocked/not_run。案例正文和原卡hash在JSON，表中不以一句摘要替代其约束。

| 原卡 / 原验收合同 | 全部所需切片 | 原最终前置 | 验收保留 |
|---|---|---|---|
| [T00](../../../docs/tasks/T00_repository_audit.md) · 仓库、资源与授权审计 | R00:T00 | 无 | T00-C01–C06＋6实施步骤＋引用合同 |
| [T01](../../../docs/tasks/T01_requirements_and_fixtures.md) · 评分追踪、任务状态与首批验收样例 | R00:T01、R19:T01 | T00 | T01-C01–C06＋6实施步骤＋引用合同 |
| [T02](../../../docs/tasks/T02_project_skeleton.md) · 项目骨架、依赖锁定与质量命令 | R01:T02 | T01 | T02-C01–C06＋6实施步骤＋引用合同 |
| [T03](../../../docs/tasks/T03_development_services.md) · 开发依赖容器与配置分层 | R01:T03、R20:T03 | T02 | T03-C01–C06＋6实施步骤＋引用合同 |
| [T04](../../../docs/tasks/T04_domain_contracts.md) · 领域类型、枚举与JSON Schema | R00:T04、R02:T04、R18:T04 | T02 | T04-C01–C06＋6实施步骤＋引用合同 |
| [T05](../../../docs/tasks/T05_persistence_and_raw_store.md) · 数据库迁移、原文存储和不可变版本 | R02:T05 | T03、T04 | T05-C01–C06＋6实施步骤＋引用合同 |
| [T06](../../../docs/tasks/T06_authentication_and_scope.md) · 用户认证、租户权限与审计基础 | R01:T06、R02:T06、R20:T06 | T05 | T06-C01–C06＋6实施步骤＋引用合同 |
| [T07](../../../docs/tasks/T07_jobs_and_outbox.md) · 任务、事务outbox与幂等工作进程 | R03:T07、R20:T07 | T05、T06 | T07-C01–C06＋6实施步骤＋引用合同 |
| [T08](../../../docs/tasks/T08_network_and_sources.md) · 受控抓取网关与来源注册 | R03:T08、R06:T08、R08:T08 | T04、T06、T07 | T08-C01–C06＋6实施步骤＋引用合同 |
| [T09](../../../docs/tasks/T09_document_parsing.md) · HTML、JSON、PDF解析和永久证据定位 | R04:T09、R09:T09 | T05、T08 | T09-C01–C06＋6实施步骤＋引用合同 |
| [T10](../../../docs/tasks/T10_cve_nvd_connectors.md) · CVE与NVD结构化连接器 | R04:T10 | T09 | T10-C01–C06＋6实施步骤＋引用合同 |
| [T11](../../../docs/tasks/T11_osv_connector.md) · OSV字段和版本范围输入 | R06:T11、R11:T11 | T09 | T11-C01–C06＋6实施步骤＋引用合同 |
| [T12](../../../docs/tasks/T12_vendor_blog_connectors.md) · 厂商公告与技术博客自动接入 | R04:T12、R06:T12 | T09 | T12-C01–C06＋6实施步骤＋引用合同 |
| [T13](../../../docs/tasks/T13_community_repository_connectors.md) · 安全社区与代码仓库记录接入 | R06:T13、R07:T13 | T09 | T13-C01–C06＋6实施步骤＋引用合同 |
| [T14](../../../docs/tasks/T14_academic_connector.md) · 学术论文发现、版本与摘要 | R06:T14、R09:T14 | T09 | T14-C01–C06＋6实施步骤＋引用合同 |
| [T15](../../../docs/tasks/T15_standards_policy_connectors.md) · 技术标准与政策法规原文接入 | R06:T15、R09:T15 | T09 | T15-C01–C06＋6实施步骤＋引用合同 |
| [T16](../../../docs/tasks/T16_incremental_monitoring.md) · 持续增量采集、恢复与时效测量 | R03:T16、R06:T16 | T10、T11、T12、T13、T14、T15、T07 | T16-C01–C06＋6实施步骤＋引用合同 |
| [T17](../../../docs/tasks/T17_relevance_and_event_linking.md) · AI相关性、事件归并与可撤销关联 | R02:T17、R04:T17、R10:T17 | T18、T09 | T17-C01–C06＋6实施步骤＋引用合同 |
| [T18](../../../docs/tasks/T18_model_clients.md) · 真实模型、向量与重排接口及测试替身 | R05:T18 | T04、T08 | T18-C01–C06＋6实施步骤＋引用合同 |
| [T19](../../../docs/tasks/T19_structured_enrichment.md) · 结构化富化与维度状态 | R02:T19、R07:T19、R08:T19 | T11、T17 | T19-C01–C06＋6实施步骤＋引用合同 |
| [T20](../../../docs/tasks/T20_claim_extraction.md) · 少样本抽取、来源片段与字段校验 | R05:T20、R07:T20 | T18、T19、T09 | T20-C01–C06＋6实施步骤＋引用合同 |
| [T21](../../../docs/tasks/T21_claims_entities_conflicts.md) · 实体归一、事实版本与冲突处理 | R02:T21、R10:T21 | T20、T17、T05 | T21-C01–C06＋6实施步骤＋引用合同 |
| [T22](../../../docs/tasks/T22_research_and_document_links.md) · 论文关联、风险机制与标准政策知识卡 | R07:T22、R09:T22、R10:T22 | T21、T14、T15 | T22-C01–C06＋6实施步骤＋引用合同 |
| [T23](../../../docs/tasks/T23_poc_scores_impact.md) · POC、评分、修复与影响评估富化 | R07:T23、R08:T23、R10:T23 | T21、T19、T13 | T23-C01–C06＋6实施步骤＋引用合同 |
| [T24](../../../docs/tasks/T24_asset_inventory.md) · 授权资产、组件和AI配置快照 | R11:T24 | T05、T06、T04 | T24-C01–C06＋6实施步骤＋引用合同 |
| [T25](../../../docs/tasks/T25_fofa_observations.md) · FOFA被动观察与授权范围 | R13:T25 | T24、T08 | T25-C01–C06＋6实施步骤＋引用合同 |
| [T26](../../../docs/tasks/T26_version_engine.md) · 生态化版本比较与区间包含 | R11:T26 | T04、T11 | T26-C01–C06＋6实施步骤＋引用合同 |
| [T27](../../../docs/tasks/T27_condition_rules.md) · 受限条件AST、规则发布与四态执行 | R11:T27 | T21、T26 | T27-C01–C06＋6实施步骤＋引用合同 |
| [T28](../../../docs/tasks/T28_assessments.md) · 资产研判、证据包与提交校验 | R11:T28、R16:T28 | T24、T27、T07 | T28-C01–C06＋6实施步骤＋引用合同 |
| [T29](../../../docs/tasks/T29_openvex_export.md) · 受限OpenVEX与证据报告导出 | R11:T29 | T28 | T29-C01–C06＋6实施步骤＋引用合同 |
| [T30](../../../docs/tasks/T30_hybrid_retrieval.md) · 授权过滤的BM25、向量检索与重排 | R05:T30、R12:T30 | T21、T18、T06 | T30-C01–C06＋6实施步骤＋引用合同 |
| [T31](../../../docs/tasks/T31_grounded_qa_baseline.md) · 有引用问答基线与多轮会话 | R05:T31、R12:T31 | T30、T18、T06 | T31-C01–C06＋6实施步骤＋引用合同 |
| [T32](../../../docs/tasks/T32_tool_gateway.md) · 工具注册、权限、预算和调用记录 | R14:T32、R18:T32 | T18、T25、T28、T30 | T32-C01–C06＋6实施步骤＋引用合同 |
| [T33](../../../docs/tasks/T33_agent_workflow.md) · 四角色Agent固定工作流与持久化 | R14:T33 | T31、T32、T07 | T33-C01–C06＋6实施步骤＋引用合同 |
| [T34](../../../docs/tasks/T34_evidence_gap_scheduler.md) · 关键证据缺口驱动调查与停止 | R14:T34 | T33 | T34-C01–C06＋6实施步骤＋引用合同 |
| [T35](../../../docs/tasks/T35_api_integration.md) · 统一业务API、任务轨迹与多跳整合 | R12:T35、R14:T35、R18:T35 | T29、T34、T31 | T35-C01–C06＋6实施步骤＋引用合同 |
| [T36](../../../docs/tasks/T36_dependency_watches.md) · 引用依赖、范围关注与负结果依赖 | R16:T36 | T28、T31、T21 | T36-C01–C06＋6实施步骤＋引用合同 |
| [T37](../../../docs/tasks/T37_incremental_revalidation.md) · 变化失效、局部重算与并发一致性 | R16:T37 | T36、T07 | T37-C01–C06＋6实施步骤＋引用合同 |
| [T38](../../../docs/tasks/T38_temporal_and_cache.md) · 双时间查询与缓存失效 | R16:T38 | T37、T31 | T38-C01–C06＋6实施步骤＋引用合同 |
| [T39](../../../docs/tasks/T39_personalized_recommendations.md) · 个性化订阅、推荐与修订撤回 | R15:T39、R16:T39 | T38、T28、T31 | T39-C01–C06＋6实施步骤＋引用合同 |
| [T40](../../../docs/tasks/T40_frontend_shell.md) · 前端骨架、认证与统一状态组件 | R01:T40、R04:T40、R17:T40 | T02、T06 | T40-C01–C06＋6实施步骤＋引用合同 |
| [T41](../../../docs/tasks/T41_sources_events_ui.md) · 来源、事件、维度与证据详情页面 | R04:T41、R07:T41、R10:T41、R17:T41 | T40、T17、T21 | T41-C01–C06＋6实施步骤＋引用合同 |
| [T42](../../../docs/tasks/T42_assets_assessment_ui.md) · 资产、规则条件与证据包页面 | R11:T42、R13:T42、R17:T42 | T40、T28、T29 | T42-C01–C06＋6实施步骤＋引用合同 |
| [T43](../../../docs/tasks/T43_qa_agents_recommendations_ui.md) · 问答、Agent轨迹和推荐交互 | R05:T43、R12:T43、R14:T43、R15:T43、R17:T43 | T40、T35、T39 | T43-C01–C06＋6实施步骤＋引用合同 |
| [T44](../../../docs/tasks/T44_changes_operations_ui.md) · 变化、运行监控与评测结果展示 | R16:T44、R17:T44、R20:T44 | T40、T37、T49 | T44-C01–C06＋6实施步骤＋引用合同 |
| [T45](../../../docs/tasks/T45_security_regression.md) · 全链路权限、提示词注入和污染测试 | R20:T45 | T35、T38、T39、T43 | T45-C01–C06＋6实施步骤＋引用合同 |
| [T46](../../../docs/tasks/T46_benchmark_dataset.md) · 标注工具、开发集与盲测隔离 | R19:T46 | T01、T04、T09、T10 | T46-C01–C06＋6实施步骤＋引用合同 |
| [T47](../../../docs/tasks/T47_baselines_and_ablation.md) · 强基线、消融和复跑框架 | R21:T47 | T34、T37、T46 | T47-C01–C06＋6实施步骤＋引用合同 |
| [T48](../../../docs/tasks/T48_performance_benchmarks.md) · 问答速度、吞吐与监测性能测试 | R21:T48 | T35、T43、T47 | T48-C01–C06＋6实施步骤＋引用合同 |
| [T49](../../../docs/tasks/T49_observability_alerts.md) · 结构化监控、指标和告警 | R06:T49、R20:T49 | T07、T16、T35 | T49-C01–C06＋6实施步骤＋引用合同 |
| [T50](../../../docs/tasks/T50_recovery_and_backup.md) · 自愈、故障注入与备份恢复 | R20:T50 | T37、T49、T03 | T50-C01–C06＋6实施步骤＋引用合同 |
| [T51](../../../docs/tasks/T51_ci_cd_release_pipeline.md) · 完整CI/CD与受控发布流程 | R18:T51、R20:T51 | T45、T48、T50 | T51-C01–C06＋6实施步骤＋引用合同 |
| [T52](../../../docs/tasks/T52_end_to_end_acceptance.md) · 三模块全链路与全部功能验收 | R22:T52 | T41、T42、T43、T44、T51 | T52-C01–C06＋6实施步骤＋引用合同 |
| [T53](../../../docs/tasks/T53_frozen_evaluation.md) · 冻结配置、正式盲测与结果分析 | R22:T53 | T46、T47、T48、T52 | T53-C01–C06＋6实施步骤＋引用合同 |
| [T54](../../../docs/tasks/T54_live_soak.md) · 真实持续监测与稳定性观察 | R06:T54、R22:T54 | T16、T49、T50、T52 | T54-C01–C06＋6实施步骤＋引用合同 |
| [T55](../../../docs/tasks/T55_technical_report.md) · 技术报告、设计图和可复现说明 | R24-A:T55 | T47、T48 | T55-C01–C06＋6实施步骤＋引用合同 |
| [T56](../../../docs/tasks/T56_demo_and_slides.md) · 演示脚本、匿名答辩材料与视频 | R24-A:T56 | T52、T55 | T56-C01–C06＋6实施步骤＋引用合同 |
| [T57](../../../docs/tasks/T57_independent_review.md) · 独立代码审查与干净环境复现 | R23:T57 | T51、T55、T56 | T57-C01–C06＋6实施步骤＋引用合同 |
| [T58](../../../docs/tasks/T58_rubric_gap_audit.md) · 逐评分项证据审计与缺口闭合 | R23:T58 | T53、T54、T57 | T58-C01–C06＋6实施步骤＋引用合同 |
| [T59](../../../docs/tasks/T59_release_handoff.md) · 发布冻结、交接与最终提交检查 | R24-A:T59、R24-B:T59 | T58 | T59-C01–C06＋6实施步骤＋引用合同 |

重点合并条件：T06=R01装配+R02跨进程持久化+R20全链路安全；T40=R01入口+R04真实登录/事件UI+R17统一状态/类型/可访问性；T20=R05初始生成+R07完整语义/限定/否定校验；T30/T31=R05初链+R12完整权限/历史/多轮/混合检索；T35=R12回答+R14调查/任务+R18统一API；T39=R15初版推荐+R16撤回历史；T43还需R14/15/17，首问页面不等整卡；T19/T23暴露R07仅合同，R08才实际聚合；T28需R16未来重判切片，R11CAS并发基础不能冒充变化闭环。

## 6. 旧accepted纠偏建议与证据

本分工真实重新读取基线、JSON、任务卡并rg核对源码；没有运行旧审计的153业务测试或数据库/live探针。源码位置与同SHA审计结论交叉核对，不将旧通过数当当前通过。

| 原卡 | 建议当前复核方向 | 证据与影响 |
|---|---|---|
| T06 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A01/A07：默认认证入口未装配，会话/限流/审计驻内存；本轮rg确认app.py:47/authentication.py:194–196。 |
| T09 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A02：PDF仅TEXTLAYER测试标记；本轮rg确认parsers.py:107/116。 |
| T10 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A03：真实NVD wrapper/cvssData字段错；本轮rg确认nvd.py:32–35/58–59。 |
| T16 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A06：内存游标、失败仍推进；本轮rg确认scheduler.py:35/90；运行失败例沿用同SHA审计探针。 |
| T18 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A04：只有FixtureProvider/验证器无真实三接口；本轮rg确认clients.py:126/132。 |
| T19 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A10：六内部维度非完整九维、核心账本内存；需R02/R07/R08。 |
| T21 | needs_changes；implementation=partial；保留历史accepted并引用独立纠偏意见，不仅写blocked_live。 | A05：ledger内存且transactional:true不等于真实事务；本轮rg确认claims.py:107。 |

T02/T03/T04/T05/T07/T08/T11–T15/T17/T20/T22/T23应至少重开集成/运行证据复核：无本轮复现的风险不直接登记业务failed。T05/T07曾有真库历史证据，本分析没有把“未复跑”改为“已失败”。T00/T01历史可保留，但恢复建设范围与人工冻结切片重新独立核验。T24–T59旧pending没有证据支持改绿。逐卡建议在JSON的status_correction_proposals；主控最终状态更新以其当前独立review结论登记。

重复JSON键为真实结构缺陷：`tasks.T18.note`两值完整保存在analysis JSON strict_json_errors字段。应保留历史RV-T18b说明和“执行顺序在T17之前”，不能仅保留后一项。原22项accepted缺逐层verification的现象应补证据目录；默认值not_run不等当年未跑，也不等今天passed。

## 7. 实际命令和验证层级

| 工作目录 / 命令 | 退出码 / 当前结果 | 证据 |
|---|---|---|
| D:/dianzi · `git status --short`、`git branch --show-current`、`git rev-parse HEAD` | 各0；起始main@8e265dc；5组未跟踪恢复文档/审计产物。未覆盖/清理/提交用户修改 | 工具结果87c049，分析baseline字段 |
| D:/dianzi · Get-Content AGENTS/恢复卡/地图/评分/审计；Python读取60卡实施步骤/验收；rg源码关键位置 | 0；读取并交叉核验，不是产品测试 | original_contract_snapshot（卡hash）、本报告引用位置 |
| D:/dianzi · Python object_pairs_hook分析requirements/task_manifest/task_state | 0；前两者无重复键；task_state报告T18重复note | strict_json_errors |
| D:/dianzi · Python标准库生成mapping_analysis并assert | 0；60原卡/360案例/360步骤/110切片/26节点 | mapping_analysis.json assertions |
| D:/dianzi · 结构复验 `python -c <structural_check.json argv[2]>` | 0；60原卡hash一致，全部生产切片早于消费者，无执行环；13要求/14场景/100+100 | structural_check.json：20:56:22+08:00开始/结束 |

业务unit/integration/security/frontend/e2e/live/manual均not_run；contract仅本分析结构assertions passed，不回填产品contract通过。无产品测试计数、skip、准确率/召回率/延迟/费用和持续运行数据。本分工未重解析官方PDF；官方原文核对及资源能力实测由主控R00整合证据负责。本分工未建立CBM索引或作业务调用链独立验收；主控另分工索引证据，本报告仅计划映射不以图证明代码正确。

## 8. 主控集成建议与结束条件

将recovery字段增量接入manifest，保留旧60卡合同与历史；同步13处R头部、R19/R20/R22准备规则、有效执行DAG和聚合验收说明；用严格JSON与结构负例验证缺slice、反向/环、原case缺失、R24误聚合等输入均拒绝。随后冻结R00候选SHA/tree，创建新独立reviewer复核CR-R01–09授权准确性、兼容迁移回滚与映射完整性。本分析Agent没有参与业务实现，但作为映射作者也不能独立签自己产物。

结束条件已满足：60卡均有归属；所有原验收保留；恢复依赖无环；R24-A→R23→R24-B与原T最终验收不互锁；JSON可供主控集成。下一任务由主控R00冻结审查后调度R01，本分工不擅自改状态/合同、不commit/push。

## 9. 修订记录

- 2026-10-14T20:58:51+08:00：首次创建报告，整理真实读卡/源码与结构分析；不签业务accepted。
- 2026-10-14T20:55:12+08:00：JSON终端验收映射修正为T55/T56仅A完整检查、T59 A+B；主控消息同意该解释，避免原T57前置互锁。
