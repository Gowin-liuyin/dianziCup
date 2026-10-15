# R08 · 聚合记录持久化与内部服务切片

状态：awaiting_review；本切片 implementation=complete。R08 整包仍需主控汇合、0019 迁移及产品接线，未自行签 accepted。记录时间：2026-10-16（Asia/Shanghai）。基线 `8a1b04d48346d8550f0326a77f003246a0ebbab5`，代码提交 `fb1c08ae9f1379179b3f05c5547fafa5846fe752`，tree `dfacf694e45a62ff16bbfbfd0c61cd2ef322e2ed`；材料 hash 清单见 [artifact_manifest.json](../runs/recovery_r08_aggregate_persistence_20261016/artifact_manifest.json)。

修改 3 个新增源文件：`backend/src/ai_intel/assets/aggregate_persistence_models.py`、`aggregate_repository.py`、`aggregate_service.py`；新增 `backend/tests/{unit,contract,integration,security}/test_r08_aggregate_*` 共 4 文件；[内部变更单](../../docs/decisions/CR-R08_aggregate_persistence.md)及本报告、独有 run 材料。没有修改 adapter/domain/enrichment/API/publisher/worker/frontend、公共 schema、迁移、lock 或 progress。主控工作区未提交修改始终保留。

先读 AGENTS、00、12 R08、T23、03/04/05/06、CR-R03/R07/R09、public_api_v2 与现有 exposure value。public_api_v2 已有 exposure 维度，本切片复用现有 `ExposureAggregateValue`，未擅自添加公开字段。Ponytail 5.2 full：复用唯一知识 metadata、现有 `AggregateObservation`、现有 whitelist gateway、现有 Scope/权限和 86400 秒 freshness 判断；仅新增一张不可变表及所需两个小方法族，没有通用 CRUD、迁移框架、并行事实库、ThreadPool 或自动付费 retry。

每条新观测用 UUID 留存现有类型的规范 JSON/hash、provider/query/version、UTC 时间、nullable observed_at、固定 outcome/error、data_mode、unknown 费用和服务器 scope；只存已解析安全总量。PG trigger 实际拒绝历史 UPDATE/DELETE。相同 UUID 相同内容/范围/调用身份幂等，collision 事务回滚。当前读取选最新任一 outcome，future retrieval 排除，倒序新增不覆当前；同时间失败优先。失败 value 为空，旧 available 仅 `previous_available` 历史参考；未知 observed_at 不填 current，任一有效时间达到 TTL 即 stale 并使当前 value 为空。

服务器 policy 只接受闭合授权 profile/mode/范围，tenant 来自现有认证 `AccessScope`。public 保存要求 MANAGE_PUBLIC_SOURCES；tenant 保存要求 WRITE_ASSET 且同 tenant，读按对应权限。call-key 不含凭据，live/fixture 不同；最多两个固定 provider、每 provider 一次 collect。单 provider 的真实 adapter 网关 deadline 为 20 秒，双 provider 产品便利入口顺序 wire 上界 40 秒，另有 PG/cache 开销。R07 应使用两个 provider child。实例内最多 4 在途键，同键并发立即 rate_limited，不排队重试；跨实例可能各调用一次，未宣称 exactly-once。外网调用没有 PG 事务/row/advisory 锁。

可选 cache Protocol 仅存已提交 live available 的安全总量/UUID/hash/版本/时间，读取先回查 PG 并逐字验证安全载荷，fixture 不触碰共享缓存。损坏或失效缓存不产生另一事实真相，cache 失败独立标记；PG 保存失败返回 typed persistence_failed 且不推进缓存。没有实例化 Redis 或改变 TLS 配置。没有 public outbox、LLM 投递或 raw response/headers/host records 存储。

真实执行命令、cwd、开始/结束时间与退出码见 [commands.jsonl](../runs/recovery_r08_aggregate_persistence_20261016/commands.jsonl)，后续记录均为 +08:00；最初 CBM/unit red 为 UTC，可无损换算为 +08。以下是独立实际运行结果，均无失败/skip：

| 检查 | 实际命令主体 | 结果 / 日志 |
| --- | --- | --- |
| 新 unit/contract/security | `python -m pytest tests/unit/test_r08_aggregate_service.py tests/contract/test_r08_aggregate_persistence_contract.py tests/security/test_r08_aggregate_persistence_security.py --no-cov -q` | 37 passed：unit 21、contract 15、security 1；pure_final.log / pure.xml；exit 0 |
| 独立真实 PG | `python .../execute_pg.py`，内部仅上述独有 PG 测试文件 | 最终 20 passed；pg_index_fix.log / pg.xml；exit 0 |
| 原聚合回归 | `pytest` 原 r08 aggregate unit/contract/security 三文件 | 100 passed；existing_aggregate_regression.log；exit 0 |
| 网关回归 | `pytest` r03 gateway/review-regressions/network-transport 三文件 | 120 passed；network_regression.log；exit 0 |
| R07 合同回归 | `pytest` enrichment-contracts/schema-boundaries/signal-claim-values 三文件 | 43 passed；r07_contract_regression.log；exit 0 |
| Ruff / format | `ruff check` 3 src+4 tests / `ruff format --check` 同文件 | passed；ruff_frozen.log / format_frozen.log；exit 0 |
| Mypy | `mypy` 3 新源文件 | 0 errors；mypy_frozen.log；exit 0 |

新测试共 57，相关回归共 263，以上 320 项来自这些定向命令之和，不是全仓覆盖率或性能结果。PG 覆盖真实并发同 UUID 8 线程仅 1 行、不同 payload collision、插入后 integrity 失败 rollback、DB UPDATE/DELETE 拒绝、最新错误/历史值、时间倒序/future、tenant 过滤、public 共享/权限拒绝、模式隔离、JSON/hash/index 列不一致、无 public outbox 与原始记录。缓存失败/损坏/TTL/fixture 禁用、missing product query_id=None 零 adapter 请求、并发 singleflight、零总量和各固定错误已实际断言。unit 中标 live 的对象仅为显式合成标签边界，使用无网络 fixture adapter，不计 live。

PG 从主控明确授权的 WSL test-services/connection.json 在进程内捕获，未输出 DSN/密码、未置 argv。仅创建本 WT 独有数据库 `test_dianzi_r08_aggregate_persistence_20261016` 与最终 fresh schema 数据库 `test_dianzi_r08_aggregate_persistence_v2_20261016`，host loopback:25432，均保留。final 库升级到既有 0016 后 `Table.create` 本表/触发器，未触碰开发库、旧 run 库或 production migration，不执行 downgrade/delete。最终 DDL 与自建表记录见 ddl_proposal.sql / pg_prepare_receipt.json；0019 生产迁移验收 not_run。

保留失败事实：最初 cwd 尚未创建（os267）经主控授权创建独有 WT；unit_red 退出 2 因共用 venv editable import 指向主控源码，尚无新文件，属于环境路径 collection error，不是业务断言失败，runner 显式设本 WT PYTHONPATH 后通过。初次 Ruff/format 发现格式问题并修复。final fresh schema 首次索引布尔表达式少括号报 SQLSTATE 42601；pg_prepare_final 退出 2，后续 pg_schema_final.log 为 20 failed，绝不计 passed。诊断见 pg_prepare_diagnosis；精确修复 `.self_group().asc()` 后 fresh 库表/索引/触发器建立成功，pg_index_fix 20 passed。最初 17/19 passed 为其各自历史版本，不替代最终 20 项。

已获准的四条真实安全样本只做离线重放，原来源为 `D:/dianzi/reports/runs/recovery_r08_aggregate_live_20261016/aggregate_receipt.json`。来源 hash/原 adapter code SHA、新 UUID/hash 与结果见 [safe_samples_replay.json](../runs/recovery_r08_aggregate_persistence_20261016/safe_samples_replay.json)；安全规范 JSON 副本为 replayed_safe_observations.json。四条入最终独有 PG 后经只读服务返回同总量，全部 observed_at=null/freshness=unknown。未重新付费请求，provider/account/model 新请求均 0，不计新增 live 接线验收；没有读取供应商凭据。

CBM 官方本机 0.11.0 先对本 WT src 与 assets 独立索引，再实际 `rg` 校验调用方。src 基线/最终为 1409 nodes/7128 edges，默认排除 assets；独立 assets 基线 76/243、最终/冻结 120/464。服务 trace 包含 typed constructor、repository Protocol read/save、scope/call-key/canonical 校验等边，唯一源码 caller 为产品便利入口；rg 确认 API/worker 尚未接线。缓存只在仓外 `/tmp/r08-persistence-{src,assets}-cbm-20261016`，没有索引 reports、秘密或 holdout，没有提交缓存/ADR。具体 CBM 日志与代码 commit/tree 绑定见 manifest。

合同/计划偏差：主控批准单 provider 20 秒及产品顺序 40 秒入口，无公共合同偏差；原 R08 整包不因该切片自动签通过。评分证据：F2 是可追踪安全公网总量、错误/未知/历史保持；P2 是类型/权限/时间/事务回归，不证明测绘指纹准确率；X1 是 raw/secret 隔离、不可变历史和 PG 唯一权威，不把总量解释为漏洞/自有资产数。费用 unknown。

未运行项：新真实供应商调用、真实 Redis IO、API/worker/enrichment 发布、frontend/e2e/manual、生产 0019 迁移、全仓性能/覆盖率。下一步建议主控合入该内部接口与最终 DDL，接线 R07 两 provider child，再由新非作者 reviewer 复跑冻结 code/materials；root 唯一 merge/push。本作者到 awaiting_review 停止，不 spawn、不 accepted、不 push。

材料保存采用本 run 局部 `.gitattributes * -text`，保留原日志的 CR/LF 字节；全量 Git whitespace 检查会把这些 Windows 原始日志字节报告为尾部 whitespace，未改写原始失败证据。源码/测试/CR/报告另做限定路径 diff check；材料按 manifest 逐字节 hash 检查。code 文件 hash 基于 Git blob，报告基于 LF 文本，run 材料基于被局部规则保留的原字节；此规则不禁止任何源码检查。
