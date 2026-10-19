# G-C / R06-B · 仓库与社区适配器独立评审 1

评审人：`/root/r06_repository_community_independent_review`，非作者。评审结论：**needs_changes，先修 Must 1**。不登记 accepted、不 push、不改业务或进度。

文档首次创建：2026-10-15T18:56:11+08:00；最后更新时间：2026-10-15T18:57:00+08:00。
证据截止：2026-10-15T18:54:10+08:00。独立工作目录：`D:/wt/r06-repos-review`，detached HEAD；创建前核对该路径不存在及 worktree 清单，未修改作者 `D:/wt/r06-repos`。

| 冻结项目 | 值 |
|---|---|
| 被审完整 SHA | `5e952f25d7a1c03296e1a8801a757c9c0317af99` |
| 被审完整 tree | `c99ba0178c781e3d48555b5ddbd8d9743c420d8a` |
| 业务代码 SHA / tree | `e5b48ae4db4c1e77a08d830ce12eb63ab3d49c39` / `ac960dc28edf3d4c058b3b7b1d43566b2cf3145e` |
| 比较基线 | `1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc` |
| 变更比较 | `git diff 1ff54965a0dd2e4f4a13245cee8dd59d2b3fdcfc...HEAD` |
| 独立证据目录 | `reports/runs/recovery_r06_repository_community_review_1_20261015/` |

What this change does: 本批新增固定 Ollama release 与 AVID 0.2 正文的纯解析器，收紧 commit 标识，并为 OSV 新增独立范围分支、保留兼容字段。没有接入产品采集、数据库、worker 或界面；本结论仅评审内部适配器可合并行为。

## 1. 依据、覆盖范围及独立性

已读取冻结 AGENTS、`docs/plan/00_execution_map.md`、恢复任务卡 R06、原 T11/T13、03/04/05/06 与其引用的 07 合同、manifest 中 R06 的能力前置、`progress/task_state.json`、作者报告与 run 证据。冻结状态仍将 R06 记为 pending、T11/T13 为 needs_changes，历史 accepted 说明不作为当前能力证据。采用最新 Ponytail 5.2 `ponytail-review/SKILL.md` 与 `ponytail/SKILL.md` full；按主控明确边界独立完成，没有再派 agent。

逐文件审查 4 个业务文件：`github_releases.py`、`avid_records.py`、`osv.py`、`repository.py`；5 个新增测试：release、AVID、OSV、commit 的 unit 与真实样本 contract。检查源码整体和调用函数，不只看 diff；`git diff e5b48ae HEAD -- backend` 为空，证据提交没有再次改变业务内容。

先实际查看 CBM 0.11.0 总 help 与 index/schema/trace 参数，再建立独立 full 源码索引，读取 schema，追踪 `normalize_osv_record`、`normalize_repository_record`、`normalize_community_article`、`bounded_package_query`。后续将 help 输出补存于本轮 run。范围仅 `/mnt/d/wt/r06-repos-review/backend/src`，缓存在仓外 `/tmp/dianzi-cbm-r06-repository-review-1-20261015`；WSL Ubuntu-22.04 官方 portable 为 `/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp`。独立项目 `dianzi_r06_repos_review_1_5e952f2`：1103 nodes、5363 edges、0 not_indexed / partial / unusable。源码图未索引测试，include-tests 参数不会凭空提供测试边；因此另以 `rg` 全 src/tests 追踪，共同核对 caller、旧 DTO、range 字段和新增私有 helper。缓存未提交。

真实 caller 核对结果：repository normalizer 的源码调用方只有新 release adapter；community normalizer 的源码调用方只有新 AVID adapter；OSV normalizer 和 bounded query 没有产品 caller。测试调用方与原 T11/T13 已逐项查看。图的边数或零 caller 本身不构成业务正确性证明。

本批没有 IO/数据库写入或 Claim/Assessment 修改，没有改 `source_jobs`、`source_documents`、迁移、认证、路由或公共 schema。因此可与当前 G-B 事务修复安全独立审查；本次通过的纯解析行为不会证明 G-B 事务正确，也不穿过 G-C、产品 live 或最终验收门。

## 2. Must fix

1. **[P2] OSV 显式 null 数组被当成缺失，坏记录返回正常结果**

   - **What this is：**OSV 关系、affected、ranges、events、versions 应保留字段类型和缺失状态。位置：`backend/src/ai_intel/ingestion/sources/osv.py:67–72` 的 `_string_tuple`、`:93–103` 的 `_objects`，以及调用处 `:122–124`、`:129`、`:142`、`:147`、`:163`。
   - **Problem：**触发最小 JSON 是 `{"id":"OSV-REVIEW","affected":[{"ranges":[{"type":"SEMVER","events":null}]}]}`；预期明确抛 `OsvContractError`，调用方保存原文并隔离。实际正常返回 `PackageRange(range_type='SEMVER', events=(), unsupported_scheme=False)`，没有异常。`aliases:null`、`related:null`、`upstream:null`、`affected:null`、`ranges:null`、`events:null`、`versions:null` 全部同样返回成功；7 条独立断言两次稳定失败。原因是 `payload.get(...)` 不区分缺键与显式 null，再由两个 helper 的 `None → 空集合` 分支吞掉类型错误。
   - **Fix：**在允许缺省的 caller 使用 `.get(field, [])`，两个数组 helper 仅接受 list，显式 null 继续抛 `OsvContractError`；保留缺键允许的既有合同。不要修改 schema、正式金标、分母、覆盖门或把这 7 项改成 skip。最小复验是这 7 条拒绝断言、缺键兼容例、原 T11 六项、多分支/unknown range 例，以及全 unit/相关合同和静态检查。
   - **If we skip it：**本批已实际把结构错误变为受支持的空范围或空关系，破坏 AGENTS §4 严格输入边界/不返回伪默认成功，以及 03 §1 区分缺失与未知、T11 实施 §6 schema 验证。下游一旦接线可误把坏结构当正常数据；本次没有产品 caller，未声称已经观察到资产误判。

复现脚本：`test_independent_boundaries.py::test_present_null_array_is_not_missing_or_success`。精确输入与实际输出在 `review_summary.json.null_array_reproductions`；来源标记 is_synthetic，未用实现结果生成预期。红例原日志与 JUnit 分别为 `independent_boundary_regression.*`、`independent_boundary_recheck.*`。缺陷是实证，不只是缺测猜测；当前版本尚未修复、不能标关闭。

## 3. 通过的具体行为与原始证据

Ollama 真实 release 原文数值 id 为 413093320，tag `v0.40.5-rc0`、name `v0.40.5`、draft=false、prerelease=true、target_commitish=`main`；不能从显示名称推断正式稳定版，也不能把 main 当 SHA。独立断言原文 flags/body 的实际类型和值、名称/tag 改动后身份不变、release 类型不变、正文安全字样不产生确认漏洞或执行路径。日期原字符串 `2026-10-14T19:45:22Z` 留存，缺日期为 None；没有把观察时间代替源时间。

AVID 两条分别是 AVID-2023-V001/V002，确为 `data_type=AVID`、`data_version=0.2` 的正文，而不是目录。标题来自 `problemtype.description.value`，正文来自 `description.value`，固定身份来自 `metadata.vuln_id`；原始 references 含 MITRE/论文/代码元数据。解析器不从自由文本标签制造 CVE，不自动获取或执行引用。两个 date-only 均 `2023-03-31`，未补午夜 UTC；识别引用列表为空不能推断无风险。

OSV 真实样本为 GHSA-fccc-8m69-8r78，aliases 实际为 CVE-2025-0315、GO-2025-3557，Go 包为 `github.com/ollama/ollama`，SEMVER 范围为 introduced=0 / last_affected=0.3.14，modified 纳秒字符串完整保留。独立检查同类型不同仓库分支、不同类型分支及 unknown range/boundary 各自存储；旧 ranges_type/events/explicit_versions 兼容未删，related/upstream 不并入 alias。未知生态名、扩展字段完整留 raw；正常化不进行版本比较，未知 ECOSYSTEM 比较能力仍由 R11 返回 unknown/unsupported，不能因此函数的 known range_type 声称生态受支持。未知 schema major/错误形态明确失败，兼容的 1.x minor/patch 与扩展字段留存。

独立原字节核验见 `evidence_verification.json`：5 份响应正文均与 metadata sha256/尺寸相等，Ollama 与 OSV 逐字节等于已审准备包副本。AVID 两份 API base64 解码等于提交的 record 文件，Git `blob <len>\0<bytes>` SHA1 等于 API SHA；正文 SHA256 分别 `5fb9c019fe2aed64302b2182b2c297f499a3201349ce3c252acd4a409c096667`、`adf28092a120e1e584b2195428629f56824db4085fb6f88e7179e4400577f65b`，尺寸2195/2497。冻结 run 全部64个 Git blob 均与 checkout 原字节相等。

作者公开探测实发3 GET、3 HTTP200，起始18:23:42/49/56+08，间隔7秒，15秒/2MiB/0 redirect/0 retry/无凭据参数，与 saved metadata/probe 源码一致；headers 的 UTC Date 与 quota remaining59/58/57留存。reviewer 新网络请求为0，没有付费 API、读秘密/env/DPAPI/holdout，也未运行外部 PoC。许可依据继承冻结准备包的官方 AVID MIT 来源说明；未重新联网检查，未把仓库许可扩张为所有引用论文的公开再分发许可。

**接线前置限制：**RepositoryRecord 未返回 draft/prerelease/body/canonical URI，CommunityArticle 未返回源日期精度及所有原始引用。主控必须先持久化完整原始页/API blob/解码正文及来源标识，再将日期、flags、body 和证据位置按相应合同用于产品；只存 DTO 会丢信息。此处是当前内部切片边界与后续接线必需条件，没有把未实现 PG raw→revision→outbox/cursor 标为通过。

## 4. 独立实际执行

独立 runtime：`D:/dianzi-runtime-cache/r06-repository-community-review-1/venv`，CPython3.12.13，`uv sync --offline --frozen --project backend` 使用原 lock，未联网安装。设置唯一非秘密配置 UV_PROJECT_ENVIRONMENT 为该仓外目录；后续 sync 复核有命令证据。下表不是作者日志转录，均是本 reviewer 的真实执行；完整 argv/cwd/秒级+08起止/exit 在对应 `.command.json`，输出和失败未覆盖。

| label / cwd | 起止（2026-10-15，+08:00） | exit / 实际结果 |
|---|---|---|
| unit_contract_security / WT/backend | 18:47:30–18:48:25 | 0；1212 pass / 0 fail / 0 error / 0 skip；coverage70.83%，原60门 |
| independent_boundary_regression / WT/backend | 18:50:39–18:51:22 | 1；1229 pass / 8 fail / 0 error / 0 skip；70.84% |
| independent_boundary_recheck / WT/backend | 18:52:41–18:53:20 | 1；1230 pass / 7 fail / 0 error / 0 skip；70.84% |
| mypy / WT/backend | 18:48:35–18:48:35 | 0；84 source files，无问题 |
| ruff / WT/backend | 18:48:35–18:48:35 | 0；业务/测试9文件 |
| format / WT/backend | 18:48:35–18:48:35 | 0；9 files already formatted |
| cbm_index / WT | 18:47:30–18:47:36 | 0；独立源码图 |
| cbm_schema / WT | 18:48:06–18:48:12 | 0；实际图schema/diagnostics |
| cbm_trace_normalize_osv_record / WT | 18:48:35–18:48:39 | 0；both/depth3/源码0 caller |
| cbm_trace_normalize_repository_record / WT | 18:48:39–18:48:43 | 0；新release caller |
| cbm_trace_normalize_community_article / WT | 18:48:43–18:48:46 | 0；新AVID caller |
| cbm_trace_bounded_package_query / WT | 18:48:46–18:48:51 | 0；源码0 caller |
| evidence_integrity / WT | 18:51:50–18:51:54 | 0；raw/blob/gzip/retained bytes核验 |
| frozen_diff_check / WT | 18:51:50–18:51:50 | 0；完整冻结 diff --check |
| environment_sync_recheck / WT | 18:52:41–18:52:41 | 0；frozen/offline sync |
| review_summary / WT | 18:53:42–18:53:42 | 0；JUnit真实计数/原触发输入与实际输出 |
| cbm_help及三个tool help / WT | 18:53:42–18:53:45 | 0；补存最初已实际查看的CLI说明 |
| reviewer_artifact_ruff / WT | 18:54:09–18:54:10 | 0；本reviewer4个脚本 |
| reviewer_artifact_format / WT | 18:54:10–18:54:10 | 0；本reviewer4个脚本 |

1212 项包含1089 unit、原 T11六合同+T13六合同+真实样本三合同、108 network/source security。独立新增25项，其中18通过、7个 null 拒绝断言失败；新增检查没有替换旧测试。两次扩展运行均保留原60覆盖率门，6822 statements 未变，未降低阈值或使用 skip。每次唯一 warning 为既有 StarletteDeprecationWarning。

运行命令核心为 `python -m pytest tests/unit tests/contract/test_t11_osv_connector.py tests/contract/test_t13_community_repository_connectors.py tests/contract/test_r06_repository_source_samples.py tests/security/test_t08_network_and_sources.py tests/security/test_r03_network_transport.py`；扩展运行追加 `../reports/runs/recovery_r06_repository_community_review_1_20261015/test_independent_boundaries.py` 和各自 JUnit 路径。

扩展首跑的第8项失败是已有 `test_r05_process_limits.py::test_real_native_cpu_limit_terminates_busy_child`，subprocess8秒 timeout；第一次1212运行及一次有限1237复跑中均通过。未更改该测试、超时、代码或环境限制，未转skip。已保留首次失败原文；目前只能记录一次波动，根因未确认，不能将其推断为本适配器造成或将它从失败计数移除。复跑停止于7个确定的 null 缺陷，不无限重复测试。

## 5. 作者历史失败材料及空白例外

亲自 gzip 展开两归档后，核对原文件/归档双sha256与尺寸，并读取作者 WT 的未跟踪原文件比较，完全相等；`git status --untracked-files=all` 仍显示两个原文件，未删或修改。

| 原文 | 原尺寸 / sha256 | 归档尺寸 / sha256 |
|---|---|---|
| focused_post_implementation.log | 17016093 / `27b5ca1092f4ac37c884d36308d4bc0773a27e23d4321a83f02c306f34d49668` | 30819 / `fde9d2a29d9394d2e15b5ce3c4a39c1cac6889e98210a4ea5116f463e3e8d000` |
| focused_post_implementation.junit.xml | 4484295 / `de7851265ee872b3e267df7367248f6d8c20849094694cc1141de706ef105af4` | 28826 / `c1ba12b2ed0a1af9faad67ae47c1f2a842710a6460c7aa32b57935eeabf3660c` |

展开的 JUnit testsuite 仍为1106 / 2 failures / 6 errors / 0 skipped；两条失败真实样本预期错误的名称仍在，Windows超长pytest node id错误亦保留。真实 raw 支持作者将 release title 预期纠正为name `v0.40.5`、OSV aliases纠正为两实际标识、range纠正为SEMVER；不是通过修改正式金标或计分分母。reviewer独立原文断言再次通过，但作者历史错误没有被消失。

`.gitattributes` 的 `* -text whitespace=cr-at-eol` 只在作者本 run 目录生效；`git check-attr` 对该目录正文是text unset/cr-at-eol，业务 `osv.py` 与 unit测试均 unspecified。它仅保存原始 CRLF 字节，不是全仓忽略；本轮完整冻结 diff --check 退出0，并逐blob确认真实原字节，没有靠修改采样字节消除hash差异。

## 6. 未检、偏差、评分证据与下一步

未检：新来源实时权限/429/分页/回补/并发/重启/持续窗口、PG事务与raw/revision/outbox/cursor、产品worker接线、SourceKind注册、API/UI/frontend/e2e、真实性人工核验、费用/性能/正式评测。相关 source security 是离线transport/边界回归，不能代替新源的真实错误探测。外部 live 按整卡仍未完成，日期缺失/未来/精度必须在集成时单列；没有签R06、T11、T13整卡或G-C。

本次确认偏差仅 Must1：显式 null 类型错误被吞成缺省。其余已检查实现与内部授权范围一致，没有依赖主版本、公共合同、指标分母、金标或认证变更。DTO缺信息以原文持久化作为后续必需合同，不能据此声称接线已完成。

评分证据：F1/F2 只取得release/社区/OSV真实离线解析及稳定身份、原始证据/范围分支能力；E1只取得边界/回归与真实失败保留；P1无持续时效、P2无资产判断或正式准确率证据。原 T13-C04/C05/C06 等 guard/元数据合同复跑通过，但历史持久化/真实权限/PoC运行没有被这些纯函数证明。

本 reviewer 仅交付此报告及自己的 run 目录；业务、shared、progress、金标和门槛均未改。主控实际秘密逐值扫描仍由主控完成，本人未读取真实秘密。

下一步：作者先在独立分支按 Must1 最小修复，补缺键与显式 null 的回归，冻结新的代码/证据 SHA；再安排定向独立复核。报告不等待作者修复，不自行合并或登记 accepted。

**Verdict: fix 1 first.** 本纯内部批次当前不 Ship；产品 live、整卡与阶段门保持未通过。Lean：未发现具有具体触发影响、需要另外删减的代码项。
