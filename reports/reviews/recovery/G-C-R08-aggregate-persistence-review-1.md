# G-C / R08 · 聚合持久化 service/cache 独立初审 1

What this change does: 本切片将白名单 Hunter/Quake 安全总量追加到 PostgreSQL，保留失败、未知、历史与服务器租户范围。内部服务先回查 PG 再验证可选缓存，不把公网产品数量解释为漏洞或自有资产数量。

结论：**needs_changes，先修复 Must 1**。仅评审聚合 repository/service/cache 内部切片；未签整 R08、G-C、T08/T19/T23、生产迁移、Redis live 或 API/worker/UI。没有更改业务源码、原测试、迁移、锁或状态，没有 accepted、commit、push 或 spawn。

本 reviewer 与作者不同。工作树 `D:/wt/r08-persistence-review1`，分支 `codex/r08-persistence-review1`。被审最终材料 SHA=`6706cd9eeae8bae612fc7e86dff2e2b0416eeaef`，实际 tree=`d1a6951d3ffd55aec75f5eade6eaaa4a01f410e9`；代码 SHA=`fb1c08ae9f1379179b3f05c5547fafa5846fe752`，实际 tree=`dfacf694e45a62ff16bbfbfd0c61cd2ef322e2ed`；基线=`8a1b04d48346d8550f0326a77f003246a0ebbab5`。证据命令运行窗口始于 `2026-10-16T04:19:56.006343+08:00`，主要测试/图查询结束于 `2026-10-16T04:26:39.707167+08:00`，报告记录时间 `2026-10-16T04:27:45+08:00`；最终封存时间见自有 manifest。

已读 AGENTS、00、恢复卡 R08、T23、03/04/05/06/07、public_api_v2 的 exposure、已有 ExposureAggregateValue、冻结 progress/handoff，以及作者 CR-R08_aggregate_persistence 和 R08-aggregate-persistence 报告。作者报告作为待核材料，不作为通过依据。使用 ponytail 5.2 review：先追真实调用和预期负载，再用具体输入判断缺陷；用户本轮中文与禁止改业务/spawn 的范围优先。预计本切片由服务器组合调用，尚无产品 caller；未来 worker 将共享 PG，因此另测了多实例并发。

## Must fix

1. **缓存 TTL 向上取整，超过 PostgreSQL 剩余有效期**（[aggregate_service.py:179](D:/wt/r08-persistence-review1/backend/src/ai_intel/assets/aggregate_service.py:179)，相关行 178–183）。
   - **职责与输入：** `_cache(write=True)` 给已提交的 live 标签安全总量计算缓存 TTL。独立测试把 `retrieved_at=2026-10-15T20:00:00Z`、`now=2026-10-16T19:59:59.500000Z`、`observed_at=None` 的总量 5 保存到自有真实 PG；剩余有效期 0.5 秒。
   - **实际结果：** `86400 - int(age)` 返回 1，缓存收到 `ttl_seconds=1`，断言 `1 <= 0.5` 失败。`boundaries_final.xml` 为 22 passed / 1 failed / 0 skipped；首轮同根因失败也保留。该行为违反 CR-R08_aggregate_persistence 的“TTL 不超过 PG 值剩余有效期”。observed_at 的计算使用同一取整式，同样需要修复。
   - **影响：** 缓存最多多留不足一秒。此次没有复现 stale 读值伪 current：读取仍先查 PG，达到 86400 秒会清空当前值。风险是缓存保留期合同失真，不是供应商数据泄漏或另一套事实真相。
   - **最小修复与复验：** 对正的剩余秒数向下取整，例如 `int(86400 - age_seconds)`；取 retrieval/observation 两者较小值，结果不大于 0 就不写缓存。作者修复后，原 reviewer 重跑独立 TTL 红例，并补 observed_at 的半秒边界；重跑 37 pure、20 PG、相关 263 和静态检查，不修改金标、阈值或跳过失败。

## 八层实际覆盖

| 层 | 实际核验与结论 |
| --- | --- |
| 1. 需求与合同 | R08 六案例、T23 原验收范围仍保留；只复用现有 observation/exposure 和两个产品枚举。未知、线索、宽泛总量的语义正确；TTL 一项偏差见 Must 1。 |
| 2. 调用与模块边界 | 独立 CBM src 索引 1409 nodes / 7128 edges，默认排除 assets；另索引 assets 120 / 464。两个图实际 schema/architecture 和九个函数 trace 均留存；源码 rg 检查所有新增公开方法、canonical/scope/call-key/cache helper 的 caller。collect 的唯一源码 caller 是产品便利入口，API/worker/enrichment/UI 未接。Protocol 动态调用在图中并非具体 PG caller，已读源码补齐，未把缺边当作无人调用的证明。 |
| 3. PG 表与短事务 | fresh 自有库前向升级 `0016_source_response_receipts` 后仅 `Table.create` 本表，immutable trigger 实际存在。20 原 PG 测试覆盖 UPDATE/DELETE 拒绝、UUID 同载荷重放、8 writer 同 UUID 仅一行、collision、insert 后校验失败回滚、索引/JSON/hash 交叉检查；不是 0019 生产迁移验收。 |
| 4. 权限与范围 | public 写必须 MANAGE_PUBLIC_SOURCES；tenant 写必须 WRITE_ASSET，身份从 AccessScope 来。五个角色/范围拒写负例无新增行；tenant_admin 可同租户写且跨租户读为 None；另租户重放相同 UUID collision，原记录不变。 |
| 5. 时间与缓存 | unknown observed_at 保留 unknown；retrieval/observation 独立 24 小时边界、future retrieval 历史留存且当前排除、最新失败不以旧 available 代替。缓存 UUID/hash/version/mode/额外 TTL 字段篡改均 invalid，返回 PG 原值；fixture 对共享缓存 get/set 都是 0。只发现小数 TTL 取整缺陷。 |
| 6. 错误与安全载荷 | 失败分类固定，保存失败不推进 live 标签缓存、不返回成功；canonical/hash 与 provider/query/mode/observed_at 列不一致均失败关闭。原 fixture gateway 明细/秘密不进入 PG/canonical/cache，outbox 未增加；没有 LLM 投递、任意 URL/query/SQL/shell 接口。call-key 只哈希 provider/query/version/mode/server profile，scope 再组成缓存身份，不含密钥。 |
| 7. 并发、负载与预算边界 | 自拟同 UUID 八个不同 payload writer：1 saved、7 typed collision，原 winner 保留；同实例四个 tenant key 在途，第五个立即 rate_limited，无第五次调用，adapter 等待时 engine checkedout=0。八个独立 service 共用 PG 的 barrier 检查实际 8 adapter calls/8 UUID：确认实例限制，不宣称跨进程 exactly-once。无循环自动付费 retry，生产单 provider 原网关总 deadline=20 秒；便利入口两 provider 顺序 wire 上界=40 秒，另有 PG/cache 开销。没有新外网性能实测。 |
| 8. 回归、静态与证据真实性 | reviewer 自有 offline venv，37 pure + 20 PG + 100 aggregate + 120 gateway + 43 R07 共 320 项独立通过；Ruff、format、mypy 通过。自拟最终 23 项为 22 passed/1 TTL failed/0 skipped。作者 manifest 58/58 匹配声明 basis；代码与材料版源码/test diff 为 0。原作者与本 reviewer 失败证据均保留。 |

## 实际命令和结果

所有 cwd、完整 argv、开始/结束时间和退出码见 [commands.jsonl](../../runs/recovery_r08_aggregate_persistence_review1_20261016/commands.jsonl)。以下命令在 `D:/wt/r08-persistence-review1/backend`，`PYTHONPATH` 明确为本 WT src。`python` 为本 WT `.review-venv/Scripts/python.exe`；使用 `uv sync --locked --offline` 从本地缓存安装 80 个包并构建本 WT editable package，0 网络下载/HTTP。

| 检查 | 命令主体 | 退出码与实测数量 |
| --- | --- | --- |
| 新 unit/contract/security | `python -m pytest tests/unit/test_r08_aggregate_service.py tests/contract/test_r08_aggregate_persistence_contract.py tests/security/test_r08_aggregate_persistence_security.py --no-cov -p no:cacheprovider -q --junitxml=.../pure_final.xml` | 0；37 passed；new_pure_recheck.log |
| 原真实 PG | `python .../execute_pg.py` → 原 `tests/integration/test_r08_aggregate_persistence_pg.py --no-cov -q` | 0；20 passed；pg.log / pg.xml |
| 原聚合 | `python -m pytest tests/unit/test_r08_aggregate_connectors.py tests/contract/test_r08_aggregate_contract.py tests/security/test_r08_aggregate_boundary.py --no-cov -p no:cacheprovider -q` | 0；100 passed；existing_aggregate_recheck.log |
| 网关 | `python -m pytest tests/unit/test_r03_network_gateway.py tests/unit/test_r03_network_review_regressions.py tests/security/test_r03_network_transport.py --no-cov -p no:cacheprovider -q` | 0；120 passed；gateway_recheck.log；为 socket/DNS fixture，无外网 HTTP |
| R07 | `python -m pytest tests/unit/test_r07_enrichment_contracts.py tests/contract/test_r07_signal_schema_boundaries.py tests/contract/test_r07_signal_claim_values.py --no-cov -q` | 0；43 passed；r07.log |
| 自拟 PG/缓存/并发 | `python -m pytest ../reports/runs/recovery_r08_aggregate_persistence_review1_20261016/test_review_boundaries.py --no-cov -p no:cacheprovider -q` | 1；22 passed、1 failed、0 skipped；independent_boundaries_final.log / boundaries_final.xml |
| 静态 | `python -m ruff check`、`python -m ruff format --check` 三源文件及四原新测试；`python -m mypy` 三源文件 | 全部 0；7 files formatted、3 source files 无类型错误；ruff/format/mypy.log |
| 四条脱敏样本重放 | `python .../replay_safe_samples.py` | 0；4 条入自有 PG 后只读 service 返回同总量，observed_at=null、freshness=unknown；不计新 live、不计 pytest 数量 |
| 冻结审计 | `python .../audit_frozen.py` | 0；58/58 匹配；定向 diff check 0；全量原材料 diff check 2，仅保留 CR/LF 的 run 路径 |

PG 连接只从明确授权的 WSL Ubuntu-22.04 root `/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json` 捕获在进程内，验证 host=`127.0.0.1`、port=25432、数据库 `test_dianzi_` 与用户 `test_` 前缀。只创建 `test_dianzi_r08_aggregate_review1_20261016` 和随后独有 `..._fresh`；二者保留，不 drop/downgrade，不访问开发 DSN/旧 run 库。最终复验使用 fresh 库。真实网络请求/账号请求/模型请求均 0，未读 provider credential 或 secret vault；费用仍 unknown。

## 材料 hash 与保留失败

作者 [artifact_manifest.json](../../runs/recovery_r08_aggregate_persistence_20261016/artifact_manifest.json) 本体实际 raw SHA256=`586aed51401c1b9f1d02512b4ab5cc8c2eaca801dd2d8e316b76a8f8e2a1f665`。逐 58 项区分 `git_blob`、`canonical_text_lf` 与 run 原字节，全部匹配；同时保存每项 raw hash 与最终 Git blob hash，没有把 Windows checkout CRLF 的源码原字节误称为代码 blob。检查脚本没有运行作者 freezer、改写原始材料或生成新的作者 manifest。作者 run 局部 `* -text` 规则保留原始失败日志；源码/测试/CR/报告限定 diff check=0，全量 check=2 是这些保留字节，不对工具 stdout 做净化后伪称全绿。详见 [author_material_audit.json](../../runs/recovery_r08_aggregate_persistence_review1_20261016/author_material_audit.json)。

作者历史 os267、editable import 的 collection error、Ruff/format 修复前输出、索引表达式 DDL SQLSTATE 42601 与其后 20 failed 日志逐原字节留存并核对。最终 fresh table 的索引括号/trigger 与 20 PG 已独立成功建立/复跑；仍不能推导生产 0019 通过。

本 reviewer 准备失败也保留：初次 cwd 不存在 os267，确认目标 branch/WT 无占用后获 root 指令创建，未操作 main；首轮并行 pytest 同目录 cache 临时文件竞争为 collection WinError2，wrapper 打印 GBK UnicodeEncodeError，其 child exit=2 与 outer exit=1 分别有工具/日志证据，改自有 runner UTF-8 与 `-p no:cacheprovider` 后复跑；首个 gateway 命令测试路径写错，exit=4、0 tests，修正路径后 120 passed。首个 PG prepare 将完整 revision 错写为 `0016` 的断言导致 instrument exit=2，留下该自有库，改正确前缀检查并新建 fresh 库后 exit=0。自拟首轮导入 `test_connection` 被 pytest 当额外测试收集，1 warning；改自有 import 别名后最终为 23 项且无 warning，TTL 仍失败。CBM `cli help` 不支持（exit=1），初次 glob search 0 结果不当无 caller 证明，改正则 search 返回 actual qualified names 后才 trace。

四条旧 live 安全样本只使用最终材料中的 [replayed_safe_observations.json](../../runs/recovery_r08_aggregate_persistence_20261016/replayed_safe_observations.json)，未重新读取供应商或请求付费 API。来源 receipt 的作者记录 hash=`043ab16ceab01f108373db9da0df19a41388457731b1d99702c308cb770825a4` 与 adapter code SHA=`349c5e3ec27196257b98cdfcb63c75fb50157978` 是保留 provenance；本轮核验的是封存安全副本与本轮 PG 重放，未声称重新独立 live 核验原来源。自有 replay receipt 保存副本 raw hash、新 UUID/hash 与 unknown freshness。

## 非阻断债务与未检查

跨实例 8 次调用是已复现、已声明的边界，不是本未接线 service 的隐藏 exactly-once 保证。03 §3.10 明确付费调用宕机边界可能重复，要求先预留预算；未来 R07 worker 接线必须用共享 PG 任务租约/预算与两个 provider child 约束同键失败重复和总调用量。当前 policy 布尔授权不能代替该调度证明；因此这项是产品接线门槛，不因为假设的无限循环新增本切片 Must，也不要求新 ThreadPool/进程框架。

未检查：生产 0019 空库/升级/备份恢复、真实 Redis IO/TLS、API/worker/enrichment publisher/UI 接线、实际供应商新请求/指纹误匹配率、外网完整时延、模型、全仓测试/性能/覆盖率、frontend/e2e/manual、人工金标/阶段验收。single provider 20 秒与产品 40 秒为已读代码/网关 fixture 合同，不能当本轮新 live 性能结果。

评分证据：F2 为可追踪总量/失败/未知/历史；P2 为上述合同与真实 PG 边界复验，未证明准确率；X1 为受控字段、租户权限、不可变历史、cache 回查和零明细泄漏。没有改评分分母或门槛。下一任务建议：作者按 Must 1 做单点 TTL 修复 → 本 reviewer 定向复验新冻结版本 → root 核对最终 DDL 后独占 0019 迁移及 R07 两 provider child 接线，另行评审。

Verdict: fix 1 first. 此结论仅约束本 PG 聚合 service/cache 切片。
