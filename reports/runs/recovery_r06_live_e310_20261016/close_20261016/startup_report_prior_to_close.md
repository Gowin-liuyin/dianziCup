# R06-live-e310-20261016 · 新固定版本受控采集段

状态 `in_progress`，startup切片实际通过；六小时live和manual `not_run`。Root仅授权本段，不是R06/R20/G-C或阶段accepted。严格CPU辅助门1.03125秒仍needs_changes。窗口不与原131秒、47秒或更旧三段拼接。

产品只读clean WT `D:/wt/r06-live-e310-20261016` 固定 `e310f7735bd499c4d9fbcefe8a644e2309a16a62`；工具固定 `44c94151840213d9e5ab7c653778d4ae3219c630`，仓外新detached部署WT `D:/dianzi-runtime-cache/r06-live-e310-run-20261016`。原三observer脚本逐blob仍等于 `1c4cce9770bfa29d08728a0131f7fc7fe714f9bc`，运行元数据observer_sha为工具SHA，二者分别记录。Root授权时间由系统clock实录2026-10-16T06:15:31+08:00；两个独立review报告与103材料manifest实际hash已匹配，详见本run authorization_and_deployment.json。原准备WT、准备manifest、产品源码、main/progress/schema/迁移/业务测试与旧日志未修改，未push。

真实collector start **2026-10-16 06:19:43.758521+08:00**，固定截止 **2026-10-16 12:19:43.758521+08:00**；最多21600秒与既有有限关闭grace（worker原lease+5且monotonic65秒，observer40秒，launcher2秒）。MinIO于06:19:20+08启动，最长8小时/原daemon截止；新owned cgroup只绑定本次RUN/GROUP，旧helper函数与原对象不变；collector end或wholeJob失败后自有MinIO watcher请求停止。额外disk guard只在Linux对象盘free<16GiB请求collector停止，不制造job成功。

旧自有Windows source actors数0，API28013/MinIO29400/frontend25176空闲，两个旧MinIO cgroup空；根boot8ee1634d-0b2e-4279-8426-2ae855e3b997、daemon17实际活着、8GiB/2CPU/2048pids未改。Windows C/D各约443/437GiB free，Linux对象盘约906GiB free；13.18GiB最坏raw另加32GiB normalized/PG空间是准备估计，明确capacity_proof=false，不能冒充完整容量证明。没有容器/镜像/卷创建删除、flushDB/global shutdown/ACL修改。

固定复用隔离DB test_dianzi_r06_catalog_live_8a_20261016，schema0016；旧baseline11 sourcejobs/74docs/74revisions/1266evidence保留。Redis DB15原owned prefix/queue只读复核，0body/0flush，沿用 `r06-live-8a-20261016:` / `r06_live_8a_20261016` 使原published queued工作可消费。唯一source producer为solo并发1 worker和默认beat；0REST来源submit，frontend/browser未启动，未用用户IAB或modelvault。

实际PID/kernel creation/parent清单及两种stop --check已通过：supervisor47464（launcher36008）、worker6412、beat48352、API10532、observer47076；MinIO Linux supervisor10925/child10928，专用minio-r06-live-e310-20261016组。完整proof在process_ownership_receipt.json和仓外stop_check.log/minio_stop_check.log，不只依据launcher退出。

API/core readiness200，PG/cache/search/worker/scheduler ready，MinIO200；真实runtimevault本地账号login200，documents200、actual source job200、logout200与随后401。首次ready断言在服务完全ready前失败，原响应状态未单存，不能补造；随后实际200。第二次checker误用没有实现的sources GET，已按固定源码读真实job。PG NULL时间参数缺类型、PID过滤误含console host、evidence完成后PowerShell重定向语法失败均限定修正仓外读取/启动检查，原失败保留；固定九脚本和运行中的应用字节未变，不改守卫/预算或服务版本。

截至status snapshot：41总sourcejobs/30本段新；状态{"succeeded": 33, "blocked": 4, "partial": 4}。九源新root和九源本段response receipt均实存；normalized source kinds为avid_community, cac_generative_ai, nist_ai_rmf, nvd_ollama, ollama_releases, osv_ollama, trailofbits_blog, vllm_vendor。arxiv失败receipt原文保留MinIO，generation0→0已核，不能涂绿。新段相对baseline实际增加{"documents": 327, "document_revisions": 342, "evidence": 96451, "source_response_receipts": 39, "fetch_attempts": 33}；旧74docs不计新增。

原首段被35秒守卫截断的Ollama job在本段attempt2实际succeeded，4.427847秒；本段10个release任务succeeded/partial，最长5.903373秒，处于原60秒lease内，partial原样保留，不称完整历史覆盖。读取九源实际选定raw对象read_verified共3463240bytes，hash/size匹配；本段新revision的96451条证据block坐标/quote hash核验invalid0，仅坐标完整性，不断言语义支持。raw bodies仓外MinIO，未写repo/log/prompt。

初验observer journal seq14、71819bytes，原replay核链通过/terminal=false；实时journal与latest仍在仓外部署WT的原observer live_r06_live_e310_restart_20261016目录。1MiB snapshot/16MiB journal/8MiB组件log/512MiB每进程/2GiB Windows总/20%CPU/1200CPU秒均未提高。

本段新342revision中publication unknown27、future0、known315/older-than-six-hours315；publication→ingested P50/P95/max为21163282.056242/70937973.082628/79490986.470688秒，保留初始历史发现分母，不计独立漏采验证。独立missed-reference与真实新发布≤6h监控仍not_run，不能把旧发布时间当新采集延迟绿。

Root预算450总sourcejobs含旧11，prestop410/唯一solo生产者最大418；3attempt/5pages/每job保守78 source+DoH HTTPS，总有限35100。response/fetch attempts不是实际wire；actual wire与source费用unknown，模型/付费provider0，not_configured不当模型验证。2026-10-16T06:28:42.360748+08:00交接时余21061.398秒；最后heartbeat累计CPU102.859375秒，余1097.140625秒。任何cap/guard/上游/退出导致提前结束均原样记录，不保证达到六小时。

Root持续控制：仓外operations/launch.ps1 status；自有Python stop_owned.py --check或不带--check申请有序停止。MinIO另用WSL python3 stop_minio.py --check核boot/cgroup；主停止之后会自动关闭MinIO。精确绝对命令在startup_handoff.json，正常停止先beat→当前worker有限结束/核tree→observer终态；ownership未知走原wholeJob失败关闭，不能保证terminal。无需新automation/chat，也不等待六小时。后续由root请求有限status与最终end/journal材料，正式六小时尚未完成。
