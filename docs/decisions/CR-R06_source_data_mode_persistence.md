# CR-R06 · 来源模式进入不可变原文修订

文档首次创建时间：2026-10-16T23:31:37+08:00
本次写作开始时间：2026-10-16T23:31:37+08:00
状态：approved_for_implementation；新非作者核对默认 worker 与 PG 证据后生效。

授权依据：R06 真实来源与 fixture 隔离、R18 公开读取必须如实展示来源模式，以及 PostgreSQL 原文历史不覆盖的不变量。源候选 a3e918ac268fa4a7dcddd89a849ec406faf331b8，材料 32c432a12ff2cc361036288f67ef1cc3d65627b2。公共 schema、来源类别、评分分母和预算保持。

SourceResponse 增加向后兼容的可选 data_mode，仅接受 live/fixture/None。来源 handler 从服务器 SourceSettings 注入可信模式；请求体和外部文档不能自行声明或覆盖可信模式。输入先校验，再做外部 IO。两条持久化路径统一写 revision_metadata，可信模式带 data_mode_policy_version=trusted-source-runtime-v1。目录原文 metadata 中同名外部字段先去除，其他解析/标题/时间字段保持。

复用现有 save_document_revision 的 metadata 比较：同内容同模式幂等；unknown→known、known→unknown 或 live↔fixture 均产生新修订，不原地更改旧 metadata。None 也以明确空 metadata 参与比较，防止旧 live 标签被错误复用。原文内容、历史事实与旧结论保持。没有新表/迁移，不为旧历史批量补 live 标签；旧模式未知的公开读取仍保留缺口，新的真实采集才能形成可信模式证据。

兼容与回滚：旧调用方默认 None；未配置模式不能伪装 live。回滚停止新增模式注入并恢复旧入口，保留已经写入的修订和历史，不执行 downgrade 或删除原文。影响 R06/R18/R20 的两类持久化、共享调用方及默认 worker；Root 唯一修改 workers/runtime.py 的 data_mode=source_settings.data_mode，必须在新冻结候选验证。

测试影响：来源模式校验、外部字段伪造、同内容模式变化、幂等与保存失败后的游标/事务回滚均需测试。作者 386 离线与七 PG 通过，未改文件的额外 strict 红和初始 fixture 红保留。目录既有解析 normalized 回执早于最终 PG 保存，不能把它当数据库提交成功；来源 job/游标仍需核验。真实来源 HTTP、默认 worker 和浏览器分层记录，不把 fixture 当 live。

本次写作结束时间：2026-10-16T23:33:40+08:00

修订记录：2026-10-16T23:33:40+08:00；按本轮工具实际 UTC 时钟纠正初稿误填的未来时间，开始时间依据首次写作工具时间。
