# G-B · 真实来源、原文证据与模型问答

文档首次创建时间：2026-10-15T13:48:37+08:00
本次写作开始时间：2026-10-15T19:06:14+08:00
本次写作结束时间：2026-10-15T19:06:14+08:00（本次独立意见登记）
最后更新时间：2026-10-15T19:14:59+08:00
阶段实际开始/结束时间：历史未单独记录开始；首个来源GET观测2026-10-15T11:53:40+08:00不是阶段起点 / 2026-10-15T19:01:00+08:00独立阶段门封存，不是连续服务时长
本报告证据截止时间：2026-10-15T19:01:00+08:00（独立报告封存）；本次状态登记见写作时间
主控/实现Agent：/root；各作者、工作树、文件所有权与冻结版本见progress/recovery_workstreams.md及任务报告
独立审查Agent与报告：/root/g_b_checkpoint_review；reports/reviews/recovery/G-B-checkpoint-review-1.md；固定1927最终Ship，三Must关闭；登记文档待同reviewer差异核对
阶段状态：accepted（仅批准的R04/R05阶段切片，依据新非作者限定Ship；登记文档复核中）
实现状态：complete（仅R04/R05本阶段功能候选；原T整卡、R12/R17和后段部署验收不在此提升）
各层验证状态：unit/contract/integration/security/frontend/e2e passed仅本文与独立报告限定范围；live passed仅已测分段真实来源/模型/页面及独立溯源，非1927整版本新增外部复跑；manual not_run。正式指标未验收
工作分支：codex/full-delivery-recovery
已测代码SHA：1927eeb00a7e0c1335f76340b0382f46102f08f2独立干净环境综合/PG/前端；dc014c960f19605c20e0d8e98a93e7c217f94cc6真实模型/API/页面；各早前分段不可拼同版本时长
已审代码SHA：1927eeb00a7e0c1335f76340b0382f46102f08f2；独立报告最终Ship，文档登记提交SHA待冻结后复核
提交/推送结果：G-B尚未阶段push；G-A远端fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4，2026-10-15T15:41:48+08:00已核对；实际台账reports/push/recovery_push_log.jsonl

## 1. 本阶段要解决的用户问题与验收范围

R04把真实NVD和vLLM厂商公告从共享网关接到原文库、解析、永久证据、PG事实、任务/游标及浏览器列表/详情。R05把一个当前公开事件的证据接到真实E5、pgvector、重排和两轮生成/支持核验，用户可打开固定revision证据并重读已保存答案。覆盖F1/F2/F3/A1/E1/D2/R1当前切片；U01发现、U02证据详情、U06单事件首答、U10来源操作有部分路径证据，不能签九维完整、深度多跳或全部运维场景。

原T09/T10/T12/T17/T40/T41及T18/T20/T30/T31/T43只完成本阶段映射切片，整T卡继续等待全部映射、前置与验收共同满足。R05不是R12，问答明确拒绝asset、conversation、多事件、known_at/valid_at和investigate，返回422；R17完整资产、图谱、推荐、报告与Agent工作台仍未完成。R06八类九通道调研在独立准备包推进，未计为本阶段产品来源。

## 2. 当前真实状态与修改

原有问题包括默认入口未装配、伪PDF文本层标记、NVD真实wrapper/cvssData失配、模型无真实IO、内存事实/游标、失败仍推进游标、前端骨架。G-A已建立真实PG/API/auth/worker/outbox；本阶段复用这些实现，没有另建事实数据库。

- 解析：pypdf受控子进程读取真实文本层、页号与Unicode位置；JSON严格拒绝重复键/非有限/孤立代理/NUL，保留解码字段原文及RFC6901路径。扫描PDF准确报告缺文本层，不伪称OCR。官方四页PDF独立实际parsed，3882字符、四页位置均可回切；不将单次解析耗时计问答性能。
- 来源：NVD Ollama固定查询与vLLM公开公告，经可信网关、MinIO原文、不可变response/member和PG源版本入库。厂商按真实Link的after游标分页；保存事实、回执、cursor、job/outbox同事务。首次数字page重复同10条的错误及其旧回执不删除。2026-10-15T17:10:08+08:00前向迁移核对105事件、434证据及证据身份hash完全保留。
- 问答：真实本地E5固定官方ONNX/分词器与模型空间384维写PG，真实mmarco重排；PG派生块不能扩大可见范围或复活撤回事实。只取当前公开、validated support、有效claim的证据，精确子串引用；两轮真实GenerationClient分别生成与核验，不执行模型工具。完成前重查原文/hash/epoch与权限。
- 持久化/权限：必需幂等key；PG唯一预约、420秒有界失效、owner与expiry CAS，重放不重付费；同事务FOR SHARE锁会话和用户，保证先撤销拒绝、已持锁则撤销等待答案提交。旧无lease pending需受控人工恢复，不猜付费结果；实际试验库新段启动前无旧pending。
- 前端：暗色青绿研究工作台、低亮动态拓扑背景、pointer-events:none、键盘焦点、reduced-motion；真实列表/详情/证据/来源控制/问答。加载、匿名、无权限、空、过期、部分失败、模型缺失和结果未知分别显示。问答POST预算90秒，其他请求10秒；预算不是P3达标。未知提交保留同body/key，禁止自动换key重发。

必要新增是source writer/page job、只读投影、真实模型wire/本地受控推理、单事件检索和答案生命周期及页面。复用PG、认证、网关、永久证据、标准库与现有UI组件。pypdf、pgvector、onnxruntime/tokenizers/numpy各为真实PDF/向量/模型必需；固定缓存约975MB在仓外，不执行pickle或remote code，没有哈希向量/内存产品库/模板成功页。

## 3. 并行执行与独立审查

主控独占共享schema/迁移0014/锁/状态/集成/Git。来源、解析、只读API、生成wire、语义、前端、grounding及PG测试各在独立worktree按指定文件交付。每个初审为未参与实现的新Agent，固定commit；作者仅awaiting_review。四槽滚动执行，详细所有权与交付SHA见各报告，未向其他用户聊天或协作软件发消息。

| 冻结范围 | 独立证据与结论 |
|---|---|
| PDF/JSON解析48ad907 | reports/reviews/recovery/G-B-R04-parsing-review-1.md：原两Must与数值覆盖缺口关闭，官方四页实际校验；组件限定通过 |
| API7af、来源8f6 | G-B-R04-api-review-1-recheck-2.md、G-B-R04-pipeline-review-1-recheck.md：ACL/版本/事务及after分页限定通过；原失败保留 |
| 生成31c、语义1e77、基础3ab | generation/semantic/vector-foundation专项报告：真实接口、模型空间、子进程锁/float32边界限定通过；不代替产品链 |
| grounding b151 | G-B-R05-grounded-answer-review-1.md：原跨主体未知误拒关闭，47独立探针、113核心/合同、29安全；第二模型不是人工金标 |
| 来源c83 | G-B-R04-rate-limits-review-1-recheck.md：906unit、421相关、19既有PG、40自拟；超长/过多/重复限流头不提前重试。RFC850日期边界P3仍为非阻断债务 |
| 问答UI a0a94f1 | G-B-R05-question-frontend-review-1.md：254前端、9原fixture浏览器+11独立检查；原12秒请求被10秒取消红例保留并复验关闭 |
| 问答事务dc014 | G-B-R05-question-pipeline-review-1.md：3 Must关闭；1007unit默认66.68%原60门、32PG、24新PG、8独立进程/事务反例、126核心/合同，mypy/Ruff通过 |

1ff初审候选与真实dc014的backend/src tree均6b91c2c318ec75c0f9625a3f86a52460bfe0dd36，frontend/src tree均740566274dc282ebafd12ef3fe8f42ab85becc4a。阶段初审发现clean checkout行尾使精确分类失配；修复版只改变18个分类文件的Git字节保留属性/旧归档blob，其中question-client.test.ts仅CRLF。backend/src与所有产品TS文件字节不变，frontend/src整体tree因测试文件行尾改变，不能再声称整体tree相等；git diff --cached --ignore-space-at-eol -- backend/src frontend/src为空。待同一独立阶段reviewer复核新SHA，组件Ship不自动过门。

## 4. 问题台账

每项精确发现/修复/复验时刻、输入、行号与命令在引用专项报告/原始receipt；历史没有记录的时刻不按mtime补写。下表不覆盖其原红例。

| 问题 | 触发、实际影响与根因 | 修复/状态与证据 |
|---|---|---|
| R04分页 | GitHub数字page两页实际hash相同，重复同10条并误触页上限 | 改Link after、兼容拒绝旧非首数字cursor，8f6独立关闭；旧回执保留，后5页新增40而非重复计数 |
| R04原文 | JSON二次转义/孤立代理导致精确引用失败 | 48ad907关闭，真实Unicode roundtrip与官方四页证据见解析报告 |
| R05引用换行 | 2026-10-15T15:04:28+08:00至2026-10-15T15:04:34+08:00两wire HTTP200，但模型CRLF改LF，引用不支持 | 原失败留档；单行v2另两次成功，之后产品仅精确单行派生片段，不能抹原两次失败 |
| R05 float32 | 1e-50转float32全零、极端平方范数产生NaN | 3ab按真实float32与平方范数校验，独立20PG/126相关关闭；初红全保留 |
| R05缺key | d7无key连续POST两前缀各200、总4模拟wire；违反原写入合同 | dc014在预约前422 invalid_key，0模型/0答案；原两名独立测试红例与复核保留 |
| R05中断 | 真实child os._exit后pending永不终结，重启只409 | dc014预约expiry/owner和完成CAS；独立进程与到期/late writer复验关闭，新预约不重付费，实际费用未知保留 |
| R05撤销竞态 | 最终事务外scope已取后先logout/迁租仍200 completed | dc014锁auth_sessions/users与答案同事务；真实PG先撤销拒绝、pg_blocking_pids证明后撤销等待，独立关闭 |
| UI等待 | 真12秒fixture被共享10秒取消；实际首个冷产品完整17.009秒 | a0a94f1仅问答POST90秒，默认10秒不变；独立12秒/90秒/abort/同键复核关闭，实际修复版浏览器10.213秒 |
| 综合安全扫描 | 2026-10-15T17:35:27+08:00至2026-10-15T17:36:59+08:00，1419中1安全失败：未分类credential形状 | 初扫70命中/58文件：55命中/47文件来自两个已退役venv，其余15条精确分类记录覆盖11文件/13唯一span；此前55/48、15/10口述计数已由独立审查撤回。venv原样搬仓外，4857/6532文件before/after hash完全一致；不放宽规则/目录忽略。15条已独立核对并精确合并，原36条不变；原安全单测2026-10-15T17:57:58+08:00至2026-10-15T17:58:10+08:00 exit0、1pass。全套新候选待阶段独立复跑，原1418pass/1fail保留 |
| PG回归环境 | 2026-10-15T17:40:36+08:00至17:40:39+08:00，10setup errors：run_id未包含新库随机后缀 | 仅更正子进程运行ID与同一已分配隔离库名称一致；2026-10-15T17:41:28+08:00至17:41:40+08:00，10pass；没有改隔离校验/业务/门槛 |

未解决/非阻断：RFC850完整50年日期边界会保守误blocked（非提前重试）；容器semantic extra/内存/受控出网待部署接线；Linux来源出网未由Windows成功替证；正式持续窗口、质量/速度/盲测及人工金标未完成。源时间缺时区/缺发布时间保留未知，不拿采集时刻补齐。

## 5. 实际验证

完整argv/cwd/起止秒/exit/计数/配置与SHA以原始JSON/JUnit为准。默认覆盖门仍60%，没有改分母、删题或把失败skip；重复fixture与live绝不累加成准确率。历史工具UTC记录单独标注，文档本地时刻统一+08。

| 范围/命令 | 时间、退出码与结果 | 原始证据 |
|---|---|---|
| root backend pytest tests/unit tests/contract tests/security -m 'not real_pg' -q | 2026-10-15T17:35:27+08:00至2026-10-15T17:36:59+08:00；exit1；1007unit+218contract+194security=1419，1418pass/1安全fail，另10PG明确deselected后单独运行；73.77%原60门 | reports/runs/recovery_r05_controller_20261015/gb_pure_regression.json/.log/.xml |
| root隔离PG问答/route/contract | 2026-10-15T17:33:08+08:00至17:33:42+08:00；exit0；37pass，0skip；显式synthetic模型，只计接线 | questions_api_pg_fenced_integrated.json/.log/.xml |
| root原PG权限/任务/退避 | 2026-10-15T17:41:28+08:00至17:41:40+08:00；exit0；10pass，0skip；新库test_dianzi_gb_security_20261015_76c8ab35，未升级旧G-A库 | gb_pg_security_recheck.json/.log/.xml；原setup错误gb_pg_security.* |
| 新问答前端作者+独立 | 固定a0a94f1，254pass；typecheck/lint/build通过，原9fixture浏览器与新增11检查；精确时段见各receipt | R05-question-frontend.md、G-B-R05-question-frontend-review-1.md |
| root修复版真实浏览器 | 2026-10-15T17:30:22+08:00至17:30:38+08:00；exit0；1完整业务test/13.1秒测试执行，完整单问客户端10212.6966ms，服务端10135ms；无route mock，真实HTTP登录/PG/模型 | product_live_dc014c9/browser.json、browser_artifacts/actual_question.json及桌面/390PNG |
| root首条冷产品API | 2026-10-15T17:12:18+08:00至17:12:36+08:00，23c HTTP200；完整客户端17008.697ms，真实两轮生成，GET/同key重放成功，无新增模型调用 | product_live_23c1878/question_end.json/answer_read_and_replay.json/pg_answer_trace.json |
| 真实模型次数/费用 | 31c两种wire共4次（2精确引用失败、2成功），23c产品2次，dc014浏览器2次，总8实际供应商调用；真实usage逐attempt留档，费用unknown | 两supplier run与两产品PG trace；不是8道正式金标题 |
| 实际来源/页面 | 8f6五页after新40；afe桌面1366/390列表→详情→原文→刷新2pass、管理员一页提交→PG partial1pass；具体开始/结束见两浏览器receipt | recovery_r04_source_jobs_20261015/real_browser_segment6*.json及live_segment_5_after_quota_reset/ |
| 提交真实秘密检查 | 已核对217作者证据、9秘密参考/321全值与8字节片段，gzip解压64,278,013B也扫，0命中；最终阶段全提交仍须另扫 | recovery_r01_controller_20261014/r05_author_evidence_archive_scan.json |

真实运行段：23c API为2026-10-15T17:10:56+08:00至17:22:30+08:00，requested_stop；dc014 API与Vite为2026-10-15T17:29:17+08:00至17:44:17+08:00，deadline。Windows受控terminate进程exit1如实记录，不伪称自然退出0或业务请求失败；两段都只有API、未启动worker/beat，ready可degraded。此前afe来源worker段独立记录。MinIO段2于2026-10-15T16:55:49+08:00到期，段3自2026-10-15T16:57:02+08:00起7200秒，同对象/身份但中断73秒。不同代码/中断不拼持续运行。

dc014的新段复用同E5空间20个既有派生块，query embedding、rerank与双轮生成重新执行，不能称冷索引。17.009秒与10.213秒属于不同代码/缓存条件，不拼P50/P95/max，不声明≤5秒或质量达标。问答超时、错误JSON、拒绝/权限负例主要为明确隔离contract/security，真实供应商故障未逐个强造。

not_run/未满足：正式准确率/召回率/完整性能分母、同条件基线/消融、人工双人金标、完整Linux容器新模型/来源、最终版本连续6h窗口、OCR、R12完整多跳与R17后续工作台、R23干净环境复现。没有拿首字/202/缓存命中替完整回答完成。

## 6. 合同与计划差异

按已批准CR-R04逐条补实现合同：R04_document_parsing、source_persistence、source_jobs、read_api_projection、R05_model_post与R05_question_commit；新增必需key与权限锁是落实既有05 API条款、修复偏差，不改变身份、公开字段、角色/租户、模型费用许可或评分。R05_question_commit仍awaiting_review登记，其准确落实已由独立dc014复核说明，整阶段审查后方登记。

0014前向新增retrieval_chunks/grounded_answers，旧105事件/434证据和身份hash不变；不做破坏性downgrade。API内部ask/read新增keyword-only session_token，当前产品调用方均question_routes已核对，不进模型/日志。回滚是停止新POST/模型调用并保留历史、用量、失败，前向修复，不回退fixture。

没有新范围削减、评分分母/阈值或盲测原则变更。R05单事件切片不等于T20/T30/T31/T43全部accepted；R06准备和R20部署缺口不包装为前置已完成。

## 7. 评分和场景证据

F1/R1/E1：两固定真实源的原文→PG事实/游标/任务→列表/证据与失败/partial可见；未声称八类来源完成或时效优秀。F2/A1：真实E5/pgvector/rerank和生成支持核验；九维富化全落地仍R07/R08。F3/U06：指定事件的引用首答与持久重读，缺支持拒绝，未知不自动否定；多轮多跳、资产/历史在R12。D2/U01/U02：真实浏览器操作、背景动态/减少动画与原文修订；完整演示/视频与U14未完成。P3本轮17.009/10.213秒如实记录，未达到≤5秒样本，不能自评满分。

U03–U05/U07–U09/U11–U14当前仅原规划与部分骨架/准备，不由本阶段反推已完成。正式13要求逐项最终证据在R22–R24闭合，本阶段只给上述切片。人工金标与FOFA授权资产范围仍缺，PPT用户后置；独立部分继续做，不拿blocked/awaiting_human_label作成功。

## 8. 阶段结论和下一步

已证明真实来源原文/PG/页面、两兼容wire、本地语义、单事件引用回答、历史读/幂等与新预约/权限事务、浏览器业务路径。旧三Must在限定dc014批次独立关闭，原失败未删。整合安全扫描精确分类已收口并通过原单测；新的整阶段review未发生，本报告仍不能过G-B门，不能阶段push或改整R04/R05 accepted。

下一步：最终源码/回归/文档冻结→新的阶段Agent独立复跑来源/问答/权限路径并核对状态与本文→依据其意见登记阶段与R切片、显式文件提交→检查origin/fetch/秘密/大文件→普通push codex分支并核对远端SHA、追加实际receipt。通过后继续R06–R10；准备包可以先做但不越过live门。R20补semantic镜像/容量/固定出网与恢复，R19人工金标候选/双人裁决工具，最终R22/R24-A/R23/R24-B顺序保持。

## 9. 文档修订记录

首次创建时间保留2026-10-15T13:48:37+08:00。本次2026-10-15T17:52:56+08:00至2026-10-15T17:52:56+08:00由/root按实际冻结源码、专项独立报告与raw收据重整九节，将旧全文原字节归档reports/runs/recovery_r05_controller_20261015/G-B_prior_to_integration_draft.md，SHA256 bfd6a01b5a69637c9364a19ae1046aa71cf2108d462898c512420c4fb0cbfba7；Git历史同样保留。旧报告中的进行中缺陷/组件状态是当时事实，不覆盖本次限定复核结论。没有按mtime伪造历史编写时间、没有把编写/测试/采集观察混为持续运行。

修订：2026-10-15T18:06:30+08:00，/root保留首次创建时间与所有红例；核对独立分类校正为15条/11文件/13 span和第三方55/47、实际原单测复验及完整缓存搬迁hash。精确manifest 51条，原36条不变，没有改扫描器/规则/ignore。阶段仅awaiting_review，未accepted、未push。

修订：2026-10-15T18:22:57+08:00，/root记录新阶段初审1418pass/1fail（旧fixture clean checkout行尾），独立49来源/权限PG、35向量/问答PG及254前端通过。修复按51条记录的18个精确path保留原字节；manifest全文不变，scanner/pattern/span/value/ignore不变，每个暂存blob SHA与已审记录相同。root原安全单测复验见gb_fixture_checkout_bytes_recheck.*；其初次档案EOF diff-check失败与新helper label未登记的ValueError均为控制脚本错误，确切历史时刻未单独记录，未运行业务，不计业务通过。修正精确raw属性/合法新label后才运行真正复验。首次创建时间保持。

## 阶段初审新增问题与修复候选 · 2026-10-15T18:43:56+08:00

- 新检出精确字节问题在8c809c4独立关闭：1419pass/10PG deselected、coverage73.80%，51/51 raw/hash/span、0拒绝，254前端与type/lint/build再通过。两份历史probe.py为混合行尾，root另外按精确source_path保留已审字节，见fixture_origin_bytes_freeze.json；51记录不改。
- 公开Schema原无时区日期负例在独立环境55pass/1fail，新增官方dev格式extra后root原56检查exit0/56pass。原因/兼容/迁移/回滚见CR-R04_schema_format_checks.md，待独立锁定环境复核；未改负例/阈值。
- 新confirmed来源HTTP三Must与认证竞态：缺key仍202、跨admin同job、跨source202/409、初始scope后撤销仍可受理。root原11PG回归8fail/3pass，修复后11pass；见CR-R04-R04_source_commit.md和source_http_red/green.*。完整原unit/contract/security1419pass/10另测PG deselected，coverage73.71%；mypy82/Ruff通过。不能拿前一SHA的阶段意见替新来源边界，等新候选复核。
- 实际产品live仍明确分别属于23c与dc014运行段；新候选只有source_routes.py来源HTTP边界及开发校验环境变化，问答/模型/检索/来源writer与worker逻辑未改。新来源POST/GET用真实PG回归证明，当前新候选完整外部IO/浏览器live未重跑，不拼同版本持续运行或性能。

本轮尚不能阶段push或accepted。已有原PG49/35、原文25/删证据1、PG434 span/114 MinIO对象与dc014答案核对是独立阶段审查者亲自执行，其最终报告和新SHA复验结论待落盘。仅有限切片通过不替代R12/R17/R19–24。

## 独立阶段意见登记 · 2026-10-15T19:06:14+08:00

本次写作起止均为上列真实脚本执行时点；首次创建时间保持。新非作者/root/g_b_checkpoint_review在第三个全新WT D:/wt/gb-stage-final固定1927eeb00a7e0c1335f76340b0382f46102f08f2复跑并于2026-10-15T19:01:00+08:00封存限定Ship，主控据此登记accepted，仅R04/R05本阶段切片。旧段落与红日志是按时间保留的历史，当前结论以本节及顶部为准。未修改原T任务状态、金标、阈值、分母或盲测；后段原T合并验收仍全部存在。

### 范围、独立验证和版本

两固定源→受控网关→MinIO/PG不可变原文/永久证据→PG任务/游标/outbox→认证列表/详情→浏览器；单事件当前公开证据→真实E5/pgvector/重排→两轮生成/核验→认证/epoch/owner CAS→PG答案与固定引文。新来源HTTP键与认证锁仅1927真实PG复验，不把dc014旧live冒称1927外部复跑。

最终1419纯unit/contract/security组合0fail/skip（10真实PG另测），5196/7049行=73.71258%，原60%门不变；56原计划检查；真实PG套件49、25、41、35、8、1以及来源原3负例、正式11和7合法撤权/锁顺序探针均exit0；套件重叠不可相加。前端254、type/lint/build及17浏览器fixture通过。全部cwd/命令/秒级起止/退出码/数据版本见独立报告第3/8节与reports/runs/recovery_gb_checkpoint_review_1_20261015/command_summary.json、final_metadata.json。初次浏览器缺缓存17失败是环境仪器错误，修正外部cache后同例17通过，原失败未删。真实模型未由reviewer重新付费，而是亲读核对434证据span/114对象/保存答案trace与原始浏览器结果，费用累计8次调用unknown。

### 问题台账增补与关闭

| 问题 | 输入、根因与影响 | 修复/复验与状态 |
|---|---|---|
| GB-HTTP-KEY | 两固定源POST缺key仍202；跨管理员同key折叠，跨来源碰撞；裸key幂等域缺主体/来源 | 1927认证后必需ASCII键、canonical actor/source域、事务认证锁。作者原8fail/3pass→11pass；独立原3负例与11正式、7撤权/PG锁探针通过。19:01:00+08:00审查封存关闭 |
| GB-FORMAT | fresh frozen无date-time可选实现，原无时区负例被接受，计划55pass/1fail | 1927官方jsonschema[format-nongpl] dev extra/锁；独立新环境原56pass。封存关闭，无改样本 |
| GB-BYTES | clean checkout autocrlf改变精确夹具hash/span，1418pass/1fail | 8c及1927精确路径保留原bytes；51分类及51source-origin独立通过，原manifest/regex/ignore未改；最终1419pass。封存关闭 |
| GB-RFC850 | 完整未来50年边界误只看年份，例2076误blocked，1红保留 | 非阻断保守可用性债务，未提前重试，R06来源可用性继续修；未解决，负责人/root |
| GC-CPU-LIMIT | 原R05 busy child 1 CPU秒，受并行负载时偶发8墙钟秒timeout，同参数可过 | 原红原样保留；新独立native_cpu_limit_diagnosis在1927诊断，尚未证明根因；不抬timeout/skip，不计G-B固定复跑失败 |

### 当前效果、剩余与下一步

暗色青绿/低亮动态拓扑背景、390宽度与reduced-motion已有真实截图；不是完整R17。真实修复版单问完整10212.6966ms，非≤5秒、非P50/P95、无金标准确率。R12多轮多跳、R06广来源、九维、图谱、资产、推荐/重判、Agent/MCP/插件与正式评测仍后段，未签。双人金标/裁决与授权资产范围仍缺，PPT用户后置。semantic extra/容量/受控出网的容器部署待R20；Windows成功不能代替Linux容器。

阶段无新增重大决策；三实现补充CR及兼容/前向迁移/停止入口回滚记录由新阶段reviewer与源码核对。历史raw-key job保留按job_id读，无法猜actor迁移；旧无lease pending人工恢复，不能自动重付费。源代码未因登记变化；本次只登记文档/状态/报告归档。G-B实际push尚未发生，正常push并核对远端后收据追加reports/push/recovery_push_log.jsonl随下一阶段提交。

G-C继续：两来源实现包修复后原reviewer定向复核；root独占共享catalog/document元数据版本迁移与装配，文档持久化草稿8真实PG/1019unit通过但未审且未接产品入口。不同版本/中断不拼稳定时长。MinIO段3实际18:57:02结束、段4 18:57:49开始，47秒中断，截止20:57:49；全部产品API/worker/beat当前已到期停，无持续采集声称。文档修订记录：2026-10-15T19:06:14+08:00 /root依据新独立报告登记阶段意见并保留全部历史。

## 登记修订 · 2026-10-15T19:08:27+08:00

主控首次登记漏同步R04/R05输出切片，原计划检查49pass/7fail，日志gb_registration_plan保留；根因是只改R聚合状态未改原T内slice_acceptance，与R00合同不一致。现依据相同独立Ship登记11输出切片及历史，原T整卡status/implementation/verification均未改变；没有改manifest或检查器。复验见gb_registration_plan_recheck。此为登记错误，不是降低验收门。

文档归档复核修订 · 2026-10-15T19:14:59+08:00：ab097归档漏设独立报告精确-text，checkout原交付hash正确但Git blob被CRLF规范化。按原交付bytes设单路径-text/-diff并git add --renormalize，无改报告/manifest/扫描器；修后blob与原报告SHA256 50cbd2152686af6d436514208ddd3f5fcd7116cb86b7729cfc0050974594ea32一致。初次git add未强制重过filter，索引assert失败；随后精确renormalize修正，未覆盖历史。原归档阻断待reviewer新SHA复核；其余文档独立56plan/15T06已通过。
