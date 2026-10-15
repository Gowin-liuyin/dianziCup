# R12 / T30 全库混合检索内部准备

内部包状态：awaiting_review；实现 complete（仅本次授权内部双路切片）；unit/contract/security/integration passed；semantic live passed（仅真实本地 E5/重排 + 合成中英样本）；frontend/e2e/manual、正式多跳问答/live/完整 R12/T30 验收 not_run。作者未签 accepted、未改 progress、未推送。

固定基线 `e310f7735bd499c4d9fbcefe8a644e2309a16a62`；分支 `codex/r12-hybrid-retrieval`；worktree `D:/wt/r12-hybrid-retrieval`；测试冻结代码 `f316a7aa432d6f730fa49189814c2559be8b6db4`（本地提交 fb8b5dc + 405fb57 + f316a7a）。证据归档另提交，不改变测试过的源码。报告和逐文件材料 SHA256、Git/source blob 核验见自有 run 的 `materials_manifest.json`；该 manifest 为避免循环哈希不包含自身与其归档命令日志。

## 范围与安全独立理由

已读 AGENTS、00 执行图、恢复 R12 原卡/manifest/requirements、原 T30、03/04/05/06 合同、最近 handoff 和 R05 模型/PG报告。独立 T30 内部检索只消费已支持 claim 与已核验 EvidenceSpan，不执行 R11 资产四态判断、不产出多跳结论、不连 answering/API/auth/前端。缺 R10 图/完整 R11 前置因此不会扩大本内部准备权限；仍阻断正式 R12、G-D、原 T30/T31 最终过门。图未配置时明确 graph_not_configured/partial，不伪装召回。

本次只新增 `retrieval/hybrid.py`、`hybrid_contracts.py`、`hybrid_schema.py`、`indexing.py`、`opensearch_client.py`，直接 unit/contract/security/integration 测试、显式 synthetic fixture、自有设计提案/报告/run 脚本和证据。R05 `service.py` / `persistence_models.py` 单事件公开限制保持原样；shared models、迁移、settings、lock、runtime、API、auth、answering、gold、阈值、指标分母和 progress 没有修改。独立 schema 元数据已交 root 作为 0020 输入，迁移及 authority FK/worker 注册仍由 root 集成。

## 实现

`HybridRetriever.retrieve(AccessScope, HybridQuery)` 接收服务端身份、问题与时区明确的可用时间上下界；不接租户请求字段。精确 CVE 在 PG 中按 event_id + scope_key 关联并优先返回，即使 rerank 给相似事件更高分也不会挤走准确事件。OpenSearch BM25 与 PGvector 两分支分别在查询中先过滤 scope、public/tenant XOR、时间和模型空间；固定应用层 RRF k=60，再用现有 SemanticModels 重排。返回前分别核对 PG claim、支持关系、EvidenceSpan 坐标/hash、revision、document、source、event 的当前状态与所有层 ACL。重排之后再次核对事实与 scope epochs；期间撤回会被去除，epoch 改变则返回无证据并明确 partial。

永久 evidence_id 与 chunk_id 分开，chunk 由 event+claim+现有 R05 分块 ID 派生。PG vector 固定 384 / 精确 E5 模型空间；版本、维度变化拒绝并要求新 generation/index/full 水位重建。缺索引水位、新事实、失效候选、BM25 不可用、图未配和无受支持证据都有明确原因；空 hits 永远不声称全库无风险。精确结构化新事实可直接补查 PG，并保留 index_lag。

索引器校验可信 outbox 的 `pg:change:` 与 change_events scope，通过每 generation/scope advisory lock 串行完整快照刷新。OS bulk → refresh → 同 scope 旧 epoch 清理 → refresh 成功后，锁定/核对 PG epochs，才在同一事务替换派生 projection、写 watermark 和 receipt。失败/并发变化不推进水位。旧消息晚到按当前完整范围建立快照，receipt 重放幂等。OS generation metadata 校验支持创建结果未知后安全恢复，拒绝混用其他模型/维度。未调用生产 create_all；测试只在明确独有 schema 创建提案表。

客户端使用已有 httpx 官方 REST，没有新增依赖。只接受可信固定 base URL、专用 dianzi 命名索引，remote 连接必须 HTTPS，重定向禁用，错误不带响应体或凭据。提案配置、精确表列、接口与官方 Search/Bulk/Refresh 文档链接见 `docs/design/recovery/R12-hybrid-index-proposal.md`。

## 真实资源、命令与结果

日志根 `reports/runs/recovery_r12_hybrid_retrieval_20261016/`。所有实际质量/测试入口均有 `*.command.json`：完整 argv、cwd、+08 起止、退出码、code SHA、墙钟耗时及日志；pytest 数量来自保留 JUnit，不累加重复复跑。首次资源准备的外层完整起止没有独立 receipt，不能补造；resource_ready receipt 仅计其测试子命令。

唯一授权 GET `/` 在 3s 上限内返回 200，必要版本字段 OpenSearch 2.17.0；未打印 body/账户/秘密。现有授权 `connection.json` 通过 WSL 子进程 capture_output 仅内存解析，配置搜索键为空；DSN 仅派生到测试子进程 env。专用库 `test_dianzi_r12_hybrid_20261016`；真实 PG 16.14、pgvector 0.8.2。各测试使用独有 `test_r12_hybrid_*` schema、`dianzi_test_r12_*` index；cleanup 日志保存精确自身对象名，只删除自己创建的 schema/index。未 restart/flush/drop 共享服务或其他库。

| 冻结版本实际命令 | 结果与计数 |
| --- | --- |
| `project-python run_checks.py final_classified_fixture -m pytest tests/unit/test_r12_hybrid.py tests/contract/test_r12_hybrid_contracts.py tests/security/test_r12_retrieval_boundaries.py tests/unit/test_r05_evidence_chunks.py tests/unit/test_r05_embedding_boundaries.py tests/contract/test_r05_semantic_contract.py -o addopts= -q --junitxml=.../final_classified_fixture.xml` | exit 0；64 passed、0 failed/error/skip；30 新 fixture/unit/contract/security + 34 相关 R05 回归 |
| `project-python with_services.py final_classified_integration -m pytest tests/integration/test_t30_hybrid_retrieval.py -o addopts= -q -s --junitxml=.../final_classified_integration.xml` | exit 0；22 passed、0 failed/error/skip；2026-10-16T05:38:02.264424+08:00–2026-10-16T05:38:48.093287+08:00；命令墙钟 45.8297s，pytest 44.10s |
| `project-python run_checks.py final_classified_mypy -m mypy --cache-dir <仓外 r12 cache> src` | exit 0；122 source files 无错误 |
| `project-python run_checks.py final_classified_ruff -m ruff check <13 个直接源码/测试/run 文件>` | exit 0；无 lint 错误 |
| `project-python run_checks.py final_classified_format -m ruff format --check <同13文件>` | exit 0；13 files already formatted |
| `project-python cbm_checks.py` | 独立 CBM 0.11 fast 源索引/backend/src、schema、retrieval architecture、retrieve outbound trace 与 rg 交叉检查均 exit 0；不索引秘密、附件、holdout、run 数据 |

CBM 首次实际索引为 1533 nodes/7973 edges（最终刷新7975 edges），retrieval 函数/模型/证据读取调用存在；源码冻结后以 final_cbm_* 最新日志刷新。CBM 只是静态辅助，没有拿 graph 缺边推断没有运行接线。

原 C01–C06 对应：C01 精确 CVE 优先；C02 实际 E5 中英文向量 PG 余弦 top1 为支持证据，真实重排首位也为支持证据；C03 公共/同 tenant/其他 tenant/future 四组输入，两个真实分支 count=2 且 viewer count=1；C04 七类撤回/旧修订/失效事件/支持失败/ACL 隐藏均在重排前被清除；C05 维度/模型合同拒绝及真实 PG 投影事务未提交；C06 新 unindexed CVE 用 PG 补查并显式 index_lag。其余覆盖 outbox 乱序/并发/重放、scope 伪造、OS 失败、embedding 期间 epoch 改变、rerank 期间事实撤回和图未配。

真实语义样本只有三个公开合成正文：提示注入英文、中文和煮米饭无关正文；问题与原文在冻结测试/source blobs 中。使用现有核验 cache `C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime`，E5 `intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3`，重排 `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@1427fd652930e4ba29e8149678df786c240d8825`，空间 fingerprint 使用现有模块完整值。没有 hash 向量冒充语义；其余21个集成例显式 FixtureSemanticModels 只证明 SQL/REST/合同/安全边界，不计 semantic live。没有下载新模型或调用付费 API。

冻结最后中/英文完整 retrieve 耗时分别 4.2140s / 4.3281s（从 retrieve 输入到 PG 最终回查后返回，包含 embed/rerank）；BM25 0.0237/0.0357s，vector（含实际 query embed）1.8853/1.9847s，rerank 2.1601/2.2562s。其他校验与完整耗时保留原 trace。此为温热本地缓存小样本，无吞吐、准确率、召回率、冷启动、QA SLA 或评分达标声明。

## 首次红测与失败记录

`first_red` exit 2，1 collection error，原因新 hybrid 模块尚未存在；不算业务断言失败。`first_green` 7 passed。初始静态入口误用了 backend cwd 下的 backend/src 路径，5 E902；更正路径后保留实际 18 处样式项及2处 mypy 注解项，按格式/显式类型修正，未新增全局 ignore。

`integration_first` exit 1：6 failed/9 passed，多文档合成源固定 name 违反已存在 sources.name 唯一约束；只改 fixture 名为独有 source ID。`integration_seed_fix` exit 1：2 failed/13 passed，精确 CVE 子查询缺 event_id 关联（同 scope 相似事件错误进入精确候选），以及 bulk 更新未先 refresh 就 delete-by-query 返回固定 unavailable。原 HTTP 状态/响应体未保留，旧可见版本导致版本冲突是推断；增加 refresh 后该路径通过，不能把推断写成已记录响应事实。实际失败和修复回归保留。加入 event_id 关联及 bulk 后/清理后各 refresh，`integration_core_fix` 15 passed；补完整负例并冻结后22 passed。同一根因修复一次即取得进展，没有改旧断言、金标、阈值、分母或 skip。

## 未完成、影响与交接

本内部包不等于完整 R12/T30；F3/P3 仅有真实双路检索、权限/有效性回查与小样本语义行为证据，不给评分档位。root 仍须按提案集成 migration0020/authority FK、settings/worker 路由、版本化全库初建与现有 outbox 消费，安排全新 reviewer 审查和复跑冻结f316a7a。索引器完整范围刷新目前上限10000 chunk，超限会显式失败；其更大语料分区/增量扩展需另审。时间界限表示当前事实可用时间，不提供历史真值（R16前置）；graph 正式接线、资产结构化条件补查、多跳回答/引用论断、API/UI 和最终回答发布 epoch 锁定仍不在本授权范围。caller 提交回答前必须按自己的事务再次核对 scope/facts，不能长期缓存此返回快照冒充当前事实。

没有外部 live 资源阻塞影响本内部样本；正式前置、迁移/产品接线/独立审查仍未通过。下一建议：新 reviewer 先审 freeze + 64/22 证据及表列；root 完成最小0020/worker集成与其真实迁移检查，再按 R10/R11 前置恢复完整 R12。专用测试数据库保留作为复跑资源，具体运行寿命依赖已有 WSL 总段截止（2026-10-17 21:49:15+08）；本包未续期或改变共享服务生命周期。


封存前补了一处明确错误分类：HTTP401/403 → opensearch_permission_denied，timeout → opensearch_timeout，其余HTTP状态为固定安全码；检索partial区分bm25权限/超时。新增403/timeout合同断言不回显响应/请求秘密；f316a7a全部64/22与静态检查再次通过。

本包仅在自有 run 目录增加 `.gitattributes` 的 `-text`，使原始日志/XML/JSON/blob 字节不被 autocrlf 改写；日志/XML `-diff` 与既有证据归档做法一致，检查原内容仍以文件/哈希为准。没有更改根 attributes、源码检查或忽略规则。材料同时记录 raw SHA256 与 LF 标准化 SHA256；任务报告等文本 checkout 行尾不同可按 LF 值核验，原始 run 证据应按 raw 值核验。实际依赖版本完整记录于 runtime_versions.log。
