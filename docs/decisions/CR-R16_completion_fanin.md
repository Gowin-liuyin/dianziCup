# CR-R16 · 不覆盖历史的重判任务汇总与原子完成

文档首次创建时间：2026-10-16T23:46:47+08:00
本次写作开始时间：2026-10-16T23:46:47+08:00
状态：approved_for_implementation；公共端口与消费者分别由新非作者审查后生效。

授权依据：R03 持久任务与事务、R16 变化重判和历史不覆盖。本变更只补内部接口，不改公共 schema、原两个可信 job 类型、评分、金标、分母或模型/工具预算。整 R16 的 negative watch、历史查询、推荐撤回仍需单独实现与验收。

DetachedJobHandler 增加服务器固定的可选 completion_guard，类型为 Callable[[Session, JobExecutionContext, bytes, JobExecutionResult], None] | None，默认 None。Detached 返回后，在最终 fresh Session.begin 中先校验 expected_attempt 的租约，再调用固定 guard，最后通过原 complete_job 与新的 clock 校验提交。guard 不能由 payload 选择，不做外部 IO；分类错误沿既有 fresh 事务重试/blocked，租约失效不运行 guard。None 保持旧构造兼容。R16 guard 在这同一事务按既有锁顺序核 owner、scope epoch、规则 fingerprint、资产快照及结果有效性，防止检查与完成之间的变化竞态。

复用内部 revalidate_change/既有 owner binding，RevalidationChangeRequest 新增可选 fan_in manifest，None 保持旧路径。manifest 固定 parent_job_id、唯一 child_job_ids（最多 100）、next_page_job_id（可空）、非分页缺口原因、effective_epoch 与 remaining_checks（严格 1..10）。只使用 enqueue 返回的实际 ID，核同 owner/change/cutoff/cohort；请求不能自授 scope 或改预算。

原调度父在同事务固定指向首 completion job 后终态 partial 保留；不得升级、移动 result_ref 或改写旧任务/研判历史。completion 自身保存新的汇总结论，用同一个 job 的现有 retry/outbox/退避等待孩子，max_attempts 对应固定检查上限；最后 attempt 仍 pending 时明确 partial/budget_exhausted，不能将等待解释为否定或安全。continuation 的 partial 调度只有通过固定、同 cohort 的 completion 引用才可读取其实际完成状态，禁止任意引用、循环或无界遍历。

原 signed cursor 仍按 requested_epoch 工作；续页 request 保留 requested_epoch 与原 frozen map/fingerprint/cutoff，manifest 和已执行孩子使用单独 effective_epoch。requested 可以小于等于 effective，但 continuation 实际计划/汇总及所有孩子必须同一 effective，最终与当前 epoch 再核验。不重新签输入、从头 restart、重置分页预算或重复计分；不得仅因原请求较旧就判无效，也不得把旧目标自动当当前结果。

只有全部本页孩子与 continuation 已完成、无计划缺口、目标仍有效，新的 completion 才可 succeeded。缺失、失败、blocked、cancelled、未知、超预算分别保留明确状态；晚到聚合不能覆盖较新事实。现 AssessmentService 负责四态与原结果语义，汇总不另写判断算法。

兼容/迁移/回滚：无新增表、无 downgrade，不改原两个 factory 类型；旧 handler 默认 None、旧 request 默认 fan_in=None。关闭新汇总生产并按各自版本处理活动 completion，保留所有 PG 历史。共同 executor.py 由唯一指定作者实现，R16 作者只写 revalidation 消费者；Root 负责两个冻结源的组合与默认入口独审。

测试影响：R03/R16/R20 的租约变化、guard rollback/重试、None 兼容、重放/并发、父历史不变、孩子归属/continuation 循环、分页 coalescing、预算耗尽和目标变化竞态必须验证；原 two-types Oracle 不改。unit/contract/integration/security/frontend/e2e/live/manual 分层，实际 PG 未执行前不得判通过。

本次写作结束时间：2026-10-16T23:46:47+08:00
