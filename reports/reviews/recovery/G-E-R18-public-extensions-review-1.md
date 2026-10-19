# G-E / R18 public extensions 独立审查 1

What this change does: 这次四文件变更新增 public extensions v1、10 个结果/来源/任务定义及 23 个隔离 schema 案例，并落细 CR-R09 已授权的兼容、风险与协议输出词表合同。旧 v2 的 14 个定义保留，当前变更没有实现新 REST producer、SDK/MCP adapter 或 8000 token 输出控制。

任务编号与状态：R18 public 合同切片 `needs_changes`；实现仍 `partial`。结论只适用于此切片，不放行整 R18、G-E、原 T04/T32/T35/T51，也不登记 accepted。

被审代码：`456320b6c78e2936fd9f9767724ec3eb17f5c88b`；范围 `456320b^..456320b`，4 个新增文件、2009 行。fresh worktree `D:/wt/r18-public-extensions-review1`，分支 `codex/r18-public-extensions-review1`，创建完成 `2026-10-16T09:35:33.5718573+08:00`。非作者 reviewer：`/root/r18_public_extensions_first_independent_review`。报告首次写作/封存时间见本报告末尾；证据截至 `2026-10-16T09:41:34.5415539+08:00`。

读取 AGENTS、00 执行地图、恢复 R18 卡、T04/T32/T35/T51 与其 03/04/05/06/09 合同、固定版本 progress/task_state/context_handoff、CR-R09、CR-R18、两 public schema、原新增测试和任务报告；采用 Ponytail 5.2 review。固定版本 progress 索引中整 R18 尚为 pending/not_started，而本切片任务报告明确 awaiting_review/partial；进度不是功能证据，本审查不修改这些材料。

审查文件是 `backend/tests/contract/test_r18_public_extensions.py`、`contracts/schemas/public_api_extensions_v1.json`、`docs/decisions/CR-R18_public_envelopes_and_output_budget.md`、`reports/tasks/R18-public-envelopes-output-budget.md`。实际新增文件仅本报告与 `reports/runs/recovery_r18_public_extensions_review1_20261016/`；没有改业务、原材料、进度、秘密或盲测，没有提交/push/DDL/付费调用。

## Must fix

1. **任务轮询地址允许非 UUID 尾部**（`contracts/schemas/public_api_extensions_v1.json:1454–1456`，P2）。

   - **职责：** TaskDescriptor 提供带 UUID 的任务身份与轮询地址，供新客户端恢复异步状态；03 通用 ID 合同与同对象 task_id 的 uuid 格式要求适用。
   - **触发与问题：** 保留合法 task_id `11111111-2222-4333-8444-555555555555`，只把 poll_uri 改为 `/api/v1/tasks/` 加 36 个 `-` 或 36 个 `a`。带 FormatChecker 的实际 Draft202012Validator 对两者均返回 true，因为字符类只限制字符集合与总长度；这些尾部不是 UUID，消费者按该地址轮询无法得到所描述的任务。
   - **最小修复：** 仅将新 TaskDescriptor 的 pattern 收紧为 `^/api/v1/tasks/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`，补入这两条负例和合法地址正例。原 v2 TaskHandle 与 14 个复制定义不能修改；地址 UUID 是否与 task_id 相同仍由 typed validator/producer 比较。
   - **不修的影响与复验：** 格式合同会向 SDK/MCP 承诺一个不能正确寻址的任务。固定代码自拟 97 案例中这两条真实失败；只在独立测试进程内替换 pattern 的建议验证 97 passed/exit0，说明该最小修复保留本次合法矩阵。该绿结果属于修复假设，仓库代码仍未改、Must 未关闭；作者冻结新 SHA 后复跑原23、自拟97、14defs一致性和 lint/format，再交独立复核。

## 合同切片核验与生产接线条件

两 schema 均通过 JSON Schema 元合同检查。旧 v2 Git 内容相对父提交未变，14/14 defs 逐项结构相同，extensions 有24defs；新10对象都拒绝额外字段。新 UUID 字段拒绝畸形标识；时间字段拒绝无时区和不存在日期；新任务外部地址、路径追加和 query 注入被拒绝。九状态 × ask/stack_check 的合法组合及非终态假答案、成功缺结果/带 error/pending/failed、失败/取消/blocked 假成功/缺 Problem、错误 task_type payload 均核验，没有发现 conditional 联合误拒合法矩阵。

风险 score/severity 基本边界、四档 confirmed 阈值、缺 claim/assessment/citation/rule_version 拒绝通过。CR-R18 明确 `r18-risk-policy-1` 是应用归一化分带，参考 [FIRST CVSS v3.1 §5](https://www.first.org/cvss/v3.1/specification-document#5-Qualitative-Severity-Rating-Scale)；本次实际读取该官方表，未把 v2 源分级称为含 critical。v2/3.0/3.1/4.0 原分数版本可保留，归一化等级不能覆盖原始 claim。

以下是独立 `provenance.json` 记录的**schema 接受但部署前必须额外校验**的输入，不计作业务通过，也不把当前缺失的 producer 称作已经实现但只缺测试：

| 输入 | schema 实测 | 下一切片必须验证 |
|---|---|---|
| RiskFinding citation URI=`javascript:alert(1)` | 接受，继承冻结 v2 的 uri 语法 | 安全公开链接规则；已有共享 CitationProjection 使用 HttpUrl，前端 parseCitation 拒绝非 HTTP(S)/凭据；新 adapter 必须复用并实测，不修改14defs来伪称旧协议已有安全链接判断 |
| healthy 且两个观测时间均 null | 接受 | 来源健康由当前持久化观测推导；enabled 不是成功证明，无观测只能 never_polled/unknown |
| none_confirmed 同时包含 high finding；complete 同时有 unknown index | 接受 | 跨数组一致性拒绝，unknown/conflict/partial/stale 不降为 CLI0 |
| 单组件请求中的 finding index=199 | 接受，仍在绝对上限内 | 绑定真实请求数量与已评估范围，去重、事件/assessment/claim/rule/current/ACL 全链资格核验 |
| 合法 poll UUID 与 task_id 不同 | 接受 | producer 使用真实 job，typed validator 对两 ID 做一致性检查 |
| partial/null result/null error 且三个 step 数组空 | 接受 | partial 来自真实进度/缺口事实，不能据 schema 宣称成功完成或伪造任务轨迹 |

CR-R18 已明确上述跨数组/支持/PG资格校验未实施，因而本审查不将这些全部归为当前 JSON 合同的 Must；同时不能借此允许消费者直接用 JSONSchema 生成安全结论。原测试 `test_source_health_remains_unknown_until_an_actual_observation` 实际只验证 unknown 示例可接受和 secret_ref 可拒绝，没有建立实际健康判定功能证据。

SourcePage/VulnerabilityPage/Detail 的 cursor 空串/2049字符与 SourcePage101项均拒绝；合法页接受。principal/ACL/查询/scope epochs/排序绑定、当前权限重锁和跨页事实完整性仍未运行。风险必须同事件支持、完整证据 validator、当前研判/规则/快照和最终事务核验；引文存在、schema 有 required 引用不证明内容支持。确认阈值 finding 可以令 CLI1 同时显示未知；没有该 finding 且有任意不确定只可 CLI2。原 check 默认保持 v2 StackCheckResult，新 profile 只能显式 opt-in 媒体类型；旧客户端缺风险摘要仍2。此处仅核准合同要求，没有执行 CLI0/1。

## 调用关系与范围证据

独立 CBM `r18_public_review1_backend_456320b`、独立仓外 cache `/tmp/dianzi-cbm-r18-public-review1-20261016` 只索引此 WT 的 backend/src：146 File、2069 nodes、11375 edges，0 partial/unusable/skipped；index、schema、architecture、create_application 与 build_question_router trace 均 exit0。另用 `rg_old_callers` 及直接代码阅读交叉核查：app.py134–153 注册现有 `/v1` 与 `/api/v1` 别名；question_routes.py103/129 返回 QuestionAnswerResponse；job_routes.py39–40 为 `/jobs/{job_id}`；answering/service.py162/299 使用既有严格问答投影；共享 CitationProjection/QuestionAnswerResponse 与前端 question/source client 路径保持旧调用链。

`rg_new_profile_symbols` 在 backend/src、frontend/src、templates、scripts 无新增 profile/producer/词表符号，exit1 是无匹配。先前附带8000词搜索匹配了 fixture UUID 中的8000，日志保留，已用精确符号查询澄清。图没有边不单独证明缺接线；结论来自注册入口、共享类型、调用方阅读和明确未实施声明的合证。未启动应用或测试真实认证/PG/HTTP。

## 真实执行与非冻结材料

全部关键执行的完整 argv、cwd、+08 起止、退出码和 stdout/stderr 见同目录 `*.command.json`，汇总见 `commands.json`；下表是结果摘要。

| 运行 | +08 开始/结束 | exit | 实际结果 |
|---|---|---:|---|
| original23；Python offline runner → pytest 原文件 `-v --no-cov -p no:cacheprovider --junitxml=...` | 09:36:50.233527 / 09:36:53.645950 | 0 | 23 passed，0 fail/skip；原七schema样例在case中复验，不重复计数 |
| independent 初次 | 09:38:20.151648 / 09:38:22.589601 | 2 | 0 collected/1 collection error；审查 fixture 错取不存在的 StackCheckResult 示例键，不是业务失败 |
| independent_fixture_fix1；自构建有效 stack/vulnerability | 09:38:52.991997 / 09:38:55.682903 | 1 | 97 collected，95 passed/2 failed/0skip，两红属于同一 poll_uri Must |
| proposed_pattern_only；只改测试进程内 pattern | 09:40:02.846580 / 09:40:07.101634 | 0 | 97 passed/0skip；修复建议证据，不能当固定456通过 |
| tracked_style / tracked_format | 09:40:57.006768 / 09:40:57.517901 | 0/0 | 原新增测试 Ruff检查/format --check通过 |
| provenance_git_blob / diff_check | 09:40:57.647112–09:40:59.124326 / 09:41:33.911950–09:41:33.990263 | 0/0 | schema/14defs/缓存digest、冻结diff空白检查通过 |

两 offline runner 对 socket.connect 显式拒绝并记录0连接尝试；本审查物理 PG 请求0、付费调用0、词表下载0。没有将 `--no-cov` 结果冒充全仓60%覆盖门，门槛没有修改。第一批只读导航命令还出现不存在候选路径与默认GBK读取错误；改为实际路径和UTF8后继续，未误计业务测试失败。

主仓库仅只读精确原材料路径：`D:/dianzi/reports/runs/recovery_r18_public_contracts_20261016/{commands.json,whole_coverage_scope_mismatch.stdout.log,contract_scoped.xml}` 与 `D:/dianzi/reports/runs/recovery_r18_output_encoding_20261016/{encoding_receipt.json,encoding_receipt_initial.json,offline_encoding_smoke_initial.log,offline_encoding_smoke.log,official_installed_o200k_source.txt}`。逐文件hash与来源内容在 provenance.json；这些是主仓库未跟踪原运行证据，不是固定456 Git材料。原合同子集23passed但覆盖约2%/exit1、style初红与修复后0、最初patch.mock AttributeError/exit1和修后offline成功均保留。

外部官方 pinned cache `D:/dianzi-runtime-cache/tiktoken-o200k-base-20261016/fb374d419588a4632f3f557e76b4b70aebbca790` 本次只读核hash：3613922 bytes，SHA256 `446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d`。原 encoding receipt 绑定较早 d31f37f 并记录 offline smoke；本次没有重跑编码，也没有8000token CallToolResult实现或分页检查。该词表只定义协议预算，不等于提供者计费token；费用unknown。

冻结 extensions Git blob/LF内容 SHA256=`af28d516ddfb894eece4c88a8520f71b4ff0ecf37281296adfd30d4a98ed4611`，与CR记录相符；Windows CRLF checkout bytes=`fdfe280f8b32b3811cb715c552af4075161c47271f94daf46b16d0f87e2c63f7`，两者不混称。v2 canonical=`1c12e4dee3682a531f35f776760da4a97e47eab65564e28e93f9b026382a17f3`。

## 下一步与审查边界

评分证据仅支持 A1/E1/X1 的版本化 schema、未知保留、引用字段与离线资源准备这一合同切片；没有准确率、性能、真实客户端兼容、插件隔离、部署或整 T 验收证据。unit/integration/security/frontend/e2e/live/manual 为 not_run；合同固定版本因 Must 为 failed。未运行付费模型、PG、前端、完整覆盖、producer资格/ACL并发、MCP最终输出token/bytes/continuation或Codex/Claude Code实际调用。

主控可先修 Must1 并冻结新 SHA，补原23及自拟负例复验；后续接口工作只能在显式新媒体 opt-in、旧14defs不变、共享PG/认证/证据服务为权威、typed语义安全校验拒绝上述缺口的条件下实施。输出必须对最终 compact JSON 整体计算8000 tokens/1MiB，缓存缺失/损坏 not_configured、不隐式下载、不拆断事实引用或去掉未知；真实 producer与客户端链需另独立审查。上传/报告/订阅/插件仍按原R18范围继续，不被这次合同评审取消。

Verdict: **fix 1 first / needs_changes，仅 public 合同切片**。没有 lean 删除项。代码与允许接口条件、报告SHA、每个自有文件digest将在 `manifest.json` 封存；报告不自签 accepted。

报告首次写作时间与封存时间：由 manifest.json 的 `report_first_written_at` / `sealed_at` 记录，均使用 +08:00。
