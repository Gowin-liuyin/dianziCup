What this change does: 修复 NVD 文本和时间边界，并将完整响应回收改为先通过 PostgreSQL 删除检查，再删物理原文。新增 register_response_content 复用同 hash 事务锁、校验原字节并登记 PG 对象，由调用方在同一事务完成引用。

复核结论：**原初审三个 Must fix 在本固定版本已关闭，来源组件修复小批限定通过。** 这不是整 R04/T 卡或 G-A/G-B 验收；卡的实现与产品闭环仍 partial，本报告不更改 progress、合同、业务或锁，不提交、不 push。原 needs_changes 报告和失败日志继续保留。

Agent：/root/r04_sources_independent_review（原独立 reviewer，非修复作者）。文档具体写作起止未单独计时，不以测试时刻或文件 mtime 补造；实际命令秒级时刻与结束封存时刻见 receipts/manifest。使用首次已实际读取的新版 [ponytail-review](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，并复读冻结 R04/合同修订、作者记录和入口源码。

## 冻结与未变的原输入

实际目标 `6c7fd7a4a01107acbbfbd90fc7ad62136b0da71b`；tree `226cb707ad7903a2352085ff429c85b3361a8d1c`。基线为初审 `2ff2f999b3824252d54b93af6d1da78ecb6f1427`。新干净分支 `codex/recovery-r04-sources-review-1-recheck`，worktree `C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1-recheck/dianzi`，创建后和封存前 porcelain 均空。

仅复核 NVD/revisions、直接来源与 metadata 回归、CR 兼容说明及本轮证据。未集成的来源写服务、root POST/PDF 小改、其他 worktree 业务不属于目标；root 混合 440 项和作者覆盖率不作本报告证据。冻结版 `api/app.py` 仍只挂 auth/health，worker handlers 仍只含 record_source_fetch_failure，新增 helper 与两个来源 normalizer 的产品装配未完成。

[原 16 探针](D:/dianzi/reports/runs/recovery_r04_sources_review_1_20261015/test_independent_boundaries.py)复制后仅替换一个 WT 路径字符串，未改输入、期望、GC 同步点或 fixture 数据；程序逐字验证此适配关系。原 SHA-256 `967a0646ac4fe86198e7fabb0a4264b909cc4ecb089454340ff7f7daefac1f7b`，本轮 `b49e08a5a56c0e1f1ec0496b813d44690c781917f1db11303dc2be8464655a6f`，见 [输入与覆盖来源核对](D:/dianzi/reports/runs/recovery_r04_sources_review_1_recheck_20261015/coverage_and_probe_origin.command.json)。真实 PG 两种响应 FK 竞争仍在原 ContentStorage.delete_object 入口启动第二线程/Session；允许安全实现拒绝引用，仅对已提交引用要求原文可重读。

## 原三个 Must 的关闭证据

1. **完整响应 GC 竞争已关闭。** [revisions.py:351](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1-recheck/dianzi/backend/src/ai_intel/knowledge/revisions.py:351) 在 savepoint 先执行 PG DELETE，再物理删除；仅 sqlstate 23503 返回 False，其他 IntegrityError 重抛。原 revision/fetch_attempt 两种竞争均通过，不再观察到已提交引用指向缺失字节。自身另加真实竞争，在最后 COUNT 后、DELETE 执行前提交 fetch FK，确认返回 False、原字节仍可读、Session 在 savepoint 恢复后可查询；用专属 schema 的真实触发器产生 23514，确认该错误传播且未删除字节。未扩展到调用方后续主动 rollback 或完整备份恢复的未验证场景。

2. **NVD 未知/非法/损失精度时间已关闭。** [nvd.py:85](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1-recheck/dianzi/backend/src/ai_intel/ingestion/sources/nvd.py:85) 先做明确时间格式检查，再用标准 datetime。原 -00:00、+00:60、7 位小数、偏移带秒四负例全部被明确拒绝；合法 naive 留档仍只有 raw/业务 None，原合法 offset 与 raw 保留用例通过。没有补造发布时间、改变历史行或时效分母。

3. **描述/CWE/reference UTF-8/NUL 边界已关闭。** [nvd.py:156](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1-recheck/dianzi/backend/src/ai_intel/ingestion/sources/nvd.py:156)、166、184 复用 _optional_text，Unicode 编码错误归为明确 ValueError；URL 在原 scheme/host/user 检查前也拒绝空白/控制字符。六个原 NUL/surrogate 负例全部拒绝，真实 API 样本、多 CVSS 版本/机构、缺字段、Rejected 及厂商条件与恶意 URI 回归通过。

新增 [register_response_content:83](C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1-recheck/dianzi/backend/src/ai_intel/knowledge/revisions.py:83) 在 store 前获取同 hash 锁；检查不可变 bytes、带时区时间、存储 hash/长度、read_verified 原字节，再登记 content_objects。本 reviewer 的 11 项独立补测覆盖二次登记一行、原始 Unicode/NUL 字节完整保留、str/bytearray/naive 拒绝、错误 hash/size/read 内容、write/read OSError 传播且无 PG 假登记，以及上述两种真实 PG 错误。此 helper 没有建立第二套事实或缓存。

## 本 reviewer 实际复跑

| 检查 | 实际 +08 起止 | exit / 结果 | 原始 label |
|---|---|---|---|
| 原 16 个独立探针 | 13:27:40–13:27:46 | 0；16 passed，0 fail/error/skip | original_16_fixed |
| 真实留档 + 原 T10/T12/T13 | 13:27:40–13:27:42 | 0；131 passed，0 fail/error/skip | target_original_contract_fixed |
| 原 21 PG + 新 helper 正例 | 13:27:40–13:27:52 | 0；22 passed，0 fail/error/skip | pg_source_migration_t05_fixed |
| 纯 unit 原门槛 | 13:27:40–13:28:09 | 0；396 passed，0 fail/error/skip | pure_unit_fixed |
| 新 helper 补测首轮 | 13:29:10–13:29:18 | 1；10 passed / 1 自建测试失败 | response_helper_checks |
| 修正查询后的 helper 补测 | 13:30:14–13:30:23 | 0；11 passed，0 fail/error/skip | response_helper_checks_final |
| Ruff / format | 13:30:14–13:30:16 | 各 0；11 文件 | ruff_changed_fixed / format_changed_fixed |
| mypy | 13:30:16–13:30:17 | 0；65 source files | mypy_all_fixed |

真实命令、cwd、+08 秒起止、退出码、test counts、版本、log/XML 在 [本轮证据目录](D:/dianzi/reports/runs/recovery_r04_sources_review_1_recheck_20261015) 各 `*.command.json`。重复运行不可相加为独立测试总数。环境 Python 3.12.13、pytest 8.4.2、pytest-cov 6.3.0、Ruff 0.16.9、mypy 1.20.2、SQLAlchemy 2.1.1、psycopg 3.3.6、实际 PG 16.14；未装依赖或改锁。

原始 coverage JSON：**2606/4154 = 62.73471352912855% ≥ 原 60**，missing 1548、excluded 42。所有 run 均设置 label 专属 COVERAGE_FILE；纯 unit 的 `pure_unit_fixed.coverage` 原文件与 JSON 同时保留。CoverageData 实际 53 个 measured_file 均来自本 frozen Windows worktree，unexpected roots 为 []；未用 default .coverage、跨 OS 合并、root65.50% 或终端63%作门槛证据。

本轮新增 helper 首轮唯一失败是 reviewer 查询未按响应 hash 筛选，选到 seed_document 插入的占位零 hash；GC已返回预期 False，属于自建测试错误。仅补充该查询的 hash 条件后 11 项通过，原失败 XML/log 和 response_helper_first_snapshot.py 保留；不改变业务预期或金标。原 16 探针无修改、无失败。纯 unit 的既有 Starlette deprecation 与仓外证据测试导入 seed helper 的 real_pg marker warning 均留档，没有因此 skip。

## 真实调用路径与边界

实际 CBM 0.11.0：help → 新独立 index → schema → trace，缓存 `/tmp/dianzi-cbm-r04-sources-review-1-recheck-20261015`，仅索引自身 frozen backend/src；844 nodes/3686 edges，未索引/skip/partial/unusable 全 0。helper trace 到 _lock_content_hash、store_bytes、read_verified、PG 登记；GC trace 到 hash lock/ContentStorage，NVD trace 到 record/文本/时间/CVSS。图中 GC heuristic self-edge 不作真实调用依据。

随后 [frozen rg 与入口源码](D:/dianzi/reports/runs/recovery_r04_sources_review_1_recheck_20261015/frozen_fixes_and_callers.log)交叉确认：本目标里 helper 仍只有定义/测试调用，来源 normalizer 尚无产品 worker/API 路径。不能用图无边单独证明缺路径，也不能将本次直接 Session 测试算来源产品入库。另一 worktree 的来源写服务应在新冻结版独立接线验收。

性能结论限于实际有界输入：每例单原文和两 PG Session、3106/8800 字节留档；本轮未跑吞吐、大库或端到端延迟，不推导时效/准确率。schema、DTO、评分、原卡六项、金标/分母未改。G-A 未通过时仍可独立推进纯来源解析、前向兼容持久化及隔离边界测试；本报告不授权跨阶段或跳过真实网关/任务/游标/页面前置。

## 交接状态

限定 unit/contract/integration 与静态检查通过，原三 Must 无未关闭项；security 仅边界检查，整卡 not_run。来源实际 fetch→PG→event/alias→证据→API→browser、MinIO、模型、持续运行、正式指标与人工验收本轮均 not_run，整 R04/G-A/G-B 仍不签通过。模型付费调用 0，外部来源 GET 0；未读用户真实产品 key、KEYS、.env、holdout，未执行 PoC 或资产扫描。

只新增本报告及本轮 run 目录，不修改作者修复、progress/合同/业务/锁。自己的专库 test_dianzi_r04_sources_review_20261015 再次独立创建，每例 schema 自行清理；13:32:42–13:32:49 验证无 active session 后已释放，未升级/降级其他库。没有长期后台进程；CBM独立项目在封存前释放，干净原/new frozen worktree保留用于证据复核。

原始日志、脚本、JUnit、coverage二进制/JSON、输入适配 hash、源码 blobs、报告 hash 与完整 manifest 留档。实际测试凭据全值和所有连续 8 字节片段扫描见 credential_scan.json，不打印秘密或连接；历史首次失败不删除。下一步由主控在固定版本接通来源写服务和产品入口，再取得原 R04 完整闭环与新的阶段审查。

Verdict: Ship this reviewed source-component fix batch. 原三个 Must 关闭；没有整卡/stage acceptance。

Not checked: 未集成来源写服务/worker/API/browser live链、MinIO、模型、持续监测、备份恢复全场景、正式评测与人工验收。
