# G-B 阶段独立检查点审查 1

审查者：`/root/g_b_checkpoint_review`，未参与 R04/R05 实现与修复。首个实际时钟记录：2026-10-15T18:12:03+08:00。首稿写作起止未单独计时，不用测试时间或mtime补造；最终截止时刻以末尾封存记录为准。只写本报告及 `reports/runs/recovery_gb_checkpoint_review_1_20261015/`，没有修改业务、合同、共享状态、金标、阈值或分母，没有 commit/push/accepted，也没有派发子 Agent。

**What this change does:** R04 将两固定公开来源接到原文版本、证据、PG 任务/游标与界面；R05 将指定事件的当前公开证据接到真实本地语义、pgvector、两轮生成/支持核验与持久答案。此处评审这条阶段链及其映射切片，不验收 R12 多轮多跳、R17 全工作台、R19 金标、R20 容器、R22 正式评测。

**最终阶段意见：Ship，限定冻结 SHA `1927eeb00a7e0c1335f76340b0382f46102f08f2` 的 R04/R05 阶段切片。** 本 reviewer 在第三个全新 detached WT 独立复跑后，初审 clean checkout 字节、来源 HTTP 幂等与 frozen schema 格式三项 Must 全部关闭；保留全部旧红例。RFC850 完整50年边界仍为明确非阻断债务。此意见不登记 accepted，不签后段整卡或正式质量/性能。

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

### 初审 Must，最终已逐项复验关闭

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

4. **RFC850 的 50 年边界仍只看年份。** `ingestion/source_jobs.py` L238–240。
   - 输入为 clock=`2026-10-15T12:34:56Z`、Retry-After=`Saturday, 16-Oct-76 00:00:00 GMT`；完整时间超过未来50年边界，应映射过去1976，有限7秒重试。
   - 实际误选2076并 blocked，`rfc850_debt` 为 1 failed。影响是保守的可用性误阻塞，没有提前重试或绕过限流；该既有债务继续明确开放，不能说所有附加负例全绿。
   - 最小修复是完整 datetime 比较再回退100年，并在世纪/闰日边界复验。本阶段不以此单项推翻已经验证的安全阻塞或一般限流行为，但后续来源覆盖/可用性仍应补齐。

## 3. 亲测命令与结果

完整 argv/cwd、开始/结束 ISO 秒级+08、SHA、exit 见每项 `.command.json`；JUnit 是实际计数来源。下表套件重叠，不相加成业务题目分母。所有 PG 模型 wire/向量标记 synthetic/fixture，非模型质量 live。

| label / 实际命令 | cwd | ISO+08 起止 | exit / 计数 |
|---|---|---|---|
| `backend_full`<br>`D:/wt/gb-stage-review/backend/.venv/Scripts/python.exe -m pytest tests/unit tests/contract tests/security -m "not real_pg" -q --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/backend_full.xml` | `D:/wt/gb-stage-review/backend` | 2026-10-15T18:13:52+08:00<br>2026-10-15T18:15:36+08:00 | 1；total=1419, pass=1418, fail=1, error=0, skip=0, deselected=10 |
| `source_security`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r04_source_jobs_pg.py tests/integration/test_r04_revision_metadata.py tests/integration/test_r04_review_regressions.py tests/security/test_r02_auth_state_boundaries.py tests/security/test_r03_executor_authorization.py tests/contract/test_t07_jobs_outbox.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_security.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:19:16+08:00<br>2026-10-15T18:20:18+08:00 | 0；total=49, pass=49, fail=0, error=0, skip=0 |
| `source_details`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_details.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:22:35+08:00<br>2026-10-15T18:23:01+08:00 | 0；total=25, pass=25, fail=0, error=0, skip=0 |
| `vector_question`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r05_vector_persistence.py tests/integration/test_r05_question_api_pg.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\vector_question.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:19:15+08:00<br>2026-10-15T18:20:09+08:00 | 0；total=35, pass=35, fail=0, error=0, skip=0 |
| `question_probes`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_recheck.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\question_probes.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:22:25+08:00<br>2026-10-15T18:22:44+08:00 | 0；total=8, pass=8, fail=0, error=0, skip=0 |
| `deleted_evidence`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_deleted_evidence.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\deleted_evidence.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:26:26+08:00<br>2026-10-15T18:26:30+08:00 | 0；total=1, pass=1, fail=0, error=0, skip=0 |
| `knowledge_api`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_knowledge_api.py --no-cov -q --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\knowledge_api.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:31:15+08:00<br>2026-10-15T18:31:57+08:00 | 0；total=41, pass=41, fail=0, error=0, skip=0 |
| `backend_static`<br>`powershell -NoProfile -Command ".venv/Scripts/python.exe -m ruff check src tests; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; .venv/Scripts/python.exe -m ruff format --check src tests; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; .venv/Scripts/python.exe -m mypy src; exit $LASTEXITCODE"` | `D:/wt/gb-stage-review/backend` | 2026-10-15T18:20:17+08:00<br>2026-10-15T18:20:19+08:00 | 0；非 pytest 检查 |
| `frontend_quality`<br>`powershell -NoProfile -Command "npm run typecheck; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run lint; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run test -- --reporter=junit --outputFile=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/frontend_unit.xml; exit $LASTEXITCODE"` | `D:/wt/gb-stage-review/frontend` | 2026-10-15T18:14:54+08:00<br>2026-10-15T18:15:21+08:00 | 0；total=254, pass=254, fail=0, error=0, skip=0 |
| `browser_fixture`<br>`"C:/Program Files/nodejs/node.exe" node_modules/@playwright/test/cli.js test --config=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/playwright.config.mjs` | `D:/wt/gb-stage-review/frontend` | 2026-10-15T18:19:42+08:00<br>2026-10-15T18:19:54+08:00 | 1；total=17, pass=0, fail=17, error=0, skip=0 |
| `browser_fixture_cache`<br>`"C:/Program Files/nodejs/node.exe" node_modules/@playwright/test/cli.js test --config=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/playwright.config.mjs` | `D:/wt/gb-stage-review/frontend` | 2026-10-15T18:21:03+08:00<br>2026-10-15T18:21:16+08:00 | 0；total=17, pass=17, fail=0, error=0, skip=0 |
| `official_pdf_recheck`<br>`backend/.venv/Scripts/python.exe reports/runs/recovery_gb_checkpoint_review_1_20261015/probe_official_pdf.py` | `D:/wt/gb-stage-review` | 2026-10-15T18:26:59+08:00<br>2026-10-15T18:27:00+08:00 | 0；非 pytest 检查 |
| `live_provenance`<br>`backend/.venv/Scripts/python.exe reports/runs/recovery_gb_checkpoint_review_1_20261015/audit_live_provenance.py` | `D:/wt/gb-stage-review` | 2026-10-15T18:24:21+08:00<br>2026-10-15T18:24:23+08:00 | 0；非 pytest 检查 |
| `recheck_backend_full`<br>`D:/wt/gb-stage-recheck/backend/.venv/Scripts/python.exe -m pytest tests/unit tests/contract tests/security -m "not real_pg" -q --cov-report=json:D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/recheck_coverage.json --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/recheck_backend_full.xml` | `D:/wt/gb-stage-recheck/backend` | 2026-10-15T18:25:28+08:00<br>2026-10-15T18:27:02+08:00 | 0；total=1419, pass=1419, fail=0, error=0, skip=0, deselected=10 |
| `recheck_frontend_quality`<br>`powershell -NoProfile -Command "npm run typecheck; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run lint; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run test -- --reporter=junit --outputFile=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/recheck_frontend_unit.xml; exit $LASTEXITCODE"` | `D:/wt/gb-stage-recheck/frontend` | 2026-10-15T18:25:38+08:00<br>2026-10-15T18:26:03+08:00 | 0；total=254, pass=254, fail=0, error=0, skip=0 |
| `semantic_smoke`<br>`D:/wt/gb-stage-recheck/backend/.venv/Scripts/python.exe D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/probe_semantic.py` | `D:/wt/gb-stage-recheck` | 2026-10-15T18:29:06+08:00<br>2026-10-15T18:29:14+08:00 | 0；非 pytest 检查 |
| `plan_contract`<br>`backend/.venv/Scripts/python.exe -m pytest tests/plan -q --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/plan_contract.xml` | `D:/wt/gb-stage-review` | 2026-10-15T18:28:18+08:00<br>2026-10-15T18:28:41+08:00 | 1；total=56, pass=55, fail=1, error=0, skip=0 |
| `source_idempotency__recheck`<br>`D:\wt\gb-stage-review\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source_idempotency.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_idempotency__recheck.xml` | `D:\wt\gb-stage-review\backend` | 2026-10-15T18:33:16+08:00<br>2026-10-15T18:33:21+08:00 | 1；total=3, pass=0, fail=3, error=0, skip=0 |
| `rfc850_debt`<br>`D:/wt/gb-stage-recheck/backend/.venv/Scripts/python.exe -m pytest D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/test_rfc850_debt.py --no-cov -q --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/rfc850_debt.xml` | `D:/wt/gb-stage-recheck/backend` | 2026-10-15T18:29:06+08:00<br>2026-10-15T18:29:08+08:00 | 1；total=1, pass=0, fail=1, error=0, skip=0 |

数据库：新建 `test_dianzi_gb_stage_review_20261015_bba59f55`，RUN_ID 精确匹配，原 fixture guard未绕过；source/knowledge各用 UUID schema。vector/question仅使用已获准专库 `test_dianzi_r05_pgvector_20261015` 的自有 UUID schema，不改旧G-A库，不 downgrade/重启共享服务。`test_review_source.py`/`test_review_knowledge_api.py` 直接导入原测试函数/业务断言，仅替换硬编码资源 fixture；没有编辑业务树测试。

审查仪器错误另列（均保留原日志，不改为skip）：首 PG 私密配置读取未指明 Ubuntu/root，尚未执行 pytest；首官方PDF探针错用不存在 full_text 属性，改用现有 normalized_text；来源幂等首次缺 transitive empty_schema_engine fixture，3 setup errors后原断言复跑3业务失败；CBM 首次类限定函数名不匹配，随后实际 ask trace通过。各原失败日志留存，不记成产品通过或新增业务缺陷。source-origin审查先误把 git hash-object过滤后的SHA1当raw SHA1，已按原提案代码解释，不能把该仪器误判当业务错误。最终自制role撤权探针首轮错误地把tenant=None的global admin仅改成viewer，违反既有users CHECK，实际3pass/1fail(503)；修正为合法viewer+tenant后，原4项加GET3项共7pass。汇总脚本首次误读browser_initial.json文件名，exit1，随后读取实际browser.json；这些均非产品defect。

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

共同manifest仍51=原36+新增15；15条涉及11文件、13唯一path/span，旧55/48和15/10口述数已撤回。8c fresh checkout所有分类raw/hash/span/value精确匹配，扫描器/pattern/ignore与1ff不变。新15的每条literal均在已标isolated fixture或redaction来源行；Git source_blob与当时Git过滤后字节，与source_sha的原工作树字节分别核对，不能强称两个标识相等。两个R02 probe的混合行尾原始字节已在1927按精确path保留；最终历史source SHA 51/51、可核对Git source标识39/39，新增15的来源字面量全部在指定行匹配。旧G-A记录的可选source_content_git_blob与历史review_ref缺口没有冒充新记录完整性；详见逐条origin_metadata。

2370原始blob/45504351字节的旧暂存receipt、raw属性冻结脚本已核对：-text/-diff仅保留具体原始档案和EOF，不是扫描目录忽略。51记录文件的新字节修复已独立亲测，实际秘密值不由本reviewer取得。主控既有9refs/321patterns、gzip展开和0命中receipt是核对的主控证据，不记成本reviewer亲测实际秘密扫描。两旧venv原样仓外迁移before/after清单各4857/6532项与inventory hash相等，原 metadata 70命中/58文件、第三方55命中/47文件均独立重算；未把第三方55命中分类为fixture，也未通过放宽规则消失。

## 7. 未检查、评分限定与交接

未运行真人manual、正式质量金标/准确率/召回率、同条件对照/消融、完整响应性能分母/并发吞吐、最终连续运行窗口、OCR/布局表格、完整Linux容器semantic/来源出网、FOFA/资产、多轮多事件/时间/调查、完整R12/R17、最终R23复现。当前真实≤5s不成立；没有改变阈值、分母或把failed改skip。

评分只支持本阶段F1/R1/E1的两源原文/任务/永久引用、F2/F3/A1的真实接口与单事件首答、D2的有限桌面/390业务界面。不能从切片通过推出九维/七类以上来源、多跳优秀、Agent完整协作或生产可用。

下一步由主控依据此有限阶段意见登记相应阶段/CR与切片，再按其授权进入后续批次；本reviewer不更新progress、不push、不替实现者登记accepted。原失败与非阻断RFC850保持。

**历史中间意见：1ff/8c阶段 needs_changes；来源幂等与frozen格式修复前不允许阶段Ship。原三项Must及各红例不删除，最终复验见下节。**


## 8. 最终冻结候选的独立复验与阶段意见

第三 detached WT `D:/wt/gb-stage-final` 创建前确认路径未占用，实际 HEAD=`1927eeb00a7e0c1335f76340b0382f46102f08f2`，完整tree=`9c58236461186803ece26d1dda70186094199ea0`；backend/src=`2e85b41a18456d462619959e22622a23e4ca7b78`，frontend/src=`5862a0f0a690bf66f3f3ea7f3fdbd2caa9b62e8a`。后端相对8c只有source_routes产品代码改变，前端产品和整个src tree相对8c均未变；相对dc014不能称整个业务tree相等。问答/检索/worker/原文writer与真实dc014代码逐blob相同，来源HTTP鉴权/幂等新行为由本次真实PG测试覆盖，没有新付费产品调用。

本WT使用全新 `uv sync --frozen --project backend --extra semantic` 和 `npm ci`，不是沿旧env补pip。原jsonschema schema/负例不变，官方 `format-nongpl` extra安装后原56项通过。full backend **1419pass/0fail/0error/0skip，10 real_pg deselected**，coverage原始5196/7049=`73.71258334515534%`，原60门未改。10真实PG安全用例在49项source/security套件另行实际执行，未改skip。Ruff check、190文件format、mypy82源码通过。

最终真实隔离PG：49来源任务/权限/执行器/合同、25原文、41知识API、35向量与问答、8问答进程/并发/锁序、删除支持证据1、原3来源幂等、7新增POST/GET auth锁、11正式来源HTTP，共各套件全部pass/0fail/error/skip，不加成题目或性能分母。新增来源3/7/11、25原文与41知识API继续本人数据库bba59f55；最终49来源/security另建 `test_dianzi_gb_stage_review_20261015_a15dd559`，精确RUN_ID、UUIDschema与原guard均有效。新增正式11测试直接导入原函数，单换本人空库资源fixture，原业务断言不改。

来源Must1的原无键四POST现在422且0PG行，两个独立管理员与两个source_kind同键各产生独立job；两前缀同主体/来源重放与并发只一个job，异body409。来源源码L128–141、L153–179和L204复用原auth session/users share锁，在同PG提交/读取事务验证当前身份。亲测锁前logout→401、合法降权/迁租→403并0job；持锁logout在PG阻塞，提交后才撤销；GET锁前撤销/降权/迁租均拒绝且无job正文。旧裸key任务保留、无法可靠补actor归属；已读CR-R04-R04_source_commit的停未知重投/核对job_id迁移限制，不声称旧键可无损推断迁移。

最终frontend type/lint/build、**254 unit pass**、**17 fixture browser pass**均在1927自己的node_modules/src执行。浏览器包括1366/390、reduced-motion、键盘引文、固定revision、未知写入body/key保持、权限/异常状态、HTML按文本及来源任务状态；没有产品API或模型POST。raw manifest三候选全文SHA256均`b525699f38bf2deb2eac85ef1912e71ae8049503f903eb07740438729e651240`，51/51 WT raw/HEAD blob/span/值、0拒绝，scanner与ignore diff为空。历史source_sha51/51，Git标识39/39；两个R02原始mixed-CRLF字节缺口关闭。

最终CBM重新索引本人backend/src：1085nodes/5219edges，not_indexed/skipped/partial/unusable0；重新get_graph_schema与trace_path build_source_router/lock_authenticated_scope。router trace确实连接create_application与POST/GET route。嵌套lock_source_scope未索引的失败原样保留，用rg、源码L128/L159/L204与7真实PG探针补证，不冒称静态图完整。

root实际secret staged scan是核对其元数据：9refs/321patterns/32本次staged路径、0命中；本reviewer没有取得秘密值，实际秘密精确扫描仍明确not_run_by_reviewer。2370/45504351 raw完整性为核对既有主控receipt和属性机制，不声称本reviewer重新生成2370原始历史字节。两份venv before/after entries完整清单相等、4857/6532与inventory SHA对应原receipt；未删除原失败或豁免第三方文件。

| label / 实际命令 | cwd | ISO+08 起止 | exit / 计数 |
|---|---|---|---|
| `final_uv_sync`<br>`uv sync --frozen --project backend --extra semantic` | `D:/wt/gb-stage-final` | 2026-10-15T18:44:59+08:00<br>2026-10-15T18:45:11+08:00 | 0；非 pytest 检查 |
| `final_npm_ci`<br>`npm.cmd ci` | `D:/wt/gb-stage-final/frontend` | 2026-10-15T18:52:31+08:00<br>2026-10-15T18:52:37+08:00 | 0；非 pytest 检查 |
| `final_backend_full`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe -m pytest tests/unit tests/contract tests/security -m "not real_pg" -q --cov-report=json:D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/final_coverage.json --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/final_backend_full.xml` | `D:/wt/gb-stage-final/backend` | 2026-10-15T18:45:33+08:00<br>2026-10-15T18:47:18+08:00 | 0；total=1419, pass=1419, fail=0, error=0, skip=0, deselected=10 |
| `final_plan_contract`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe -m pytest tests/plan -q --junitxml=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/final_plan_contract.xml` | `D:/wt/gb-stage-final` | 2026-10-15T18:45:43+08:00<br>2026-10-15T18:46:12+08:00 | 0；total=56, pass=56, fail=0, error=0, skip=0 |
| `source_idempotency__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source_idempotency.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_idempotency__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:48:49+08:00<br>2026-10-15T18:48:55+08:00 | 0；total=3, pass=3, fail=0, error=0, skip=0 |
| `source_formal__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source_formal.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_formal__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:48:49+08:00<br>2026-10-15T18:49:01+08:00 | 0；total=11, pass=11, fail=0, error=0, skip=0 |
| `source_auth_lock__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source_auth_lock.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_auth_lock__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:48:49+08:00<br>2026-10-15T18:48:56+08:00 | 1；total=4, pass=3, fail=1, error=0, skip=0 |
| `source_auth_lock__final_valid_fixture`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source_auth_lock.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_auth_lock__final_valid_fixture.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:49:37+08:00<br>2026-10-15T18:49:46+08:00 | 0；total=7, pass=7, fail=0, error=0, skip=0 |
| `source_details__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_source.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_details__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:50:01+08:00<br>2026-10-15T18:50:25+08:00 | 0；total=25, pass=25, fail=0, error=0, skip=0 |
| `knowledge_api__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_knowledge_api.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\knowledge_api__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:49:08+08:00<br>2026-10-15T18:49:47+08:00 | 0；total=41, pass=41, fail=0, error=0, skip=0 |
| `source_security__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r04_source_jobs_pg.py tests/integration/test_r04_revision_metadata.py tests/integration/test_r04_review_regressions.py tests/security/test_r02_auth_state_boundaries.py tests/security/test_r03_executor_authorization.py tests/contract/test_t07_jobs_outbox.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\source_security__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:50:36+08:00<br>2026-10-15T18:51:44+08:00 | 0；total=49, pass=49, fail=0, error=0, skip=0 |
| `vector_question__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest tests/integration/test_r05_vector_persistence.py tests/integration/test_r05_question_api_pg.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\vector_question__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:51:37+08:00<br>2026-10-15T18:52:39+08:00 | 0；total=35, pass=35, fail=0, error=0, skip=0 |
| `question_probes__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_recheck.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\question_probes__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:51:37+08:00<br>2026-10-15T18:52:00+08:00 | 0；total=8, pass=8, fail=0, error=0, skip=0 |
| `deleted_evidence__final`<br>`D:\wt\gb-stage-final\backend\.venv\Scripts\python.exe -m pytest -p conftest D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\test_review_deleted_evidence.py --no-cov -q -s --junitxml=D:\wt\gb-stage-review\reports\runs\recovery_gb_checkpoint_review_1_20261015\deleted_evidence__final.xml` | `D:\wt\gb-stage-final\backend` | 2026-10-15T18:51:37+08:00<br>2026-10-15T18:51:41+08:00 | 0；total=1, pass=1, fail=0, error=0, skip=0 |
| `final_static`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe -c "import subprocess,sys; commands=[[sys.executable,'-m','ruff','check','src','tests'],[sys.executable,'-m','ruff','format','--check','src','tests'],[sys.executable,'-m','mypy','src']]; codes=[subprocess.call(cmd) for cmd in commands]; sys.exit(max(codes))"` | `D:/wt/gb-stage-final/backend` | 2026-10-15T18:50:01+08:00<br>2026-10-15T18:50:02+08:00 | 0；非 pytest 检查 |
| `final_frontend_quality`<br>`powershell -NoProfile -Command "npm run typecheck; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run lint; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run build; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; npm run test -- --reporter=junit --outputFile=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/final_frontend_unit.xml; exit $LASTEXITCODE"` | `D:/wt/gb-stage-final/frontend` | 2026-10-15T18:52:47+08:00<br>2026-10-15T18:53:14+08:00 | 0；total=254, pass=254, fail=0, error=0, skip=0 |
| `final_browser_fixture`<br>`"C:/Program Files/nodejs/node.exe" node_modules/@playwright/test/cli.js test --config=D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/playwright.final.config.mjs` | `D:/wt/gb-stage-final/frontend` | 2026-10-15T18:52:47+08:00<br>2026-10-15T18:53:02+08:00 | 0；total=17, pass=17, fail=0, error=0, skip=0 |
| `final_classification`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/audit_classifications.py D:/wt/gb-stage-final classification_audit_final.json` | `D:/wt/gb-stage-final` | 2026-10-15T18:49:07+08:00<br>2026-10-15T18:49:21+08:00 | 0；非 pytest 检查 |
| `final_origin`<br>`D:/wt/gb-stage-final/backend/.venv/Scripts/python.exe D:/wt/gb-stage-review/reports/runs/recovery_gb_checkpoint_review_1_20261015/audit_manifest_origins.py D:/wt/gb-stage-final manifest_origins_final.json` | `D:/wt/gb-stage-final` | 2026-10-15T18:49:07+08:00<br>2026-10-15T18:49:11+08:00 | 0；非 pytest 检查 |

完整命令收据及所有仪器失败包含在 `reports/runs/recovery_gb_checkpoint_review_1_20261015/command_summary.json`；逐文件依据SHA在document_inventory.json，最终版本/hash/coverage核验在final_metadata.json，亲测live溯源在live_provenance.json。JUnit计数与browser JSON可以独立重算；所有套件有实际起止秒级+08，不拼不同候选的结果声称同版全绿。

**最终 Verdict：Ship — 仅1927固定R04/R05阶段与当前映射切片；Must1/2/3已独立关闭。Should4 RFC850债务开放；Not checked 为第7节的正式评测/人工/容器/后段范围。** 此限定意见已覆盖本阶段六项验证和历史实际live链路溯源；新来源HTTP行为由真实PG认证/事务测试证明。没有新模型live、没有质量金标、当前10212.6966ms真实完整响应不满足≤5s，不称生产可用，不修改阶段状态。


初审全部字节差异补核：12条checkout hash拒绝及13条Git blob hash差异涉及9个唯一path，均已亲测CRLF/LF归一后字节完全相同；initial_byte_failures.json逐条保留原manifest/checkout/blob SHA、拒绝数和原因（2026-10-15T18:58:47+08:00至18:58:48+08:00，exit0）。不是9个实际秘密。下列列表为全部差异路径：

- `reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log`：WT拒绝记录=0，blob差异记录=1
- `reports/runs/recovery_r01_behavior_review_1_20261014/frontend_behavior.test.tsx`：WT拒绝记录=12，blob差异记录=0
- `reports/runs/recovery_r01_behavior_review_1_recheck_20261015/backend_security.log`：WT拒绝记录=0，blob差异记录=4
- `frontend/src/api/question-client.test.ts`：WT拒绝记录=0，blob差异记录=3
- `reports/runs/recovery_r01_search_tls_review_1_20261015/forced_failure_showlocals.log`：WT拒绝记录=0，blob差异记录=1
- `reports/runs/recovery_r01_search_tls_review_1_20261015/forced_failure_showlocals_recovered.log`：WT拒绝记录=0，blob差异记录=1
- `reports/runs/recovery_r02_minio_review_1_20261015/native_auth_failure.stdout.log`：WT拒绝记录=0，blob差异记录=1
- `reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_sanitized.log`：WT拒绝记录=0，blob差异记录=1
- `reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure_v2_sanitized.log`：WT拒绝记录=0，blob差异记录=1

资源通知（核对主控消息，非本reviewer续期）：MinIO段3在2026-10-15T18:57:02+08:00结束，段4在18:57:49+08:00启动，47秒中断，新硬截止20:57:49+08:00。本人114对象亲测属于段3；不拼持续时长，也没有因资源续期重复验证既有对象。产品候选仍1927。

最终报告补核封存实际起止：2026-10-15T19:01:00+08:00 → 2026-10-15T19:01:00+08:00；证据截止包含final_metadata_seal 18:59:31+08:00；封存时刻2026-10-15T19:01:00+08:00。审核停止于本G-B阶段。
