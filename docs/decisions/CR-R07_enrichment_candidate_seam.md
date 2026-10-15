# R07 · 九维候选与逐维尝试接口

落实已批准九维、PG唯一事实、候选与支持事实分离、未知不等于否定；不新增评分口径、不减原T验收。此记录与实现均awaiting_review，不能替代R07最终验收。

新增内部domain/enrichment_values与enrichment/contracts，九类受限值、服务端上下文、固定修订/块、相对块quote坐标与hash、逐维尝试状态。DimensionName移到领域层统一来源；API knowledge_contracts显式再导出、PG DimensionSubmission引用同一Literal，九个值及现有JSON投影不变。引用坐标在最终发布时加永久TextBlock.start_offset转为原fulltext_unicode_v1；结构/hash匹配不是内容支持，候选不含可自填supports_claim/human_confirmed。

现有ClaimRecord v1/v2、公共HTTP schema2和数据库未变。新九类值本切片只用于内部候选；接入Claim JSONB时由唯一集成人补有版本的受限谓词映射、schema导出与旧记录读取回归，再进行真实发布。不能把候选json塞进旧文本值或metadata冒称已落库。当前没有生产调用/新worker；这一接口冻结只是供A/B在同基线并行，不代表已接线的产品效果。

兼容：旧API九维Literal与DimensionSubmission输出schema逐字比较；旧引用、状态/权限与CVSS链保持。需要类型同一处命名，避免两Agent发明不同词汇。旧dimensions.py六维fixture辅助仍保留，但新作业不得用其旧kind矩阵。

迁移：本切片无schema/依赖/锁/环境迁移。回滚可删除尚未接线的新模块并恢复两个类型import，既有PG事实与历史不动；一旦后续新谓词真实写入，须按后续版本合同兼容读取，不得用此无数据回滚说明删除事实。

测试：九维typed roundtrip、错维值、缺scope/time的not_found、失败原因、重复同值不构成冲突、未知时间与真实0、禁止资产明细/PoC运行成功、bool/NaN、错误hash/坐标/重复块、partial正文标记；原R02值/维度与只读投影回归。API/PG两个既有模型schema与固定1156旧版本比较。候选的真实块身份/语义/权限/最新版本由后续验证/发布服务做，不能仅靠类型通过发布。

影响：R07:T13/T19/T20/T22/T23/T41的内部接口；R08复用aggregate值；R09/R10/R11最终能力仍保留。A只返回信号候选/请求计划，B只返回字段/模型候选并验证，root独占PG发布/作业/公共DTO/迁移。新基线记录、实际时刻与命令见R07-core报告。官方阈值、金标、分母、盲测隔离无变化。
