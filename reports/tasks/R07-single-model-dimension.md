# G-C / R07 · 单任务单模型维度入口

记录时间：2026-10-16T02:57:31.916287+08:00，实际上海时间（本报告限定扫描 receipt 起点）。状态 `awaiting_review`；本接口切片实现 `complete`，unit / contract / security `passed`。整 R07、原 T 卡和 G-C 未被本报告验收；本报告作者是实现者，不是独立 reviewer。

本轮将已有真实四维接口拆为可供一个 worker 子任务调用的一个维度入口。未提高 worker 租约，也未改 worker / PG / API / UI / 公共 schema / auth / runtime / generation / migration / lock / progress。主控后续接持久 jobs；本切片没有产品调用方、真实供应商调用或模型 live 证据。

## 固定身份与范围

| 项目 | 值 |
|---|---|
| 主控授权基线 | `cc1b1d302e22048f567475b7084bcd5490761ed2` |
| 必需前置原提交 | `47c47bc2b5d537166ee47a01c2ab14c035466e3d`，已独立 Ship 的共享生成派发前超时修复 |
| 本 WT 前置 cherry-pick | `63e4cafe1363530eb08cdfe7fec56cfc07a81b8a`；前置代码未修改 |
| 本接口代码提交 | `d8a3189bb7bc1cfde24825f5478920e37eac9556` |
| Worktree / branch | `D:/wt/r07-single-field` / `codex/r07-single-model-dimension` |
| 运行解释器 / import 根 | 既有 `D:/dianzi/backend/.venv/Scripts/python.exe` / 当前 WT `backend/src` |
| 运行材料 | `reports/runs/recovery_r07_single_model_dimension_20261016/` |

先读 AGENTS、执行图、恢复 R07/R03、T18/T19/T20、03/04/05/06、CR-R07 候选与 v3 合同、固定 progress/handoff 和前两根因修复/复核报告，使用 Ponytail 5.2.0 full。主控已有用户/控制器未提交修改，未触碰；本 WT 从指定 SHA 新建，开始时干净。固定进度索引中的旧整 R07 pending/not_started 不代表后续候选代码不存在，也不被本实现者改成 accepted。所需候选来源与真实生成接口实际存在；本轮不依赖未授权外部资源。

输入是服务已选定的可见固定修订/块、真实 `GenerationClient` 和明确的模型维度/预算/外发策略；输出仍是 `ModelFieldResult`，仅含所选一个 `DimensionAttempt` 及实际 `AttemptMetadata`。授权边界只允许 `model_fields.py` 和三个新专属测试，另有本报告/新 run 材料；旧专属测试和旧报告/材料未修改。

## 实现和调用合同

新增入口为：

```python
extract_model_dimension(
    context, documents, client, *,
    dimension,
    budget_authorized,
    content_is_private,
    egress_granted,
    total_output_token_budget=1024,
) -> ModelFieldResult
```

仅严格字符串 `atlas / versions / literature / poc` 可调用；空值、未知维度、大小写变体、容器、多维和重复维度形状均在 0 调用时抛现有 typed `FieldEvidenceError("field_dimension_invalid")`。单维总输出预算接受严格 int 的 1..8192，完整传给唯一生成请求，未经许可不静默分割或截断；非法值抛 `field_call_policy_invalid`。

真实 client 的 `limits.total_timeout_seconds` 必须不超过 20 秒，超过即 0 调用时抛 `field_single_dimension_timeout_invalid`。共享 `GenerationClient.generate` 没有 per-call timeout 参数，因此本入口不突变共享 client、不增加构造/凭据读取，也不扩大租约。后续 worker 必须配置独立客户端，令其 total timeout 同时满足 `<=20s` 和该工具预算；更小客户端预算保持原值。此限制约束模型生成的既有整次 deadline，不是对整个 Python 进程/候选 CPU 校验的硬杀死承诺。

旧 `generate_model_field_attempts` 的原签名、默认 4096 总预算、ATLAS→versions→literature→poc 顺序、floor(total/4) 分配与最多四调用保持。两入口只委托同一私有实现；其早期空结果、总耗时上限和预算除数使用所选维数。单维不会先跑四调用再过滤，0 额外 repair。原 `_generate_field` / `allow_format_repair=False` / 来源门禁 / 候选校验 / `AttemptMetadata` 返回完全复用。

主控后续父流程固定每个 child 默认 1024 输出预算、`<=20s` 且最多一个 wirecall；四个模型维度的父默认合计仍为 4096。入口允许显式配置更大单维预算，不计为父流程默认上限提高，也不授予未经批准的费用预算。

| 改动文件 | 内容 |
|---|---|
| `backend/src/ai_intel/enrichment/model_fields.py` | 新增严格单维入口，将旧正文保留为共享内部实现；早期结果只遍历所选维度 |
| `backend/tests/unit/test_r07_single_model_dimension.py` | 41 项：四维单选、1024 默认/显式预算、非法输入、超时配置拒绝、早期结果、固定 ATLAS 门禁、条件/unknown 保留、旧四维兼容、固定时钟派发前超时 |
| `backend/tests/contract/test_r07_single_model_dimension_contract.py` | 44 项：四 provider × 四维成功合同/元数据，四维 × 七失败路径的单调用/no repair |
| `backend/tests/security/test_r07_single_model_dimension_security.py` | 18 项：私有外发拒绝、权限/支持字段提升拒绝、资产清单/fixture client 输入拒绝 |
| 本报告 / 新 run | 真实 receipts、stdout/stderr/JUnit、原 red、draft、CBM、复用探针审计、范围扫描、raw/blob manifest |
| `.gitattributes` | root 对原始输出封存另授权：仅本run/** -text 与实际产生 whitespace 报告的具体 raw log/XML -diff，逐文件理由附后 |

固定官方 ATLAS commit 路径与 `source_version` 匹配仍由共享来源层核验；只做结构绑定，不声称合成 `a×40` 是实际官方 commit。完整版本表达式、必要条件、证据坐标/hash 保留，`comparison_support=unknown`，所有有效模型候选仍为 `MODEL_HYPOTHESIS / PENDING`。引文存在不证明语义支持；PoC 只是 link metadata / candidate_found。无事实发布权限或历史覆盖变化。

## 固定代码验证与原红

每个 `*.command.json` 保存完整真实 argv、cwd、+08 起止、child exit、当时 source SHA 和 PYTHONPATH。`run_command.py` 转发 child exit，不把包装器成功冒充业务通过。最终检查在先提交的 `d8a3189` 上运行，之后 source/test 未修改。pytest 用 `-o addopts=` 做有界套件，未改变原项目 `--cov-fail-under=60`，没有 whole-project coverage 声明。

| 检查 | 实际 child 结果 | 证据前缀 |
|---|---|---|
| 修正夹具后的原代码 red | exit 1；102 failed / 1 passed / 0 error/skip | `baseline_red2.*`，02:51:22.541566–02:51:29.457484+08:00 |
| 新单维三层检查 | exit 0；103 passed / 0 fail/error/skip | `final_new_103.*`，02:53:00.626487–02:53:08.085083+08:00 |
| 原作者指定回归 | exit 0；236 passed / 0 fail/error/skip | `final_original_236.*`，02:53:00.752614–02:53:11.169321+08:00 |
| 原独立 reviewer 47 探针 | exit 0；47 passed / 0 fail/error/skip | `final_original_47.*` |
| 原两根因 46 边界 | exit 0；46 passed / 0 fail/error/skip | `final_original_46.*` |
| 原更底层 gateway 32 探针 | exit 0；32 passed / 0 fail/error/skip | `final_review_32_recheck.*` |
| 前置共享生成超时 | exit 0；17 passed / 0 fail/error/skip | `final_generation_17.*` |
| Ruff / format / mypy | 各 exit 0；四 source/test 文件，mypy 一个业务模块 | `final_ruff.*` / `final_format.*` / `final_mypy.*` |
| Source/test diff check | exit 0；63e4caf→d8a3189 | `final_source_diff_check.*` |
| CBM help/schema/index/qualified traces | 各 exit 0；最终 1391 nodes / 7057 edges，未索引/partial/unusable 0 | `cbm_*.command.json` |
| 原/新调用方 rg | exit 0；无产品 source caller | `rg_callers_pre.*` / `rg_callers_final.*` |
| 限定秘密模式/材料核验 | 实际结果见独立 receipts 与 manifest | `scope_scan.*` / `material_manifest.json` |

最终六组共 103 + 236 + 47 + 46 + 32 + 17 = **481 个通过检查**，不是准确率、召回率、评分分母或性能证据。原 236 套件准确沿用原报告中的十一文件；原 47 从已冻结前置 run 的两个文件重跑；原 46 是 `test_r07_model_field_root_causes.py`。32 探针按字节复制原 reviewer 的 `test_gateway_independent.py`，SHA-256 `7171b4f22fd1f52f54641787fee24e35336a0434b106a7b643a7826e06335234`；其依赖通过显式 pytest pythonpath 指向已冻结原 47 文件，不改探针内容。17 是前置 `test_r05_generation_predispatch_timeout.py`。

新 103 实际执行：

```text
cwd=D:/wt/r07-single-field/backend
D:/dianzi/backend/.venv/Scripts/python.exe -m pytest -o addopts= -q tests/unit/test_r07_single_model_dimension.py tests/contract/test_r07_single_model_dimension_contract.py tests/security/test_r07_single_model_dimension_security.py --junitxml=D:/wt/r07-single-field/reports/runs/recovery_r07_single_model_dimension_20261016/final_new_103.xml
```

原回归及静态/CBM的完整可复跑逐参命令均在相应 receipt，数量从 JUnit 独立读取并保存在 `run_summary.json`。原 red runner 仅从 `63e4caf` 的 Git blob 读取原 `model_fields` 替换当前进程模块，其他来源/生成代码和测试不变；原模块 raw SHA-256 `3a855b58d843e2aaecc42db4a3f86341b0b438f18c90e28e9965062c77027faa`。102 个单维检查因入口不存在而失败，旧四维兼容一例通过；不是环境缺失伪装业务失败。

保留的仪器失败：`original_red` 为 103 failed（其中旧兼容例错误地期望网关地址 list，实际为 tuple）；`green_draft` 为 66 failed/37 passed，同一夹具错误；`green_draft2` 为 5 failed/98 passed，四例空 documents 误构造空 revision_ids 上下文、一例错误预期 timeout 码；`new_draft_green` 为 1 failed/102 passed，极短真实 deadline 会在 schema 前或 slot 等待耗尽不同位置触发不同既有 typed 码。最终改用固定时钟精确验证前置已批准的派发前 `model_network_timeout`，不降低失败标准或修改生成业务。`baseline_red` 有 3 collection error，仅脚本 sys.path 漏 backend；`final_review_32` 有 1 collection error，仅拷贝 probe 的原依赖未入 import path，显式 pythonpath 修正后原 probe 32 项通过。首轮 Ruff 长行/Iterator import 错误也保留，随后格式/import修复。所有原失败日志仍在，无删题、改 skip、金标或阈值变动。

## 调用路径、材料与复用限制

新 tests 不替换 generate / gateway.post_json；实际经过 `GenerationClient.generate → NetworkGateway.post_json → _bounded_fetch → _fetch`，只替换 offline resolver 和底层受控 transport。四 provider codec 的成功各为恰好一个 POST 与一条安全 `AttemptMetadata`；format/network/timeout/401/429/503/302 各仍恰好一个调用，无格式 repair、跳转或失败重试。授权/私有/配置拒绝是 0 transport。这里的 wirecall 是离线 transport 边界观察，真实外部 socket/TLS/DNS/供应商调用为 0，费用仍 unknown，不能计 live/integration。

复用原 32 探针进一步通过真实 `PinnedHttpTransport.request → _HttpResponse`，只替换 connection/socket 边界；这是旧四维行为保持的回归证据，不冒充新增单维已在线验证。当前新单维不做模型 SDK、环境凭据、FOFA、付费网络、PG 或服务启动。

CBM 使用官方 WSL Ubuntu-22.04 root CLI `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`，缓存 `/tmp/dianzi-cbm-r07-single-field-20261016` 在仓外，只允许本 WT `backend/src`，persistence=false；未索引 reports / holdout / 秘密。CLI 初次无 project 的 schema 参数错误未被称为通过，之后先依据已有项目读取 schema 再索引独有 src，最终再读该项目 schema。qualified trace 明确单维/旧入口都连向同一 `_generate_model_field_attempts` / `_generate_field` / GenerationClient / gateway / 来源校验，source callers 0；rg 同时检查原测试、文档和 exports，没有遗漏需改的已有生产 caller。

材料使用一次性 `git -c core.autocrlf=false add` 保留新证据原始字节，不写 Git 配置。首次材料 diff-check 即使限定 cr-at-eol 仍 exit 2，因为原 pytest 输出尾空白和 CBM 原 EOF 空行，日志完整保留；root 随后明确授权本run/** -text，以及这些具体 raw log/XML 的 -diff，逐文件规则与原因附后。未修剪日志，也未扩大 source/test 或全仓 ignore。`final_material_diff_check_recheck` 误用默认 CR 规则，保留的原 Windows CRLF 被识别为尾空白，exit 2 同样保留；恢复原计划中仅材料路径的 cr-at-eol 检查后 `final_material_diff_check_crlf` exit 0，blank-at-eol/eof/space-before-tab 均保持。manifest 同时登记 raw size/SHA-256 与 staged Git blob identity/size/SHA-256，源码另登记 code commit blob 与当前 raw；不因 Windows checkout CRLF 差异冒称二者字节相同。原报告/manifest/日志没有重写。源码仍用原 whitespace 检查，最终源码未变化和 diff-check 两项均 exit 0，见 `final_source_unchanged` / `final_source_diff_check_sealed`。

| 验证层 | 本轮结果 |
|---|---|
| unit / contract / security | passed，仅上述限定离线边界、回归和模式扫描 |
| integration / frontend / e2e / live / manual | not_run |

真实官方 taxonomy 加载真实性、供应商行为与费用仍是后续 `blocked_live` 缺口；它不阻碍本入口的离线开发，也不能在最终验收当通过。F2/P2 的证据是每子任务一个维度的真实 codec/gateway 调用上限、独立故障状态和条件/候选边界；R1 仅沿用文献固定身份及 partial 内容回归。没有完整九维产品、worker持久 jobs、PG发布/重放、准确率/召回、长期监测、吞吐或人工评分证据。

本轮对公共合同、计划、旧测试、依赖和预算分母无偏差。最小复用要求是 caller 使用明确单维入口和独立 `<=20s` 且满足工具预算的批准 client，服务先确定可见固定输入，之后把实际 metadata 持久化；本入口不替 caller 判断权限、当前修订、语义支持或发布事实。

下一项建议：root 另派非作者新 reviewer 固定代码和材料重跑边界，再依据意见登记状态；后续另接 worker/PG jobs。实现者在本切片停止，不 accepted、不 push、不转换 reviewer 角色。

未检查：真实模型/来源出网及费用、官方 taxonomy 下载真实性、跨块/隐含条件语义、持久 worker/PG/API/UI、生产吞吐和人工/最终评分验收。

## 精确 raw 材料属性登记

root 已明确授权仅本 run/** 的 `-text` 和下列原始工具输出的 `-diff`；未放宽 source/test 或全仓检查。原 Git 属性 blob 完整作为前缀保留。完整前后 hash 与规则见 `attribute_adjustment.json`。

| 本 run 内具体文件 | 原始字节保留理由 |
|---|---|
| `cbm_schema.stdout.log` | new blank line at EOF |
| `cbm_schema_final.stdout.log` | new blank line at EOF |
| `final_material_diff_check.stdout.log` | raw diff-check output echoes the preserved pytest trailing whitespace |
| `green_draft.stdout.log` | trailing whitespace |
| `green_draft.xml` | trailing whitespace |
| `green_draft2.stdout.log` | trailing whitespace |
| `green_draft2.xml` | trailing whitespace |
| `new_draft_green.stdout.log` | trailing whitespace |
| `new_draft_green.xml` | trailing whitespace |
| `original_red.stdout.log` | trailing whitespace |
| `original_red.xml` | trailing whitespace |
