# R03 · 页面回执服务端指纹迁移准备

首次创建/本次写作开始/结束/最后更新时间：2026-10-15T12:30:06+08:00；root，awaiting_review/partial。

独立R03审查同page_key/count可替换entry或final标记。主控唯一schema所有者新增0012_source_page_fingerprint与request_sha256 nullableText/check，旧receipt保留NULL不猜hash，后续业务遇NULL需legacy_page_receipt_unverifiable且不执行callback/推进游标。完整新server canonical摘要输入及兼容/恢复见CR-R04-R03最新条款。

只准备schema，不声称已修业务复用或terminaljob问题。新增原0011真实receipt前向升级测试，旧key/count/NULL保存原样；空schema、0006旧claim、维度和原0011schema相关组合259passed/0fail/skip，cov61.17保持60门。命令/开始结束/退出码0/JUnit：reports/runs/recovery_r02_minio_20261015/r03_cursor_fingerprint_schema.*。单独新test_dianzi_r03_cursor_fix_20261015，未升级任何reviewer现用库，private root600仓外；已存在资料不清理。无downgrade，迁移不在API/worker启动时自动执行。该日志为schema与当时unit组合，不给后续JSON/业务修改背书。

业务后续由原实现者在root冻结迁移基底上修，原独立reviewer复核；整R03/T07/T16/G-A未accepted。
