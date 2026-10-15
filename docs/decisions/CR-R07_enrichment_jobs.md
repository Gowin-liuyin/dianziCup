# CR-R07 · 九维异步任务与真实调用轨迹

状态：awaiting_review。本变更实现已批准R07九维与R03持久任务目标，不削减原T卡、评分或盲测。

## 输入输出与权限

新增POST `/v1/events/{event_id}/enrichment-jobs`接收expected_event_version、
dimensions（默认九维、明确子集不扩展）、product_query_id（仅ollama/vllm或未知）。
不接收tenant、role、模型名、密钥或自报egress授权；会话、Origin/CSRF及Idempotency-Key沿用05合同。
公共事件写入须公共管理员，私有事件须现有WRITE_ASSET，身份来自认证上下文；
分析员的资产写权限合同冲突另在R11处理，不能在此悄然增加权限。

202返回调度父job和workflow标识；GET工作流明确区分调度完成与九维完成。
子任务状态只读PG job_runs，不按动画计进度。默认仍九维；未知产品查询不发送测绘请求，
暴露维度明确unknown/blocked，不用零或资产受影响数量替代服务统计。

## 有界执行与持久化

父任务冻结实际事件/原文版本再产生逐维子任务。每个模型子任务最多一次wirecall、
默认1024输出、客户端20秒，与现有Celery 25/30秒边界协调；四模型默认总4096。
模型失败与未验证候选保留原状态。租约丢失/版本变化不发布半写结果。
外部模型调用前独立PG记录预约，调用后保留实际provider/model/token/时间/hash；
未知费用unknown，worker中断且无回执记incomplete_interrupted，不重发付费请求假装幂等。
任何新独立事务不得等待handler持有的job/原文锁；metadata预创建、预约只更新自己的元数据。

PG job_runs是任务状态权威；enrichment_results/claims仍为事实权威。
新工作流和调用元数据仅保存关系、不可变请求与轨迹，不复制另一套业务状态或事实。
请求之外另冻结服务器execution policy及hash、actor permission_version；provider/approved model、
generation/aggregate开关与private egress均不从用户body取得。执行时当前配置、权限或会话不符
原快照就阻断，不能复用旧幂等键悄悄换模型或扩大权限；凭据与其hash不写policy。
exposure两个provider使用独立20秒子步骤，再由最终发布汇合成逻辑一个维度；物理子job
数量可以多于九，前端仍明确九维状态，不能将调度父任务成功当全部维度成功。
原会话hash用于执行时撤销/过期/当前角色复查，原token、CSRF、密钥不写job payload或公开响应。

## 兼容、迁移与回滚

计划0017增加工作流/子任务元数据，两表与既有job/事实关联；原来源任务、问答与维度读格式不改。
认证会话不做可破坏历史的外键；原文、资产明细和model prompt不写公开轨迹。
前向迁移只建新表/索引，不downgrade删除调用证据。回滚接线可停止新调度，
已有job/事实与费用轨迹保留，未完成工作流不能包装完成。
新增REST与实际worker handler须同批接到app/runtime并独立审查，只有定义不算产品验收。

## 验收影响

R07/R03/T07/T18/T19/T20/T35/T41能力切片。覆盖严格输入/九维不遗漏、
租户与当前角色、撤权/重放/幂等冲突、真实PG+默认worker、每维预算/部分失败/费用轨迹、
重启与任务接管。fixture只unit/contract，真实模型/source/browser另分live/e2e；
模型候选仍不可进入supported事实或强边，引用存在不当作内容支持。

首次创建的实际写作时间将由任务报告绑定；此前编写时长未完整记录，不依mtime补写。
