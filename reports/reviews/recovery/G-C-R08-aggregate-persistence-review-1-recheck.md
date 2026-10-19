# G-C / R08 · 聚合持久化 service/cache 初审 1 定向复核

What this change does: 新版本只把缓存 TTL 改成对 PG 剩余有效秒数向下取整，retrieval 与 observed_at 两条时间都受限。剩余不足整秒时不写缓存，24 小时过期阈值与原业务状态保持。

**结论：Must 1 已关闭，限定 service/cache 切片 Ship。** 没有新增阻断发现。此意见不验收整 R08、G-C、原 T08/T19/T23、生产 0019、真实 Redis IO、API/worker/enrichment/UI 或 live；未写 accepted，未改业务/原测试/迁移/状态，未 commit/push/spawn。

原初审 reviewer 本轮继续独立复核，未参与作者修复。新干净工作树 `D:/wt/r08-persistence-recheck1`、分支 `codex/r08-persistence-recheck1` 从最终材料 `a76374ca9200945441a83421050eceef00db47d8` 创建；实际 tree=`0abfeae5aa1c4f2b4ed9b37c5aa4d50441c37f81`。修复代码 SHA=`4a3ba0f384eb15cc64b2e4e9cde33805909c6884`、实际 tree=`79cbc8e8c3c82ef25b5371d89d9f7f33aeac2010`；前版材料基线=`6706cd9eeae8bae612fc7e86dff2e2b0416eeaef`。运行窗口为 `2026-10-16T04:57:21.050468+08:00` 起至 `2026-10-16T05:00:36.455601+08:00` 主要测试/图查询结束，报告记录时间 `2026-10-16T05:00:36+08:00`，最终封存时间见自有 manifest。

重新读安装的 ponytail 5.2 review SKILL.md、新版 CR-R08_aggregate_persistence、R08-cache-ttl-fix1 报告、修复 diff 与新两类测试，核对冻结 AGENTS/00/R08/T23/03–06/public v2 exposure、task_state/handoff 和初审结论。Ponytail review 的具体案例/真实 caller/预期负载要求用于本轮；中文、禁止改代码和禁止 spawn 按本轮授权执行。作者报告与 41 项声明均由本 reviewer 复跑，未沿用为通过证据。

## Must 1 关闭证据

初审具体缺陷：年龄 86399.5 秒时旧公式 `86400-int(age)` 写 TTL=1，大于 0.5 秒剩余期。原 reviewer 的红日志、probe、报告与 manifest 完整保留在 `D:/wt/r08-persistence-review1`，68/68 原封存项逐字节复核无漂移；原 manifest 本体 SHA256 仍为 `28d5eacb9c6ff36eb18981926f87d8afd63761345cbc2cc821e0ce0a2248fcfd`。原红日志 hash=`95172c39e6ac0a3a379a7257f4d7ebd67e55d85b3094eab25f41a1a96fb4778a`，原 probe hash=`be097136b8a47abd6ac0d8041e012202ac73b41b3ba18ccd177aaf172854546f`；详情见 [original_review_preserved.json](../../runs/recovery_r08_aggregate_persistence_review1_recheck1_20261016/original_review_preserved.json)。没有把原失败改成通过或覆盖原文件。

修复行 [aggregate_service.py:180](D:/wt/r08-persistence-recheck1/backend/src/ai_intel/assets/aggregate_service.py:180) 与 181 使用 stdlib `floor(86400-age)`，185–186 沿用剩余整秒 <=0 不写 cache。业务 diff 仅增加 math.floor import 和两处表达式，未修改 TTL 常量、查询/授权、模型值、PG repository/table 或原测试期望。代码与最终材料版 src/tests diff=0。

自有新 run 复制原 23 个边界探针，并只在新副本新增 6 个 retrieval/observed 边界；原失败的 retrieval 半秒输入现已通过。新增六例均在独有真实 PG 保存后查询 UUID/安全值，结果如下：

| 剩余有效期 | retrieval 边界实际结果 | observed_at 边界实际结果 |
| --- | --- | --- |
| 1.5 秒 | cache TTL=1，available，freshness=unknown | cache TTL=1，available，freshness=current |
| 0.5 秒 | cache set=0，available，freshness=unknown | cache set=0，available，freshness=current |
| 0 秒（年龄 86400） | cache set=0，unknown/stale，当前 value=None | cache set=0，unknown/stale，当前 value=None |

每个正 TTL 都独立断言不超过真实剩余秒数；0.5 秒 available 来自已提交 PG，并未把尚未过期值提前设 stale。nullable observed_at 没有被 retrieval 冒充。作者单测与 PG 测试另覆盖 86399 秒 TTL=1、future retrieval 不推进 cache、future observed 类型拒绝、cache setter 独立读回已提交 UUID/hash/总量；两条时间的半秒 red/green 材料核 hash 留存。**原 Must 1 复现输入、最小修复及两条时间回归均已闭合。**

## 本次真实命令与数量

完整 argv/cwd/+08 开始结束/退出码见 [commands.jsonl](../../runs/recovery_r08_aggregate_persistence_review1_recheck1_20261016/commands.jsonl)。命令 cwd 为本 WT backend，显式 `PYTHONPATH` 指向本 WT src；本 WT `.review-venv/Scripts/python.exe` 由 `uv sync --locked --offline` 从本地缓存安装 80 包并构建 editable package，无网络下载/HTTP。

| 检查 | 实际命令主体 | 退出码 / 结果 |
| --- | --- | --- |
| 作者 pure 定向 | `python -m pytest tests/unit/test_r08_cache_ttl_fix1.py tests/unit/test_r08_aggregate_service.py --no-cov -p no:cacheprovider -q` | 0；31 passed：新 TTL 10 + 原 service 21；author_units.log/xml |
| 作者真实 PG 定向 | `python .../execute_pg.py author_pg tests/integration/test_r08_cache_ttl_fix1_pg.py` | 0；10 passed；author_pg.log/xml |
| 必要原 PG 回归 | `python .../execute_pg.py original_pg tests/integration/test_r08_aggregate_persistence_pg.py` | 0；20 passed；original_pg.log/xml |
| 原 reviewer 探针新副本 + 两时钟边界 | `python -m pytest ../reports/runs/recovery_r08_aggregate_persistence_review1_recheck1_20261016/test_review_boundaries.py --no-cov -p no:cacheprovider -q` | 0；29 passed：原 23 + 新 6；independent_pg.log/xml |
| Ruff / format | `python -m ruff check`、`python -m ruff format --check` service 与两个新作者测试 | 0；3 files formatted；ruff/format.log；format 首次 cache 写入 os5 warning 保留，`--no-cache` 复跑 exit0 无 warning |
| 类型 | `python -m mypy src/ai_intel/assets/aggregate_service.py` | 0；1 source file 无类型问题；mypy.log |
| 新冻结材料 | `python .../audit_frozen.py` | 0；32/32 basis 匹配，定向 diff check 0；原 raw run 全量 diff check 2；author_material_audit.json |
| 原初审不可覆盖 | `python .../verify_original_preserved.py` | 0；原 68 项无漂移，旧 manifest hash 相同 |

本次 **90 个定向 pytest 用例，0 failure/error/skip**。作者声明的 41 项已全部独跑；额外原 PG 20 与 reviewer 29 另列，不改分母。此前初审 320 项来自旧 SHA 的历史定向检查，**本轮没有全重跑 320**；没有重跑原 100 聚合 connector、120 网关、43 R07，不能将其旧通过记录冒称新 SHA 全仓/全回归验收。

## 八层定向覆盖与剩余边界

| 层 | 本轮实际结果 |
| --- | --- |
| 合同/范围 | 新 CR 正确描述 floor 剩余期；24 小时 TTL、unknown、计数语义和原卡范围未改。小数剩余期偏差关闭，无新公共 schema 或权限语义。 |
| 源码/caller | diff 仅三处业务改动；rg 新 WT src/frontend 的新增符号与 `_cache` caller，唯一直接 caller 仍 `_result`。service API/worker/enrichment/UI 未接；没有以图缺边替代源码结论。 |
| PG/事务 | 新独有 DB 前向 0016 后创建原单表/trigger，原 20 PG 覆盖 immutable UPDATE/DELETE、同 UUID 8 writer/typed collision、rollback、JSON/hash/indexcols、最新失败与历史、future/乱序与模式范围。不是 production migration。 |
| ACL | reviewer 五个角色/范围拒写、tenant 同范围写/跨租户不可见、另一 scope 同 UUID collision 全通过；服务器 public MANAGE_PUBLIC_SOURCES、private WRITE_ASSET 边界不变。 |
| 时间/cache | 新六时钟边界和作者 20 TTL 用例通过；原坏 UUID/hash/version/mode/额外 TTL 载荷为 invalid 且仍 PG 原值；fixture 对共享 cache get/set=0；stale/future 不推进缓存。只是注入缓存合同，未连接 Redis。 |
| 错误/历史/安全 | 最新 failure 不以旧 available/cache 代替，previous_available 仍明确历史；PG 保存失败不写缓存，cache failure 不否定已提交零值。原 canonical/outbox/明细隔离 PG 回归通过；没有供应商/模型访问。 |
| 并发/费用 | 原 reviewer 八实例共享 PG 检查仍实际 8 adapter calls/8 UUID；四个在途 tenant key，第五个立即 rate_limited，adapter 等待时该 engine checkedout=0；不同 payload 同 UUID 8 writer 1 saved/7 collision。既有跨实例限定与 R07 PG 租约/预算预留门槛保留，无新的 exactly-once/性能承诺。 |
| 静态/证据 | 新 90 定向检查与静态通过；新 32 作者材料逐 basis、原 68 reviewer材料逐 raw 校验；作者 red 2 failed/8 passed 和原 reviewer red 都保留。src/assets 图分别重新索引并绑定新版 SHA/tree；未用作者旧 trace 替代。 |

CBM 本机 0.11.0 对当前材料 SHA/tree 独立索引：src 1409 nodes / 7128 edges，默认 assets 排除；另 assets 120 / 463。两个图实际 `get_graph_schema`、`get_architecture`、actual qualified name search 及 `_cache`/`_result`/read/collect 四条双向 trace 均 exit0。`_cache` 的直接 caller `_result`，再到 read/collect/product；回查 PG→freshness→safe payload→cache Protocol 的源码已读。缓存目录仅 `/tmp/r08-persistence-recheck1-{src,assets}-cbm-20261016`，不索引 reports、secret 或 holdout。

PG 仅从获准 WSL test-services connection.json 捕获于内存，验证 `127.0.0.1:25432`、test_dianzi_ DB/test_ 用户前缀；只创建并保留 `test_dianzi_r08_aggregate_review1_recheck1_20261016`。真实记录 revision=`0016_source_response_receipts`，单表不可变 trigger=1；不读 dev DSN、不变更旧库、不 drop/downgrade。0 新 provider/account/model 请求，live 标签来自显式合成 fixture，费用 unknown，不计 live。原四条脱敏样本不需要 TTL 修复重放，本轮未重放，不把此前 4 条结果累加成新 live。

新版作者 [artifact_manifest.json](../../runs/recovery_r08_cache_ttl_fix1_20261016/artifact_manifest.json) 本体 **实际 raw SHA256=`31f6dfbe893920663480ae99fd47cdf55fa248b271ddf8b64064cd9b023d475d`**；32 项全部按声明 git_blob/canonical_text_lf/run 原 bytes 核验，每项同时记录实际 raw 与最终 Git blob hash。run `* -text` 的 CR/LF 保留导致全量 diff check exit2，仅限定新 run 路径；源码/tests/CR/报告限定 check exit0，未改写工具原输出。此前作者 58 项冻结材料与初审红证据保留；本轮仅核新版 32，原 reviewer 68，不虚报重新核此前作者全部 58。

未检查：生产 0019 空库/升级/恢复、真实 Redis IO/TLS、API/worker/enrichment publisher/frontend/e2e/manual、供应商新 live/指纹误匹配率、真实外网完整时延、全仓测试/覆盖率/性能、人工金标和阶段验收。单 provider 20 秒、两 provider 顺序 40 秒合同不受三行修复影响，本轮未重跑 120 网关或做新 live 时延测量。未来共享 PG worker 必须落实任务租约、预算预留和两 provider child；service 的实例内 singleflight 不承担跨进程付费 exactly-once。

评分证据仅 F2/X1 的时效/缓存/安全边界与 P2 的上述可复跑检查，不证明正式准确率或完整资产能力。下一建议：root 按限定 Ship 核对新冻结代码/DDL，再单独集成/评审生产 0019 与 R07 provider child 产品接线；整 R08/G-C 保持未验收。

Verdict: Ship. 范围仅为已复核的 PG aggregate repository/service/cache 切片及 Must 1 TTL 修复。
