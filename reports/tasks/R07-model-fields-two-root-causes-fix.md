# G-C / R07 · 四维模型候选两项根因修复

记录时间：2026-10-16T01:32:46+08:00（实际上海时间）。任务状态：`awaiting_review`；本修复切片实现 `complete`，整 R07、原 T19/T20/T22/T23 和 G-C 未被本报告验收。

本轮是实现者修复，不是独立评审。输入为既有真实 `GenerationClient`、服务选定的修订/块与来源版本；输出仍为固定 `ModelFieldResult` 四维尝试和 `MODEL_HYPOTHESIS` / `PENDING` 候选。无公共类型、schema、迁移、配置、依赖、worker、API、公共状态、金标、阈值或分母改动，无 push。没有读取真实凭据、发出外部请求、访问资产或执行 PoC。

## 固定身份、授权和范围

| 项目 | 固定值 |
|---|---|
| 原作者材料 | `6199ad193d36da17c6597ee286aae40af887d425` |
| 原作者代码 | `6463e62bd0504e6cf83fd84b6d64c8bbfd33f994` |
| 本轮代码提交 | `696b1d88045ee862db1af3aaf569574ad361feaf`，2026-10-16T01:29:51+08:00 |
| 独立工作树 / 分支 | `D:/wt/r07-model-fields-two-root-causes-fix` / `codex/r07-model-fields-two-root-causes-fix` |
| 原独立意见 | `D:/wt/r07-model-fields-review-1/reports/reviews/recovery/G-C-R07-model-fields-review-1.md`，两项 Must / needs_changes |
| 本轮运行材料 | `reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/` |
| 运行解释器 | 既有 `D:/dianzi/backend/.venv/Scripts/python.exe`，未安装依赖 |
| 本轮进口路径 | `PYTHONPATH=D:/wt/r07-model-fields-two-root-causes-fix/backend/src` |

先读仓库 AGENTS、执行图、R07 恢复卡、原 T19/T20/T22/T23、03/04/07 合同、CR-R07 候选接口及 typed v3 合同、固定 progress/handoff 和原评审；使用 Ponytail 5.2.0 full。主控目录存在用户/控制器未提交修改，均未触碰。固定快照的旧整 R07 pending 只是索引历史，不被用来否定已有候选实现，也不被改成 accepted。R02/R05/R06 的后续整卡或 live 状态不由本切片推断；所需内部候选/生成/来源输入接口确实存在，此次离线根因修复不依赖未授权外部资源。

开始前定义的回归是原评审浮动 taxonomy 两例和同块次行必要条件一例；先按字节复制原评审两个文件到新 run 并真实冻结红色结果，再改共享校验。原 reviewer 文件和断言没有修改。代码先提交，最终回归、静态检查和 CBM 均在该提交 SHA 上执行；`*_draft` 记录是提交前工作树试验，不能被当作提交 SHA 的通过证据。

## 实现与文件清单

| 文件 | 必要变化 |
|---|---|
| `backend/src/ai_intel/enrichment/field_sources.py` | `is_atlas_taxonomy` 同时供调用前门禁和返回候选核验使用：只允许 HTTPS 官方 `mitre/atlas-data` 的完整 40 位 commit 路径，`source_version` 必须与路径完全一致；仍要求 full_text / complete blocks。拒绝浮动、普通当前技术页、短 hash、错配 hash、非官方路径、query/fragment/userinfo/非标准端口。新增 `_require_version_qualifiers` 从实际证据坐标定位同块同段，要求完整显式必要条件及其换行续文包含在 `raw_expression` 的同一完整引用中。 |
| `backend/tests/unit/test_r07_model_fields.py` | 仅把原作者合成 ATLAS 正例的 URI / version 改为一致的合成完整 commit；原断言、case 和数目不变。原 `fixture-taxonomy-1` + 普通当前页无法证明上游不可变身份，不能保留为正例。`a` 重复 40 次明确是 unit synthetic 格式身份，不是已核实存在的官方提交。 |
| `backend/tests/unit/test_r07_model_field_root_causes.py` | 新增 46 个离线边界，含 17 个门禁拒绝、两种 commit URI 正例、输出 version 错配、前后条件/CRLF/续行/拆行关键词/多条件/中文、单独 limitation 或 quote 不足、完整原文保持 unknown/pending、段落隔离、第二必要条件漏掉，以及真实 codec + gateway 至 transport 的六种调用次数路径。 |
| 本报告和新 run | 保存原 red、draft、最终日志/JUnit、真实命令时间退出码、CBM、原材料审计、范围扫描及 manifest；原 run / manifest 未重写。 |
| `.gitattributes` | 只为本轮新材料的精确路径追加 raw `-text`；原始日志/XML 用精确路径 `-diff` 保留工具输出字节。源文件、业务测试的 whitespace 检查未放宽；原 73 件材料属性及内容未改。 |

复用现有严格 Pydantic 候选、块 hash/坐标、来源门禁、真实生成 codec、固定端点/网关、错误码、文献绑定和 PoC metadata；没有引入新算法、模型提供者、通用服务或依赖。两个根因都在共享来源层修复，四个 provider 使用同一路径。

浮动/缺失 taxonomy 仍返回 `atlas_taxonomy_missing`，不调用 ATLAS。其他三个维度可以继续。完整跨行表达式、条件和引文保持原文，版本比较仍 `unknown`，不会被升级为 supported；只给范围、把条件另放 limitation/quote 或漏掉后续条件则拒绝该候选，不删除有效兄弟维度。

ATLAS pin 校验是受信来源加载器所给 URI/版本的结构绑定，不证明下载真实性；未从 regex 推断某官方 release。当前只支持两个明确的 commit artifact URI 形状，普通 MITRE 当前页面及 release label 会安全保留缺口。真实官方版本加载/校验另需授权输入。条件检查限定同块同段的显式语词和续行；同段无关的明确条件可能保守拒绝，跨块、跨段或隐含语义仍需要后续语义/人工复核，不能称为完整语义支持验证。

## 原红与固定 SHA 验证

每个 `*.command.json` 记录实际 argv、cwd、+08 开始/结束、child exit、当时 source SHA 和 PYTHONPATH；wrapper 自身不转发 child exit，以下数字全部取 child receipt/JUnit，不把 wrapper exit 0 当作通过。全部 pytest 用 `-o addopts=` 做指定有界套件，未修改项目原 `--cov-fail-under=60`，没有 whole-project coverage 声明。

| 检查 | 实际结果 | 证据前缀 |
|---|---|---|
| 原评审 47 个复制探针，原 6199ad1 | exit 1；44 passed / 3 failed / 0 error / 0 skip | `frozen_red`，2026-10-16T01:25:40.882677+08:00 至 01:25:44.277511+08:00 |
| 同一 47 个文件，696b1d8 | exit 0；47 passed / 0 failed/error/skip | `frozen_green`，01:30:13.490917 至 01:30:16.148427+08:00 |
| 原指定回归，696b1d8 | exit 0；236 passed / 0 failed/error/skip | `regression_236`，01:30:13.497922 至 01:30:21.555990+08:00 |
| 新边界，696b1d8 | exit 0；46 passed / 0 failed/error/skip | `new_boundaries`，实际时间在 receipt |
| Ruff / format | exit 0 各；六个相关 source/test 文件 | `ruff` / `format` |
| mypy | exit 0；两个相关业务模块 | `mypy` |
| 业务/test diff check | exit 0；6199ad1 → 696b1d8 | `source_diff_check` |
| 首次新材料 diff check | exit 2；新 raw JSON 的 CRLF 被识别为行尾 whitespace；保留原失败原文，随后仅给精确证据路径声明 cr-at-eol | `package_diff_check`；最终复验见 `package_diff_check_final` |
| CBM help/schema/index/两条 fully qualified trace | exit 0 各；1326 nodes / 6623 edges，未索引/partial/unusable 均 0，persistence=false | `cbm_help` / `cbm_schema` / `cbm_index` / `cbm_trace` / `cbm_generation_trace` |
| `rg` 调用方交叉核对 | exit 0 | `rg_callers` |
| 原 73 件及原 reviewer 字节审计 | exit 0；73/73 author raw hash+size，26/73 原 Git blob 精确 hash，73/73 仅规范换行后相同；两个 reviewer 复制 SHA 与原文件完全相等 | `materials_audit` / `evidence_audit.json` |
| 本轮限定安全模式扫描 | exit 0；初次 80 个文件，0 findings；最终实际文件数见 `scope_secret_scan_final`；原模式未更改 | `scope_secret_scan` / `scope_secret_scan_final` |
| 新材料保存检查 | 真实结果见 `material_integrity.json`；逐文件 raw SHA、size 与 staged Git blob 核对 | `material_integrity.json` |

最终新增与回归是三组独立执行的 236 + 47 + 46 = 329 个通过用例，不是准确率/召回或评分分母。236 原回归包含本候选 56 unit / 4 contract / 16 security 和既有 160 项；原六项 T 卡测试存在于该有界回归，不等于整卡最终验收。

真实 child 命令要点（完整逐参 argv 和 JUnit 路径以各 receipt 为准）：

```text
cwd=D:/wt/r07-model-fields-two-root-causes-fix/backend
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -o addopts= -v tests/unit/test_r07_model_fields.py tests/contract/test_r07_model_field_contract.py tests/security/test_r07_model_field_security.py tests/unit/test_r07_enrichment_contracts.py tests/unit/test_t19_structured_enrichment.py tests/unit/test_r05_generation.py tests/unit/test_r05_generation_review_fixes.py tests/contract/test_t18_model_clients.py tests/contract/test_t20_claim_extraction.py tests/contract/test_t22_research_and_document_links.py tests/contract/test_t23_poc_scores_impact.py --junitxml=D:/wt/r07-model-fields-two-root-causes-fix/reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/regression_236.xml
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -o addopts= -v --import-mode=prepend D:/wt/r07-model-fields-two-root-causes-fix/reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/test_independent_model_fields.py D:/wt/r07-model-fields-two-root-causes-fix/reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/test_independent_boundary_extra.py --junitxml=D:/wt/r07-model-fields-two-root-causes-fix/reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/frozen_green.xml
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -o addopts= -v tests/unit/test_r07_model_field_root_causes.py --junitxml=D:/wt/r07-model-fields-two-root-causes-fix/reports/runs/recovery_r07_model_fields_two_root_causes_fix_20261016/new_boundaries.xml
```

红色失败正是原两项 Must 的三例。draft 试验保留，未发生新业务失败后改 skip、改金标或减少用例。所有最终自动测试 0 skip。原材料有 47/73 个 Git LF 与 author raw CRLF 差异，本轮只复核并诚实保留，不重写原 manifest，也没有用新 attributes 声称修复历史 Git 字节。

第一次材料封存因 `.gitattributes` 工作树旧 CRLF 与其 staged LF 不等而停止，未生成有效 manifest；随后将普通属性文件规范到其原 Git LF 格式，仅新增精确路径，raw JSON 原字节未改，并重做 staged byte 自检。该材料错误与业务测试无关，首个 exit 2 日志完整保留；不能把源码 exit 0 冒称首次全包也通过。

## 调用次数、调用方与限制

`GenerationClient.generate` 的 `max_calls=2` 循环只有 `model_format_invalid` 且 `request.allow_format_repair=True` 才继续；此入口一直显式 False。HTTP 401/429/503、网络失败和超时均不重试。`NetworkGateway.post_json` 使用 `max_redirect_hops=0`，transport 只对 `addresses[0]` 执行一次 POST，没有 IP 轮询或隐藏 retry。因此当前批准合同内不需公共 client/网关变更。

新增六例在真实 GenerationClient + NetworkGateway 下，只替换离线 resolver 和底层 transport，成功/格式坏/503/302/网络失败/超时各产生恰好四个 transport 调用和四个 AttemptMetadata；失败保留安全状态，没有 format repair 或 redirect 增加调用。原 reviewer 同时覆盖四 provider codec、token 预算与未知 fee。这里的 wire 是离线 codec/gateway 边界观察，真实外部付费 wire 为 0，不能算 live，费用始终 `unknown`。总输出预算仍按四维 floor 分配，已有超限检查保持。

官方 WSL 工具 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp` 独立只索引本 WT `backend/src`；缓存 `/tmp/dianzi-cbm-r07-model-fields-two-root-causes-fix-20261016` 在仓外，reports/holdout/秘密不在允许根。schema 后使用真实 qualified entry 与 GenerationClient trace：前者 source callers 0，后者连至 `_generate_field`、gateway 等既有路径；`rg` 证实本固定快照 entry 只有本切片测试调用。ATLAS 门禁/候选验证共享一处，新条件 helper 已出现在 trace。不能据此推断主控尚未冻结的 worker/API 当前消费者；后续接线方必须提供固定来源 commit 对及完整必要条件原文，无默认版本或候选发布权变化。

## 验证层、评分证据和交接

| 层 | 本轮结果 |
|---|---|
| unit | passed，仅上述自动离线边界/回归 |
| contract | passed，仅指定离线候选/原合同回归 |
| security | passed，仅指定离线权限/注入/PoC/预算边界，范围扫描另列 |
| integration / frontend / e2e / manual | not_run |
| live | not_run；官方 taxonomy 实际加载、真实供应商行为/费用及账户授权仍 `blocked_live`，本轮禁止网络/凭据读取 |

F2/P2 证据是四维候选的更严格来源与条件边界、未知比较和维度故障隔离；R1 仅沿用文献固定身份/partial 拒绝回归。没有性能、accuracy、recall、九维完整产品效果、真实 PG 发布/重放、持续运行或人工评分证据。本轮公开接口及计划无偏差，只有有理由的合成正例输入更新；原 T 卡全部条件和完整项目目标保留。

下一项建议：由原非作者 reviewer 固定本轮代码与材料重跑两 Must 和保留的原探针，主控据其意见登记；之后另行受控接线和授权 live。实现者在本切片停止，不自行 accepted，不推送。

未检查：真实官方 commit 内容真实性、跨块/跨段/隐含条件语义、PG/worker/API/UI、真实模型出网与费用、生产并发吞吐、人工标注和最终评分验收。
