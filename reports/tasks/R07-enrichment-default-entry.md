# R07/R03 · 默认 API 与持久 worker 接线（含 R10/R11 读入口）

文档首次创建时间：2026-10-16T06:17:27+08:00
本次写作开始/结束时间：2026-10-16T06:17:27+08:00 / 2026-10-16T06:17:27+08:00
最后更新时间与证据截止：2026-10-16T06:17:27+08:00
实际编写首次开始：历史未记录；运行命令起止以下方收据为准，不能以文档时长当编码或采集时长。
主控/实现：/root；状态 awaiting_review；整R07/R03/R10/R11 partial；新非作者review尚未发生。
已测源码SHA：1f0522e3f3fb9547ea55136efa64fc589466c992；初次 API 冻结 b18349962cb6bee251d0f1d57310366c49175239；合并已审服务/前向0019基线 3c2831b12dfc724897b5ad68f799ce0c879811ac。
已审SHA：尚无；材料提交SHA另由提交收据记录；push尚未发生。

## 用户行为和实现

默认create_application真实装入 POST /v1/events/{id}/enrichment-jobs、GET /v1/enrichment-workflows/{id} 与唯一GET /v1/jobs/{id}，/api/v1同服务别名。复用 PG会话/Origin/CSRF/事务outbox/worker executor；原来源 job reader只在独立router默认保留，默认App关闭它并使用共享job读入口。请求只可选事件版本、九维子集及ollama/vllm固定查询ID，不能自报tenant/权限/模型/密钥/URL。公开读投影不带会话hash、prompt或内部执行policy。

server配置增加三个默认false开关；凭据存在不自动许可后台生成或私有原文外发。每子任务新GenerationClient，20秒/最多1调用/1024output预算；4个模型维度拆独立PG子任务，structured本地、不适用与缺失分开。内部595服务与0017合同保持，PG task是真相，Celery结果不写另一业务状态。默认consume_job使用本地handlers副本注册固定parent/step/publication，保持原source/custom handlers，不更改主队列、25/30秒和60租约。

默认App同时复用已审PG graph 1.2与私有InventoryService路由工厂。同认证/engine，加载不联网、不create_all。真实默认HTTP验证 JSON导入201、当前与固定历史、运行时换租户后404/空列表。图样本仅CVSS，因此返回事件节点且无六类强关系边，不伪造关系。图服务六类正负证据引用独立R10报告。

修改文件见api_worker_code_freeze_receipt.json（12项）、default_readers_code_freeze_receipt.json（3项），既有0017 root合同/内部595与main已审切片需一起审查。新增代码用于真实入口、strict读DTO与执行policy接线，没有新增依赖；基础库继承main48冻结。复用为什么必要：原默认API没有富化/图/资产装配，原worker只有source handler；仅保留函数或测试调用无法完成真实任务路径。

## 实际验证与边界

最后组合：35真实PG（原执行21、API/registered consume_job9、default reader5）0fail/0error/0skip；133选定unit/contract0fail/0skip；此前相关unit/contract/security194、0017 PG20各通过。重复测试/重叠不累计成产品指标。全src128 Ruff/format/mypy通过；原整仓严格CPU门失败没有在此关闭，不声称完整全仓绿。

HTTP→注册consume_job→子任务→原子发布/重复消费not_claimed已验证，但调用在测试进程中，真实Redis/Celery worker进程 e2e未运行。关闭模型时versions被BLOCKED/model_budget_not_authorized，CVSS成功，混合发布partial；调度parent succeeded不等整workflow complete。源和模型输入为明确fixture，真实PG不计模型/source live。unit/contract/security/integration仅本切片targeted passed；frontend/browser e2e/live/manual not_run。

|收据（包含实际argv/cwd）|开始 / 结束（+08）|exit|JUnit tests/failures/errors/skipped|
|---|---|---:|---|
|[api_wiring_pg.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg.json)|2026-10-16T05:29:29+08:00 / 2026-10-16T05:29:48+08:00|1|{"tests": 6, "failures": 4, "errors": 0, "skipped": 0}|
|[api_wiring_pg_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg_v2.json)|2026-10-16T05:32:05+08:00 / 2026-10-16T05:32:14+08:00|1|{"tests": 6, "failures": 1, "errors": 0, "skipped": 0}|
|[api_wiring_pg_v3.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg_v3.json)|2026-10-16T05:34:15+08:00 / 2026-10-16T05:34:25+08:00|0|{"tests": 6, "failures": 0, "errors": 0, "skipped": 0}|
|[api_wiring_pg_v4.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg_v4.json)|2026-10-16T05:57:43+08:00 / 2026-10-16T05:57:58+08:00|1|{"tests": 8, "failures": 2, "errors": 0, "skipped": 0}|
|[api_wiring_pg_v5.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg_v5.json)|2026-10-16T05:59:19+08:00 / 2026-10-16T05:59:36+08:00|1|{"tests": 8, "failures": 1, "errors": 0, "skipped": 0}|
|[api_wiring_pg_v6.json](../runs/recovery_r07_enrichment_jobs_20261016/api_wiring_pg_v6.json)|2026-10-16T06:00:36+08:00 / 2026-10-16T06:00:53+08:00|0|{"tests": 9, "failures": 0, "errors": 0, "skipped": 0}|
|[api_worker_combined_pg_replay_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_combined_pg_replay_v2.json)|2026-10-16T06:02:03+08:00 / 2026-10-16T06:02:07+08:00|1|{"tests": 50, "failures": 0, "errors": 49, "skipped": 0}|
|[api_worker_execution_pg_v3.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_execution_pg_v3.json)|2026-10-16T06:02:34+08:00 / 2026-10-16T06:03:25+08:00|1|{"tests": 30, "failures": 1, "errors": 0, "skipped": 0}|
|[api_worker_format_final.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_format_final.json)|2026-10-16T06:01:21+08:00 / 2026-10-16T06:01:21+08:00|0|null|
|[api_worker_format_replay_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_format_replay_v2.json)|2026-10-16T06:01:54+08:00 / 2026-10-16T06:01:55+08:00|0|null|
|[api_worker_mypy_final.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_mypy_final.json)|2026-10-16T06:01:22+08:00 / 2026-10-16T06:01:30+08:00|0|null|
|[api_worker_mypy_replay_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_mypy_replay_v2.json)|2026-10-16T06:01:55+08:00 / 2026-10-16T06:01:55+08:00|0|null|
|[api_worker_nvd_artifact_recheck.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_nvd_artifact_recheck.json)|2026-10-16T06:04:03+08:00 / 2026-10-16T06:04:07+08:00|0|{"tests": 1, "failures": 0, "errors": 0, "skipped": 0}|
|[api_worker_related_final.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_related_final.json)|2026-10-16T06:01:30+08:00 / 2026-10-16T06:01:32+08:00|4|{"tests": 0, "failures": 0, "errors": 0, "skipped": 0}|
|[api_worker_related_replay_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_related_replay_v2.json)|2026-10-16T06:01:56+08:00 / 2026-10-16T06:02:02+08:00|0|{"tests": 194, "failures": 0, "errors": 0, "skipped": 0}|
|[api_worker_ruff_final.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_ruff_final.json)|2026-10-16T06:01:21+08:00 / 2026-10-16T06:01:21+08:00|0|null|
|[api_worker_ruff_replay_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/api_worker_ruff_replay_v2.json)|2026-10-16T06:01:54+08:00 / 2026-10-16T06:01:54+08:00|0|null|
|[default_entry_contract.json](../runs/recovery_r07_enrichment_jobs_20261016/default_entry_contract.json)|2026-10-16T06:15:36+08:00 / 2026-10-16T06:15:41+08:00|0|{"tests": 133, "failures": 0, "errors": 0, "skipped": 0}|
|[default_entry_format.json](../runs/recovery_r07_enrichment_jobs_20261016/default_entry_format.json)|2026-10-16T06:14:38+08:00 / 2026-10-16T06:14:38+08:00|0|null|
|[default_entry_mypy.json](../runs/recovery_r07_enrichment_jobs_20261016/default_entry_mypy.json)|2026-10-16T06:14:38+08:00 / 2026-10-16T06:14:40+08:00|0|null|
|[default_entry_pg.json](../runs/recovery_r07_enrichment_jobs_20261016/default_entry_pg.json)|2026-10-16T06:14:40+08:00 / 2026-10-16T06:15:36+08:00|0|{"tests": 35, "failures": 0, "errors": 0, "skipped": 0}|
|[default_entry_ruff.json](../runs/recovery_r07_enrichment_jobs_20261016/default_entry_ruff.json)|2026-10-16T06:14:38+08:00 / 2026-10-16T06:14:38+08:00|0|null|
|[default_readers_pg_v1.json](../runs/recovery_r07_enrichment_jobs_20261016/default_readers_pg_v1.json)|2026-10-16T06:09:41+08:00 / 2026-10-16T06:09:51+08:00|1|{"tests": 5, "failures": 2, "errors": 0, "skipped": 0}|
|[default_readers_pg_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/default_readers_pg_v2.json)|2026-10-16T06:11:25+08:00 / 2026-10-16T06:11:35+08:00|0|{"tests": 5, "failures": 0, "errors": 0, "skipped": 0}|
|[metadata_pg.json](../runs/recovery_r07_enrichment_jobs_20261016/metadata_pg.json)|2026-10-16T04:19:02+08:00 / 2026-10-16T04:19:38+08:00|0|{"tests": 17, "failures": 0, "errors": 0, "skipped": 0}|
|[metadata_policy_v2.json](../runs/recovery_r07_enrichment_jobs_20261016/metadata_policy_v2.json)|2026-10-16T04:46:40+08:00 / 2026-10-16T04:47:15+08:00|0|{"tests": 20, "failures": 0, "errors": 0, "skipped": 0}|
|[metadata_policy_v3.json](../runs/recovery_r07_enrichment_jobs_20261016/metadata_policy_v3.json)|2026-10-16T06:02:45+08:00 / 2026-10-16T06:03:12+08:00|0|{"tests": 20, "failures": 0, "errors": 0, "skipped": 0}|
|[request_green_draft.json](../runs/recovery_r07_enrichment_jobs_20261016/request_green_draft.json)|2026-10-16T03:28:57+08:00 / 2026-10-16T03:28:58+08:00|0|{"tests": 27, "failures": 0, "errors": 0, "skipped": 0}|
|[request_red_executed.json](../runs/recovery_r07_enrichment_jobs_20261016/request_red_executed.json)|2026-10-16T03:28:34+08:00 / 2026-10-16T03:28:37+08:00|2|{"tests": 1, "failures": 0, "errors": 1, "skipped": 0}|

## 问题与原红

- API早期PGv1（4fail2pass）连接search_path被默认engine固定options覆盖、测试路由计数未认识FastAPI懒include；修专用public testDB和实际OpenAPI/HTTP观测，没有改变业务事务。v2（1fail5pass）非法viewer无tenant违反既有users约束；改合法viewer/tenant角色更新。v3六PG通过。
- API worker v4（2fail6pass）/v5（1fail7pass）是新测试误把模型versions当structured且忽略来源seed已存CVSS结果；按真实四模型维合同增加独立纯成功/明确partial两场景，对负例比较不新增结果。v6九PG通过，业务算法未改。
- related_final argv误写不存在test_r01_application_settings，exit4/0cases；改实际rg发现runtime_settings，replay194通过。
- combined_pg_replay_v2（1pass49error）测试数据库run_id不匹配且metadata fixture有不同专用前缀。依原test守卫分开执行，execution/api30批29pass1fail，失败为原测试固定报告目录不存在；创建声明目录后同原失败例1pass，未改断言。metadata20通过。最后统一default_entry35全部通过。
- default reader v1两图测试错误要求CVSS生成六类非空强边，实际正常200仅eventnode；按冻结图合同改相同输入期望为空边，不增加伪事实。v2五例通过。
- 原所有红log/XML/错误收据保留。首次Ruff长行/import red见工具记录，部分早期命令没有磁盘回执写历史未记录；PowerShell串联不能作为全部退出0证据，最后每命令分别receipt验码。

## 调用链、限制与下一步

本WT prebusiness/job metadata定位继承此前root实际工具输出；新的源码索引root_api_worker_wip及最终default_entry_frozen receipt各6真实命令，source-only排秘密/holdout/cache。build_enrichment_job_service图有App与consume_job两个入口；consume_job inbound为空是Celery decorator注册静态图能力限制，源码四个固定task注册和真实调用验证补证，不将无边当未接线。

R08 available aggregate→PG事实发布尚未连接；默认policy aggregate false，无伪0。R07分类目录/输入选择7dae后续版另Agent初审，尚未本版本集成；job policy prompt/selection版本指纹与durable coverage审计需要后续前向切片，旧任务不得在新算法下重用。当前schema0017–19已有前向迁移，但不代表生产部署完成。Neo4j、source修订后整个增量重判、真实模型九维/浏览器动作与人工金标还未证明。

新增差异：CR-R07_enrichment_jobs.md、CR-R11_default_readers.md；没有改金标/阈值/分母/评测原则。新独立review需固定本候选、复跑事务/ACL/并发/中断/默认路径后才能有限登记；此报告不自行签accepted。

修订记录：2026-10-16T06:17:27+08:00 /root首次创建，记录真实成功/失败层级与未检查内容。材料manifest只封原bytes、GitLF/sourceblob分列，提交和审查不要求文档包含自身SHA。
