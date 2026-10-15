# G-A · R00–R03 独立阶段门审查 1

本次改动做了什么：把合同恢复切片、默认认证 API、PG 事实与任务、内容存储、受控网络和实际 Celery 消费组合成可运行底座。审查检查完整产品调用链，并在独立资源中复跑事务、权限、重启、分页与进程死亡恢复。

首次创建时刻未单独采集；本次写作开始实际读钟：2026-10-15T15:09:58+08:00；最后更新与完成时间见报告末尾。审查者 `/root/g_a_checkpoint_review` 未参与本批实现，只写本报告及专属运行目录，未改业务、合同、进度、验收状态或 push。

**当前结论：代码与三个组合回归修复已取得独立通过；阶段文档和证据归档仍待固定提交复核。初始 `8f6bd9f` 不能直接 ship。** 本文不登记 accepted。后续文档复核结果追加于末尾，不覆盖初始失败。

## 1. 固定对象、授权与审查边界

| 对象 | 固定版本与位置 |
|---|---|
| 初审代码 | `8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce`；tree `1b9a94ac49b58ddd12debb40f173749dbd3110a7` |
| 初审独立分支/WT | `codex/ga-checkpoint-review-1-20261015`；`D:/dianzi-ga-checkpoint-review-1` |
| 三测试修复复核 | `b27a79d9bce769564e86034a164010b3fd176080`；tree `f8c8b6871af3572870efedc744f8a844d9c50b46`；独立分支 `codex/ga-checkpoint-review-1-recheck`；WT `D:/dianzi-ga-checkpoint-review-1-recheck` |
| 初始阶段文档 | 根工作区实际 `reports/stages/recovery/G-A.md`；只读副本 `G-A_document_snapshot.md`；SHA256 `38d63cfeb13c7da2e5bc29ff4b5d385e5338ccb8d146e5c5081bc65835cafc88` |
| 全部本轮证据 | `reports/runs/recovery_ga_checkpoint_review_1_20261015/`；每个实际测试的完整 cwd/argv/+08 秒级起止/exit 见对应 `*.command.json` |

两份 WT 各自 `uv sync --locked --group dev`，Windows CPython 3.12.13；Linux 使用独立 `/tmp/dianzi-ga-checkpoint-review1-20261015/venv`，同锁安装。初末业务 diff 均为 0。前端 build 生成的自有 `tsconfig.tsbuildinfo` 按 HEAD 原字节恢复，没有恢复用户工作区文件。未提交、未 push、未改原测试或阈值。

`8f6→b27` 的完整差异只有三份 G-A 测试和模型生成模块/直接模型测试。`ga_source_diff.command.json` 对 backend/src（排除 infrastructure/models）、frontend、infra、scripts、CI、contracts 实际 diff exit0；本阶段业务与共享 HTTP 无变化。模型修复由另一个非作者审查者负责，不能据本审的 G-A 结论扩大其范围。

已读仓库 AGENTS、00/11/12 的 R00–R03、原 T00–T08/T16/T17/T19/T21/T40 与其引用合同、严格解析的 requirements/manifest/state、CR-R01–09、R02 实施/维度、R03 执行及其网络补充、认证 CR 与 CR-R10、生效与专项初审/复核报告。`prompts/12_full_delivery_parallel_push.txt` 确认有界完整批次和独立阶段审查授权；外部资料没有被当作权限指令。官方 PDF 本地四页实际用 pypdf 提取并核对，未浏览第三方解释替代原文。

使用最新 Ponytail 5.2.0 full/review；源码、`rg` 与 CBM 0.11.0 图交叉。独立 cache `/tmp/dianzi-cbm-ga-checkpoint-review1-20261015` 只索引两份 src：backend 958 nodes/4496 edges，frontend 153/510；前端 fast 模式按设计排除10个测试文件，未用图推断其测试通过。backend parse_partial/unusable/skipped=0；已实际调用 architecture/schema/execute_job、consume_job、commit_page trace。图没有发现动态 Celery 注册的 inbound 调用，故以 runtime.py 显式 task 注册及真实消费补核，未把零 caller 误报成死代码。

## 2. 独立资源和真实输入

- PG 只从指定 root/0600 私有连接内存读取；先核对 loopback 25432 与原根库身份，再仅 CREATE 自己的 `test_dianzi_ga_checkpoint_review_20261015`，run ID `ga_checkpoint_review_20261015`。没有 drop、downgrade、清库或迁移旧 review/live 库。自己的库最终 head `0013_revision_source_metadata`，同库历史保留。
- Redis 仅 DB10、自有随机 queue；未使用主控 DB14、28000/25300。实际 Linux API 独立端口28012；worker prefork，结果 backend disabled。所有自有进程已退出，DB10 最终 key 数0。
- MinIO 只29400与自建 `test-dianzi-r02-ga-checkpoint-review-20261015` bucket。7项独立测试覆盖原文字节、跨进程、A→B→A、回滚、坏对象不覆盖、拒绝身份与并发。1200组合后15:12:52最终核对12个对象及 PG fixture 引用保留供复现，没有删除已引用对象。
- MinIO 原段在14:55:37结束，新受控段14:55:48启动至16:55:48上限；本审对象 IO 在新段执行。没有把11秒中断拼成连续运行。
- 一次固定公开 NVD GET：15:05:58–15:06:00，严格生产网关、显式 Cloudflare DoH、无 token、无重定向，HTTP200/3105 bytes，响应 SHA256 `3ccec6525f26d9effa2461cef0537447dd21cb6c290cf7c887a22c426d345f6b`。不是来源持续监测、模型调用或评分实测。

账号、来源和任务输入均明确是隔离合成 fixture；从未调用付费模型、测绘、第三方扫描或下载 PoC。实际服务成功不是把 fixture 当真实情报。连接秘密不进 argv/报告；精确真实私密值与 DB 密码/MinIO secret 连续8字符扫描无命中。access identity 的若干8字符碰撞位于既有公开路径/安装文本，精确 identity 0命中，单列 hash 分类，不删除日志或把它们当秘密泄漏关闭。

## 3. 本阶段行为核查

**R00：** JSON object_pairs_hook 严格拒绝重复键；60个原 T、13个要求、初/决赛分值各100。manifest 保留原依赖/order/C01–C06，recovery.requires_slices 是执行依赖，original_task_aggregation 仍要求全部切片和最终原前置；R24-A→R23→R24-B、R19 准备/正式冻结分开。旧 accepted 纠偏保留 history，未把后续整卡或 live 默认写 passed。CR-R01–09 的准确生效来自既有独立意见，本审没有重写批准或评分口径。

**R01：** 默认 create_application 装 DatabaseUserDirectory+PgAuthenticationStateStore，认证路由不会因缺配置消失。真实 readiness 逐项检查 PG migration、Redis、搜索和 PG 中 worker/scheduler 观测；not-ready/降级返回503。实际28012 API 与 prefork/beat 启动后15:03:49为ready；15:03:51实际 API 子进程重建后同 Cookie 可读同账号，注销后401；停止 worker/beat 后15:04:34两项观测均 stale，API503/degraded，DB/cache/search仍ready。`runtime_health.json` 有4条独立断言及所有 PID 收尾。搜索本次使用隔离 HTTP/test 服务；没有把它冒充新 HTTPS/生产 TLS 验证，TLS既有专项范围另保留。

**R02：** 真实 PG 64项独立检查覆盖跨进程会话/撤销、限流/审计权限、知识发布回滚、并发同key、历史修订、稳定ID/事件操作、关系身份、不同authority/ecosystem/分支不误替代、维度失败后同输入新尝试、空库和0006/0009前向升级。MinIO7项另实际复跑。PG依旧事实、版本、权限、任务唯一权威，未用缓存或 Celery 结果填补数据；新应用实例和独立进程都已核查，未把单个TestClient叫完整进程重启。

**R03：** `runtime.consume_job→execute_job→claim/require_lease/read_payload→固定handler→complete/retry` 与 `dispatch→recover_expired→outbox relay` 真实可达；处理结果与完成状态同 PG 事务。两个 Linux prefork worker+beat 的实际检查2项通过：重复投递一效果；强杀进程后未提交副作用为0，约60秒租约后接管，attempt1→2且只一效果；broker暂不可用保留未发布outbox，发送后回滚/重放仍一效果。未测试 task hard time limit，强杀恢复不能冒充硬时限验证。

54项游标检查保留业务断言，只在本审副本适配专库身份/head/输出位置；回执完整指纹、terminal/exhausted 引用拒绝、失败页不推进、final重新核查前页恢复引用、legacy NULL明确失败、live/backfill与过期generation拒绝均实测。后续 b27 的原49项无需副本适配即可直接通过。网络单元/安全负例覆盖私网重定向、DNS/peer/SNI/CA、总deadline、错误分类、metadata脱敏和单层重试；真实网关 GET 另单列。

真实来源分页/NVD-vendor业务广度、九维算法、图/语义检索、真实模型问答、Agent协作等仍属 G-B 以后；本审未把合理后段缺口制造成本阶段阻断，也不把它们宣称已通过。未注册的后段 job_type 明确 blocked，不声称已有消费能力。

## 4. 发现、触发、最小修复与复验

以下三项为已证实质量/回归门缺陷，影响 R01/R03 阶段可重复验证；不是未经证实的生产数据丢失。

1. **当前 head 被旧游标 fixture 拒绝。** `backend/tests/integration/test_r03_cursor_persistence.py:70–72` 固定0012；当前真实库0013时27项及其复用 fixture 的22项全部 setup error。预期应检查当前候选 schema，并执行原业务断言；实际49项未执行。最小修复用官方 Alembic ScriptDirectory(MIGRATIONS_DIR).get_current_head() 对比，不跳过迁移或放宽错误。root b27已按此修复；本审98组合及同库重复均通过。原49错误原件保留。**closed at b27。**

2. **任务引用测试与已有公共发布冲突。** `backend/tests/integration/test_r03_jobs_pg.py:208,230` 把新 change_events 写死 public/epoch1；先跑知识发布或在同一库再跑时触发 uq_change_scope_epoch，而不是完成引用/摘要/越权断言。最小修复复用已有 PG 原子 bump_scope_epoch，不清库或删历史。root b27已修；同库连续两次98项通过，引用/摘要/越权断言未删。**closed at b27。**

3. **跨盘 nested pytest 扫到 Windows 系统目录。** `backend/tests/contract/test_r01_quality_checks.py:181–201` 在 D: worktree、C: tmp_path 时未限定 child rootdir，实际对 C:\\Documents and Settings 扫描 WinError5，返回2而不是故意断言失败1。独立只含合成DSN的最小probe给出同错误；因此原脱敏行为尚未测到，不能用该失败称脱敏已通过。最小修复显式 `--rootdir=probe.parent`，保留原 outcome/终端/JUnit脱敏断言。root b27已修，本审两次98中原例均通过。**closed at b27。**

4. **冻结提交缺11份已引用证据。** 初审8f6 `verify_plan.py` 实际 exit1：R01行为最终、runtime cache、search TLS报告、R01-runtime-recovery任务报告；R02.md、default_auth_resume.command.json/.xml、credential_failure.observed.json、relations_fix_first.command.json、MinIO和dimension报告均 EVIDENCE_ABSENT。根WT存在的未跟踪文件不能自动成为固定提交的一部分。影响 R00/R01 的干净检出可核查性及阶段交付；最小修复精确归档必要证据和当前阶段快照，随后在新文档提交独立运行严格 verify_plan。**文档固定复核 pending，未拿当前可变文件存在签过门。**

没有以无复现担忧、风格偏好或后段能力作 Must。没有删除困难测试、改 gold、改计分分母、改覆盖门或把失败改 skip。

## 5. 独立实际命令与结果

日期均2026-10-15、+08:00。下列缩写路径对应每份 command.json 中的完整 argv/cwd；所有计数从 JUnit testcase 逐项计算，重复运行不累计独立案例数。

| 版本/检查 | cwd与实际命令范围 | 开始–结束 | exit；结果 |
|---|---|---|---|
| 8f6 全unit | 初审WT/backend；`python -m pytest tests/unit`，原60覆盖门 | 14:55:23–14:56:01 | 0；678/0失败/error/skip；raw3511/5421=64.766648% |
| 8f6 真实PG核心 | 同上；9份R01/R02/R03 migration/auth/knowledge/dimension集成文件 | 15:02:35–15:02:58 | 0；64 passed |
| 8f6 真实MinIO | 同上；`test_r02_minio_persistence.py --no-cov` | 14:58:21–14:58:26 | 0；7 passed |
| 8f6 游标适配副本 | 同上；原27+22+5断言，仅身份/head/输出适配 | 15:02:28–15:02:32 | 0；54 passed |
| 8f6 Linux队列 | `/mnt/d/...初审WT/backend`；独立复制原Celery两项，资源/进程死亡适配见脚本 | 14:59:00–15:00:40 | 0；2 passed；Linux prefork、实际beat |
| 8f6 实际API运行 | Linux同上；28012/prefork/beat，真实PG/Redis/search | 15:03:37–15:04:34 | 0；4个运行断言，非pytest数量 |
| 8f6 网关一次GET | 初审WT/backend；`probe_gateway_once.py` | 15:05:58–15:06:00 | 0；NVD200/3105bytes，非持续采集 |
| 8f6 Ruff/format/mypy | 初审WT/backend；src/tests/scripts；mypy src | 14:59:27–14:59:28 | 全0；171格式文件/72 source类型文件 |
| 8f6 npm ci | 初审WT/backend；`npm --prefix ../frontend ci` | 15:03:58–15:04:02 | 0；300包审计0漏洞 |
| 8f6 frontend lint/type/test/build | `npm --prefix ../frontend run ...` | 15:04:24–15:04:46 | 子命令全0；120 test，0失败/error/skip |
| b27 修复组合 | 复核WT/backend；原cursor27+fixes22+jobs15+quality34 | 15:06:51–15:07:01 | 0；98 passed |
| b27 同库原样再跑 | 同上，同一PG库，没有清理历史 | 15:07:02–15:07:12 | 0；98 passed |
| b27 全unit | 复核WT/backend；原60覆盖门 | 15:07:01–15:07:36 | 0；686 passed；raw3515/5426=64.780686% |
| b27 阶段完整相关组合 | 复核WT/backend；unit+contract+security+上述真实PG/MinIO/原49游标/任务集成文件，完整argv见ga_combined_b27.command.json | 15:09:41–15:11:24 | 0；1200 passed，0fail/error/skip；混合raw5126/6032，不替代纯unit门 |

初始失败严格保留：`pg_combined.xml` 为1185项/4fail/49error/0skip；`pg_replay.xml` 为507项/4fail/49error/0skip；`contracts_pg_isolated.xml` 为379项/1fail/0error/skip。前三次 runner 错把产品 DATABASE_URL/REDIS_URL 注入缺配置测试，造成3个预期不一致；修正只注入 TEST_* 后仅剩上述可复现三测试缺陷。`contract_security.xml` 初次不提供PG，10个资源错误是本审调度缺资源，不报业务失败。`minio.xml` 初次685项中的1fail同属错误注入产品配置。不得把这些失败计为通过，也不因此误报实现缺陷。

本审工具错误另留存：第一版 runner 把连接清单整数也当秘密字符串，测试完成后脱敏整理 TypeError，未生成可信 stdout 回执；原JUnit保留并另次复跑取得完整回执。前端 build 子命令exit0后 wrapper 的GBK打印UnicodeEncodeError；UTF8原日志和exit0 command回执已先保存，外层失败没有被倒写成成功。Linux适配原测试的过程receipt仍有旧 `redis_db:8`/`pool:native solo`模板文字，实际guard已固定DB10、argv为prefork；以适配脚本、外层linux_worker.command.json及实际prefork runtime日志为准，旧字段不冒充事实。上述均为审查工具问题，不改产品测试 outcome。

初始覆盖二进制曾位于自有run目录，已移动到仓外 `%TEMP%/dianzi_ga_checkpoint_review_1_20261015/coverage/`，新runner直接写仓外；JSON覆盖证据保留。混合覆盖率包含额外子进程/范围，不替代纯unit分子分母。

## 6. 合同、评分和未覆盖范围

R00原范围、原T最终合并、13要求和两阶段各100分不变；本审无新增合同偏差。R02 typed事实/维度和 R03 fingerprint/lease 的细则由主控既有CR冻结，本审按其检查，未把实现者报告当批准。

E1/R2支持认证、依赖健康、持久事务、可消费任务和故障恢复底座；F1/P1支持有界采集游标、失败分类和一次真实网关请求。F2只证明事实/维度的持久与证据边界。它们不能折算成时效、准确率、问答或任何满分；U01/U09/U10只取得本阶段基础能力证据。

未在本审新跑：全Docker Compose冷启/全部profile、HTTPS OpenSearch自有故障容器、MinIO服务本身重启/生产TLS/备份恢复、浏览器e2e/manual、task hard time limit、真实来源全自动连续监测/新版本两源业务页、模型/embedding/rerank/图/真实多跳/测绘/正式盲测与性能。前述TLS/缓存等存在旧非作者专项有限证据，已读并保留边界；本审不把其次数计为自己的新测试。未运行不代表失败，也不能标本轮passed；最终功能验收仍留在相应原T/R后段任务。

## 7. 当前结论与下一步

初始8f6有三项已证实质量门问题和11项冻结证据缺失，初审结论 needs_changes。三测试修复b27已独立关闭，G-A生产源码对8f6无变化；完整1200相关组合及同库重跑通过，真实PG/MinIO/队列/重启/网络及原60门已有本审证据。只要新固定文档提交补齐证据、更新准确阶段快照并通过独立严格核查，就可给出**仅G-A能力范围**的 ship 意见；当前尚未签该文档或阶段accepted。

下一步由主控提供文档归档SHA；本审只核查精确差异和verify_plan，不重跑不受影响的业务。主控依据最终独立意见登记状态、选择文件及阶段push；本审不代签accepted、不push。后续真实问答、九维、监测广度、正式安全/评测与材料继续按原DAG验收。

Not checked：上述后段、生产部署和正式live/人工范围。已测底座不等于完整系统交付。

本轮代码/测试复核证据截止：2026-10-15T15:12:52+08:00。最终资源收据 `resource_closure_after_combined.json`：PG head0013、DB10空、全部自有PID不存活、真实私密值及secret连续8字符无命中、access identity精确值无命中。

**Verdict: needs_changes — 只剩第4项的固定证据与阶段文档归档复核；第1–3项在b27已closed。** 未签accepted、未push。文档固定提交送审后可由本reviewer定向复核，不必重跑源码未变的1200项。
