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

## 2026-10-17T00:31:04+08:00 · 本次执行内的 VerifiedContentReuse 与调用方兼容

本次写作开始时间：2026-10-17T00:31:04+08:00
授权记录：主控已在本批派单冻结以下内部边界，消费者新非作者须核 source d550c8232b5e8b46550941c513db5aba04078308；公共端口 968c71b6 的四参数/None 兼容签字不代签消费者。

使用私有 frozen JobExecutionResult 子类携带本次真实 verified bytes/proof，不改共同端口，不建 global job/cache map。证明绑定 job/worker/attempt/tenant/精确 Actor/request SHA。handler 必须通过原 AssessmentService.read 与 ContentStorage.read_verified/原 SHA 检查取得真实原文；冻结只读 Mapping 和不可变 bytes 后，final guard 仅重放同 hash 字节、复用原 load_rule_inputs 算法重建全部当前 PG 证据、权限和语义，再比 input_digest/epoch/rule fingerprint/asset snapshot。缺 hash、新 hash、错 context、停止或超限明确 blocked/partial，不回读外部 MinIO、不用 None 假 store、不用 PG metadata 代替原文。该证明只是此 attempt 的内容寻址观测，不跨重启或成为另一套事实权威；lease 丢失未调用 guard 时随执行结果释放。

去重缓存总上限 64MiB，沿原 R11 每对象 2MiB/每规则 8MiB 较低限；新 hash IO 前核 PG size 与缓存总预算，最多本页 100×20 次有界引用读取。超限 explicit partial/verification_budget_exhausted，不改变原 page/model/tool/评分分母。read-only 重放 store 的 store/delete 拒绝；原文 bytes 不经 repr、JSON、日志或公开结果输出，不声明外部对象存储掉电/篡改恢复已证明。

依赖读取提取同原 actor owner/digest 的无依赖 job FOR UPDATE 路径，保留实时 credential/scope 校验、读后重读状态与 immutable binding 校验；当前执行 job 的 lease/guard 事务锁完整保留。此举避免 continuation B→completion C 与执行 C→parent B 的 job 锁环，不能放松 ACL。

既有 test_page_budget_preserves_blocked_owned_continuation 的一处实现指针按新不可变父 completion 引用解析 manifest.next_page_job_id 后，仍精确检查原 continuation blocked/cursor/not_claimed。原完整字节和初红归档，不改变 two-types 或其他 Oracle。原 drive outcomes 只允许 succeeded/partial 的另一个调用方尚未真实验证，新增 retry_wait 可能触发；保留原断言，必须先实际复现，再精确协调原 harness 的重试驱动，不用排序/删样本规避。

验证新增范围：真实字节与 tamper/缺 hash/size、缓存边界/不跨生命周期、repr/日志边界、同 job 重放/lease 丢失/owner/actor/source 变化、旧/新/空 cohort、continuation 与真实 PG 并发/晚到。作者 194 离线/85 新只是自检，三 PG 仅 collect；新独审前不得 accepted 或称完整 R16。回滚关闭新 completion 生产，保留 PG 历史与旧请求/父结果；无表或公共 schema 迁移。

本次写作结束时间：2026-10-17T00:31:04+08:00
