# R07 · 公共四维候选包两个 Must 根因修复 1

首次创建：2026-10-16T00:53:46+08:00；本次写作开始：2026-10-16T00:57:42+08:00；本次写作结束：2026-10-16T00:57:42+08:00；最后更新：2026-10-16T00:57:42+08:00；证据截止：2026-10-16T00:57:42+08:00。均为实际上海时刻，不从文件 mtime 反推工时。

任务：R07:T19/T23 公共四维切片；任务状态 **awaiting_review**；本次修复实现 complete。实现 Agent `/root/r07_public_signals_two_root_causes_fix`，与原独立 reviewer `/root/r07_public_signals_independent_review` 不同。下述原独立探针的重跑是修复自检，不能替代 root 派原 reviewer 的定向复核；不自行 accepted，不 push，不进入下一卡。

工作树 `D:/wt/r07-public-signals-fix1`；分支 `codex/r07-public-signals-fix1`。完整起点 `7f8cdc81108e39819d192c09bf1b4a61c640aec9`，原作者代码 `7142c38620150d5f2b7d81963389bdf8b725c316`；本次固定业务 SHA `9df5a61d29ff489e13fb87876e35399ebb9cb00a`。包含本报告、run/manifest 的材料封存提交 SHA 在最终交接给 root；其业务树必须与该固定 SHA 相同。初始本工作树干净；主仓库既有未提交修改未碰。

## 允许范围、输入输出与改动文件

已读 AGENTS、00 执行索引、R07 卡、T19/T23、03/04/07 合同、CR-R07/候选 seam、冻结 enrichment/contracts 与 domain/enrichment_values、当前 state/handoff、作者报告及原独立报告；先逐行读 signals.py、signal_sources.py 与 NVD/vendor 正规化，再新建 CBM 完整 source-only 索引/trace，并用 rg 核所有相关调用。适用本机 Ponytail 插件 5.2 full，具体 SKILL 路径/hash 见 candidate_identity.json。

输入仍为服务端支持的 CVE、固定可见修订、正规化来源身份和精确 JSON 叶块；输出仍为 cvss/epss/kev/cwe 四维 DimensionAttempt，只提候选。未改变九维类型、PG 真值、来源/修订/块身份、值/状态枚举或候选发布权限。

仅业务三个文件：

- `backend/src/ai_intel/enrichment/signals.py`
- `backend/tests/unit/test_r07_public_signals_fix1.py`（13 个 CVSS scope 回归）
- `backend/tests/contract/test_r07_public_signals_fix1_cwe.py`（11 个合成 CWE selection 合同回归）

另只新增本报告和 `reports/runs/recovery_r07_public_signals_fix1_20261016/` 的证据/复放/封存脚本。没有改 signal_sources.py、原 101 个测试、core/PG/公共 schema/worker/API、依赖/锁、共享 progress、认证、阈值、金标或分母。业务 diff 是 280 insertions / 38 deletions（含两新测试文件），不是质量或性能指标。普通本地提交仅用于冻结可复核 SHA，没有外部 push。

## Must 1：CVSS 比较范围从正规化源标识取得

旧 `_scope` 取第一条以 CVE/GHSA 开头的引文，厂商 `/ghsa_id` 在 `/cve_id` 前，导致同 CVE/3.1 的 NVD 9.8 与 vendor 8.1 被分到两个 scope，错误 available；标识形状的 publisher 字符串也可能误充目标。

现在在成功源核验后维护本次计算内部的 revision → CVSS target：NVD 取已核规范 CVE；vendor 取其正规化 cve_id，仅确实无 CVE 时取正规化 ghsa_id。`_scope` 只用候选源 revision 查这一映射，再加 standard_version；不从引文内容/顺序猜身份，不把 context 的唯一 CVE 套到 GHSA-only 公告，不推导新事件别名或跨 CVE 归并。此映射只属于纯计算，不是另一套业务真值。

同 target/标准的 score 或 vector 分歧 conflict，值和证据均保留；同值不同机构、不同 CVE 或标准并列 available。新用例覆盖来源输入顺序、score/vector、同 GHSA 下不同 CVE、同 CVE 下不同 GHSA、同/不同 GHSA-only、context 只有一个 CVE 但公告无 CVE、标识形状 publisher、引文倒序、跨 context CVE 拒绝。没有任意重新排列引文作为修复。

## Must 2：只在同一目录版本和 XML 内容内合并选取

旧 `_cwe_candidates` 要求每个 selection 含源每个 CWE。加入合法的无关 79 selection 就令已验证 78 从 available/1 变 blocked/0。

现在先严格校验每份官方来源 selection，再按 `(taxonomy_version, source_xml_sha256)` 分组。一个组内各子文档选中 ID 的并集覆盖全部源 ID，才生成该组候选；每个候选仍引用实际含该 ID/name 的选择文档，保留版本、源 ID 和精确块证据。未请求该 ID 的合法子集不当否定；同一 XML 的 ZIP/XML 外层响应可以不同，XML hash 是目录内容分组边界。

相同版本不同名字继续形成 conflict；不同完整版本可以带明确版本并列。不能把版本 A 的 78 和版本 B 的 79，或同版本但不同 XML 原体的两个不完整子集拼成“已验证”。确实没有完整目录组确认源 ID 仍 blocked/cwe_identifier_not_verified；显式 missing_cwe_ids 不变成真 ID；非法 selection 不被忽略，CWE failed 而 CVSS 成功保留。新合同用例包括无关子集前后顺序、同目录分列 ID、重叠子集引文、真实缺 ID/显式 missing、名字冲突、不同版本/原 XML 禁拼、完整版本并列、坏 XML hash。

这些 CWE 原体是显式合成 fixture，只验证合同与可观察行为，不证明真实 MITRE 目录版本/真实性，不能计 live。

## 红证据与冻结自检

独立原脚本逐字复制为 `test_independent_boundaries_original.py`，原 reviewer 文件未改。首次复跑两个 Must：00:42:05 → 00:42:08，exit 1，2 failed / 21 deselected / 0 error/skip，保存 original_red.log/xml/command.json，固定旧业务树。原 reviewer 第二版红 log/xml/receipt 也逐字保存为 review_original_*，快照等同性见 identity。

新回归先在旧代码上 00:44:46 → 00:44:49 执行，exit 1，11 failed / 13 passed / 0 error/skip；没有删项或 skip。红时合并测试文件原 bytes 在 new_red_test_snapshot.py；随后按 unit/contract 职责拆分，断言语义保持。修复后早期 24 passed，log/receipt 保留；早期 green JUnit 文件名被冻结拆分回归复用，未额外留一份早期 green XML，不用它给冻结代码背书。冻结数量只据下表对应最终 XML。

新环境 `uv sync --offline --frozen`，00:41:46 → 00:41:53，exit 0，安装 79 包，Python 3.12.13，未安装 semantic extra。纯测试使用本工作树 `.venv/Scripts/python.exe`。测试/静态检查 cwd 为本工作树 backend；CBM cwd 为工作树根；每条完整 argv、cwd、起止、退出码、固定 SHA 与源文件前后 hash 在命令 receipt，无未执行测试伪报。

| 冻结检查 | 上海起止 | exit | 实际结果 |
|---|---|---:|---|
| focused_frozen | 00:47:53 → 00:47:55 | 0 | 101 passed / 0 fail / 0 error / 0 skip |
| regression_frozen | 00:47:53 → 00:47:55 | 0 | 146 passed / 0 fail / 0 error / 0 skip |
| original_recheck_frozen | 00:47:53 → 00:47:54 | 0 | 23 passed / 0 fail / 0 error / 0 skip |
| new_regression_frozen | 00:47:53 → 00:47:55 | 0 | 24 passed / 0 fail / 0 error / 0 skip |
| ruff_frozen | 00:49:05 → 00:49:05 | 0 | exit 0 |
| format_frozen | 00:49:05 → 00:49:05 | 0 | exit 0 |
| mypy_frozen | 00:49:05 → 00:49:06 | 0 | exit 0 |
| recorded_replay_frozen | 00:49:05 → 00:49:06 | 0 | exit 0 |
| source_diff_check | 00:52:01 → 00:52:01 | 0 | exit 0 |
| changed_files | 00:52:01 → 00:52:01 | 0 | exit 0 |
| rg_final | 00:52:01 → 00:52:01 | 0 | exit 0 |
| material_diff_check | 00:57:40 → 00:57:40 | 0 | exit 0 |

focused 的 101 为原 unit 51 + contract 50；新 24 为 unit 13 + contract 11，不与原独立 23 重复相加给总体通过数量。旧 regression 为原 NVD/vendor/T19/T10/T12/T23 七文件，准确 argv 在 receipt。所有冻结检查源 hash 前后不变；Ruff 检 6 文件，format 6 files already formatted，mypy 2 产品模块无问题，diff_check exit 0。初轮 Ruff/format 曾因两新测试 import 顺序/长行/布局 exit 1，ruff_fix exit 1 改完 import 后由 format_fix exit 0 修排版；原静态红日志保留，最终检查才计 passed。

## CBM、调用链与字节封存

CBM v0.11.0 portable 独立仓外 cache `/tmp/dianzi-cbm-r07-public-signals-fix1-20261016`，只索引 backend/src，不含报告、fixtures、秘密或 holdout。先 baseline 1333 nodes / 6765 edges，再固定新业务 1333 / 6769；每次 not_indexed/skipped/parse_partial/parse_unusable 均 0。schema、architecture 与 enrichment/scope/CWE candidates/CWE selector 四 trace 全部 exit 0，完整日志/命令分别保存。边数不当源码等同性证据；源码以 Git blob 与实际字节为准。

新入口图 callers 0 与最终 rg 一致：此片仍是纯候选模块，未接 worker/API/PG，不宣称产品在线能力。candidate_identity.json 保存完整 backend/src filelist/tree SHA、8 个关联源码/测试的工作 bytes SHA、精确 Git blob 与 Git bytes SHA，CRLF 工作树同时比较 LF 规范字节；所有作者原报告/run 的 Git blob 在 base/本次业务 SHA 逐个相同。旧 four module/tests 中仅允许的 signals.py 有修复，signal_sources/原 tests/两合同原样。

artifact_manifest.json 保存本报告及新 run 文件列表、字节数、SHA256、按原 bytes 计算的 Git blob、filelist hash、每条命令和实际 JUnit 数量。manifest 本身不自包含自己的 hash；它的材料提交 SHA 由 root 最终交接固定。封存时用本次 add 命令的 core.autocrlf=false 保留新证据原 bytes，并逐 blob 比较 index/工作 bytes；未修改共享 .gitattributes，不覆盖旧红证据。

材料默认 `git diff --cached --check` 曾把保全的 CRLF 证据脚本每个 CR 判为 trailing whitespace（material_diff_initial，exit 2），原日志保存。针对本次报告/脚本用命令级 `core.whitespace=trailing-space,space-before-tab,cr-at-eol` 核验通过；仍检查实际尾空格/空格后 tab，不加全局忽略，不修改原快照 bytes。业务 source_diff_check、Ruff/format 均已独立 passed。

## 录制资料、费用与原未关闭项

复放只读仓外两份旧公开原 body 及公开 receipt，复用原独立 replay 断言（仅 import 改到本次原脚本快照），原复放脚本 bytes 另保留。先核 HTTP200 与 SHA：EPSS 203 B / c842f9164ed0c3eb350310d4ac181c2a65d61f05629f221b907ab4753d3a59e3；KEV 1787354 B / 47b463a136b8e0956756cfbcdbc2e4b4ccb60c96b4ca7a1ca9f507817cc83045，1745 行。三查询分别 EPSS CVE-2024-37032 available、KEV 同 CVE not_found、KEV CVE-2026-105134 available；原 hash/范围/行索引/值/quote 坐标/hash 通过。两内存负例 cross_cve_epss_lookup 和损坏 KEV invalid_kev_record 通过。不是额外 pytest 数量，也不是 live；原 raw 未复制进 Git。

新增外部文档/来源/模型/测绘/PG 请求均 0，未读秘密/.env/DPAPI/私有资产、未下模型或跑 PoC。保留原作者外部文档 10 项 > 8 预算（超 2，正文成功 5/失败 5）偏差，不追認为 8，不以补请求填缺口；原真实 wall/bytes 未暴露仍 unknown。

原完整 pure_frozen 的 **1944 passed / 1 failed / 10 real_pg deselected**、exit 1、coverage 75.75%（原门 60）保持未关闭；原 native-cpu 守护 GetProcessTimes kernel4062500 + user6250000 = 1.03125s 未过原 <1s。本次不跑整 pure、不改 CPU/阈值或 skip，不用定向信号绿覆盖继承红；主控独立诊断继续。真实 CWE ZIP/XML 缺口仍 blocked_live；完整 CVSS 数学/可选指标语义、PG 发布/权限/并发、运行时/API/UI/e2e、live/manual/性能均未由本片证明。

## 验证状态、评分证据与交回

本次 unit passed（13 新 + 原 unit 51 及所列相关回归），contract passed（11 合成 CWE + 原 50 + 录制复放）；integration/security产品/frontend/e2e/live/manual 均 not_run，CWE 真实目录 blocked_live，继承全 pure failed。实现 complete 只允许 awaiting_review。

T19-C01 保留原值/路径，C05 与 T23-C03 的同范围跨源分歧已有修复和原红→冻结绿；T23-C05 仍保留来源/日期与“非资产入侵”语义。F2/P2 仅登记四维候选及状态的这一证据切片，未生成准确率/召回率/分母/性能结论。T19-C03/C04/C06 的 PG partial/幂等/权限、T23 其余 PoC/修复/资产条件、九维/R07/G-C 最终范围不在本片验收内，合同与计划无变更。

下一步建议：root 将固定新业务/材料 SHA 派给原独立 reviewer 定向复核两个 Must 与其边界；复核前保持 awaiting_review，root 独占状态登记及后续接线。没有自审签字或启动下一卡。

Not checked: 新业务全 pure、PG/运行时/权限/并发、API/UI/e2e、真实 CWE、完整 CVSS 数学、live/人工/正式评分；继承 CPU 红未关闭。
