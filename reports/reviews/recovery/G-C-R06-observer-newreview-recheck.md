# R06 / R20 观察器修复 1 独立定向复核

What this change does: 新V2仅记录PG的安全观察投影，将opaque游标改为摘要和长度，给完整record建立哈希链，并把过大的delta转成完整snapshot。原三项Must已关闭；没有发现阻断此离线观察器切片的剩余问题。

结论：**限定 Ship：观察器离线准备/安全投影/容量与回放恢复切片。** 本报告不签整R06/R20/R22、原T卡或G-C，不写accepted，不授权live启动。作者状态仍为awaiting_review，root依据本证据登记。integration/security/frontend/e2e/live/manual六层均not_run。

本轮独立短工作树 `D:/wt/r06-recheck`、分支 `codex/r06-recheck`，初始clean，从补充材料 `b08824f738ca185776916ae02689d8507f956c5c` 创建。代码冻结 `1c4cce9770bfa29d08728a0131f7fc7fe714f9bc`，主材料 `521b740612b2d0465f2be50cd58b5028f1c820b7`，修复前材料6957/代码fc6；产品源调用链基线349c。时间为2026-10-16+08:00，本轮命令03:18起读取，首轮03:21:04→03:27:15；最终自有锁定环境03:32:22→03:35:58。完整argv、cwd、SHA、开始/结束、退出码和raw log hash保存于自有 `reports/runs/recovery_r06_observer_newreview_recheck_20261016/*_receipt.json`。

沿用已读Ponytail Review 5.2.0；重新核AGENTS、00执行图、R06/R20/R22合同和冻结状态/交接、V2合同/接入材料、作者fix1报告、修改diff和直接测试。原T16/T45/T52/T54及04/06/09合同的最终门不变。只写本新报告和自有run；未改业务、作者源码/测试、旧报告/材料、progress/公共合同/root运行材料；没有spawn、commit、push、读环境凭据、PG/外网/来源请求、付费接口或产品服务启动。作者WT只读status复核为clean。

## 原阻断关闭证据

| 原项 | 独立复核结果 |
|---|---|
| Must1：writer成功写出1132124B delta但reader只能读1056769B | 原998098B合法snapshot、全身份替换和九cursor变化原样保留。新记录kind=snapshot，998750B，replay状态一致；新增测试验证新segment恢复与terminal。snapshot≤1048576B、record≤1056768B含LF、总16777216B均未涨。writer与reader现在统一边界，delta大于snapshot时也直接用较小完整记录。 |
| Must2：opaque URL/key值落盘 | page_token和after仅保留独立核算的SHA256/UTF-8长度，PG操作游标和产品token规则未改。原URL/api_key canary、after canary、changed token、heartbeat、restart和terminal均未含原值；元数据严格投影，非法值错误不回显。追加2048B边界两型均保持精确摘要，2049B写前拒绝；不通过秘密正则猜业务token。 |
| Must3：损坏segment/墙钟/reason仍被replay接受 | 每record严格schema/key/type/SHA/run/segment/seq/已知时区/非倒退墙钟、gap及reason；完整metadata/payload的record hash链接上一条。原4个篡改均拒绝，新10测试含重新算hash仍非法的类型/时区/时序/段/receipt反例。追加embedded snapshot时间不一致、重算record hash但错误prev link、复用已出现segment均拒绝且原字节保留。正常latest崩溃后terminal=false、新segment完整snapshot/gap可恢复；terminal已写而receipt缺失则明确标缺收据且不能续写。 |
| Should4：报告CRLF工作树hash与LF固定Git blob不一致 | 新manifest分别列Git blob OID/content hash和working-tree hash/bytes，150/150固定树OID、blob内容与工作树按声明核验通过。原报告唯一CRLF/LF差异明确保留，fix1报告精确raw属性生效，没有改旧manifest伪造35/35。 |

摘要链用于发现意外损坏及定位版本，**没有对全权限改写者提供认证或不可伪造承诺**。旧V1 journal在V2下拒绝原文件续写；没有将旧记录补写成新版或将不同schema/segment拼成连续时长。

## 逐观察点与实际测试

原审查manifest本体 `adef785ee9fbb5f3783945af095327ff455a4e8f3941a6a6de8e9a27c415ae37` 实核，116个原审查产物hash均未变。原脚本 `b0a8efd6a520f16b91bcf807f62c1570127d94ac142aeeb3abc35488a50b4f8e` 与留存txt逐字节相等。独立加载其原函数执行20个点；legacy点用本审查独立排序、投影、折叠和SHA计算替换旧业务token相等期待，未调用作者的投影helper生成期望。原21名字、顺序和分母全部核对，不删除/skip；完整旧/新期待与结果在 `independent21_mapping.json`。

| 点 | 原可观察要求 | 复核 |
|---|---|---|
| 1 | 369旧轮次独立重建 | 369安全公共投影/独立opaque摘要一致；root批准迁移，不再声称操作token原样恢复 |
| 2 | 新segment没有snapshot/gap | 拒绝 |
| 3 | gap类型错误 | 拒绝 |
| 4 | terminal reason与同目录receipt不同 | 拒绝 |
| 5 | recorded_at=NULL | 拒绝 |
| 6 | 非法source metadata六种插入顺序 | 固定ObservationError，无输入回显 |
| 7 | 可打印URL/key游标canary | 产品形状合法值可接收，但原值不落盘；原隐私断言保留，安全投影取代“只可拒绝”的文字期待 |
| 8 | 缺observed_at | 拒绝 |
| 9 | 缺jobs | 拒绝 |
| 10 | 缺cursors | 拒绝 |
| 11 | 缺fetches | 拒绝 |
| 12 | 缺source_summary | 拒绝 |
| 13 | 缺page_receipts | 拒绝 |
| 14 | 缺publication_time_quality | 拒绝 |
| 15 | 缺counts | 拒绝 |
| 16 | 缺publication_statistics_scope | 拒绝 |
| 17 | 缺empty_result_means_safe | 拒绝 |
| 18 | 最后半行恢复 | 拒绝且原字节不变 |
| 19 | 入口预算终止 | 正常返回，reason=observation_log_budget，完整terminal；不能把exit0当足时通过 |
| 20 | 完整main缺gate | 环境不可读取、engine调用0，拒绝 |
| 21 | 合法最大delta可重建 | full fallback后状态一致；其新segment恢复另由新增测试实跑 |

原21的15符合/6失败raw仍保留；本轮独立21/21符合，0failed/skip。不是把作者“21pass”直接签字。原22个test名称18+4一一保留，100/1000轮两段合成时钟改为单调秒，符合新增真实记录时序合同；轮数、数据量、失败保留、容量门和评分分母没有降低。

首轮只读复用既有 `D:/dianzi/backend/.venv/Scripts/python.exe -B`，其32/21/8结果与日志保留。为严格满足自有锁定环境，复制当前backend的pyproject.toml和uv.lock到本run/runtime_env，实际执行 `uv sync --frozen --offline --no-config --no-python-downloads --no-install-project --project <本run>/runtime_env --python D:/dianzi/backend/.venv/Scripts/python.exe`，exit0；无网络/模型下载或共享venv修改。最终完整复跑使用 `<本run>/runtime_env/.venv/Scripts/python.exe -B`，cwd独立WT。以下为最终自有环境实际命令，完整参数见owned_* receipt：

| 命令 | 真实结果 |
|---|---|
| `-m ruff check --config backend/pyproject.toml <作者run>` | exit0 |
| `-m ruff format --check --config backend/pyproject.toml <作者run>` | exit0，9文件 |
| `-m mypy --follow-imports=silent --disallow-untyped-defs` 加六个作者脚本 | exit0，6文件 |
| `-m unittest discover -s <作者run> -p test_*.py -v` | exit0，32/32，0fail/skip；外层216.641秒，原unit raw记录内层耗时 |
| `<作者run>/observe.py` | 实际exit1，预期exit1，缺gate拒绝 |
| `<本run>/independent_probes.py` | exit0，原21独立映射21/21，0skip |
| `<本run>/boundary_and_sources.py` 最终复跑 | exit0，追加8/8合成边界；AST/rg调用证据同时封存 |

作者run固定为 `reports/runs/recovery_r06_incremental_observation_preparation_20261016`；本run固定为 `reports/runs/recovery_r06_observer_newreview_recheck_20261016`。非测试命令不计unit数量；32、21观察点和8追加边界分列。

最终21映射、8边界和369回放结果在 `owned_environment/`，首轮结果仍保留。运行时依赖大文件不纳入报告证据封存；保留冻结输入字节hash、uv离线同步raw receipt及实际Python/安装包版本inventory，可按相同命令重建，不把runtime文件当产品证据或抬高观察日志预算。

满数量1000轮小增量实际8111875B、snapshot651830B、最大record652513B。全集合持续变化仍在第21轮预算终态，14311405B，原16MiB门内保留末状态。均为合成容量，不承诺任意变化都能六小时运行。

369旧轮次白名单安全投影和独立record链逐轮核验通过，4snapshot/30delta/335heartbeat+terminal；本run journal613208B、持久703021B（run/segment标识不同产生与作者不同的字节数）。原16,803,098B文件前后SHA256均 `012e5354d35c8eb8c55aa0adfcbf8555714412c7a1c3c111d82ddaa53ac3524f`；旧产品1927、墙钟19:45:24→22:49:51、11067秒/3h04m27，不与V2拼接。旧日志只验证已采样公共投影、NULL/失败/历史计数与独立opaque指纹；不恢复操作token，不说明采样间全部事件，也不证明新版本可以安全启动。

本轮保留两项仪器失败：首次CBM组合pattern被WSL shell拆分，inner exit127，改为单名查询成功；首次追加边界在调用产品前因审查代码把canary长度算少1字节而assert失败，inner exit1，修正仅审查脚本后8/8成功。原raw log/receipt未覆盖；这两项不算产品失败，也没有把所有执行都写成exit0。

## 本次实际CBM核对

新获官方CLI路径后实际运行0.11.0的help、index帮助、schema帮助/查询、索引、search及qualified trace；没有回填初审当时CBM not_run记录。CLI每次本地执行后退出，不启HTTP UI/MCP daemon或产品服务。

仅从349c固定Git blob复制99个 `backend/src` tracked源文件到自有 `cbm_source`（当前HEAD源内容一致），索引路径精确为该源代码副本，未索引原reports、holdout、配置秘密或运行资产。fast/persistent独立项目 `r06_observer_recheck_src`，1292nodes/6424edges、0 skipped/partial/unusable；默认排除 `ai_intel/assets` 1目录，不能声称其代码已索引。

真实qualified `...ai_intel.ingestion.source_jobs.enqueue_source_page` trace有source_polling.enqueue_due_source_collections和runtime.poll_due_public_sources的LSP边（0.97），至outbox.enqueue_job的LSP边（0.97）。API/file caller标heuristic，未当强解析证明。`...SourceCursorRepository.commit_page` trace实际0caller，不能宣称图已连上动态handler。

动态链用六个349c固定blob的AST/rg补证：runtime `EXECUTION_HANDLERS[SOURCE_JOB_TYPE]` 绑定build_source_page_handler；consume_job→execute_job；executor从job_type取handler并调用；source_jobs内collect_page创建SourceCursorRepository，repository.commit_page传following。outbox enqueue_job和relay/publisher也核实际源码。AST只说明真实语法/绑定，不冒充运行链通过。旧collect/supervise与新observe/log脚本单列run组，明确不存在于src图，不伪造CBM边；证据见 `source_evidence.json`、`source_rg.log`和CLI原输出。

## 交付边界

输入/输出已限定为固定九源、PG只读有界集合→安全观察证据；pg_snapshot固定SQL/transaction/statement_timeout未变，没有任意SQL/URL/shell或新REST提交层。缺gate完整入口在env/DB前failclosed实证成立。安全独立依据是固定本地代码、合成观察和授权旧run可验证此工具，而不依赖未完成来源/model/live前置；它支持离线切片放行，不能跨阶段代签。

评分仅补F1/P1/E1容量、观察投影、恢复可追溯性。没有独立漏采参考集合/有效发布时间分母，因此没有时效p50/p95/max、漏采率、准确率或六小时通过；HTTP202提交不计完成时效。source_polling须按实际配置启用并由既有beat/outbox/worker真正采集，观察器0REST仅表示无REST路径。

unit/contract本切片passed；integration/security/frontend/e2e/live/manual均not_run，未跑产品全套回归，未实测PG/队列/存储、来源/费用、root Windows Job/MinIO/WSL资源所有权或正式人工走查。root唯一选择新固定8a产品完整SHA、新run/segment/supervisor和live gate；本报告不启动这些运行，不代表新live安全门已核验。

Verdict: Ship. 仅上述离线观察器切片；原3Must和Should4关闭。

Not checked: 产品集成、安全全套、UI/E2E、live/人工、外部来源和资源门实测未检查；CBM默认排除的assets代码亦未索引。
