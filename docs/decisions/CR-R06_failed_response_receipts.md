# R06 · 收到的来源响应在解析失败后留证

创建时间：2026-10-16T00:37:26+08:00；状态awaiting_review。这是落实已批准R06来源原文/失败审计和PG唯一权威的内部合同，不减评分、原T验收或live要求。

当前真实触发：HTTP原body在normalize_catalog_page之前尚未持久；解析抛错后source task事务回滚，arxiv失败原文无法重读。旧fetch_attempts/source registration/source cursor受同一业务事务与FK锁影响，首次注册未提交及job FOR UPDATE使另一session复用旧表可能等待/死锁。

新增0016_source_response_receipts，down_revision0015，只新增表/索引，无旧事实重写。job/source身份无FK以避尚未提交注册与作业锁；service必须用已提交PG job context核对jobtype、public租户、attempt、payload里的固定source_kind/stream/window，身份不得来自外部模型/请求体自报。response_content_hash有FK content_objects，独立事务对content hash加原锁、store写与hash/size读回核验、登记content_objects/receipt，commit成功才进入normalize。job/cursor/document事实仍由原业务事务；receipt不代表采集成功。

receipt键绑定job_id/attempt_count/response_ordinal(1..2)，记录固定source_kind/source_id/stream/window、cursor与请求SHA、真实observed、HTTP状态、固定MIME、原文hash/size≤5242880及安全错误码。不存完整URL/header/正文/凭据/私有资产。源响应5MiB与现有NetworkPolicy/source_documents一致。HTTP200真实空body允许真实空hash；无body网络/HTTP失败不造对象。

parse_outcome四态received/normalized/normalization_failed/transport_failed。normalized仅解析成功，不能计文档落库/任务成功；失败须固定错误码，normalized不带错误码；normalized/normalization_failed须HTTP200和真实bodyhash，transport_failed无body。nullable hash/size必须同时空或同时存在，显式IS NOT NULL消除PG CHECK三值逻辑漏洞。

知识GC新增receipt引用计数；现有DELETE-before-store/FK异常机制继续保护内容，禁止清理已有raw/失败/历史。只允许系统管理scope从固定服务读取公开来源receipt，API暴露由后续主控统一合同，不公开任意读取。

迁移：先备份/确认任务专用库，服务暂停相关写入后向前执行0016，再部署接线代码；不得升级旧1927 collector库/把不同版本窗拼起来。重启PG后原对象/receipt可读。回滚：关新source handler写入、保留0016表/读层/原对象，用前向修复或已验证备份恢复；downgrade显式拒绝，不删审计历史。

任务/测试影响：R06/T08/T49原文与失败留证；原成功页游标合同不变。必须覆盖解析失败独立commit、PG业务rollback、storage failure不推进、收据写失败不进入parse、重复与并发、AVID tree/blob各次序、public管理员边界与敏感字段不落盘、真实PG表/模型一致及GC拒删、进程重启再读。当前schema准备片静态检查通过，真实PG/业务接线由实现包及新独立review补齐，不能单独验收整R06或G-C。

2026-10-16T00:39:47+08:00 真实0016迁移首次26setup错误由实现者发现，root生成显式SQL源码时类型名替换顺序把BigInteger误写成Bigsa.Integer。src-only mypy未覆盖migration升级函数，不能称迁移已验证；原日志保留，最小改为sa.BigInteger并补独立migration mypy/真实PG升级复验。
