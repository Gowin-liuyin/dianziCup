# G-A / R02 维度状态与历史持久化 · 独立初审 1

首次创建/本次写作开始：2026-10-15T11:57:56+08:00。证据截止：2026-10-15T11:57:37+08:00；本次写作结束/最后更新时间见下方收口登记。审查者：`/root/r02_dimension_independent_review`，未参与候选实现。

**What this change does:** 0010 前向迁移把维度尝试的唯一键从输入摘要改为独立发布键，使同输入失败后能够保存新的成功尝试。新仓储在同一 PostgreSQL 事务中保存逐维当前结果、历史、知识变化、epoch、任务和 outbox，并核对事件版本、事实支持及租户范围。

**结论：本固定候选的维度持久化切片通过限定独立审查；未确认阻断缺陷。** 这不签署整 R02、R07、T19、T21 或 G-A 的 `accepted`。整体状态和后续接线仍由主控登记；本报告不改 progress、业务源码、金标、分母、阈值或 skip。

## 冻结范围与依据

候选 `a366c4e5616d8a163ef69431cd2d90e8988b88fa`，tree `0527b5cb45d92b497f918bd7c900452619766168`；基底 `2be32ba49496c9f50d1c713bb15174c1b2c71e62`。独立工作树 `C:/Users/yinha/.codex/worktrees/recovery-r02-dimensions-review/dianzi`，分支 `codex/recovery-r02-dimensions-review`，审前不存在后按授权创建，最终 tracked diff 干净。未追随 main 后续 0011，未 push/commit。

已读 AGENTS、00、恢复 R02 卡、T19/T21、03/04/05/06、冻结实施合同和维度细则，及固定候选中的 task_state/交接；主仓未提交的 `reports/tasks/R02-dimensions.md` 仅用于定位自检说法，未当作通过事实。采用 [Ponytail-review 5.2 技能](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，按正确性、安全、并发、测试与复杂度核查。本轮 4 槽占满，由该独立审查者直接完成各轴。

相对基底恰好 8 文件、783 新增/2 删除：0010 迁移；`enrichment/persistence.py`；`enrichment/persistence_models.py`；2 个新增 PG 测试文件；原 schema 升级测试的 head 更新；新增单元边界测试；维度 CR。没有改变公共九维/七态、公开 API schema、manifest、依赖或原 60% 覆盖门。`git diff --check` 与这些合同文件的 `git diff --exit-code` 均 exit 0。实际路径与每文件 SHA-256/大小见 [candidate_files.json](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/candidate_files.json)。

## 真实运行与资源边界

只读取 WSL root 权限 0600 的 `/tmp/dianzi-r02_dimensions_20261015/connection.json`，在子进程内存/环境注入连接。实际核实库 `test_dianzi_r02_dimensions_20261015`、用户 `test_dianzi_r01`、head `0010_enrichment_publications`，首尾一致。只在此授权库写合成测试数据及用例独占随机 schema；迁移 fixture 的清理仅删除自己新建的 `test_r02_schema_<UUID>`。未降级/删除共享业务库，未升级其他 reviewer 的 0009 库。

Python 3.12.13 使用主仓现有 `.venv`，`PYTHONPATH` 指向固定工作树源码；首尾进程打印的模块路径均是该工作树。连接串和密码未进入 argv、报告、JUnit 或日志；收口对所有 run 文件做实际 DSN/解码密码精确字节扫描，0 匹配，值不输出。

下表时间均为 2026-10-15、`+08:00` 秒级时间。cwd 均为固定工作树 `backend`。`PY` 为 `D:/dianzi/backend/.venv/Scripts/python.exe`；完整 argv、cwd、SHA、起止和退出码保存在对应 `.command.json`，不是伪造的命令摘要。

| 实际命令 | 起止 | 结果与证据 |
|---|---|---|
| `PY -m pytest tests/unit -q --junitxml=<run>/unit.xml` | 11:51:34–11:51:45 | exit 0；161 passed，0 failed/error/skip；cov 62.91%，原 60 门通过；[unit.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/unit.log) |
| `PY -m pytest tests/integration/test_r02_dimension_persistence.py tests/integration/test_r02_dimension_migration.py tests/integration/test_r02_schema_migration.py -q --no-cov --junitxml=<run>/pg.xml` | 11:53:06–11:53:11 | exit 0；12 passed（维度 9、0009 升级 1、空库/0006 升级 2），0 failed/error/skip；[pg.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/pg.log) |
| `PY -m pytest <run>/test_independent_dimensions.py -q -c <WT>/backend/pyproject.toml -p conftest --no-cov --junitxml=<run>/negative_final.xml` | 11:57:28–11:57:33 | exit 0；独立 PG 边界 20 passed，0 failed/error/skip/warning；[negative_final.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/negative_final.log) |
| `PY -m ruff check .` | 11:51:34–11:51:34 | exit 0；[ruff.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/ruff.log) |
| `PY -m ruff format --check .` | 11:51:34–11:51:35 | exit 0，130 文件；[format.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/format.log) |
| `PY -m mypy src` | 11:51:35–11:51:43 | exit 0，58 source files；[mypy.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/mypy.log) |

固定候选回归合计 173 个不同用例通过，另加独立 20 个不同 PG 探针，共 193 个不同用例；重跑不重复计数。完整 unit 的 1 个 Starlette/httpx 弃用 warning 如实保留。先前 20 探针 run `negative` 的 1 个 warning 来自审查脚本 `model_copy` 放入字符串 enum；只改审查脚本为 canonical enum 后定向复跑，原 `.log/.xml` 保留，未改被审源码。没有把合跑作者日志的 69.86% 当成本轮纯 unit 覆盖率。

## 行为与合同核对

| 边界 | 独立证据与结论 |
|---|---|
| 同输入失败后成功 | 原 PG 用例实跑：不同 publication key 生成两结果、旧 failed 保留、current 为新 available。|
| 同 key 重放/碰撞 | 同 digest 复用 result/receipt；异 digest 抛既有 `IdempotencyConflictError`（适配层所需 409 语义）。此次未测试 HTTP 409 接线。|
| 多 worker 重复发布 | 原 PG 及额外双连接 barrier 均实跑；结果/receipt/change/job/outbox 各一，epoch 恰好增 1。并发假定为真实多个连接，不靠单进程内存锁。|
| 发布中途 SQL 故障 | 在真实 outbox INSERT 注入 `SELECT 1/0`；旧 current 恢复，result/claim/epoch/change/job/outbox 均无部分变化；同 key 可以重试。外层整体回滚也实跑。|
| 单维失败隔离 | epss failed 不改 cvss 当前结果和 claims；额外七态历史逐次持久化，只有最新尝试 current，引用 facts 仍 current。conflict 探针只验证两事实结构门，未声称验证语义冲突算法。|
| 旧库与未知 | 0009 行原值/原 recorded_at 保留，6 个新增来源/发布字段 NULL；空库和 0006 旧 claims 升级保留原值、schema1/legacy 未核验；新的 available 缺 observed_at 时 freshness 仍 unknown。|
| 新进程读取 | 保存后另启全新 Python 进程、独立连接，读取同 result ID/status/current；不是仅 `Engine.dispose()` 冒称进程重启。|
| 权限与输入范围 | 他租户和本租户 viewer 的历史读取拒绝；public viewer 写拒绝；私有 source/claim/evidence 不能引用到 public 结果；跨事件非有效 revision 引文拒绝。隐藏事件返回统一 `resource not found`。|
| 来源支持门 | source_verified/current/supported 或 disputed 非 hypothesis facts 与 validated/supports/verified 引文为必要条件。额外实跑 model_hypothesis、legacy、历史/撤回事实、未验证引文、context/unvalidated link 拒绝，且没有 result 写入。|
| job 与事件版本 | job tenant 不匹配拒绝；旧 business_version 拒绝；实际 EventRepository merge 后源 merged 与目标 version 增量都拒绝迟到维度尝试，既有结果不被覆盖。|

源码核对：输入七态/九维及缺失约束在 `persistence.py:42–79`；事件 ACL/写权限在 `:95–113`；引用事实/引文支持门在 `:115–182`；job tenant 校验在 `:183–189`；scope 发布锁/幂等与事件版本检查在 `:205–227`；current 切换、结果与公共发布收据在同 nested transaction `:229–272`。0010 保留旧列值、新列无伪造默认、拒绝 downgrade；没有另建事实库或内部 commit。

## 索引、调用与独立交叉检查

实际使用官方 portable `codebase-memory-mcp 0.11.0`，只索引固定 `backend/src`，独立 cache `/tmp/dianzi-cbm-r02-dimension-review1-20261015`，`persistence=false`，workspace 无 graph 写入。11:53:52–11:54:07 的 index/schema/精确 qualified search/trace 全部 exit 0：687 nodes、2885 edges、58 source files、parse partial/unusable/skipped 均 0。

`DimensionRepository.publish` trace 连到既有 `knowledge_scope_key`、`publication_payload_digest`、`find_prior_publication`、`save_change_publication` 及验证方法。src inbound 为 0；[rg_callers.log](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/rg_callers.log) 交叉核实目前只有测试调用，API/worker 尚未接线。图是调用分析证据，不代替运行/权限证明。

## 已确认问题、缺测与验收限制

**已确认本切片缺陷：0。** 本轮没有将风格偏好或没有具体触发输入的猜测列作缺陷，没有业务修复或修复复验事项。

**已证实的合同内边界：** `persistence.py:183–189` 只核 job 存在及 tenant。额外 PG 探针把同 tenant job 置为 expired/previous owner 后，该维度 publish 仍可成功。维度输入没有 lease owner 参数，不能称完整 worker fence；[维度细则](C:/Users/yinha/.codex/worktrees/recovery-r02-dimensions-review/dianzi/docs/decisions/CR-R04-R02_dimension_publication.md) 明确由 R03 外层 lease 校验负责。该事实按已批准分工保留，不把未来职责误列为 a366 切片缺陷；后续 R03 必须测试外层拒绝及原子业务提交。

**缺测/未测：** 本轮独立 PG 探针位于专属 run 目录，未纳入仓库常规回归入口；后续接线可择要加入正式集成 suite。此次 contract/security 专用命令、完整知识/auth/MinIO 套件、API/worker 实际协作、跨租户搜索/导出、前端/e2e、live/真实模型、性能/大规模负载、完整来源变更失效、备份恢复和人工验收均未运行。现有 60fe MinIO 审查只作基底背景，不重新签署。真实外部来源/模型和 R07 算法不由合成 PG 探针证明；没有准确率、时延或持续运行宣称。

E1/F1/F2 本批证据仅支持 PG 迁移兼容、逐维状态/历史与权限、事务/outbox/幂等和重启读取；P2 正式效果与整项优秀档未验收。合同与计划未发现本切片偏离；全局任务状态未由审查者修改。

## 交回与产物

本审只新增此报告及 [专属 run 目录](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015)。[artifact_manifest.json](/D:/dianzi/reports/runs/recovery_r02_dimension_review_1_20261015/artifact_manifest.json) 精确列出 62 个 run 文件的相对名、字节数、SHA-256（manifest 自身不做自指哈希）；含 3 个复现脚本、原始日志/XML、所有命令收据、固定 8 源码文件 hash、CBM 5 组命令/输出、rg/diff 交叉检查、测试总数及 secret scan。没有后台占库进程，所有会话连接已关闭，专库仍 0010，资源交回主控。工作树保留固定候选供复核，不覆盖用户 main 修改。

下一步建议：主控只采用本切片限定通过结论；继续 R03 外层 lease fence 与 R04 API/worker 接线及真实端到端验收，保持 R02/R07/G-A 未完成项可见。

**Verdict: Ship，仅固定 a366 维度持久化切片。Not checked:** 上述后续接线、正式专用层与 live/人工/性能验收。

收口：2026-10-15T12:00:21+08:00。run manifest 的 62 个条目已逐一复核哈希，0 不匹配；固定工作树 tracked diff 仍干净。
