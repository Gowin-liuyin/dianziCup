# R11/T24 清单候选解析两项 Must 定向复核

What this change does: 修复只对权限声明的语义哈希排序，并在两个时间入口验证实际偏移、归一 UTC、拒绝不可表示的时间。返回候选仍保留原权限 tuple 与 raw 来源；内部候选继续没有 PG、API 或真实资产调用链。

**限定 Verdict: Ship。初审两项 P2 Must 已关闭，没有新 Must。** 结论仅针对本片修复与候选准备代码；不签整 R11/T24/G-D，不登记 accepted。原 38 个独立探针仍为 37 passed / 1 failed，CSV 方言探索红例如实保留。

实际时钟核对：2026-10-15 18:56:11 UTC，即 2026-10-16T02:56:11+08:00。代码冻结 `64dcd946601cd0e0f7435f59019ee709e3738a35`；材料冻结 `37e492b4e26fc5b6197b60d2494926d4181a21c3`；基线 `e651a0576785de4d8f9bf4e0dd114c8984bfd2d3`。独立工作树 `D:/wt/r11-recheck1`、分支 `codex/r11-recheck1`，从指定材料建立；作者树当时 clean，作者声明仅作线索，结论来自以下独跑。

已复读 [初审报告](D:/wt/r11-review1/reports/reviews/recovery/G-D-R11-manifest-parser-review-1.md)、AGENTS、00 执行索引、12/R11、T24/T29、03/04/05 合同、冻结 progress/交接及 [Ponytail review 5.2.0 官方 SKILL](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)。检查修复 diff、完整受影响函数、调用方和原/新增测试；假设负载仍为声明的每份 10 MiB/10,000 组件纯计算，不推断真实多用户/PG 吞吐。

## 缺陷闭环

| 原编号 | 触发与修复 | 独立验证 | 判定 |
|---|---|---|---|
| 1，权限集合换序改变 hash/ID | [manifest_parser.py:430](D:/wt/r11-recheck1/backend/src/ai_intel/assets/manifest_parser.py:430) 只在语义值中排序非 None 权限；返回 tuple、raw/source hash 继续保留来源顺序 | 原权限红例通过；作者 36 中排列/空值/身份用例通过；自拟 6 排列的语义 hash/ID 相同，6 原 source hash 不同，tuple 顺序完全保留。None 与 [] 不同；依赖路径倒序仍改变组件与快照身份，版本字符串原样保存 | closed |
| 2，时间偏移缺失与 UTC 转换异常 | [manifest_parser.py:320](D:/wt/r11-recheck1/backend/src/ai_intel/assets/manifest_parser.py:320) 的私有函数只读一次 offset；两个入口分别在 371、372 行调用，None 拒绝，已知 ValueError/OverflowError/TypeError 返回固定校验原因与字段定位；候选用已归一值 | 原无偏移和下限溢出两红例通过；作者 36 覆盖两时间字段、缺失/非法类型/非法偏移/上与下溢出/UTC 极值；自拟 28 补齐 JSON/CSV 两入口、+05:45:30 的单次 offset、CSV UTC 极值和 TypeError/OverflowError。无截断、clamp、coerce 或当前时间默认 | closed |

时间修复没有改认证、公共领域时间对象、schema 或其他调用方。固化的是该输入 datetime 已给出的偏移，保留精确瞬时值；候选输出为 UTC，不再调用原自定义 tzinfo。未知异常未被伪造为成功结果；受验证的缺失与不可表示时间均走明确错误。

## 原 CSV 探索红例仍保留

原 probe bytes SHA256 为 `ac13a06334ea163e5c3f95da0d7592aaa7c61a232b1ed7178be6b99983ab2b1c`，初审原件、修复材料 Git blob 和新工作树副本逐字节相同。完整运行 38 例，三个 Must 红例转通过，唯一失败仍是 `test_unquoted_csv_quote_is_rejected_as_malformed_record`：`Name,Ver\nlangchain,1"2\n` 被当前 stdlib CSV 方言接受。

初审已说明当前合同未冻结更严格引号方言，故该例不判 Must，本次维持此判定。没有改 probe、期望、skip 或分母使整体变绿，没有新建自造 CSV 解析器；38 的命令 exit 1 及其 stdout/JUnit 保留。版本有效性由后续生态版本判断负责，本解析器不把 `1"2` 宣称为有效版本或安全状态。

## 实际环境、命令与结果

独立自有 venv 由 `C:/Users/yinha/.local/bin/uv.exe sync --frozen --offline --no-progress` 在本树 backend 建立，exit 0，CPython 3.12.13、79 包来自本地缓存；没有下载、改锁或共享环境。该环境的解释器为 `D:/wt/r11-recheck1/backend/.venv/Scripts/python.exe`。下表 `python` 均是此绝对解释器，pytest/质量 cwd 为 `D:/wt/r11-recheck1/backend`，仅注入本树 src 的 PYTHONPATH 和 UTF-8 输出；收据保存实际完整参数、+08 开始/结束、代码/材料 SHA、退出码与 JUnit。

| 收据 | 实际命令核心 | 退出码 / 结果 |
|---|---|---|
| original_65 | `python -m pytest tests/unit/test_r11_manifest_parser.py tests/contract/test_r11_manifest_candidate.py tests/security/test_r11_manifest_parser_boundary.py --no-cov -q --junitxml=…/original_65.xml` | 0；32 unit + 1 contract + 32 security = 65 passed，0 fail/error/skip |
| added_36 | `python -m pytest tests/unit/test_r11_manifest_parser_identity_time.py --no-cov -q --junitxml=…/added_36.xml` | 0；36 passed，0 fail/error/skip |
| related_112 | `python -m pytest tests/unit/test_t04_domain_contracts.py tests/unit/test_t06_access_scope_boundaries.py tests/contract/test_t18_model_clients.py tests/unit/test_r08_aggregate_connectors.py tests/unit/test_r13_fofa_relay.py --no-cov -q --junitxml=…/related_112.xml` | 0；112 passed，0 fail/error/skip；已有相关回归单列，不重复汇入其他 review 数量 |
| original_review_38 | `python -m pytest ../reports/runs/recovery_r11_manifest_parser_fix1_20261016/test_independent_manifest_review.py --no-cov -q --junitxml=…/original_review_38.xml` | 1；37 passed / 1 exploratory failed，0 error/skip；Must 对应三例均通过 |
| independent_28、independent_28_final | `python -m pytest ../reports/runs/recovery_r11_manifest_parser_review1_recheck_20261016/test_independent_fix_boundaries.py --no-cov -q --junitxml=…` | 均 0；28 distinct 自拟例通过，0 fail/error/skip；最终复跑不叠加用例数 |
| ruff / format | `python -m ruff check`、`python -m ruff format --check` 本片源码与四个直接测试文件 | 均 0；5 文件通过 |
| mypy | `python -m mypy src/ai_intel` | 0；100 源文件无问题 |
| source_diff_check | `git diff --check e651a05… 64dcd94…`，cwd 本树根 | 0；源码修复与新增直接测试通过 |
| frozen_evidence | `python ../reports/runs/…/verify_frozen_evidence.py` | 0；新旧 Git blob、初审原件、probe 与流式归档核验通过 |

我的新增 probe 首次独立 Ruff 有两个 E501 长字节字面量，记录 exit 1；只将新增 probe 的字面量拆成等值相邻 bytes，Ruff 重检与最终 28 例均 exit 0。初审原 probe、作者源码/原测试未改，首 lint 日志保留。格式化也只用于本次新增 probe，不触碰冻结原件。

`--no-cov` 为已授权定向复跑选择，不是正式全工程覆盖率门通过。没有运行 fullsuite，旧四项 CPU/fullsuite 问题未关闭，也不由这些定向结果推断关闭。

## 调用链与静态边界

官方 CBM portable CLI 首先实际 `cli --help`，再以 WSL `Ubuntu-22.04`、root、本次唯一 XDG `/tmp/dianzi-r11-recheck1-cbm` 索引当前工作树，取得独立 schema 后追踪调用。backend/src 图为 1,292 节点/6,424 边，明确默认排除 assets；显式 assets 根另建 108 节点/394 边、5 源文件，not_indexed/parse_partial/parse_unusable 均 0。

assets `parse_manifest` 入向 0、出向 22；时间 helper 入向 1 个函数，源码有两个实际调用位置与一个 UTC 转换位置。全源码/测试 rg 交叉核验，生产入口仍未接入候选。源图的 AccessScope 入向调用保持既有范围；不把图的默认 exclude 当作无资产代码，不把静态图当运行接线证明。

## 冻结证据核验

修复 artifact_manifest 本体为 `c0cb74e7019bf4588e76143d3b019f9ac0c3aa35fc36397f964808bd64689a68`，84 artifact 条目逐固定 Git blob 核对长度/hash，5 源码证明核对 code/material blob 和本树 Git filtered object。源码允许 Git 的 LF/CRLF 表示差异，raw run/probe 按原字节；不将工作副本 raw hash 差异误当源码变更。

旧 manifest 本体仍为 `e1827675743d736036c0d6ded14ce3243280ef96dd694033a431253066d30a92`。其 102 条目全部按基线 e651 blob 核对，其中当前仍有 100 条目字节相同；仅 parser 与 `.gitattributes` 两个旧路径按本次批准修复改变，后者只新增该唯一新 run 的证据属性及四个精确原始失败材料 `-diff`。旧 run、旧报告和原 65 测试未变，旧 parser 历史 blob 仍保留，不能把原源码 hash 当新源码 hash。

初审 manifest 本体仍为 `1c644e365aaf9bf1d5ad9a273f0c85da669f3609162b51cad6cbfc980051c0e0`，其 80 文件逐原 raw 工作字节核对；初审报告、manifest、原红日志都未改。

旧大失败日志的 gzip 仍是 44,590 B、SHA256 `6a03747311af06c0812c21743004c3cc046ac1a2f62dd9b60f004e0ce759cad6`。流式解压与仓外原件 `D:/dianzi-local-evidence/recovery_r11_manifest_parser_20261016/green_boundary.stdout.log` 均为 41,951,937 B、SHA256 `3cccbce776d43c2fb1910a851859ae70de0d3290a387efbd870814e78d8b0323`；未打印巨行、巨大 pytest 参数，未移动/重写原件或停止进程。

## 验证层与原验收范围

| 验证层 | 本轮状态 | 范围 |
|---|---|---|
| unit | passed | 原 32 + 新 36 及必要自拟边界；原 38 总体仍 failed（CSV exploratory）单列 |
| contract | passed | 原候选 1 例与相关已执行合同，不代表公开资产接口合同 |
| security | passed | 原 32 输入/认证/秘密/IO边界重跑；无实际外部资产操作 |
| integration | not_run | PG/认证事务/资产真实归属、KB/生产 caller 未接 |
| frontend | not_run | 本片无 UI 验证 |
| e2e | not_run | 未验证真实导入/历史/current/研判/导出闭环 |
| live | not_run | 0 网络/模型/PG/服务/实际资产扫描，缺真实授权资产范围 |
| manual | not_run | 人工业务验收与真实性/完整性核验未签 |

原 T24 六类验收保持：C01 仅 JSON/CSV 候选规范化，C02 仅纯回放，C03 仅不可变候选差异，C04 仅 unknown/partial 与声明字段，C05 仅受支持方言行/大小边界，C06 仅认证 scope 与输入路径拒绝。PG 幂等/通知、历史 current、真实 asset 归属及完整声明的真实性没有被本片证明。T29 的六项导出、SBOM、四态与产品真值、界面未由这轮完成。READ_ASSET 仍仅是 root 批准的纯候选范围，写权限冲突与正式资产归属留 root。

本轮只新增新复核报告和唯一 run 目录内的离线脚本/证据/manifest；没有改业务、原 tests、progress、domain/schema/lock/auth/API。主仓未提交修改保留，未 commit/push/accepted。评分 F2/F3/P2 仍只有候选输入质量与追溯的局部代码证据，没有准确率、持续时间、正式性能或真实资产结论。后续由 root 决定登记本准备片，整 R11/T24 仍按原卡推进。

Verdict: Ship, limited to these two Must fixes and the pure candidate preparation slice.

Not checked: fullsuite/旧四项 CPU 问题、PG/API/KB 生产接线、真实授权资产、frontend/e2e/live/manual、SBOM/OpenVEX、整 R11/T24/G-D。
