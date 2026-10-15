# G-B 阶段独立检查点审查 1

审查者：`/root/g_b_checkpoint_review`，未参与 R04/R05 实现与修复。首个实际时钟记录：2026-10-15T18:12:03+08:00。首稿写作起止未单独计时，不用测试时间或mtime补造；此时审查尚未结束，最终截止时刻以末尾封存记录为准。只写本报告及 `reports/runs/recovery_gb_checkpoint_review_1_20261015/`，没有修改业务、合同、共享状态、金标、阈值或分母，没有 commit/push/accepted，也没有派发子 Agent。

**What this change does:** R04 将两固定公开来源接到原文版本、证据、PG 任务/游标与界面；R05 将指定事件的当前公开证据接到真实本地语义、pgvector、两轮生成/支持核验与持久答案。此处评审这条阶段链及其映射切片，不验收 R12 多轮多跳、R17 全工作台、R19 金标、R20 容器、R22 正式评测。

**阶段状态：needs_changes，尚不能 Ship。** 1ff 的 clean checkout 安全回归失败已在 8c 的独立全套复跑中关闭；进一步真实 PG 探针发现来源写接口的三条幂等合同反例。另有 frozen 环境公共 schema 格式校验依赖缺口。主控正在修复；本报告不以其自检替代新 SHA 的独立复验。最终意见将在末节明确追加。

## 1. 固定版本、范围与依据

| 对象 | 完整 SHA / tree |
|---|---|
| 已验收 G-A 起点 | `fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4` |
| 委派候选 | `1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc`；父代码 `7ed73540c001a4e7f5b5fa5dc2948c4b4635590f` |
| 第一独立 detached WT | `D:/wt/gb-stage-review`；创建前路径不存在，主仓两处未跟踪报告保留 |
| 原始业务后端 tree | `6b91c2c318ec75c0f9625a3f86a52460bfe0dd36`，与真实 dc014 精确相等 |
| 原始业务前端 tree | `740566274dc282ebafd12ef3fe8f42ab85becc4a`，与真实 dc014 精确相等 |
| 第一次修复候选 | `8c809c42296e3c4d064c8eaf46965303f2b8124d`，第二全新 detached WT `D:/wt/gb-stage-recheck` |
| 8c 后端 tree | 上述 `6b91c2…` 不变 |
| 8c 前端 tree | `5862a0f0a690bf66f3f3ea7f3fdbd2caa9b62e8a`；只有 question-client.test.ts 行尾，产品 TS 无行为差异，不能称完整前端 tree 与 dc014 相等 |

实际读取 frozen AGENTS、00、11/12 恢复计划、R04/R05、原 T09/T10/T12/T17/T18/T20/T30/T31/T40/T41/T43，及其 02–09 合同、requirements/manifest/state、G-B/R04/R05 报告、各专项审查的原发现和最新定向结论。CR-R04 的解析、原文持久化、来源任务、只读投影、模型 POST 与 R05_question_commit 均逐条对照源码。Ponytail 使用实际读取的 5.2 review/full 技能，而非旧版本摘要。

R04 输出切片为 T09/T10/T12/T17/T40/T41；R05 为 T18/T20/T30/T31/T43。manifest 的阶段门要求新独立审查，原 T 最终前置、所有切片和 C01–C06 未删除。当前源时间缺时区仍未知；不将采集时间补成发布时刻。完整 U01–U14、九维、七类以上来源、完整 Agent 与正式评分仍属于后段。

## 2. Confirmed defects 与复验要求

### Must fix

1. **来源写入不要求请求键，也未按主体与 canonical 来源路由隔离。** `backend/src/ai_intel/api/source_routes.py` 原 L132–155；`infrastructure/outbox.py` L53–77。
   - 输入/预期：已登录全局系统管理员，正确 Origin/CSRF，POST 两前缀固定来源但不带键，应在预约前 422，0 PG 任务；两个主体或两个固定来源路由的同键应各自独立。
   - 实际：无键四 POST 全部 202，四不同 job、四 PG 行；两独立管理员同键/body 返回同一 job；同一管理员同键用于 NVD/vLLM 得到 202/409。`source_idempotency__recheck.log/xml` 为 3 failed，全部真实隔离 PG，无外部 GET。
   - 根因：HTTP 只在 key 非 None 时校验，把原键直接交给仅 `(tenant=None, job_type, key)` 的通用任务幂等域；缺少认证主体与路由维度。
   - 影响：提交结果未知后重试可重复创建采集任务；不同管理员的操作相互折叠或冲突；不同来源路由错误碰撞。不是已证第三方扫描或付费重复生成。
   - 最小修复：HTTP 边界要求 ASCII 可见 1..200 字符键，用认证 user_id、固定 source_kind canonical 路由和原键形成稳定有界 PG 键；两个 API 前缀共享同一 canonical 路由。通用 worker 续页键保持既有意义。旧无 actor 的任务保留，不能猜其归属。
   - 复验：原三条输入/业务断言不得改变，再验同主体两前缀重放、异体409、不同主体/来源、并发和权限撤销顺序。主控同时补事务内认证锁；需亲测锁前撤销/降级/迁租，以及持锁时 logout 真正被 PG 阻塞。

2. **锁定测试环境没有注册公共 schema 的 date-time 格式校验。** `backend/pyproject.toml` dev jsonschema 声明；`tests/plan/test_public_api_v2.py` L94–100。
   - 输入/预期：原公共 AskResult 的 `created_at="2026-10-14T20:00:00"`，无时区，应被原 FormatChecker 拒绝。
   - 实际：fresh `uv sync --frozen --extra semantic` 后 tests/plan 为 55 passed / 1 failed；验证器判有效。注册格式列表没有 date-time，rfc3339_validator 不存在。
   - 根因/影响：基础 jsonschema 不保证安装其可选格式实现，原合同负例在项目声明的干净环境无法复现。此为依赖/合同检查缺口，未据此断言 Pydantic 产品问答接受无时区时间。
   - 最小修复/复验：锁定官方格式 extra，不写另一个格式正则，不改 schema 或负例；在全新 frozen 安装上重跑原 56 项，并保留旧 55/1。

3. **已关闭的初审安全阻断：clean checkout 改变精确夹具字节。** `.gitattributes` 与 `reports/runs/recovery_r01_behavior_review_1_20261014/frontend_behavior.test.tsx`。
   - 输入/预期：core.autocrlf=true 的新 detached checkout，原 51 条精确分类应仍与原 raw 字节/hash/span 匹配。
   - 实际：1ff 全后端为 1418 passed / 1 failed，原 T06-C06 失败。12 个拒绝均同文件的六 span × 两模式；manifest/HEAD blob SHA256=`9b401b2a37da5375326f82a838186f43973b230b12cb5247964757eec953661c`，checkout=`60db6f0dd6c0d62138156ac01c03909e96ee470e63d7a390af19d9816a539520`，text 属性未指定。不是发现实际秘密值。
   - 最小修复：精确 path 保留已审原字节，不改扫描器、pattern、span、value、manifest 或 ignore。8c 在第二全新 WT 的 raw/hash/span/HEAD blob 均 51/51、rejected=0；全套 1419 passed，0 failed/skip，原覆盖门不变。原 1ff 红日志保持。

### Should fix / 非阻断债务

4. **RFC850 的 50 年边界仍只看年份。** `ingestion/source_jobs.py` 原 L248–253。
   - 输入为 clock=`2026-10-15T12:34:56Z`、Retry-After=`Saturday, 16-Oct-76 00:00:00 GMT`；完整时间超过未来50年边界，应映射过去1976，有限7秒重试。
   - 实际误选2076并 blocked，`rfc850_debt` 为 1 failed。影响是保守的可用性误阻塞，没有提前重试或绕过限流；该既有债务继续明确开放，不能说所有附加负例全绿。
   - 最小修复是完整 datetime 比较再回退100年，并在世纪/闰日边界复验。本阶段不以此单项推翻已经验证的安全阻塞或一般限流行为，但后续来源覆盖/可用性仍应补齐。

## 3. 亲测命令与结果

完整 argv/cwd、开始/结束 ISO 秒级+08、SHA、exit 见每项 `.command.json`；JUnit 是实际计数来源。下表套件重叠，不相加成业务题目分母。所有 PG 模型 wire/向量标记 synthetic/fixture，非模型质量 live。

| label / 命令范围 | cwd / 2026-10-15 +08 起止 | exit；实际数量 |
|---|---|---|
| backend_full；pytest unit/contract/security `-m 'not real_pg' -q` | 第一 WT/backend；18:13:52 起，结束见原 receipt | 1；1418 pass / 1 fail / 10 deselected / 0 skip；coverage73.80%，原60门 |
| source_security；来源任务/metadata/原修复+PG权限/执行器/任务合同 | 第一 WT/backend；receipt | 0；49 pass，0 fail/error/skip |
| source_details；导入原 source_documents 测试，仅绑定本人 UUID schema | 第一 WT/backend；receipt | 0；25 pass；回放、A→B→A、no-CVE后补、并发、整页回滚、旧证据 |
| vector_question；原 vector/question API | 第一 WT/backend；receipt | 0；35 pass；真实 pgvector/PG，两前缀/重放/失效/跨主体/失败费用轨迹 |
| question_probes；原 dc014 独立探针原字节复制 | 第一 WT/backend；receipt | 0；8 pass；真实硬退出、双进程、到期/late writer、PG auth 锁等待 |
| deleted_evidence；本 reviewer 新探针 | 第一 WT/backend；18:26:25–18:26:30 外层 | 0；1 pass；物理删除全部支持证据后新问答503/无新增生成、旧GET404，原答案行不覆盖 |
| knowledge_api；原知识API与原修复测试，只绑定自有 schema | 第一 WT/backend；receipt | 0；41 pass；真实cookie→PG列表/详情/证据、嵌套ACL、stale、坏引用503、来源管理员门 |
| backend_static；Ruff check/format + mypy src | 第一 WT/backend；18:20:17–18:20:19 | 0；全 src/tests 检查通过 |
| frontend_quality；typecheck/lint/build/Vitest | 第一 WT/frontend；18:14:54–18:15:21 | 0；254 pass，0 fail/skip |
| browser_fixture 初次 / cache复跑 | 第一 WT/frontend；各 receipt | 初次exit1：17 browser setup失败，缺默认1248；原失败保留。既有仓外cache复跑exit0：17 pass/0 fail/skip/flaky |
| official_pdf_recheck；真实解析官方原件 | 第一 WT；18:26:59–18:27:00 | 0；PDF hash固定、3882字符、页1–4全部精确回切 |
| live_provenance；read-only PG+MinIO | 第一 WT；18:24:21–18:24:23 | 0；434证据、114唯一原对象校验；无新来源/模型POST |
| recheck_backend_full；8c完整 unit/contract/security，原60门 | 第二 WT/backend；18:25:28–18:27:02 | 0；1419 pass / 0 fail/error/skip / 10 real_pg deselected；raw5193/7037=73.79565155606082% |
| recheck_frontend_quality | 第二 WT/frontend；18:25:38–18:26:03 | 0；254 pass，类型/lint/build通过 |
| semantic_smoke；现有官方只读权重的真query/passages/rerank | 第二 WT；18:29:06–18:29:14 | 0；384维query、2真实passage向量、rerank索引[0,1]；active children0，0下载/付费 |
| plan_contract | 第一 WT；receipt | 1；55 pass / 1 fail，格式依赖缺口 |
| source_idempotency__recheck | 第一 WT/backend；18:33:15–18:33:21外层 | 1；3业务反例 fail，原输入留档 |
| rfc850_debt | 第二 WT/backend；18:29:06–18:29:08 | 1；1 fail，非阻断既有债务 |

数据库：新建 `test_dianzi_gb_stage_review_20261015_bba59f55`，RUN_ID 精确匹配，原 fixture guard未绕过；source/knowledge各用 UUID schema。vector/question仅使用已获准专库 `test_dianzi_r05_pgvector_20261015` 的自有 UUID schema，不改旧G-A库，不 downgrade/重启共享服务。`test_review_source.py`/`test_review_knowledge_api.py` 直接导入原测试函数/业务断言，仅替换硬编码资源 fixture；没有编辑业务树测试。

审查仪器错误另列：首 PG 私密配置读取未指明 Ubuntu/root，尚未执行 pytest；首官方PDF探针错用不存在 full_text 属性，改用现有 normalized_text；来源幂等首次缺 transitive empty_schema_engine fixture，3 setup errors后原断言复跑3业务失败；CBM 首次类限定函数名不匹配，随后实际 ask trace通过。各原失败日志留存，不记成产品通过或新增业务缺陷。source-origin审查先误把 git hash-object过滤后的SHA1当raw SHA1，已按原提案代码解释，不能把该仪器误判当业务错误。

## 4. 实际调用链与复杂度

官方 WSL portable CBM0.11.0 真实 help→index→schema→trace，独立仓外缓存 `/tmp/dianzi-cbm-gb-stage-review-20261015`。只索引本人固定 WT src：后端1085nodes/5218edges，not-indexed/skipped/partial/unusable0；前端232/822，fast模式明确16测试文件未索引，另由源码与实际Vitest复核。没有图索引报告、秘密、holdout或权重。

- 来源：source_routes认证/CSRF→PG job/outbox→worker execute_job围栏→source cursor claim→固定网关GET→strict JSON/member原字节→MinIO/PG revision/evidence/claim/event→commit_page/下一页延后outbox→PG只读API→界面。错误页事务回滚；旧page>1 blocked；after从受控Link提取后重建固定仓库URL。原始头在转字典前拒绝重复；限流解析失败不提前重试。
- 问答：question_routes→必需key预约→EventEvidenceRetriever的public/current/active支持筛选→永久证据原文核验→最多32 evidence/64派生chunk→真实E5/pgvector top8→真实重排→两轮生成与支持核验→同事务auth session/user share锁+epoch锁+owner/expiry CAS→PG completed；GET重新鉴权/校验旧引文，epoch差标stale。返回接口不带会话token到模型或trace。
- 前端：AuthenticatedQuestions/runRequest→submitQuestion→CSRF前后代次核验→fetchJson的问答POST90s→严格DTO→固定revision/evidence侧栏。未知写入结果保持原body/key；不会自动重发；React文本输出与脱敏错误，无HTML执行或私有正文存储。

CBM对嵌套闭包/动态装配并不完整，ask callers为0不能据此断言未装配；以 question_routes、app、runtime源码、rg调用点和亲测 PG 路由交叉补证。负载假设只按当前单事件同步槽/单worker受控段；未做多用户/多进程容量或吞吐性能。没有发现需新增通用框架、仓储层、第二事实库或主观删行的整改项。

## 5. 真实证据核验与不冒称的结果

本 reviewer没有再次发付费模型POST、没有读取真实生成key/.env/DPAPI，也没有启动产品API/worker。当前没有产品服务在线。根产品来源库 `test_dianzi_r04_pipeline_20261015` 用 `default_transaction_read_only=on` 的 REPEATABLE READ连接，只读既有批准配置；MinIO原对象只读。

dc014 answer=`ee73ded8-bfad-59b0-ad16-c251404eb778`：实际 PG response/model_trace/scope_epochs 与 root raw逐项相等；引文revision、URI和子串相等。434条证据全部独立核对block Unicode回切、quote SHA、源成员重新解析block，以及完整响应JSONpointer成员；114个唯一MinIO对象经完整SHA校验。只读观测105事件/434证据/2历史答案/20检索块，原数据不写回。

root browser receipt确为1完整业务test，真实HTTP/无route mock，完整客户端10212.6966ms，服务端10135ms；两次供应商attempt，fee unknown。该段复用20个同空间既有派生块，query/rerank/双轮生成重新执行，不能称冷索引。早前23c的17008.697ms属于另一版本/缓存条件，不混为分位值；累计8真实供应商调用不是8金标题。语义smoke仅检真实数值、排序接口及进程回收，不作准确率或性能达标。

R04实际来源/页面的 root原记录和专项独立真实UI记录保持原SHA归属；本次25/49/41 PG及17浏览器fixture为独立复跑。公开JSON原件路径、after页回执、原105/434迁移、已保存MinIO字节与当前源事实交叉，不用fixture声明供应商live故障。NVD外站网页正文 blocked_external_content不等于已存证据丢失，不改成可达正文。

## 6. 分类、原始档案与秘密检查边界

共同manifest仍51=原36+新增15；15条涉及11文件、13唯一path/span，旧55/48和15/10口述数已撤回。8c fresh checkout所有分类raw/hash/span/value精确匹配，扫描器/pattern/ignore与1ff不变。新15的每条literal均在已标isolated fixture或redaction来源行；Git source_blob与当时Git过滤后字节，与source_sha的原工作树字节分别核对，不能强称两个标识相等。两个R02 probe的精确历史raw source SHA仍须补保存或明确缺口，不能拿规范化blob掩盖该缺口。

2370原始blob/45504351字节的旧暂存receipt、raw属性冻结脚本已核对：-text/-diff仅保留具体原始档案和EOF，不是扫描目录忽略。51记录文件的新字节修复已独立亲测，实际秘密值不由本reviewer取得。主控既有9refs/321patterns、gzip展开和0命中receipt是核对的主控证据，不记成本reviewer亲测实际秘密扫描。两旧venv原样仓外迁移before/after清单各4857/6532项与inventory hash相等，未把第三方55命中分类为fixture，也未通过放宽规则消失。

## 7. 未检查、评分限定与交接

未运行真人manual、正式质量金标/准确率/召回率、同条件对照/消融、完整响应性能分母/并发吞吐、最终连续运行窗口、OCR/布局表格、完整Linux容器semantic/来源出网、FOFA/资产、多轮多事件/时间/调查、完整R12/R17、最终R23复现。当前真实≤5s不成立；没有改变阈值、分母或把failed改skip。

评分只支持本阶段F1/R1/E1的两源原文/任务/永久引用、F2/F3/A1的真实接口与单事件首答、D2的有限桌面/390业务界面。不能从切片通过推出九维/七类以上来源、多跳优秀、Agent完整协作或生产可用。

下一步只复核主控固定修复候选的来源幂等/事务锁、frozen格式依赖和精确source档案。新代码应重新完整unit/contract/security、受影响PG与必要frontend检查，再据同SHA证据给阶段意见；原失败和非阻断RFC850保持。不更新progress、不push、不替实现者登记accepted。

**Verdict（本中间证据截止）：fix 1 and 2 first；3已在8c关闭，4为明确非阻断债务。Not checked：上述正式评测/人工/容器/后段范围。**
