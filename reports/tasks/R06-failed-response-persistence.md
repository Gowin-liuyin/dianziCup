# R06 · 失败响应原文独立持久化

报告实际文件创建时间：2026-10-16T00:52:32.366161+08:00；冻结时间见 artifact_manifest。任务状态 awaiting_review；本失败留证切片 implementation complete；整 R06/G-C 不在本包自行验收。固定基线 c3a2abc9a5246993eabb351d26cfeb51d0270b31；工作树 D:/wt/r06-failed-response-persistence，分支 codex/r06-failed-response-persistence。代码提交 e192234550fdd1c405d165a7a93772a952b8ea5b；没有 push、accepted 或全局 progress 修改。

根因是实际 `_fetch_catalog_page` 先 normalize 后返回响应，失败 body 无法到达 collector 的 register_response_content；executor 的业务事务失败回滚也不能承担留证。独立 CBM src-only index/schema/architecture 和 `_fetch_catalog_page`、build_source_page_handler、execute_job、register_response_content 的 both trace 已执行；最终 1265 nodes/6394 edges、0 skipped/partial/unusable，源码 rg 全 caller 在 callers.log。最初成功 CBM 输出在本 run 冻结前被最终刷新覆盖，只冻结最终索引收据，不以最终日志冒充首次索引时刻。

读取了 AGENTS、00 执行索引、12 中 R06、03/04/05/06、T08/T10–T16/T49、当前进度/交接，以及主工作区的 R06-integrated-live.md、R06-live-failure-diagnosis.md。使用 Ponytail 5.2 full；release/AVID 的 c3 兼容修复不重写。未创建额外 daemon，未读取 provider 秘密，0 新外网、模型、测绘、付费或 PoC 请求。

## 文件和小合同

本包产品只改 ingestion/source_jobs.py 和新 ingestion/source_failure_receipts.py。直接测试为新 test_r06_failed_response_boundary.py、test_r06_failed_response_persistence_pg.py、test_r06_failed_response_legacy_pg.py；旧 test_r04_source_rate_limits.py 仅补两行明确 recorder/get_bind Mock 夹具，原期待不改，生产代码没有无数据库后备。

主控独占并提供依赖 114c42d645e237e20c9812fcc79d63f0f2e96717 与 a2be6ef4ad6407897b68352300dadd101f247c21，在本树分别 cherry 为 10b9b5f、33ff7bc：0016_source_response_receipts、source_failure_models、knowledge/revisions GC 引用保护、CR-R06_failed_response_receipts.md。本作者没有占迁移号或修改公共模型/认证/设置/worker/runtime/API。字段、约束和数据库三值逻辑以该冻结 CR 为准。

输入是 handler 的可信公开 system_admin scope、已提交 PG job/attempt/worker context、固定 source/stream/window/cursor 和服务端构建的有界请求。记录前核对已提交 job 类型、public tenant、运行租约、attempt 与 job payload source/stream；实际 lease window 可早于本次 request window 以保留已有窗口恢复语义，不能晚于 request 或当前观察时刻。

输出是独立 PG 事务中的响应收据和内容引用：hash 锁 → ContentStorage 写入及 hash/size/字节读回 → content_objects → deterministic job/attempt/ordinal 收据 → commit。主业务事务仍负责文档、事实、游标、continuation/outbox 和任务结果。收据提交失败不解析、不推进 cursor；对象写入或读回失败只保存准确 metadata，然后有界 retry；业务 rollback 后原文引用仍有效。GC 拒绝回收收据引用的 hash。

HTTP200 通过来源 MIME/5MiB 边界后保留完整实际 bytes，包括真实空 body 的空 hash。HTTP 非200 在现有网关不会读取 body；没有 FetchResult 的网络失败也只保存 nullable HTTP/hash/size metadata，不制造原文。result.final_url、header、异常文本、正文、身份及秘密均不进收据或日志；请求与游标只记录 SHA256。

received/normalized/normalization_failed/transport_failed 不替代 PG job 或 cursor 状态。AVID tree/blob 分别留证，tree 解析成功后单独 normalized；第二响应失败保留两次身份。body 已收到但后续总 deadline 超限时保留 received + network_timeout，不能标 normalized，也不能把真实 body 丢弃伪称不存在。解析失败仍使用原 source_response_invalid/blocked；网络与限流保留原 blocked/retry_wait/permanent 策略。

## 实际命令和结果

所有 pytest/mypy/Ruff cwd 为本树 backend，运行本树 Python 3.12.13/.venv；`uv sync --offline --frozen --extra semantic` 实际 exit0/92 packages，无锁文件修改。sync 的起止时间没有单独捕获，不补造。run 下同名 JSON 保存完整 argv、cwd、实际起止/退出码，XML 保存测试计数，log 保留原输出；旧 early checks 在未提交 diff 上执行，未捕获其逐文件 launch hash，最终源码 working/git blob 两种身份在 frozen_source_identity.json。

| Run / 核心命令 | 退出及真实结果 |
|---|---|
| pg_baseline_red：固定 c3 main/src PYTHONPATH，`pytest -p tests.conftest <run>/test_before_fix.py --no-cov` | exit1，3 failed；坏 arXiv/release/OSV HTTP200 原文无 PG 引用 |
| pg_initial：`pytest tests/integration/test_r06_failed_response_persistence_pg.py --no-cov` | exit1，26 setup errors；主控迁移 sa.Bigsa.Integer 拼写错误，未计业务失败；a2be 修复 |
| pg_recheck：同新 PG 文件 | exit0，26 passed，23.50s |
| pg_extended：新 PG 文件 + 原 test_r04_source_jobs_pg.py | exit1，54 passed/1 failed；新 schema 夹具以 TIMESTAMP.__str__ 与带时区 compile 比较不一致，改为两侧 dialect compile；原两源19用例全部 passed |
| pg_final：新 PG 文件 | exit0，37 passed，36.29s；真实 INSERT 拒绝、数据库约束、子进程 PG/raw 重读和 deadline body 保留通过 |
| pg_contract_delta：同文件 `-k approved_contract` | exit0，6 passed/37 deselected，5.27s；六个旧失败场景的新冻结留证合同 |
| pg_legacy_unchanged：新 wrapper 调用原九源 worker 测试函数对象 | exit1，27 passed/6 failed，37.07s；六个旧 content_objects==0 期待与已批准 CR 冲突，详见下段 |
| unit_initial：新增 boundary + 原 source_worker | exit1，62 passed/1 failed；新测试遗漏 JSONDecodeError 属 ValueError，修正测试异常类型 |
| unit_recheck：五个相关文件 | exit1，303 passed/3 failed；原无 bind 单元夹具缺 recorder/get_bind 注入，补两行夹具 |
| unit_fixed：同五文件 | exit0，306 passed |
| unit_related：12 个来源相关 unit/contract 文件，完整列表见 JSON | exit0，568 passed；1 已知 Starlette deprecation warning |
| pg_frozen / pure_frozen：上述完整43新PG与12纯文件，在 e192234 冻结代码上 | 各 exit0；43 passed/35.29s 与568 passed，无skip |
| mypy_candidate：`python -m mypy src` | exit0，95 source files |
| mypy_frozen / style_frozen / formatting_frozen | 各 exit0；冻结 e192234 上95 source files类型和六个产品/直接测试文件check/format通过 |
| ruff_delivery / format_frozen | exit0；产品和直接测试 check/format 通过，代码 git diff --check exit0 |
| CBM 最终七条命令 | 各 exit0；src-only，最终索引统计见上 |

真实 PG 只使用 test_dianzi_r06_catalog_failure_receipt_20261016，DIANZI_TEST_RUN_ID=r06_catalog_failure_receipt_20261016。复用 catalog_engine 的专库前缀检查与 UUID schema；没有使用原硬编码 exactDB 的 worker fixture。DSN 从获准 WSL private test-services connection.json capture 到内存，未写到 argv/报告。每次收据 public_tables 前后均 []，每例只 drop 自有 schema，无旧业务库、生产库或旧 collector 库写入。首次 private 配置调用挂起，手动中断工具 session exit1，精确启动/阶段未捕获；其后主控恢复 PG 再执行测试，不将中断算业务红。

原始产物用 git -c core.autocrlf=false add 登记，并逐 index/blob SHA256 核对原 bytes；源码 working 与 git blob 的换行身份分别保留。材料 diff --check 因原始 Windows CRLF/失败行尾空格报错，不改写 raw 日志来消红；主控已收到本 run 精确 -text/CR-at-EOL 属性集成需求。该错误是证据文本检查边界，不覆盖源码 diff 检查结果。artifact_manifest 与 secret_scan 是本 run 最终冻结的元数据，允许在封存前刷新，不把其创建时刻冒充业务测试时刻。

## 六类验收与原期待冲突

坏 JSON/XML/非法成员覆盖原两源与新来源，HTTP200/hash/size/raw 读回一致，blocked 结果准确、无业务发布或 cursor。对象写/读回失败有 metadata 无伪 hash；实际 PG INSERT CHECKfalse 拒绝保留 retry 状态并阻止 parser。业务 PG/OSError、资料写后、cursor commit、continuation 失败全部 rollback 文档/证据/claims/events/成功 fetch/游标/后续任务，独立 raw 仍留存。重放 unique job/attempt/ordinal、冲突拒绝、并发 receipt/重复 worker 以及 GC 拒删通过。public scope、tenant/owner/attempt/expired context 与 synthetic secret 元数据负例通过。错误 body 不进入成功 fetch 或文档计数；修复 parser 后可从 retained bytes 重处理，原 failed job 历史不改。独立新 Python 进程验证 PG 和 raw 可读。

原 test_r06_source_worker_pg.py:283 的 all-content-rollback 期待没有修改。其 second_document、cursor_commit、continuation、invalid_page、blob_corrupt、blob_limit 六场景在 raw content_objects 计数得到1或2，原期望0，故 pg_legacy_unchanged 保留6失败；不是 skip，也不是宣称全 suite 通过。批准 CR 改为独立 raw/receipt 留存，其他业务效果仍0；新增六个同输入、同触发场景逐一验证这些剩余断言并成功。该合同变更与旧回归裁定仍交新独立 reviewer，不自签关闭。

## 主控集成 caller 和限制

实际生产 caller 是 workers/runtime.py:100 的 SOURCE_JOB_TYPE→build_source_page_handler（继续使用部署 ContentStorage），source_polling.py:129 的 enqueue_source_page，api/source_routes.py:170 的认证 collect 和 :198 的 PG job 读取。前端 api/source-client.ts:5 collectSourcePage、features/sources/source-workspace.tsx:80 仍消费既有 SourceJobResponse，不消费新收据。后续由 root 独占 API/readonly 管理员收据读层与 UI：关联 job_id/attempt、实际 parse_outcome/错误码/hash/size/观察时刻；不能从 received/normalized 推断 live 或成功文档。当前没有增加 API 字段或任意原文/URL读取入口。

上线本入口先执行0016前向迁移并保留旧历史，根合同不允许破坏性 downgrade。真正 MinIO 后端、新版本默认 worker/API/UI/真实来源端到端、来源八类 live、人工验收与长期窗口本轮 not_run；本轮 PG + local ContentStorage 属明确 offline fixture integration，不冒充 MinIO/live。arXiv 原失败 bytes 仍不存在，其初次解析根因仍 unknown，本补丁只防止以后同类证据丢失。前端、完整全局覆盖率和全部项目回归未执行，六个旧期待冲突不隐藏。

E1/F1/R1/T08/T16/T49 仅登记失败可追溯、PG 真值、恢复/权限和原文留证的上述代码/测试证据；不登记官方评分、准确率、时效、性能、连续运行或整 R06 验收。下一建议为 root 合并合同依赖与此代码，安排新非作者冻结版本复跑，随后受控验证 MinIO/默认入口和管理员读层。报告、文件列表、原命令/退出/计数与 SHA 清单在 recovery_r06_failed_response_persistence_20261016，只进入 awaiting_review。
