# Root · 批次13读服务与更新整合 checkpoint

文档首次创建时间：2026-10-17T02:36:46+08:00
本次写作开始/结束时间：2026-10-17T02:36:46+08:00 / 2026-10-17T02:36:46+08:00
最后更新时间与证据截止时间：2026-10-17T02:36:46+08:00
基线：9726363e0d9b33467ba40a06a8bde9548b46bccf
工作分支：codex/full-delivery-recovery
状态：awaiting_review；实现partial；不是阶段验收，不push。

完整导入R14 0114779a、R07 ca17917f、R18 c18cd5ea、R16 ccbdf7eb共40个冻结文件，逐文件原始SHA核对。默认App新增四个公开读取路由的服务器装配，保持原认证服务；复用原reader、持久任务、源码证明与fan-in，不新增依赖。三个原R18 PG helper以233339be冻结Git blob完整保留，未改原Oracle。

Root真实验证：read_proofs_batch13 442/442、public_producer_batch13_fix1 107/107（与前组重叠5）、fanin_batch13 105/105，失败/错误/skip均0，649 distinct离线案例。配置mypy193文件通过；13个相关源码Ruff通过。各命令、实际开始结束、退出码、PID/birth与残余在同run对应.command.json；普通峰值6/7，残余0。PG/integration/frontend/e2e/live/manual本checkpoint均not_run；作者较早的PG结果不替代新默认集成运行。

原失败历史保留：Root新增mount测试最初把既有{source_kind}误写{source_id}，106pass/1fail；修正新增测试后107pass。App新增import首轮Ruff I001，修复后通过。原forward head两个0019/0026断言与实际0030不一致仍未关闭，未改阈值、skip或原断言。普通unit使用显式fixture/no-cov，不计live或正式覆盖率门。

当前关键缺口：修订真实mode误标、SourceEnricher报告未接线与实际UTF-8输出预算、真实默认业务/浏览器链、public typed task仍503、graph_apply未默认注册。两份CR-R06_revision_mode_read_projection/CR-R14_source_report_output_accounting只批准实施，尚未验收。六小时持续采集未启动，G-C仍in_progress/partial。任务T最终合并验收不因本checkpoint变化。

索引：Root-batch13-index.md冻结224py树3df28309，193source/2924nodes/17369edges/0解析缺口。之后App仅import排序改变，索引旧hash不冒充新树；新批review要再刷新。源码/rg及实际测试交叉核对SourceReport无默认消费者、graph_apply未注册、final fan-in guard已真实接线。

并行：R01独立修复自建engine释放；R06作者/独审处理启动与停机guard；R10独立图默认消费者；R19独立标注工具整合；R20独立终态竞态修复。新CR实施与Root业务review从本checkpoint滚动派发。文件所有权见progress/recovery_workstreams.md；Root唯一集成/提交/push负责人。

用户原frontend/tsconfig.tsbuildinfo哈希验证不变且不stage；原push台账不纳入本checkpoint。人工双标/裁决、授权资产范围与CNNVD登录仍未取得；正式评测/金标未运行，不记通过。当前复用的新增reader/proof/fan-in代码是已冻结真实行为接线必要组件，公开DTO、migration/lock/评分分母均未改变；整卡限制见上述缺口。

本地原始日志保留在reports/runs/recovery_reviewed_integration_20261016。本次checkpoint携带源码、合同与小验证收据，较大原始日志的完整材料提交另行进行，不伪称已远端上传。
