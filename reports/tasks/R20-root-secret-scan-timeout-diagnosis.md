# R20 根工作区秘密扫描超时诊断

## 任务与范围

本诊断状态 `awaiting_review`，诊断实现 `complete`；整 R20 仍为已有的 `in_progress / partial`。元数据与局部自检通过，完整根扫描实际失败，unit/integration/live/manual 均未由本诊断执行。未签 `accepted`、未 push、未改共享状态。

输入版本为 `codex/full-delivery-recovery@0ce3ed3af51d7e1c60e75c64fc6fcef71b7b7695` 加主控的五个安全登记 WIP。已读 AGENTS、执行索引、R20 卡、原 T06 卡与数据/API/运维合同、状态及交接；采用 Ponytail 5.2 的最小诊断原则。只写本报告与 `reports/runs/recovery_r20_root_scan_timeout_diagnosis_20261016/`。没有改 scanner、registry、测试、根目录属性、用户 tsbuildinfo、blockers、push log、业务模块或 progress。

资源为纯本地离线诊断。PG、模型、网络 API、付费调用、第三方资产访问均为 0；不读 KEYS.env、holdout、答案或新的秘密来源。不清理任何扫描对象。

## 已证实的结论

1. 原联合 helper 的 `subprocess.run(..., capture_output=True, timeout=120)` 未捕获 `TimeoutExpired`，因此退出 1 时没有把子 stdout、JUnit 或结束收据保存下来。原失败保留，原开始时间为 `history_not_recorded`，不能从 mtime 或后来运行反推原来进入了哪个测试。
2. 当前根工作区在元数据快照中有 20,409 个 eligible 文件、183,171,997 字节；其中 `reports/runs` 为 20,129 个文件、180,188,477 字节。完整排序遍历与 stat 元数据只需约 2.7 秒；136 条分类表加载约 0.203 秒，不能把 registry 初始化称作已证实的长阻塞。
3. 主控单独执行的新 provenance 文件实际为 **144 passed / 0 failed / 0 error / 0 skipped**，耗时 93.844 秒。作者/审查的 **171** 是新 144 项与原 R01 分类 27 项的联合口径；本诊断不重复这批测试。原联合 helper 实际只选择新 provenance 与一个原 T06 根门，不应称作“171 + T06”。
4. 主控批准的 S2 完整原扫描，保留全部五根、七种扩展名、原两种模式和 136 条分类，未注入实际秘密，实际读取 20,420 个文件，109.703 秒后退出 **1**，没有超时。123 条 Finding 中有 97 条已登记 fixture、1 条公开错误比较、**25 条未分类命中**。原门的红灯还包含真实的分类覆盖缺口，不能只靠延长时间宣称通过。
5. 25 个拒绝命中实际分布在 **13 个路径**，全部是当前未跟踪的报告/独立探针；这 13 个路径在 registry 中的登记数均为 0。原 raw hash、LF 和 CRLF 变体都无对应登记，因此本批不是既有登记条目的单纯换行漂移。

S2 使用 cProfile 的跨线程活动快照作为进度探针，产生了不自洽的累计耗时：`scan_repository` 累计小于其 `_canonical_path` 子调用。这是本诊断仪器缺陷，**S2 的函数耗时及热点排名不可用于根因或收益判断**。原 profile、日志与执行脚本字节均保留。真实墙钟、进程退出、原函数调用和 Finding 输出仍为此次实际观测。主控不批准只为修 profile 再做全扫描；准备的 `single_thread_probe.py` 为 `not_run`，本轮没有 S2b。

## 输入闭包与元数据

扫描算法位置：`scripts/security_scan.py:71` 路径边界、`:147` 分类加载、`:186` 原根扫描。每个 eligible 文件重新 resolve repository root、target 与五个 allowed roots，再读原字节、hash、规范换行、执行原模式和精确分类；不会因为未跟踪或属于缓存而自动豁免。

分类表有 136 条，其中原 54 条与 `registry_original_bytes.bin` 的解析内容逐项相等，新增 proposal 为 82 条、15 个 distinct artifact 路径、8 个值哈希家族。测试的运行时文件依赖包括 proposal JSON、原 registry bytes、136 条 table 和 ZIP。ZIP 有 15 个 member，未压缩 member 合计 152,391 字节，ZIP 文件本身 155,593 字节。本探针未解压输出 member 正文。

metadata 记录了 registry targets、origin source、review refs、proposal binding 及上述测试直接依赖合计 55 个路径/引用。52 个按字面路径存在；一个 `review_ref` 带 `#必须修复`，其字面路径不存在不等于正文缺失。另两个 `G-F-R20-secret-provenance-review-1` 与 `-fix1` 报告当时尚未归档到根目录，主控负责补档。scanner load 只校验这些来源与 review 引用的字段格式，不读取其正文；不能把加载成功当作来源内容已验证。

CBM 只索引 scanner 的源码副本一个文件，使用独立仓外 WSL `CBM_CACHE_DIR=/tmp/dianzi-cbm-r20-root-scan-timeout-20261016` 与 `/tmp/dianzi-r20-root-scan-source-20261016`；没有索引 reports、registry 内容、秘密或评测材料。结果 34 nodes / 83 edges，0 skipped / partial / unusable；schema 与 architecture 用 rg 交叉核对。初次 get_graph_schema 缺 project 的 exit 1 保留为工具调用错误，随后指定项目成功。

## 拒绝条目

以下均为 `unclassified_credential_shape`，只列路径和数量。模式、规范文本行与 span、值 SHA-256/长度、raw/LF/CRLF SHA-256、换行计数、registry binding 状态详见 [安全元数据](../runs/recovery_r20_root_scan_timeout_diagnosis_20261016/rejected_findings_metadata.json)。该 JSON 不含 matched_text 或凭据正文。

| `reports/runs/` 下路径 | 拒绝数 |
|---|---:|
| `recovery_gc_integrated_e310_validation_20261016/test_rosters.json` | 4 |
| `recovery_gc_integrated_e310_validation_20261016/test_rosters_before_pg_security.json` | 4 |
| `recovery_gc_integrated_e310_validation_20261016/test_rosters_before_t07_contract.json` | 4 |
| `recovery_r07_default_entry_review1_20261016/independent_idempotency_scope_pg.log` | 1 |
| `recovery_r07_default_entry_review1_20261016/probes/test_independent_idempotency_scope.py` | 1 |
| `recovery_r07_default_entry_review1_fix1_20261016/probes/test_independent_idempotency_scope.py` | 1 |
| `recovery_r07_input_audit_fix1_20261016/probes/test_independent_idempotency_scope.py` | 1 |
| `recovery_r07_input_audit_review1_fix1_20261016/probes/test_independent_idempotency_scope.py` | 1 |
| `recovery_r08_aggregate_connectors_review_1_20261016/test_independent_r08_boundaries.py` | 2 |
| `recovery_r11_sbom_inventory_review1_20261016/resources/test_r11_sbom_inventory_postgres.py` | 1 |
| `recovery_r11_sbom_inventory_review1_fix1_20261016/resources/test_r11_sbom_inventory_postgres.py` | 1 |
| `recovery_r18_api_key_expiry_fix2_20261016/independent_pg_probe.py` | 2 |
| `recovery_r18_api_key_review1_fix2_20261016/independent_pg_probe.py` | 2 |

四份 R07 probe 原字节 SHA 相同，两份 R18 probe 原字节 SHA 相同；报告没有因内容相同而给予复制件豁免。R11 两 resource 的 LF/CRLF 元数据分别记录。所有匹配的 URL userinfo/DSN 和 JWT 形状提示为 false；R08 两匹配满足长 opaque URLsafe 字符串形状。这些只是待审提示，不能证明实际秘密不存在，也不能证明其为 synthetic fixture。25 条真实性均为 `unverified_do_not_register_without_provenance_review`，没有新增任何分类。

此前口头报“15 distinct rejected paths”混用了 proposal 的 15 artifact 路径数；rejection probe 在读取任何拒绝文件之前的断言检测出错误。初次 exit 1、正确 group-by 13 的证据和修正后 exit 0 都保留，最终以本表 13 路径为准。

## 实际命令与结果

执行 Python 为 `D:/dianzi/backend/.venv/Scripts/python.exe`，cwd `D:/dianzi`，均带 `-B`，不写产品 pycache。时间均为真实 `+08:00` 记录，mtime 仅为文件观察元数据。

| 检查 | 实际开始 → 结束 | 退出与结果 |
|---|---|---|
| `python -B .../metadata_probe.py` | 18:58:39.969 → 18:58:42.696 | exit 0；2.719 s；136/54/82 与总文件/字节自检通过 |
| `python -B .../profile_probe.py s1`，主控批准最多256 metadata paths/30s | child 19:02:47.387 → 19:02:48.600 | exit 0；1.203 s；256 canonical call；局部 canonical 累计 0.2797485 s、resolve 1792 call；不读内容 |
| `python -B .../profile_probe.py s2`，主控批准一次 original scan/180s | child 19:02:59.270 → 19:04:48.963 | exit 1；109.703 s；123 Finding/25 rejected；stdout 直落盘，owned child 已退出；累计 profile 无效 |
| `python -B .../rejection_metadata_probe.py` 修正后 | 19:10:15.695 → 19:10:16.689 | exit 0；1.000 s；13路径/25匹配，pattern Counter 与原 Finding 对齐 |
| Ruff check + format --check，四个 own probes | 见各 `ruff_*_final.json` | 最终均 exit 0；初始长行失败和修复过程保留 |

原联合 timeout 收据与主控 144 项的 XML/log/receipt 是读取的主控证据，不计本 Agent 执行。完整 pytest 原 T06 认证/审计 gate、原 R01 27 项、全 Linux CI、实际秘密精确扫描、live/manual 均为本诊断 `not_run`；S2 只是原扫描器的本地调用，不能替代完整 T06 case、准确率或安全验收。

## 最小根因、限制与建议

已证实的最小链条是：根目录额外报告/缓存均属于原扫描对象；144 个 provenance 测试本身约94秒；固定120秒联合 helper超时时丢失证据；完整原扫描实际还存在25个未登记命中。不能据 fresh checkout 的绿覆盖本根范围，不能据不自洽 profile 声称 regex、文件 IO 或 resolve 各自占用某个比例，尚无证据判定环境容量不足或某个模式发生算法退化。

先由新作者逐项核实这13份材料的真实来源、已审版本、原字节与匹配位置；存在真实登录 token、密码或带凭据 DSN 时交主控受控处理，禁止登记为 fixture。确认 synthetic 的候选也必须按原精确 provenance 合同独审，不放宽模式、roots、raw hash、分类或盲测边界。根门保持 failed。

编排层可以把 provenance 与原根门分别有界运行，并在开始时落盘、stdout直写、捕获 timeout、finally保存原始退出与缺失项；这改进失败证据，不改变验收阈值。源代码存在每文件重复 resolve 五个固定 roots 的复用机会，但本轮没有可靠完整热点计时，不建议立刻补业务代码。若后续指定作者优化，只能复用同一次受控扫描的固定边界计算，继续逐文件真实 target resolve、hash 与原模式，并验证 junction/symlink/逃逸边界和全部原对象，不建立长期缓存或永久豁免。

本轮偏差只在诊断仪器与初始路径数统计，均已显式记录；没有业务合同变更。评分 E1/X1 的证据是失败可追溯、原扫描范围保持及真实拒绝元数据；不据此放行 R20、G-F 或最终安全验收。下一任务建议为这25条拒绝的独立 provenance 核验；算法修复须由主控另外指定作者。
