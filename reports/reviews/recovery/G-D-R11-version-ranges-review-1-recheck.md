What this change does: 修复给两个内部版本入口增加严格的分支身份校验，避免空或非法分支产生确定排除。可信精确排除的返回后移，使区间与显式版本的未定原因留在结果审计中。

Looks good. Ship. 本结论仅覆盖 R11/T26 内部纯精确版本比较准备切片；首轮 Must 1 与 Should 2 关闭，不签整 R11/T26/G-D，不改变 progress 或 accepted 状态。

任务：R11/T26 version-ranges fix1 独立定向复核。Reviewer：`/root/r11_version_ranges_independent_review`；开始 clock 为 2026-10-16T02:17:45+08:00，完成记录 clock 为 02:23:36+08:00，封存实际时间另见 manifest。
继续使用 [Ponytail review 5.2.0](C:/Users/yinha/.codex/plugins/cache/ponytail/ponytail/5.2.0/skills/ponytail-review/SKILL.md)，本轮只核首轮两个问题与直接回归，不扩大风格或功能范围。已核当前 AGENTS、00map、恢复 R11、03/04、T26 原六验收、progress 与作者修复报告；正式依赖 CR-R11 继续沿首轮固定 f624 的依据。

固定修复 source：`65838b42c0dcff863036968e39a1404aa323b3c9`；最终 code：`71e724131daf4d03372392d58cd17c764c3e2e40`；最终 material：`8f5fe818774349b41b0b5aceb45d69ba81410678`。658→71e 只删除新测试 import block 的一个空行，生产代码 blob 相同；71e→8f 生产/测试 blob 亦相同。
原 code `3e896da58bdcabdd738a3430f7b77358e7f8b03a`、原 material `5a35cc5e6dec307e7d5fbdf06c9d49881679cb61` 与首轮报告保持原证据，未改写。

独立新 worktree：`C:/Users/yinha/.codex/worktrees/r11-review-f1/dianzi`；分支 `codex/r11-version-ranges-review1-fix1`；HEAD 固定 8f5f。作者 `C:/Users/yinha/.codex/worktrees/r11-version-ranges/dianzi` 开始时 clean，本轮未写入该目录或主工作区。

**首轮问题关闭证据**

| 原问题 | 固定代码位置 / 实际结果 | 复核结论 |
|---|---|---|
| Must 1：空/非法分支可变成确定排除 | `version_ranges.py:52–59` 的共享验证允许 None 表示缺失；非 None 严格 str、1–200 字符、无首尾空白且可打印。`:126–129` 同时验证资产和来源分支；`:242–245` 阻止独立显式命中或可信排除绕过非法资产上下文。 | 原 4 红变绿；新边界覆盖空串、首尾空白、C0/DEL/C1/零宽字符、201 字符、int/bool、200 字符合法值、Unicode、内部空格、合法精确匹配/不同分支、来源 model_copy 绕过。未 trim 或转换身份；合法异分支仍 `branch_mismatch / not_affected`，None 对带分支区间仍 missing_branch。 |
| Should 2：排除早退漏显式版本审计 | `version_ranges.py:237–249` 先解析显式版本、汇总区间未定原因，再返回可信排除。 | 原审计红变绿，排除仍为 `not_affected / explicitly_excluded`，同时保留 `missing_branch` 和 `invalid_explicit_version`；原“晚到非法 exclusion 必须 unknown”回归保持。 |

生产修复 23 行新增 / 2 行删除，新增直接 `backend/tests/unit/test_r11_version_branch_context.py` 137 行。没有新生态、接口、框架、IO、模型或外部调用。两个入口共享同一分支判断，汇总处只防护显式/排除绕过；本定向复核没有新增 Must/Should/Nice findings，不提出风格或行数修补。

**真实运行与环境**

本轮只新增该报告与 `reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/`。未修改业务、作者新/旧测试、合同/schema、依赖/锁、旧 CPU 路径、progress、分母或阈值；未 commit、push、spawn 或设置 accepted。
每个同名 receipt 均记录完整实际 argv、cwd、+08 开始/结束、exit、三个固定 SHA 与 PYTHONPATH；stdout/stderr/JUnit 为原字节。

首次新长名 worktree 操作 `9f9d7c6e-3b8a-44f7-8063-82bf941d146a` 因历史 PNG 路径超过 Windows 文件名长度而由工具返回 error；随后短名操作 `3583ea63-279e-407f-83dc-5eac285cdeed` 成功。未修改共享 Git 配置或清理历史文件；工具错误保留在会话输出，不冒充业务测试失败。

独立新环境 `uv sync --locked --offline --link-mode copy` exit 2，原因是 jsonschema 4.26.0 wheel 安装访问拒绝；新 .venv 的两次 pytest 启动分别 exit 1、`No module named pytest`，0 cases、未进入 collection，原 `offline_sync.*`、`original_33.*`、`new_67.*` 保留。未把这三项当业务红或通过，也未反复安装/改 ACL/联网。

后续复用首轮独立 reviewer 的 `C:/Users/yinha/.codex/worktrees/r11-version-ranges-review1/dianzi/backend/.venv/Scripts/python.exe`，不是作者环境。锁文件与原环境的固定 lock 完全相同；子进程 PYTHONPATH 指向这次新 worktree `backend/src`，runtime 原输出确认比较模块实际路径是 `C:/Users/yinha/.codex/worktrees/r11-review-f1/dianzi/backend/src/ai_intel/assessment/version_ranges.py`。Python 3.12.13、packaging 26.3、semver 3.1.0、pytest 8.4.2、ruff 0.16.9、mypy 1.20.2 均实测。此次不声称全新依赖环境安装通过，定向行为复核使用上述同锁环境完成，全程无网络访问。

下表 cwd `backend` = 新工作区 backend，`root` = 新工作区根。pytest 都保留 `--no-cov -q --junitxml ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/<记录>.xml`；完整 argv 在对应 receipt，没有省略实际输入文件。

| 记录 / cwd | 实际子命令 / 输入 | exit / 实际数量 |
|---|---|---|
| recheck_original_33 / backend | `python -m pytest ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/test_independent_version_cases.py --no-cov -q --junitxml ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/recheck_original_33.xml` | 0；33 passed / 0 failed/error/skip |
| recheck_new_67 / backend | `python -m pytest tests/unit/test_r11_version_branch_context.py --no-cov -q --junitxml ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/recheck_new_67.xml` | 0；67 passed / 0 failed/error/skip |
| recheck_original_94 / backend | `python -m pytest tests/unit/test_t26_version_engine.py tests/contract/test_r11_version_ranges_contract.py tests/security/test_r11_version_ranges_security.py --no-cov -q --junitxml ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/recheck_original_94.xml` | 0；94 passed / 0 failed/error/skip；83 unit + 3 contract + 8 security |
| recheck_original_175 / backend | `python -m pytest tests/unit/test_t26_version_engine.py tests/unit/test_t04_domain_contracts.py tests/unit/test_r07_enrichment_contracts.py tests/unit/test_r06_osv_range_boundaries.py tests/contract/test_t11_osv_connector.py tests/contract/test_r02_value_contract.py tests/contract/test_r11_version_ranges_contract.py tests/security/test_r11_version_ranges_security.py --no-cov -q --junitxml ../reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/recheck_original_175.xml` | 0；175 passed / 0 failed/error/skip；内含同一 94 新例，不与 94 重复相加 |
| ruff / backend | `python -m ruff check src tests` | 0；全源检查通过 |
| format / backend | `python -m ruff format --check src tests` | 0；246 files already formatted |
| mypy / backend | `python -m mypy src/ai_intel` | 0；100 source files |
| diff_check / root | `git diff --check` | 0；tracked 业务 diff 为空 |
| material_verification / root | `python reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/verify_fixed_material.py` | 0；两作者 manifest、复制用例、保护 blob 和红/绿 JUnit 核对通过 |
| source_callers / root | `rg -n 'compare_versions\|contains_version\|evaluate_version_assertion\|_contains_parsed_version\|_valid_branch_label\|VersionAssertionValue\|VersionInterval' backend/src backend/tests scripts contracts` | 0；完整源码和测试调用交叉核对 |

原 33 复验实际 2026-10-16T02:22:00.003487+08:00 至 02:22:01.598005+08:00；新 67 实际 02:21:59.990159 至 02:22:02.269973；94/175 与质量命令的各自真实时间见 receipt。所有数量由本轮原 JUnit 核查；不是作者报告转述，也不以重复执行累计新用例。

**证据保护与固定字节**

原 reviewer 33 用例首次文件、作者 fixed material 的复制件、本轮再复制件三方 6098 bytes 完全相同，SHA256 均 `b76bd21296694bf47cebf01d2878f22f17830bb86d8fbdbedfa166a6630af5e6`；输入、期望、参数、case ID、分母均未改变。作者修前 33 的 28 pass / 5 fail、新 67 的 6 pass / 61 fail 和 I001 红记录均继续封存；本轮 33/67 绿使用新文件名，不覆盖原红。

作者首次 manifest 本体 `85fb8c8074bff0ebd5594339b4e465beab58656f446591a0c307b657cc480861`，113 artifacts + 本体 = 114；fix1 manifest 本体 `a90e7ed882d62c1312f000f7a5178a2d324ab07c92d1383e0dbb1a6df6cba861`，119 artifacts + 本体 = 120。逐固定 8f Git blob 对两 manifest 的 bytes / SHA256 均 0 mismatch；新 checkout 所有 raw log/xml/json 及精确复制的原用例也 0 mismatch。两份材料各 4 个普通 helper/report 仅发生 CRLF/LF 变化，raw hash 与 EOL 等价列分开记录；没有归一原日志来冒充字节相同。详情 `fixed_material_verification.json`。

保护核对包括原 94 三测试、public enrichment 值、pyproject/uv.lock、process_limits、PDF worker、原 CPU guard 测试，全部与原 5a 固定 Git blob 相同。全部 backend/src、backend/tests、contracts、progress、docs/plan、依赖/锁的 5a→8f diff 只有被授权的版本模块和新增分支测试两个路径。658→71e 只有新测试 `0 add / 1 delete` 空行，生产源码不变，最终材料源码等同 71e。

原 fullunit 1631 cases = 1627 pass / 4 R20 fail / 0 error / 0 skip、coverage 71.03%、原 60% 门完整保留。相同 guard/PDF/test blob 不等于因果证明，首轮 `--no-cov` 16 pass 也不覆盖全量红。本次没有再跑 fullunit 或 R20，不签关闭这些失败；严格总 CPU 界和主控后续局部修复不属于本 fixed8f 定向复核。

**当前调用链与未检查范围**

在新 worktree 的当前 src 上新建 CBM 0.11.0 project `r11-review1-fix1-src`，`--mode fast --persistence false`，1312 nodes / 6507 edges，无 partial/unusable。新 schema 和 `_contains_parsed_version`、`_valid_branch_label`、`evaluate_version_assertion` 的真实 both/depth3 traces 均 exit 0，原输出保存。共享 interval 的 inbound 是 contains 与 evaluate；branch validator inbound 来自共享判断和 assertion 汇总；evaluate 没有生产 inbound。源码 rg 与图相符，没有新增 API/worker/assets 接线。

主 src 图仍排除 assets，本次未用其“零调用”替代资产结论；首轮已用独立 assets / assessment 索引和源码核对，当前 assets 无 diff，本次只定向核修复。没有新增真实资产读取或索引 holdout/秘密。

限定 unit/contract/security 与相关回归复验 passed，可合入内部纯版本准备切片。整 R11/T26 仍 partial，R07/R10/G-D 正式依赖门不由此放行；OSV raw→证据约束 typed assertion、条件 AST、资产快照、PG 提交校验、OpenVEX、API/worker/frontend 和真实产品真值案例仍未获本片实现证据。评分 F2/P2/F3 仅登记内部精确比较/保守未知/审计的本地证据，不报告正式准确率、性能或评分档次。

Verdict: Ship. 仅该 fixed71e/8f 内部精确版本切片及本次最小修复；可以安全独立合入/继续准备，后续接线需按原前置与门控制。主控依据此报告更新索引，本 reviewer 没有设置 accepted 或推进下一任务。

Not checked: 全量 unit 本轮独立复跑、全新依赖环境安装成功、PG/worker/API 研判集成、真实资产、模型、网络/live、frontend/e2e、性能、人工、整 R11/T26/G-D 终验。原 R20 fullunit failed 持续可见，未读取密钥/DSN/holdout/资产详情，未网络扫描。

本轮自有 manifest 单独封存该报告与新 run，manifest 不自引用；本体 hash 在最终交接提供。
