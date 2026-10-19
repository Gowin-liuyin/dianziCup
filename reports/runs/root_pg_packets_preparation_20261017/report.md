# Root PG packet preparation · 2026-10-17

任务 `root_pg_packets_preparation_20261017`，状态 `awaiting_review`，准备实现 `complete`，包状态 `prepared_not_run`。只新增 `D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/`；未改 Root/App/schema/migrations/progress、原 helper、业务断言、费用授权或资源。没有创建新 WT、提交、push 或 accepted。Root 当前 branch `codex/full-delivery-recovery`，HEAD `0291d197587141b9f7f5da0d01800d8cbdf58d11`；已有用户修改保持。

任务授权首先为 R10/R16 参数准备，随后 Root 明确追加 R16 controller 构造与 QA19 首窗准备。已读 AGENTS、execution map、R10/R16 卡、CR-R10 graph validity、CR-R16 HTTP、测试合同、task_state 与当前 handoff；采用 Ponytail 5.3.1 full。R10/R16 整卡当前 in_progress/partial，本工具包没有升级整卡验证层。

## 文件与实现

`launch_root_pg_packet.ps1` 以 `-File -Packet <exact path> -Group <single whitelisted label>` 启动指定固定 controller。`launch_bindings.json` 绑定三个 packet 的真实 schema、controller/worker/admission/source raw 和 mtime，且把 Root 当前 31 迁移加入每次前置核验；packet 按 QA、R10、R16 排序。严格核输入后仅 Root runtime 在内存读取原 DPAPI，清空继承环境、使用 ArgumentList 参数数组、隐藏进程窗口、600s UTC authority、60s outer timeout与拒绝覆盖原收据。helper 不支持任意命令/URL/SQL、任意 packet 或 budget 参数。

新 `r16_pg_support/` 共 13 文件。7 helpers 从已 actual closed R18 母板 byte-exact 复制：process metadata、native limiter、parent lock sampler bridge、phase plugin、process identity、worker entry、migration entry。三个改变文件的完整差异见 `run_pg_review.py.mother.diff`、`pg_review_environment.py.mother.diff`、`task_pg_identity.py.mother.diff`。改变仅固定 WT/source/baseline/material、authority/nonce/schema/sampler名称、原 packet fixture_guard plugin、准确 evidence 描述；controller 所有原 Assert AST 不变。JSON plan/admission/packet 为新的受控材料，不是业务合同。

R16 精确 13 leaf nodes 从 reviewer 已封存的 collect13 raw 输出恢复：原 HTTP12 + reviewer trusted fixture HTTP1。原 fixture、mode probe、19 个作者切片 source/test 的 raw 均核对；另一个 author modes PG1 没加入。生产 `run_migrations` 与 head0031 完整保留；母板当前 migration entry 已无 R05 seed，原 `history_engine` 自建 schema 与 finally DropSchema 无改动。R16 admission 冻结全部 backend source/migrations/tests 和直接探针/guard/packet，695 source files /11 entry files；没有用收集数声称 PG passed13。

| 包 | fixed source | entries/source raw | 组与不同原节点 |
|---|---|---:|---|
| QA | `07664fd7f328803ade6f30372bfd04c395033a42`；workflow `e310b1a8f5a47a8e7f409805d034472b1f8a4306` | 12 /255 | 7 labels：3+3+3+3+3+3+1=19 |
| R10 | `986b01ea21b9cc51d5bd30bd569a8fc63af0d3ba` | 14 /242 | `pg_policy_original4`=4；synthetic GraphStore，非 Neo4j |
| R16 | `14ce965b66fbf8f74221eb01e1426cf1636ea9fc`；UI `dd35f7a90bb8573e2acbd62319a62577804fcddd` | 11 /695 | `pg_history_original13`=13 |

| 包 | controller raw SHA256 | admission raw SHA256 | worker raw SHA256 |
|---|---|---|---|
| QA | `aa7d94bcd52e49ee05b3381077f0cdec825f1892cef85db16a05e7979a106c0b` | `fdbc913cc261aefceecd0258414f6a348ea4d492136f862363c6c056d118cf35` | `c6bf4c406fc7bc61652999dc70c1e7f57ec82ddcf3a2cc5432e9f1ae75f83dbe` |
| R10 | `6554917073e997895a41e010d0bba0e4163146cc369ab1d8ca3486d3a9133964` | `dbd1a152416b8658a202235d4f7c42be310be928ca5f048f0e46d4a1515d7bd5` | `c6bf4c406fc7bc61652999dc70c1e7f57ec82ddcf3a2cc5432e9f1ae75f83dbe` |
| R16 | `a18ba06453ff07425333171776bcce0e7eda5260f374ae207a8e0d0fbb688f8f` | `3b62da3d23fe714ac221ef52dfc1413aa5083b8f95d54882cfe4debf49e82da6` | `c0fb18c77711223557c0568107aad0160571e6e00b0cdb2e79f7999514085dde` |

原完整 R16 reviewer packet 路径、SHA 与13节点记录在新 `r16_pg_support/root_launch_packet.json`。其 input/material 与 source19 来自固定独审 `G-E-R16-R17-change-history-review-1-recheck-fix1.md`；不把旧5ff、历史 CBM 或 author194加成这次实际测试。

## 实际校验与原失败

首次命令 `& 'D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/bounded_prepare.ps1'`，exit1，约2.30s；已生成受控输入后，syntax-only subprocess 的旧 `C:/Program Files/PowerShell/7/pwsh.exe` 不存在，WinError2。`bounded_prepare.stdout.log/stderr.log` 保留原字节。该错误属于工具 executable 路径，不是 PG/业务测试失败。通过读取当前 PowerShell 进程路径确认实际 bundled runtime；只将后续语法检查改为已观察的绝对路径。

最终命令 `& 'D:/dianzi/reports/runs/root_pg_packets_preparation_20261017/bounded_verify.ps1'`，exit0；实际区间 `2026-10-17T13:37:02.882846+08:00`–`2026-10-17T13:37:04.011560+08:00`，内部1.141s。9s native watchdog /10s outer，512MiB/process /1GiB/job /2 logical CPU /native9；job测得CPU1.1875s、peak memory49,582,080 bytes、结束active1（校验器本身）。只运行 stdlib/固定 native limiter和语法解析器，未启动业务资源；业务测试执行0。

结果：1256 个不同 frozen inputs 的 raw/mtime核对；2985 个细粒度准备检查；13 Python文件 AST parse 与5 PowerShell文件 Parser.ParseFile exit0。这些是工具层检查，不是2985业务 unit cases。`verification_receipt.json` 记录精确时间、argv、结果、预算与全部check名；`input_manifest.json` 记录原始SHA、长度、精确mtime。

Root与R10/R16/QA三组31迁移共93文件对照；每组前30完整raw换行归一与whole AST相同，0031同样相同。不是只检查revision名称。原始raw是否字节相等、双方SHA、归一SHA、wholeASTSHA均在 `migration_compatibility.json`；没有运行迁移、修改旧迁移或替换oracle。

`launcher.mother.diff` 保存旧 actual Root R18 launcher 到本通用helper的完整差异；git no-index比较实际exit1仅表示文件差异，收据 `launcher_diff_receipt.json`，Git提示LF将在未来checkout转CRLF，没有修改原文件。

`preserved_failures.json` 只读冻结旧R10 independent3红/原oracle preflight/原4PG脚本，以及R16首次 M01红、原PG反例、修复独审最初 fixture credential类型红的 raw。R10原4PG前置Name(now)修复与11 Assert不变记录原样保留；没有重写旧红、失败改skip、改门槛或分母。首次准备路径错误亦保留。

## 六层状态与剩余

| 层 | 当前事实 |
|---|---|
| tool unit | passed；13Python+5PS syntax only，业务unit0 |
| tool contract | passed；frozen hashes/mtime/schema/93迁移/原controller Assert AST |
| integration / PG | not_run；本准备者连接0，无实际XML通过数 |
| security / frontend / e2e | not_run；未运行产品安全/UI/浏览器 |
| live | not_run；无model/source/FOFA/Neo4j访问 |
| manual | not_run；未代签人工或阶段验收 |

controller/child/outer 58/48/60、2target+1sampler≤3、512MiB/1GiB/2CPU、native9+outer1严格保留；Source OID10451302/10434264的身份与注释只比较不修改。成熟parent角色可实际是superuser，因此最多声称sample观测峰值，不能把rolconnlimit=2说成硬连接cap。准备者没有独立验证正在运行的Source requested/effective PID/birth或实际root资源；这些由Root在真实窗口前检查。original packet的author material未给已知SHA的字段保留原值，不猜。

评分只新增工程可复现性/版本与资源准备证据，不能计F1/F2/F3/A1产品完成、PG通过、真实live或性能分数。合同/计划偏差只包括Root明确追加R16受控准备与QA19映射；没有业务合同或阈值变化。

下一建议：Root按 `root_operation.md` 先QA七个独占窗19，再R10原4、R16原13；每窗核原始XML/command/samples/cleanup/ownbirth0，失败保持原证据后回给指定作者。Root源码新导入需要新的冻结映射与review，不使用此准备包移签。helper frozen raw `2cb1c7b05d7f077f9efff443f68df7659875e3ac0ed876307f66090e082a53ef`，bindings raw `852217ca0703f76fbe01f8a69799bbc51d2428a20ca54129883f726582142d9a`；最终本目录清单以 `file_manifest.json` 为准。

未检查真实PG/live/manual；本报告只交付准备能力，不能代替后续Root实际运行与独立评审。
