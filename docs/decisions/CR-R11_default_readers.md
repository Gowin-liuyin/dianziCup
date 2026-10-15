# CR-R10/R11/R17 · 默认应用装配共享只读服务

首次创建时间：2026-10-16T06:16:08+08:00
写作开始/结束时间：2026-10-16T06:16:08+08:00 / 2026-10-16T06:16:08+08:00
主控：/root；状态：awaiting_review。

用户已经批准真实工作台/API闭环。复用已审 graph_routes.build_graph_router 与 assets.inventory_routes.build_inventory_router，向两个工厂传入同一认证provider、PGengine，并在 /v1 与 /api/v1 注册。API 不建表、不另建用户/事实/任务状态，不接受body身份或配置。

兼容：既有认证、健康、知识、来源、问答、富化与job路由保持；只新增原工厂已经定义的路由，不改变DTO。真实schema前向0019另由已审迁移提供，App导入不会自动迁移。reader错误与原工厂401/403/404/409/503一致，viewer不因注册而获得资产权限。

回滚：移除默认factory的两组注册即可恢复入口范围，PG资料/原模块不删。前端对应菜单需显示不可用，不能保留模拟成功。

验证：默认factory真实PG5例，涵盖两套URL、未认证、图版本1.2、未知资源、JSON资产导入201、当前/固定历史读取、运行时tenant变化404及列表清空。输入为显式合成fixture，HTTP为TestClient；不计浏览器或外部live。图样本只有CVSS，六关系不在该样本得到证据，因此准确返回一个事件节点与空边；最初要求非空边的两个测试错误已保留，修正依据六类关系合同，没有伪造边或改业务。原服务六类关系的独立证据另见G-C-R10报告。

默认完整接线联合PG35例及选定契约回归日志见 reports/runs/recovery_r07_enrichment_jobs_20261016/default_entry_*；首次错误和未运行的Celery进程/浏览器/live/manual原样记录。该变更待新的非作者review，不签整R10/R11/R17或阶段。
