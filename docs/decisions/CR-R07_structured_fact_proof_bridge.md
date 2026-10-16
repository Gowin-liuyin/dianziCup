# CR-R07_structured_fact_proof_bridge · 结构化事实的原文支持读取

文档首次创建时间：2026-10-16T19:43:27+08:00
本次写作开始时间：2026-10-16T19:43:27+08:00
状态：approved_for_implementation；当前有界完整授权内的实现合同细化，awaiting独立首审核对。

新StructuredFactProofPort以当前认证Actor/tenant和3UUID(event/evidence/revision)读取原ClaimRecordV3+Owner路径，输出reported/partial/not_found。reported仅指来源报告值，不把unknown条件改TRUE/资产影响或安全。CVSS/EPSS/KEV必须同claimowner+assertion/evidence/path/span/hash；CWE无sameclaimowner为partial、其余五维unsupported，不从raw/兄弟claim推owner。最多8facts、原5s、有界SQL每claim证据LIMIT9(8+lookahead)，原文IO两短事务中间、父/claim/assertion/link/evidence/block/epoch有序锁二次核验当前ACL/版本。legacy SourceProof、R10四predicate门保持。

兼容性：不新表/迁移/依赖主版本/公开REST权限/金标/阈值/分母。共享公开旧DTO、raw历史、fact condition/freshness和权限不改；新内部read能力未注册时仍原not_configured，未知不默认成功。迁移无需数据重写。回滚仅撤销新adapter注入或新QA prompt配置，保留事实、任务和原审查/失败证据；不得delete历史或downgrade。主控持有公共合同与默认App入口；作者只冻结报告所列文件；本卡及原映射T卡全部切片仍需合并验收。

任务/测试影响：R07原范围与六类验收完整保留，受影响R12/R14/R17/R18消费需重新caller核查及定向回归。首次必须新非作者冻结完整source/material输入亲复offline/关键负例；PG所需read/bridge亲复实际finalSHA并测currentACL/tenant/history/conflict/statement预算/锁。QA本批0新增付费，审查后真实模型另开显式有限run并保存原请求输出和完整耗时。frontend/e2e/live/manual未执行写not_run，不用fixture顶live。无需新的用户重大授权，独审未过不记accepted。

本次写作结束/最后更新时间：2026-10-16T19:43:27+08:00；修订人/root。
