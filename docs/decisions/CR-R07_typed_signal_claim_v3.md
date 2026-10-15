# R07 · 九维结构值进入版本化知识账本

落实已批准的九维富化、PG唯一事实和历史保留要求；本切片 `awaiting_review`。不改变金标、评分分母、阈值或盲测隔离，不引入新的产品范围。

## 合同与行为

`ClaimRecord` 显式增加 `schema_version=3`，只接受九个已登记谓词与对应的结构值：cvss_signal、epss_signal、kev_signal、weakness、atlas_mapping、version_assertion、literature_reference、artifact_reference、exposure_aggregate。新值不能塞入v2文本或旧score/link/version_range；v3也不接受任意文本谓词。默认仍为v2，v1/v2原记录的版本和值不被升级或改写。

候选只是来源和模型提出的结构，合法类型、引文存在、坐标或hash相等均不证明内容支持。现有发布权限、固定修订/证据、支持关系核验及model_hypothesis必须unverified的规则保持；新CVSS值增加与既有score相同的评分机构一致性检查。

PG现有 `object_json`、`value_kind`、`schema_version` 保存完整结构，无数据库迁移。v3 `object_value` 仅为旧工作台的显示摘要，超过4000个Unicode字符明确标记截断；完整结构仍由知识账本重读，原文证据可打开。不能把摘要解析回事实，不能因显示截断丢弃JSONB或原文。旧v1/v2的显示序列化不变。HTTP响应仍为原schema2，九维投影与DimensionSubmission不变。

## 兼容、迁移与回滚

先部署能读取v3的服务，再启用后续v3发布者；本批尚未接线自动作业，不把PG fixture roundtrip记为live富化。无需迁移、清空、改写已有记录或重建数据库。现有公共schema_bundle中的ClaimRecord联合扩展并保留旧分支。

未写入v3前可以回退代码；一旦出现v3数据，应关闭新发布作业并保留v3读取兼容层，不能直接回退为只识别v1/v2的旧二进制，更不能删除新事实或覆盖历史来配合回滚。后续API若需要完整结构响应，另作明确兼容扩展，不能悄悄改变display_value字段含义或长度合同。

## 任务与验证影响

涉及R07及T13/T19/T20/T22/T23/T41的账本输入，R08聚合统计复用结构；不代表这些原T卡全部完成。复用既有Pydantic判别联合、JSON Schema、SQLAlchemy事务/发布收据、权限与证据账本，不新增依赖、通用服务或迁移。

验证包含九类v3 roundtrip、谓词/版本错配拒绝、v1/v2原合同和JSON Schema一致性；真实隔离PG中新session重读、重放、跨租户/写权限拒绝、CVSS机构冲突回滚，以及大结构显示截断但完整JSONB不变。源真实性、语义支持、九维自动发布/更新重判、API/worker/UI接线及模型/live须后续独立验证，不从本切片推定通过。原始失败与修复日志均保留，实际时刻、SHA及命令见R07-core报告。
