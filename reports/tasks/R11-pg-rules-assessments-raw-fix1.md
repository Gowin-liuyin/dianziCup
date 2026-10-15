# R11 / T27–T28 PG 原文当前性 fix1

状态：`awaiting_review`；本修复实现 `complete`，整 R11 仍 `partial`。作者不签 accepted。独立初审 `needs_changes` 和原来的两个红例均保留；本轮是对同一根因的最小修复，待原独立 reviewer 定向复验。

代码冻结：`2ddc8fe2ff3e7becfad3b1774a10407911eacbe6`。原代码 `d56a1ed306d975be408a2f6f8fbe3e905d940643`、原材料 `ad122224b02ec16194e03f937b02a218ff6faaa5` 不改写。工作树 `D:/wt/r11-pg-assessments`，分支 `codex/r11-pg-assessments`；没有 push、进度状态或生产数据库变更。

## 根因和改动范围

初审指出 `AssessmentService.commit` 与 `_read_result` 把 `None` 交给 `load_rule_inputs`。准备时原文正常、此后 CAS 损坏时，只比 PG 指纹仍能写入或返回 current。原文存在、可访问以及哈希/大小正确不能由准备收据永久代替。

修复只修改 `backend/src/ai_intel/assessment/assessment_service.py` 与 `rule_persistence.py`，新增直属 `backend/tests/integration/test_r11_assessment_raw_rechecks_pg.py`。共享加载接口现在必需 `ContentStorage`，两个遗漏调用均传真实 `self.content_store`；每次 commit、read、replay 经 `read_verified` 重新打开源 roster 的原文，再核实际长度与 SHA256。其他 create/validate/review/publish/prepare 调用原本已经传真实 store，此次用 fresh CBM 图、源码 rg 和类型检查核对所有调用。没有 nullable 或跳过核验路径。

已批准的 PG 锁顺序不变。认证、来源 ACL、源/document/revision 配对与 roster、规则生命周期、资产快照及 scope epoch map 仍从 PG 重查；有界原文 IO 位于这些锁覆盖的输入核验点。未增加可能与 ingest/GC 逆序的内容 hash 锁，也未增加缓存、公共参数、依赖、表、迁移、API 或 worker。仍为单源 2 MiB、每次加载总计 8 MiB、源 roster 20 条的既有上限。

正常 ContentStore 写入沿用内容寻址对象：已有损坏对象报错，不覆盖修复；实际 `cleanup_unreferenced_object` 检查 document/revision/fetch/source-response 引用后，拒绝删除已引用对象。新 PG 用例验证这些实际调用。外部存储和直接文件损坏不能假定永远不会发生；当前性核验点实际读取 bytes，下一次读或提交重新核验，不把永久安全归因于 CAS 命名。

缺失或损坏原文明确抛错，不写新 current、不吞成空结果、不伪造否定。已写历史的不可变 payload 保留，原文丢失后不能由 read 返回 current；直接 PG 历史检查仅验证原创建收据没有覆盖。跨租户不可见结果先拒绝，不打开原文，也不返回 evidence body。ACL/role 变化拒绝无新结果、来源/资产变化保存 stale 的旧边界仍由原 33 项验证。

## 真实测试和证据

时间均为 Asia/Shanghai，精确到秒。实际完整 argv、cwd、exit code、elapsed、stdout/stderr 与 JUnit 位于 `reports/runs/recovery_r11_pg_assessments_raw_fix1_20261016/commands.jsonl` 及同目录文件。命令经 `D:/dianzi/backend/.venv/Scripts/python.exe <run>/run_checks.py <label> ...` 执行；PG 连接只从已授权 WSL connection.json 内存读取并以环境传递，未打印或放 argv。

| 标签 / 实际核心命令 | 开始—结束（2026-10-16 +08:00） | exit | 结果 |
|---|---|---:|---|
| original_two_red：`-m pytest` 精确两个独立 repro 名称，`--no-cov -q --junitxml=…/original_two_red.xml` | 06:42:33—06:42:36 | 1 | 修复前 2 failed，DID NOT RAISE；保留原红 |
| raw_rechecks_green：`-m pytest tests/integration/test_r11_assessment_raw_rechecks_pg.py --no-cov -q --junitxml=…/raw_rechecks_green.xml` | 06:43:02—06:43:08 | 0 | 当时 11 passed，迭代记录，不能累计计数 |
| original_pg_33：`-m pytest tests/integration/test_r11_pg_assessments.py --no-cov -q --junitxml=…/original_pg_33.xml` | 06:43:46—06:43:58 | 0 | 原 33 passed / 0 skipped，原测试 blob 未改 |
| related_354：`-m pytest` 原 T26/version branch/manifest identity/T27/condition schema/security 七文件，`--no-cov -q --junitxml=…/related_354.xml` | 06:43:46—06:43:50 | 0 | 原 354 passed / 0 skipped，未改断言/金标/阈值 |
| all_types：`-m mypy src` | 06:43:46—06:43:47 | 0 | 126 source files |
| raw_final_12：同新测试文件 | 06:45:08—06:45:15 | 0 | 当时 12 passed，迭代记录，不能累计计数 |
| raw_final_15：同新测试文件，`--junitxml=…/raw_final_15.xml` | 06:46:56—06:47:04 | 0 | 最终新 15 passed / 0 skipped，pytest 6.27 秒 |
| frozen_quality：`-m ruff check` 两个修改源文件与新测试 | 06:47:26—06:47:26 | 0 | passed |
| frozen_format：`-m ruff format --check` 同三文件 | 06:47:26—06:47:26 | 0 | 3 files already formatted |
| final_cbm：`<run>/cbm_audit.py` | 06:46:36—06:47:03 | 0 | 新 src/assets 独立 index、schema/architecture、commit 与资产 import trace、rg callers 均 0 |

最终新 15 项覆盖：两项原精确输入；commit/read/replay 原文缺失；健康三路径每次重读且重放后损坏拒绝；store 返回值的等长错误 hash 与错误 size；实际 PG 父对象锁等待期间原文替换或丢失；原文 IO 核验点阻塞 revision writer，提交后 writer 变化再读 stale；不可见结果不打开原文；正常存储写/GC 不覆盖或删除引用对象。原红输入字面 bytes 与 reviewer 的 `b"independent review: damaged CAS object"` 相同。

专用库 `test_dianzi_r11_assessment_20261016` 与旧作者随机隔离 schema 复用，receipt 标明 forward 0019 和原 6 个局部表；本轮没有 create/migration/drop/downgrade。正式 0021 仍由 root 独占，`not_run`。

独立 reviewer 初轮 10 项 / 2 red / 8 green；其追加诊断轮 12 项 / 2 red / 10 green 是同一轮分母，不累计。原 reviewer 文件未修改。本材料仅逐字保留 `test_independent_boundaries.py` 为 `independent_probe_original.py` 并记录 SHA256，未执行这份复制件；其中 observation 测试记录修复前漏洞、seam 测试只是 monkeypatch 对照，不能把它们当修复后的产品断言。作者重现只复制两个行为用例到直属新测试。

原材料 118 项 raw artifact 逐字/已提交 Git blob 双重 SHA256 复核不变；新增材料有独立 manifest。修改源、真实其他 callers、ContentStore/GC 与原 PG 测试共 7 个已提交 source blob 记录工作树 SHA256、Git blob ID 与 blob SHA256。secret scan 使用实际测试密码但只记录匹配名单，必须为空。审核复验将记录新轮次，不能覆盖原红。

## 未运行、合同影响和交接

unit/contract 与整个基础报告保持原真实记录；本 fix 的 PG integration/security/concurrency 与相关回归如表。frontend/e2e/live/manual、provider/source/model 外部调用和生产 0021 为 `not_run`；三类外部调用均 0，费用 `unknown`。fixture approver 仍不是人工标签，human labels 0，必要性语义审核真实人工输入缺口未消除。修复不证明产品 gold 或真实线上审核通过。

按 root 冻结边界使用原 PG 锁内有界 raw IO，公共合同和 schema 不变，局部内部 store 参数从可选变为必需。沿用完整 epoch map、published rule 显式版本和 source/asset fingerprints；没有仅 scalar epoch 判等、没有 retired 历史复活。整 R11 的默认 latest API、无规则任意空结果/T36 接线、前端、OpenVEX、真实人工规则收据、外部 live 等缺口见原报告，不在本修复中冒称完成。

下一步：root 向原独立 reviewer 交付新冻结 code/material，按原两个 probe 精确输入和新增边界独立复验；作者保持 awaiting_review，不自签整卡或改 progress。
