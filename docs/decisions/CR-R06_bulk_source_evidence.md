# CR-R06 · 来源证据有界批量持久化

状态：awaiting_review；建设范围由主控本轮任务明确授权，实施人不自行 accepted。
记录时间：2026-10-16 +08:00。基准代码：8a1b04d48346d8550f0326a77f003246a0ebbab5。

原问题：真实 616,865 字节 release 页产生 20 个文档、11,827 个块和全文证据。独立诊断两次原 handler 需要约 55 秒；每块执行六次 SQL，其中重复查修订和块的成本占据主要耗时。35 秒本地 watchdog 原失败与 60 秒有效租约同时存在，不能通过延长租约或减少原文解释为修复。

实现合同：仅新增 `knowledge/revisions.py` 的 `SourceRevisionBlock` 与 `register_source_revision_blocks`。该入口服务已完成解析的来源修订，在数据库访问前校验全部输入块的 Unicode 范围、digest、唯一 ordinal、页码与文本元数据；同一 savepoint 内锁住并核对 revision 存在、current 与精确 visibility/tenant，再使用现有 SQLAlchemy Core executemany 每批最多 500 行写入块及按需全文证据。单批最多块 5,000 / 证据 7,500 个绑定值；请求总范围由原来源响应和解析合同约束，不新增总块数门。UUID 保持独立生成，不将 parser block ID 当数据库主键。

catalog 调用登记全部块及 `supports_claim=False` 的全文证据；NVD/vendor 调用只批写原块，`_fact_submissions`、`attach_evidence_span` 与 `KnowledgeRepository.publish` 继续独立核查支持关系。不会因全文引文已登记而发布事实。既有 `add_text_block`、`attach_evidence_span` 签名、校验和调用者语义原样保留。

兼容与事务：不改 schema/迁移/公共 API/config/认证/worker executor/Celery limits/JSON limits。旧历史 revision、原文 CAS、source identity/ACL、文档锁、修订链、GC hash lock、旧论断失效、scope epoch、游标 CAS/页收据/物理 outbox 原路径不变。调用者整页 savepoint 与主事务照常提交；任何块或证据批失败会回滚全部该 helper 写入，随后原整页失败路径回滚业务页/游标。0016 response receipt 仍独立事务保留响应，CAS 的独立物理文件可能保留，仍需既有 GC 追责，不擅删文件。

影响与调用方：生产文件仅 `source_documents.py`、`catalog_documents.py`、`knowledge/revisions.py`。R02/T05 历史证据与租户用例仍调用旧逐条 API；R04 facts 的 monkeypatch 负例继续命中原函数；source_jobs 的唯一 catalog 调用保持原签名。全部调用方通过独立 backend/src CBM 和 rg 核对，tests/exports/config 未发现额外生产接线。报告记录精确结果与未检查层，不以本单签整 R06/T09/T12/T16/T07 或 E1/F1/P1/R1。

回滚：恢复三个生产文件到基准实现即可；新 helper 未引入新表或新数据格式。既有完整 PG 记录由旧版本读取，不删历史和原文，不重置游标。批量执行异常仍抛出原调用者可分类的错误；没有 on-conflict 忽略错误或伪成功。

验证合同：原逐条和 bulk 逐字段比对（关联 ID 独立生成，验证对应关系）、500/501 边界、tampered hash/duplicate ordinal 预 IO 拒绝、missing/current/跨租户、外部存储失败与任一批失败整页撤销、原回放/并发/event 更新回归。真实 raw handler 作者最多两次，fixture 空 headers 终页不证明 live 分页。作者第二次完整大页验证通过；作者没有施加原 Windows Job CPU/内存 caps，同资源性能门须由新非作者在原 caps 下核验，原阈值不变。
