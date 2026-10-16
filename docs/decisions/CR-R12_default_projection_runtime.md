# CR-R12 · 默认知识变化索引入口

文档首次创建时间：2026-10-16T09:54:48+08:00
本次写作开始时间：2026-10-16T09:54:48+08:00
状态：approved_for_implementation；源码与默认运行验证 awaiting_review。
授权：用户完整有界批次、CR-R02/CR-R07 的真实投影、PG权威、受控worker与恢复要求。未改变评测分母、阈值、金标或任务范围。

原默认worker未注册knowledge_change，真实发布后只能blocked/unsupported_job_type。新增retrieval/runtime_policy.py复用HybridIndexer与现有PG租约执行器，默认consumer注册固定handler；输入只从该job绑定的PG change/outbox/tenant读取，不接受请求自报scope或任意URL。

新增HYBRID_GENERATION_ID=e5-v1与HYBRID_INDEX_NAME=dianzi_e5_v1；严格固定代际/索引名，只取服务端配置，模型维度及版本沿用E5 384维。无OpenSearch或固定官方模型缓存明确blocked/corpus_projection_not_configured。新的模型代际必须新建索引并重建，不能把既有成功任务当成新代际重建完成。

单job上限20秒，原worker软25/硬30秒不变；每次原生推理取剩余预算与10秒的较小值，索引写入/最终PG收据提交前检查deadline。未配置模型、原生超时与运行失败分别固定安全码。外部索引只能保存派生数据；查询仍经原HybridRetriever回查PG权限、当前性与epoch。原10000片段容量不放大或截断，超限/超时失败保留，不能假造empty成功。

Indexer派生收据可先于job状态提交；worker中断或租约失效后重试使用同outbox/代际幂等收据。它不提交新的业务事实或另建任务真相。当前仅接混合索引消费者，知识图谱、旧新空结果重判和推荐消费者尚未接：结果必须partial/knowledge_change_other_consumers_pending，不能声称R10/R16已完成。

兼容：旧Indexer caller未传deadline时保持原行为；旧R05单事件问答不改，旧任务、答案、事实与索引收据不覆盖。回滚移除默认handler与新增配置引用、保留派生与历史PG记录；不得用downgrade删除事实。

任务影响：R03/R10/R12/R16/R20、T07/T21/T30/T36–T38。离线装配、deadline正负例及原worker/settings回归通过；真实PG/OpenSearch/ONNX、重启/故障/并发、浏览器/live/manual尚未运行，须新独立reviewer亲复。两次本轮仪器/样式错误原日志保留，原评测合同未调整。

本次写作结束时间：2026-10-16T09:54:48+08:00
最后更新时间：2026-10-16T09:54:48+08:00
证据截止时间：2026-10-16T09:54:48+08:00

## 独立审查与修复修订 · 2026-10-16T11:02:05+08:00

首次 eebee0e 独立报告 D:/wt/r12-default-projection-review1/reports/reviews/recovery/G-D-R12-default-projection-runtime-review-1.md：92回归、31原PG/OS、8生产schema、15默认入口正负例绿；两Must分别22.843秒完整IO超20，以及public10000/tenant1先读无关分区触发SQL57014。真实红保留，不是live/正式指标通过。root修复源码8d62b54d83a3e6b56aeeb23102faa777496328db：成熟httpx.AsyncClient+asyncio.timeout完整headers/body/关闭剩余截止，同源/TLS/认证不放宽，sync保留较短配置timeout；六表ACL及目标分区SQL过滤先于原10001容量探针，逐row deadline检查，10000容量不改。原同步调用兼容、默认生产仅受控worker调用async桥；不新增依赖/事实真相，不动金标/阈值/分母。局部3contract及旧selected22/style/mypy4亲跑过，原始工具输出尚非持久run日志；由原非作者新WT重跑并封存实际证据。真实修复验证awaiting_review，不拿旧绿给新SHA背书；其他knowledge_change消费者仍partial。

修订人/root；本次追加写作结束/证据截止：2026-10-16T11:02:05+08:00。首次时间保持原样。
