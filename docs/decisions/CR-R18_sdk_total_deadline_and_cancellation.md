# CR-R18 · SDK整体截止与执行中取消

文档首次创建时间：2026-10-16T11:02:05+08:00
本次写作开始时间：2026-10-16T11:02:05+08:00
状态：approved_for_implementation；实现/独立审查未完成。
授权：本批R18/T32/T45以及已批准CR-R04/09，落实既有有限资源/完整延迟/取消语义，不削减范围或改评分。

独立实际slow-stream显示原IO timeout=.1仍约.312/.313秒完成，执行中线程只丢结果不能终止IO。现timeout_seconds/question_timeout_seconds保持IO语义及10/100默认；新增operation_deadline_seconds默认10、question_deadline_seconds默认100，合法范围(0,60]/(0,120]，bool/非有限拒绝。整体预算覆盖等待并发槽、headers、全部body及必要解析/清理；单调时钟，不以首字或提交延迟当完整响应。

采用成熟httpx.AsyncClient streaming+asyncio.timeout与任务取消，新增ask_async/check_stack_async/aclose和async context；真实stdio生命周期复用同async client。同步CLI/SDK方法保原签名/typed返回并桥接同真实网络实现，已运行loop调用sync方法要明确可用边界，不能死锁。显式旧BaseTransport测试DI因同步handler无法强杀仅保旧fixture兼容路径，必须显式标识此路径无法证明产品整体deadline/取消；默认真实网络不得进入该支路。新增AsyncBaseTransport DI用于async合同隔离，不计live。共享业务编解码保持单一严格DTO，不复制权限或另一业务真相，不改8000token/1MiB及公开工具语义。

迁移：客户端可选参数兼容旧调用；既有原测试断言/模型/REST合同不改，真实产品默认增实际预算。回滚关闭新客户端入口、保留PG历史，不修改数据库。任务影响R18/R14/R20/R21与T32/T45；需真实loopback慢headers/滴水body/排队和执行中取消、并发4、socket关闭、CLI退出、秘密错误边界及原296/3BaseException/230相关去重回归。只拿fixture绿不签产品取消。报告记录原红、真实耗时、资源关闭和未检项，冻结新非作者审查后才可有限放行。

本次写作结束时间：2026-10-16T11:02:05+08:00
最后更新时间：2026-10-16T11:02:05+08:00
