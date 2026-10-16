# R12 · 默认知识变化索引切片

文档首次创建时间：2026-10-16T09:54:48+08:00
本次写作开始时间：2026-10-16T09:54:48+08:00
任务状态：awaiting_review；实现：partial。不是整R12、R10、R16或G-C/G-D放行。
工作分支：codex/full-delivery-recovery。代码编写开始时间：历史未记录；候选源码SHA在冻结后登记。

本轮修改：retrieval/runtime_policy.py、indexing.py、infrastructure/settings.py、workers/runtime.py、直属unit测试及CR-R12_default_projection_runtime.md。复用现有HybridIndexer、OpenSearchCorpusClient、LocalSemanticModels、PG outbox/jobs与Celery，不新增基础设施依赖。新增小factory、限时模型适配与固定handler为默认入口/安全预算所需，未另建事实库。

问题：默认没有knowledge_change handler；配置缺失被笼统标unsupported。现在固定handler已注册，未配置仍明确阻断。完整正向默认worker→PG→OpenSearch链尚未实际验证；partial保留其他消费者缺口。原单次模型10秒若在剩余3秒开始会超总预算，已用剩余预算clip；真正原生超时/故障需独立集成复验。

实际检查：commands_fix2.json逐命令记录cwd/开始结束/exit，最后4命令exit分别[0, 0, 0, 0]；public合同28、projection/旧worker/settings 26通过，0skip；Ruff、现有backend配置mypy4源通过。此为unit/contract，不计live。旧跨test import collection exit2、初Ruff4问题及mypy未指定既有配置2import-untyped均保存，修复后的日志使用fix1/fix2后缀，未覆盖原红。

集成/security真实外部/前端/e2e/live/manual：not_run。未使用产品密钥或执行付费请求，无accuracy/recall/P95/6h指标。新schema轮询路径Must另在831c61f修复并由独立reviewer有限Ship，此处public日志不能证明本索引业务。

合同差异与回滚见正式CR。下一步：冻结源码交全新非作者review，使用隔离标记PG库、独立OpenSearch代际和官方已校验ONNX缓存复跑默认入口、失败/重放/重启与当前性；同一阶段尚有其他阻断项，不登记accepted/push。

本次写作结束时间：2026-10-16T09:54:48+08:00
最后更新时间：2026-10-16T09:54:48+08:00
证据截止时间：2026-10-16T09:54:48+08:00
