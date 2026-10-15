# G-C / R06 来源块与证据批量持久化

What this change does: The source persistence path writes every parsed block in batches of 500 rows. It retains all raw content and verified coordinates, while fact publication continues through its existing independent validation.

任务状态：**awaiting_review / implementation complete**。作者不签 accepted。代码候选 `a89e94b66e240a0c958f7b7e2b8dc22e88f79348`，tree `25bcfe534c447b5b83d4bceed9b1393cfb266109`；基准 `8a1b04d48346d8550f0326a77f003246a0ebbab5`。工作树 `D:/wt/r06-bulk-evidence`，分支 `codex/r06-bulk-evidence`。原 live 段仍 failed；整 R06/T09/T12/T16/T07、正式时效和持续运行不据此通过。

根因修复已在真实 PG 上保留 **20 docs / 20 revisions / 11,827 blocks / 11,827 evidence / 1 page receipt / 1 response receipt / 1 cursor**。第二次真实原文离线 handler 为 **1.161 秒**、execute_job 为 **1.187 秒**、保存为 **1.023 秒**，Python execute CPU **1.000 秒**，511 次 SQLAlchemy cursor 执行调用，其中 80 次 executemany。作者未施加独立诊断的 20% Windows Job CPU / 每进程 512 MiB / 总 2 GiB caps；这些数字不是相同资源下的正式性能对比，**须由新非作者在原 caps 下复跑**。生产 lease、CPU gate、JSON 节点门和本地 35 秒标准均没有修改。

## 依据和范围

已读取 AGENTS、00 执行地图、12 的 R06、T09/T12/T16/T07、03/04/05/06 合同、对应 source persistence/document parsing/collection catalog 变更、状态与交接，使用插件 ponytail 5.2 full。主仓未提交修改未动；本作者不 spawn/push/改 progress、不运行外部 HTTP/模型/资产任务。

独立慢基线为 `D:/wt/r06-release-pg-diagnosis/reports/tasks/R06-large-release-persistence-diagnosis.md`，报告 SHA-256 `34729c3c141a781250713b16119fcbe59f933f2124c9f81eaa8706f022d0233e`；其 run/artifact_manifest SHA-256 `d223c872a6844f6419521e7164da2b6fdc9ae0427a5b4085dd2f2bf58048d1cc`。该独立报告的两次 execute 55.656 / 54.600 秒、保存 55.438 / 54.433 秒、SQL 实际 71,344（块级 70,962，六次/块）；不沿用早期估算 71,351，不再第三次重跑慢版。原失败由有效 60 秒 lease 内的 35 秒本地 watchdog 终止，baseline 不支持 PG 长期锁死；原失败瞬间无 PG writer 采样的限制仍保留。

生产修改恰为三个文件：

- `knowledge/revisions.py`：新增 source-specific `SourceRevisionBlock` 和 `register_source_revision_blocks`，预 IO 验证全部块；一次 revision 存在/current/精确范围检查与行锁；同 savepoint 的 500 行 Core executemany。块 10 字段、全文证据 15 字段，单批绑定数最多 5,000 / 7,500。批次数据临时列表只覆盖 500 行，不新增总块数限制。
- `catalog_documents.py`：替换逐块六 SQL，批写所有块及全文证据，metadata/pointer/page/ordinal/offset/digest/quote/verified_at/coordinate_version 保留。全文 evidence 的 supports_claim 恒 false。
- `source_documents.py`：仅批写 NVD/vendor 原文块，保留 `_fact_submissions`、旧 `attach_evidence_span` 和知识发布审查；不因块登记而默认事实支持。

旧 `add_text_block` 和 `attach_evidence_span` 定义 bytes 不变。source_response_receipts 的 0016 独立事务、主事务 cursor CAS、物理 outbox、文档和 hash 锁、CAS 读回验证、修订历史、ACL、旧 claim 失效与 scope epoch 不变。没有修改 inputs/publication/enrichment/model/api/通用 jobs/迁移/config/认证/官方指标/金标/计分分母。

额外文件为四个直属测试、`docs/decisions/CR-R06_bulk_source_evidence.md`、本报告和 run 下的可复跑脚本/日志/manifest。第一代码提交 `8d48c95ec525536435c80379f87559a42511a75e` 实现三个源文件、四测试及 CR；第二代码提交仅将 security 测试输入的嵌套三元改为明确条件，生产文件与第二次大页实跑逐 bytes 相同。最终精确 diff 见 `source.diff` 和 Git 提交范围。

## 调用方和兼容性

`all_callers_before.log` 使用基准 git grep，`all_callers_after.log` 使用实际 rg，检索 src/tests/scripts/config/contracts 的全部新旧入口。旧逐条 API 的生产调用仅来源两模块；tests 包括 T05、R02 revisions/relation identity、R04 source documents；catalog 持久化唯一生产调用是 source_jobs 原 handler，R06 catalog/worker/failed-response 测试覆盖。没有需要新增的 export/config 接线。R04 的 quote-mismatch monkeypatch 仍命中原事实证据函数，原 25 个 body 复跑证明未绕开发布校验。

CBM 0.11.0 仅索引本工作树 backend/src，独立项目 `dianzi-r06-bulk-evidence`、cache `/tmp/dianzi-cbm-r06-bulk-evidence-20261016`。初图在修改前完成；catalog 双向 trace 留存 `cbm_before_catalog.json`。固定候选上的 index/schema 和六条双向 trace 全 argv、时间与退出码见 `cbm_commands.json`。索引不含测试/报告/raw/fixtures；AI assets 的源代码可能属于 src 图范围，未读取或索引任何资产材料。图的动态闭包推断仍须与实际 source/rg 相互核对。

## 测试输入与真实 PG

全部新 PG 测试使用自有 `test_dianzi_r06_catalog_bulk_20261016`，端口 25432，独立 UUID schema，forward 到 `0016_source_response_receipts`。私有 WSL connection.json 仅子进程 capture 后在内存解析，不进 argv/stdout/报告；不用 dev DSN，不 downgrade/drop 旧库。旧测试仅清理自有 UUID schema 或本新库 fixture 行；两份 raw replay schema 和 CAS 根保留给 reviewer。

真实公开 raw 仍在仓外 `D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin`，**616,865 B**、SHA-256 `25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7`。没有输出、索引或提交其正文。运行 `execute_job → collect_page → persist_catalog_documents`，注入固定 GitHub URL 的 fixture fetcher，**0 HTTP / 模型 / 资产请求**；真实 PG 与本地 ContentStore 均按原路径校验内容。空 headers 的终页 fixture 只验证负载，不能证明原 Link headers、下一页或 live。

标准 json 从真实 raw 独立遍历叶值及 RFC6901 路径，在内存生成坐标期望；没有用被测 bulk 输出生成期望。20 个 canonical member bytes / 21 个 CAS 对象均核对完整 SHA 与 bytes；11,827 行全部核对 ordinal、Unicode start/end、text/quote hash、json_pointer、page_number、关联 revision/block、locator、public/tenant、supports_claim=false、verified_at、created_at、coordinate_version。`members` 的归档只包含 locator/hash/count，不含正文。

逐条等价测试另用手工 Unicode/JSON pointer/PDF page 输入，经原逐条 API 与新 bulk 保存，比较除独立生成 ID 外的**每个块和证据列**，并核对 block/revision 对应关系。历史与当前 revision 不混淆；重复来源页不增加修订/证据；并发来源/事件关联更新沿用真实 PG 旧回归。

## 真实命令、失败和资源记录

检查入口为 `D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_r06_bulk_source_evidence_20261016/run_checks.py <label> <check arguments>`，shell cwd 本工作树；check cwd 为 backend。每项 `.command.json` 记录 +08:00 起止/退出码/数量/日志，`.log` 保留真实输出。后期 check 通过 `measure_cpu.py` 启动实际 Python 模块，CPU 为 `time.process_time`，不是 PG server CPU；早期命令未有效测量 CPU 的值不能当实测 CPU。`runner_launches.json` 给出 canonical check 和实际 child argv 的映射。

| label / check | +08:00 起止 | exit / 结果 | wall / Python CPU 秒 |
|---|---|---|---|
| red_unit / pytest 新 unit | 初始 shell 命令，未完整封存时间 | 2，ImportError 新入口尚未实现；非环境缺失 | 不补编 |
| unit | 04:10:44–04:10:45 | 0，6 passed | 1.158 / 未测 |
| new_tests | 04:11:43–04:11:46 | 2，同 basename collection mismatch | 2.497 / 未测 |
| new_tests_fixed | 04:12:05–04:12:14 | 1，7 passed / 9 setup errors，仓外 basetemp 父目录未建 | 9.092 / 未测 |
| new_tests_ready | 04:12:40–04:12:53 | 0，16 passed | 13.545 / 未测 |
| fixed_real_release_1 | 04:14:34–04:14:38 | 1，handler succeeded 且 <35 断言通过，后置误用短 migration ID | 4.151 / handler 精确计时未封存 |
| fixed_real_release_2 | 04:15:51–04:15:54 | 0，全 20/11,827 坐标与 bytes 核验 | 3.176 / 脚本2.094，execute1.000 |
| legacy_source_pg | 04:16:04–04:16:06 | 2，CPU wrapper sys.path 未加入 backend，两个 collection errors | 2.272 / 1.938 |
| mypy 三源文件 | 04:16:10–04:16:16 | 0，no issues in 3 source files | 6.745 / 未测 |
| legacy_source_pg_ready | 04:17:06–04:19:05 | 1，127 passed / 25 setup errors；旧 R04 fixture 硬编码旧库名 | 119.024 / 29.859 |
| t05_t07_pg | 04:17:15–04:17:19 | 0，21 passed | 3.881 / 2.266 |
| first_release_readonly_verify | 04:18:01–04:18:03 | 0，只读补核第一份完整 20/11,827，handler 调用0 | 1.968 / 1.297 |
| new_tests_final | 04:18:34–04:18:50 | 0，17 passed = unit6/contract1/security5/integration5 | 16.296 / 4.359 |
| legacy_r04_dedicated_fixture | 04:20:02–04:20:36 | 0，原25 body/期望不变，专用资源fixture适配 | 33.979 / 9.672 |
| security_style_final | 04:22:41–04:22:47 | 0，5 passed，去嵌套三元后定向复核 | 6.150 / 2.359 |
| ruff_sealed / format_check_final | 04:22:57–04:22:58 | 均0，7 files already formatted / all checks passed | 各<0.2 |

旧回归文件为 R06 catalog_documents/source_worker/failed_response、R04 source_documents、R02 knowledge_revisions/relation_identity 和 T05/T07。首轮 127 passed 不能改记为152通过；25个 setup 拒绝保持原日志。主控明确允许仅专用 runner 替换资源 fixture 为已有新库 catalog_engine：同真实 forward0016、UUID schema、real_pg 与专属新库前缀校验，旧文件/body/expectation/case数完全不变；未连接硬编码旧库。25个定向通过单独列示，没有业务断言失败被弱化或 skip。

作者真正 raw handler **恰2次**，脚本 wall 合计 **7.326 秒**，每次 <120 / 合计 <240；没有第三次，也没有把额外小 fixture 回归算大页性能样本。第一份只读补核确认 20 docs、11,827 所有证据与 CAS 完整，但不能补编已丢失的 handler 秒数；早期 launcher GetProcessTimes 的0.015625秒并非实际 Python CPU，不使用它。第二份准确数据在 `fixed_real_release_2.json` 与提前封存的 `fixed_real_release_2_handler.json`。

Ruff 初次 12 errors 后按规则修复，日志保留；format/check、Ruff/check、mypy 和生产/测试/CR 范围的 git diff --check 通过。材料全范围 staged diff --check 实际退出2，仅原样归档的 pytest/CBM/diff 日志包含尾空格或 EOF 空行；记录在 `material_whitespace_check.json`，不修改原输出 bytes，也不新增忽略规则。一次 PowerShell `HEAD^{tree}` 未引用导致元数据命令退出1，随后用准确 list argv / 引用重读为上述固定 tree；不能当业务失败或编造首次通过。

## 八层状态、偏差与交接

| 验证层 | 本轮状态 | 限制 |
|---|---|---|
| unit | passed | 六个预 IO 负例；非全项目 unit suite |
| contract | passed | 500/501 SQL bounded writes 与 source text 非 supporting fact |
| integration | passed，性能同资源门 awaiting_review | 新5 PG用例、旧127+资源适配25、T05/T07的21；作者raw caps 不匹配 |
| security | passed | 五个 missing/historical/scope拒绝；非全项目安全审计 |
| frontend | not_run | 无前端修改 |
| e2e | not_run | 未运行浏览器或部署链 |
| live | blocked_live / not_run | fixture transport 与 ContentStore；无原 Link headers/真实 MinIO/新live段 |
| manual | not_run | 无新非作者评审或人工评分验收 |

计划偏差只有明确披露的测试 harness 前置错误、旧 fixture 的安全资源适配和作者未使用原 Windows caps。没有放宽业务门或缩减范围。F1/E1/R1 的本轮证据只证明完整来源原文与证据写入、事务/范围和可追溯修订；P1 仅有作者负载测量，原 caps 下性能、新 live、正式时效、持续运行、模型/资产/网页层仍需各自真实证据。

封存时另保留 `frozen_materials.zip`，含 manifest 列出的原始工作树 bytes，供跨 Git 换行转换的独立复核；ZIP 不含 raw 正文、资产或秘密。普通文件 sha 指作者实际 bytes，code commit/tree 指 Git 对象版本，不能把换行转换误判为业务内容修订。

下一步：主控的新非作者 reviewer 冻结本候选及 manifest，按原 Windows Job caps 重放相同 raw，经 generic execute_job 核查完整 20/11,827 与 <35，再复查批次失败/权限/历史/幂等/并发/原文与 outbox 路径。原问题和所有 red 保留。通过独立 review 后由主控登记状态；作者不会继续下一任务、提交 raw、push 或自行 accepted。

未检查正式 live/浏览器/生产 MinIO/原 caps；风险是同资源性能尚未被本作者验证，当前候选仅供独立审查。
