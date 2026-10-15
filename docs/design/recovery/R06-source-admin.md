# R06 来源管理 UI 扩展

作者 r06_document_workspace；基线0a45185ae3ffb73a6d186b98421e26a52f78bfc6；本切片awaiting_review，整R06/R17仍partial。新隔离WT D:/wt/r06-source-admin-ui，分支codex/r06-source-admin-ui。

已读AGENTS、执行图、R06/R17、03/05/08、新CR-R06_source_collection_catalog及CATALOG_SOURCES。采用Ponytail5.2 full，复用既有黑绿tokens、低亮动态背景、Cookie/CSRF/幂等/source job页面；不重做App、全局配置或认证，不增依赖。用户ui-design.md仅参考视觉分层/类别/任务进度，不把外部9类源或指标占位指令当内部合同。

设计判读为既有安全情报产品的来源管理切片，保留暗色黑绿、原导航、原输入顺序与访问控制。design-taste-frontend明确不用于dense product/admin，本次仅参考其保留品牌、单一主题、可读性与状态审计；redesign-existing-projects按已有React/native CSS扫描后作局部改进。不套用营销页的图片、hero、随机数据或新设计库要求。DESIGN_VARIANCE维持既有，MOTION_INTENSITY维持低亮背景（本切片无新增动画），VISUAL_DENSITY按原产品界面。

固定九key映射八类别：NVD与OSV同结构化漏洞，vLLM厂商公告，AVID社区，Ollama发布记录，Trail of Bits研究文章，arXiv论文，NIST标准，网信办政策。目录静态登记范围，逐条标「未验证」；不请求GET/sources，不展示开启/在线覆盖统计。真实状态只来自明确提交单源POST与随后手动GET/job；尚未查询保持未知。

设计：桌面左侧按类别分组的平面来源目录，右侧保留提交和PG任务查询。每行名称、固定key、来源范围与未验证，选择按钮仅选中并将焦点移至表单；提交仍由既有单源按钮明确触发。选中上下文先解释发布记录未研判、RSS片段/论文摘要与全文不同、标准自愿框架与政策适用判断尚未执行。390px单列，点击来源后定位提交表单，长key/说明可换行；不增动画，背景pointer-events:none与reduced-motion保留。

SourceKind闭合值扩9；请求体仍window_end/stream_kind/max_pages，响应仍原SourceJob。client本身不需改。任意key/URL/自报tenant继续在发送前拒绝。SourceCategory类型复用现有八值；元数据与主控CATALOG_SOURCES逐key测试对齐。

前置行为：原两源、live默认5页、原样重试同body/key、显式新轮次新key、CSRF晚到不POST均保留。切源与新轮次清旧job/查询时间；提交在途或请求冻结期间不能切源。管理员权限拒绝403清本页管理状态，CSRF403保持原样重试，401清身份；429/503解释失败/未确认，partial不等于来源采完。未知UUID查得job不推断其来源；本轮提交返回相同job_id时才标对应来源。查询时间是前端实际取得快照时刻，独立于PG任务时间；API未给freshness/TTL，不自行计算过期阈值，明确「未提供时效标记，请手动刷新」。

检查先定义闭合key/八类一致性与九POST负例，再做界面。单元验证管理员/无权/权限撤回、403/429/503/partial、重试、切源清空、CSRF/任务晚到、查询时效语义；全前端回归、strict/type/lint/build；1366/390/keyboard/reduced-motion与旧四来源fixture browser。新worker未完成时仅fixture/contract，不签live或完整评分项。
