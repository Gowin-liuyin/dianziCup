# R18 · SDK/CLI 定向修复 1 · 材料修订

文档首次创建时间：2026-10-16T09:18:03+08:00
本次写作开始/结束：2026-10-16T09:18:03+08:00 / 2026-10-16T09:18:03+08:00
最后更新时间/证据截止：2026-10-16T09:21:41+08:00
业务代码编写起止：历史未记录；不由文件 mtime 或测试时长推算。
作者：/root/r18_protocol_sdk_contract_preparation；状态：awaiting_review；实现：partial（当前修复片完整，整R18保持partial）。
工作树/分支：D:/wt/r18-sdk-client-fix1 / codex/r18-sdk-client-fix1。
基线：d1c30d27dee54bb7895c0860c6a3ce18ea4d4632；已测/冻结代码：6d85742b0114cc5e304e88b2aa930755ccce9bc9；tree：88018597cb9bb94971edb38d90e4525f6b04a8a4；已审修复SHA：尚未独立复核。
material提交、manifest和推送以实际收据为准；本Agent未push，未改accepted或全局进度。

## 1. 具体问题与修复

依据 [独立初审](D:/wt/r18-sdk-client-review1/reports/reviews/recovery/G-E-R18-sdk-cli-review-1.md)，报告SHA b3d9c3cfe11ac84e6f1b39db6c025309b016fed67f40ea7676cf663d06b70527。原作者86材料与reviewer83材料均逐raw hash核对未变，见 [protected_upstream.json](../runs/recovery_r18_sdk_client_fix1_20261016/protected_upstream.json)；原65 probe逐字复制未改断言。
Must1：三种无连字符/花括号/urn UUID、空格日期、短偏移格式、逗号秒、epoch字符串被Pydantic JSON strict路径接受并规范化；冻结FormatChecker拒绝。现共享PublicUuid/PublicDateTime在转换前检验原始字形，覆盖所有既有UUID/aware字段和数组，成熟Pydantic仍负责typed UUID、日历和时间解析。JSON模式明确委托原strict AwareDatetime TypeAdapter；普通Python UUID/aware datetime仍支持，无新依赖。
Must2：合法中文emoji QAAnswer在PYTHONIOENCODING=ascii实际进程UnicodeEncodeError，stdout空、exit1。现wire_json增加兼容可选ensure_ascii=False，CLI ask/check用True保留JSON解析后的全字符；普通REST默认序列化不变。执行/输出错误保留3，旧风险未完整仍2，未据自然语言或202推0/1。
新增2共享字形guard及兼容序列化参数是修复共同根因所需；没有逐对象拷贝校验、另造JSON/RPC、额外输出框架、业务数据库或根依赖。只修改models.py/cli.py与自有回归/仪器；client.py、原99/9、公共schema/auth/locks/package metadata/LICENSE/build/progress均未改。

## 2. 时序、调用方与冻结

新WT基线d1c30d27，首次业务修改前独立CBM index与全UUID/AwareDatetime/wire_json/stdout调用搜索exit0；原旧WT/d1c/f17目录未改。
调用链：CLI→strict输入DTO→DianziClient固定POST→typed返回→CLI ASCII JSON；格式guard为八对象/common共享，HTTP返回违规变ResponseContractError，输入违规在IO前拒绝。wire_json默认保持原调用兼容，当前额外调用仅CLI。
独立project=dianzi_r18_sdk_fix1_20261016，索引范围sdk/python，未包含秘密/holdout；freeze后refresh绑定6d85742b0114cc5e304e88b2aa930755ccce9bc9，wire/CLI trace与rg交叉核实。图零边不代表无调用；fixtures排除由源码和真实子进程补证。
MCP f17使用原models，缺陷传播仍阻断其验收。必须在另新组合WT复用固定源码+f17后跑原114和新格式MCP测试，再新非作者审查；本修复不改f17冻结目录或拿其旧绿给新代码背书。

## 3. 实际验证

最终组合230 / 230passed / 0failed/error/skip：原SDK99、原公共合同9、逐字原review65、新格式46、新CLI11。新CLI在临时loopback fixture真实子进程验证ASCII/UTF8 ask/check/queued完整JSON、2；401和输入格式错3；输出sink失败3。Fixture均显式synthetic，零产品/付费外调；临时服务器有100调用/60秒边界和join关闭，实际network收据在run，不能称PG/model/live。
strict mypy4产品源文件exit0；项目backend Ruff/format现改文件和自有仪器exit0；staged diff check0。
unit/contract/security边界passed（仅列出范围）；integration仅临时HTTP/实际CLI传输passed；frontend/e2e/manual not_run；产品PG、Key撤销/租户隔离、六工具/正式预算/安装包/插件/live blocked或not_run。本片未验证官方评测、准确率或完整系统时效。

| 标签 | 实际argv | 开始 / 结束（Asia/Shanghai） | exit | 原日志 |
|---|---|---|---|---|
| original65_datetime_json_fix | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py -o addopts= --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/original65_datetime_json_fix.xml` | 2026-10-16T08:45:59+08:00 / 2026-10-16T08:46:10+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/original65_datetime_json_fix.log) |
| original99_plus9_plus65_and_new | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests tests/plan/test_public_api_v2.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py -o addopts= --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/original99_plus9_plus65_and_new.xml` | 2026-10-16T08:48:58+08:00 / 2026-10-16T08:49:17+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/original99_plus9_plus65_and_new.log) |
| original_65_after_fix | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py -o addopts= --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/original_65_after_fix.xml` | 2026-10-16T08:44:16+08:00 / 2026-10-16T08:44:28+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/original_65_after_fix.log) |
| original_65_before_fix | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py -o addopts= --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/original_65_before_fix.xml` | 2026-10-16T08:43:21+08:00 / 2026-10-16T08:43:31+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/original_65_before_fix.log) |
| protect_upstream | `D:/dianzi/backend/.venv/Scripts/python.exe reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:49:35+08:00 / 2026-10-16T08:49:35+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.log) |
| sdk_fix1_code_commit | `git commit -m R18 fix strict wire formats and portable CLI JSON output` | 2026-10-16T08:50:30+08:00 / 2026-10-16T08:50:30+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_code_commit.log) |
| sdk_fix1_final_format | `D:/dianzi/backend/.venv/Scripts/ruff.exe format --check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:50:18+08:00 / 2026-10-16T08:50:18+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_final_format.log) |
| sdk_fix1_final_format_check | `D:/dianzi/backend/.venv/Scripts/ruff.exe format --check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:49:35+08:00 / 2026-10-16T08:49:35+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_final_format_check.log) |
| sdk_fix1_final_source_lint | `D:/dianzi/backend/.venv/Scripts/ruff.exe check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:49:53+08:00 / 2026-10-16T08:49:53+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_final_source_lint.log) |
| sdk_fix1_format_apply | `D:/dianzi/backend/.venv/Scripts/ruff.exe format --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py` | 2026-10-16T08:48:17+08:00 / 2026-10-16T08:48:17+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_format_apply.log) |
| sdk_fix1_frozen_index | `wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r18-sdk-client-fix1/sdk/python --name dianzi_r18_sdk_fix1_20261016 --mode fast` | 2026-10-16T08:50:31+08:00 / 2026-10-16T08:50:38+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_frozen_index.log) |
| sdk_fix1_helper_format | `D:/dianzi/backend/.venv/Scripts/ruff.exe format --config backend/pyproject.toml reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:49:53+08:00 / 2026-10-16T08:49:53+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_helper_format.log) |
| sdk_fix1_prechange_architecture | `wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json get_architecture --project dianzi_r18_sdk_fix1_20261016 --format json` | 2026-10-16T08:43:00+08:00 / 2026-10-16T08:43:04+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_prechange_architecture.log) |
| sdk_fix1_prechange_callers | `rg -n UUID|AwareDatetime|\.wire_json|sys\.stdout\.write|sys\.stderr\.write|QAAnswer|Citation sdk/python` | 2026-10-16T08:42:59+08:00 / 2026-10-16T08:42:59+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_prechange_callers.log) |
| sdk_fix1_prechange_index | `wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r18-sdk-client-fix1/sdk/python --name dianzi_r18_sdk_fix1_20261016 --mode fast` | 2026-10-16T08:42:34+08:00 / 2026-10-16T08:42:40+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_prechange_index.log) |
| sdk_fix1_ruff_first | `D:/dianzi/backend/.venv/Scripts/ruff.exe check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py` | 2026-10-16T08:47:23+08:00 / 2026-10-16T08:47:23+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_ruff_first.log) |
| sdk_fix1_stage_code | `git add -- sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_independent_boundaries.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py reports/runs/recovery_r18_sdk_client_fix1_20261016/protect_upstream.py` | 2026-10-16T08:50:19+08:00 / 2026-10-16T08:50:19+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_stage_code.log) |
| sdk_fix1_staged_check | `git diff --cached --check` | 2026-10-16T08:50:19+08:00 / 2026-10-16T08:50:19+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_staged_check.log) |
| sdk_fix1_style_after_format | `D:/dianzi/backend/.venv/Scripts/ruff.exe check --config backend/pyproject.toml sdk/python/ai_intel_client/models.py sdk/python/ai_intel_client/cli.py sdk/python/tests/test_wire_formats.py reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py reports/runs/recovery_r18_sdk_client_fix1_20261016/run_check.py` | 2026-10-16T08:48:38+08:00 / 2026-10-16T08:48:38+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_style_after_format.log) |
| sdk_fix1_trace_cli | `wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project dianzi_r18_sdk_fix1_20261016 --function-name dianzi_r18_sdk_fix1_20261016.ai_intel_client.cli.main --direction both --depth 2 --max-output-tokens 1600 --format json` | 2026-10-16T08:50:51+08:00 / 2026-10-16T08:50:56+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_trace_cli.log) |
| sdk_fix1_trace_wire | `wsl.exe /tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json trace_path --project dianzi_r18_sdk_fix1_20261016 --function-name dianzi_r18_sdk_fix1_20261016.ai_intel_client.models.PublicRecord.wire_json --direction both --depth 2 --max-output-tokens 1600 --format json` | 2026-10-16T08:50:46+08:00 / 2026-10-16T08:50:51+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_trace_wire.log) |
| sdk_fix1_type_after_format | `D:/dianzi/backend/.venv/Scripts/mypy.exe --strict sdk/python/ai_intel_client` | 2026-10-16T08:48:38+08:00 / 2026-10-16T08:48:39+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_type_after_format.log) |
| sdk_fix1_type_first | `D:/dianzi/backend/.venv/Scripts/mypy.exe --strict sdk/python/ai_intel_client` | 2026-10-16T08:47:20+08:00 / 2026-10-16T08:47:23+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_fix1_type_first.log) |
| sdk_format_and_cli_fix1 | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_and_cli_fix1.xml` | 2026-10-16T08:47:54+08:00 / 2026-10-16T08:47:57+08:00 | 2 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_and_cli_fix1.log) |
| sdk_format_and_cli_fix1_recheck | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests reports/runs/recovery_r18_sdk_client_fix1_20261016/test_cli_fix1_regressions.py --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_and_cli_fix1_recheck.xml` | 2026-10-16T08:48:17+08:00 / 2026-10-16T08:48:26+08:00 | 0 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_and_cli_fix1_recheck.log) |
| sdk_format_regressions | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_regressions.xml` | 2026-10-16T08:47:08+08:00 / 2026-10-16T08:47:10+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_format_regressions.log) |
| sdk_original99_after_fix | `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -q sdk/python/tests --junitxml=reports/runs/recovery_r18_sdk_client_fix1_20261016/sdk_original99_after_fix.xml` | 2026-10-16T08:45:14+08:00 / 2026-10-16T08:45:16+08:00 | 1 | [log](../runs/recovery_r18_sdk_client_fix1_20261016/sdk_original99_after_fix.log) |

## 4. 原红与修复台账

| 触发 | 实际/根因 | 修复/复验 | 状态 |
|---|---|---|---|
| 原65同输入 | 57pass8fail，确认7格式+ASCII输出失败 | 共享字形与ASCII输出；原65后65/65 | 已修，待独立复核 |
| 首版BeforeValidator | 合法日期在Pydantic前置Python路径误拒，原65有5红、原99有6红 | JSON模式委托原strict datetime adapter；全230通过 | 已修，原红保留 |
| 新格式仪器 | 把inline AnswerClaim/Assessment误作$defs独立项，2失败 | 使用合同实际JSON Pointer，不改样例/预期；46通过 | 已修，仪器 |
| 新CLI仪器 | pytest参数名request保留，collection exit2 | 改自有变量名input_value；11通过 | 已修，仪器 |
| 样式/仪器 | 新行超项目100列、helper格式；Ruff/format红 | 项目格式化后lint/format0 | 已修，仪器 |
| PowerShell树读取 | 未引用HEAD^{tree}造成参数解析错误，未保存该交互raw文件 | 引用或Python argv取得实际tree 88018597cb9bb94971edb38d90e4525f6b04a8a4 | 已修，定位仪器；不伪称有原raw收据 |

实际发现/关闭时点见首红/复验JSON；没有独立逐编辑时钟者标历史未记录，不拿test时间冒充写作时间。修复源码均冻结于6d85742b0114cc5e304e88b2aa930755ccce9bc9。

## 5. 合同、限制与交接

没有新重大决策、评分/金标/阈值/分母/失败skip变动；没有项目外用户文件、凭据/产品key/holdout读取与提交。原86+83材料和copy65精确hash保护。代码回滚为仅回退本片models/cli及自有测试，保留所有历史；不迁移/downgrade/drop。CLI输出转义是JSON表示变化，解析值保持一致；需消费者按JSON解析。
依据：[Pydantic严格JSON说明](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)、[jsonschema格式校验](https://python-jsonschema.readthedocs.io/en/stable/validate/#validating-formats)、[RFC3339](https://www.rfc-editor.org/info/rfc3339/)。当前范围仍使用冻结FormatChecker的无闰秒支持，不宣称覆盖其未支持形式。
费用：编程Agent费用unknown；未产品API/模型/测绘付费调用，不虚填0。本片尚未独立accepted、未push；整R18/T04/T32/T35/T51/G-E不因这230绿而过门。

## 6. 修订记录

2026-10-16T08:51:52+08:00 · 首次落盘；两Must、真实首红/回归、7文件source identity、83+86保护与依赖传播记录。后续独立复核由root登记，不由作者自签。

## 7. 字节证据补记

2026-10-16T08:52:44+08:00 · 六个真实fixture subprocess的ASCII/UTF8 answer、queued、stack已保存完整stdout/stderr.raw，见 [fixed_cli_raw_observations.json](../runs/recovery_r18_sdk_client_fix1_20261016/fixed_cli_raw_observations.json)。均exit2、JSON值逐项完整、单次loopback请求，无traceback或合成Key；fixed_cli_raw命令exit0。不是产品live。首次创建时间保持，实际最后更新时间/补记写作开始结束为2026-10-16T08:52:44+08:00。

2026-10-16T08:54:41+08:00 · 证据首版生成器的长Markdown字面量触发E501；首版完整保留为write_fix1_evidence_initial.txt，同名Python改为小型来源/230结果验证器。没有禁用或忽略检查；材料验证exit0、最终helper lint0。此变化仅证据仪器，产品冻结source不变。补记实际最后更新时间为2026-10-16T08:54:41+08:00。

## 8. 材料检查更正

2026-10-16T08:55:54+08:00 · 代码source6d暂存检查exit0；首个材料检查exit2，原pytest红日志与JUnit包含原始尾随空格。后续命令错误地继续产本地材料checkpoint 1a24ff9d8fff2aa38b167e39d449ebfca51779c0，未push、未验收，保留历史。现仅本run/.gitattributes将.log/.xml/.raw标binary，保留原始bytes和所有红，不修改根属性、不忽略业务/代码测试；审查者须读取原文件及hash而非仅依赖文本diff。原106 manifest逐字保留artifact_manifest_initial.json（SHA9edda5ec7c27ce3d2a7737b1dc0ee116be54544e4d4afb397d31ec78b4bc3164），新材料另冻结。最后更新时间/本修订写作时点为2026-10-16T08:55:54+08:00。

## 9. 独立诊断与最终材料修订

2026-10-16T09:15:55+08:00 · 独立诊断8d8d26e044dfb150cfc6a8657bbc67d4d46796e6确认stat cache与属性时序根因，18 Git调用/10 toy场景/6 failclosed场景；诊断不替代产品验收。root实际读取后授权一次57path受控renormalize，09:08:35–09:08:41 exit0；全110 index/disk逐hash、source6d、原86+83保护通过，proof5574fb196b9eaafd0c15e097dec9cc44d77d0b095b620876bcb57ee195b6180e。root另核绿proof后批准现31 changed paths checkpoint，严格前置exit0，09:12:07真实commit0，SHA c5d1e734510afdc2d9754a1b9938dfd612796e3b。新postcommit完整逐110字节核验见repair31_verified_commit_bytes.json，不含业务改动。

原1a24ff9d材料check2和f1eafe20原字节proof1之后误继续commit都保留，外层两临时脚本全部原行/精确失败时点未保存者仍unknown；现每个mutation前单独看exit与proof，不在同exec无条件接commit。初post-proof名字与runner receipt冲突，记录被覆盖成receipt，不能称旧逐条文件仍存在；新增独立不同名proof按实际新时点重验。尝试修改自有已入110 manifest的验证helper导致postcheck1，未继续commit，现已精确恢复原bytes，全110原manifest成员未变。以后历史helper只对原声明SHA执行，不为当前tip伪造已运行。

原110 artifact_manifest.json SHA265539c8e9978eb28c36f8e017d323e4f91707dec8819f7a9b10b5166b387558保持原bytes，新追加材料明确使用artifact_manifest_final.json，不递归改原manifest。来源代码仍6d85742b0114cc5e304e88b2aa930755ccce9bc9/tree88018597cb9bb94971edb38d90e4525f6b04a8a4；修复仍awaiting_review，待原非作者新WT定向230/原65/raw完整检查。提交之后的SHA/tree与核验留post receipt，未push。首次创建时间保留，本修订实际写作/更新时间为2026-10-16T09:15:55+08:00。

## 10. 新文件边界与旧报告恢复

2026-10-16T09:18:03+08:00 · 此文件为新的独立材料修订，保留原230测试和两Must完整事实及全部材料失败。旧R18-sdk-client-fix1.md按原manifest绑定raw SHA f3d196caaeffe2d76ef443e3c033e2bb01401f25a8c43442b0c95abb2c82d6f9恢复；先比较Git LF候选不匹配exit1且没有mutation，再在两个候选中只选cryptographic完全匹配的CRLF原bytes，不假定Git文本等于原raw。原110封存成员及旧helper保持不变，现修订/后置proof/新增manifest用新文件名。未修改正式SDKsource6d/根属性/原169材料/金标。原artifact_manifest_final.json为早期未提交候选已superseded，其旧报告hash不作为最终结论；最终范围将由新artifact_manifest_material_repair.json明确列原110 digest和新成员。

2026-10-16T09:21:41+08:00 · 新scope名单首轮断言exit1（cachedcheck0）：原artifact_manifest.json自引用排除于原110 files，仪器误归新增，导致期待staged含未变旧文件。仅改新manifest分类为frozen_original_manifest，不动原文件；原失败日志保留，新staged名单必须精确等新增scope。没有失败后继续commit。
