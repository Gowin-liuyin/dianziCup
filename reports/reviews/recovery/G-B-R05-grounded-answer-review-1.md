# G-B / R05 引用生成核验内核独立初审

当前有限结论：2026-10-15T16:52:29+08:00，已在修复业务 `b1511145d4e6c15c5b1f6595bb7c776781ecf2ab` 独立定向复核，关闭下列 Must 1。允许该公开来源内核切片进入主控接线与有限 live 验证；整张 R05/T31/R12/G-B 未验收。原初审、红例和收据完整保留，复核详见文末附录。

本变更作用（What this change does）：将公开来源证据交给现有 `GenerationClient` 生成结构化论断，再用第二次独立调用核验论断支持关系。返回正文仅由已验证 claims 组成，引用元数据来自输入，失败保留实际调用 attempts。

任务状态：本切片建议 `needs_changes`，发现 1 个 Must fix。没有验收整张 R05、T31、R12 或 G-B，没有改写 progress，也没有 push。独立审查者未参与作者实现。

审查记录：2026-10-15T16:34:31+08:00，Asia/Shanghai，秒级。业务固定 `c1804d0a38cd4e451b801f1ec88df9c3c47629e0`；起点 `afe490ce15e567bf916d2e7b970354ddff3e193e`；作者证据提交 `90f0c98d1ca576aed6d1f170b8c4a2070e7912a6` 只作范围与原命令参考，以下结果来自独立执行。

独立分支 `codex/r05-grounded-answer-independent-review-1`，clean worktree `C:/Users/yinha/.codex/worktrees/r05-grounded-answer-independent-review/dianzi`。测试 cwd 均为其 `backend`；锁定环境在 `D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/venv`，Python 3.12.13。实际 import origin 和 coverage 文件列表已核对只指向独立工作树，没有共享主仓 editable `.pth` 或双树覆盖。主仓及作者活跃目录的未提交业务修改均未触碰。

已读 AGENTS、00执行索引、11恢复主计划、12恢复任务卡中的 R05/R12、T31、03/04/05/06 合同、冻结 `public_api_v2.json` 的 AskRequest/QAAnswer/Citation、progress 与交接，以及 Ponytail 5.2 `ponytail-review/SKILL.md`。按当前任务授权，只写本报告与指定 runs 目录。没有读 vault、用户附件、holdout，没有真实产品模型调用或付费调用。

## Must fix

1. **[P1] 同一引用内另一主体的未知/否定误拒当前主体的直接事实**（`backend/src/ai_intel/answering/grounding.py:127–140`；调用路径 `generate_grounded_answer:200 → validate_citations`）。

   **职责与触发输入：**程序要防止从“不受影响”裁出“受影响”，因此检查原引用上下文。输入 evidence ID `00000000-0000-0000-0000-000000000001`、完整 quote `产品A已在1.2.3修复。产品B是否受影响未知。`，问题 `产品A的状态是什么？`；模型候选是 `source_fact`、text/selected quote 均为 `产品A已在1.2.3修复。`、support_ids 仅该 ID。候选是严格 JSON 数组与 UUID 字符串，经过真实 `GenerationClient` wire 解码和 `GeneratedAnswer.model_validate_json(strict=True)`，没有绕过生成器。

   **预期与实际：**预期继续第二次核验，在保留产品 B 完整上下文的前提下返回产品 A 的直接事实。实际 line 128 将整个原 quote 作为 `context_text`，line 132–134 发现产品 B 的“未知”就要求产品 A 也写未知，抛 `answer_uncertainty_lost`；仅 1 次 synthetic wire 调用、1 个 succeeded attempt，核验调用未发生。四个独立输入全部复现同根因：

   | 完整来源 | 所选 quote / claim | 实际错误 |
   |---|---|---|
   | 产品A已在1.2.3修复。产品B是否受影响未知。 | 产品A已在1.2.3修复。 | answer_uncertainty_lost |
   | 产品A已在1.2.3修复。产品B不受影响。 | 产品A已在1.2.3修复。 | answer_negation_lost |
   | 产品A受影响。产品B不受影响。 | 产品A受影响。 | answer_negation_lost |
   | 产品A不受影响。产品B是否受影响未知。 | 产品A不受影响。 | answer_uncertainty_lost |

   **影响：**包含多个产品、分支或不同状态的公告会拒绝有直接支持的正常回答，且无法由正确的第二核验结果挽回。作者报告已披露长片段保守词表局限，但当前允许的公开来源问答自然包含多个主体，实际范围已经跨过该局限；不能将正常任务拒绝计为安全成功。独立探针另有“不同支持 ID 的两个主体各自生成 claim”正常对照通过，问题集中在完整引用内的状态泛化。

   **最小修复与复验：**将本地否定/未知约束绑定到所选引文在原文中的相关主体、范围及定位上下文；无法证明同一命题时，不把整段任意词命中无条件传播到当前 claim。继续把完整证据交给独立核验，保留同主体/同范围的未知、否定、限定条件和冲突。不能通过删掉产品 B 的未知，或仅检查所选子串而失去“不受影响→受影响”防护来修复。复跑本报告四个正常输入与作者全部否定/未知攻击配对；同主体删否定、未确认变肯定仍须拒绝。

   **精确复现：**[独立探针](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/test_independent_grounded_probes.py) 的 `test_unrelated_subject_state_does_not_block_direct_fact`，[UTF-8 失败日志](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/independent_probes_utf8.log)，[JUnit](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/independent_probes_utf8.xml)，[输入、调用数与错误码快照](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/review_summary.json)。原始 4 failed / 24 passed 保留，没有修改期望、skip 或业务代码。

## 独立执行证据

下面数量来自 JUnit，不叠加为互不相交测试总数。每条具体 executable、args、cwd、开始/结束、exit、SHA 和独立环境路径均在 runs 中同名 `*.receipt.json`；使用 `run_command.ps1` 执行，coverage 每次有独立文件。

| 检查 | Asia/Shanghai 开始—结束 | exit | 实际结果 |
|---|---|---:|---|
| `uv sync --locked --python 3.12` | 16:25:21—16:25:31 | 0 | 独立 venv，68 包；跨盘 hardlink 回退 copy 警告，锁未改 |
| 内核 unit + contract | 16:25:59—16:26:06 | 0 | 99 passed：77 unit、22 contract |
| 作者明确 security 子集 | 16:28:59—16:29:01 | 0 | 23 passed、54 deselected；不是全系统 security |
| 共享 HTTP/transport security | 16:25:59—16:26:04 | 0 | 24 passed，与上行不同范围 |
| 生成客户端相关回归 | 16:28:59—16:29:07 | 0 | 142 passed：111 unit、24 contract、7 本机 socket；不能整体称 T18 live |
| 完整 unit，原 coverage 门 60 | 16:27:52—16:28:32 | 0 | 763 passed、1 warning；3707/5627 = **65.87879864936912%**，无重复源树 |
| 全部 contract | 16:30:11—16:30:26 | 1 | 207 passed、1 error、1 warning；T07 PG 未覆盖，0 skip |
| 新增独立输入探针 | 16:28:59—16:29:01 | 1 | 24 passed、4 failed，同根因 Must 1；0 skip |
| mypy 全源码 | 16:30:11—16:30:12 | 0 | 75 source files，无问题 |
| Ruff / format 五文件 | 16:30:12—16:30:12 | 0 / 0 | All checks passed / 5 files already formatted |

实际 Python executable 为 `D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/venv/Scripts/python.exe`。主要参数如下，cwd 为上述独立 `backend`，JUnit 与 JSON 输出见同名收据；未用 `--no-cov` 的完整 unit 保留 pyproject 默认 `--cov=ai_intel --cov-fail-under=60`。

```text
-m pytest tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py --no-cov -q --junitxml=.../grounded_99.xml
-m pytest tests/unit/test_r05_grounded_answer.py -k security --no-cov -q --junitxml=.../answer_security_23.xml
-m pytest tests/security/test_r05_http_post.py tests/security/test_r05_transport_timeouts.py --no-cov -q --junitxml=.../shared_security.xml
-m pytest tests/unit/test_r05_generation.py tests/unit/test_r05_generation_review_fixes.py tests/contract/test_t18_model_clients.py tests/contract/test_r05_generation_wire.py tests/integration/test_r05_generation_http.py --no-cov -q --junitxml=.../client_regression_142.xml
-m pytest tests/unit -q --cov-report=json:.../unit_coverage.json --junitxml=.../full_unit.xml
-m pytest tests/contract --no-cov -q --tb=short --junitxml=.../all_contract.xml
-m pytest D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/test_independent_grounded_probes.py --no-cov -q --tb=short --junitxml=.../independent_probes_utf8.xml
-m mypy src
-m ruff check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
-m ruff format --check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
```

上面 `...` 仅为显示长度省略，执行命令没有省略；逐项完整参数保存于收据。完整 unit 的既有 Starlette/httpx deprecation warning 未修依赖或忽略规则。contract 唯一 error 是 `test_t07_jobs_outbox.py::test_transient_failure_parks_in_retry_wait_then_retries_exactly_once` 的 fixture：`blocked: DIANZI_TEST_RUN_ID must be a lowercase test identifier`，未建立真实 PG 连接；环境缺失不是业务断言失败，仍记录 exit 1 / error，未改为 skip。最小补充资源是按项目隔离规则批准的 test run ID 与 PG 环境，留给主控。

首次新增探针 stdout 使用 Windows 默认编码，中文显示乱码；真实 XML 和测试结果有效，原日志保留。仅给本审查 runner 设置 UTF-8 后重跑，业务无改动，四个失败相同；以 `independent_probes_utf8` 为可读复现证据。

## CBM、源码与调用流交叉

官方 portable CLI `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 实际版本 0.11.0。初次仅设置 `XDG_CACHE_HOME` 没有产生独立缓存目录，故该轮 index 不作为隔离索引证据；原日志保留。随后明确设置 `CBM_CACHE_DIR=/tmp/dianzi-r05-grounded-independent-cache-20261015` 重新执行 help、index/schema/trace，各步 exit 0，独立目录实际出现该项目 `.db`，采用 `*_dedicated.log` 和同名 receipt。

仅索引固定 WT 的 `backend/src`，`--mode full --persistence false --name r05-grounded-independent-review-20261015`。992 nodes、4687 edges；未索引、skip、parse partial/unusable 均 0；12 个 `__pycache__` 目录被排除。没有索引报告、密钥、附件或 holdout。实际 schema 有 Class/Function/Method/CALLS/IMPORTS 等；trace `generate_grounded_answer` 得 36 个 transitive callees、0 个生产 callers；trace `validate_citations` 数据流确认入参是 `generated_result.value,evidence`。

源码与 `rg` 二次确认：五文件差异仅 `answering/__init__.py`、`contracts.py`、`grounding.py` 和直接 unit/contract。真实数据流是严格客户端 JSON → GeneratedAnswer → 引用/本地校验 → SupportVerification → 全编号核验 → claims formatter → GroundedAnswerDraft。没有新网络网关、工具执行入口、自由 answer_text/limitations 入口或 API 接线。CBM 不是业务正确性的替代证明。

## 已验证边界与剩余缺测

确定通过的行为包括：OpenAI 与 Anthropic 两种实际 wire 的 JSON list / UUID 字符串可接收；嵌套额外字段拒绝；单行引文完整保留字符，八类分隔符与 CRLF/Unicode 规范化伪引文拒绝；支持 ID、重复证据与 verdict 全覆盖检查；数字/版本的部分匹配攻击拒绝；rule_result 显式不可用；无证据零模型调用；建议经独立核验并与事实分开；模型失败和 deadline 后失败保留 attempts；禁止格式修复第三次调用；恶意问题/来源仅在不可信数据里，未进入可信 system 或固定 limitations。没有确定复现的未验自由正文泄漏。

权限声明准确限于公开来源调用合同：CitationProjection 本身不携带 ACL/tenant/epoch，内核没有能力验证公开可见性或授权变化；调用前后鉴权、公开过滤、版本有效性与 epoch 回查必须由主控调用者实现。当前没有该调用者，故全链路权限与私有出境均 `not_run`，不能把内核 unit 计为权限验收。

本地扫描有上限：20 evidence、20 claim、64 KiB 输入文本；字典和 set 去重直接实现，无新依赖、共享状态或无界集合。按本切片最多 20 个片段与两次模型调用判断负载，没有发现必须新增抽象的复杂度问题；真实多用户并发吞吐和首字/完整延迟尚 `not_run`。65 秒检查点和每次 client ≤30 秒有源代码/离线测试依据，没有本切片真实模型 wall-clock 或 ≤5 秒性能证明。

**确定缺测：**问答 PG/API/检索/UI/e2e 尚未接线；T31-C02/C06、多轮、多跳、资产、规则、历史/撤回、跨租户最终范围仍归主控/R12；产品 live 与人工金标均 not_run。作者/本审查产品 provider 调用 0，费用 unknown；7 本机 socket 测试不是产品 live。

**未升级为确定缺陷的推测：**第二次同模型核验可能误判语义或受到数据指令影响；无人工金标与真实模型配对样本，不能宣称其准确率、证明事实真实或把模型 verdict 当人工真值。本地数字词法与状态词表也不是所有自然语言的完整判断器；仅把已复现的正常误拒列 Must，未以假定模型错误制造其他 Must。

F3/R1 的有限证据是结构化论断、支持关系接口、源修订/位置/URI 保留与安全失败边界；Must 1 阻断当前切片正常事实通过。P3 无真实性能、多跳或人工正确率证据。原计划、公共 schema、依赖锁、阈值、分母和最终验收范围均未变。

Verdict: fix 1 first. 本轮封存后停止；建议原作者只修同根因和直接回归，冻结新 SHA，再由本非作者定向复核。通过定向复核后，仍需主控产品 live、PG/API/UI 与完整 R05/R12 验收。

## 定向复核附录 · scope_recheck_1

记录时间：2026-10-15T16:52:29+08:00，Asia/Shanghai。主控明确授权复核修复业务 SHA `b1511145d4e6c15c5b1f6595bb7c776781ecf2ab`（父 `90f0c98d1ca576aed6d1f170b8c4a2070e7912a6`），作者证据 `a0fc736576e9cf0c4f0534bc6c060703f75ec121` 仅供定位，作者通过数量不作为本次结论。

沿用独立 clean worktree，分支改为 `codex/r05-grounded-answer-independent-review-scope-1`；源码 HEAD 实际为 b151，git status 为空。仍用该 WT 的独立 editable venv，未修改业务、schema、锁、progress、金标、分母或 skip，未 push。新增复核文件全部在原 runs 下 `scope_recheck_1/`；初审 c180 的四个红例日志/JUnit 和 sealed 文件不覆盖。

### Must 1 关闭依据与测试改动判断

修复仅改变 `grounding.py` 及直接 unit：`validate_citations:136` 将本地词法拒绝限定为 `_same_proposition_except_state:149–161` 判断去掉状态标记后完整文字相同的命题。额外主体、谓词、条件、句子或时间导致完整命题不同，就继续第二模型核验；此函数不更改引用原文或 exact 子串检查。所有原始证据仍发送，第二核验逐 claim 完整覆盖、失败不能被覆盖或再调用。prompt 升为 `r05-grounded-answer-2`，schema 未变，核验提示明确同一主体、谓词、适用范围与时间。

原四个正常误拒输入未经改写，均从原 c180 的 1-call failure 变为 b151 的 2-call verified draft，原独立 28 项全部通过。额外独立 19 项确认：

- 同主体 `未确认受影响→受影响`、`不受影响→受影响`、`受影响→不受影响`、`未观察到利用→观察到利用`、英文 `not affected→affected` 仍在第一调用后拒绝，保留 1 attempt。
- 原样来源“未知/不受影响/未观察到利用”可以保留状态并返回；不同主体、开启/关闭配置、2025/2026 时点的明确局部事实能到核验，核验仍收到完整原文。
- 非字面同命题、跨主体错归因、删条件、旧版与当前未知冲突，收到 `unsupported/unknown` 或 `states_preserved=False` 必须失败；2 attempts 保留，第三个候选不会被调用。跨支持 ID 的未选未知证据仍进入第二请求。
- 注入不能绕开第二核验、修改 system 或增加调用；原 28 项继续覆盖数字/版本、Unicode/跨行、自由正文和 rule_result 拒绝。新 prompt/verify 版本逐 attempt 记录，费用保持 unknown。

作者将原六项状态攻击中的两项（`修复版本未知。→已完成修复。`、`No evidence of exploitation.→Exploitation has occurred.`）改为第二次 `unsupported` 路径。核对 diff 后确认原来源、selected quote、claim 和最终拒绝未改变，新增的是明确的 synthetic verdict、2 calls/2 attempts 断言；没有删难题或降为 skip。该改动符合收窄本地词法范围后的语义核验分工，本审查另用独立输入再次验证最终拒绝。

这两条测试现在只能证明服务遵守否定核验结果，不能证明真实模型会给出正确 verdict。修复后的本地状态检查覆盖范围确实更窄，复杂状态与 scope 依赖独立模型辅助核验；没有以字面相等断言自然语言实体/范围已经被程序完全解析。此边界必须在主控真实模型配对与人工支持抽查中继续验证，不能把 synthetic 模型输出当人工金标。本次没有发现绕过现有必经校验路径的新确定缺陷。

### 实际定向检查与剩余验证

cwd 仍为独立 WT `backend`。执行脚本为 `scope_recheck_1/run_command.ps1`，完整 executable/args、cwd、秒级时间、exit、代码 SHA 和独立环境路径在同名 receipt；所有执行 exit 0。

| 检查 | 2026-10-15 UTC+08:00 开始—结束 | 实际结果 |
|---|---|---|
| 原独立 28 + 新独立 19 | 16:50:52—16:50:55 | **47 passed**，0 fail/error/skip；[JUnit](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/scope_recheck_1/independent_scope.xml) |
| 内核 unit + contract | 16:50:52—16:50:58 | **113 passed**（91 unit + 22 contract）；模块 201/208 = **96.63461538461539%**，仍保留 60 门；[coverage](D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/scope_recheck_1/answering_coverage.json) |
| 答案安全子集 | 16:50:52—16:50:55 | **29 passed / 62 deselected**；不是全系统安全验收 |
| mypy 全源码 | 16:50:55—16:50:56 | 75 source files，通过 |
| Ruff / format 五文件 | 16:50:56—16:50:56 | 通过 / 5 files already formatted |
| 源码差异 whitespace / clean WT | 16:52:29 检查 | `git diff --check` 0，status 为空，固定 b151 |

主要命令参数如下，所有完整参数（含绝对 XML 路径）已保留在 receipt；Python 为原独立 venv 的 `Scripts/python.exe`。

```text
-m pytest D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/test_independent_grounded_probes.py D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/scope_recheck_1/test_independent_scope_recheck.py --no-cov -q --tb=short --junitxml=.../scope_recheck_1/independent_scope.xml
-m pytest tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py --cov-reset --cov=ai_intel.answering --cov-report=json:.../scope_recheck_1/answering_coverage.json -q --junitxml=.../scope_recheck_1/grounded_scope.xml
-m pytest tests/unit/test_r05_grounded_answer.py -k security --no-cov -q --junitxml=.../scope_recheck_1/answer_security_scope.xml
-m mypy src
-m ruff check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
-m ruff format --check src/ai_intel/answering tests/unit/test_r05_grounded_answer.py tests/contract/test_r05_grounded_answer_contract.py
```

按主控“定向复核、不复跑无新影响的整仓测试”指令，本轮没有再跑完整 unit、全部 contract、142 个未改客户端回归或 T07 PG。作者的 777/65.92%、142、live 数量不转为独立复核结论；初审 c180 的完整 unit 763/65.88% 与 T07 error 保持其原 SHA 和范围，不冒称 b151 的整仓验证。

CBM 0.11.0 在相同已核实独立 `CBM_CACHE_DIR` 下，以新项目 `r05-grounded-scope-recheck-b151-20261015` 重新仅索引 b151 WT `backend/src`，994 nodes、4691 edges，未索引/skip/parse partial/unusable 均 0；实际 schema 和 trace 原始日志在 `scope_recheck_1/cbm_*.log`。源码/rg 与 trace 交叉确认新 helper 只被引用检查调用，核心仍必经第二客户端与 `validate_support_verdicts`，无新增产品调用方。没有索引原报告或秘密材料。

**有限结论：Must 1 在 b151 关闭，此公开来源回答内核 scope 修复可以交主控集成并有限 live。** 本轮 unit/contract/security 的通过范围如表；问答 API/PG/检索/UI/e2e、调用前后权限/epoch、真实模型 wall-clock、人工支持真值仍 not_run；不签整项 R05、T31、R12 或 G-B，不将两个模型的一致意见计为正确率。下一步由主控完成这些链路与配对真值验证，本审查封存后停止。
