# CR-R04 · 来源写入幂等与认证提交实现补充

状态：awaiting_review；本记录落实已批准CR-R04及05 API §2，不新增权限、评分或费用决策。
首次创建/本次写作开始/结束/证据截止：2026-10-15T18:43:56+08:00
作者：/root；独立核对：/root/g_b_checkpoint_review，待固定候选复核。

## 问题和现有授权

独立8c809c4阶段审查真实复现：缺key的两前缀4次POST返回202且4不同任务；两global admin相同key共用同一任务；同一admin同key在NVD/vLLM返回202/409。05合同要求写入键必需，域包括tenant、route和主体。root额外复现提交前logout/角色改变仍被旧scope受理，原11回归8失败/3通过日志保留。

## 实现、兼容与迁移

HTTP先执行认证/CSRF，再校验可见ASCII字符1–200的必需键；错误在预约前422 invalid_key。传PG的key为固定v1域+SHA256(JSON[canonical source-collect,user_id,tenant_id,source_kind,原key])，两个/v1与/api/v1别名共享canonical域，不同来源/主体分开。请求体不提供主体/租户；客户端body/key不变。同键同body回原job，异body409。

任务创建和读取PG事务内复用lock_authenticated_scope的FOR SHARE会话/用户锁，重查global system_admin；已撤销/迁租/降权拒绝，锁后发生的修改等待事务结束。任务/事实/游标/outbox仍为PG权威，无新状态库。通用enqueue_job和worker source-next自动续页幂等键未改。

历史job_id/状态/payload/裸key不重写、不删除。旧裸key没有可证明的actor归属，不能猜测迁移为某个用户的新域；旧操作继续按已返回job_id查询，新命名域从本修复版本的新HTTP受理开始。升级时须先保存旧在途job_id并停止旧客户端未知请求的自动重投，不能承诺未知历史裸key在新域必然重放原job；来源事实/修订仍由共享writer去重。后段R20迁移演练继续核查此兼容边界，不把历史数据改成另一个用户的操作。

## 回滚

停止来源POST并保留已受理job/PG/outbox与证据；按已知job_id读取现有任务，前向修复。不得回退为缺键可写/跨主体复用，不做downgrade/删除历史，也不改通用worker租约与续页规则。

## 测试、任务与范围

R04、原T06/T07/T35的来源HTTP切片；不签原T整卡，不影响R05模型接口、R12多跳或盲测/分母。新增test_r04_source_http_idempotency_pg.py：缺/空/不可见/超长key、两主体、两来源、双前缀重放/冲突、双线程同键、初始scope后logout/角色变化共11项。原红8/3，修复2026-10-15T18:39:29+08:00至2026-10-15T18:39:41+08:00 exit0 11pass；全原unit/contract/security原60门1419pass、10明确PG另测，coverage73.71%；mypy82/Ruff通过。精确argv/起止/exit/日志：reports/runs/recovery_r05_controller_20261015/source_http_*。专项与阶段独立复验尚待新SHA。

## 独立核对登记 · 2026-10-15T19:06:14+08:00

当前状态accepted，仅本记录对既有授权的实现落实；前述awaiting_review为保留历史。新非作者/root/g_b_checkpoint_review固定1927eeb00a7e0c1335f76340b0382f46102f08f2已核对合同/兼容/迁移/回滚并独立复跑，见reports/reviews/recovery/G-B-checkpoint-review-1.md最终Ship；未新增重大决策、未削减评分/原任务。登记文档待同reviewer核对差异，业务代码未改。
