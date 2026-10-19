# G-C / R10 PG 证据图只读切片 · 初审 1 Fix2 定向复核

结论：**限定 Ship**，仅固定 PG 只读 service/router 工厂及本次修复范围。原 9 项 probe 首跑、重复跑均 9 passed，原四个红例已闭合；本轮 163、相关 103、共享 122 的实际重跑均通过。下文保留旧验收红例和绕过 epoch 协议的故障注入红例，不能据此宣称所有测试为绿。整个 R10/G-C、产品 App、Neo4j、UI 和 live 不在本签署范围。

本次改变关系极性检查和 RC 锁集合。否定/未知的论文分析与攻击机制保留 gap；肯定句中缺过滤、not only、月份 May、中文不受信任保留支持。锁集合来自本次实际可见输入；加锁后仍完整重读当前 PG 输入，不按旧 ID 筛选新查询。规则为 `r10-graph-1.2.0`，内部 schema=1、GraphSnapshot/GraphEdge 字段及两个 gap reason 不变。没有新增 NLP/模型或将 PG supported 事实写成撤回。

## 固定版本、权限与材料

- 实际 reviewed commit：`08b141bd437c1de70a8435a1f7f6c448a131ed0d`；tree `17d15ef9dc0d744f74cb44e47a4930d98a6a4421`。
- 核心代码冻结 `11d24131aff176cc97f138d2e4a222cd378590d4` → 08b 的 `backend/src` diff 为空；08b 增加 8 个源/目标正文覆盖 PG 用例。本轮导入和所有测试使用 08b。
- 独立 WT：`D:/wt/r10-graph-recheck2`，分支 `codex/r10-graph-recheck2`。own locked editable venv，`ai_intel` 导入路径已实际核对。没有实现参与、spawn、业务改动、改原测试/probe、progress/accepted 或 push。
- 本轮交付是新报告、新 run `reports/runs/recovery_r10_pg_evidence_graph_review1_recheck2_20261016/` 及主控明确授权新增的范围补充CR `docs/decisions/CR-R10_graph_fix2_review_scope.md`；原初审/定向复核报告和封存内容仍独立保留。
- 已读 AGENTS、执行图、恢复 R10、主计划 6.2、T17/T21/T22/T23/T41、docs03/04/05/06/public_api_v2、两份 CR 及 Ponytail Review 5.2.0。用户的中文和冻结/不 spawn 边界优先于技能输出语言/并行建议。

最终材料 `ff5aa737f37c7a591bee6758485e745a0e83b086`，tree `87b30406e45107f7b79e1918615922839d994ad6`。作者 manifest 共 120 项 raw/Git blob 字节、SHA-256、OID 与声明全部对应；源码/CR清单 9 项在固定代码、材料、独立工作树一致。manifest 原 raw 49057 bytes / `eec6981567e5f14047fce952a412006f5ae920e8c1fce7ce883f491e1d70e343`；冻结 Git blob 48088 bytes / `b9f956699957dc2b92392a7b3696230a0ef1f9930462fc35dd629dae8eed5edd`。前两次 reviewer 封存 247 项（83+164）全匹配；原红记录未改。

## 原问题复验

| 问题 | 固定版本证据 | 判断 |
|---|---|---|
| 否定、未确认论文仍强关联 | 原 `test_review2_pg.py` 两个 analysis 反例均通过，来源 value/quote/hash/坐标完全匹配仍保留 unknown gap | 修复证据成立 |
| 否定攻击机制仍映射 ATLAS | 原 `Untrusted instructions do not enter a model input.` 反例通过；新版英/中文否定/未知对照也通过 | 修复证据成立 |
| 私有无关联 claim 被公开请求锁住 | 原独立 held-writer 反例通过；作者 8 个 public/private、viewer/analyst、hidden/unlinked/linked 对照各 200、相同摘要、相同 25 SELECT，耗时 0.174–0.311s，无 40P01/55P03 | 请求范围锁隔离修复成立；不是全局侧信道消除证明 |
| 旧三 P1 一 P2 | 无关引文六反例仍拒绝；source/doc/revision 直接撤权、claim 撤回、event business_version、epoch、role/tenant/session 当前性回归通过；memo 每次请求重新校三父 ACL | 初审修复证据保留 |

原 9 probe 文件 SHA-256 仍为 `1b12f82583d8c067cc52d604c54aa53bddeb593c1cf8c2bfcccdc32d6d810c47`，首跑和重复的 9 case IDs 与前次红执行逐项相同。本次另自拟 6 个真实 PG 正例：ATLAS not sanitized、not only、不受信任；paper May、not only、无运行利用代码的中文安全说明，均产生对应 supported 边。不能以直接否定词全文匹配来得出拒绝。

六类强边均由当前 PG supported/source_verified/validated 支持产生；candidate/disputed/retracted/withdrawn/stale/current=false 门、真实 event_documents/external IDs 绑定、自然 CVE/GHSA 及非 CVE descriptor 对照通过。组件身份保留生态；反向组件→漏洞与正向边共用 claim/evidence。论文 source 与 target 的 doc/rev 完整且有效、三父可见性和 metadata_only/excerpt/unknown/blocks_complete=false 八种覆盖对照通过。PoC 保持存在性或静态状态，不成为运行成功/处置证明。

## 当前读围栏与保证边界

`graph_routes.py:60`–`:88` 先 RR 获取候选和实际输入，关闭事务；新 RC 锁当前 auth，完整比较 scope，再 `evidence_graph.py:351` 按 source→document→revision→event→claim/evidence/block/assertion→支持关联取锁，重读当前图，最后锁/比较 epoch，持锁序列化 JSON bytes。父级直接撤权不 bump epoch、撤回、版本变化均有真实 PG 409；角色/租户变化 403、session revoked 401。未知/跨租户资源固定 404，无任意 SQL、URL 或 DSL 参数，未知 query 422。工厂不静默落回 fixture。

writer 先锁父→epoch 的真实并发对照返回 409，无 40P01；reader 先持锁后在 JSONResponse 构建处启动 writer，独立复用原序列化 probe：200 bytes 已构建，writer 仍等待，响应锁释放后才提交。原 lock_timeout=5000 / statement_timeout=15000 保持；父锁超时实际 5.159s、503/55P03，未伪造空成功。

**no-epoch 增强只在已验证窗口成立。** 新 claim/evidence/event_documents 在首次 RR 读取后、RC fresh support SELECT 前提交，即使 fixture 手动不增 epoch，也因完整 fresh input hash 变化返回 409。本文没有把这推成任意时序的 DB 篡改容错保证。

独立补测在第二次、即 RC `SELECT DISTINCT claims...` **已经执行后**、epoch 锁前提交新输入：claim 用正常 `KnowledgeRepository.publish`，随后在测试 SQL 把 epoch 手动恢复；evidence/association 用直接测试 SQL 挂接，并同样保持 epoch。三项返回 200，响应仍是此前摘要，下一次 fresh read 摘要已变化；正常 epoch 增加三项对照均 409。原独立单 claim 的同一窗口也是 200。原 raw/JUnit 和断言 `expected 409` 的红源保持，不改期待/skip。

这是明确的故障注入边界：`KnowledgeRepository.publish` 实际走 `save_change_publication` (`persistence.py:238`,`:472`) 增 epoch；本 probe 主动覆盖它，不是产品正常 publish 漏 bump。静态追踪全部 claim/support 写入口、event publish/merge/undo、source_documents、catalog 与 enrichment：可见新增经同事务 epoch 或 event business_version 协议，尚未发现实际产品 commit 漏增路径；低层 `attach_evidence_span` 本身不 bump，但挂接为有效 claim/support 的产品调用经发布协议，catalog 新正文另有 scope upsert。故没有将任意 SQL 破坏协议列为产品 Must fix。接入时必须保留写入协议；主控已明确确认 noepoch 宣称按上述提交窗口限定；新增范围补充CR `docs/decisions/CR-R10_graph_fix2_review_scope.md`（3206 bytes，SHA-256=`7b8cea169d444dc6ca95057723114db86b1bde9587ca128ea536ef8fa0bc5fe4`）记录这一必要解释，原 ff5 冻结CR/raw不覆写，也不改变原验收/评分/分母。不能声称 FOR SHARE 旧 identity 防住所有未来插入。

故障注入的文件/版本：`test_review3_pg.py:46` 原独立单 claim；`test_late_fence_pg.py:55` 三类晚窗口，`:131` 新 fresh digest 不同、`:135` 409 期待失败。`late_fence6` 首次文本替换因 CRLF 未换钩子，实际上仍在早期 RR event SELECT 提交，6 passed **不作为晚窗口通过证据**；其 v1 源 `test_late_fence_pg_v1_early_window.py`、hash 和输出保留。修正 reviewer probe 后 `late_fence6_actual` 明确 3 passed/3 failed。这是 reviewer harness 版本差异，没有更改产品源码或旧金标。

## SQL、负载与复杂度

合法输入是 100 claims×20 精确自然来源证据=2000 support rows、同一可见 paper target、max_nodes=1/max_edges=1。本次真实数据库监听：**7 SELECT、1 target ACL**，服务读取 0.837635s，选集 1 node/0 edges/truncated=true。目标 source/doc/rev 撤权后下一次读取仍校验当前权限，没有 global ACL 缓存。旧性能 probe 通过是因为旧泛泛 JSON 引文被新语义门忽略、目标查询为 0；它不能替代合法输入负载证据。

只报实际观察，不把旧 2002 SQL/整条测试 6.09 秒与本次服务读取时延混算加速比。节点≤200/边≤400，支持读取、每 claim evidence、正文 block 和输入 fence 均有上界；规则没有新外部模型或依赖。请求内 GraphReadInputs/memo 直接服务当前性锁，未发现无用全局抽象、无限重试或无界缓存。固定 regex 检查是保守的关系断言门；fixture 通过不代表自然语言全语法理解、官方正文真实性或语义准确率达标。

选集内容摘要 canonical 排序包含 nodes/edges/gaps、scope、rule/event business_version；`truncated` 表示当前输入或输出边界令选集不完整，gap 不伪造否定。它只校验选集，与全 Neo4j 重建、历史全图或所有节点一致性不等价。

## 原红例与分母

初审分母 **33=32扩展+1性能**，原实际 20 passed/13 failed；首次独立 20 是更早的明确子集，原 8 passed/12 failed，独立材料保留。不能采用作者只跑 32 的 22/10 改写初审33。作者冻结20子组的case IDs与原最初20一致、16 passed/4 failed；本review未另执行20命令，但原33中相同20实际执行也16/4，属于子集派生统计，不新增20到执行分母。

本次原未改32+性能1完整 **33=23 passed/10 failed**。32 bytes SHA=`cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16`；性能 SHA=`3aa334b558e31e52e6a3fa6ae0f16e2e7ae5dfc32a1c2a45928de0df26d9c6c9`。10红是六个无自然语义/事件绑定的旧 JSON+内部UUID正例、三个小限额旧无效关系的 truncated 期待、一个未绑定旧PoC的same_event期待；CR 已批准语义迁移，原期待/失败仍保留。旧作者35完整24/11；旧unit7先独跑6/1，补上原contract/security3后原pure10=9/1，唯一红是规则Literal1.0→1.2。没有删 case、扩大误差、降门、改金标或把旧输入的拒绝涂绿。

## 真实命令、八层验证

所有测试 cwd=`D:/wt/r10-graph-recheck2/backend`，解释器 `D:/wt/r10-graph-recheck2/backend/.venv/Scripts/python.exe`。命令收据 `D:/dianzi/reports/runs/recovery_r10_pg_evidence_graph_review1_recheck2_20261016/<label>.json` 保存完整 argv/cwd/+08 start/end/exit/code SHA；`.log` 原 stdout/stderr、`.xml` 原 JUnit，不清洗。pytest 实际统一 `-m pytest -o addopts= -v <明确文件> --junitxml=<本run>`；原模块适用单元检查不用总仓覆盖率门冒充此切片指标。`locked_environment` 实际 `uv sync --locked --offline` exit0；Ruff9文件、format9文件、mypy3源文件均exit0，src diff-check0。ff5相对29e全材料diff-check实际exit2（原red stdout/staged diff的尾空白与EOF保留），源码/CR diff-check0，不虚报全0。

| label | tests | passed | failed | errors / skipped | exit | 实际 +08 窗口 |
|---|---:|---:|---:|---:|---:|---|
| `original9` | 9 | 9 | 0 | 0 / 0 | 0 | 2026-10-16T05:00:09.629234+08:00 → 2026-10-16T05:00:25.292592+08:00 |
| `original9_repeat` | 9 | 9 | 0 | 0 / 0 | 0 | 2026-10-16T05:06:44.613128+08:00 → 2026-10-16T05:06:58.630692+08:00 |
| `pure` | 39 | 39 | 0 | 0 / 0 | 0 | 2026-10-16T05:00:31.339244+08:00 → 2026-10-16T05:00:34.498023+08:00 |
| `complete_pure` | 42 | 42 | 0 | 0 / 0 | 0 | 2026-10-16T05:06:39.555926+08:00 → 2026-10-16T05:06:41.753002+08:00 |
| `fresh_pg` | 112 | 112 | 0 | 0 / 0 | 0 | 2026-10-16T05:00:32.529260+08:00 → 2026-10-16T05:03:32.487610+08:00 |
| `shared122` | 122 | 122 | 0 | 0 / 0 | 0 | 2026-10-16T05:00:31.371421+08:00 → 2026-10-16T05:00:40.944128+08:00 |
| `related103` | 103 | 103 | 0 | 0 / 0 | 0 | 2026-10-16T05:02:07.801256+08:00 → 2026-10-16T05:02:38.717249+08:00 |
| `legacy33` | 33 | 23 | 10 | 0 / 0 | 1 | 2026-10-16T05:02:32.175089+08:00 → 2026-10-16T05:03:29.129401+08:00 |
| `legacy35` | 35 | 24 | 11 | 0 / 0 | 1 | 2026-10-16T05:04:11.579849+08:00 → 2026-10-16T05:04:54.550418+08:00 |
| `legacy_pure10` | 7 | 6 | 1 | 0 / 0 | 1 | 2026-10-16T05:05:31.726282+08:00 → 2026-10-16T05:05:34.057072+08:00 |
| `legacy_pure_complete10` | 10 | 9 | 1 | 0 / 0 | 1 | 2026-10-16T05:06:41.863083+08:00 → 2026-10-16T05:06:43.906839+08:00 |
| `independent8` | 9 | 8 | 1 | 0 / 0 | 1 | 2026-10-16T05:02:07.763436+08:00 → 2026-10-16T05:02:25.963194+08:00 |
| `late_fence6` | 6 | 6 | 0 | 0 / 0 | 0 | 2026-10-16T05:03:33.626285+08:00 → 2026-10-16T05:03:44.765740+08:00 |
| `late_fence6_actual` | 6 | 3 | 3 | 0 / 0 | 1 | 2026-10-16T05:04:48.882531+08:00 → 2026-10-16T05:05:04.254941+08:00 |

主复跑分母是 complete_pure42 + fresh_pg112 + original9 = **163**；related103/shared122独立记录，共388 functional executions（不把重复组、历史红组、注入红组重复计入这388；作者另一次388的冻结JUnit已独核，也不与本review数量相加）。`pure39` 是少contract/security3的早期子组；`independent8` label实际收集9=6正例+2晚claim窗口+1原序列化，8pass/1fail，不能按label把分母记成8。

| 层 | 状态与实际范围 |
|---|---|
| unit | passed：图边界/DTO、关系极性、R07共享模型候选与预算 |
| contract | passed：内部DTO不改public Relation，R07抽取schema；旧规则输入Literal红另列 |
| integration | passed：真实私有PG、service/router factory，六类/ACL/当前性/重放/限额/负载；DB故障注入晚窗口红另列 |
| security | passed：当前会话/角色/tenant、父链、隐藏claim取锁、固定错误；不宣称已部署环境无全部侧信道 |
| frontend | not_run：本轮没有UI接线或前端变更 |
| e2e | not_run：main App图工厂尚未注册，不能签端到端 |
| live | not_run：0外网来源/provider/模型/真实taxonomy/Neo4j访问，全部显式fixture |
| manual | not_run：无真实产品点击图、演示或人工语义金标评分 |

独占数据库 `test_dianzi_r06_catalog_r10_review3_20261016`，runid=`r06_catalog_r10_review3_20261016`，loopback:25432。WSL Ubuntu22.04/root 私有 connection.json 仅 capture 到内存再环境注入；命令、日志/报告没有 DSN 或凭据。实际DB/user guards已通过，每例UUID schema/upgrade后清理，剩余schema0；未用development/主控库、未downgrade、未降锁门。临时原文对象在本run显式fixture目录；没有模型/provider/第三方资产/金标或付费访问。

## CBM 与接线缺口

官方 WSL portable codebase-memory-mcp0.11.0 先实际help/CLI，再对 **08b backend/src** 独立full index `r10_graph_recheck2_backend_src`：1488 nodes/7664 edges、107 Python files、not_indexed/skipped/partial/unusable均0。实际graph schema、architecture、qualified event_graph/lock/router/shared-validator/writer traces、query和rg都有新收据；未拿旧图。full模式这次 assets实际60 symbols已包含；默认/fast exclusion不能据此忽略资产代码；excluded摘要只列__pycache__（count13且摘要truncated）。

共享 `validate_field_candidate` 图查询与rg均证两直接caller：`model_fields._generate_field` 和 graph `_validated_support`，R07原4文件122已独跑。graph/router/lock的CBM caller0来自嵌套路由解析边界，rg实际证graph_routes两处调用，不能以零边证明无能力。rg并确认 `build_graph_router` 当前仅定义，没有main App注册；Neo4j projection/consumer、full rebuild与实际UI点击均未接。本次不是整个R10完成证据，不上调accepted，不给F2/P2/A1或G-C总评分通过。

Ponytail Review 的正确性、安全、数据历史、负载、测试、速度与必要复杂度均按连接调用方检查；没有新的合规产品 Must fix。上述 DB 重置红例限定了noepoch增强的范围，语义门仍有固定语法局限。下一项应由主控授权完成App/UI/Neo4j接线、真实图重建/current回查及live/manual证据，不由本reviewer顺带改业务。

**Verdict: Ship — 仅固定 PG read service/router 工厂和 Fix2 定向修复。Not checked：产品端到端、Neo4j全图一致性、真实来源/模型、人工语义和整R10/G-C。**
