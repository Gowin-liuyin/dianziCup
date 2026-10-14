# R01 / G-A · 历史合成夹具的精确秘密扫描分类

任务状态：awaiting_review；实现状态：complete（仅本实现包）。验证：security=passed（固定候选的离线安全组），unit/contract/integration/frontend/e2e/live/manual=not_run。实际授权秘密的 exact 扫描=not_run，由主控独立注入后复验，不能据本包放行整 R01/T06 或 G-A。

输入固定 SHA：`fd4f1d42e1ad2e39ff7c80897fd50511c3faf299`。分支：`codex/recovery-r01-secret-scan`；工作树：`C:/Users/yinha/.codex/worktrees/recovery-r01-secret-scan/dianzi`。初始 Git 状态为空、detached HEAD；本包新建子分支，没有修改业务 src、公共合同、金标、阈值、依赖锁、infra、全局状态或作者旧日志，没有 push。代码冻结提交=`fd49be0979703db25ac86672d703a840f008b553`；证据提交由交付消息和 Git HEAD 给出，源内容及 Git blob SHA 见本 run 的 `source_snapshot.json`。

首个存档验证命令：2026-10-15T00:34:21.9801542+08:00；最终安全组：2026-10-15T01:02:33.683602+08:00—2026-10-15T01:02:40.223417+08:00。所有时间为实际 Asia/Shanghai 墙钟，没有调整时钟。每条正式复验的 argv、cwd、起止、wall、退出码、JUnit 数量、日志 SHA256 存在对应 JSON。

## 问题、输入输出与边界

独立初审 `reports/reviews/recovery/G-A-R01-behavior-review-1.md` 第 5 项确认明确隔离的 HTTP 测试 nonce 被 C06 当作秘密。前端源码已经生成动态 nonce，但原 rg 输出和失败 traceback 保留了旧合成字面量，导致源已修而原安全扫描仍失败。基线实际重跑 C06：1 failed，exit 1，日志 `baseline_c06.log` 保留。该命令使用 `--tb=no`，避免继续把匹配值复制到新 traceback；没有改原始失败证据。

新增小 `scripts/security_scan.py`，没有依赖、扫描框架或业务入口改动。输入是仓库根、受审分类表和可选已授权 exact 值；输出仅路径、原模式 ID、安全类别。C06 调用相同 helper，所有未知匹配仍失败，断言元数据不带匹配值。原公开 PG 错误布尔比较的 AST 判定和原开发占位策略搬入 helper，语义保持。

两个原正则文本、IGNORECASE、长度 16/6、原扩展名集合和全部五个原扫描根保持：`backend/src`、`scripts`、`frontend/src`、`frontend/dist`、`reports/runs`。`original_pattern_identity.json` 直接从固定输入 Git AST 取原正则比对，两者一致；模式 SHA256 分别为 `09f50b6d1b7a234629bd577c60dd5fa44f1f24842335cb35a35fb178c8618eeb`、`617acb1609824a321f172a0375f094daf1aadbda174cb33adb1229dc5e37f0fb`。缺根仍保留原行为，本 clean checkout 未生成 frontend/dist，本包没有证明新的前端构建扫描或浏览器验收。

分类精确绑定：规范仓库相对路径、原始字节 SHA256、原模式 ID/version=1/模式文本 SHA256、具体左闭右开 span、匹配值、已确认 fixture 出处。span 的单位明确为 UTF-8 errors-ignore 解码、通用换行后的 Unicode code point，与原 read_text 扫描文本一致；原始字节哈希单独固定，Windows 换行改变也不能复用分类。绝对旧 WT 路径、反斜杠、`..`、不规范路径以及解析后逃出仓库或原扫描根的路径全部拒绝。Git 来源绑定 commit/blob/源 raw SHA/行；独立审查夹具来源绑定固定审查报告 raw SHA、审查候选 SHA、源文件 raw SHA/行，不伪称它在被审 commit 内。

exact 比对先看原始字节，即便该值也是已分类夹具仍产生拒绝项。CLI 用显式 `--secret-env <已授权变量名>` 读取主控注入环境，仅比较、不回显；缺失或空输入返回 2 / not_run，无输入输出 not_run。28 个新增合成回归包含 helper 与 CLI 的秘密优先拒绝，但实际密钥测试未执行；本 Agent 未读 DPAPI、KEYS、.env 或真实凭据。

## 最小分类表与出处

表 `reports/security/recovery_fixture_false_positives.json`：36 个匹配记录、7 个精确路径，SHA256=`ab87ee5b9f7b9d8b5dc227a789644326659510049dbf7dd2e705a03646d839ac`。没有目录/整文件豁免，不改变原 regex 分母，没有为第三方 node_modules 扩大表。

| 精确仓库相对路径 | 匹配数 | 原始字节 SHA256 | 来源 |
|---|---:|---|---|
| reports/runs/recovery_r01_frontend_20261014/atomic_secret_scan.log | 4 | 42a2e536b239a8a41b1c998366aa37bc522fd97a83abdf91c63adc3ad9eda71a | b07596c 的 mock HTTP fixture |
| reports/runs/recovery_r01_frontend_20261014/recheck_rg_before.log | 7 | 58e3053b3d3591ec8f6952efdbcefb353eed68f9fb22d2b4328bc8f164ce345c | b07596c 的 mock HTTP fixture |
| reports/runs/recovery_r01_behavior_review_1_20261014/backend_security.log | 1 | 80205b50cd48993b5c27930ce2fe06930c69a49b910bccf9008cc19afe338c98 | 原初审 C06 traceback、同 Git fixture |
| reports/runs/recovery_r01_behavior_review_1_20261014/frontend_behavior.test.tsx | 12 | 9b401b2a37da5375326f82a838186f43973b230b12cb5247964757eec953661c | 非作者 vi.stubGlobal fetch、data_mode=fixture |
| reports/runs/recovery_r01_behavior_review_1_recheck_20261015/backend_security.log | 4 | c22e0f225db93c9d4aca09f578f220e81d9aa47ca6dff8d578ca98596028081a | 后续 C06 traceback、同 Git fixture |
| reports/runs/recovery_r01_secret_classification_20261015/diff_check.log | 4 | 9790dfa15d9e9e56b8c386b65c7c0b0dd54d0ca960f3541cda5b546290643ede | fd4f1d4 既有 pytest 参数化负例 |
| reports/runs/recovery_r01_secret_classification_20261015/diff_check_final.log | 4 | e9ea4fd34a8c24738fe19a4bc0a005639a3f101298d59e8b3f74bb3f1c9dbe72 | 同一既有 pytest 参数化负例 |

`build_classification_table.py` 用 git show/rev-parse 实际核对 b07596cbe6082051bb55bac39f7b5df7020be68c 的源 blob、源 raw SHA 和源行。前两份输入本身是两文件、七个不同源日志行、11 个重叠正则匹配。初审报告固定 raw SHA=`30b9fa7ccd8496537aafe4f79eff5dea1d7d1840482a3b435c788e4a69cf580a`；审查源为 4a17ca7b967a10d6077ba5219984a2d1a74cf320 的独立测试。追加两份主仓审查产物由主控本轮明确授权，代码只读取并生成记录，没有复制或修改原文件。逐 span 详细 diff 全部在 JSON 表中，待非作者定向核对。

另核对 dependency reviewer 保留的 `source_crosscheck.stdout.log`，raw SHA=`f4b971f171f409b391a0a60998e26cdd80a522b5c61f11d2509e80cc179f8fdb`，两原正则实际均为 0 匹配，因此未新增分类。

两次失败的 Git whitespace 诊断在保 CRLF 时回显了旧 T06 测试源码，复制出 8 个重叠匹配。每条都与 fd4f1d4 的原 test Git blob、raw SHA 和完整源码行相等，属于原三条明确 pytest fixture 参数，记录保持精确日志 hash/span。没有删改失败输出，追加分类后再次完整安全复跑（final_3）。这类 Git 诊断本身会回显源码；本包扫描器和 C06 的拒绝元数据只带路径/模式/类别。

## 真实检查与失败记录

下面 B 为本 WT/backend，R 为本 WT；完整 `--junitxml` 绝对参数见对应 JSON，以下 `<run>` 为 `reports/runs/recovery_r01_secret_classification_20261015`。

| cwd / 真实命令 | exit | 实际结果 | 原始日志 |
|---|---:|---|---|
| B uv run --locked pytest tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06 -q --tb=no --cov-fail-under=0 | 1 | 基线 1 failed | baseline_c06.log |
| B uv run --locked pytest tests/security/test_r01_secret_classification.py tests/security/test_t06_authentication_and_scope.py -q --cov-fail-under=0 --junitxml=<run>/targeted_final_3.junit.xml | 0 | 42 passed / 0 failed / 0 errors / 0 skip | targeted_final_3.log |
| B uv run --locked pytest tests/security -q --cov-fail-under=0 --junitxml=<run>/security_final_3.junit.xml | 0 | 60 passed / 0 failed / 0 errors / 0 skip | security_final_3.log |
| B uv run --locked ruff check . ../scripts/security_scan.py | 0 | 保留已有全 backend lint | ruff_final_3.log |
| B uv run --locked ruff format --check . ../scripts/security_scan.py | 0 | 全 backend 与 helper 格式通过 | format_final_3.log |
| B uv run --locked mypy --explicit-package-bases --follow-imports=silent ../scripts/security_scan.py tests/security/test_r01_secret_classification.py tests/security/test_t06_authentication_and_scope.py | 0 | 3 files；MYPYPATH=本 WT/backend/src;本 WT，显式 namespace 定位 | type_final_3.log |
| B uv run --locked mypy src | 0 | 48 source files | source_type_final_3.log |
| R backend/.venv/Scripts/python.exe scripts/security_scan.py | 0 | 候选 19 原正则匹配均精确分类；exact_scan=not_run | candidate_regex_final_2.log |

非 unit 层的 `--cov-fail-under=0` 沿用已有 dev.py 约定，unit 冻结覆盖率阈值未改，未运行 unit suite。完整安全组保留原 32 例，新增 28 例；C01–C06 及旧公开错误三分例全部执行，没有改 skip/阈值/金标。

新增观察边界：原字节无关篡改仍拒绝；同一行或旁边插入真实形态 credential 拒绝；旧 synthetic 复制到新文件拒绝；哈希相同但表外 span 拒绝；路径逃逸/绝对旧 WT/反斜杠/表外根拒绝；原五根未知形态全部拒绝；实际秘密模拟输入等于 synthetic 的 helper 与 CLI 均拒绝；值不进入错误元数据；缺失/空 exact 输入不能声称完成；模式版本/哈希、fixture 标记、固定 review SHA 校验。

初次定向命令在 PowerShell 将 `--junitxml=(Join-Path ...)` 拆错，exit 4 / 0 tests，保留 targeted.json/log；使用完整 argv 参数后 targeted_2 为 32 passed。初版类型命令未指定 namespace 搜索路径，exit 1（输出在会话，未单独归档），配置 MYPYPATH 后出现重复模块名，type_final.log 为 exit 2；增加 --explicit-package-bases 后通过，没有使用忽略或 cast。初版补丁格式修复前的 Ruff 超长行输出留于会话；最终静态结果以存档 final_3 为准。没有把这些执行器/配置失败当业务失败或通过。首轮 40/58 和当前 42/60 的通过日志均保留，没有覆盖。

## 主仓传播、CBM 与尚缺验证

主仓只读复扫只用受审表与两个原正则，不注入真实秘密。清理前 `main_uncovered.json` 为 148 匹配 / 146 拒绝 / 28 文件，包含 dependency reviewer 独占临时 replay 中的安装缓存。主控安排其作者核验归属并回收缓存，原始命令、JSON、JUnit 和哈希证据保持；本 Agent 未删除任何主仓文件，也没有为第三方库编造 fixture 豁免。

清理后 `main_uncovered_2.json`（2026-10-15 实际 +08:00 起止在文件）为 18 匹配 / 0 表外拒绝 / 4 文件：17 个精确合成分类和原 PG 公开失败布尔比较 1 个。每个路径/模式/数量/raw SHA 都保留，未输出匹配值。主仓文件尚未全部进入本候选，candidate 的 60 passed 仅证明固定 WT 加本补丁，不能传播成主仓完整安全或整 R01 通过。主控还须在新冻结主仓独立执行真实秘密 exact 优先比对，并由非作者 review 核查本表；当前没有实际授权秘密命中与否的结果。

CBM 使用官方 portable `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` v0.11.0，独立外部 cache `/tmp/dianzi-cbm-r01-secret-classification-20261015`，persistence=false。只索引本 WT/backend/src 与 scripts，未索引 reports、holdout、秘密目录。backend/src 初索引 524 nodes / 1972 edges；代码变更后刷新 scripts 为 109 / 365（cbm_scripts_final.json/log）。scan_repository inbound 显示 CLI main 与 module 2 个 caller；安全测试在范围之外，由 rg_callers_final.json/log 核对真实 C06 与所有回归调用，没有把图缺边当无调用。未产生 ADR 或第二套业务索引。

六个开发层 unit/contract/integration/frontend/e2e/live 未跑；manual、PG/Redis/OpenSearch、浏览器、容器与外部模型/来源未跑。未下载大模型、未使用付费 API、未执行第三方 PoC。E1/X1 的证据只对应 T06-C06 精确扫描与不泄漏诊断，原认证/租户完整验收、真实密钥安全与 G-A 不据此签字。

## 改动文件与下一步

业务实现文件为 `scripts/security_scan.py`；既有测试改动仅 `backend/tests/security/test_t06_authentication_and_scope.py`；新增回归 `backend/tests/security/test_r01_secret_classification.py`；分类表 `reports/security/recovery_fixture_false_positives.json`；本报告和自有 run 的证据脚本、日志、JSON、JUnit、原模式核对与源快照。完整文件清单见 `source_snapshot.json`，实际 diff 检查见 `diff_check_final_2.json/log`。主控明确追加授权 `.gitattributes` 仅本 run 的 `*.log -text -diff` 与 `*.xml -text -diff` 两条，保持原始证据字节，未扩大扫描豁免。初次 stage 保原字节时 CRLF 被默认 whitespace 检查视为尾随字符，diff_check.json/log 保留 exit 2；追加属性后 Git 保留了已暂存源码的旧 CRLF index，diff_check_final.json/log 仍为 exit 2；只对本包明确路径执行 Git 文本 renormalize 后，既有测试回到 11 增/70 删的最小 diff，final_2 为 exit 0。raw 证据按两条精确属性保持，没有修改输出行尾或空格。

没有公共合同/计划语义偏差。仅按已授权包完成根因修复，状态 awaiting_review；全局 state/旧作者报告不改。下一步由主控冻结集成候选、受控注入真实 secret exact 扫描，再由非作者 reviewer 对 raw hash、span、negative cases 和原安全全组定向复核。未做的六层和外部验证保持 not_run；本包不能用于声称 live 安全、整 T06、R01 或 G-A 已通过。
