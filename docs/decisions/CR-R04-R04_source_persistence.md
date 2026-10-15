# CR-R04 / R04 · 来源修订与页面读取的最小持久化合同

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:59:31+08:00。
记录者：/root。状态 awaiting_review；属于已授权R04/T05/T09/T10/T40/T41的兼容补齐，不改变评分、金标、分母或来源类别。

原缺口：原文修订只保存created_at，不能替代来源发布时间、首次观察、入库时间；文本块未保存页码或JSON路径；完整HTTP响应未被PG引用，回收可能误删。API的RevisionSummary/EvidenceResponse已冻结这些字段，本次不改其外部结构。

0013只前向增列：document_revisions按版本保存canonical_uri、source_published_at/source_modified_at/first_observed_at/ingested_at、parser_version/normalizer_version、parse_status、source_response_hash/source_json_pointer；text_blocks增加block_type/page_number/json_pointer；fetch_attempts增加response_content_hash/final_url。响应hash外键指向同一content_objects，不另建事实数据库。保存完整响应原字节；按原始JSON成员截取字节建立稳定文档修订，source_json_pointer记录成员在完整响应中的RFC6901位置，不能把重新序列化的JSON叫原始响应。API envelope的动态timestamp不应制造成员修订；原始每次响应仍留fetch_attempts引用。

旧行日期、URI、解析器、定位保持NULL，parse_status=legacy_unverified；不能从created_at或旧文件mtime推测first_observed。旧文本、Unicode坐标、修订号与is_current保持。无时区的NVD发布/修改原值保存在完整原文，归一化业务时间为None；在获得官方明确时区依据前列入无有效来源时间，不能默认为宿主时区或抓取时间。

原文引用回收必须同时检查document、revision.content_hash、revision.source_response_hash和fetch_attempts.response_content_hash。新增外键不允许丢失原文。回滚方式为停用新来源写入、保留数据并前向修复；downgrade明确拒绝，不能破坏历史证据。没有对其他独立审查使用中的数据库执行迁移。

真实验证：12:58:45–12:59:10，专用test_dianzi_r04_sources_20261015与每例隔离schema，共332通过，0失败/skip，覆盖64.69%；含旧0012修订升级不补时间、原坐标保留、完整HTTP响应两类引用阻止清理、非法parse_status/page拒绝及原T05原文历史回归。Ruff曾发现新增测试两行SQL过长，随后仅拆字符串修正；最终静态复核结果由实际日志给出。本报告不宣称API、worker、浏览器、模型链已经接通；代码冻结后须新独立审查。

读取服务冻结边界：仅GET /v1/events、/v1/events/{UUID}、/v1/evidence/{UUID}及/api/v1别名，复用api/knowledge_contracts.py，身份来自现有cookie认证上下文。SQL在PG查询阶段过滤public/同租户且具read:asset；跨租户/不存在统一404，数据库失败503不能返回空列表。分页按(first_seen_at,event_id)有界keyset，过滤参数q/product/risk_type/updated_after与cursor绑定；cursor不是授权，重新校验权限。所有嵌套revision/claim/evidence/dimension分别校验范围及来源版本，不能只校验顶层event。首次读取旧字段未知保持null/unknown/legacy，不假装在线富化。live/fixture由部署配置确定，测试注入只能明确fixture。
