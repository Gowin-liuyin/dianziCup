# CR-R18 · 当前组件风险摘要生产器

文档首次创建时间：2026-10-17T07:01:45.941+08:00
状态：approved_for_implementation；非作者独审/实际PG仍待执行。

落实已批准CR-R18_public_envelopes_and_output_budget的r18-risk-policy-1，不修改v2/extensions/SDK validator。唯一新实现者新增api/public_risk_summary.py及直属tests，函数build_current_stack_envelope(payload,assessment_service,knowledge_service,*,minimum_severity='high')返回严格PublicStackCheckEnvelope；Root负责default route/最终身份围栏/媒体类型切换。复用现selector和stack adapter/同Session研判读取，以及公开知识共享验证器，禁止raw claim分数直接决定风险。

评估须覆盖本次请求组件的所有当前已发布相关规则和当前研判，bounded查询超过范围/未知规则/多候选归因/版本缺失/未评估/冲突/来源失效不得complete。不能凭现selector选择一个结果声称查询全域已完成；未支持范围显示partial或unknown，不宣称安全。每finding绑定同事件current适用性研判、规则版本、语义证据验证的CVSS claim、真实引用；source优先级不消冲突。只有本次明确查询范围全部当前、有证据排除或已分级且无阈值finding时none_confirmed；空范围永不complete。多规则无法在现冻结一组件一研判封装表达时明确gap并报告合同边界，不擅改schema/默选最新。

新类型按冻结对象及跨数组不变量验证，minimum阈值/grade normalization使用既定政策且保存原CVSS版本，不增加新源/model/依赖。所有query/auth/assessment/claim/proof应同caller-ownedSession；没有caller最终identity/epoch fence不得挂公开入口。原stack旧result兼容，媒体类型opt-in另Root挂。

验收包含grade边界、missing/unknown/conflict/stale、多规则/过量/空范围、same-event binding/重复claim、真实PG当前原文与资产变化/两tenant/ACL/revoke/rollback；fixture只是unit/contract，实际PG必须Root随机nonce/OIDcomment窗。回滚只卸载producer，新类型/文档保留，不删历史/规则/研判/证据。作者只新module/tests/report，无Root App/metadata/迁移/locks/旧test/状态/评分改动；source冻结后新独立reviewer复跑。
