# G-B / R04 来源持久化与分页装配独立审查 1

审查人：`/root/r04_pipeline_independent_review`，未参与本批实现。本文为中文质量审查；使用 ponytail-review 5.2.0。**当前结论：needs_changes；空 package 的 Must 1 已于 `7184dc6` 闭合，但新确证的真实 GitHub 分页 Must 2 尚未闭合，撤回对 7184 来源分页装配的 Ship 结论。** 不是 R04 整卡、任何原 T 整卡或 G-A/G-B 阶段验收，不自行写 accepted。首次创建和实际最后写入时间由本轮 `review_document_times.json` 记录，不以测试时段代替编码工时。

**What this change does:** 本批把两个固定公开来源的原始 HTTP 响应、原始成员字节、历史修订、事件、事实与证据写入共享 PG/内容存储。每个任务处理一页，页回执、游标、下一页 outbox 和本页状态同事务提交；API 用现有 cookie/Origin/CSRF 认证，默认 worker 注册固定 handler。

**Verdict: fix 2 first.** 原 7184 定向通过只能关闭空字段缺陷；整数 page 的 fixture 通过不足以证明实际 GitHub 分页正确。先前附录/manifest 已原样归档，下面保留原记录并追加撤回与新缺陷证据。`95ba650` 的读取投影另有原 API reviewer 定向发现的问题，不在此签绿；该服务后续修复由其独立复核。

## Must fix（1 已闭合；2 未闭合）

1. **真实厂商公告的空包名/生态导致整页无法入库**（`backend/src/ai_intel/ingestion/sources/vendor_advisories.py:109,162–163`；调用边界 `source_documents.py:254`）。
   - **是什么：** 公开 GitHub 公告的 package 字段进入可选 `str | None` 包身份字段，来源修订应保留未知归属和原始范围文本。2026-10-15 的真实第一页十条响应，第六条 `GHSA-5fj9-pfhr-6j48` 的 `package` 为 `{"ecosystem":"","name":""}`，原始范围 `< v0.30.0`、修复范围 `>= 0.30.0`。
   - **问题：** `_vulnerabilities` 将这两个可选字段交给拒绝空字符串的 `_text`，抛出 `VendorAdvisoryError`；写服务转为 `SourceDocumentError`，整个十条页失败。独立固定版复跑直接 normalizer 和真实 PG 全页持久化，**2 failed，0 skipped，exit 1**；首轮其他九条可解析不能使本页成功。公共原样本 SHA-256 为 `f5007db50489ecebbbfec5d8cc8798eb18cff1d12faf503795ce97c85e6894e1`，115956 bytes。
   - **最小修复：** 只对可选 package ecosystem/name 将空或全空白字符串归一为 `None`，继续拒绝非字符串、NUL 和不合法 UTF-8，保存原字节；不从仓库名猜包身份，也不丢失原始版本条件。`source_documents.py:316` 已有 `package_name is not None` 守卫，未知字段应不形成 `affected_product` 或确定版本事实。
   - **不修的影响：** 实际厂商首十条响应持续 blocked，零厂商游标/修订，第一条两源闭环无法满足。现有单条录制 fixture 和纯 unit 通过不能代表这个生产输入成功。失败日志、JUnit 和原始测试保存在 `actual_vendor_empty_identity_red.*`；向主控报告后，已按末尾新固定 SHA 完成定向复核。

2. **厂商任务忽略真实 Link 游标，整数 page 请求不断重取首页**（`backend/src/ai_intel/ingestion/source_jobs.py:74,87–95,213`）。
   - **是什么：** GitHub 的 repository advisories 列表使用响应 Link 的 before/after 游标；官方参数列有 before/after/per_page/state，没有整数 page。本 reviewer 实际读取核对了[GitHub 官方接口文档](https://docs.github.com/en/rest/security-advisories/repository-advisories#list-repository-security-advisories)。
   - **问题：** `source_page_url` 重建 `page=2`，`_next_position` 只按 body 长度递增整数，未读取 `FetchResult.redacted_headers` 的 Link。主控 14:24:49–52 真实固定网关对 page 1、2 均 200，两个完整响应完全相同（115956 bytes、SHA `f5007db...e6894e1`、相同十 GHSA）；两页均给 `after=Y3Vyc29yOnYyOpHOAAg-eQ%3D%3D` 的 next Link。独立保存原 body/Link 后，在固定 7184 的真实 PG handler 回放中，正确 next 位置应来自 after，当前却为 `{"page":2}`；**14:26:52–14:26:59，1 纯函数 + 1 真实 PG 回放，2 failed/0 skip/exit 1**，见 `recheck_7184/actual_vendor_link_cursor_red.*`。此处是 recorded/fixture 回放，不计本 reviewer live。
   - **最小修复：** 解析有界且严格校验的唯一 next Link，只接受已批准 HTTPS origin、固定命名或已实证 numeric repository 路径、精确 per_page/state 和单个 after；提取 token 后仍重建固定请求 URL，不执行 Link 中任意 URL。没有 next 才完成；重复/malformed/self cursor 拒绝。旧 `page>1` 位置明确 blocked，保存旧回执/原文，不假推断完成位置。
   - **不修的影响：** 后续十页重复同十公告，最多二十页后 partial，却漏采其余公告并消耗请求；PG 幂等只能防重复事实，不能证明覆盖。主控观察到 vendor page 14 时总事件仍只有十 vendor；该运行通知不作本 reviewer live 验收，但相同原输入的独立复现已说明算法错误。Must 1 关闭仍成立，source_jobs 和完整 R04 不可通过。

## 候选与独立边界

- 固定审查候选：`95ba6503dcae4b86ea8fdffea150f1b59a941014`；tree `25afdc66cbac783fddc748b434a2244d685c96b6`；diff 基线 `08c4471`。主体为 `df214c6` 的来源 writer 和 `95ba650` 的分页 handler/API/runtime；附带 read-service 接线检查，不替代原 reviewer。
- 独立 Windows 工作树：`C:/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review/dianzi`；分支 `codex/review-r04-pipeline-20261015`。原始业务文件、合同、progress、锁文件、金标未改，未提交/push/accepted。原工作树用户未提交修改未触碰。
- `candidate_windows_git.json` 实际 `git status` 为空，`git diff --exit-code --quiet` 为 0；70 个源码经 native Git 路径过滤后的 blob 均等于候选。WSL Git 的 diff 摘要 hash 为 `408e380a...a3e6d9e`，反映 Windows checkout 与 WSL 行尾过滤差异，不能称业务补丁；native Git 及 70 文件候选 blob 核对是干净依据。
- 读取了 AGENTS、执行地图、恢复计划 11、卡 12 的 R03/R04/R05、T09/T10/T12/T17/T40/T41 及引用 03/04/05/06/07/08/09 合同、两份来源 CR、当前冻结状态/交接。作者 `42dfa93` 报告仅作输入，未拿其通过次数替代复跑。作者终轮 41 mixed 明确是 27 PG + 14 纯计算，不能写成 41 PG。

## 实际复跑

全部 Linux 检查 cwd 为独立工作树 `backend`；命令完整参数、+08:00 秒级起止、exit、数量见各 `*.command.json`。`uv run --locked` 使用独立 `UV_PROJECT_ENVIRONMENT=/tmp/dianzi-r04-pipeline-review-20261015/venv`、CPython 3.12.13 和锁定 68 包；未覆盖主控 Windows 或其他 Linux venv。

| 标签 / 命令主体 | 实际时间 +08:00 | 结果与层级 |
|---|---|---|
| `pure_unit_frozen` / `pytest tests/unit -q --cov-report=json:...` | 14:00:25–14:01:20 | 505 pass、0 fail/error/skip、exit 0；纯 unit；1 既有 Starlette deprecation warning |
| `source_pg_frozen` / 原 writer 测试精确资源适配副本 | 14:00:46–14:01:23 | **25 真实 PG** pass，exit 0，0 skip |
| `jobs_pg_frozen` / `test_r04_source_jobs_pg.py test_r03_jobs_pg.py` | 14:01:37–14:01:56 | **24 真实 PG** pass（本批分页 9 + 既有任务 15），exit 0，0 skip |
| `api_pg_frozen` / 原 API 与定向回归资源副本 | 14:03:02–14:03:59 | **39 真实 PG** pass，exit 0，0 skip；显式 fixture/TestClient，不是运行进程/浏览器 live |
| `static_frozen` / Ruff check、format --check、mypy src | 14:04:06–14:04:10 | 三命令 exit 0；75 文件格式、70 源码类型检查 |
| `targeted_negatives_first` / 新独立补充测试 | 14:06:56–14:07:00 | exit 1：1 pass、7 fixture setup errors；审查 harness 漏导入 `empty_schema_engine`，不是业务失败；原日志/源码副本保留 |
| `targeted_negatives_resource_fixed` | 14:08:12–14:08:30 | exit 1：6 pass、2 fail；审查查询误选 `knowledge_change` 当来源下一任务，期待未改；原日志/源码副本保留 |
| `targeted_negatives_source_selector_fixed` | 14:10:18–14:10:33 | 8 pass、exit 0、0 skip；修正任务选择为固定 `SOURCE_JOB_TYPE`，同一业务输入/期待 |
| `original_contracts_frozen` / T09/T10/T12 contract 与 T17 unit | 14:11:40–14:11:43 | 26 pass、exit 0、0 skip；纯计算/显式 fixture，与 unit 部分重复，不相加为独立正式样本 |
| `actual_vendor_empty_identity_red` / 真实公共十条响应回放 | 14:12:36–14:12:40 | **2 fail、exit 1、0 skip**；1 纯 normalizer + 1 自有真实 PG。Must 1 证据 |
| `source_shared_raw_gc_frozen` / 既有独立原输入回归 | 14:15:24–14:15:29 | 16 pass，exit 0、0 skip；**2 真实 PG 并发 GC + 14 纯计算**，不是 16 PG |

原覆盖门 `--cov-fail-under=60` 未改、未混入 PG 抬覆盖率。纯 unit 原始 JSON：`3075 / 5021 = 61.24278032264489%`，1946 missing、42 excluded（既有工具配置），0 新增忽略。每轮独立 `COVERAGE_FILE` 保存在仓外 `/tmp/dianzi-r04-pipeline-review-20261015/<label>.coverage`。

自有库为 `test_dianzi_r04_pipeline_review_20261015`，连接只在内存/环境；未升级旧库。writer/API 硬编码库名只在审查副本适配为自有库；writer `FIXTURES` 与 conftest `PROJECT_ROOT` 仅绑定该 WT。`test_adaptations.json` 与逐文件 `.adaptation.diff` 保存原/副本 hash，原输入、期望、金标、分母未改。

## 路径、行为与规模核对

codebase-memory-mcp 注册工具不存在，实际先执行 portable CLI help/schema，使用 v0.11.0。独立 cache `/tmp/dianzi-cbm-r04-pipeline-review-cache`，项目名 `dianzi-r04-pipeline-review-95ba650`，`CBM_ALLOWED_ROOT` 仅本 WT `backend/src`。full index 为 70 Python files、925 nodes、4349 edges，not-indexed/skipped/partial/unusable 都为 0；未索引 secrets、holdout、报告或源样本。13 个实际 CLI 命令和 architecture/trace 保存在 `cbm.command.json` 与 `cbm_*.log`。

图与源码交叉确认：`create_application → build_source_router → enqueue_source_page → PG job/outbox`；`runtime.EXECUTION_HANDLERS → build_source_page_handler → collect_page → gateway → persist_source_response → register_response_content / save_document_revision / EventRepository / KnowledgeRepository / DimensionRepository → PG/ContentStorage`；`knowledge_routes → KnowledgeReadService → 现有 DTO`。CBM 能识别外层路由和公共持久化调用，不能解析嵌套 `collect_page` 节点（trace/search 实际无节点）；该段用源码和真实 job PG 测试交叉，不能凭图无边推断未接线。

按仓库的多线程/多 worker 任务规模检查，未自行声称额外吞吐能力。已观察验证：

- 响应 hash 与原字节可重读、成员原字节与 JSON 路径、UTF-8/code-point 证据坐标、score/authority/vector 三字段独立支持；严格 JSON 拒重复键、NUL/surrogate、非有限值及超界。
- 同末版幂等、envelope-only 不造业务修订、A→B→A 三修订、旧证据不覆盖；无 CVE 与后补 CVE 的主键；已有公开别名使用真实事件 ID、硬标识冲突整页回滚；四线程同时首写只发布一次。
- scope/角色/来源身份/固定 URL 白名单拒绝、来源内部 worker 不信任 payload 租户；API cookie/Origin/CSRF、别名、幂等冲突、租户拒绝和 payload 不外露。
- 全页 rollback、成员/存储/证据失败没有假成功；下一页持久延后 7 秒、页上限 partial、失败保留已提交位置；本次补测真正执行了 NVD 第二页和厂商满十条后的空页。
- 任务重放、两 worker、retry due、旧 owner/attempt/job lease fence 与源任务超时效果回滚；HTTP 429/403/404/503 分类保留前成功窗；没有在 handler 内另建睡眠/重试。
- 两类原响应引用并发 GC 原输入复跑；另用自有唯一 MinIO bucket 实际确认 full-response 引用阻止 GC 后原字节仍可读。该测试是真实 PG+MinIO+公开录制 fixture，**不是匿名 HTTP live 或持续采集**，只删除自己 bucket 对象。
- 来源 `Rejected`/withdrawn 声明只作为有证据的来源事实，未推断全局安全或自动撤回；版本条件仍留 raw/normalizer，当前 writer 没有凭仓库名形成版本适用结论。

## 未检查、阻塞与后续

本 reviewer 没有启动真实 Celery/浏览器链，也没有自行执行新的匿名 live GET。Must 的原响应由主控固定网关真实 GET 获取，本次验证为不可改样本的独立回放；主控 Windows/WSL 运行证据另列，不能混算本审查 live。主控通知：WSL 出口失败；Windows 固定 95 NVD 首页已进入实际 worker/PG/MinIO，而 vendor 因 Must 1 blocked。这些通知仅作范围提示，不替代独立原始日志审查。

R04 的两源完整公开抓取→实际 worker→数据库→页面/录像仍需补齐；PDF/UI 等此前报告不为后续未测版本自动背书。`95ba650` read-service 的三 Must 与后续 unrelated-reference 问题归原 API reviewer 定向复核。无真实模型、正式准确率/召回率/时效/性能、连续运行时长或人工金标结果；R05/R16/完整 R04/阶段门均不由此报告通过。R16 撤回传播、旧新结果/原空结果重判仍未做，不把原文留档当传播完成。

评分证据只支持 F1/F2/D2/R1 的来源原文/事件/证据/任务切片；不能把两固定来源叫七类覆盖，或把 source_status 留档叫完整更新闭环。未发现需改冻结合同、依赖主版本、认证或计分分母的理由。

审查只新增本报告与 `reports/runs/recovery_r04_pipeline_review_1_20261015/**`。秘密扫描、文件 SHA-256/大小清单与自有 DB/schema/连接释放结果见 `secret_scan.json`、`manifest.json`、`resource_close.json`，封存时由实际脚本写入；没有关闭共享服务或删除其他 Agent 对象。下一步先冻结 Must 1 最小修复并复跑该原样本、原合法/非法 package 输入与来源 writer/jobs；只有限定复核通过后再进入剩余 R04 live/UI 验证。

## 7184dc6 定向复核与问题闭合

主控已冻结 `7184dc63525ae3e8ea439ec64fc03dfaa629f7a8`，tree `ac9208e31abfb91deefe7959bcaecb3be3f3f2b7`。本 reviewer 新建第二个干净工作树 `C:/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review-fix/dianzi` 与分支 `codex/review-r04-pipeline-fix-20261015`；未 cherry-pick、修改业务或用活目录测试。该提交本身只改六文件；相对 95 的完整历史还包含 read-service/HTTP transport 和作者报告集成，**这些其他组件的后续审查结论仍由指定 reviewer 负责**。

修复仅对两个可选 package 身份字段增加 `_optional_package_text`：长度不超过 10000 的空/全空白字符串返回 `None`，其余仍通过原 `_text`，非字符串/NUL/surrogate/超限空白继续拒绝。没有降低来源长度限制，没有猜包名、改来源类别或丢弃范围。真实 fixture 与独立保存 raw hash 完全相同。原失败测试文件与复跑文件 SHA-256 同为 `bb4b79d949ac7c044a23decd4f0978813ac8f8f91c9f86df2c920ef26ab34bbe`；未改任何输入或期待使其通过。

| 定向检查（`recheck_7184/`） | 实际时间 +08:00 | 结果 |
|---|---|---|
| `actual_vendor_original_red_green` | 14:20:09–14:20:16 | 原两个 red 变为 **2 pass**，exit 0：normalizer 的未知包归属/range 保留 + 自有真实 PG 全十成员持久化/raw 重读；第六修订无虚构 affected_product/版本事实 |
| `original_writer_25` | 14:20:09–14:20:46 | 原 **25 真实 PG** pass，exit 0，0 skip |
| `pure_unit_fixed` | 14:20:09–14:21:05 | **514 unit pass**，0 fail/error/skip，exit 0；包含新 missing-package 9 用例；raw `3079/5036 = 61.13979348689436%`，1957 missing、42 既有 excluded，原 60 门通过 |
| `fixed_source_and_jobs_pg` | 14:20:58–14:21:25 | **25 真实 PG** pass（来源 10 + 既有任务 15），exit 0，0 skip；新增真实十公告页经 job/PG 成功、cursor page 2 |
| `fixed_independent_negatives` | 14:20:58–14:21:23 | 原独立 8 补充 PG/MinIO 用例全部 pass，exit 0，0 skip；继续覆盖第二页/空页/租约/错误分类/GC |
| `fixed_static` | 14:20:58–14:21:03 | Ruff/format/mypy 三命令 exit 0，75 格式文件、70 源码类型检查 |

全部新命令在新 WT 后端、独立 Linux venv `/tmp/dianzi-r04-pipeline-review-fix-20261015/venv` 执行；coverage 仍为原审查独有目录下新的 label，不与原 95 或主控共享。新 CBM 项目 `dianzi-r04-pipeline-review-7184dc6`、独立 cache `/tmp/dianzi-cbm-r04-pipeline-review-fix-cache`、allowed root 仅新 WT `backend/src`，实际 index 70 文件、926 nodes、4360 edges，0 skipped/partial/unusable，cache 中的 `__pycache__` 目录明确排除；13 命令全部 exit 0。native Windows Git 新树 status 为空，70 源码 blob 全匹配该 SHA，证据为 `candidate_fixed_windows_git.json`。

**Must 1 关闭于上述固定修复版本；对 source_jobs 的综合 Ship 结论已因 Must 2 撤回。** 原正常 fixture 只证明整数 page 假设下的事务/续接，不证明真实 provider 分页。95 失败、原初审报告与初始 manifest、原 7184 通过附录和 `manifest_7184_before_pagination.json` 均保留，不用新通过覆盖旧失败。当前读取/HTTP transport 的其他新提交未被本复核独立签认。真正两源实际 worker/PG/MinIO/浏览器闭环、完整 R04、真实模型、正式指标、R16 更新传播和阶段门仍待其各自证据。

初次秘密启发式把 DSN 的公共结构八字节命中 57 次、MinIO access 标识的公共路径片段命中 30 次；完整 DSN/access、真实密码/secret 及其八字节片段都未匹配。初始启发式 JSON 原样保留为 `secret_scan_heuristic_first.json`，未改日志/测试/原样本抹除命中。最终扫描只把完整 DSN/access、完整与任意八字节 password/secret 视为秘密匹配，结果与自有 schema/连接为 0；详细 scope 与最终文件清单见扫描/manifest 收据。

下一步先冻结 Must 2 的真实 cursor 修复，独立复跑原 body/Link、异常 Link/no-SSRF/legacy cursor、PG 提交和真实后页；再完成剩余 R04 实际两源 worker→PG/MinIO→API/页面证据，并引用原 API reviewer 和共享传输 reviewer 的独立结果。当前不得以本审查签来源装配、完整 R04 或 G-B。

主控已将分页修复派给未参与本 review 的实现 Agent；本轮依其有界槽位安排到此停止，后续新固定 SHA 再定向复核。所有独立测试进程已结束，专用库保持空测试 schema/零其他连接供复现，未删除整个数据库；自有 MinIO 桶已清理，未停止共享服务。没有新外部 source GET，避免重复匿名配额使用。
