# G-B · 真实来源、证据页面与模型回答

文档首次创建时间：2026-10-15T13:48:37+08:00
本次写作开始时间：2026-10-15T16:17:02+08:00
本次写作结束时间：2026-10-15T16:17:02+08:00（本次证据整理时点）
最后更新时间：2026-10-15T16:17:02+08:00
阶段实际开始/结束时间：历史未单独记录，首个来源GET观测为2026-10-15T11:53:40+08:00，并非阶段开始时间 / 尚未结束
本报告证据截止时间：2026-10-15T16:17:02+08:00
主控/实现Agent：/root、r04_vendor_source、r04_knowledge_api、hacker_frontend，精确包与所有权见progress/recovery_workstreams.md
独立审查Agent与报告：专项报告及固定版本见当前快照；整阶段新审查尚未发生
阶段状态：in_progress
实现状态：partial
各层验证状态：unit/contract/integration/security/frontend/e2e/live/manual整阶段均not_run；专项结果不能替代整阶段
工作分支：codex/full-delivery-recovery
已测代码SHA：afe490前端178及真实浏览器2+1；31c供应商探测；fd01ea3基础102/6PG，retrieval working diff10PG，均限定范围，非整阶段
已审代码SHA：7af API/8f6来源/31c生成/d391时间/fccc来源UI/1e77语义限定意见；fd01ea3新基础初审在途，整阶段未审
提交/推送结果：G-A已推远端fa5，当前G-B本地fd01ea3，G-B尚未阶段push，见实际台账



## 当前权威快照 · 2026-10-15T16:17:02+08:00

集成分支codex/full-delivery-recovery，HEAD fd01ea3e0205361c1f446d6fb97694aa3aa715cf；远端最后核实为G-A fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，2026-10-15T15:41:48+08:00成功推送并ls-remote核对，见reports/push/recovery_push_log.jsonl。G-A范围已独立accepted；当前G-B in_progress/partial，未阶段push；原T整卡状态与最终范围不变。

当前来源分页e6/c3与空package/API Must已独立关闭；8f6真实after游标5页新增40，15:27观测95事件/414证据且厂商partial。afe工作台15:56桌面/移动原文证据2pass，15:59管理员真实提交/PG partial状态1pass。403/429提前重试语义修复仍在独立WT；整卡未验收。

31c生成metadata/nested/defer Must均独立关闭；两wire共4次真实调用，首轮2次因CRLF精确引用失败，single-line-v2两次通过，费用unknown。1e77语义锁Must独立关闭并集成fd01ea3；root102回归、6真PG/0014保历史/mypy75通过；新retrieval草稿10真PG通过但未冻结/未审。模型/PG/问答/API/UI完整链尚未接通，整卡未验收。

afe来源工作台已独立限定Ship，root178前端通过；真实浏览器桌面/390宽度证据2pass，管理员来源一页提交→PG partial1pass。暗色青绿/低亮拓扑/减少动画/指针焦点已验证。首轮admin selector错误已保留，按role改测试后复验通过；完整问答/资产/图谱/推荐等工作台仍未完成。

真实受控Windows段6固定afe490：API/worker/beat 15:55:43至16:10:43，前端15:55:45至16:10:46，均到期结束；不同代码/中断绝不拼连续运行。MinIO段2 14:55:48至16:55:48硬截止；Docker总截止2026-10-17T21:49:15+08。模型缓存/凭据/连接只在仓外，holdout不索引；双人金标/裁决与FOFA授权范围仍缺，PPT按用户后置。

并行：root独占公共schema/迁移0014/依赖锁/集成/进度/推送及retrieval/API接线；r05_grounded_answer_core拥有answering/contracts.py、grounding.py、直接测试/自有报告，禁止改API/PG；r04_source_rate_limits拥有source_jobs._http_failure/直接测试/自有报告（旧单个错误断言授权纠正）；新的r05_vector_foundation_review只审冻结fd01ea3并复跑，不改业务。总4槽位，子Agent不得自行扩大文件所有权/再spawn/签accepted/push。

下一步：完成单事件真实向量检索→严格引用生成/核验→PG用户答案→API→问答页面；新小批独立review后真实全链验证；限流修复新review。G-B通过后才安排新的整阶段review/push。下面旧段落仅历史，不覆盖本快照。


## 当前权威快照 · 2026-10-15T14:44:29+08:00

集成分支codex/full-delivery-recovery，HEAD d391f89c65fb892b27b6a3b45cf0a06fea6032b0；2026-10-15T14:38:43+08:00重新核对origin为授权地址。G-A/G-B仍in_progress/partial，无阶段accepted或阶段push。旧段落均为历史，不覆盖本快照；原T卡完整切片与验收条件不变。

真实来源链已在Windows受控运行段证明：7184后端于14:18:16启动，NVD实际45事件/3页完成；厂商10条已入库，来源合计55事件，证据334条为14:22附近观测。GitHub数字page实际重复同10条，达到页上限的partial不算全采完。14:24:49–52两页原始响应哈希一致，Link明确after游标；厂商分页Must未关闭，作者在独立WT修复，旧backfill游标/原始响应不删除，下一轮从未用live流验收。NVD源时间无时区保持未知，不能拿观察时间补源发布时间。

API三Must已由独立reviewer固定7af91b3定向关闭：43真实PG/探针、505纯unit(raw3075/5026)；来源空package两负例固定7184也已独立关闭。pipeline新发现翻页Must，整体仍needs_changes。真实浏览器7184链41项交互通过，含实际PG列表/详情/固定修订证据、刷新、移动端、分页和错误恢复；NVD外网页内容仍blocked_external_content，GitHub外网页200/内容可核验。来源监控页仍待接线，完整R17未完成。

UI已实现暗色青绿黑客工作台与低亮动态拓扑。真实浏览器验证transform变化、减少动画后停止、pointer-events:none及焦点可用。新Must为SavedTime直接显示UTC/微秒；root d391f89统一北京时间秒级+08:00且保留原datetime，120前端unit/类型/lint通过，独立定向复验待槽位。首次root测试子命令exit0，打印输出GBK异常使外层exit1，原始日志保留并修报告脚本；不能算业务测试失败或抹去外层失败。

生成接口436455d已接两种DeepSeek wire及原生OpenAI/Anthropic接口，尚未产品接线。新独立review固定该SHA：574unit(raw3442/5356=64.26437640029873%)、共享HTTP/安全112、真实本机socket3通过，但新增probe确证两Must：prompt/schema版本可将synthetic credential写metadata；TypedDict/dataclass显式extra=ignore可吞字段。作者只修generation和直接测试，初审报告G-B-R05-generation-review-1.md保留失败，产品模型调用仍0、费用unknown，embedding/rerank未选/未探测。

当前四槽滚动：root统一合同/状态/集成及UI时间；r04_vendor_source独立source_jobs/source_documents及直接测试；r04_knowledge_api独立generation及直接测试；新独立r05 reviewer初审完成后释放，下一槽短时给原liveUI reviewer定向复验，再给pipeline reviewer复验。各自不得扩文件权属、不push、不accepted。公共schema/锁无本轮变更。

真实运行分段：Linux95段13:59:50–14:04:54因WSL出网失败两源0事实/0游标；Windows95段14:08:14–14:17:26证明NVD45，厂商空package失败；Windows7184段14:18:16开始、14:48:16硬截止，API28000/worker/beat，RedisDB14、独立PG0013。WindowsSolo由独立PG期限看守及JobObject内存限制，不能冒称Linux生产hard-limit验证。前端7184服务25300自14:19:19开始、14:49:19截止。MinIO新段13:17:25至15:17:25截止，中断与版本不得拼连续运行；Docker总资源17日21:49:15截止。所有启动/停止以raw收据为准，快照不是新的运行时长证据。

双人独立标注/裁决与FOFA授权资产范围仍缺；PPT按用户后置。不阻断当前接口/来源/工作台实施。凭据只在仓外DPAPI与子进程环境；不进入前端/索引/报告。下一步：翻页与生成Must修复→原独立reviewer复验；UI时间真实浏览器复验；新版本真实来源流；生成限定通过后有限模型live，再接embedding/rerank与引用回答。G-A仍需新的整阶段审查，未具备阶段push条件。


## 1. 本阶段要解决的用户问题与验收范围

R04/R05，原T09/T10/T12/T17/T18/T20/T30/T31/T40/T41/T43的切片；D2/F1/F2/F3/A1/R1。用户登录后能查看真实NVD/厂商公告、历史原文与定位证据，再得到真实模型支持的引用回答。原卡所有映射切片共同完成才能独立验收；本阶段不能替代推荐、正式多跳、完整工作台或持续运行。

## 2. 当前真实状态与修改

已实现真实PDF/严格JSON解析、NVD实际wrapper/CVSS与厂商公告归一化、PG来源元数据与原文引用、两源页面写服务、认证的事件列表/详情/证据读取、黑客风页面与低亮动态背景。复用现有PG仓储/版本/证据和网关，新增代码负责真实API字段、原始成员切片与事务装配，无平行数据库或通用CRUD框架。生成客户端由新并行包复用有界POST；真实回答、向量、rerank仍未证明。

## 3. 并行执行与独立审查

## 历史快照 · 2026-10-15T13:48:37+08:00

分支 codex/full-delivery-recovery，HEAD df214c664847f8a2c721579955108da47a55c9a6；G-A/G-B 均 in_progress/partial，无阶段 accepted 或 push。R00 的限定激活不扩为原 T 卡验收。旧快照仅为历史，以下以当前字段和证据为准。

来源修复6c7fd7a的三 Must 已由原非作者定向关闭，报告 reports/reviews/recovery/G-B-R04-sources-review-1-recheck.md：16原探针、131合同、22实际PG、396纯unit（raw62.73471352912855%）及11helper补测通过。root来源writer df214c6刚集成，尚无新独立审查；其作者41项混合命令实际27PG+14纯计算，不能写41PG。API4934de3初审又发现三Must：NUL过滤变503、损坏维度引用变空、stale支持claim仍current；root正在共享read service修复，不能把原24PG通过当API验收。

并行四槽：root拥有 source_jobs.py/source_routes.py、app/runtime接线、公共合同、状态与集成；r04_vendor_source封存sourcewriter证据后释放；r04_api_independent_review只读固定4934de3并封存初审；r04_knowledge_api在独立R05 worktree实施两种wire生成客户端，拥有infrastructure/models与直接测试，不读真实keys、不push。下一个新槽用于新sourcewriter reviewer，初审固定df214c6或新的明确候选；不能自审。

真实服务：旧API0b段已13:01:56停止，当前没有API/worker长期段；MinIO新段13:17:25启动，7200秒上限，截止15:17:25，日志 recovery_r04_minio_20261015；与旧段13:15:28存在间断，不能拼连续运行。Docker/PG/Redis为已隔离资源，不升级旧审查库。root本轮将建单独source_jobs测试库；所有coverage单run仓外隔离。

前端黑客暗色、低亮缓慢拓扑与reduced-motion已实现并有独立交互结果；当前截图明确fixture。真实GET→MinIO/PG→Celery→API→浏览器仍未闭环。产品模型调用0、费用unknown；DeepSeek两wire正在实现，embedding/rerank未选择/探测。双人金标和FOFA授权资产范围仍缺，PPT按用户后置；它们不阻断当前采集和模型接口。秘密保持仓外DPAPI/环境，不进日志、索引、前端或提交。

下一步：修API三Must并冻结供原reviewer定向复验；sourcewriter新初审；root完成分页任务负例/PG原子性与真实队列采集段；R05客户端冻结后新独立审查，再由主控有限live调用。G-A还需综合集成候选与新的阶段reviewer，所有阶段push尚未发生。


## 4. 问题台账

| 问题 | 触发、预期/实际、影响 | 根因、修复、状态与责任 |
|---|---|---|
| RB-001 | 真实NVD字段与旧fixture不一致，实际CVSS丢失；影响R04/R07 | wrapper/cvssData层级；0e622修正，6c7严格时间/UTF8边界；原非作者定向关闭限定问题 |
| RB-002 | 原响应回收COUNT后并发提交FK，可删除已引用原文 | GC先读后删竞态；6c7先PG DELETE/savepoint，真实23503/23514复验通过；完整恢复仍R20 |
| RB-003 | Linux原unit396通过但静态subprocess.CREATE_NO_WINDOW不成立 | 4934使用有官方依据的Windows常量，Linux396/raw62.60494%通过；此改尚需独立覆盖 |
| RB-004 | API q/product/risk_type NUL返回503，损坏维度引用HTTP200空，过期支持claim维度current | 4934初审真实PG复现；root共享过滤/投影修复中，未签通过；精确输入/行号/日志待初审报告封存 |
| RB-005 | 新source POST ISO字符串被strict datetime拒绝，实际422未达认证 | root首次29例27通过/2失败；显式ISO字符串解析正在复跑；另修新测试problem字段错误，不改合同 |

发现/关闭的独立秒级时间以原命令收据为准；历史未记录的不补造。代码修复SHA、复验与关闭在冻结后补齐，未解决项不得当关闭。

## 5. 实际验证

- 来源修复6c7独立16原探针、131合同、22PG、396unit(raw2606/4154)、11helper与静态通过，报告G-B-R04-sources-review-1-recheck.md；测试重复不可累计成独立总数。
- API4934独立原24PG通过，独立8补测3通过/5失败，三Must未关闭；原始证据recovery_r04_api_review_1_20261015，不用作者通过抵消缺陷。
- 来源writer作者最终41混合=27实际PG+14纯计算，446unit raw2810/4479；代码df214，独立新review待派。
- 解析和UI专项见G-B-R04-parsing-review-1.md、G-B-R04-frontend-review-1-recheck.md；截图明确fixture，旧真实auth段对应0b后端。
- 真来源匿名GET：NVD与vLLM实际200留档，仅诊断/原样本；不是worker采集、连续运行、问答live或正式指标。
- 本阶段完整浏览器真实数据、真实模型/embedding/rerank、故障恢复、性能和人工结果not_run。每条真实命令的cwd/起止/退出码/数量/数据版本见runs收据；未运行的不算passed。

## 6. 合同与计划差异

CR-R04-R04_source_persistence.md与CR-R04-R04_source_jobs.md落实已授权事务/来源切片；CR-R04-R05_model_post.md落实真实模型有界请求。无需调整评分/金标/分母。观察轮次不等于上游快照，未知NVD时区原值保留且不造watermark；withdrawal传播留R16，未删验收。

## 7. 评分和场景证据

F1/F2/D2/R1仅当前来源/证据准备切片；U01登录已有专项，真实情报用户闭环尚未证明。F3/A1需真实模型与检索回答，当前未达，不自评满分。U02–U14仍按原映射保留。

## 8. 阶段结论和下一步

部分可继续开发，G-A/G-B均未过门。先修API三Must、新sourcewriter审查并完成真实worker/MinIO/PG/浏览器段；生成客户端冻结→新review→有限live，再接真实embedding/rerank与回答。缺少人工金标/资产授权只传播到相应后段验收，不能据此停止独立实施。

## 9. 文档修订记录

2026-10-15T13:48:37+08:00：/root首次创建，登记实际组件、失败、未知与并行所有权；阶段未结束，未编造历史写作时间或持续运行时长。

2026-10-15T14:44:29+08:00：/root修订当前权威字段，保留历史；补真实链路、重复分页、生成两Must、UI时间修复及受控服务边界，阶段仍未过门。

修订记录：2026-10-15T16:17:02+08:00，主控/root补G-A实际推送、旧Must关闭、95/414分段观测、真实浏览器和4次供应商探测、语义/PG进展；保留所有旧失败及未接线范围。
