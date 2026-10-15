# G-B 安全命中诊断与精确 fixture 分类

准确性修订时刻：`2026-10-15T17:58:16+08:00`。仅校正去重文件数和已记录时间格式，原扫描/测试日志及提案记录未改。

本次结果：原分类器发现的 15 个项目命中已逐个追到隔离测试字面量或生成脱敏替代标记，提出 15 条精确记录；原 manifest 没有修改。第三方审查环境内另有 55 个命中，保留扫描前事实与安全元数据，没有归为 fixture；主控原样迁出退役缓存后，临时合成表的扫描拒绝数为 0，原 T06-C06 单例实际 1 passed。

任务状态 `awaiting_review`；诊断/草案实现 `complete`。此结论仅覆盖分类来源、原合同格式和临时输入定向复验，不签 G-B、整 security、live、manual、真实秘密比对或最终验收。

## 输入、边界与原始失败

- 分支 `codex/full-delivery-recovery`。委派冻结为 `799028ef637b61547683b7d210d2ca5df93bb1bc`；扫描及草案实际 HEAD 为 `7ed73540c001a4e7f5b5fa5dc2948c4b4635590f`。主控说明新增提交只包含真实浏览器测试；本诊断使用实际文件 SHA256，未以旧 HEAD 为新增文件背书。
- 已读 AGENTS、00 执行地图、T06 原卡及 03/05/09 合同、状态/交接、最新 Ponytail 5.2 问答接线审查，scanner 和既有 manifest。分析文件 hash 与观察时刻见本 runs 的 `analyzed_file_snapshots.json`、`proposal_source_snapshots.json` 与原 `unclassified_metadata.json`。
- 原始失败为 `reports/runs/recovery_r05_controller_20261015/gb_pure_regression.log/xml/json`：exit 1，1418 passed / 1 failed / 10 deselected，失败为 `test_audit_and_sources_carry_no_secret_values_t06_c06`。log 末尾记录运行 89.17 秒、原 coverage 门 60 已达 73.77%；失败没有删除、覆写或改 skip。
- 只使用 scanner 原 `SCAN_ROOTS`、`SCAN_SUFFIXES`、两模式及安全类别。未读实际凭据、`.env`、附件 KEYS、DPAPI、holdout；未新增业务、更改阈值/模式/ignore、执行付费调用、push、accepted 或新聊天。
- 原允许的 task 报告目录与 scanner 的 `review_ref` 前缀合同冲突。主控明确追加授权本正式 review 入口；未使用路径绕过或修改合同。

## 根因与全部初始命中

首次扫描：`2026-10-15T17:40:31+08:00` 至 `2026-10-15T17:40:57+08:00`，旧表 36 records，70 个未分类模式命中 / 58 个文件。每一命中的 `path/pattern_id/start/end/line/raw_sha256/match_sha256` 均在 `unclassified_metadata.json`；没有写疑似值或原始上下文。offset 按 scanner 原 UTF-8 errors-ignore + universal-newline 的 Unicode 左闭右开位置。

根因有两部分：新增隔离测试/故障审查输出中的已证非真值尚未登记精确位置；两份审查 venv 位于原 scanner 的 reports/runs 候选范围，第三方源码也被扫描。分类缺口不能通过把目录或文件全忽略来解决。

第三方 venv 共 55 个命中 / 47 个文件，逐项结构检视包括语法高亮色值、类型枚举、SQL/Unicode token、库内文档示例、连接参数名、脱敏 repr 与格式字符串。它们不满足当前 fixture 分类来源语义，本提案不加入任何一条。主控核对所有权和无活动依赖后，实际搬迁：

| 原绝对根 | 仓外映射末级 | 主控确认文件数 / before-after 清单 hash |
|---|---|---|
| `D:/dianzi/reports/runs/recovery_r02_persistence_review_1_20261015/venv` | `retired-review-venvs/20261015/recovery_r02_persistence_review_1_20261015` | 4857 / `13966e60e07248c42df86aad8f8d2c24c45e0b8afeade0022df540b5030a0f1f` |
| `D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/venv` | `retired-review-venvs/20261015/recovery_r05_grounded_answer_review_1_20261015` | 6532 / `e258446eb079ef042f4a7a9acc7d6e734dd0d8a11b1c8abcb2ab8206fe431665` |

完整目标父目录 `D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4`；主控原始 receipts 为 `reports/runs/recovery_r05_controller_20261015/retired_review_venvs_before.json`、`retired_review_venvs_after.json`、`retired_review_venvs_move.json`。本 agent 没有移动或删除原文件。`2026-10-15T17:43:56+08:00` 的进程精确路径检查排除检查器自身后，两根无命中。原 review/日志/脚本保留；历史 venv 路径复跑需归档映射或新建冻结环境，不能声称原入口仍可用。

## 项目 15 命中的逐项来源

下表的“数”是 pattern 命中数；同一 span 被两种模式匹配时分别保留记录。共 15 records、11 文件、13 个唯一 path/span。

数字校正：项目文件数先前人工写为 10，没有从 records 的 path 集合实际去重；由此将历史总 58 文件的第三方部分误算为 48。原 proposal 实算为 15 records / 11 unique_paths / 13 unique_spans；原扫描 metadata 实算仍为 70 records / 58 unique_paths，其中 venv 为 55 records / 47 unique_paths，非 venv 为 15 records / 11 unique_paths。原扫描历史、提案记录和分类来源均未改；校正公式、时间、原文件 SHA256 和修订报告 seal 见本 runs 的 `counts_correction_receipt.json`、`counts_correction_seal.json`。

| 被扫位置 | 数 | 核验来源与隔离证据 |
|---|---:|---|
| `frontend/src/api/question-client.test.ts` L13/L27/L37 | 3 | Vitest `vi.stubGlobal` fetch 替身固定返回 CSRF；假时钟/取消场景，来源即当前已提交测试行，git commit/blob/raw hash 全保留。 |
| R01 search TLS `forced_failure_showlocals.log` 与 `forced_failure_showlocals_recovered.log` 各 L53 | 2 | `review_checks.py` L53/L61 的逐字替代常量；两原收据候选 `4b4b9763dc0b75594864b3893dc95a215861d594`，公开失败记录仍 exit 1。真实随机测试密码已由 runner 替换，本分类只针对替代标记。 |
| R02 MinIO `native_auth_failure.stdout.log` L29 | 1 | 当前 `backend/tests/conftest.py` L109 固定脱敏替代字面量。原测试以真实隔离 PG 生成随机 session，匹配的字符串是替代标记；不把原随机值分类为 fixture。 |
| R02 persistence `credential_failure_sanitized.log` L28 与 `credential_failure_v2_sanitized.log` L31 | 2 | 对应 `credential_failure_probe.py` L37、`credential_failure_probe_v2.py` L34 的逐字替代常量。receipt 冻结 `0fe642b1c9e5fe4dafa2774e9432bd96079c1b72`，原内部红例仍保留。 |
| R03 recheck 1 的 header redaction probe、recheck 2 的 header body integrity/redaction probes 各 L17 | 3 | 文件 docstring 明确仅合成；固定字面量传给 `SocketFixture`，输出 `fixture_only`；正式原审报告分别绑定 `59466ceb1703e2741406939adcfb1196e20c77d2` 与 `2522b3a941030f373ccd1736bd54cee411e939a9`。 |
| R05 controller `source_rate_candidate_parser_red.log` L14 | 2 | 同一隔离 socket 异常常量被两模式匹配；逐字追到 `backend/tests/security/test_r03_network_transport.py` 的 AST Constant。原 receipt `2026-10-15T16:51:24+08:00` 至 `2026-10-15T16:51:26+08:00`、exit 1，候选 `00261c4993011b293586a6afd6559b769c14611d`；当前来源 commit/blob 和实际 raw hash 另保存。 |
| R05 frontend `independent_negative.spec.ts` L39 | 2 | `page.route` / `route.fulfill` 显式固定响应 CSRF，原报告说明全部 v1 请求 fixture 隔离、无真实后端；原审最终候选 `a0a94f1007dfdb1811df327ca2f931034af33a2e`。 |

草案 `reports/security/gb_fixture_classification_proposal.json` 只写上述已证非真值的必要 `match_value`。每条按现行 schema 保留模式版本/hash、文件原始 SHA256、精确 start/end、source path/line/hash、`data_mode=fixture`、正式诊断 `review_ref`。git 来源具有实际 commit/blob；未提交 reviewer probe 使用既有 `review_fixture` 协议，保存原 candidate commit、原 report path/hash，以及源字节计算的 `source_content_git_blob`，没有伪造 probe 已存在于业务提交中。

## 实际检查与限定结果

| 实际命令 / cwd | exit / 结果 | 原始证据 |
|---|---|---|
| `python reports/runs/recovery_gb_secret_fixture_classification_20261015/inspect_candidates.py` / `D:/dianzi` | 0；原 70/58 安全元数据 | `unclassified_metadata.json`，含实际起止与原表 hash |
| `python reports/runs/recovery_gb_secret_fixture_classification_20261015/trace_fixture_origins.py` / `D:/dianzi` | 0；AST 来源定位；parser 来源再由草案程序定向补核 | `origin_resolution.json` |
| `python reports/runs/recovery_gb_secret_fixture_classification_20261015/build_proposal.py` / `D:/dianzi` | 0；15 新 records、旧新合成 51；原 loader/schema、全部 hash/offset/逐字 source 检查通过 | `gb_fixture_classification_proposal.json`、`proposal_source_snapshots.json`、`combined_fixture_manifest.json` |
| `uv run --frozen --extra semantic python ../reports/runs/recovery_gb_secret_fixture_classification_20261015/verify_proposal.py` / `D:/dianzi/backend` | 0；`2026-10-15T17:48:34+08:00` 至 `2026-10-15T17:48:46+08:00` scanner 52 findings：51 精确 fixture + 1 原公开 PG 错误比较，0 rejected；原 T06-C06 在 `2026-10-15T17:48:46+08:00` 至 `2026-10-15T17:49:00+08:00` 单例 1 passed、12.63 秒、0 failed/skip | `combined_scan.json`、`targeted_t06.log/xml/receipt.json` |

单例参数为 `tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06 --no-cov -q --junitxml=<本runs>/targeted_t06.xml`。临时 pytest plugin 只在已收集原测试模块替换 manifest 输入路径，原测试、scanner、公共源 manifest 的文件字节未改；不把这个限定输入复验冒充源表已正式合并后的回归。唯一共享表仍 36 records，SHA256 `ab87ee5b9f7b9d8b5dc227a789644326659510049dbf7dd2e705a03646d839ac`。

探索中的首轮 Python import 被本机 site-packages 的同名 scripts 包遮蔽，exit 1；改用 scanner 原文件 importlib 定位后原命令完成。一次 PowerShell 引号表达式及 Windows rg literal-glob 探索失败，也未计为业务回归失败或通过。这些探索命令的精确起止时刻历史未记录，不补猜。未新增测试实现，原 red 日志未覆盖。

## 剩余、计划偏差与下一步

- 搬迁后当前临时合成表扫描没有未分类命中；搬迁前 55 项仍以原始 unclassified 历史保存，没有豁免它们。15 项没有剩余疑似真实值；这是来源诊断结论，实际秘密精确/full+fragment 检查本 agent 为 `not_run`，主控另行负责。
- 原 G-B 整批回归未由本 agent 重跑；live/manual/人工金标/正式指标未运行，不能登记通过。原红例发现的历史密码输出缺陷及其原审结论不因替代标记分类而被抹去。
- 改动只含自身诊断脚本/安全元数据/草案/本报告及 task 索引。scanner、公共合同、业务、认证、金标、阈值、分母、共享 manifest 和 progress 未由本 agent 修改。
- 评分证据限 T06-C06 / E1 的精确分类、可追溯保留失败和既有扫描边界；不扩大为整 E1 或 G-B 达标。
- 建议主控审查提案后统一合并，再实际执行 `python scripts/security_scan.py` 与原 `uv run --frozen --extra semantic pytest tests/unit tests/contract tests/security -m "not real_pg" -q`。实际秘密输入由主控既有授权 scanner 注入；不得把未注入秘密的 `exact_secret_scan=not_run` 改为通过。

Verdict: 分类提案可交主控独立合并审查。Not checked: 源表合并后的完整回归、真实秘密比对、G-B 阶段/live/manual 验收。
