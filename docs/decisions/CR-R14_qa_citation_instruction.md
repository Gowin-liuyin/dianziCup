# CR-R14_qa_citation_instruction · QA引用合同的模型输入说明

文档首次创建时间：2026-10-16T19:43:27+08:00
本次写作开始时间：2026-10-16T19:43:27+08:00
状态：approved_for_implementation；当前有界完整授权内的实现合同细化，awaiting独立首审核对。

仅QA generation_request补13instruction lines及prompt_version r14-qa-2：全局citations按evidence_id唯一，claims复用同citation；quote为exact连续单行覆盖所附claims，不拼原文/元数据或生成UUID/offset，不能支持则unknown。schema仍r14-qa-1/max2048/repair0；原validate_citations/Graph/Critic/Reporter不变。5885旧真实六重复引用继续被拒绝，不能去重旧输出当live成功。

兼容性：不新表/迁移/依赖主版本/公开REST权限/金标/阈值/分母。共享公开旧DTO、raw历史、fact condition/freshness和权限不改；新内部read能力未注册时仍原not_configured，未知不默认成功。迁移无需数据重写。回滚仅撤销新adapter注入或新QA prompt配置，保留事实、任务和原审查/失败证据；不得delete历史或downgrade。主控持有公共合同与默认App入口；作者只冻结报告所列文件；本卡及原映射T卡全部切片仍需合并验收。

任务/测试影响：R14原范围与六类验收完整保留，受影响R12/R14/R17/R18消费需重新caller核查及定向回归。首次必须新非作者冻结完整source/material输入亲复offline/关键负例；PG所需read/bridge亲复实际finalSHA并测currentACL/tenant/history/conflict/statement预算/锁。QA本批0新增付费，审查后真实模型另开显式有限run并保存原请求输出和完整耗时。frontend/e2e/live/manual未执行写not_run，不用fixture顶live。无需新的用户重大授权，独审未过不记accepted。

本次写作结束/最后更新时间：2026-10-16T19:43:27+08:00；修订人/root。
