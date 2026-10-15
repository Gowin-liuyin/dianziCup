# R11 / T26 · 分支上下文与排除审计最小修复

状态：awaiting_review；本次修复实现 complete，原 T26 / 整 R11 / G-D 不由作者验收。
旧固定 code：`3e896da58bdcabdd738a3430f7b77358e7f8b03a`；旧材料：`5a35cc5e6dec307e7d5fbdf06c9d49881679cb61`。
修复 code：`65838b42c0dcff863036968e39a1404aa323b3c9`；新测试 import spacing 修正后最终冻结 code：`71e724131daf4d03372392d58cd17c764c3e2e40`。
材料 commit / manifest 本体 SHA256 在最终交接单独提供，不用自引用哈希。
记录时间：2026-10-16T02:10:39+08:00；所有 receipt 保存实际 +08 开始 / 结束、argv、cwd、exit、当时 HEAD 和 PYTHONPATH。

## 1. 依据与复现

已重新读取 AGENTS、00_execution_map、恢复 R11 / 原 T26、03 / 04、状态和交接；Ponytail 5.2.0 full 继续生效。
读取独立 reviewer 的 `G-D-R11-version-ranges-review-1.md`，按主控明确授权只处理 Must 1 与同路径 Should 2。
独立报告在 `C:/Users/yinha/.codex/worktrees/r11-version-ranges-review1/dianzi/reports/reviews/recovery/`；作者未修改 reviewer 工作区。
原调用链及接口范围见 [首次切片报告](R11-version-ranges.md)。主工作区未触碰；沿原独立 worktree、分支 `codex/r11-version-ranges` 实施。

先逐字复制原 `test_independent_version_cases.py` 到本新 run，SHA256 两边均为
`b76bd21296694bf47cebf01d2878f22f17830bb86d8fbdbedfa166a6630af5e6`。
原 33 案例未改输入、期望、参数、case ID 或分母，也未 skip / 格式化复制件。
修前实际为 28 passed / 5 failed / 0 error / 0 skip，exit 1：四项空 / 空白 / 整数 / bool 分支错误排除，一项可信排除丢失显式缺口审计。

另先定义 67 个直接边界：非法资产 / 来源分支、200 / 201 字符、首尾空白、C0 / DEL / C1 / 零宽不可打印字符、整数 / bool、合法精确匹配 / 异分支 / Unicode / 内部空格、显式或排除命中下非法资产上下文仍未知。
新测试修前为 6 passed / 61 failed / 0 error / 0 skip，exit 1。原红日志与 JUnit 完整保留，没有以修后绿覆盖。

## 2. 最小实现与文件

仅生产改 `backend/src/ai_intel/assessment/version_ranges.py`：23 行新增、2 行删除。
新增直接测试 `backend/tests/unit/test_r11_version_branch_context.py`；原 94 项的三个测试文件逐字节未变。
新增本报告、`reports/runs/recovery_r11_version_ranges_fix1_20261016/` 原始证据 / helper / manifest。
`.gitattributes` 只追加本新 run 的 `*.log`、`*.xml`、`*.json`，及精确原样复制的 reviewer Python 案例文件四条 `-text -diff`。
公共 domain/schema/lock/auth/API/worker/assets/settings/progress、旧 CPU 实现 / 测试 / 阈值、原六验收、盲测和评分分母全部未改。

新增唯一共享 `_valid_branch_label`：None 仍表示缺失；非 None 必须为严格 str，1–200 字符，无首尾空白且可打印。
200 沿既有 enrichment `Label` 上界；不修改其公共模型，不使用 cast / Any / ignore 掩盖合同。
不把 bool / int 转成字符串，不 trim 原身份。Unicode 与内部普通空格仍合法，两个合法但不同的标签仍明确不匹配。

`contains_version` 与 `evaluate_version_assertion` 共用的区间判断先验证资产和来源分支，非法返回 unknown / 可定位 reason。
汇总保留每个 interval_results；非法资产分支即使有独立精确显式命中或可信排除也保持 unknown，并保留 `invalid_asset_branch`，避免早退路径绕过上下文校验。
来源分支缺失 / 无法解释仍保留局部未知；其他独立精确命中与已有可信排除语义不被撤销。

Should 2：可信排除返回移至显式版本解析和 unresolved_reasons 汇总之后。
排除事实仍为 `not_affected / explicitly_excluded`，同时保留 `missing_branch`、`invalid_explicit_version` 等来源缺口。
晚到非法 exclusion 仍 unknown；没有通过把可信排除状态改成 unknown 来讨好测试。
依赖仍是已锁 packaging 26.3 / semver 3.1.0，未新增框架、生态适配、命令执行或 IO。

## 3. 真实检查

cwd：pytest / Ruff / mypy 为本 worktree `backend`；CBM / rg / diff 为 worktree 根。
完整真实命令均在新 run 同名 `.receipt.json`；stdout、stderr、JUnit 为原 bytes。

| 记录 | 实际子命令核心 | exit / 结果 |
|---|---|---|
| independent_original_red | `pytest ../reports/runs/.../test_independent_version_cases.py --no-cov -q` | 1；33 cases = 28 pass / 5 fail，无 error / skip |
| new_boundaries_before_red | `pytest tests/unit/test_r11_version_branch_context.py --no-cov -q` | 1；67 = 6 pass / 61 fail，无 error / skip |
| fixed_logic_first | 新 67 + 原独立 33 | 0；100 passed，实施中尚未冻结，未冒充固定 SHA |
| original_94_prefreeze / original_175_prefreeze | 原作者 / 原相关集 | 0 / 0；94 / 175 passed，实施中 |
| fixed_original_94 / 175 / 33 / new_67 | 首次固定修复 658 的四集 | 0；94 / 175 / 33 / 67 passed |
| fixed_ruff | 固定 658 `ruff check src tests` | 1；新测试 import block 多一个空行，保留 I001 原红；只改该空行后另提交 |
| final_original_94 | 最终固定 71e `pytest` 原三新文件 `--no-cov -q` | 0；83 unit + 3 contract + 8 security = 94 passed，0 fail / error / skip |
| final_original_175 | 最终固定 71e 原 T04 / R07 / OSV / T11 / R02 相关集 | 0；175 passed，0 fail / error / skip；包含同一原 94，不能相加当独立数量 |
| final_original_33 | 最终固定 71e 原样独立复制件 | 0；原 33 passed，0 fail / error / skip |
| final_new_67 | 最终固定 71e 新直接分支上下文集 | 0；67 passed，0 fail / error / skip |
| final_ruff | `python -m ruff check src tests` | 0；全后端通过 |
| final_format | `python -m ruff format --check src tests` | 0；246 files |
| final_mypy | `python -m mypy src/ai_intel` | 0；100 source files |
| final_diff_check | `git diff --check` | 0 |

最终行为检查实际时段 02:09:07+08:00 至 02:09:11+08:00，具体微秒见 receipt；数量由 JUnit 核对，不由耗时推算。
原六 T26 验收及成熟组件语义负例在原 94 内未删，固定重放仍通过。
新 67、独立 33 与相关 175 的联合独立案例集合为 275；各次重复执行不累计为新的案例或性能指标。

本轮不再跑 fullunit 或 R20 碰绿。旧固定 3e 原全量保持 1627 pass / 4 R20 fail / 0 error / 0 skip，71.03% 达原 60% 门但整体 failed。
三个相关 guard / PDF / 原测试文件本轮与旧固定 5a 的 Git blob 相同；原报告已与 349 核实一致。
`preserved_blob_verification.json` 另保留原 94 测试、公共值、依赖与锁文件原字节同一性。
没有把未修改这些路径当完全因果证明或环境免责，也未覆盖旧失败日志；缺口仍交所属 R20 审查处理。

## 4. CBM 与调用方

修改前真实 CBM 0.11.0 help、独立 `r11-version-ranges-fix1-src` 当前 src 索引 / schema / shared interval trace 与全源码 rg，均 exit 0。
修改前 1310 nodes / 6500 edges；最终 71e 刷新为 1312 / 6507，96 source files，partial/unusable 0。
最终 schema、`_contains_parsed_version`、`_valid_branch_label` traces 和全 src / tests / scripts / contracts rg 都在新 run。
共享 interval 的真实 inbound 为 contains / evaluate；新增校验由该共享判断与汇总使用。没有新增生产 API / worker inbound。
工具默认排除 assets / cache，未据此宣称 assets 已索引或功能完整；修复仅针对两个内部入口，原独立 review 的资产源码核对结论与本片范围保持。
索引 cache 在工作区外、persistence=false，未索引秘密、holdout 或用户资料。

## 5. 状态、限制与交接

本轮限定 unit / contract / security 自动检查通过；作者只交 awaiting_review，Must / Should 是否关闭由原独立 reviewer 定向复核。
整仓库 fullunit 本轮 not_run，旧 failed 不抹去；integration / frontend / e2e / live / manual / performance 全部 not_run。
没有 PG、模型、HTTP、FOFA、真实授权资产或三产品真值验证，合成算法输入没有伪装这些层。
原 OSV raw → 证据化 typed input、资产快照、条件 AST、PG 提交校验、OpenVEX、API / worker / 页面仍未接线，整 R11 / T26 / G-D 不放行。
计划 / 合同偏差没有扩大：沿原批准内部精确比较范围做严格上下文校验与审计修复；公开模型和原完整验收不变。
F2 / P2 / F3 仅补版本条件边界 / 审计正确性的本地证据，不生成正式评分、准确率或性能数字。

下一动作：主控将最终 code / material / manifest hash 交原新独立 reviewer 定向复核，通过后才合入内部代码切片。
不 push、不 accepted、不改 progress、不 spawn、不继续其他任务。旧材料与旧 manifest 保持原 SHA。
