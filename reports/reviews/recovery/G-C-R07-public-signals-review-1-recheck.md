# G-C · R07 公共四维候选包评审 1 定向复核

What this change does: 修复从已正规化来源标识确定 CVSS 比较目标，并在同一 CWE 目录版本和 XML 内容内合并选择子集。独立复跑确认原两项 Must 已关闭，原值、机构、字段证据及未知/失败边界仍保留。

**Verdict: Ship. 仅本公共四维纯候选切片。** 不签整 R07、原 T19/T23 或 G-C，不写 accepted、不 commit/push。原完整 pure CPU 失败仍未关闭，真实 CWE 和 PG/运行时/API/UI/live/manual 仍缺证据。

评审人：`/root/r07_public_signals_independent_review`，原独立 reviewer，未参与作者修复；首次评审与原红材料保留。独立 worktree `D:/wt/r07-public-signals-review-fix1`，分支 `codex/r07-public-signals-review-fix1`。完整材料 SHA `facf6cce653de318ac966e71ac62b479e562aa61`，业务 SHA `9df5a61d29ff489e13fb87876e35399ebb9cb00a`；前次材料/代码 `7f8cdc81108e39819d192c09bf1b4a61c640aec9` / `7142c38620150d5f2b7d81963389bdf8b725c316`。

首次创建、本次写作开始/结束、最后更新和证据截止均为实际上海 `2026-10-16T01:20:22+08:00`。复核正式日志第一项从 `2026-10-16T01:12:16+08:00` 开始；初始普通只读探索的精确秒未逐项记录，不回填 mtime。两个 Must 的新定向实证结束时间为 `2026-10-16T01:14:44+08:00`。

## 复核范围与版本身份

沿用本对话已读 Ponytail 5.2 review 规则、AGENTS、00/03/04/05/06/07、T19/T23、冻结候选合同及 R07 manifest 依据；本轮重读 AGENTS、执行索引/R07 manifest、当前 state/handoff 要求、T19/T23 和 seam，读修复 diff/新正反测试与作者报告，先独立刷新 src 图和 qualified trace、源码 rg 后运行测试。前次规范读取记录不重复伪报为本轮新检查。

从 7f 到 9df 的业务范围仅 `backend/src/ai_intel/enrichment/signals.py`（+48/-38）、新 unit `test_r07_public_signals_fix1.py`（99 行）、新 contract `test_r07_public_signals_fix1_cwe.py`（133 行）。作者没有改原 101 个测试、signal_sources、冻结两合同、依赖/锁、原阈值或金标。上述五个旧文件逐 Git 原字节相同；本 worktree 的八关联源码/测试在完整材料与业务 SHA 间逐字相同，所有正式命令前后实际工作字节哈希不变，业务 diff exit 0。

本 reviewer 只新增本报告及 `reports/runs/recovery_r07_public_signals_review_1_recheck_20261016/`。原独立 23 项探针和公开复放脚本从首次独立 worktree 按原 manifest 哈希逐字复制，没修改期望或原红日志。新目录 `.gitattributes` 仅在本证据目录禁止文本转换，以保全录制字节；不改共享忽略规则或业务配置。

## 原 Must 关闭结果

1. **跨 NVD/vendor 同 CVE 的 CVSS 冲突漏报：关闭。**
   - 原触发：同 CVE/3.1 的 NVD 9.8、vendor 8.1 被第一条 GHSA 引文拆成两 scope，返回 available。
   - 固定修复：`signals.py:548–552, 680–698` 从通过源核验的 NVD CVE / `vendor.cve_id` 生成 revision → target；只有厂商确实无 CVE 时使用正规化 GHSA。`_scope` 从这一内部映射取得比较目标，再加标准版本；不依据引文字符串、排列、publisher 形状或 context 唯一 CVE 猜别名。
   - 新独立证据：原触发已 conflict 并保留两个分数；原独立全 23 项通过。新 13 个 CVSS scope 回归覆盖输入顺序、同值不同机构、score/vector 分歧、不同 CVE 共用 GHSA、同 CVE 不同 GHSA、GHSA-only 身份、不将 GHSA-only 套到 context CVE、标识形状 publisher、引文倒序及未支持 CVE 拒绝。源码确认映射只在成功提候选后绑定，所有当前 CVSS 引文来自其源修订，caller 没有遗漏签名参数。

2. **无关 CWE selection 删除已验证候选：关闭。**
   - 原触发：source CWE-78 + 78 selection 为 available，加入合法 79 selection 后变 blocked/0。
   - 固定修复：`signals.py:438, 451–463, 464–491` 校验每个 selection，再按 `(taxonomy_version, source_xml_sha256)` 分组。完整组的选中 ID 并集覆盖全部源 ID 才产生候选，每个候选仍引用实际含其 ID/name 的文档；无关子集缺少该 ID 不构成否定。
   - 新独立证据：原触发保留 available/1。新 11 个 CWE 正反例通过，包含同目录互补子集、前后顺序、缺 ID/显式 missing、重叠证据、同 ID 同版本不同名字 conflict、不同完整版本并列、跨版本及同版本不同 XML 禁拼、坏 XML hash 失败。源码保留未完整验证组 blocked 与非法 selection failed；不能用不同 XML 的不完整子集凑验证。这里是显式合成目录，不把版本字符串或哈希形状当真实 MITRE 真实性。

本轮没有发现需要新增修复的问题；没有风格偏好类 findings 或经核实的精简行数收益。关闭判断基于本 reviewer 新跑日志与源码，而不是作者自检绿结论。

## 新正式验证记录

新独立 `.venv` 通过 `uv sync --offline --frozen` 安装 79 包，Python 3.12.13，无 semantic extra 或网络安装。测试/静态工作目录为 `D:/wt/r07-public-signals-review-fix1/backend`，图谱/材料/源码/Git 检查为独立 worktree 根。下列短名都对应本 run 的 `.command.json` / `.log`；其中保存完整 argv、cwd、上海起止、exit、两固定 SHA、源码前后哈希与绝对探针脚本输入哈希，pytest 另留 JUnit。没有执行整 pure 或新增产品外部请求。

| 检查 | 上海开始→结束（2026-10-16） | exit | 实际结果 |
|---|---|---:|---|
| 新 CBM index/schema/architecture/三个 qualified trace | 01:12:16→01:12:43 | 每项 0 | 1333 节点/6764 边；0 未索引/跳过/partial/unusable 文件 |
| author_material_verify（严格按错误转述指纹） | 01:13:14→01:13:14 | 1 | manifest 字节 SHA 不等于交接名称；原失败保留，见下方纠正 |
| author_material_verify_v2 | 01:14:16→01:14:23 | 0 | 固定 Git blob 的 100 清单项大小/SHA/Git object 均逐项匹配，另核 manifest 本体 |
| sync：`uv sync --offline --frozen` | 01:14:23→01:14:28 | 0 | 独立离线环境/79 包 |
| rg_fixed_callers | 01:14:40→01:14:40 | 0 | `_scope` 唯一直接 caller 为 `_attempt`；CWE helper 为 enrichment 入口 |
| original_triggers：原脚本 `-k` 两 Must | 01:14:40→01:14:44 | 0 | 2 passed/21 deselected/0 error/skip；pytest 1.64s |
| independent_all：原独立脚本全量 | 01:14:56→01:14:58 | 0 | 23 passed/0 fail/error/skip；pytest 0.54s |
| new_regression：13 unit + 11 CWE contract | 01:14:56→01:14:59 | 0 | 24 passed/0 fail/error/skip；pytest 0.24s |
| focused：原 unit/contract 两文件 | 01:14:56→01:14:59 | 0 | 101 passed/0 fail/error/skip（51/50）；pytest 0.28s |
| regression：必要旧 NVD/vendor/T19/T10/T12/T23 七文件 | 01:14:56→01:14:59 | 0 | 146 passed/0 fail/error/skip；pytest 0.32s |
| ruff / format | 01:14:56→01:14:57 | 每项 0 | 6 候选/回归文件通过；6 files already formatted |
| mypy | 01:14:57→01:15:02 | 0 | 2 产品模块 no issues |
| recorded_public_replay | 01:15:02→01:15:03 | 0 | 3 正常/无命中查询 + 2 内存坏响应变体通过；不是 pytest 或 live 数量 |
| history_audit | 01:16:32→01:16:33 | 0 | 29 个 checkout 差异均仅换行；红/最终 18 个 test 函数 AST 相同 |
| handoff_digest_corrected | 01:18:03→01:18:04 | 0 | 独立重算 filelist digest，与 manifest bytes digest 分开 |
| git_business_scope / git_business_unchanged | 01:18:04→01:18:04 | 每项 0 | 三业务文件范围固定；reviewer 未改源码/原测试 |

两 Must 子集是原 23 项的重复，不与全量重复相加；23/24/101/146 也不包装成正式准确率分母。23 项中的坏来源、quote mismatch、metadata-only/缺字段、无时间/不完整块、partial 与 XML/ZIP 安全检查仍通过。

CBM cache 新建在 `/tmp/dianzi-cbm-r07-public-signals-review-fix1-20261016`，只有 backend/src，不索引 reports/fixtures/秘密/holdout。使用完整限定名 `r07-public-signals-review-fix1-facf6cc.ai_intel.enrichment.signals.*`。图中 `_scope` 入向 `_attempt` 和其上层 enrichment；`_cwe_candidates` 入向仅 enrichment，源码确认直接调用关系。新公开 enrichment 入口入向仍为 0，未接 PG/worker/API；不能把纯候选 Ship 解释成产品在线。图边数随项目/语义关联变动，不作为代码身份依据，身份已逐 Git blob 核对。

## 材料完整性、交接纠正与原红历史

固定 `facf` 的作者 manifest 本体为 **144509 B / SHA256 `91125322b8fa70d7c5dd9c40af8f84ad1afcd56c6070316af8dddb32094885dd`**。顶层 **filelist_sha256** 为 **`a3ea1549f82c7dd714418046703b20424445ca5ac79265b287d85d4c081bee06`**，由清单的排序键/紧凑 JSON 独立重算得到。作者 100 项材料全部按固定 Git 原 bytes 校验 `bytes`、SHA256 与 `git_blob_exact_bytes`，加 manifest 共 101 个核验对象。29 个 checkout 字节差异全经规范 LF 比较确认仅换行，不把 checkout 转换冒称作者材料漂移。

root 已重新读取作者 worktree 原体及 `git show`，确认前述本体 SHA 一致。原交接把 **filelist SHA** 转述为 **manifest 指纹**，导致本 reviewer 的首次严格断言 exit 1；root 已明确纠正名称。`author_material_verify.log/command.json` 原失败未覆盖，`handoff_digest_correction.json` 记录两个指纹及独立重算；不追认 a3ea 是文件字节哈希，不更改作者原材料。

原首次独立 2 failed/21 passed 日志与 23 项原探针保留，脚本哈希原样。作者修复前新增 24 项原红 **11 failed/13 passed** 的 log/receipt/`new_red_test_snapshot.py` 保留；分拆后的两个测试文件 18 个 test 函数 AST（含装饰器/断言）与原红快照逐项相同，未以删难例或改期待转绿。此核验只证明该函数快照等同性，不把旧运行冒称固定新业务测试。

作者早期 `new_regression` 的 JUnit 路径后来被最终 `new_regression_frozen` 复用，早期 log/receipt 保留，但没有单独早期 green XML；不能再把该 XML 与早期 argv/SHA 配对当独立历史证明。作者最终证据只按 `*_frozen.command.json` 对应固定 9df/输入哈希及最终 XML 阅读；本结论使用新独立 JUnit，不依赖这一复用文件证明当前行为。新增仪器失败还包括不存在的探索 `checks.py` 与 Windows 字面 `*.py` rg 路径，已分别换实际 runner 与 `rg -g '*.py'`，不当产品失败。

## 公开录制复放与保留限制

只读旧公开 EPSS body 203 B / `c842f9164ed0c3eb350310d4ac181c2a65d61f05629f221b907ab4753d3a59e3` 和 KEV body 1787354 B / `47b463a136b8e0956756cfbcdbc2e4b4ccb60c96b4ca7a1ca9f507817cc83045`（1745 项）及公开接收记录。EPSS CVE-2024-37032 available/4 引文，KEV 同 CVE not_found，CVE-2026-105134 available/6 引文；原 hash、选取范围/行索引、值、quote 坐标/hash 通过。EPSS 跨 CVE 与 KEV 无关损坏行仍拒绝。原体没有入 Git，新网络/模型/测绘/PG 调用均 0，未读秘密、资产或盲测材料。

原全 pure **1944 passed/1 failed/10 real_pg deselected**、exit 1、coverage75.75%（原门60），native-cpu `4062500+6250000=1.03125s` 未过原 `<1s`，仍未关闭。本轮不整 pure、不跑 CPU 诊断、不降阈值/分母或 skip，不以本片绿盖旧红。作者原外部文档 10>8 预算、成功正文5/失败5 的超2偏差仍保留，本轮新增0；外部费用/wall/bytes 无实测者仍 unknown。

真实 CWE ZIP/XML 全文仍 blocked_live；合成目录选择不证明真实版本/真实性。CVSS 完整数学重算与可选 metric 完整语义仍未实现，只保留 source-reported 分数/向量、基础 syntax/取值/版本；评分时间未知不替换成 published/observed。新输出仍仅候选，PG 最终发布必须重新验证 registered source、当前 revision、租户/权限、永久块、原响应 hash/reselection 与支持关系。本片没有产品发布集成、并发/负载、运行时/API/UI、人工验收或正式评分指标。

## 状态与交回

| 层级 | 本片复核状态 | 实际范围 |
|---|---|---|
| unit | passed（限定） | 原51、新13、原独立23及相关旧回归；两 Must 关闭 |
| contract | passed（限定） | 原50、新11、旧来源回归及公开 recorded_response_contract |
| integration | not_run | 无 PG/worker/API 发布 |
| security | not_run（产品） | 纯边界已随23/24通过，未测认证/租户/race |
| frontend/e2e | not_run | 本轮无产品界面接线 |
| live | not_run；CWE blocked_live | 旧公开录制复放不计新 live |
| manual | not_run | 未作人工标注或体验签字 |
| inherited full pure | failed，未关闭 | 原 CPU 红保留，交主控独立诊断 |

T19-C01 的原值/证据与 C05 并列/冲突、T23-C03 跨来源分歧和 C05 EPSS/KEV 来源日期在本片有新证据。T19-C03/C04/C06 的完整 PG partial/幂等/权限、T23 PoC/修复/资产以及其他九维范围仍未由此片验收；F2/P2 只登记这一候选能力，不推导95%指标或整卡完成。

下一步建议：主控可将固定 9df/facf 公共四维候选修复纳入后续集成；继续分列 PG 发布/实际来源/live 与原 CPU 根因诊断。共享进度和切片状态由主控依据报告登记，本 reviewer 到定向复核停止。

Verdict: Ship. **只限固定 9df / facf 的公共四维候选切片。**

Not checked: 整 R07/九维、PG 发布/权限/并发、worker/API/UI/e2e、真实 CWE、完整 CVSS 数学/可选语义、产品 live/负载/人工/正式评分；原全 pure CPU 红未关闭。
