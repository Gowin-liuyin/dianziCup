# Root · 批次18风险切片与实际采集续接

文档首次创建时间：2026-10-17T13:36:47.367+08:00
本次写作开始时间：2026-10-17T13:36:47.367+08:00
最后更新时间：2026-10-17T13:36:47.367+08:00
任务状态：awaiting_review；实现partial；整G-C/G-E未过门。
工作分支：codex/full-delivery-recovery；导入前Root SHA0291d197587141b9f7f5da0d01800d8cbdf58d11。

本批Root导入8125ca3已独审风险producer及9直属测试，生产源码10文件中只有保全baseline测试作正式CR修订，新REST默认入口尚未挂载。6个保全对象中新增producer精确9aa，其余5既有文件精确Root0291，PGexpired输入AST仍9aa/原Grade与权限断言保持；没有修改生产行为、金标、阈值或分母。

| 验证 | 时间（+08） | 退出码 | 实际结果 |
|---|---|---:|---|
| risk18 | 2026-10-17T11:28:31.256+08:00—2026-10-17T11:28:39.273+08:00 | 1 | 139/140 passed，fail1/error0/skip0 |
| risk18_fix1 | 2026-10-17T11:35:34.170+08:00—2026-10-17T11:35:42.652+08:00 | 0 | 140/140 passed，fail0/error0/skip0 |
| check18 | 2026-10-17T11:43:25.157+08:00—2026-10-17T11:43:25.334+08:00 | 0 | 工具检查，无测试计数 |
| types18 | 2026-10-17T13:27:49.590+08:00—2026-10-17T13:27:51.679+08:00 | 0 | 工具检查，无测试计数 |

原140中139pass/1fail未删除；CR更正后140pass是相同原用例复跑，不与139累计。Ruff10与mypy1通过。执行cwd D:/dianzi/backend，完整argv/真实限额/exit/XML见 reports/runs/recovery_reviewed_integration_20261016/reviewed_slices_batch18_*；Windows峰4–6/own0，512MiB进程/1GiBjob/2CPU/60s。复用helper回执baseline_sha仍带历史972636、source_hashes为旧两workflow文件，不能把它们当risk源码证明；本批qualified标签明确Root0291，风险10实际raw由reviewed_batch18_risk_import.json、root_batch18_conservation_baseline_change.json和新的risk_source_manifest.json绑定。未改写旧回执。

Producer原合格13PG是9aa/8125源的限定证据，本批Root默认risk route、真实PG、browser/e2e/live/manual尚未run。新独审必须固定本批实际commit/source manifest；Root不自签accepted。

实际Source独立product912d8b3与COREaf639/OPS6b775，第四启动13:17:46.640400+08硬截止19:17:46.640400+08；worker/beat实际出生标识匹配与alive已有原回执。任务计数不是成功采集数，费用与wire仍unknown，六小时formal=false。旧三次失败、CPU与42/450ledger原件保留。代码编写/文档/测试/采集墙钟分别记，不合并不同产品版本窗口。

并行：R16/17指定集成App变化入口、R18新risk route、R12新87a问答与1bb仅fixture资源修+全新review、R10新e8dfasync/DNS+新review、R20空库恢复准备、PG共享控制prepare；R14五生产adapter适配唯一workflow/runtime owner。每个WT独立，Root中央schema/锁/状态/Git/push/秘密唯一。CBM按≤45秒串行独立scope，业务实现不因此串行；实际PG2target+sampler1逐窗Root独占。

复用风险producer已存Assessment/KnowledgeReadService、现有成熟native监督器和原PG控制；新risk路由必要用于默认产品接线，task publication与role adapters补真实未配置能力，不新增万能框架。当前限制：完整Agent/多跳/历史/恢复/正式金标/浏览器全链尚未验；人工gold0/授权资产仍外部缺口；G-C及后续阶段未放行，无新阶段push。用户3个修改与未知output均不stage。

下一：独审当前风险保全更正与集成冻结；QA19/R10policy4/R16 PG13＋新default2实际隔离；默认API/worker/UI挂完整已审业务；持续采集观察实际逐Source成败与发布时效，原60T要求不删。

本次写作结束时间：2026-10-17T13:36:47.369+08:00
