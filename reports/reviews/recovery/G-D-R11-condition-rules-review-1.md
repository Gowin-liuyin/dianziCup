# R11 / T27 条件与规则纯切片独立初审

What this change does: 本切片实现八类受限条件叶、all_of/any_of 四态组合、固定资产快照求值及逐叶证据发布资格验证。规则生命周期与验证资格分离，纯函数保留证据、冲突、缺口和范围限制；PostgreSQL 发布、实际来源 ACL 与提交重校验仍属后续接线。

结论：**Ship，仅限冻结纯条件/规则切片供后续集成。没有开放的 Must fix、Should fix 或 Nice to have。** 这不是整 R11/T27/T28 的 accepted，也不是 G-D 阶段通过、PG 安全背书或产品真人真值验收。主控继续维护状态；本评审没有修改 progress、accepted、合同、认证、依赖、生产迁移、业务代码、原测试、金标或分母，没有 push。

## 冻结与独立性

- 任务：R11 / T27 独立准备边界，G-D 整门尚未审。新非作者 reviewer 使用 `codex/r11-condition-review1`，工作目录 `D:/wt/r11-condition-review1`。
- 历史源码：`328ed7a933a9a81ec715f447235f4b933e0ed506`；最终源码：`ddfbf8c631a7ea002865d6ae0c1385e63bd87674`；最终材料：`3865fd6a9c568b0d4e6b816e62eb808de5330427`。先独立 checkout 328，再仅 fast-forward 到材料冻结；`git diff` 确认 ddfbf8c→3865 的 backend/src、backend/tests 与 proposal 没有改动。没有把作者未冻结目录用作审查输入。
- 必读依据：AGENTS、00 执行地图、11/12 恢复计划 R11、T26/T27/T28 精确卡、03 §3.6–3.8、04 W06/W07、06 测试合同、`CR-R11_condition_rules_proposal.md`、最新 Ponytail 5.2.0 `ponytail-review/SKILL.md`。先读冻结接口与调用方，再使用合法合成输入和自主负例验证语义。
- 本 reviewer 只交付本报告与 `reports/runs/recovery_r11_condition_review1_20261016/` 中的脚本、原日志、JUnit、收据和 hash 清单。评审缓存不作为交付文件。
- 测试使用已有 `D:/dianzi/backend/.venv/Scripts/python.exe`，不同步/更改依赖。Python 3.12.13、Pydantic 2.13.5；显式 `PYTHONPATH=D:/wt/r11-condition-review1/backend/src`，实际 import origin 两源文件均是独立 worktree；见 `import_origin.log`。缓存、JUnit 和 mypy cache 指向自有 run；禁止写 bytecode。

## 历史 Must 已关闭，旧红保留

1. **验证收据建议回退已发布或退休生命周期**（328 `backend/src/ai_intel/assessment/rules.py:247`；修复后 `rules.py:238`）。
   - 职责与触发：`validate_rule` 返回版本化发布资格收据。传入合法 published 规则和完整支持，或传入合法 retired 规则及时间戳，历史代码的 `resulting_status` 分别返回 validated、candidate。
   - 影响：未来事务调用者若按这个字段保存，会把已发布/退休历史建议回退；本纯切片当前没有 PG 写入，评审没有宣称实际库被改写。retired 应留退休历史，新版恢复必须新规则版本。
   - 最小修复：保留 published/retired 输入状态；只对 candidate/validated 根据资格建议 validated/candidate。作者 ddfbf8c 采用此修复，没有更改规则 AST、政策、阈值或旧断言。
   - 复验：reviewer 自主 `test_lifecycle_validation_does_not_downgrade_frozen_history[published/retired]` 在 328 **2 failed / exit 1**，原样日志/JUnit `historical_lifecycle_328.*` 保留；同文件相同两条断言在最终源码随自主 25 条全部通过。原作者新增的生命周期测试还核对 published 缺支持时资格 false 且状态仍 published；最终直属 102 unit 通过。

## 真实复跑

以下时间均为 Asia/Shanghai 秒级 +08。pytest 工作目录 `D:/wt/r11-condition-review1/backend`；完整 argv、cwd、起止、exit 与当时材料 HEAD 见每项同名 `.command.json`，日志与 JUnit 同名 `.log/.xml`。收据 HEAD 3865 指材料版本，业务源码对应 ddfbf8c。

共同 pytest 命令前缀是 `D:/dianzi/backend/.venv/Scripts/python.exe -m pytest --no-cov -o addopts= -o cache_dir=<自有 run>/pytest_cache --junitxml <自有 run>/<name>.xml -q`。本轮只复跑指定行为集，不据子集计算全仓 coverage；没有改项目配置或门槛。整仓原门结果另列，未改为 passed。

| 项目 / name | 命令末尾目标 | 起止 +08 | 实际结果 / exit |
|---|---|---|---|
| 历史生命周期 `historical_lifecycle_328` | 自有 `test_independent_conditions.py -k lifecycle` | 05:59:23→05:59:25 | 2 failed、23 deselected / 1 |
| 直属 unit `direct_unit_final` | `tests/unit/test_t27_condition_rules.py` | 06:00:25→06:00:27 | 102 passed、0 fail/error/skip / 0 |
| 直属 contract `direct_contract_final` | `tests/contract/test_r11_condition_schema.py` | 06:00:27→06:00:31 | 12 passed、0 fail/error/skip / 0 |
| 直属 security `direct_security_final` | `tests/security/test_r11_condition_security.py` | 06:00:31→06:00:33 | 22 passed、0 fail/error/skip / 0 |
| 自主负例 `independent_final` | 自有 `test_independent_conditions.py` | 06:00:25→06:00:26 | 25 passed、0 fail/error/skip / 0 |
| 旧资产/解析/版本 `old_asset_version_regression` | 下面 11 个既有文件 | 06:00:54→06:01:00 | 288 passed、0 fail/error/skip；2 deprecation warnings / 0 |
| Ruff `ruff_final` | `python -m ruff check` 两源、三直属测试 | 06:01:36→06:01:37 | 全部通过 / 0 |
| 格式 `format_final` | `python -m ruff format --check` 相同五文件 | 06:01:37→06:01:37 | 5 files already formatted / 0 |
| 类型 `mypy_final` | `python -m mypy --cache-dir <自有 run>/mypy_cache` 两源 | 06:01:37→06:01:39 | 2 source files、0 issues / 0 |
| 源码 diff `source_diff_final` | `git diff --check e310f773… ddfbf8c… --` 六个本切片文件 | 06:02:27→06:02:27 | 无错误 / 0 |
| 冻结材料 `frozen_material_audit` | 自有 `audit_frozen_materials.py` 只读 Git objects | 06:01:37→06:01:42 | 78 entries、源码不漂移、canonical hash 一致 / 0 |

旧回归目标为 `tests/unit/test_t26_version_engine.py`、`test_r11_version_branch_context.py`、`test_r11_manifest_parser.py`、`test_r11_manifest_parser_identity_time.py`、`test_r11_inventory.py`；`tests/contract/test_r11_version_ranges_contract.py`、`test_r11_manifest_candidate.py`、`test_r11_inventory_contracts.py`；`tests/security/test_r11_version_ranges_security.py`、`test_r11_manifest_parser_boundary.py`、`test_r11_inventory_boundary.py`。不是 PG 集成测试。

本轮最终代码行为计数为直属 136、自主 25、旧回归 288，共 **449 passed / 0 fail/error/skip**；另有历史 328 的 2 条失败单独保存，未计入新版本 passed。

## 语义、边界与调用链

| 合同 / 检查点 | 已核实可观察结果 |
|---|---|
| T27 C01/C02、四态真值表 | 直属覆盖 32 个 AND/OR 表格组合；自主 false AND disputed→false、true OR disputed→true，仍保留 disputed 子节点、claim 与 span ID。不会短路删掉非决定性冲突。 |
| 八 predicates、组合和预算 | 八叶内部 schema 往返；空组合、未知谓词/任意 NOT、SQL/eval/URL、额外 authority 字段、duplicate JSON key/node ID、cycle/shared node 都拒绝；64/65 节点、8/9 层边界真实检查。63 版本叶含 50 intervals 和 100 explicit versions 的合法满 AST 容量通过，字段预算不当 AST 节点计数。自主 16 MiB 超限与 50000 JSON scalar/container 超限拒绝。 |
| T27 C03、资产与版本 | partial/unknown 空组件不产生排除；absence 仅接受指定 declared_scope 完整声明。fixed 边界、未知版本、维护分支缺失、Go/generic unsupported 与回补未决传播；原版本/解析回归通过，未替换算法或生态支持。 |
| T27 C05、ConditionFact | exact asset_snapshot_id、source/document/revision 链必须匹配；旧快照、model_hypothesis、withdrawn、context 或脱离来源证据不确认实施缓解。支持与反驳/争议保留冲突。纯模型支持事实的 span 仍可审计，不能计为 implemented mitigation。 |
| RuleLeafSupport | 必须绑定 exact leaf digest；修改 leaf expected 后沿用旧支持资格 false。已核验 refutes 即使与 supports 并存仍阻止资格；private span 不能进入 public rule；range_complete=True 必须另有完整性支持。eligible/automatic_publication_eligible 是资格，无实际审批或写入；candidate 仍 candidate。 |
| 生命周期与深层对象 | 只有 published 能 evaluate，candidate/validated/retired 拒绝；时间戳一致性和 strict 正整数 version 拒绝 bool/string/float/非正值。嵌套 VersionInterval 普通赋值受 frozen 拒绝；自主对 `__dict__` 篡改导致 fixed/last_affected 同存后，求值与验证入口重新校验并拒绝，不能利用 mutable 对象逃逸。 |
| T27 C06、T28 C04/C05 的纯部分 | network false 只给 observed_path；software_applicability 网络叶 unknown 且不能取得发布资格。research 前提 true 保留 `research_prerequisites_do_not_confirm_execution_success`，无利用或网络执行；RuleEvaluation 始终保留 rule_kind 限制。 |

独立 WSL 官方 portable CLI 最终命令为 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp cli --json index_repository --repo-path /mnt/d/wt/r11-condition-review1/backend/src --name r11-condition-review1-ddfbf8c --mode fast`：06:00:25→06:00:33、exit 0，1511 nodes / 7815 edges、0 未索引文件。默认 excluded `ai_intel/assets`，另 index `/mnt/d/wt/r11-condition-review1/backend/src/ai_intel/assets`，06:01:59→06:02:04、exit 0，198 / 823。两个图 schema、architecture、评估/验证/parse_manifest 双向 trace 均真实保存。

CBM 最终入边：`evaluate_rule` 和 `validate_rule` 为 0；`evaluate_condition_tree` 仅有 `evaluate_rule` 一条。`rg` 独立跨 backend/src 交叉核查一致，当前没有 API/worker/导出发布接线；不能以图中没有 caller 当作不存在风险的唯一理由。读取 `version_ranges.evaluate_version_assertion`、`AssetSnapshotResponse`、`InventoryService.get_snapshot` 与 manifest parser 确认实际依赖。评审负载依据为冻结 AST 上限 64、facts/supports 上限 64、parser 组件上限 10000 和 Compose worker concurrency=1；未测吞吐、实时性能或生产并发。

作者材料明确首次 CBM 在实现之后。本评审保留此**程序顺序偏差**，没有把后补图伪写为 implementation before；新增独立图只证明这次冻结版本的结构与调用方核查。

## 材料 hash 与既有失败

作者 manifest 78 entries 的 canonical JSON SHA-256 独立重算为 `5dbcce2243ac2622309e21ab9809a7b81b48f442cf18aa3620fc7eeb2555342a`，与作者登记一致。冻结 manifest Git blob 实测 SHA-256 是 `fba4730a9961eade50bb5062149b054066be28a55b2b130c6e66b97f23edc635`；该 blob 的外部 expected 未提供，记 **null**，不把 entries digest 当文件 digest。

`frozen_material_audit.json` 逐项记录作者 raw expected hash/bytes、checkout raw actual、Git blob actual、未知 Git expected=null 和精确匹配表示。78 项均与冻结 bytes 或明确 LF/CRLF 重构匹配；这是冻结内容与作者 raw 清单的一致性核查，未独立读取作者磁盘 raw 目录。不能笼统声称所有 checkout raw 原样 hash 都相同。作者原红、旧版本与原 CPU 限制断言全部保留在材料提交；本评审未修改或删除。

本 reviewer 自有材料另有 `review_manifest.json` 逐项 raw/Git blob hash、`review_filelist.json` 精确文件清单和 `raw_evidence.zip` 原 bytes 备份，ZIP 解压内容逐项 hash 验证通过。原 pytest 的两条红断言日志/JUnit 含四处 `E         ` 行尾空格；自有材料 `git diff --cached --check` 会 exit 2，四处全部保留，未为了外观通过删改旧红、全局禁用 whitespace 或改 `.gitattributes`。源码 diff、评审 prose/脚本的范围检查另行通过；raw ZIP 确保 Git LF 转换不丢原字节。

**整仓 unit 仍 failed**：冻结作者最终 replay JUnit 2214 tests = 2208 passed + 6 failed、0 errors/skipped，exit 1，原门 coverage=73.96% 达 60%。失败为既有 `test_r20_native_cpu_guard.py` 的 python-gil-held/kernel-io LIMIT_APPLIED 空 stdout、idle/short-task 异常返回、TREE readiness 和 native strict CPU 秒门。原 native 最新 `6718750+5156250=11875000`（1.1875 CPU 秒）违反 `<10000000`；历史 `5625000+4687500=10312500`（1.03125）也保留。历史 2212 passed/1 failed、73.95% 不替代最终 6 fail；单独定向曾绿不等于根因已修复。

本评审没有再次运行整仓 CPU 部分：已按明确授权保留所属 R20 风险、避免重复耗资源，不改 limits/timeout/skip 或断言。449 通过是本轮相关纯切片证据，不能改写整仓结果，不能宣称全门 passed。

## 未检查、计划偏差与下一步

integration/PG、frontend、e2e、live、manual 均 **not_run**。PG 实际来源/租户 ACL、revision/block 坐标与 Unicode 子串、内容对必要条件的 semantic support、claim/event 配对真实性、当前性/epoch/CAS、人工审批授权、事务生命周期/outbox 均未由此函数证明。`EvidenceReference.validation_status` 与 `necessary_condition_supported` 是受信调用者收据字段，不能用 fixture 或模型自报替代真实 PG 查询；proposal 0021 仍未实施。无真实外网调用、付费 API、网络资产探测或 PoC 执行。

R11 的 3→5 产品可靠真人真值、双人标注/裁决、T27 持久发布、T28 完整研判/证据包/幂等与提交并发重验、OpenVEX、产品 UI 与 G-D 必要证据删除整门仍保留原验收缺口。已验证的 F2/F3/P2 仅为范围明确的条件/证据行为，A1 仅为确定性内部入口，不给官方准确率/召回率或 Agent 成效数字。

下一建议：主控以此有限 review 处理纯切片，再实现 proposal 中 PG 窄入口并由新的非作者 reviewer 实测真实 ACL、坐标/语义支持、发布/退休、变更 epoch 与并发快照；R20 原 CPU 风险由其所属任务诊断。没有批准公共 schema 或生产迁移改动。

Verdict: **Ship.** 范围仅是 ddfbf8c 纯条件/规则代码与 3865 固定材料供后续集成；整 R11/T27/T28、PG 和 G-D 不签通过。

Not checked: PG/实际 ACL/semantic support/epoch/人工 approval、API/worker/前端闭环、产品真值、真人金标、整门性能与 R20 根因；上述 not_run/failed 不由 fixture 补齐。

自动审批审查拒绝了清理评审 worktree 新建 Ruff 缓存的操作，理由为 `blocked by policy`。没有执行删除或重试；缓存留原处并排除交付，收据 `cache_cleanup_rejection.json` 记 exit=null/process_started=false，拒绝准确发生秒未由工具提供，未编造。
