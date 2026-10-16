# CR-R16 · 持久游标签名配置

文档首次创建时间：2026-10-16T21:18:22+08:00
本次写作开始/结束时间：2026-10-16T21:18:22+08:00 / 2026-10-16T21:18:22+08:00
状态：approved_for_implementation；Root配置待新非作者审查。
授权：本批R16/T36–T38，已批准事实/任务PG权威及重启持久能力。

原CandidateDiscoveryService已要求服务端SecretStr，但默认worker未接且不能用随机进程键或模型密钥临时代替。新增可选ApplicationSettings.revalidation_cursor_signing_key，环境REVALIDATION_CURSOR_SIGNING_KEY，仅小写64hex/32bytes；未配置None意味着该能力未配置，不创建进程内新权威。生产/staging拒绝已知三种fixture键，秘密隐藏错误与序列化。真实CurrentUser DPAPI文件只存仓外，实际创建20:38:14.5941439+08，配置字段本身不证明worker使用它。

兼容/迁移：可选字段不破坏既有部署/认证会话；已签游标保持相同key重启才能继续，显式换key旧游标必须拒绝并重查，绝不回退未签游标。部署通过已有guarded秘密加载器注入，key不进job/API/日志/前端。PG事实/绑定/epochs不迁移、不改schema。回滚停用新重判入口、保留PG历史/原key，不伪造安全结果。原T最终依赖和验收未缩减。

任务/测试影响：R16默认worker/API、R20秘密/重启、T36–39；14配置边界例已经Root离线通过，服务重启/真实PG游标/secret注入/defaultfactory仍not_run，不能将字段存在签R16。Root唯一settings/config所有权，独审冻结代码后才有限放行；金标/分母/性能门不变。
