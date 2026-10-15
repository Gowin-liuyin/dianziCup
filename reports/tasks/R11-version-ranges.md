# R11 / T26 · 精确版本规则内部准备切片

状态：awaiting_review。实现：本次授权纯规则切片 complete；原 T26 / 整 R11 保持 partial，作者不签 accepted。
记录时间：2026-10-16T01:43:10+08:00。所有命令 receipt 使用实际 +08:00 开始、结束时间。

基线：`349c5e3ec27196257b98cdfcb63c75fb50157978`。
分支：`codex/r11-version-ranges`。
独立 worktree：`C:/Users/yinha/.codex/worktrees/r11-version-ranges/dianzi`。
主控依赖提交：`f62466ff3282c872336288fc42e600e4e2dcc84a`；本分支 cherry 对应 `d7b3ea4d7c377cce8454b932d308e06feac85afd`。
冻结代码：`3e896da58bdcabdd738a3430f7b77358e7f8b03a`，代码提交仅下列四个业务 / 测试文件。
材料提交与 manifest 本体 SHA256 由最终交接提供，manifest 不自引用自身字节。

## 1. 授权、合同与实际范围

已读 AGENTS、00_execution_map、恢复 R11、原 T26 卡、03 / 04 合同、progress 状态与最近交接。
开工时主工作区有大量未提交修改，本 worktree 从指定 SHA 隔离，未修改主工作区。
R02 已 accepted，R07 partial，R10 尚未实施；G-D 正式门未通过。主控明确授权不依赖图、PG、资产或 live 的内部版本纯规则准备，不能据此签整 R11。

Ponytail 使用新版 5.2.0 full；先核实真实复用与全部调用方，未创建未来生态的空接口。
实际公共类型为 `VersionAssertionValue`、`VersionInterval`，没有 `VersionIntervalValue`。
既有 intervals 上限是 50，explicit_versions 上限是 100；没有机械改成 64，也未修改公共 domain / JSON Schema。
主控已批准内部 keyword-only `excluded_versions: tuple[str, ...]`（最多 50）、`range_complete: bool=False`，不扩公共 schema。

主控唯一维护依赖。packaging 26.3 从既有传递依赖改为直接依赖，semver 锁 3.1.0；其余锁定包版本未改。
依据见 [CR-R11](../../docs/decisions/CR-R11_version_comparison_dependencies.md)，该变更仍 awaiting_review。
所用官方语义：[packaging Version](https://packaging.pypa.io/en/stable/version.html)、
[python-semver 精确比较](https://python-semver.readthedocs.io/en/latest/usage/compare-versions.html)，主控 2026-10-16 已查证。

## 2. 改动文件与复用

新增生产代码：`backend/src/ai_intel/assessment/version_ranges.py`。
新增直接 unit：`backend/tests/unit/test_t26_version_engine.py`。
新增直接 contract：`backend/tests/contract/test_r11_version_ranges_contract.py`。
新增直接 security：`backend/tests/security/test_r11_version_ranges_security.py`。
材料：本报告、`reports/runs/recovery_r11_version_ranges_20261016/` 的命令 receipt / 原始 stdout、stderr / JUnit / 封存脚本与 manifest。
`.gitattributes` 只追加本新 run 的 `*.log`、`*.xml`、`*.json` 三条 `-text -diff`，经主控明确批准用于保留原字节。

复用 frozen Pydantic 值对象；未改 `domain/records/values/enrichment/signals/model_fields`。
复用成熟 `packaging.version.Version` 和 `semver.Version.parse`，区间组装为直接纯函数，没有自制版本排序。
原 OSV `normalize_osv_record` 已保留每条 `range_branches`，本轮不重写来源解析。
未修改 public schema、迁移、锁文件、全局依赖、settings、API、worker、progress、盲测、金标或计分规则。

## 3. 输入输出与行为

`compare_versions(left_version, right_version, *, scheme, ecosystem)` 返回 frozen `VersionComparison`：
`comparable` 时 ordering 为 -1 / 0 / 1；缺失或非法输入为 unknown，unsupported 时 ordering 为 None。

`contains_version(version, interval, *, scheme, ecosystem, branch=None)` 判断一个规范区间，返回 `VersionMatch`。
这是单区间成员关系，不表示已遍历完整漏洞知识，也不能单独作为资产安全结论。

`evaluate_version_assertion(assertion, *, package_key, ecosystem, version, version_scheme,
branch=None, downstream_backport=False, excluded_versions=(), range_complete=False)`
返回 frozen `VersionMatch(status, reason, interval_results, unresolved_reasons)`。
status 明确为 affected / not_affected / unknown / unsupported；每段区间保留源顺序和未定原因。

仅支持精确 PEP 440 / 精确 SemVer，以及明确的 OSV ECOSYSTEM 适配：PyPI → pep440，npm → semver。
生态字符串与 package_key 必须严格匹配。purl 按身份键完整比较，同名但不同 purl、限定字段或生态不匹配时保持未知；没有猜测别名。
组件与断言的 scheme 需解析到同一受支持生态。Git 无祖先关系工具、未知 scheme、其他生态返回 unsupported。
不解释任意 npm 语法，不把 `<2 || >=3` 的 raw_expression 或 mitigation 文本伪装成已解析范围。

introduced 左闭；OSV introduced=`0` 表示所有早期版本；省略下界为开放下界。
fixed 右开，last_affected 右闭；闭区间相同端点支持唯一版本，空右开或倒置区间为未知。
先检查两端边界，不能因低于下界而隐藏非法上界。多区间和不连续范围不扁平合并。
维护分支需明确匹配；源区间有分支而资产没有分支则保持 unknown。

explicit_versions 独立匹配精确规范版本；PEP 440 与 SemVer 保持各自规范语义：
PEP 440 的 local / epoch / post / dev 与 SemVer 的 prerelease / build precedence 不混用。
SemVer 严格拒绝 `1`、`1.2`、前导零、`v1.2.3` 与 PEP 440 的 `1.2.3rc1`，不自动补零。
exact exclusions 必须由调用方提供已有可信排除证据；解析不了任一 exclusion 即 unknown，不能先命中一项便隐藏后续非法项。
明确命中的有证据 exclusion 可以支持排除该精确版本，不能推断整个知识库完整。

没有命中只在 `range_complete=True` 且所有相关区间 / 显式版本可解释时返回 not_affected。
默认完整性未知；调用方不能因 raw_expression 非空就置 true。
已知 affected 命中可以保留，同时在 interval_results / unresolved_reasons 中保留其他分支或显式版本的缺口。
下游回补一旦标记就返回 `downstream_backport_unverified`；本层没有接受权威修复证据的接口，不从上游版本或 vendor_fix / mitigation 文本猜已修复。
source comparison_support 为 unknown / unsupported 时不覆盖来源状态。

精确版本限制 128 字符，无首尾空白或控制字符；区间 50、显式版本 100、排除版本 50。
纯函数不读环境、不执行字符串、不发 HTTP、不访问 PG / 资产、不调用模型；并发调用没有共享可变状态。

## 4. 原 T26 六案例证据

| ID | 测试入口 / 断言 |
|---|---|
| T26-C01 | `test_t26_c01_inside_introduced_fixed_range`：1.4.1 ∈ [1.0.0, 1.4.2) → affected |
| T26-C02 | `test_t26_c02_fixed_boundary_is_not_included`：1.4.2 为 fixed，可信完整范围 → not_affected |
| T26-C03 | `test_t26_c03_numeric_release_order`：PEP 440 / SemVer 均 1.10.0 > 1.9.0 |
| T26-C04 | `test_t26_c04_prerelease_independent_maintenance_branches`：预发布、两个维护分支、边界与未知分支；另有不连续范围和规范顺序传递性断言 |
| T26-C05 | `test_t26_c05_missing_invalid_and_git_versions`：None / 非法 → unknown，git / 未知 scheme → unsupported，无确定否定 |
| T26-C06 | `test_t26_c06_identity_and_backport_are_not_guessed`：同名异生态 / purl / 未核验回补不推断受影响或修复 |

补充边界包括源支持未知、纯 mitigation、部分区间、无完整性、晚到非法 exclusion、缺身份、128 字符与 50 / 100 项上限、Pydantic 绕过上限、数据不变、frozen 输出、32 次四线程比较、恶意 Python / shell / SQL / URL 文本和有效版本的无 IO 断言。
全部仅为显式合成算法输入，没有充当真实资产真值、live 或人工金标。

## 5. 真实执行与结果

运行环境：Python 3.12.13、uv 0.10.9、packaging 26.3、semver 3.1.0、pytest 8.4.2、ruff 0.16.9、mypy 1.20.2。
导入路径已核对指向本 worktree 新模块，不使用主工作区业务源码。
目录简记：下列 backend 命令 cwd 为本 worktree 的 `backend`，CBM / rg / diff 命令 cwd 为 worktree 根。
每条原 argv、cwd、实际时间、退出码与 code SHA 见 run 同名 `.receipt.json`；stdout / stderr 均原 bytes 留存。

| 记录 | 实际命令核心 | exit / 结果 |
|---|---|---|
| test_first_import_red | `python -m pytest tests/unit/test_t26_version_engine.py --no-cov -q` | 2；新模块未实施的 collection 缺模块红，1 error / 0 cases，不冒充业务失败 |
| dependency_sync | `uv sync --locked` | 2；Windows Celery wheel 访问拒绝，环境安装失败 |
| dependency_sync_copy | `uv sync --locked --link-mode copy` | 0；原锁安装；没有改 ACL、锁或关闭检查 |
| targeted_first | 新 unit `pytest ... --no-cov` | 0；72 passed |
| ruff_first / mypy_first | 新模块 / unit 定向检查 | 1 / 1；9 处长行与 1 处 Optional 窄化，原日志保留；format 与明确 if 修复 |
| targeted_expanded | 新 unit / contract / security | 0；83 passed |
| targeted_prefreeze | 补齐边界与审计缺口后的定向 pytest | 0；94 passed |
| fixed_targeted | 冻结 3e896da 的三新测试文件 `--no-cov` | 0；83 unit + 3 contract + 8 security = 94 passed，0 failed/error/skip |
| fixed_related_contracts | 原 T11 / R02 合同 + 新 contract / security | 0；33 passed，0 failed/error/skip |
| fixed_relevant_regression | 新测试 + 原 T04 / R07 / OSV 范围 / T11 / R02 | 0；175 passed，0 failed/error/skip；包含 94 新案例和 81 既有案例，不能与其他重复执行相加 |
| fixed_ruff | `python -m ruff check src tests` | 0；全后端检查通过 |
| fixed_format | `python -m ruff format --check src tests` | 0；245 files |
| fixed_mypy | `python -m mypy src/ai_intel` | 0；100 source files |
| fixed_diff_check | `git diff --check` | 0 |
| fixed_unit_regression | `python -m pytest tests/unit -q --junitxml ...` | 1；1627 passed / 4 failed / 0 error / 0 skip / 1 warning；71.03% 达原 60% coverage 门，但整体失败 |
| fixed_r20_failure_replay | 原 R20 整文件 `pytest ... --no-cov -q` | 0；16 passed；没有改变实现或阈值，不替代上行失败，也未证明完整因果 |

全量单元红例均在既有 `test_r20_native_cpu_guard.py`：三个
`test_guard_hard_exit_after_readiness_terminates_worker_tree` 的原累计 CPU `<1s` 断言，
及 PDF `test_real_product_worker_starts_guard_and_job_cleans_it_on_exit` 原 8 秒 ready 期限。
前者实际分别为 1.140625s、1.609375s、2.484375s；后者真实 deadline 失败。
主控已有独立 R20 累计 CPU 缺口诊断，本切片没有扩大至 guard / PDF 修补，也没有降低门槛、跳过失败或改分母。
`r20_baseline_blob_comparison.json` 逐字节确认三个相关生产 / 测试文件与 349c5e3 相同。
这一事实和源调用搜索说明此处没有改动 R20 路径，不能将全量红例自动归为环境免责；作者未完成完全因果证明，交独立 reviewer 判断纯版本切片能否限定审查。

首次命令 runner 使用相对可执行文件时发生 WinError 2，子 pytest / Ruff / mypy 尚未启动；随后解析为绝对路径再真实执行。
另一次 uv --version 调用误填不存在的 cwd `baseline`，子命令未启动；真正 uv 版本核对为 fixed_uv_version、exit 0。
这两项工具启动错误仅存在原工具交互输出，不伪造 receipt / 原进程日志或通过数量。

首次材料字节校验把普通文本 `.gitattributes` 也当成原始 run 输出，因其正常 Git CRLF / LF 归一而报 mismatch；封存范围纠正为自有 run 原始 bytes 与报告，配置只保留三条限定规则的正常 Git diff。日志 / XML / JSON 的逐字节校验要求没有放宽，原输出未改写。材料 helper 首次 format-check 的两处格式提示亦修正后复验。

定向 `--no-cov` 表示只做本切片行为检查，不声称整个后端覆盖率；全量单元原 coverage 配置和 60% 门均完整保留。

## 6. CBM、真实调用方与接线限制

真实 CBM v0.11.0 help 后建立独立 `r11-version-ranges-src` 索引，仅 `backend/src`；未索引秘密、holdout 或用户资料。
工具缓存未入库，persistence=false。开工索引 1292 nodes / 6424 edges；冻结 SHA 后索引 1310 nodes / 6500 edges，96 source files。
真实 get_graph_schema / VersionInterval validator trace / OSV normalize trace / compare / contains / evaluate traces 均 exit 0，日志在 run。
工具自动排除 assets、__pycache__ 等，本片未声称图覆盖被排除资产；源码 rg 另行核查整个 backend/src 和全部 tests / scripts / contracts。

开工 rg 确认 VersionAssertionValue 的使用为 domain 联合值、enrichment 合同映射、schema 与 R07 合同案例；旧 VersionRangeValue 在知识持久化身份冲突 / 合同中使用，不是成熟比较器。
OSV 的生产路径为 source_jobs → catalog_pages → normalize_osv_record，范围事实仍按原有 source parser 保存。
冻结 rg 确认 compare / contains / evaluate 的调用只在本模块或三新测试文件中；CBM 无生产 inbound，与源码交叉相符。
真实路径为纯函数 → scheme 明确映射 → 成熟精确解析 → 区间 / 显式 / 排除汇总 → frozen result；没有数据库或外部 IO。

本切片尚未把 OSV raw range_branches 转成受证据约束的 VersionAssertionValue，也未接入资产快照、条件 AST、PG 提交校验、OpenVEX、API / worker / 页面。
因此原 T26 第 2 步的产品输入映射、R11 其余范围及至少 3 个真实产品案例仍待后续授权与前置门；不会因纯算法测试通过而登记整卡 complete。

## 7. 验证层、偏差与评分证据

本次纯版本切片：unit=passed（83 新案例及相关回归），contract=passed，security=passed。
整个仓库 unit 回归=failed，保留原 4 个 R20 红例。integration / frontend / e2e / live / manual 均 not_run；performance 亦 not_run。
没有 HTTP、模型、PG、授权资产、FOFA 或 live 执行；没有以 fixture 替代这些层。
G-D 与整 R11 不放行。progress 由主控统一更新，本作者未修改状态文件。

计划偏差是主控明确授权的内部纯规则准备：新文件 `version_ranges.py` 替代原 T26 目标 `versions.py`，实际消费 frozen R07 值类型，未改其公共合同。
原六验收、原前置、阈值、金标与盲测分母完整保留；不删除完整 OSV 映射或真实资产验收要求。
F2 / P2 / F3 仅获得版本边界与保守未知语义的本地代码证据，不报告准确率、正式性能、实测影响面或评分档次。

下一任务建议：主控交新独立 reviewer 固定代码 / 材料审查并复跑；在 G-D / R07 / R10 相应前置满足后，再由接口所有者实现可信输入映射与资产 / 条件接线。
本任务到此停止，不 push、不 accepted，不继续其他任务或擅自修复 R20。
