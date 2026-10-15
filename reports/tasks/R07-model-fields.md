# R07 模型字段候选切片

状态：`awaiting_review`；本切片候选能力实现 `complete`；整体 R07 仍需主控接线、独立 review 与 live，不自行验收。

基础提交 `cb34097898b412390ee7e119d0d5c2c90d090673`；代码冻结提交 `6463e62bd0504e6cf83fd84b6d64c8bbfd33f994`；独立工作树 `D:/wt/r07-model-fields`、分支 `codex/r07-model-fields`。本地记录采用实际 UTC 时刻，首个 CBM 索引 2026-10-15T16:24:00.139078+00:00 至 16:24:16.328071+00:00，最后回归 16:38:12.375501+00:00 至 16:38:20.536291+00:00。对应北京时间为 2026-10-16。最终交付 manifest 另记封存时刻。

## 范围与输入输出

本轮读 AGENTS、执行索引、恢复 R07/R09、03/04/05/06 合同、原 T13/T20/T22/T23、两份 R07 core 变更记录与既有 domain、enrichment、模型适配源码。Ponytail 插件 5.2 full 生效。本轮只新增两业务模块、三直接测试、当前报告和自有 run。未修改公共 schema、领域合同、认证、锁、依赖、迁移、API、loader、worker、PG 发布或共享进度。

`generate_model_field_attempts(context, documents, client, *, budget_authorized, content_is_private, egress_granted, total_output_token_budget=4096) -> ModelFieldResult`。`context` 与 `documents` 使用冻结 `EnrichmentContext/EnrichmentDocument`，服务端负责选择认证可见、有效且固定的 revision。`ModelFieldResult.attempts` 固定按 ATLAS、versions、literature、poc 返回四个 `DimensionAttempt`；`model_attempts` 原样保存既有 `AttemptMetadata`。主控应把它们记入自己的 PG 作业轨迹，不把本地结果当业务状态权威。

每维单独调用已有 `GenerationClient.generate`，复用 OpenAI/Anthropic（含既有 DeepSeek 兼容 codec）的真实受控网络接口。最多四个请求，无格式修复、无请求重试、无其他提供者或 fixture 产品回退。输出 token 上限按总额除四逐维分配；少于四或超过 8192、bool/float 均拒绝。模型原始响应经既有严格 JSON/Pydantic 解析，额外支持、身份、tenant、authorization、origin、review、target UUID 字段拒绝。每次网络时限来自已配置 client（上限 120 秒）；四次串行总网络等待上限为四倍该时限，另有本地处理开销。本模块不读取环境凭据、价格或预算秘密；费用沿用 `unknown`，不填零。

`field_sources.py` 单独测试证据与字段判断。先重新验证固定输入、块 SHA 和 context 范围，拒绝资产清单进入源文本；再验证 block-relative Unicode 左闭右开偏移、revision/block 精确身份、quote 与 SHA、重复定位以及完整源行，不能靠摘掉局部条件获得候选。最终出版仍需主控回查权限、有效修订、语义和发布策略。

## 四维实现与限制

| 维度 | 实际能力 | 缺口与保守结果 |
|---|---|---|
| ATLAS | 从已加载官方 `atlas.mitre.org` 或 MITRE atlas-data 文档引用 technique、固定 taxonomy 版本与事件机制；机制和已识别前置保留原行 | 没有完整 taxonomy/source_version 则 `pending/atlas_taxonomy_missing`，不调用 ATLAS 模型。官方域名和 service provenance 是必要条件；不是来源真实性或机制映射正确性的完整证明。映射始终 `MODEL_HYPOTHESIS` |
| 版本 | package/ecosystem、原始完整受影响表达式、introduced/fixed/last_affected、explicit versions/branch、厂商修复与一般缓解分离；数值边界必须有对应原文操作符 | 本切片不运行版本比较器。PyPI/PEP440 和 npm/SemVer 比较结果保持 unknown，git/unknown/未支持生态显式 unsupported。无法解释的范围不猜；否定或未知不能产生正向 affected 区间。支持英文明确操作符/标签和部分中文状态，其他自然语言交给 review |
| 文献 | 精确 title+URI 同一源句、extractive support_summary、paper/article/standard/policy 与关系；准确 canonical URI 唯一命中服务选定文档时绑定 document+revision UUID | target UUID 禁模型填。多修订目标歧义拒绝；未加载目标只保留未绑定链接候选。metadata/excerpt/unknown/不完整正文只能背景候选，不能升级全文分析/实验结论 |
| PoC | 有类型依据的精确标题、链接与固定 commit/路径/许可元数据候选；关键字段需源证据 | `candidate_found` 只表示源材料中存在链接候选。本模块不请求链接，不下载、不 clone、不审核代码、不执行。模型不能自填 static_reviewed/lab_verified，真实静态审核须另有服务端记录 |

合法候选统一 `MODEL_HYPOTHESIS`，维度 `pending/model_hypothesis_requires_review`，不输出 available 或 supported。缺证据仍 pending，不把“本次输入没有”写成全网 not_found；跨候选版本矛盾并列保存、重复同值去重，不合并成受影响范围。某维模型错误或证据错误不抹掉其他维候选；同维一个非法候选也不抹掉该维另一个合法候选。字段检查只核查 extractive 一致性及有限确定性边界，不声称完整语义证明或准确率。

## 改动文件与调用方

- `backend/src/ai_intel/enrichment/model_fields.py`
- `backend/src/ai_intel/enrichment/field_sources.py`
- `backend/tests/unit/test_r07_model_fields.py`
- `backend/tests/contract/test_r07_model_field_contract.py`
- `backend/tests/security/test_r07_model_field_security.py`
- 本报告和 `reports/runs/recovery_r07_model_fields_20261016/`

实现前 CBM 0.11.0 独立 cache `/tmp/dianzi-cbm-r07-model-fields-20261016`，project `r07-model-fields-src`，只索引当前 WT/backend/src，persistence=false；1289 nodes/6409 edges，零未索引/partial/unusable。真实 schema、architecture、generate trace 与 rg 源码相互核对，既有 generate 入站为 grounding 与 question service。冻结代码刷新 1325 nodes/6615 edges；新候选函数连接真实 generate→网络网关→严格解析→证据/四字段校验；图中无生产调用方，rg 确认只有本包测试调用。主控接线后必须在新版本重新核对调用方；不能据图边声称产品链路已通过。未索引秘密、holdout、附件或报告。

## 实际验证

所有命令、cwd、开始/完成时刻、exit 与完整 stdout/stderr 都在同名 `.command.json/.log`。以下 Python 使用已经存在的 `D:/dianzi/backend/.venv/Scripts/python.exe` 3.12.13，`PYTHONPATH` 指向本 WT/backend/src；未安装依赖。

| 检查 | 实际命令概要 | 结果与日志 |
|---|---|---|
| 新测试初始收集 | `pytest -o addopts= -v` 三个初始同名文件 | exit 2，45 collected/2 collection errors；同名 module 冲突为测试布局错误，不冒称业务失败，`tests_initial.*` 原样保留 |
| 布局修正后 | 三个唯一 basename 文件 | exit 1，52 passed/7 failed；PoC 私有 subclass roundtrip 未转回冻结基类一项修复；六项安全测试误写网关错误码修正为既有 model_format_invalid，不改原测试/金标。`tests_after_collection_fix.*` 保留 |
| 修正与边界 | 新测试三文件 | `tests_field_fix1.*` 59 passed；`tests_boundary.*` 73 passed/1 synthetic enum warning，随后测试构造改用 DocumentKind enum，最终无 warning |
| 最终相关回归 | `pytest -o addopts= -v` 新三文件 + r07 contracts/t19 structured + r05 generation/review fixes + t18/t20/t22/t23 原合同 | exit 0，236 passed/0 failed/0 skipped/0 warnings。新 unit 56、contract 4、security 16，既有回归 160。`sealed_regression.log/.command.json`、`regression.xml`（最后一次结果） |
| 静态 | `ruff check`、`ruff format --check` 五文件；`mypy --config-file pyproject.toml` 两业务文件 | 全部 exit 0；`sealed_ruff.*`、`sealed_format.*`、`sealed_mypy.*`。自有 run 脚本也经 backend Ruff/format 检查 |
| diff | `git diff --check`；提交前业务五文件 `git diff --cached --check` | 业务代码 exit 0；无公共合同、依赖或用户文件修改；冻结 patch 和 SHA 清单见 manifest。全包 diff --check exit 2，原因仅原样留存的 CBM EOF 空行、pytest 失败日志/XML 空白行尾空格；`delivered_diff_check.*` 保留，不修改原始失败证据、不添加忽略规则 |
| 安全模式 | 复用 `scripts/security_scan.py` 的原 PATTERNS，仅扫当前五文件与自有 py/json/log | exit 0，56 files/0 findings，`sealed_secret_scan.*`；未读取任何秘密值或调整分类/忽略表。是文件范围扫描，不冒称全仓安全验收 |

旧 `regression.log/.command.json` 记录添加 limitation 三项负例之前的 233 passed；同一成功 JUnit 路径在最后回归刷新为 236，故最终 XML只对应 sealed_regression，本报告不把它归于旧 233 次命令。所有失败日志/XML独立命名保留。

正常、缺失、不同源矛盾、同维部分失败、格式错/重复 JSON 键、跨修订/块/坐标、源条件裁断、前置丢失、vendor/mitigation 混淆、unsupported、元数据半文、错误 URI/title/commit/license、模型自填身份/支持、外发/预算拒绝均有真实执行断言。fixtures 明确位于 unit/contract/security，并通过 monkeypatch 替换现有 HTTP 边界；不作为产品模式，也不计真实模型能力、外部对照或官方准确率。

## 未运行、偏差与交接

integration/live/frontend/e2e/manual = `not_run`。本作者外部模型/来源请求为 0；无真实 taxonomy 采集或四维模型输出实测，不能填 live_verified。预算和凭据由主控后续授权环境注入；真实模型 refusal、网络、超限仍须受控 live。两个 core CR 在当前 base 仍 awaiting_review，只能作为独立候选开发前置，不能替代最终验收。

未发生公共合同、依赖主版本、指标、阈值、分母或计划变更。私有 extraction schema 缩窄权限和输出，不进入公共 schema。因本包只实现候选，原 T13/T20/T22/T23 的完整六项验收、R09 知识卡、R11 比较器和 R07 九维产品效果仍保留，未签整卡。F2/P2 的证据是四维真实接口代码、确定性源字段拒绝和失败隔离；R1 仅文献固定目标/类型/coverage 候选能力。首次报告封存脚本引用旧 timezone 名称导致 NameError，修正为现有 UTC 后成功；`seal_initial_failure.json` 保留 exit 1 与未捕获命令时刻的事实。业务代码、失败测试、金标均未由此变化。

主控下一步：将 `result.attempts` 和 `model_attempts` 接入唯一 PG worker/job/出版链，出版保持 model_hypothesis→unverified 并重新核对 ACL、固定修订及支持关系；加载已许可的真实 ATLAS 固定版本资料；在已授权调用/费用边界内受控验证两种真实 codec 与四维源证据；冻结集成版本交由新非作者 review。未 push、未修改 shared state、未自签 accepted。
