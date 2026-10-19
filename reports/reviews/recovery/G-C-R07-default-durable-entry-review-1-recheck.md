# G-C/G-D · 默认持久富化初审 Must 1 的 fix1 复核

What this change does: fix1把父富化幂等操作绑定认证 tenant、规范事件 route、认证 user 和 raw key，并明确复用完整一致的旧父任务。它修复不同合法用户/不同事件原先共 key 错误409的问题，保留旧预约和执行协议。

限定结论：**Ship**，初审 Must 1 已闭合；没有遗留可复现 Must/Should finding。本意见只覆盖这项 fix 与初审已检查的默认 API/worker/图/资产入口小批，不签整 R07/R03/R10/R11、原 T 卡、G-C/G-D 阶段门或真实 Celery/live。

reviewer：`/root/r07_default_durable_entry_first_independent_review`，同原非作者初审 reviewer，未实现修复；使用 ponytail-review 5.2.0。WT：`D:/wt/r07-default-entry-review1-fix1`；分支 `codex/r07-default-entry-review1-fix1`。本报告首次写作：2026-10-16T07:15:06+08:00。review commit：null，未提交/未 push/未改 accepted 或 progress。

## 固定版本与材料

原初审对象业务 `1f0522e3f3fb9547ea55136efa64fc589466c992`，内部 root/B595 durable 流程已初审；元数据测试兼容 `8a0cc6b6a93551d9d6060b7ab6abd949326e5cb6`、基线材料 `e61d9d6dd1215c337755d32d112dfe70f13d9e94`。本次 source fix `ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce`，最终材料 `9982c5ec444cef429cef554bdd2e85253c1afe82`；相对 fix source，最终材料没有 backend/src/tests、迁移、公共合同、依赖变更。

作者唯一 run：`reports/runs/recovery_r07_idempotency_scope_20261016`。raw_manifest 原 bytes SHA-256 `2dbdad200695ea322ab104548f068c2fdd86f42d2abc80fb76139d6c3ab1826a`；bytes_fix_manifest SHA-256 `9bc0e8c15649dc7ee919953afb93b1dc04221cc9b257e8b6a89ae46e10f8d5c8`。独立验证 48 条原材料 author raw / 最终 Git blob一致，10 条追加 metadata一致，7 条业务/测试源文件按原 lf_sha256 与冻结 source blob一致。独立 checkout 的任务报告/CR有正常 CRLF差异，LF相符，未称原 raw相同；详见 material_audit.json。

原 manifest53材料含5个生成 pyc，按最终归档明确 excluded/not_Git_verified，未读取、拷贝或强制入Git；不能把含这些缓存的60行称全部raw/blob一致。`a92cc7c64592a06a00317e0ae2887124d3c51141` 的早期autocrlf风险由最终998重新按原bytes stage修正，本结论绑定998，不能单用a92。

唯一作者attrs在该run内：`* -text`保原bytes，log/xml只定点允许数据行尾空格，NVD具体JSON只认可其CRLF。无根/全局attrs豁免。baseline_job_service.py逐byte等于e61原Git blob，SHA-256 `13dd4cfe22ab590bcf74483656d7ef1c9eb745f0bc02909d0876029b5a1daa5e`；作者早期29pass/3fail、后续30pass/2fail、修复regression33以及bootstrap harness失败均保留。

原两个固定失败probe与共享hook由旧独立WT只读复制，原字节、断言与输入不变；固定probe SHA-256 `50de2cabbbecb77c26f4497a97e58b0dcf26c9d82d9dcaaab668645705b79842`。旧初审包/report/run未修改；这次独立2/2通过，初审原2fail仍在旧包。

## 实际路径和兼容性

新 namespace 使用固定JSON：version、认证 current.tenant_id 的真实null、规范 `/v1/events/{UUID}/enrichment-jobs`、current.user_id、raw key，经SHA256得77 ASCII字符键；`/api/v1`与UUID大小写是同一规范route。父PG job scope仍来自事件，认证scope与事件scope不混用；body不能提供tenant/role/模型/URL或权限。

server authenticate→锁实际当前AuthContext→service.enqueue→现有parent/legacy核验→原事务 enqueue_job/outbox。新键并发唯一仍用原PG advisory lock，不改变共享source/outbox行为。workflow UUID与父内部key同源；session不进namespace，同主体/route/tenant的body、policy或新session变化仍409，禁止用新的执行身份隐式替代旧请求。RULE_VERSION、worker payload、API DTO、迁移/table metadata/依赖/模型预算均未变。

复用前核PG parent type/key、payload reference/digest、WF UUID/parent/scope、request/policy类型与摘要、完整binding。旧UUID须符合原event-tenant+raw-key算法；旧准确匹配保原UUID/job/预约与trace。合法另一actor/event建立独立v2且不动旧行；未知、orphan、篡改固定409。raw key恰像已存合法v2内部key时不别名；source同rawkey不被误读/重绑。

旧同actor/event的认证tenant或其它冻结binding变化保守409，这是CR明示的legacy边界，不能说旧scope任意变更仍可reused；新v2的认证null与literal public则明确独立。安全回滚保留v2键生成/兼容读取，或停用新enqueue并留全部历史；不能只恢复旧算法后将已有v2当不存在重复收费。该CR落实了冻结协议与潜在付费预约保护，未删历史或改变费用unknown语义。

## 六类验证与独立新增边界

1. 正常：原两名合法public管理员/两事件HTTP请求各202且独立job；默认原35+新alias1共36通过；CVSS本地正例/versions预算禁用partial与PG注册consume路径保留。
2. 缺失/损坏：原scope8个security例含WF orphan、request/policy/actor/UUID/payload及v2 prefix损坏拒绝；额外默认HTTP v2 payload_ref损坏409、全部jobIDs不新增。
3. 冲突：v2和legacy的body/policy/session变化均409，不为变更重建付费操作；新认证tenant null/public区分，私有job tenant仍是真实事件scope。
4. 权限：public写角色不足、private跨tenant与body身份字段拒绝；独立private legacy在普通tenant及literal public两例，用实际PG用户/会话和默认HTTP复用旧任务，不从body获取scope。
5. 重放：同scope/alias不增parent或outbox；旧原UUID/潜在模型预约保留；source同rawkey不误冲突；Unicode/分隔符/200字符及raw-v2仿键保持有界独立。Unicode是内部service键测试，未声称HTTP放开原ASCII header合同。
6. 并发：同scope两线程只有一个parent、一份outbox，两个receipt分别新建/reused；没有重复model预约。额外private legacy经实际registered consume父初始化后，预约一次成功、重放后再次reserve false、全部jobID和原step完整记录不变。预约是显式synthetic潜在付费，不是实际账单/费用实测。

额外四例：大小写UUID+/api/v1规范重放1例、private legacy预约普通tenant/literal public2例、损坏v2 PG reference1例，4/4通过。

## 真实命令、退出码和环境失败

所有下表收据含展开argv、独立cwd、+08起止、exit、log/XML/hash。Python复用已有venv依赖；源码PYTHONPATH与cwd为本独立WT。新专用API数据库run ID `r07_execution_api_review1_fix1_20261016`；新scope数据库 `r07_execution_scope_review1_fix1_20261016`，保留真实loopback25432/test用户守卫，未碰作者旧test DSN、来源queue15、采集器或生产库。

作者scope_engine硬编码作者数据库名，为保持独立资源，自己的wrapper只导入原16 PG+8 security测试函数/断言和相同synthetic业务fixture，提供新库的等价随机schema fixture；原source/test/helpers未改，timeout/locks/head断言没改。原两probe和默认36原文件直接pytest运行。

|收据|开始 / 结束（+08）|exit|tests/failures/errors/skipped|
|---|---|---:|---|
|[original_two_probe_pg.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/original_two_probe_pg.json)|2026-10-16T06:53:37+08:00 / 2026-10-16T06:53:45+08:00|0|2/0/0/0|
|[author_scope_resource_wrapper_pg.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/author_scope_resource_wrapper_pg.json)|2026-10-16T06:53:45+08:00 / 2026-10-16T06:56:46+08:00|1|24/0/1/0|
|[author_resource_disconnect_case_recheck.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/author_resource_disconnect_case_recheck.json)|2026-10-16T06:59:46+08:00 / 2026-10-16T06:59:49+08:00|0|1/0/0/0|
|[default_entry_pg35.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/default_entry_pg35.json)|2026-10-16T06:56:46+08:00 / 2026-10-16T06:58:19+08:00|0|36/0/0/0|
|[independent_boundary_pg4.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/independent_boundary_pg4.json)|2026-10-16T07:01:11+08:00 / 2026-10-16T07:01:22+08:00|0|4/0/0/0|
|[namespace_contract_unit.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/namespace_contract_unit.json)|2026-10-16T06:53:50+08:00 / 2026-10-16T06:53:52+08:00|0|8/0/0/0|
|[src_ruff.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/src_ruff.json)|2026-10-16T06:53:36+08:00 / 2026-10-16T06:53:36+08:00|0|不适用|
|[src_format.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/src_format.json)|2026-10-16T06:53:36+08:00 / 2026-10-16T06:53:37+08:00|0|不适用|
|[src_mypy.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/src_mypy.json)|2026-10-16T06:53:37+08:00 / 2026-10-16T06:53:50+08:00|0|不适用|
|[material_audit_command.json](../../runs/recovery_r07_default_entry_review1_fix1_20261016/material_audit_command.json)|2026-10-16T07:07:35+08:00 / 2026-10-16T07:07:39+08:00|0|不适用|

scope wrapper初轮23pass/1error，唯一在fixture迁移DDL时 `PG server closed the connection unexpectedly`，业务断言未执行；原error log/XML与计数保留，未改为skip或业务失败。使用已授权受保护本地测试资源参考、只在内存捕获JSON后，同一原error case在同source/相同guard/timeout下1/1通过。不能累加成25独立case或称原24批exit0；该目标24例分别已运行通过，初轮环境失败明确保留。源/阈值未改，也没无限重跑原strictCPU门。

固定NVD输出只在本独立WT准备，生成观察移入本次owned resources，未覆盖作者字节。src Ruff/format/mypy全通过；namespace unit6/contract2合8通过。未机械重复旧194/133，旧133与194本来重叠；未把它们累计新指标。

## 索引、源码和材料复查

本tree source-only独立CBM `r07_default_entry_review1_fix1_src`：1594 nodes/8499 edges；schema/architecture/qualified trace及全src rg调用方已保存。bound enqueue入边为0属于静态callback/实例调用识别限制；source/rg确认真实enrichment_routes调用、runtime_policy构造、handlers固定注册，实际HTTP/consume补证。其它source/question/child共享enqueue不变，修复只在富化父namespace；assets未被该source index纳入且本fix未改它，不将空边当实际没接线。

作者最终source变更仅下面七项；其中业务仅job_service.py（enqueue及必要helper）。固定代码diff/material audit确认API、settings、worker、公共metadata/schema/迁移、依赖、旧tests、frontend与progress未变。

- `backend/src/ai_intel/enrichment/job_service.py`
- `backend/tests/contract/test_r07_idempotency_namespace_contract.py`
- `backend/tests/integration/test_r07_idempotency_scope_api_pg.py`
- `backend/tests/integration/test_r07_idempotency_scope_pg.py`
- `backend/tests/r07_idempotency_scope_helpers.py`
- `backend/tests/security/test_r07_idempotency_scope_security.py`
- `backend/tests/unit/test_r07_idempotency_namespace.py`

独立实际秘密值扫描覆盖本次owned raw/report、作者48+10材料、7源与manifest；按当前受保护测试参考的真实password/完整DSN及受控环境secret逐值比对，并解压CBM zst检查。5个excluded pyc始终不读；不以regex形状0替代实值检查，也不保存值或其hash。最终scan收据与review manifest位于本run，review commit null。

## 限定评分证据、偏差与未验证

05/T07/T35的主体/route幂等、重放/并发/权限/历史预约保护有真实PG与默认HTTP证据。不是新准确率、召回率、性能、实际费用或连续运行指标。旧metadata19/1红和之后20/20兼容闭合仍按初审报告分列，本fix没有更改它或重跑金标。

原默认worker消费仍是测试进程中真实consume_job，真实Redis/Celery broker/worker进程e2e、浏览器、live、manual not_run；外部model/provider/source HTTP与paid calls 0，费用unknown。未运行POC/第三方扫描/holdout/正式对照，不签全仓strictCPU或阶段门。

R07整体仍partial：R08 available aggregate发布未接，默认aggregate=false；新7dae selector/schema尚未在本对象集成，prompt/selection版本durable指纹与coverage审计缺口继续传播，不能沿用本fix通过让旧排队任务在新算法下收费执行。Full NVD模型选片预算失败仍保留，CVSS成功不等九维完成。R10默认CVSS graph floor只有event node/空edge，不能冒称六关系/MCP真实推理；R11默认current/history读取不等完整资产研判/FOFA。

计划/合同偏差：独立资源wrapper与一次PG环境error如上明示；没有原测试/金标/指标/阈值放宽。下一步仅供root按冻结证据登记这个小批的有限review；跨stage、真实worker/live和完整R卡仍需各自验收。

Verdict: **Ship（限定fix1/default-entry小批）**。Not checked: 真实Celery broker/worker、浏览器/live/manual、九维真实覆盖、prompt/selection跨版本durable升级、完整R/T/G-C/G-D与全仓工程门。
