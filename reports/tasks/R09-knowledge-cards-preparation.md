# R09 · 公开知识卡准备切片

记录时间：2026-10-16T01:46:58.797852+08:00。本切片 `awaiting_review`，实现 `complete`
限于内部候选抽取边界；整 R09 仍是未完成的工作包，不能据此验收整
R09/T09/T14/T15/T22。

## 输入输出与范围

本地分支 `codex/r09-knowledge-cards`，原始基线
`349c5e3ec27196257b98cdfcb63c75fb50157978`；主控授权引入公共合同 `c5d9080d6a0494a01b1fe26086220365deca7583`（对应 root
`f62466ff3282c872336288fc42e600e4e2dcc84a`，其中 R11
依赖/锁文件属于主控既有提交）。本实现代码冻结 `02bea007dec5046458c7f2f1c969f0080ef03889`，7
个代码/测试文件，1089 additions / 7 deletions。原主控工作树未提交修改没有修改。

输入复用 `DocumentReadService.document_detail` 已按 ACL 筛选的公开 `DocumentDetailResponse`、现有
`AccessScope` 与 `GenerationClient`。此 DTO 的证据是保存的来源 span，不保证每个 span
覆盖整块/全文；本片没有提供读取任意
URL/SQL/shell 的产品能力，也没有接 tenant 资料外发。调用方应明确选取 <=50 个已验证
span；不得悄悄截断默认 100 项资料页。

输出 `KnowledgeCardDraft` 是待审内部值对象，不是第二套业务存储。论文固定 8
字段：机制、攻击者控制、输入路径、模型/任务、工具权限、作者环境、结论、限制；标准/政策
固定 9 个公共字段加各自推荐/义务字段。每个字段绑定 document/revision/原文
revision number；每个有值候选附 evidence/block、全局 Unicode 左闭右开坐标、原文
quote、quote SHA-256、来源 span
SHA-256 和页面/JSON 定位。span hash 不冒充完整 block/raw-document
hash；原文版本回查仍由既有 PG 完成。

所有值为 `model_hypothesis`，有引用仍为
`candidate`、`semantic_support=unverified`、`confirmation_status=a
waiting_review`、`verification_level=unknown`。缺失字段为 unknown；同字段不同值并列
conflict。摘要与 clause_text
分开，clause_text 必须原样回切引用；标准推荐字段不能放入 policy
卡，法规义务字段不能放入 standard 卡。source
日期精度、草案/正式、发布时间/生效候选独立；不进行法律裁决或资产研判。单次共享客户端、
严格嵌套 schema、无格式重试/模板回退；错误保留真实 attempt 元数据并只暴露固定错误码。

## 改动文件与复用

- `backend/src/ai_intel/enrichment/knowledge_cards.py`
- `backend/src/ai_intel/enrichment/card_extraction.py`
- `backend/tests/r09_card_fixtures.py`
- `backend/tests/unit/test_r09_knowledge_cards.py`
- `backend/tests/contract/test_r09_knowledge_card_contract.py`
- `backend/tests/security/test_r09_card_boundaries.py`
- `backend/tests/contract/test_t22_research_and_document_links.py`

重用 `DocumentDetailResponse`/`EvidenceResponse`/`AccessScope`、HTML
parser、`TextBlock`、`locate_evidence_span`、`GenerationClient.generate`、`AttemptMetadata`、受控
gateway 与既有 T22 六例。不修改 research_links、公共
DTO/domain/schema、PG/migrations、设置、worker、API、frontend 或 progress；不自建
repository、缓存、规则结果或模型接口。唯一新业务模块 `card_extraction.py`；fixture
helper 为三层直接测试共享合成输入。

## 语义修复与历史失败

按 [主控 CR-R09](../../docs/decisions/CR-R09_verification_labels.md)，`verification_label(False,Fa
lse)` 改为 unknown，其余布尔语义和 PaperCard/PolicyCard 构造保持。旧 T22-C01…C06
没有减少，仅 C06 错误期待纠正；其业务 red
`label_red_utf8` 为 1 failed / 5 deselected，原错误返回 rule_inferred_for_asset
清晰留存。这不是金标、阈值或计分分母调整。

`extraction_red` 是模块尚未实现的 collection
error，不是环境缺失，也不计业务测试数量。首次 `unit_first` 为 38 passed / 1
failed，测试把既有网关 401 错误码误写为 model_authorization_failed；依据现行
`classify_http_failure` 改正为
model_permanent_auth_error，未改错误实现。`style_first` 8
个长行后格式修正；`mypy_final` 2 个定长元组赋值错误后加
`tuple[str,...]` 显式类型，`mypy_recheck` 0 issues。原日志全部保留。最早 `label_red`
的日志工具打印遇 GBK
UnicodeEncodeError；child exit=1 已写回执，后续显式 UTF-8 重跑 `label_red_utf8`，没有覆盖该原记录。

## 真实检查结果

| 验证层 | 结果 | 实际范围 |
|---|---|---|
| unit | passed | 268 tests, 0 fail/error/skip; R09 38 + shared regressions |
| contract | passed | 76 tests, 0 fail/error/skip; R09 10 + original contract regressions |
| security | passed | 36 tests, 0 fail/error/skip; R09 12 + shared boundaries |
| integration | not_run | 本片没有 PG/worker 接线，未启动隔离服务 |
| frontend | not_run | 未改前端 |
| e2e | not_run | 没有 R09 产品完整链 |
| live | not_run | 0 外部请求、0 真实模型调用、0 真实机制案例 |
| manual | not_run | 0 人工金标/复现/条款适用性裁决 |

三层相关回归共 380 项；最终代码版本 focused 再检 66 passed（60 个新增 fixture tests +
旧 T22 六例），0
fail/error/skip。`--no-cov`
仅用于限定范围回归，没有产生覆盖率或正式性能/准确率声明，配置与阈值未修改。Ruff/format
（7 文件）、mypy（2
source 文件）、git diff --check 均 exit 0。既有 repo secret scanner exit 0，既有 findings
全保留且分类表未改；没有注入凭据，exact_scan=not_run。所有 pytest 和工具运行复用现有
D:/dianzi/backend/.venv/Scripts/python.exe，PYTHONPATH 指向本独立 WT
src/tests，未安装/下载模型或新依赖。

完整命令、cwd、+08 开始/结束和 child 退出码位于各 `.command.json`，JUnit 为同名
`.xml`。原命令参数在回执中逐项保存，没有凭据或原文秘密。

材料脚本检查也保留真实失败：首次 material_style 为 17 个长行，
按 code point 包行后 material_style_recheck 仍有 33 个显示宽度超限；
根因为 Ruff 按中文显示宽度计数，修正材料文字包行后
material_style_width_recheck 与 material_format_check 均 exit 0。
没有修改业务代码或放宽规则，代码冻结断言和材料哈希自检真实执行通过。

| 检查 | 实际 +08 时钟 | child exit | 日志 |
|---|---|---|---|
| `label_red_utf8` | 2026-10-16T01:31:09.654047+08:00 → 2026-10-16T01:31:11.190423+08:00 | 1 | [label_red_utf8.log](../runs/recovery_r09_knowledge_cards_20261016/label_red_utf8.log) |
| `extraction_red` | 2026-10-16T01:30:53.709750+08:00 → 2026-10-16T01:30:55.493804+08:00 | 2 | [extraction_red.log](../runs/recovery_r09_knowledge_cards_20261016/extraction_red.log) |
| `unit_first` | 2026-10-16T01:33:08.941916+08:00 → 2026-10-16T01:33:11.351651+08:00 | 1 | [unit_first.log](../runs/recovery_r09_knowledge_cards_20261016/unit_first.log) |
| `focused_first` | 2026-10-16T01:35:00.881208+08:00 → 2026-10-16T01:35:03.523685+08:00 | 0 | [focused_first.log](../runs/recovery_r09_knowledge_cards_20261016/focused_first.log) |
| `style_first` | 2026-10-16T01:35:00.933393+08:00 → 2026-10-16T01:35:01.196492+08:00 | 1 | [style_first.log](../runs/recovery_r09_knowledge_cards_20261016/style_first.log) |
| `format_apply` | 2026-10-16T01:35:34.866919+08:00 → 2026-10-16T01:35:35.049319+08:00 | 0 | [format_apply.log](../runs/recovery_r09_knowledge_cards_20261016/format_apply.log) |
| `format_apply2` | 2026-10-16T01:36:13.553301+08:00 → 2026-10-16T01:36:13.712006+08:00 | 0 | [format_apply2.log](../runs/recovery_r09_knowledge_cards_20261016/format_apply2.log) |
| `unit_final` | 2026-10-16T01:37:35.271825+08:00 → 2026-10-16T01:37:43.297540+08:00 | 0 | [unit_final.log](../runs/recovery_r09_knowledge_cards_20261016/unit_final.log) |
| `contract_final` | 2026-10-16T01:37:35.209684+08:00 → 2026-10-16T01:37:40.030657+08:00 | 0 | [contract_final.log](../runs/recovery_r09_knowledge_cards_20261016/contract_final.log) |
| `security_final` | 2026-10-16T01:37:35.435566+08:00 → 2026-10-16T01:37:38.896000+08:00 | 0 | [security_final.log](../runs/recovery_r09_knowledge_cards_20261016/security_final.log) |
| `style_final` | 2026-10-16T01:37:35.479678+08:00 → 2026-10-16T01:37:35.766762+08:00 | 0 | [style_final.log](../runs/recovery_r09_knowledge_cards_20261016/style_final.log) |
| `format_final` | 2026-10-16T01:37:56.761122+08:00 → 2026-10-16T01:37:56.951782+08:00 | 0 | [format_final.log](../runs/recovery_r09_knowledge_cards_20261016/format_final.log) |
| `mypy_first` | 2026-10-16T01:35:00.880195+08:00 → 2026-10-16T01:35:03.037065+08:00 | 0 | [mypy_first.log](../runs/recovery_r09_knowledge_cards_20261016/mypy_first.log) |
| `mypy_final` | 2026-10-16T01:37:57.148096+08:00 → 2026-10-16T01:37:57.853483+08:00 | 1 | [mypy_final.log](../runs/recovery_r09_knowledge_cards_20261016/mypy_final.log) |
| `mypy_recheck` | 2026-10-16T01:38:23.204254+08:00 → 2026-10-16T01:38:23.873809+08:00 | 0 | [mypy_recheck.log](../runs/recovery_r09_knowledge_cards_20261016/mypy_recheck.log) |
| `style_freeze` | 2026-10-16T01:39:45.048648+08:00 → 2026-10-16T01:39:45.226113+08:00 | 0 | [style_freeze.log](../runs/recovery_r09_knowledge_cards_20261016/style_freeze.log) |
| `format_freeze` | 2026-10-16T01:39:45.370916+08:00 → 2026-10-16T01:39:45.541769+08:00 | 0 | [format_freeze.log](../runs/recovery_r09_knowledge_cards_20261016/format_freeze.log) |
| `focused_freeze` | 2026-10-16T01:39:32.596649+08:00 → 2026-10-16T01:39:35.029801+08:00 | 0 | [focused_freeze.log](../runs/recovery_r09_knowledge_cards_20261016/focused_freeze.log) |
| `secret_scan` | 2026-10-16T01:39:10.666005+08:00 → 2026-10-16T01:39:32.467108+08:00 | 0 | [secret_scan.log](../runs/recovery_r09_knowledge_cards_20261016/secret_scan.log) |
| `code_diff_check` | 2026-10-16T01:40:15.228104+08:00 → 2026-10-16T01:40:15.295795+08:00 | 0 | [code_diff_check.log](../runs/recovery_r09_knowledge_cards_20261016/code_diff_check.log) |
| `cbm_help` | 2026-10-16T01:37:56.817226+08:00 → 2026-10-16T01:37:57.048550+08:00 | 0 | [cbm_help.log](../runs/recovery_r09_knowledge_cards_20261016/cbm_help.log) |
| `cbm_refresh_frozen` | 2026-10-16T01:43:14.796181+08:00 → 2026-10-16T01:43:19.891576+08:00 | 0 | [cbm_refresh_frozen.log](../runs/recovery_r09_knowledge_cards_20261016/cbm_refresh_frozen.log) |
| `cbm_schema_frozen` | 2026-10-16T01:43:20.000063+08:00 → 2026-10-16T01:43:22.987409+08:00 | 0 | [cbm_schema_frozen.log](../runs/recovery_r09_knowledge_cards_20261016/cbm_schema_frozen.log) |
| `cbm_trace_frozen` | 2026-10-16T01:43:23.106407+08:00 → 2026-10-16T01:43:26.100150+08:00 | 0 | [cbm_trace_frozen.log](../runs/recovery_r09_knowledge_cards_20261016/cbm_trace_frozen.log) |
| `rg_callers` | 2026-10-16T01:38:45.301382+08:00 → 2026-10-16T01:38:45.370386+08:00 | 0 | [rg_callers.log](../runs/recovery_r09_knowledge_cards_20261016/rg_callers.log) |
| `material_compile` | 2026-10-16T01:43:14.786135+08:00 → 2026-10-16T01:43:14.920000+08:00 | 0 | [material_compile.log](../runs/recovery_r09_knowledge_cards_20261016/material_compile.log) |
| `material_style` | 2026-10-16T01:44:31.563562+08:00 → 2026-10-16T01:44:31.717529+08:00 | 1 | [material_style.log](../runs/recovery_r09_knowledge_cards_20261016/material_style.log) |
| `material_format_apply` | 2026-10-16T01:45:17.799929+08:00 → 2026-10-16T01:45:17.974949+08:00 | 0 | [material_format_apply.log](../runs/recovery_r09_knowledge_cards_20261016/material_format_apply.log) |
| `material_style_recheck` | 2026-10-16T01:45:18.111787+08:00 → 2026-10-16T01:45:18.282417+08:00 | 1 | [material_style_recheck.log](../runs/recovery_r09_knowledge_cards_20261016/material_style_recheck.log) |
| `material_style_width_recheck` | 2026-10-16T01:46:10.402182+08:00 → 2026-10-16T01:46:10.538640+08:00 | 0 | [material_style_width_recheck.log](../runs/recovery_r09_knowledge_cards_20261016/material_style_width_recheck.log) |
| `material_format_check` | 2026-10-16T01:46:10.644967+08:00 → 2026-10-16T01:46:10.780681+08:00 | 0 | [material_format_check.log](../runs/recovery_r09_knowledge_cards_20261016/material_format_check.log) |

## CBM、调用方与精确冻结

开工先以真实 portable help/schema 索引现有 src：基线 1292 nodes / 6424 edges。`verification_label`
没有生产调用，rg 补查仅旧 T22；`GenerationClient.generate` 既有调用为 grounding →
question service。本轮冻结后再次
fast 索引/trace，参数和原始输出已保存。CBM 默认配置排除
assets/缓存目录，不能声称是全仓无遗漏图；本片调用方使用 rg 全 src/tests
核对。新的抽取入口没有生产调用者，只有直接测试。

精确 diff：[code_diff.log](../runs/recovery_r09_knowledge_cards_20261016/code_diff.log)；代码文件
worktree 与 Git blob
SHA-256：[code_freeze_receipt.json](../runs/recovery_r09_knowledge_cards_20261016/code_freeze_receipt.json)。整个材料
清单为同目录 `artifact_manifest.json`，其本体 SHA-256 在
`artifact_manifest.sha256`；清单不包含自身与
sidecar，防止循环 hash。材料提交 SHA 在交接中另列。

## 评分证据、偏差与后续

F2：具备带固定原文位置的论文前提候选和标准/政策字段边界；F3/R1：原文/摘要、日期、历史
revision 与缺失/冲突保留、输入注入隔离。这些只证明 fixture
合同实现，不证明三类真实非 CVE 案例或完整问答质量/来源接通。R09
六验收中的原文定位/历史/推荐义务分离/未知边界已有 fixture
证据；真实三类资料、文献语义关系、正确时点问答仍未验收。research_links 原强关联语义与
T22 原案例继续保留，新的关系确认由主控后续切片审查，不以任意非空引文升级。

与授权计划一致：R07 产品发布前置尚待主控接线，本片是安全独立准备，不把 R07 或整 R09
live 改为通过。下一步由全新非作者 reviewer 核对
`02bea007dec5046458c7f2f1c969f0080ef03889`/主控 CR 实际落实、复跑三层测试；随后主控接 PG
候选/审核账本、文献关系与检索/API/界面、官方原文三机制目录和真实模型预算门。模型候选必
须经过单独语义支持/审核才可发布，仍不可自动成为团队复现或当前资产规则。

未检查 integration/frontend/e2e/live/manual；核心风险是本入口尚无生产接线，现有公开投
影不能用于 tenant 内容外发或完整原文缺失结论。
