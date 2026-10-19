# CR-R12 · 失败模型调用保留输入预算审计

文档首次创建时间：2026-10-17T13:41:23.022+08:00
本次写作开始时间：2026-10-17T13:41:23.022+08:00
状态：approved_for_implementation，独审须核对修复，不升级整卡。

新非作者对87a/1bb实际GenerationClient fixture故障两次attempt确认：成功路径持久化prepared generation_input_bytes/generation_budget/token_counter_version，_record_failure丢失这三种已计算安全输入审计；attempt正文digest不足以证明输入UTF8/可信token计量预算。原红probe及计数保留。

授权最小内部修复仅传入既有准备阶段的准确UTF8尺寸、安全token budget proof和counter version给failure trace metadata，成功/失败都保留；名称/状态明确prepared而不是实际上线sent。未到模型准备阶段或counter未配置记缺失/unknown，不能伪token。真实AttemptMetadata/传输尝试/provider usage/unknown费用保留，不能用prepared充计费。无正文、秘密、私有资产明细进入公共日志。

不改公开DTO、model费用事实、原模型call/repair次数、预算上限、金标、阈值或分母，无DB迁移（既有JSONmetadata内补安全键）。兼容旧trace读取字段optional不回填假数据；回滚可恢复旧内部写法并保留缺口，不能称已验。必要测试：原红sameoracle、准备前失败/counter unavailable/部分success后critic fail/attemptunknown、正常旧317相关回归；fixture不计live，真实PGtrace落库必须后续检验。只原作者改runtime及直属tests，新固定SHA交非作者定向复核。

本次写作结束时间：2026-10-17T13:41:23.022+08:00
