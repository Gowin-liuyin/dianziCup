# CR-R06 · 固定公开来源集合在既有采集API和工作台的扩展

首次创建/本次写作开始/结束/冻结时间：2026-10-15T20:53:48+08:00；主控/root。状态frozen_for_implementation/awaiting_review，落实已授权CR-R06来源广度及R06/R17范围，无新重大决策/评分/权限更改。

## 小接口与文件所有权

既有POST /v1/sources/{source_kind}/collect与/api/v1同义；输入SourceCollectionRequest window_end有时区且不晚于当前、stream_kind live/backfill、max_pages1..20默认20；Cookie/CSRF/Origin/Idempotency-Key/公开system_admin且无tenant合同不变，输出既有SourceJobResponse(job_id,status,attempt_count,error_code,result_ref,created_at,finished_at)，GET /jobs/{job_id}仍读PG权威。只把原source_kind二值扩为固定九值，不接受URL、provider token、任意query、tenant或自报权限，不新增前端抓取通道/GET /sources。

固定key：nvd_ollama、vllm_vendor、osv_ollama、avid_community、ollama_releases、trailofbits_blog、arxiv_security、nist_ai_rmf、cac_generative_ai。类别/名称/来源范围以ingestion.source_catalog.CATALOG_SOURCES现有九条为准，不另建业务真相；frontend可维护相同封闭union/中文标签，但必须对齐固定合同。结构化漏洞两源共一类，九key覆盖八类，不把注册数/按钮数等于实际live覆盖。

root独占source_catalog/catalog_pages/catalog_documents/公共合同/迁移/锁；唯一后端集成人r06_legacy_migration_fixture_repair独占source_jobs/source_routes/对应新tests；r06_document_workspace在新隔离WT独占本source管理UI/客户端封闭key/直接tests，不能改后端、公共schema/全局状态/锁/进度。各自冻结后新非作者review，root集成并真实验证。

## UI效果与失败

复用已设计暗色青绿/低亮动态背景、原来源任务交互，按八类展示九个固定源及内容范围：release尚未研判、RSS仅发现/片段、arxiv摘要与全文分开、标准/政策不代表合规/资产影响。默认未取得本次PG任务结果就写未验证/未采集，不以注册成功宣称在线。用户点击单源才提交受控任务，不在渲染时批量采集；结果只显示PG任务状态/失败/partial与实际时间，不用前端计时假进度。不混真实资料与演示fixture；非管理员按既有权限隐藏/拒绝管理操作，401/403/失败后不保留错误成功提示，旧任务late response不能覆盖当前源。主要操作在窄屏和reduced-motion可完成，来源原文仍走现有已验证证据链接，不渲染HTML。

## 兼容、迁移、回滚与验收

老二key、路径、请求/响应字段、幂等/CSRF/角色不变，新key增量。沿用0015和PG游标/任务/outbox，前后端均不增加事实库或迁移；旧客户端不调用新key仍可用，缺新worker时服务真实拒绝或失败，不能UI假成功。回滚为关闭新7入口并停其受控任务，保留已存原文/历史、注册身份、游标与PG任务，不downgrade/删库。后端就绪前UI仅允许显式fixture验收，不能签integration/live。

必要检查：九key/八类一致性、原两源回归、未知key/任意URL拒绝、管理员/CSRF/角色撤销、幂等/重复/并发、HTTP失败与partial/恢复、旧页与空页、源类别/范围标签、加载/过期/空/403/503/晚到任务、1366/390/reduced-motion；最终同集成SHA真实来源→原文→PG→API→UI。原T全部映射切片、正式指标分母与门槛、人工金标/盲测原则保持。