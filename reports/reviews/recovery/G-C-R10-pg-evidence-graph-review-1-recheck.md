# G-C / R10 PG 证据图只读切片 · 初审 1 定向复核

结论：**needs_changes**。响应当前性、认证撤销和论文目标请求内复用已取得修复证据，但语义否定/未知仍产生强边，新增围栏还会锁住不属于可见图输入的其他租户 claim。不得把本报告用于接受整个 R10、G-C 或原 T 卡；未修改业务、原测试、原 probe、progress、accepted、push，未 spawn。

这次修复增加了来源字段/事件绑定校验，并将 HTTP 的候选 RR 读取与当前 RC 返回围栏分开。当前事务锁认证、父链和事实，最后锁 epoch，在持锁期间构建 JSON bytes；同一论文目标仅在本次读取中复用 ACL 结果。规则版本升为 `r10-graph-1.1.0`，内部 schema=1、字段和两个 gap reason 未变。

## 固定版本与复核范围

- 新代码：`3516b9109b9b7f2c5691d78ad0439aea4a659f4f`。
- reviewed code tree：`8991d9bed5ac73d0deb735112ca7ac6a6d593297`。
- 独立工作树：`D:/wt/r10-graph-recheck1`，分支 `codex/r10-graph-recheck1`；own locked editable venv。所有业务读取/导入/测试均使用这份固定源码。
- 最终材料：`29e1ebddca5cbadffc8c6533bdeeb08b8d63e469`。作者固定目录仅进行封存 raw bytes/hash 核对，不从新修复工作树取结论。
- reviewed material tree：`d185a0414952923281c33edf10e3eee3151d95b7`。
- 对照：[原独立初审](G-C-R10-pg-evidence-graph-review-1.md)，其原 33 项、全部红日志/报告和 83 项封存内容保持原字节。
- 已核对 AGENTS、执行图、原 R10/T17/T21/T22/T23/T41、docs03/04/05/06/public_api_v2、当前进度、CR-R10_graph_validity 和 Ponytail Review 5.2.0。CR 与主控明确授权允许 fixture 语义输入迁移，不授权删 case、改旧 probe、削弱权限/当前性断言或计分分母。

源码冻结变化是 graph service/router、原 35 PG fixture、原 unit 的规则版本输入、新 30 PG 回归与 CR，共 6 个清单文件。没有新增认证系统、公共 Relation 改形、数据库 schema、锁配置或依赖变化。当前实际入口仍是 `EvidenceGraphReadService(session, scope).event_graph(...)` 与 `build_graph_router(...)` 工厂；main App、Neo4j、UI 未完成接线。

## 必须修复

### 1. [P1] 论文和 ATLAS 的明确否定/未知句仍发布 supported 强边

位置：`backend/src/ai_intel/knowledge/evidence_graph.py:736`、`:745`、`:919`、`:937`；连接代码 `backend/src/ai_intel/enrichment/field_sources.py:154`、`:322`。

- **职责：** 新 admission 在精确原文中验证 typed 值与自然事件身份，再决定可否发布强关系。
- **实际触发：** 通过真实 PG 发布接口建立自然 GHSA、合法 paper 目标、完整且 hash/坐标匹配的合成来源。论文 `relation=analysis` 的 support_summary 分别明确写 **“This paper does not analyze this vulnerability … it analyzes an unrelated package.”** 和 **“Analysis … is unconfirmed; the mechanism is unknown.”**，仍得到 supported `related_paper`。ATLAS mechanism 明确写 **“Untrusted instructions do not enter a model input.”**，仍得到 supported `mapped_atlas`。三例首跑与重复跑均红。
- **原因/影响：** 引用准确对应 value，但 value 的内容本身否定或保留未知；论文 validator 只要求 analysis marker，ATLAS 只检查机制句存在。`validate_field_candidate` 的抽取检查结果随后被用于 strong-edge admission，尚不能支持“分析了该漏洞”或“机制成立”。这仍违反未知不等于确认、内容存在不等于支持；原 P1 的无关引文门已改善，语义门尚未完整闭合。
- **最小修复：** strong relation 的校验至少拒绝明确否定、未确认、未知的对应关系/机制，并保留其 unknown/candidate 状态。校验应针对具体边的谓词和条件；不能用命中 `analysis` 或逐字引文替代支持判断。难以确定的语义应明示缺口，不声称离线程序已验证来源真伪或所有语义。
- **复验：** 固定 probe `test_review2_pg.py:39` 的两参数、`:48` 的 ATLAS 反例；原 raw SHA-256=`1b12f82583d8c067cc52d604c54aa53bddeb593c1cf8c2bfcccdc32d6d810c47`。保留这些 bytes 和两轮红 JUnit，再加肯定句/否定句/未知句对照；不要改其期望为 supported。

### 2. [P1] 当前围栏无范围过滤地扫描并锁住其他租户的无关联 claim

位置：`backend/src/ai_intel/knowledge/evidence_graph.py:352`–`:353`、`:379`–`:389`；调用位置 `backend/src/ai_intel/api/graph_routes.py:73`。

- **职责：** 返回围栏应锁住本次可见图的实际输入，以校验当前版本和权限。
- **实际触发：** 一个公开事件有合法公开支持，viewer 的直接图读取有效。另建 tenant=other 的 private claim，仅 subject 使用这个公开事件 UUID，其私有来源没有进入事件的 event_documents。该 claim 被候选 `_support_rows` 正确排除。另一连接持有它的写锁时，公开 HTTP 请求却试图 FOR SHARE 锁它，等待原有 5 秒 lock_timeout 后 503；没有这个无关锁时公开输入本身仍有效。两轮均复现。
- **原因/影响：** `claim_rows` 只按 subject 查询，没有 ACL、来源关联或实际依赖约束，后续将所有这些 claim IDs 纳入锁集。其他租户的不可见、未关联状态影响了公开请求的可用性；它不是公开结果中真正待核的输入。已证实的是跨租户可用性隔离问题，未声称回显了私有字段或已在产品公网利用。
- **最小修复：** 从本次范围内的实际关联/输入构造锁集，排除不可见且未关联的其他租户 claim。保持对曾经有效输入在当前发生撤权/撤回时的失效校验，以及父链→事实→epoch 的顺序；不要以遍历所有同 subject 的私有事实来代替这项检查。
- **复验：** 固定 probe `test_review2_pg.py:56`，期望公开合法请求 200 且摘要与公开图相同，实际 503；失败在 `:71`。同时保留原来源父撤权、claim withdrawn 和当前版本/epoch 的 409 回归，避免通过放弃当前性锁修复跨租户锁问题。

合同依据：AGENTS §5/§7，docs03 私有派生/AccessScope，docs04 W04/W09，docs06 安全隔离及已知 stale 门，主计划 6.2 的每条强关系内容支持。上面 4 个失败均为真实 PG 可观察行为，不是接口缺失、环境缺失或未运行。

## 原四问题逐项证据

| 原问题 | 新固定版本实测 | 结论 |
|---|---|---|
| 泛泛 explicit-source 引文晋升六强边 | 原 probe 六个无关引文反例全部通过；自然 CVE/GHSA 不含内部 UUID 的独立正例通过；新 35 中六类 supported 边及正反同 claim/evidence 通过 | 字段与事件绑定改善；上面明确否定/未知反例仍阻止语义门放行 |
| RR 后父 ACL/事实/版本变化逃逸 | 新 30 中 source/document/revision/claim/epoch/event_version × bump/no-bump 12 例均 409、无 edges；直接父撤权不 bump epoch 也拒绝旧图 | 已取得定向修复证据 |
| role/tenant/session 变化逃逸 | 三例均符合 role/tenant=403、revoked session=401，无私有图；原 probe 角色降权反例也通过 | 已取得定向修复证据 |
| 同论文目标 2000 次查询 | 合法自然原文、100 claims × 20 support=2000 行，max_nodes=1/max_edges=1：实际 7 SELECT、1 target ACL、0.5712172 秒服务读取；target source/doc/rev 撤权后的新调用不复用旧权限 | 请求内 memo 改善已实证；无 global ACL cache |

锁时序两方向有实证：writer 先持父锁、reader 等待，writer 能提交 epoch，reader 返回 409，未出现 40P01；reader 已完成当前锁及校验后，在 JSONResponse 构建处启动 parent→epoch writer，该 writer 仍等待，JSON bytes 已建成后才能提交，HTTP 200。原 5 秒父锁等待失败测试返回 503/55P03、无 fake success。独立第二方向结果在 `serialization_lock_observation.json`。

性能比较仅报事实：初审 2002 SQL/2000 目标查询、6.09 秒是整条用例时间；新 0.5712172 秒是服务读取时间，两者不是同一时延指标，不计算提升比例。SQL 数量对照同一 2000 支持行量级，但旧单 claim 与新 100×20 分组不同。旧性能 probe 在新规则下通过时，没有证明有效关系目标读取：旧 JSON+内部 UUID 引文被拒绝，target 查询为 0。P2 的闭合依据是新合法输入的实际 SQL 计数及三父撤权后重读。

## 原 case、分母与 fixture 迁移

**初审分母仍是 33**：原扩展 probe 32（20 passed/12 failed）加性能 1（1 failed），合计 20 passed/13 failed。作者另报旧 probe 32=22 passed/10 failed，是不同执行清单，遗漏了单独性能文件，不能将初审 33 改为 32。

本复核完整执行原未改的 32 文件 **加原性能文件**：33 collected，23 passed/10 failed/0 error/skip。32 文件 bytes 与初审原件完全一致，SHA=`cfbbb95d227f4e884d2765bde6da5dbd1121c5ffd9c159ac99a1e9eadf0bfe16`；性能文件 SHA=`3aa334b558e31e52e6a3fa6ae0f16e2e7ae5dfc32a1c2a45928de0df26d9c6c9`，也逐 byte 相同。仅旧 helper 的数据库身份换成本 reviewer 库，业务/期待逻辑不改。

这 10 红保留原期待：六个旧 JSON+内部 UUID 正例、三个旧无效关系输入的小限额 truncated 正例、一个旧无事件绑定 PoC same_event 正例。CR 已具体解释其语义输入缺口；它们不被 skip、涂绿或删除。原作者 35 也独立重跑为 **24 passed/11 failed**：10 个不具支持的正例与 1 个旧 rule_version 期待失败，结果与迁移说明相符。原完整 raw/blob 与本次新版 35 的 case IDs/参数保留，不用新 75 吞掉历史失败。

旧 pure 10 的原 unit Git blob 另行原字节复制重跑，实际 **9 passed/1 failed**；唯一红例是固定输入 `r10-graph-1.0.0` 不满足新 1.1 Literal。元数据迁移获批，旧输入/期待/红日志仍保留，不改为新版本来伪造旧例通过。

获准的新版 fixture 采用自然 GHSA/CVE/非 CVE 描述、精确来源原文、实际对象存储 hash/坐标、固定合成 taxonomy commit、成对论文目标和 1.1 元数据。新 35 加新 30 PG、新 pure 10 **75 passed**，保留原权限/current/关系数量条件。它们均显式合成，不是官方 taxonomy 真实性、来源 live 或人工语义金标。

## 真实执行与八层状态

证据目录：`reports/runs/recovery_r10_pg_evidence_graph_review1_recheck_20261016/`。每次 `.json` 命令收据保存完整实际 argv、cwd、+08:00 开始/结束、exit 与固定 code SHA；`.log` 原 stdout/stderr 和 `.xml` JUnit 保持未清洗。解释器为 `D:/wt/r10-graph-recheck1/backend/.venv/Scripts/python.exe`，cwd=`D:/wt/r10-graph-recheck1/backend`；`uv sync --locked --group dev --no-default-groups` exit 0，ai_intel 导入本工作树。

仅使用 `test_dianzi_r06_catalog_r10_review2_20261016` / run ID=`r06_catalog_r10_review2_20261016`，loopback:25432；私有 WSL connection.json 仅 capture 到内存/环境，DSN/秘密不输出、不入 argv 或报告。真实库/账号 guard 后，每个图例 UUID schema/upgrade；原锁配置 statement_timeout=15000、lock_timeout=5000 保持，没有 development DSN、降门、生产 downgrade、清库或旧 reviewer 数据修改。临时内容对象也位于本 run 的临时 fixture 目录。

| label | 实际执行 | exit / 真实结果 |
|---|---|---|
| `new_pure` | `python -m pytest -o addopts= -v` 新 rule 的 unit/contract/security 3 文件 | 0；10 passed |
| `new_pg` | 同命令，新固定 PG 35 与新 validity PG 30 | 0；65 passed |
| `related103` | R02 publication/boundaries/dimension、R07 typed contract/signal PG/paper ACL PG、R02 relation identity 7 文件 | 0；103 passed |
| `legacy_author35` | 原 35 的旧 helper/期待，只隔离数据库身份 | 1；24 passed/11 failed |
| `legacy_probe33` | byte 不变原 32+原性能 1 | 1；23 passed/10 failed |
| `legacy_pure10` | 原 unit 1.0 blob+不变 contract/security | 1；9 passed/1 failed |
| `independent_pg` | 固定自然 ID、否定/未知、隐藏锁、目标三父 memo 9 例 | 1；5 passed/4 failed |
| `independent_pg_repeat` | 同一固定 9 例重复确认，未改 probe | 1；5 passed/4 failed |
| `serialization_lock` | 独立 reader 先锁、writer 后启动/JSON bytes 时序 | 0；1 passed |
| `ruff/format/mypy` | 5 个变化 Python 文件 lint/format，2 个 source mypy | 均 0 |


实际 +08:00 窗口（完整 argv/cwd 在同名收据）：

| label | 开始 | 结束 | exit |
|---|---|---|---|
| `new_pure` | 2026-10-16T04:17:00.031045+08:00 | 2026-10-16T04:17:05.699110+08:00 | 0 |
| `new_pg` | 2026-10-16T04:17:06.875299+08:00 | 2026-10-16T04:18:53.479241+08:00 | 0 |
| `related103` | 2026-10-16T04:20:51.466114+08:00 | 2026-10-16T04:21:13.433795+08:00 | 0 |
| `legacy_author35` | 2026-10-16T04:19:15.376441+08:00 | 2026-10-16T04:20:00.683451+08:00 | 1 |
| `legacy_probe33` | 2026-10-16T04:20:01.711662+08:00 | 2026-10-16T04:20:51.073185+08:00 | 1 |
| `legacy_pure10` | 2026-10-16T04:34:08.281297+08:00 | 2026-10-16T04:34:11.075619+08:00 | 1 |
| `independent_pg` | 2026-10-16T04:18:19.823399+08:00 | 2026-10-16T04:18:44.447462+08:00 | 1 |
| `independent_pg_repeat` | 2026-10-16T04:20:27.559340+08:00 | 2026-10-16T04:20:50.650192+08:00 | 1 |
| `serialization_lock` | 2026-10-16T04:23:05.232592+08:00 | 2026-10-16T04:23:08.888998+08:00 | 0 |
| `ruff` | 2026-10-16T04:20:26.744696+08:00 | 2026-10-16T04:20:27.170012+08:00 | 0 |
| `format` | 2026-10-16T04:20:27.327112+08:00 | 2026-10-16T04:20:27.501731+08:00 | 0 |
| `mypy` | 2026-10-16T04:20:27.621358+08:00 | 2026-10-16T04:20:35.584044+08:00 | 0 |


上述每组均 0 error/skip；新业务与相关回归合计 178 passed，新增独立 10 个不同 case 为 6 passed/4 failed；重复跑不再计新增 case。历史两组红例另列，不混入新任务分母。focused pytest 使用 `-o addopts=`，未宣称全仓覆盖率门通过。记录 Starlette/httpx warning，未改依赖。

八层：unit=`passed`、contract=`passed`；integration/security=`failed`（本次 4 红例）；frontend/e2e/live/manual=`not_run`。测试没有外部 HTTP/provider/model/资产调用或 PoC 执行，没有盲测/金标访问。main App 注册、Neo4j 重建/滞后/真实投影、图 UI 和正式性能/持续运行未验证，不能替代为工厂 TestClient 成功。

## CBM、清单和完整性

独立使用官方 WSL Ubuntu-22.04 root CLI 0.11.0，实际 help、schema、architecture、自己的 fixed backend/src full index、service/lock/router qualified traces、query_graph callers 及 rg。project=`r10_graph_recheck1_backend_src`，1486 nodes/7643 edges、未索引/skip/partial/unusable=0；排除项是 __pycache__，本次 assets 60 符号实际可查。没有使用旧索引；零 inbound 不能证明无能力。query_graph 查到 `_validated_support` 和原 `_generate_field` 共用 validator；rg 确认 App 未注册新路由。

封存核对 `archive_verification.json`：作者最终 **92/92** raw bytes/hash 与 Git blob OID/bytes/hash 一致；冻结代码清单 **6/6**、最终材料对应源码与3516一致；原 reviewer **83/83** 原封存文件保持 bytes/hash。source 工作树干净。作者冻结旧 red 的 JUnit 和副本均未删，新/旧计数按实际不同材料列示。审查 archive verifier 最初两次因白名单漏两个旧目录 CBM 文件、误用旧命令文件名报错，原日志保留；按清单取得真实文件名后完整核验成功，不是材料 hash 或业务测试失败。

- 作者 manifest Git blob SHA-256=`211668b01a31a4f3c15ca60a01fd42a4d97c3879a6e4e21e9a3da5c70206444f`。
- 作者 manifest raw SHA-256=`1368e32cf24f7894629ca0d1af85da5a88d8a4aa48d409316b6b543e5c1613cd`。
- manifest Git blob=37578 bytes，raw=38323 bytes；两种字节口径分开核对。
- 代码/CR 的 `git diff --check 16803ce... 3516b91 -- backend docs/decisions/CR-R10_graph_validity.md` exit 0；完整归档到29e1 exit **2**，来自原始 red/log 中的行尾空白及其 staged diff 收据。原日志未裁剪，没有全材料“空白全绿”声明。
- reviewed code/material tree、各文件 byte 数、实际 diff exit 和 secret scan 见本 run 的汇总/核验收据。只读审查没有改变原 CR 状态或 approved/accepted 状态。

## 交接与评分边界

F2/A1/P2 有六类来源绑定、自然 ID、scope/version、目标 ACL、selected nodes/edges/gaps canonical digest 及 IO 改善的代码/fixture 证据。digest 仍是选集摘要，不等价完整 PG/Neo4j 图一致性，也不替代当前性；原 T17/T21/T22/T23/T41 整卡和准确率/召回率/多跳评分未由此验收。

下一项建议：在新的作者工作树最小修复上面 1、2；保持本次四个 negative、原全部 33、原四问题回归及清单字节。具体修改冻结后由非作者再次复核，不在当前审查目录改源或改期待。需要扩展合同/语义范围时提出具体变更，不能把 unknown/否定强行改成支持，或用放弃当前有效性围栏绕过跨租户锁。

**Verdict: needs_changes，先修复 1、2。** 未检查：真实来源/模型语义质量、产品端到端、UI、Neo4j、正式性能/长跑及人工复核。
